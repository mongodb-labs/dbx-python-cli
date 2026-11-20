"""Sync command for syncing repositories with upstream."""

import base64
import io
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

import typer
from rich.console import Console, Group
from rich.markup import escape
from rich.panel import Panel
from rich.text import Text

from drivers_python_cli.utils import repo
from drivers_python_cli.utils.output import paginate_output, should_use_pager
from drivers_python_cli.utils.release import BUCKETS as _BUCKETS
from drivers_python_cli.utils.release import classify_commit as _classify_commit
from drivers_python_cli.utils.release import git_out as _git_out
from drivers_python_cli.utils.release import latest_release_tag as _latest_release_tag
from drivers_python_cli.utils.repo import is_worktree

app = typer.Typer(
    help="Sync repositories with upstream",
    no_args_is_help=True,
    invoke_without_command=True,
    context_settings={
        "allow_interspersed_args": True,
        "help_option_names": ["-h", "--help"],
    },
)

console = Console(highlight=False, soft_wrap=True)
err_console = Console(stderr=True, highlight=False, soft_wrap=True)


def _echo(message, style=None, err=False):
    """Print one line through Rich, with optional style and stderr routing."""
    if not isinstance(message, Text):
        message = Text(message, style=style)
    (err_console if err else console).print(message)


STATUS_STYLES = {
    "synced": "green",
    "dry_run": "cyan",
    "skipped": "yellow",
    "failed": "red",
}
STATUS_ICONS = {
    "synced": "✅",
    "dry_run": "🔍",
    "skipped": "⏭️ ",
    "failed": "❌",
}
STATUS_LABELS = {
    "synced": "synced",
    "dry_run": "checked",
    "skipped": "skipped",
    "failed": "failed",
}


def _print_repo_panel(repo_name, status, lines):
    """Print one repo's buffered steps in a panel."""
    console.print(
        Panel(
            Group(*lines) if lines else Text("No output", style="dim"),
            title=f"[bold cyan]{escape(repo_name)}[/]",
            border_style=STATUS_STYLES.get(status, "dim"),
            padding=(0, 1),
        )
    )


def _print_overall_panel(title, counts):
    """Print the final summary panel with one row per outcome."""
    rows = []
    for status in ("synced", "dry_run", "skipped", "failed"):
        count = counts.get(status, 0)
        if count:
            rows.append(
                Text(
                    f"{STATUS_ICONS[status]} {count} {STATUS_LABELS[status]}",
                    style=STATUS_STYLES[status],
                )
            )
    border = "red" if counts.get("failed") else "green"
    console.print(
        Panel(
            Group(*rows) if rows else Text("Nothing to do", style="dim"),
            title=f"[bold]{escape(title)}[/]",
            border_style=border,
            padding=(0, 1),
        )
    )


def _sync_repo_list(repos, header, ctx, verbose, force, dry_run, config=None):
    """Sync a list of repos, print a header and a summary, and honour the pager flag."""
    use_pager = should_use_pager(ctx, command_default=False)

    if use_pager:
        output_buffer = io.StringIO()
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        sys.stdout = output_buffer
        sys.stderr = output_buffer

    try:
        _echo(header.strip(), style="bold")

        counts = Counter()
        for repo_info in repos:
            lines = []
            status = _sync_repository(
                repo_info["path"],
                repo_info["name"],
                verbose,
                force,
                dry_run,
                upstream_branch=repo_info.get("upstream_branch"),
                preferred_branch=repo.get_preferred_branch(
                    config, repo_info.get("group", ""), repo_info["name"]
                )
                if config
                else None,
                lines=lines,
            )
            counts[status] += 1
            _print_repo_panel(repo_info["name"], status, lines)

        title = "✨ Dry run complete!" if dry_run else "✨ Done!"
        _print_overall_panel(title, counts)
    finally:
        if use_pager:
            sys.stdout = old_stdout
            sys.stderr = old_stderr

    if use_pager:
        paginate_output(output_buffer.getvalue(), use_pager)


def _current_branch(repo_path):
    """Return the currently checked-out branch, or an empty string if unavailable."""
    try:
        return subprocess.run(
            ["git", "-C", str(repo_path), "branch", "--show-current"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except subprocess.CalledProcessError:
        return ""


def _local_branch_exists(repo_path, branch):
    """Return True if ``branch`` exists locally in ``repo_path``."""
    return (
        subprocess.run(
            [
                "git",
                "-C",
                str(repo_path),
                "rev-parse",
                "--verify",
                "--quiet",
                f"refs/heads/{branch}",
            ],
            check=False,
            capture_output=True,
            text=True,
        ).returncode
        == 0
    )


def _default_sync_branch(repo_path, preferred_branch=None):
    """Return the branch sync must operate on, or None if none exists locally.

    The configured ``preferred_branch`` wins; otherwise ``main``, then ``master``.
    """
    for branch in [preferred_branch, "main", "master"]:
        if branch and _local_branch_exists(repo_path, branch):
            return branch
    return None


def _has_local_changes(repo_path):
    """Return True if tracked files are modified or staged.

    Untracked files are ignored: ``git switch`` does not move them, so they do
    not block a branch change.
    """
    result = subprocess.run(
        ["git", "-C", str(repo_path), "status", "--porcelain", "--untracked-files=no"],
        check=False,
        capture_output=True,
        text=True,
    )
    return bool(result.stdout.strip())


def _sync_all_branches(
    repo_info,
    config,
    verbose,
    force,
    dry_run,
    no_ci=False,
    branch_filter=None,
    backport_report=False,
    show_all=False,
    security_only=False,
):
    """Sync branches in a repo's ``upstream_branch`` mapping.

    Checks out each mapped local branch in turn, runs the normal
    fetch/rebase/push sequence, and restores the originally checked-out branch
    when finished. Requires a dict-form ``upstream_branch`` mapping for the repo.

    When ``branch_filter`` is a non-empty list of branch names, only those
    branches are synced (each must exist in the mapping); otherwise every mapped
    branch is synced.

    Each branch is rebased onto its upstream target, which rewrites history, so a
    plain push would always be rejected as non-fast-forward. Force-push (via the
    safe ``--force-with-lease``) is therefore the default for this flow; ``--force``
    is redundant here but harmless.
    """
    from drivers_python_cli.utils.repo import get_upstream_branch

    path = repo_info["path"]
    name = repo_info["name"]
    group = repo_info.get("group", "")

    # Rebasing rewrites the branch, so force-push is required to update origin.
    force = True

    mapping = get_upstream_branch(config, group, name)
    if not isinstance(mapping, dict):
        typer.echo(
            f"❌ Error: --all-branches requires a dict-form upstream_branch mapping for '{name}'",
            err=True,
        )
        typer.echo(
            "Configure [repo.groups.<group>.upstream_branch] with a {local = upstream} map.",
            err=True,
        )
        raise typer.Exit(1)

    if branch_filter:
        unknown = [b for b in branch_filter if b not in mapping]
        if unknown:
            typer.echo(
                f"❌ Error: branch(es) not in upstream_branch mapping for '{name}': "
                f"{', '.join(unknown)}",
                err=True,
            )
            typer.echo(f"Available branches: {', '.join(mapping.keys())}", err=True)
            raise typer.Exit(1)
        # Preserve the requested order, de-duplicated.
        seen = set()
        branches = [b for b in branch_filter if not (b in seen or seen.add(b))]
    else:
        branches = list(mapping.keys())
    original_branch = _current_branch(path)

    _echo(
        Text.assemble(
            ("[dry-run] " if dry_run else "", "dim"),
            (f"Syncing {len(branches)} branch(es) of ", "bold"),
            (name, "bold cyan"),
        )
    )

    synced_count = 0
    skipped_count = 0
    failed_branches = []
    synced_branches = []
    restored = True

    # In dry-run mode we never mutate the working tree: instead of checking out
    # each branch, fetch upstream once and compare each mapped branch's
    # origin ref against its upstream target directly. This lets --all-branches
    # and --dry-run work together even when the tree is dirty.
    if dry_run:
        try:
            if verbose:
                _echo("[verbose] Fetching from upstream...", style="dim")
            subprocess.run(
                ["git", "-C", str(path), "fetch", "upstream"],
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as e:
            _echo(
                f"❌ Failed to fetch from upstream: {e.stderr}", style="red", err=True
            )
            raise typer.Exit(1)

        for branch in branches:
            lines = []
            lines.append(Text.assemble(("🌿 ", ""), (branch, "bold cyan")))
            _show_commit_comparison(
                path,
                name,
                branch,
                f"upstream/{mapping[branch]}",
                verbose,
                emit=lambda message, style=None: lines.append(
                    message if isinstance(message, Text) else Text(message, style=style)
                ),
            )
            synced_count += 1
            _print_repo_panel(f"{name} · {branch}", "dry_run", lines)

        _print_overall_panel("✨ Dry run complete!", {"dry_run": synced_count})
        if backport_report:
            _print_backport_report(
                repo_info,
                config,
                mapping,
                branches,
                verbose,
                show_all=show_all,
                security_only=security_only,
            )
        return

    try:
        for branch in branches:
            lines = [Text.assemble(("🌿 ", ""), (branch, "bold cyan"))]
            try:
                subprocess.run(
                    ["git", "-C", str(path), "switch", branch],
                    check=True,
                    capture_output=True,
                    text=True,
                )
            except subprocess.CalledProcessError as e:
                lines.append(
                    Text(f"❌ Failed to switch to {branch}: {e.stderr}", style="red")
                )
                failed_branches.append(branch)
                _print_repo_panel(f"{name} · {branch}", "failed", lines)
                continue

            # abort_on_conflict keeps the working tree clean on a failed rebase
            # so the loop can move on to the next branch and restore the
            # original branch afterwards, instead of leaving a rebase in progress.
            status = _sync_repository(
                path,
                name,
                verbose,
                force,
                dry_run,
                upstream_branch=mapping,
                abort_on_conflict=True,
                lines=lines,
                checkout_default=False,
            )
            _print_repo_panel(f"{name} · {branch}", status, lines)
            if status == "skipped":
                skipped_count += 1
            elif status in ("synced", "dry_run"):
                synced_count += 1
                synced_branches.append(branch)
            elif status == "failed":
                failed_branches.append(branch)
    finally:
        # Restore whatever branch was checked out before we started.
        if original_branch and _current_branch(path) != original_branch:
            try:
                subprocess.run(
                    ["git", "-C", str(path), "switch", original_branch],
                    check=True,
                    capture_output=not verbose,
                    text=True,
                )
            except subprocess.CalledProcessError:
                restored = False

    # Dry-run returns early above; this path only handles the real sync.
    _print_overall_panel(
        "✨ Done!",
        {
            "synced": synced_count,
            "skipped": skipped_count,
            "failed": len(failed_branches),
        },
    )

    if failed_branches:
        _echo(
            f"⚠️  Rebase these branch(es) manually: {', '.join(failed_branches)}",
            style="yellow",
            err=True,
        )

    if original_branch and not restored:
        _echo(
            f"⚠️  Could not switch back to original branch '{original_branch}'",
            style="yellow",
            err=True,
        )

    # Re-run downstream CI for branches that actually rebased+pushed. The backend's
    # PR workflows check out the fork branch at a pinned ref, so a rebased branch is
    # only re-validated when those PRs' CI is re-run (see get_ci_rerun_targets).
    if not no_ci and synced_branches:
        _rerun_downstream_ci(config, group, name, synced_branches, verbose)

    # Rebasing the fork branches only aligns them with upstream's *current* tip;
    # it says nothing about whether the released backend already contains those
    # commits. Report that gap so a fix backported upstream after the last
    # release (e.g. a 5.2.x security fix landing after backend 5.2.4) is noticed.
    if backport_report:
        _print_backport_report(
            repo_info,
            config,
            mapping,
            branches,
            verbose,
            show_all=show_all,
            security_only=security_only,
        )


def _rerun_downstream_ci(config, group_name, repo_name, synced_branches, verbose=False):
    """Re-run downstream CI for the branches that synced, per the ci_rerun mapping.

    Each fork branch maps to a downstream target that is either a **PR number**
    (re-run that PR's workflow runs), a **git ref** (dispatch the repo's
    ``test-python*`` workflows on that backend branch via ``workflow_dispatch`` —
    no PR needed), or a PR number flagged for **Evergreen** (additionally comment
    ``evergreen retry`` to re-trigger the PR's Evergreen patch, since a rebased
    fork branch pinned by the PR does not re-trigger Evergreen on its own). Only
    branches that actually rebased are processed; a branch that failed or was
    skipped triggers nothing.

    Best-effort: this never fails the sync. A missing ``gh`` CLI, an unconfigured
    ``ci_rerun`` mapping, or a GitHub API error is reported as a warning and
    skipped.
    """
    import json
    import shutil

    from drivers_python_cli.utils.repo import get_ci_rerun_targets

    # Collect (branch, target, kind, value) actions for every synced branch,
    # de-duplicating in case two branches map to the same PR or ref.
    seen = set()
    actions = []
    for branch in synced_branches:
        for target, spec in get_ci_rerun_targets(
            config, group_name, repo_name, branch
        ).items():
            for number in spec["prs"]:
                key = (target, "pr", number)
                if key not in seen:
                    seen.add(key)
                    actions.append((branch, target, "pr", number))
            for ref in spec["refs"]:
                key = (target, "ref", ref)
                if key not in seen:
                    seen.add(key)
                    actions.append((branch, target, "ref", ref))
            for number in spec["evergreen_prs"]:
                key = (target, "evergreen", number)
                if key not in seen:
                    seen.add(key)
                    actions.append((branch, target, "evergreen", number))

    if not actions:
        return

    if not shutil.which("gh"):
        typer.echo(
            "⚠️  Skipping downstream CI re-run: 'gh' CLI not found "
            "(install GitHub CLI or pass --no-ci to silence)",
            err=True,
        )
        return

    def _gh_json(args):
        result = subprocess.run(
            ["gh", *args], check=True, capture_output=True, text=True
        )
        out = result.stdout.strip()
        return json.loads(out) if out else []

    typer.echo("")
    for branch, target, kind, value in actions:
        if kind == "pr":
            _rerun_pr_ci(target, value, branch, verbose, _gh_json)
        elif kind == "evergreen":
            _retry_evergreen(target, value, branch, verbose, _gh_json)
        else:
            _dispatch_workflows(target, value, branch, verbose, _gh_json)


def _gh_error_message(stderr):
    """Extract the API error message from ``gh``'s stderr.

    ``gh api`` reports failures as ``gh: <message> (HTTP <code>)`` on stderr,
    sometimes preceded by the raw JSON body. Pull out the human-readable part so
    callers can report *why* GitHub refused instead of guessing.
    """
    for line in reversed((stderr or "").strip().splitlines()):
        line = line.strip()
        if line.startswith("gh: "):
            return line[4:].strip()
    return (stderr or "").strip().splitlines()[-1].strip() if stderr else ""


def _pr_state(target, number, _gh_json):
    """Return a PR's state (``OPEN``/``CLOSED``/``MERGED``), or None if unknown.

    Best-effort: a lookup failure returns None so callers proceed rather than
    skipping work over a transient API error.
    """
    import json

    try:
        pr = _gh_json(["pr", "view", str(number), "--repo", target, "--json", "state"])
    except (subprocess.CalledProcessError, json.JSONDecodeError):
        return None
    return pr.get("state") if isinstance(pr, dict) else None


def _rerun_pr_ci(target, number, branch, verbose, _gh_json):
    """Re-run the workflow runs attached to an open PR's head commit.

    A closed or merged PR is reported and skipped: its CI would not gate
    anything, and a stale ``ci_rerun`` mapping pointing at a superseded PR is
    a configuration bug worth surfacing rather than silently acting on.
    """
    import json

    typer.echo(f"♻️  {branch} → re-running CI on {target}#{number}...")
    try:
        pr = _gh_json(
            [
                "pr",
                "view",
                str(number),
                "--repo",
                target,
                "--json",
                "headRefOid,state",
            ]
        )
        state = pr.get("state") if isinstance(pr, dict) else None
        if state and state != "OPEN":
            typer.echo(
                f"   #{number} ⚠️  PR is {state.lower()} — skipping "
                f"(update the ci_rerun mapping for '{branch}')",
                err=True,
            )
            return
        head_sha = pr.get("headRefOid") if isinstance(pr, dict) else None
        if not head_sha:
            raise ValueError("no head commit returned")
        runs = _gh_json(
            [
                "api",
                f"repos/{target}/actions/runs?head_sha={head_sha}&per_page=100",
                "--jq",
                "[.workflow_runs[].id]",
            ]
        )
    except (subprocess.CalledProcessError, json.JSONDecodeError, ValueError) as e:
        stderr = getattr(e, "stderr", "") or str(e)
        typer.echo(f"   #{number} ⚠️  could not resolve runs: {stderr}", err=True)
        return

    if not runs:
        typer.echo(f"   #{number} — no workflow runs for head commit")
        return

    requeued = 0
    reasons = []
    for run_id in runs:
        try:
            subprocess.run(
                [
                    "gh",
                    "api",
                    "-X",
                    "POST",
                    f"repos/{target}/actions/runs/{run_id}/rerun",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            requeued += 1
        except subprocess.CalledProcessError as e:
            reason = _gh_error_message(e.stderr)
            if reason and reason not in reasons:
                reasons.append(reason)
            if verbose:
                typer.echo(
                    f"   [verbose] rerun failed for run {run_id}: {e.stderr}",
                    err=True,
                )

    if requeued:
        typer.echo(f"   #{number} ✓ queued ({requeued} workflow run(s))")
        return

    # Report what GitHub actually said. The common refusals are meaningfully
    # different: runs older than GitHub's 30-day retry window can never be
    # re-run (the PR needs a fresh push instead), whereas a missing
    # `actions: write` scope is fixable by re-authenticating.
    if reasons:
        typer.echo(f"   #{number} ⚠️  no runs re-queued: {reasons[0]}", err=True)
        for extra in reasons[1:]:
            typer.echo(f"      also: {extra}", err=True)
        if any("over a month ago" in r for r in reasons):
            typer.echo(
                "      → runs are past GitHub's 30-day retry window; push to the "
                f"PR branch to get fresh Actions runs on #{number}",
                err=True,
            )
    else:
        typer.echo(f"   #{number} ⚠️  no runs re-queued", err=True)


def _retry_evergreen(target, number, branch, verbose, _gh_json=None):
    """Re-trigger a PR's Evergreen patch by commenting ``evergreen retry``.

    Evergreen's PR patch checks out the backend PR at a pinned fork ref, so a
    rebased (force-pushed) fork branch does not re-run Evergreen on its own.
    Commenting ``evergreen retry`` on the PR aborts any existing patch for the
    head commit and starts a fresh one. Best-effort: never fails the sync.

    A closed or merged PR is skipped: Evergreen does not run patches for it, so
    the comment would be noise on a PR nobody is watching.
    """
    typer.echo(f"♻️  {branch} → retrying Evergreen on {target}#{number}...")
    if _gh_json is not None:
        state = _pr_state(target, number, _gh_json)
        if state and state != "OPEN":
            typer.echo(
                f"   #{number} ⚠️  PR is {state.lower()} — skipping "
                f"(update the ci_rerun mapping for '{branch}')",
                err=True,
            )
            return
    try:
        subprocess.run(
            [
                "gh",
                "pr",
                "comment",
                str(number),
                "--repo",
                target,
                "--body",
                "evergreen retry",
            ],
            check=True,
            capture_output=not verbose,
            text=True,
        )
        typer.echo(f"   #{number} ✓ commented 'evergreen retry'")
    except subprocess.CalledProcessError as e:
        typer.echo(
            f"   #{number} ⚠️  could not comment 'evergreen retry': "
            f"{e.stderr if not verbose else ''}",
            err=True,
        )


def _dispatch_workflows(target, ref, branch, verbose, _gh_json):
    """Dispatch the target repo's ``test-python*`` workflows on a backend ref.

    No PR is needed: ``workflow_dispatch`` runs each matching workflow using its
    definition on ``ref``, which pins the fork branch it checks out.
    """
    import json

    typer.echo(f"♻️  {branch} → dispatching CI on {target}@{ref}...")
    try:
        workflows = _gh_json(
            [
                "api",
                f"repos/{target}/actions/workflows",
                "--jq",
                '[.workflows[] | select(.path | test("workflows/test-python")) '
                "| .path]",
            ]
        )
    except (subprocess.CalledProcessError, json.JSONDecodeError) as e:
        stderr = getattr(e, "stderr", "") or str(e)
        typer.echo(f"   @{ref} ⚠️  could not list workflows: {stderr}", err=True)
        return

    if not workflows:
        typer.echo(f"   @{ref} — no test-python* workflows found")
        return

    # Only workflows that declare a `workflow_dispatch` trigger can be run on a
    # ref; the others (push/schedule/pull_request only) would 422. Inspect each
    # workflow's definition on `ref` and skip the un-dispatchable ones quietly
    # rather than surfacing them as failures.
    dispatchable = []
    for path in sorted(workflows):
        name = path.split("/")[-1]
        try:
            content = subprocess.run(
                [
                    "gh",
                    "api",
                    f"repos/{target}/contents/{path}?ref={ref}",
                    "--jq",
                    ".content",
                ],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            body = base64.b64decode(content).decode("utf-8", "replace")
            # Avoid a YAML dependency: a workflow can only be dispatched on a ref
            # if its definition mentions the `workflow_dispatch` trigger at all.
            has_dispatch = "workflow_dispatch" in body
        except subprocess.CalledProcessError as e:
            stderr = e.stderr or ""
            # A 404 means the workflow file no longer exists at `ref` — a stale
            # entry in the Actions registry (renamed/deleted workflow). It can
            # never be dispatched on this ref, so skip it quietly rather than
            # attempting a dispatch that is guaranteed to 422.
            if "404" in stderr or "Not Found" in stderr:
                typer.echo(f"   {name} — skipped (not present on {ref})")
                continue
            if verbose:
                typer.echo(f"   [verbose] could not inspect {name}: {e}", err=True)
            has_dispatch = True  # transient/other error: fall back to attempting
        except Exception as e:  # noqa: BLE001 — best-effort; still try to dispatch
            if verbose:
                typer.echo(f"   [verbose] could not inspect {name}: {e}", err=True)
            has_dispatch = True  # fall back to attempting the dispatch
        if has_dispatch:
            dispatchable.append(path)
        else:
            typer.echo(f"   {name} — skipped (no workflow_dispatch trigger)")

    if not dispatchable:
        typer.echo(f"   @{ref} — no dispatchable test-python* workflows")
        return

    dispatched = 0
    for path in dispatchable:
        name = path.split("/")[-1]
        try:
            subprocess.run(
                ["gh", "workflow", "run", name, "--repo", target, "--ref", ref],
                check=True,
                capture_output=not verbose,
                text=True,
            )
            dispatched += 1
            typer.echo(f"   {name} ✓ queued")
        except subprocess.CalledProcessError as e:
            typer.echo(
                f"   {name} ⚠️  dispatch failed: {e.stderr if not verbose else ''}",
                err=True,
            )

    if not dispatched:
        typer.echo(
            f"   @{ref} ⚠️  no workflows dispatched (check ref/permissions)", err=True
        )


@app.callback()
def sync_callback(
    ctx: typer.Context,
    repo_name: str = typer.Argument(
        None,
        help="Repository name to sync (e.g., mongo-python-driver)",
    ),
    group: str = typer.Option(
        None,
        "--group",
        "-g",
        help="Sync all repositories in a group",
    ),
    all_groups: bool = typer.Option(
        False,
        "--all",
        "-a",
        help="Sync all repositories across all groups",
    ),
    all_branches: bool = typer.Option(
        False,
        "--all-branches",
        "-b",
        help="Sync every branch in a repo's upstream_branch mapping (e.g. the Django fork)",
    ),
    branch: list[str] = typer.Option(
        None,
        "--branch",
        "-B",
        help="Sync only the named branch(es) from the repo's upstream_branch mapping (repeatable)",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Force push after rebasing (use if previous sync failed)",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show what would be synced without making changes",
    ),
    quiet: bool = typer.Option(
        False,
        "--quiet",
        "-q",
        help="Hide detailed progress lines (verbose output is the default)",
    ),
    backport_report: bool = typer.Option(
        False,
        "--backport-report",
        help="Report upstream commits landed since the latest downstream release (see release_repo config)",
    ),
    all_commits: bool = typer.Option(
        False,
        "--all-commits",
        help="List every commit in the release-gap report, including the chores hidden by default",
    ),
    security_only: bool = typer.Option(
        False,
        "--security-only",
        help="In the release-gap report, list only commits fixing a CVE (overridden by --all-commits)",
    ),
    no_ci: bool = typer.Option(
        False,
        "--no-ci",
        help="Skip re-running downstream CI (GitHub Actions + Evergreen retry) after --all-branches (see ci_rerun config)",
    ),
):
    """Sync repository with upstream by fetching, rebasing, and pushing.

    Sync runs on the repo's default branch (the group's preferred_branch, else
    main, else master). If another branch is checked out, sync switches to the
    default branch, syncs it, and switches back. A repo with modified tracked
    files is skipped, because the switch would fail.

    Rebase behavior:

    - Default branch: Rebases to upstream/main or upstream/master
    - --all-branches: Rebases each mapped branch to its upstream target

    Usage::

        dpy sync <repo_name>                    # Sync a single repository
        dpy sync <repo_name> --all-branches     # Sync every branch in the repo's upstream_branch map
        dpy sync <repo_name> -B <branch>        # Sync only the named branch(es) from that map (repeatable)
        dpy sync <repo_name> -b --backport-report  # Sync all branches, plus the release-gap report
        dpy sync <repo_name> -b --dry-run --backport-report --all-commits  # Release-gap report, every commit
        dpy sync <repo_name> -b --dry-run --backport-report --security-only  # Release-gap report, CVE fixes
        dpy sync -g <group>                     # Sync all repos in a group
        dpy sync -a                             # Sync all repos in all groups
        dpy sync -g <group> <repo_name>         # Sync specific repo in a group
        dpy sync <repo_name> --force            # Force push after rebasing
        dpy sync <repo_name> --dry-run          # Show what would be synced
        dpy sync -g <group> --dry-run           # Preview group sync without changes
        dpy sync -a --dry-run                   # Preview all groups sync without changes
        dpy sync -g <group> <repo_name> --dry-run  # Preview single repo in group

    Examples::

        dpy sync mongo-python-driver                    # Sync single repo
        dpy sync django --all-branches                  # Sync every Django fork release branch
        dpy sync django -b --dry-run                    # Preview syncing all branches
        dpy sync -g pymongo                             # Sync all repos in group
        dpy sync -a                                     # Sync all repos in all groups
        dpy sync -g pymongo mongo-python-driver         # Sync specific repo in pymongo group
        dpy sync my-repo --force                        # Force push after rebase
        dpy sync my-repo --dry-run                      # Preview changes without syncing
        dpy sync my-repo --quiet                        # Hide detailed progress lines
        dpy sync -g pymongo --dry-run                   # Preview group sync
        dpy sync -a --dry-run                           # Preview all groups sync
        dpy sync -g pymongo mongo-python-driver --dry-run  # Preview specific repo
    """
    from drivers_python_cli.utils.repo import (
        find_all_repos,
        find_repo_by_name,
        find_repo_by_path,
        get_upstream_branch,
        is_path_like,
    )

    def _enrich(repo_list):
        """Drop worktrees, then attach upstream_branch from config to each repo."""
        repo_list = [r for r in repo_list if not r.get("worktree")]
        for r in repo_list:
            r["upstream_branch"] = get_upstream_branch(config, r["group"], r["name"])
        return repo_list

    # Verbose output is the default for sync. Use --quiet to hide it.
    verbose = not quiet

    try:
        config = repo.get_config()
        base_dir = repo.get_base_dir(config)
        groups = repo.get_repo_groups(config)

        if verbose:
            _echo(f"[verbose] Using base directory: {base_dir}", style="dim")
            _echo(f"[verbose] Available groups: {list(groups.keys())}\n", style="dim")

        # Handle all groups option
        if all_groups:
            global_group_names = repo.get_global_groups(config)

            # Get all non-global groups
            non_global_groups = [
                g for g in groups.keys() if g not in global_group_names
            ]

            if not non_global_groups:
                typer.echo("❌ Error: No groups found in configuration.", err=True)
                raise typer.Exit(1)

            # Find all repos across all non-global groups
            all_repos = find_all_repos(base_dir, config)
            target_repos = _enrich(
                [r for r in all_repos if r["group"] in non_global_groups]
            )

            if not target_repos:
                typer.echo("❌ Error: No repositories found in any group.", err=True)
                typer.echo("\nClone repositories using: dpy clone -a")
                raise typer.Exit(1)

            _sync_repo_list(
                target_repos,
                f"Syncing {len(target_repos)} repository(ies) across {len(non_global_groups)} group(s):\n",
                ctx,
                verbose,
                force,
                dry_run,
                config,
            )
            return

        # Handle syncing specific/all branches in a single repo's
        # upstream_branch mapping.
        if all_branches or branch:
            flag = "--all-branches" if all_branches else "--branch"
            if not repo_name:
                typer.echo(f"❌ Error: {flag} requires a repository name", err=True)
                typer.echo(f"\nUsage: dpy sync <repo-name> {flag}")
                raise typer.Exit(1)

            if group:
                if group not in groups:
                    typer.echo(
                        f"❌ Error: Group '{group}' not found in configuration.",
                        err=True,
                    )
                    typer.echo(
                        f"Available groups: {', '.join(groups.keys())}", err=True
                    )
                    raise typer.Exit(1)
                from drivers_python_cli.utils.repo import find_all_repos_by_name

                repo_info = next(
                    (
                        r
                        for r in find_all_repos_by_name(repo_name, base_dir, config)
                        if r["group"] == group
                    ),
                    None,
                )
            elif is_path_like(repo_name):
                repo_info = find_repo_by_path(repo_name, base_dir, config)
            else:
                repo_info = find_repo_by_name(repo_name, base_dir, config)

            if not repo_info:
                typer.echo(f"❌ Error: Repository '{repo_name}' not found", err=True)
                typer.echo("\nUse 'dpy list' to see available repositories")
                raise typer.Exit(1)

            _sync_all_branches(
                repo_info,
                config,
                verbose,
                force,
                dry_run,
                no_ci,
                branch_filter=branch or None,
                backport_report=backport_report,
                show_all=all_commits,
                security_only=security_only,
            )
            return

        # Handle sync with both group and repo name specified
        if group and repo_name:
            if group not in groups:
                typer.echo(
                    f"❌ Error: Group '{group}' not found in configuration.", err=True
                )
                typer.echo(f"Available groups: {', '.join(groups.keys())}", err=True)
                raise typer.Exit(1)

            # Find the specific repo within the group
            from drivers_python_cli.utils.repo import find_all_repos_by_name

            matching_repos = find_all_repos_by_name(repo_name, base_dir, config)
            repo_info = None
            for r in matching_repos:
                if r["group"] == group:
                    repo_info = r
                    break

            if not repo_info:
                typer.echo(
                    f"❌ Error: Repository '{repo_name}' not found in group '{group}'",
                    err=True,
                )
                typer.echo(f"\nClone the repository using: dpy clone -g {group}")
                raise typer.Exit(1)

            lines = []
            status = _sync_repository(
                repo_info["path"],
                repo_info["name"],
                verbose,
                force,
                dry_run,
                upstream_branch=get_upstream_branch(config, group, repo_info["name"]),
                preferred_branch=repo.get_preferred_branch(
                    config, group, repo_info["name"]
                ),
                lines=lines,
            )
            _print_repo_panel(repo_info["name"], status, lines)
            _print_overall_panel(
                "✨ Dry run complete!" if dry_run else "✨ Done!",
                {status: 1},
            )
            return

        # Handle group sync (all repos in group)
        if group:
            if group not in groups:
                typer.echo(
                    f"❌ Error: Group '{group}' not found in configuration.", err=True
                )
                typer.echo(f"Available groups: {', '.join(groups.keys())}", err=True)
                raise typer.Exit(1)

            # Find all repos in the group
            all_repos = find_all_repos(base_dir, config)
            group_repos = _enrich([r for r in all_repos if r["group"] == group])

            if not group_repos:
                typer.echo(
                    f"❌ Error: No repositories found for group '{group}'.", err=True
                )
                typer.echo(f"\nClone repositories using: dpy clone -g {group}")
                raise typer.Exit(1)

            _sync_repo_list(
                group_repos,
                f"Syncing {len(group_repos)} repository(ies) in group '{group}':\n",
                ctx,
                verbose,
                force,
                dry_run,
                config,
            )
            return

        # Handle single repo sync
        if not repo_name:
            typer.echo("❌ Error: Repository name or group required", err=True)
            typer.echo("\nUsage: dpy sync <repo-name>")
            typer.echo("   or: dpy sync -g <group>")
            typer.echo("   or: dpy sync -g <group> <repo-name>")
            raise typer.Exit(1)

        _is_path_like = is_path_like(repo_name)

        # Find the repository
        if _is_path_like:
            repo_info = find_repo_by_path(repo_name, base_dir, config)
            if not repo_info:
                typer.echo(
                    f"❌ Error: No managed repository found at '{Path(repo_name).resolve()}'",
                    err=True,
                )
                typer.echo("\nUse 'dpy list' to see available repositories")
                raise typer.Exit(1)
        else:
            repo_info = find_repo_by_name(repo_name, base_dir, config)
            if not repo_info:
                typer.echo(f"❌ Error: Repository '{repo_name}' not found", err=True)
                typer.echo("\nUse 'dpy list' to see available repositories")
                raise typer.Exit(1)

        lines = []
        status = _sync_repository(
            repo_info["path"],
            repo_info["name"],
            verbose,
            force,
            dry_run,
            upstream_branch=get_upstream_branch(
                config, repo_info.get("group", ""), repo_info["name"]
            ),
            preferred_branch=repo.get_preferred_branch(
                config, repo_info.get("group", ""), repo_info["name"]
            ),
            lines=lines,
        )
        _print_repo_panel(repo_info["name"], status, lines)
        _print_overall_panel(
            "✨ Dry run complete!" if dry_run else "✨ Done!",
            {status: 1},
        )

    except typer.Exit:
        # typer.Exit subclasses RuntimeError, so the broad handler below would
        # otherwise swallow every deliberate exit and re-report it as "❌ Error: 1".
        raise
    except Exception as e:
        _echo(f"❌ Error: {e}", style="red", err=True)
        raise typer.Exit(1)


def _sync_repository(
    repo_path: Path,
    repo_name: str,
    verbose: bool = False,
    force: bool = False,
    dry_run: bool = False,
    upstream_branch: str | None = None,
    abort_on_conflict: bool = False,
    lines: list | None = None,
    preferred_branch: str | None = None,
    checkout_default: bool = True,
) -> str:
    """Sync a single repository with upstream.

    Sync always targets the repo's default branch: the configured
    ``preferred_branch``, else ``main``, else ``master``. When another branch is
    checked out, sync switches to the default branch and switches back when it
    finishes. A repo with modified tracked files is skipped, because the switch
    would fail. Pass ``checkout_default=False`` to sync whatever branch is
    checked out (used by ``--all-branches``, which drives the checkouts itself).

    For main/master branches: rebases to upstream/<branch_name>
    For feature branches: rebases to upstream's default branch (main/master),
    or to upstream/<upstream_branch> if upstream_branch is explicitly provided.

    When ``abort_on_conflict`` is True, a rebase that fails (e.g. conflicts) is
    aborted so the working tree is left clean and the user is pointed at a
    manual rebase. This is used by ``--all-branches`` so one failed branch does
    not leave a rebase in progress that blocks the remaining branches. When
    False (the default single-repo behaviour), the rebase is left in progress
    for manual conflict resolution in place.

    Returns:
        "synced", "skipped", "failed", or "dry_run"

    When ``lines`` is given, steps are appended to it instead of printed, and
    no panel is printed. The caller then renders the panel.
    """
    own_lines = lines is None
    if own_lines:
        lines = []

    def emit(message, style=None):
        lines.append(
            message if isinstance(message, Text) else Text(message, style=style)
        )

    def emit_output(text, style="dim"):
        for line in (text or "").splitlines():
            if line.strip():
                emit(f"  {line}", style=style)

    def finish(status):
        if own_lines:
            _print_repo_panel(repo_name, status, lines)
        return status

    # Worktrees track a branch of the clone they belong to (typically an upstream
    # branch). Rebasing one onto upstream and force-pushing it to origin would
    # push upstream's history into the fork, so sync never touches them; sync the
    # primary clone instead.
    if is_worktree(repo_path):
        emit(
            Text.assemble(
                ("⏭️  Skipping ", "dim"), (repo_name, "bold"), (" (worktree)", "dim")
            )
        )
        return finish("skipped")

    if dry_run:
        emit(Text.assemble(("🔍 Checking ", ""), (repo_name, "bold cyan")))
    else:
        emit(Text.assemble(("🔄 Syncing ", ""), (repo_name, "bold cyan")))

    if verbose:
        emit(f"[verbose] Repository path: {repo_path}", style="dim")
        if force:
            emit("[verbose] Force push enabled", style="dim")
        if dry_run:
            emit("[verbose] Dry run mode enabled", style="dim")

    # Check if upstream remote exists
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_path), "remote"],
            check=True,
            capture_output=True,
            text=True,
        )
        remotes = result.stdout.strip().split("\n")

        if "upstream" not in remotes:
            emit("⚠️  No 'upstream' remote found (skipping)", style="yellow")
            return finish("skipped")

    except subprocess.CalledProcessError as e:
        emit(f"❌ Failed to check remotes: {e.stderr}", style="red")
        return finish("failed")

    # Get current branch
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_path), "branch", "--show-current"],
            check=True,
            capture_output=True,
            text=True,
        )
        current_branch = result.stdout.strip()

        if not current_branch:
            emit("⚠️  Not on a branch (detached HEAD), skipping", style="yellow")
            return finish("skipped")

        if verbose:
            emit(f"[verbose] Current branch: {current_branch}", style="dim")

    except subprocess.CalledProcessError as e:
        emit(f"❌ Failed to get current branch: {e.stderr}", style="red")
        return finish("failed")

    # Sync always operates on the default branch. Switch to it first, and
    # restore the original branch afterwards.
    original_branch = current_branch
    if checkout_default:
        default_branch = _default_sync_branch(repo_path, preferred_branch)
        if not default_branch:
            emit(
                "⚠️  No main, master, or preferred branch found, skipping",
                style="yellow",
            )
            return finish("skipped")
        if default_branch != current_branch:
            # A dry run reads refs only, so it can preview the default branch
            # without touching the tree. Only a real sync must switch.
            if not dry_run and _has_local_changes(repo_path):
                emit(
                    f"⚠️  Skipping: uncommitted changes block switch from "
                    f"'{current_branch}' to '{default_branch}'",
                    style="yellow",
                )
                return finish("skipped")
            if verbose:
                action = "Would switch" if dry_run else "Switching"
                emit(
                    f"[verbose] {action} from {current_branch} to {default_branch}",
                    style="dim",
                )
            if not dry_run:
                try:
                    subprocess.run(
                        ["git", "-C", str(repo_path), "switch", default_branch],
                        check=True,
                        capture_output=True,
                        text=True,
                    )
                except subprocess.CalledProcessError as e:
                    emit(
                        f"❌ Failed to switch to {default_branch}: {e.stderr}",
                        style="red",
                    )
                    return finish("failed")
            current_branch = default_branch

    try:
        status = _sync_current_branch(
            repo_path,
            repo_name,
            current_branch,
            verbose,
            force,
            dry_run,
            upstream_branch,
            abort_on_conflict,
            emit,
            emit_output,
        )
    finally:
        if (
            checkout_default
            and original_branch != current_branch
            and not dry_run
            and _current_branch(repo_path) != original_branch
        ):
            try:
                subprocess.run(
                    ["git", "-C", str(repo_path), "switch", original_branch],
                    check=True,
                    capture_output=not verbose,
                    text=True,
                )
            except subprocess.CalledProcessError:
                emit(
                    f"⚠️  Could not switch back to original branch '{original_branch}'",
                    style="yellow",
                )

    return finish(status)


def _sync_current_branch(
    repo_path,
    repo_name,
    current_branch,
    verbose,
    force,
    dry_run,
    upstream_branch,
    abort_on_conflict,
    emit,
    emit_output,
):
    """Fetch, rebase, and push the checked-out branch. Returns a status string."""

    # Fetch from upstream
    try:
        if verbose:
            emit("[verbose] Fetching from upstream...", style="dim")

        result = subprocess.run(
            ["git", "-C", str(repo_path), "fetch", "upstream"],
            check=True,
            capture_output=True,
            text=True,
        )
        if verbose:
            emit_output(result.stdout)
            emit_output(result.stderr)

    except subprocess.CalledProcessError as e:
        emit(f"❌ Failed to fetch from upstream: {e.stderr}", style="red")
        return "failed"

    # Determine which branch to rebase onto
    # For main/master: rebase to upstream/<current_branch>
    # For feature branches: use configured upstream_branch if provided,
    # otherwise detect upstream's default branch (main/master)
    if isinstance(upstream_branch, dict):
        upstream_branch = upstream_branch.get(current_branch)
    if current_branch in ["main", "master"]:
        rebase_target = f"upstream/{current_branch}"
        if verbose:
            emit(
                f"[verbose] Main branch detected, rebasing to {rebase_target}",
                style="dim",
            )
    elif upstream_branch:
        rebase_target = f"upstream/{upstream_branch}"
        if verbose:
            emit(
                f"[verbose] Using configured upstream_branch, rebasing to {rebase_target}",
                style="dim",
            )
    else:
        # Check if upstream has a branch with the same name as the current branch.
        # This handles repos where fork and upstream use matching branch names
        # (e.g. 5.2.x on both sides) without requiring explicit upstream_branch config.
        try:
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(repo_path),
                    "rev-parse",
                    f"upstream/{current_branch}",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            rebase_target = f"upstream/{current_branch}"
            if verbose:
                emit(
                    f"[verbose] Upstream has matching branch, rebasing to {rebase_target}",
                    style="dim",
                )
        except subprocess.CalledProcessError:
            # No matching upstream branch — fall back to upstream's default branch
            upstream_default = _get_upstream_default_branch(repo_path, verbose, emit)
            if not upstream_default:
                # Fallback to trying common default branches
                if verbose:
                    emit(
                        "[verbose] Could not detect upstream default, trying main/master...",
                        style="dim",
                    )
                # Try main first, then master
                for branch in ["main", "master"]:
                    try:
                        subprocess.run(
                            [
                                "git",
                                "-C",
                                str(repo_path),
                                "rev-parse",
                                f"upstream/{branch}",
                            ],
                            check=True,
                            capture_output=True,
                            text=True,
                        )
                        upstream_default = branch
                        break
                    except subprocess.CalledProcessError:
                        continue

                if not upstream_default:
                    emit("❌ Could not determine upstream default branch", style="red")
                    return "failed"

            rebase_target = f"upstream/{upstream_default}"
            if verbose:
                emit(
                    f"[verbose] Feature branch detected, rebasing to {rebase_target}",
                    style="dim",
                )

    # If dry-run, compare commits and show what would happen
    if dry_run:
        _show_commit_comparison(
            repo_path, repo_name, current_branch, rebase_target, verbose, emit
        )
        return "dry_run"

    # Rebase on target branch
    try:
        if verbose:
            emit(f"[verbose] Rebasing on {rebase_target}...", style="dim")

        result = subprocess.run(
            ["git", "-C", str(repo_path), "rebase", rebase_target],
            check=True,
            capture_output=True,
            text=True,
        )
        if verbose:
            emit_output(result.stdout)
            emit_output(result.stderr)

    except subprocess.CalledProcessError as e:
        emit(f"❌ Failed to rebase {current_branch} on {rebase_target}", style="red")
        if e.stderr:
            emit_output(e.stderr, style="red")

        if abort_on_conflict:
            # Leave the repo in a clean state so callers that iterate over
            # multiple branches (dpy sync --all-branches) can continue and
            # restore the original branch. Point the user at a manual rebase.
            subprocess.run(
                ["git", "-C", str(repo_path), "rebase", "--abort"],
                check=False,
                capture_output=True,
                text=True,
            )
            emit(
                f"  Rebase aborted. Resolve manually: cd {repo_path} && "
                f"git switch {current_branch} && git rebase {rebase_target}",
                style="yellow",
            )
        else:
            emit(
                f"  You may need to resolve conflicts manually in {repo_path}",
                style="yellow",
            )
        return "failed"

    # Push to origin
    try:
        if verbose:
            push_type = "force pushing" if force else "pushing"
            emit(
                f"[verbose] {push_type.capitalize()} to origin/{current_branch}...",
                style="dim",
            )

        push_cmd = ["git", "-C", str(repo_path), "push"]
        if force:
            push_cmd.append("--force-with-lease")
        push_cmd.extend(["origin", current_branch])

        result = subprocess.run(
            push_cmd,
            check=True,
            capture_output=True,
            text=True,
        )
        if verbose:
            emit_output(result.stdout)
            emit_output(result.stderr)

        emit("✅ Synced and pushed successfully", style="green")
        return "synced"

    except subprocess.CalledProcessError as e:
        emit(
            f"⚠️  Synced but failed to push to origin/{current_branch}",
            style="yellow",
        )
        if e.stderr:
            emit_output(e.stderr, style="red")
        emit(f"  Try running: dpy sync {repo_name} --force", style="yellow")
        return "failed"


def _get_upstream_default_branch(
    repo_path: Path, verbose: bool = False, emit=None
) -> str | None:
    """Get the default branch of the upstream remote.

    Args:
        repo_path: Path to the repository
        verbose: Whether to print verbose output
        emit: Optional callback for progress lines. Defaults to printing.

    Returns:
        str: The default branch name (e.g., 'main', 'master'), or None if not found
    """
    if emit is None:
        emit = _echo
    try:
        # Try to get the symbolic ref for upstream/HEAD
        result = subprocess.run(
            ["git", "-C", str(repo_path), "symbolic-ref", "refs/remotes/upstream/HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
        # Output will be like "refs/remotes/upstream/main"
        ref = result.stdout.strip()
        if ref.startswith("refs/remotes/upstream/"):
            default_branch = ref.replace("refs/remotes/upstream/", "")
            if verbose:
                emit(
                    f"[verbose] Detected upstream default branch: {default_branch}",
                    style="dim",
                )
            return default_branch
    except subprocess.CalledProcessError:
        # symbolic-ref might fail if upstream/HEAD is not set
        # Try to set it by running remote show
        try:
            if verbose:
                emit(
                    "[verbose] Attempting to detect upstream default branch...",
                    style="dim",
                )
            result = subprocess.run(
                ["git", "-C", str(repo_path), "remote", "show", "upstream"],
                check=True,
                capture_output=True,
                text=True,
            )
            # Parse output to find "HEAD branch: <branch>"
            for line in result.stdout.split("\n"):
                if "HEAD branch:" in line:
                    default_branch = line.split("HEAD branch:")[-1].strip()
                    if verbose:
                        emit(
                            f"[verbose] Detected upstream default branch: {default_branch}",
                            style="dim",
                        )
                    return default_branch
        except subprocess.CalledProcessError:
            pass

    return None


def _show_commit_comparison(
    repo_path: Path,
    repo_name: str,
    current_branch: str,
    rebase_target: str,
    verbose: bool = False,
    emit=None,
):
    """Show comparison between upstream and origin commits.

    Args:
        repo_path: Path to the repository
        repo_name: Name of the repository
        current_branch: Current branch name
        rebase_target: Target branch to rebase onto (e.g., 'upstream/main')
        verbose: Whether to print verbose output
        emit: Optional callback for output lines. Defaults to printing.
    """
    if emit is None:
        emit = _echo
    try:
        # Get the origin branch reference
        origin_branch = f"origin/{current_branch}"

        # Check if origin branch exists
        try:
            subprocess.run(
                ["git", "-C", str(repo_path), "rev-parse", origin_branch],
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError:
            emit(f"⚠️  No origin/{current_branch} branch found", style="yellow")
            return

        # Count commits ahead of upstream (commits in origin but not in upstream)
        result = subprocess.run(
            [
                "git",
                "-C",
                str(repo_path),
                "rev-list",
                "--count",
                f"{rebase_target}..{origin_branch}",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        commits_ahead = int(result.stdout.strip())

        # Count commits behind upstream (commits in upstream but not in origin)
        result = subprocess.run(
            [
                "git",
                "-C",
                str(repo_path),
                "rev-list",
                "--count",
                f"{origin_branch}..{rebase_target}",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        commits_behind = int(result.stdout.strip())

        # Show status
        if commits_ahead == 0 and commits_behind == 0:
            emit(f"✅ Already up to date with {rebase_target}", style="green")
        else:
            status_parts = []
            if commits_behind > 0:
                status_parts.append(
                    f"{commits_behind} commit(s) behind {rebase_target}"
                )
            if commits_ahead > 0:
                status_parts.append(f"{commits_ahead} commit(s) ahead")

            status = ", ".join(status_parts)
            emit(f"📊 {status}", style="cyan")

            # Show commit details if verbose or if there are commits
            if verbose or commits_behind > 0 or commits_ahead > 0:
                # Show commits that would be applied from upstream
                if commits_behind > 0:
                    if commits_behind > 10:
                        emit(
                            f"Commits from {rebase_target} that would be applied"
                            f" (first 10 of {commits_behind}):",
                            style="bold",
                        )
                    else:
                        emit(
                            f"Commits from {rebase_target} that would be applied:",
                            style="bold",
                        )
                    result = subprocess.run(
                        [
                            "git",
                            "-C",
                            str(repo_path),
                            "log",
                            "--oneline",
                            "--no-decorate",
                            "-n",
                            "10",
                            f"{origin_branch}..{rebase_target}",
                        ],
                        check=True,
                        capture_output=True,
                        text=True,
                    )
                    for line in result.stdout.strip().split("\n"):
                        if line:
                            emit(Text.assemble(("  + ", "green"), (line, "")))

                # Show commits in origin that would be rebased
                if commits_ahead > 0:
                    if commits_ahead > 10:
                        emit(
                            f"Commits in origin/{current_branch} that would be rebased"
                            f" (first 10 of {commits_ahead}):",
                            style="bold",
                        )
                    else:
                        emit(
                            f"Commits in origin/{current_branch} that would be rebased:",
                            style="bold",
                        )
                    result = subprocess.run(
                        [
                            "git",
                            "-C",
                            str(repo_path),
                            "log",
                            "--oneline",
                            "--no-decorate",
                            "-n",
                            "10",
                            f"{rebase_target}..{origin_branch}",
                        ],
                        check=True,
                        capture_output=True,
                        text=True,
                    )
                    for line in result.stdout.strip().split("\n"):
                        if line:
                            emit(Text.assemble(("  * ", "yellow"), (line, "")))

    except subprocess.CalledProcessError as e:
        emit(
            f"❌ Failed to compare commits: {e.stderr if e.stderr else 'Unknown error'}",
            style="red",
        )


def _branch_series(branch):
    """Return the ``X.Y`` release series a fork branch tracks, or None.

    ``mongodb-5.2.x`` → ``"5.2"``. Branches that do not follow the
    ``<prefix>-<major>.<minor>.x`` convention have no derivable series.
    """
    import re

    match = re.search(r"(\d+)\.(\d+)\.x$", branch)
    return f"{match.group(1)}.{match.group(2)}" if match else None


def _django_dev_version(path):
    """Return the in-development version on ``upstream/main`` (e.g. ``"6.2"``).

    Read from ``django/__init__.py`` so the report can name the cycle a commit
    came from even before that cycle's stable branch is cut. Falls back to
    ``"main"`` when the file or ref cannot be read.
    """
    import re

    try:
        content = _git_out(path, ["show", "upstream/main:django/__init__.py"])
    except subprocess.CalledProcessError:
        return "main"
    match = re.search(r"VERSION\s*=\s*\(\s*(\d+)\s*,\s*(\d+)", content)
    return f"{match.group(1)}.{match.group(2)}" if match else "main"


def _upstream_cycles(path):
    """Return ``(cycles, dev_label)`` describing upstream's release cycles.

    ``cycles`` is a list of ``(version, label, forkpoint)`` ascending by version,
    one per live ``upstream/stable/X.Y.x`` branch, where ``forkpoint`` is the
    ``main`` commit that branch was cut from. A commit is part of the ``X.Y``
    cycle when it is an ancestor of that branch's fork point but of no earlier
    one, so the ascending order makes the first match the right answer.

    ``dev_label`` is the cycle for commits newer than every fork point, i.e. the
    version currently in development on ``main``.
    """
    import re

    cycles = []
    refs = _git_out(
        path,
        [
            "for-each-ref",
            "--format=%(refname:short)",
            "refs/remotes/upstream/stable",
        ],
    )
    for ref in refs.splitlines():
        match = re.search(r"(\d+)\.(\d+)\.x$", ref.strip())
        if not match:
            continue
        version = (int(match.group(1)), int(match.group(2)))
        try:
            forkpoint = _git_out(path, ["merge-base", "upstream/main", ref.strip()])
        except subprocess.CalledProcessError:
            continue
        if forkpoint:
            cycles.append((version, f"{version[0]}.{version[1]}", forkpoint))
    cycles.sort(key=lambda c: c[0])
    return cycles, _django_dev_version(path)


def _classify_cycle(path, source_sha, cycles, dev_label, cache):
    """Return the upstream dev cycle label a backport's source commit belongs to."""
    if source_sha in cache:
        return cache[source_sha]

    label = dev_label
    for _version, cycle_label, forkpoint in cycles:
        result = subprocess.run(
            [
                "git",
                "-C",
                str(path),
                "merge-base",
                "--is-ancestor",
                source_sha,
                forkpoint,
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            label = cycle_label
            break
    cache[source_sha] = label
    return label


def _new_upstream_commits(path, upstream_ref, since_iso):
    """Return ``(sha, short, date, subject, body)`` for commits on ``upstream_ref``
    committed after ``since_iso``."""
    log = _git_out(
        path,
        [
            "log",
            f"upstream/{upstream_ref}",
            f"--since={since_iso}",
            "--date=short",
            "--format=\x01%H\x02%h\x02%cd\x02%s\x02%b",
        ],
    )
    commits = []
    for entry in log.split("\x01")[1:]:
        parts = entry.split("\x02", 4)
        if len(parts) == 5:
            commits.append(tuple(p.strip() for p in parts))
    return commits


def _print_backport_report(
    repo_info,
    config,
    mapping,
    branches,
    verbose=False,
    show_all=False,
    security_only=False,
):
    """Report upstream commits that landed after the matching downstream release.

    For each synced fork branch, compare its upstream target against the highest
    release tag of the same series in the group's ``release_repo`` and list the
    commits upstream has that the release does not, each labelled with the
    upstream dev cycle it was backported from. This is what catches, say, a
    security fix backported to Django's ``stable/5.2.x`` after
    django-mongodb-backend 5.2.4 shipped.

    Commits are grouped by :func:`_classify_commit` so the security fixes and
    ticket fixes -- the release-decision material -- are not buried in version
    bumps and translation updates.

    Best-effort: any missing configuration or git failure is reported as a
    warning rather than failing the sync.
    """
    from drivers_python_cli.utils.repo import find_repo_by_name, get_release_repo

    path = repo_info["path"]
    name = repo_info["name"]
    group = repo_info.get("group", "")

    release_name = get_release_repo(config, group, name)
    if not release_name:
        if verbose:
            typer.echo(
                f"[verbose] No release_repo configured for '{name}' — "
                "skipping backport report"
            )
        return

    base_dir = repo.get_base_dir(config)
    release_info = find_repo_by_name(release_name, base_dir, config)
    if not release_info:
        typer.echo(
            f"⚠️  Skipping backport report: release repo '{release_name}' not found "
            f"locally (clone it or unset release_repo)",
            err=True,
        )
        return

    release_path = release_info["path"]
    # Release tags may have been cut since this clone last fetched; a stale tag
    # list would silently over-report commits as "new since the release".
    try:
        subprocess.run(
            ["git", "-C", str(release_path), "fetch", "--tags", "--quiet"],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        if verbose:
            typer.echo(f"[verbose] Could not fetch tags for {release_name}: {e.stderr}")

    try:
        cycles, dev_label = _upstream_cycles(path)
    except subprocess.CalledProcessError as e:
        typer.echo(
            f"⚠️  Skipping backport report: could not read upstream cycles "
            f"({e.stderr.strip() if e.stderr else e})",
            err=True,
        )
        return

    typer.echo(f"\n📋 Upstream commits since the latest {release_name} release:\n")

    cache = {}
    backport_re = re.compile(r"[Bb]ackport of ([0-9a-f]{7,40}) from main")

    for branch in branches:
        upstream_ref = mapping[branch]
        typer.echo(f"🌿 {branch} → upstream/{upstream_ref}")

        series = _branch_series(branch)
        if not series:
            typer.echo(f"   ⚠️  Cannot derive a release series from '{branch}'")
            continue

        release = _latest_release_tag(release_path, series)
        if not release:
            typer.echo(f"   ⚠️  No {series}.* release tag in {release_name} yet")
            continue

        tag, since = release
        try:
            commits = _new_upstream_commits(path, upstream_ref, since)
        except subprocess.CalledProcessError as e:
            typer.echo(
                f"   ⚠️  Could not read upstream/{upstream_ref} "
                f"({e.stderr.strip() if e.stderr else e})",
                err=True,
            )
            continue

        typer.echo(f"   {release_name} {tag} ({since[:10]}) … upstream tip")
        if not commits:
            typer.echo("   ✅ nothing new upstream")
            continue

        entries = []
        for _sha, short, date, subject, body in commits:
            match = backport_re.search(body)
            if match:
                label = f"{_classify_cycle(path, match.group(1), cycles, dev_label, cache)} cycle"
            else:
                label = "unannotated"
            entries.append((_classify_commit(subject), label, short, date, subject))

        counts = Counter(bucket for bucket, *_ in entries)
        # Summarise against len(commits), not the sum of the buckets: if upstream
        # changes its commit conventions the total still moves, which is the
        # signal that the classification needs revisiting.
        summary = ", ".join(
            f"{counts[bucket]} {name.split(' ', 1)[1]}"
            for bucket, name in _BUCKETS
            if counts[bucket]
        )
        typer.echo(f"   {len(commits)} new commit(s): {summary}")

        hidden = 0
        for bucket, heading in _BUCKETS:
            group = [e for e in entries if e[0] == bucket]
            if not group:
                continue
            if not show_all and (
                (security_only and bucket != "security") or bucket == "chore"
            ):
                hidden += len(group)
                continue
            typer.echo(f"   {heading}")
            for _bucket, label, short, date, subject in group:
                typer.echo(f"     [{label}] {short} {date} {subject}")
        if hidden:
            typer.echo(f"   ({hidden} more hidden — pass --all)")
