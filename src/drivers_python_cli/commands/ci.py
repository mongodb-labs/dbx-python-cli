"""CI command: check Evergreen and GitHub Actions status in one place."""

import json
import re
import shutil
import subprocess
from pathlib import Path

import typer

from drivers_python_cli.utils.repo import (
    find_repo_by_name,
    find_repo_by_path,
    get_base_dir,
    get_config,
    get_evergreen_project_name,
    is_path_like,
)

app = typer.Typer(
    help="Check CI status across Evergreen and GitHub Actions",
    no_args_is_help=True,
    invoke_without_command=True,
    context_settings={
        "allow_interspersed_args": True,
        "help_option_names": ["-h", "--help"],
    },
)

EVERGREEN_UI_DEFAULT = "https://spruce.mongodb.com"
FAILURE_STATES = {"failure", "failed", "failed_tests", "aborted", "cancelled"}
SUCCESS_STATES = {"success", "passed"}


class CIError(Exception):
    """A CI lookup could not be completed."""


def _run(cmd, cwd=None, allow_failure=False):
    """Run a command and return the completed process, or raise :class:`CIError`.

    ``allow_failure`` returns the process even when its exit code is non-zero.
    ``gh pr checks`` needs this: it exits 1 for failing checks and 8 for
    pending checks, yet still prints the JSON report on stdout.
    """
    try:
        result = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, check=False
        )
    except FileNotFoundError as exc:
        raise CIError(f"{cmd[0]} not found on PATH") from exc
    if result.returncode != 0 and not allow_failure:
        stderr = (result.stderr or "").strip()
        message = stderr.splitlines()[-1] if stderr else f"{cmd[0]} failed"
        raise CIError(message)
    return result


def _git_current_branch(repo_path):
    """Return the checked-out git branch, or None when HEAD is detached."""
    try:
        branch = _run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_path
        ).stdout.strip()
    except CIError:
        return None
    return None if branch in ("", "HEAD") else branch


def _git_remote_url(repo_path, remote):
    """Return a git remote URL, or None when the remote does not exist."""
    try:
        return _run(["git", "remote", "get-url", remote], cwd=repo_path).stdout.strip()
    except CIError:
        return None


def _github_repo_from_url(url):
    """Extract ``owner/name`` from an SSH or HTTPS GitHub URL."""
    if not url:
        return None
    match = re.search(r"github\.com[:/]([^/]+)/([^/]+?)(?:\.git)?$", url.strip())
    return f"{match.group(1)}/{match.group(2)}" if match else None


def _github_target(repo_path):
    """Choose the repo that holds CI and PRs, plus the fork owner for the head.

    A fork checkout has ``origin`` set to the personal fork and ``upstream``
    set to the canonical repo. PRs and their checks live on the canonical repo,
    so prefer ``upstream``. The fork owner is still needed to select cross-repo
    PRs from a branch name.
    """
    origin = _github_repo_from_url(_git_remote_url(repo_path, "origin"))
    upstream = _github_repo_from_url(_git_remote_url(repo_path, "upstream"))
    target = upstream or origin
    if not target:
        return None
    head_owner = origin.split("/")[0] if origin and origin != target else None
    return {
        "repo": target,
        "remote": "upstream" if upstream else "origin",
        "head_owner": head_owner,
    }


def _json_from(result):
    output = (result.stdout or "").strip()
    return json.loads(output) if output else []


def _pr_for_branch(target, branch, head_owner):
    """Return the most recent PR for *branch*, or None."""
    head = f"{head_owner}:{branch}" if head_owner else branch
    payload = _json_from(
        _run(
            [
                "gh",
                "pr",
                "list",
                "--repo",
                target,
                "--head",
                head,
                "--state",
                "all",
                "--limit",
                "1",
                "--json",
                "number,state,title,url,headRefOid,headRefName",
            ]
        )
    )
    return payload[0] if payload else None


def _pr_checks(target, number):
    """Return the status checks attached to a PR. An empty list means no checks."""
    result = _run(
        [
            "gh",
            "pr",
            "checks",
            str(number),
            "--repo",
            target,
            "--json",
            "name,state,bucket,link,description",
        ],
        allow_failure=True,
    )
    if result.returncode != 0 and not (result.stdout or "").strip():
        stderr = (result.stderr or "").strip()
        if "no checks reported" in stderr.lower():
            return []
        raise CIError(stderr.splitlines()[-1] if stderr else "gh pr checks failed")
    return _json_from(result)


def _recent_runs(target, branch, limit):
    return _json_from(
        _run(
            [
                "gh",
                "run",
                "list",
                "--repo",
                target,
                "--branch",
                branch,
                "--limit",
                str(limit),
                "--json",
                "databaseId,name,workflowName,status,conclusion,event,url,createdAt",
            ]
        )
    )


def _check_state(check):
    bucket = (check.get("bucket") or "").lower()
    if bucket:
        return {
            "pass": "success",
            "fail": "failure",
            "pending": "pending",
            "skipping": "success",
            "cancel": "failure",
        }.get(bucket, bucket)
    return _normalise_state(check.get("state"))


def _run_state(run):
    if (run.get("status") or "").lower() != "completed":
        return "pending"
    return _normalise_state(run.get("conclusion"))


def _normalise_state(state):
    value = (state or "unknown").lower()
    if value in FAILURE_STATES:
        return "failure"
    if value in SUCCESS_STATES:
        return "success"
    if value in {"queued", "in_progress", "pending", "started", "created", "unstarted"}:
        return "pending"
    return "unknown"


def _overall(states):
    if any(state == "failure" for state in states):
        return "failure"
    if states and all(state == "success" for state in states):
        return "success"
    if any(state == "pending" for state in states):
        return "pending"
    return "unknown"


def _combined_overall(states):
    """Combine per-system results, ignoring systems with nothing to report."""
    known = [state for state in states if state != "unknown"]
    return _overall(known) if known else "unknown"


def _github_status(target, branch, limit):
    result = {
        "target": target["repo"],
        "remote": target["remote"],
        "pr": None,
        "checks": [],
        "runs": [],
        "overall": "unknown",
        "error": None,
    }
    if not shutil.which("gh"):
        result["error"] = "gh not found on PATH"
        return result

    try:
        result["pr"] = _pr_for_branch(target["repo"], branch, target["head_owner"])
        if result["pr"]:
            result["checks"] = _pr_checks(target["repo"], result["pr"]["number"])
            result["overall"] = _overall(
                [_check_state(check) for check in result["checks"]]
            )
        else:
            result["runs"] = _recent_runs(target["repo"], branch, limit)
            result["overall"] = _overall([_run_state(run) for run in result["runs"]])
    except CIError as exc:
        result["error"] = str(exc)
    return result


def _evergreen_ui_url():
    try:
        url = _run(["evergreen", "client", "get-ui-url"]).stdout.strip()
    except CIError:
        return EVERGREEN_UI_DEFAULT
    return url or EVERGREEN_UI_DEFAULT


def _evergreen_status(project, branch, limit):
    result = {
        "project": project,
        "patches": [],
        "overall": "unknown",
        "error": None,
    }
    if not project:
        result["error"] = "no [evergreen.<repo>] project_name configured"
        return result
    if not shutil.which("evergreen"):
        result["error"] = "evergreen not found on PATH"
        return result

    try:
        patches = (
            _json_from(_run(["evergreen", "list-patches", "-n", "100", "-j"])) or []
        )
        matched = [
            patch
            for patch in patches
            if patch.get("project_id") == project and patch.get("branch_name") == branch
        ][:limit]
        ui_url = _evergreen_ui_url() if matched else EVERGREEN_UI_DEFAULT
        result["patches"] = [
            {
                "patch_id": patch.get("patch_id"),
                "patch_number": patch.get("patch_number"),
                "status": patch.get("status"),
                "description": patch.get("description"),
                "create_time": patch.get("create_time"),
                "finish_time": patch.get("finish_time"),
                "url": f"{ui_url}/patch/{patch.get('patch_id')}",
            }
            for patch in matched
        ]
        # A branch can have several patches from repeated pushes or retries.
        # Only the newest patch describes the current state; older failures are
        # history and must not keep the branch red after a retry.
        if result["patches"]:
            result["overall"] = _normalise_state(result["patches"][0]["status"])
    except (CIError, json.JSONDecodeError) as exc:
        result["error"] = str(exc)
    return result


def _resolve_repo(repo):
    config = get_config()
    base_dir = get_base_dir(config)
    if repo:
        if is_path_like(repo):
            return config, find_repo_by_path(Path(repo), base_dir, config)
        return config, find_repo_by_name(repo, base_dir, config)
    return config, find_repo_by_path(Path.cwd(), base_dir, config)


def _icon(state):
    return {
        "success": "✅",
        "failure": "❌",
        "pending": "⏳",
        "unknown": "❔",
    }.get(state, "❔")


def _print_human(report):
    """Print a readable summary of the combined report."""
    repo = report["repo"]
    typer.echo(f"CI status: {repo['name']} (branch: {report['branch']})")

    github = report["github"]
    typer.echo()
    if github["target"]:
        typer.echo(f"GitHub Actions: {github['target']} ({github['remote']})")
    else:
        typer.echo("GitHub Actions: not configured (no GitHub remote)")
    if github["error"]:
        typer.echo(f"  ⚠️  {github['error']}")
    elif github["pr"]:
        pr = github["pr"]
        typer.echo(f"  PR #{pr['number']} ({pr['state'].lower()}): {pr['title']}")
        typer.echo(f"  {pr['url']}")
        for check in github["checks"]:
            typer.echo(f"    {_icon(_check_state(check))} {check['name']}")
        if not github["checks"]:
            typer.echo("    (no checks reported)")
    else:
        for run in github["runs"]:
            typer.echo(
                f"  {_icon(_run_state(run))} {run['workflowName']} "
                f"({run['event']}) {run['url']}"
            )
        if not github["runs"]:
            typer.echo("  (no workflow runs for this branch)")
    typer.echo(f"  Overall: {_icon(github['overall'])} {github['overall']}")

    evergreen = report["evergreen"]
    typer.echo()
    typer.echo(f"Evergreen: {evergreen['project'] or 'not configured'}")
    if evergreen["error"]:
        typer.echo(f"  ⚠️  {evergreen['error']}")
    else:
        for patch in evergreen["patches"]:
            typer.echo(
                f"  {_icon(_normalise_state(patch['status']))} "
                f"Patch {patch['patch_number']} ({patch['status']})"
            )
            typer.echo(f"    {patch['description']}")
            typer.echo(f"    {patch['url']}")
        if not evergreen["patches"]:
            typer.echo("  (no patches for this branch)")
    typer.echo(f"  Overall: {_icon(evergreen['overall'])} {evergreen['overall']}")

    typer.echo()
    typer.echo(f"Overall: {_icon(report['overall'])} {report['overall']}")


@app.callback()
def ci_callback(
    ctx: typer.Context,
    repo_name: str = typer.Argument(
        None, help="Repository name or path (defaults to current directory)."
    ),
    branch: str = typer.Option(
        None, "--branch", "-b", help="Branch to check (defaults to the current branch)."
    ),
    limit: int = typer.Option(
        5, "--limit", "-n", help="Number of workflow runs or patches to show."
    ),
    json_output: bool = typer.Option(
        False, "--json", help="Print a machine-readable JSON report."
    ),
):
    """Check Evergreen and GitHub Actions status for the current branch.

    The command finds the GitHub repo from the checkout's ``upstream`` or
    ``origin`` remote and the Evergreen project from ``[evergreen.<repo>]`` in
    config. It then reports the PR checks (or recent workflow runs) on GitHub
    and the recent Evergreen patches for the same branch.

    Exit code is 1 when CI is failing or neither system could be checked.
    """
    verbose = ctx.obj.get("verbose", False) if ctx.obj else False

    try:
        config, repo_info = _resolve_repo(repo_name)
    except Exception as exc:  # noqa: BLE001 — config errors are user-facing
        typer.echo(f"❌ Error: {exc}", err=True)
        raise typer.Exit(1)

    if not repo_info:
        typer.echo(f"❌ Error: repo not found: {repo_name or Path.cwd()}", err=True)
        raise typer.Exit(1)

    repo_path = str(repo_info["path"])
    branch = branch or _git_current_branch(repo_path)
    if not branch:
        typer.echo(
            "❌ Error: cannot determine the current branch (detached HEAD?). "
            "Pass --branch.",
            err=True,
        )
        raise typer.Exit(1)

    if verbose:
        typer.echo(f"[verbose] Repository: {repo_path}")
        typer.echo(f"[verbose] Branch: {branch}")

    target = _github_target(repo_path)
    project = get_evergreen_project_name(config, repo_info["name"])

    if target:
        github = _github_status(target, branch, limit)
    else:
        github = {
            "target": None,
            "remote": None,
            "pr": None,
            "checks": [],
            "runs": [],
            "overall": "unknown",
            "error": "no GitHub remote",
        }
    evergreen = _evergreen_status(project, branch, limit)

    states = [github["overall"], evergreen["overall"]]
    report = {
        "repo": {
            "name": repo_info["name"],
            "path": repo_path,
            "group": repo_info["group"],
        },
        "branch": branch,
        "github": github,
        "evergreen": evergreen,
        "overall": _combined_overall(states),
    }

    if json_output:
        typer.echo(json.dumps(report, indent=2))
    else:
        _print_human(report)

    if report["overall"] == "failure":
        raise typer.Exit(1)
    if github["error"] and evergreen["error"]:
        raise typer.Exit(1)
