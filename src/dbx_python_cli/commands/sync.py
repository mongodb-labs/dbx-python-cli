"""Sync command for syncing repositories with upstream."""

import base64
import io
import subprocess
import sys
from pathlib import Path

import typer

from dbx_python_cli.utils import repo
from dbx_python_cli.utils.output import paginate_output, should_use_pager

app = typer.Typer(
    help="Sync repositories with upstream",
    no_args_is_help=True,
    invoke_without_command=True,
    context_settings={
        "allow_interspersed_args": True,
        "help_option_names": ["-h", "--help"],
    },
)


def _sync_repo_list(repos, header, ctx, verbose, force, dry_run):
    """Sync a list of repos, print a header and a summary, and honour the pager flag."""
    use_pager = should_use_pager(ctx, command_default=False)

    if use_pager:
        output_buffer = io.StringIO()
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        sys.stdout = output_buffer
        sys.stderr = output_buffer

    try:
        typer.echo(header)

        synced_count = 0
        skipped_count = 0
        failed_count = 0
        for i, repo_info in enumerate(repos):
            if i > 0:
                typer.echo("─" * 60)
            status = _sync_repository(
                repo_info["path"],
                repo_info["name"],
                verbose,
                force,
                dry_run,
                upstream_branch=repo_info.get("upstream_branch"),
            )
            if status == "skipped":
                skipped_count += 1
            elif status in ("synced", "dry_run"):
                synced_count += 1
            elif status == "failed":
                failed_count += 1

        if dry_run:
            summary = f"\n✨ Dry run complete! Checked {synced_count} repository(ies)"
        else:
            summary = f"\n✨ Done! Synced {synced_count} repository(ies)"
        if skipped_count:
            summary += f", skipped {skipped_count}"
        if failed_count:
            summary += f", failed {failed_count}"
        typer.echo(summary)
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


def _sync_all_branches(
    repo_info, config, verbose, force, dry_run, no_ci=False, branch_filter=None
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
    from dbx_python_cli.utils.repo import get_upstream_branch

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

    typer.echo(
        f"{'[dry-run] ' if dry_run else ''}Syncing {len(branches)} branch(es) of {name}:\n"
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
                typer.echo("[verbose] Fetching from upstream...")
            subprocess.run(
                ["git", "-C", str(path), "fetch", "upstream"],
                check=True,
                capture_output=not verbose,
                text=True,
            )
        except subprocess.CalledProcessError as e:
            typer.echo(
                f"❌ Failed to fetch from upstream: {e.stderr if not verbose else ''}",
                err=True,
            )
            raise typer.Exit(1)

        for i, branch in enumerate(branches):
            if i > 0:
                typer.echo("─" * 60)
            typer.echo(f"🌿 {branch}")
            typer.echo(f"🔍 Checking {name}")
            _show_commit_comparison(
                path, name, branch, f"upstream/{mapping[branch]}", verbose
            )
            synced_count += 1

        summary = f"\n✨ Dry run complete! Checked {synced_count} branch(es)"
        typer.echo(summary)
        return

    try:
        for i, branch in enumerate(branches):
            if i > 0:
                typer.echo("─" * 60)
            typer.echo(f"🌿 {branch}")
            try:
                subprocess.run(
                    ["git", "-C", str(path), "switch", branch],
                    check=True,
                    capture_output=not verbose,
                    text=True,
                )
            except subprocess.CalledProcessError as e:
                typer.echo(
                    f"❌ Failed to switch to {branch}: {e.stderr if not verbose else ''}",
                    err=True,
                )
                failed_branches.append(branch)
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
            )
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
    summary = f"\n✨ Done! Synced {synced_count} branch(es)"
    if skipped_count:
        summary += f", skipped {skipped_count}"
    if failed_branches:
        summary += f", failed {len(failed_branches)}"
    typer.echo(summary)

    if failed_branches:
        typer.echo(
            f"⚠️  Rebase these branch(es) manually: {', '.join(failed_branches)}",
            err=True,
        )

    if original_branch and not restored:
        typer.echo(
            f"⚠️  Could not switch back to original branch '{original_branch}'", err=True
        )

    # Re-run downstream CI for branches that actually rebased+pushed. The backend's
    # PR workflows check out the fork branch at a pinned ref, so a rebased branch is
    # only re-validated when those PRs' CI is re-run (see get_ci_rerun_targets).
    if not no_ci and synced_branches:
        _rerun_downstream_ci(config, group, name, synced_branches, verbose)


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

    from dbx_python_cli.utils.repo import get_ci_rerun_targets

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
            _retry_evergreen(target, value, branch, verbose)
        else:
            _dispatch_workflows(target, value, branch, verbose, _gh_json)


def _rerun_pr_ci(target, number, branch, verbose, _gh_json):
    """Re-run the workflow runs attached to an open PR's head commit."""
    import json

    typer.echo(f"♻️  {branch} → re-running CI on {target}#{number}...")
    try:
        pr = _gh_json(
            ["pr", "view", str(number), "--repo", target, "--json", "headRefOid"]
        )
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
                capture_output=not verbose,
                text=True,
            )
            requeued += 1
        except subprocess.CalledProcessError as e:
            if verbose:
                typer.echo(
                    f"   [verbose] rerun failed for run {run_id}: {e.stderr}",
                    err=True,
                )

    if requeued:
        typer.echo(f"   #{number} ✓ queued ({requeued} workflow run(s))")
    else:
        typer.echo(
            f"   #{number} ⚠️  no runs re-queued (already running or no permission)",
            err=True,
        )


def _retry_evergreen(target, number, branch, verbose):
    """Re-trigger a PR's Evergreen patch by commenting ``evergreen retry``.

    Evergreen's PR patch checks out the backend PR at a pinned fork ref, so a
    rebased (force-pushed) fork branch does not re-run Evergreen on its own.
    Commenting ``evergreen retry`` on the PR aborts any existing patch for the
    head commit and starts a fresh one. Best-effort: never fails the sync.
    """
    typer.echo(f"♻️  {branch} → retrying Evergreen on {target}#{number}...")
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
    no_ci: bool = typer.Option(
        False,
        "--no-ci",
        help="Skip re-running downstream CI (GitHub Actions + Evergreen retry) after --all-branches (see ci_rerun config)",
    ),
):
    """Sync repository with upstream by fetching, rebasing, and pushing.

    Rebase behavior:

    - Main/master branches: Rebases to upstream/main or upstream/master
    - Feature branches: Rebases to upstream's default branch (main/master)

    This allows you to keep your main branch in sync with upstream/main,
    while also keeping feature branches up-to-date with the latest upstream changes.

    Usage::

        dbx sync <repo_name>                    # Sync a single repository
        dbx sync <repo_name> --all-branches     # Sync every branch in the repo's upstream_branch map
        dbx sync <repo_name> -B <branch>        # Sync only the named branch(es) from that map (repeatable)
        dbx sync -g <group>                     # Sync all repos in a group
        dbx sync -a                             # Sync all repos in all groups
        dbx sync -g <group> <repo_name>         # Sync specific repo in a group
        dbx sync <repo_name> --force            # Force push after rebasing
        dbx sync <repo_name> --dry-run          # Show what would be synced
        dbx sync -g <group> --dry-run           # Preview group sync without changes
        dbx sync -a --dry-run                   # Preview all groups sync without changes
        dbx sync -g <group> <repo_name> --dry-run  # Preview single repo in group

    Examples::

        dbx sync mongo-python-driver                    # Sync single repo
        dbx sync django --all-branches                  # Sync every Django fork release branch
        dbx sync django -b --dry-run                    # Preview syncing all branches
        dbx sync -g pymongo                             # Sync all repos in group
        dbx sync -a                                     # Sync all repos in all groups
        dbx sync -g pymongo mongo-python-driver         # Sync specific repo in pymongo group
        dbx sync my-repo --force                        # Force push after rebase
        dbx sync my-repo --dry-run                      # Preview changes without syncing
        dbx sync -g pymongo --dry-run                   # Preview group sync
        dbx sync -a --dry-run                           # Preview all groups sync
        dbx sync -g pymongo mongo-python-driver --dry-run  # Preview specific repo
    """
    from dbx_python_cli.utils.repo import (
        find_all_repos,
        find_repo_by_name,
        find_repo_by_path,
        get_upstream_branch,
        is_path_like,
    )

    def _enrich(repo_list):
        """Attach upstream_branch from config to each repo_info dict."""
        for r in repo_list:
            r["upstream_branch"] = get_upstream_branch(config, r["group"], r["name"])
        return repo_list

    # Get verbose flag from parent context
    verbose = ctx.obj.get("verbose", False) if ctx.obj else False

    try:
        config = repo.get_config()
        base_dir = repo.get_base_dir(config)
        groups = repo.get_repo_groups(config)

        if verbose:
            typer.echo(f"[verbose] Using base directory: {base_dir}")
            typer.echo(f"[verbose] Available groups: {list(groups.keys())}\n")

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
                typer.echo("\nClone repositories using: dbx clone -a")
                raise typer.Exit(1)

            _sync_repo_list(
                target_repos,
                f"Syncing {len(target_repos)} repository(ies) across {len(non_global_groups)} group(s):\n",
                ctx,
                verbose,
                force,
                dry_run,
            )
            return

        # Handle syncing specific/all branches in a single repo's
        # upstream_branch mapping.
        if all_branches or branch:
            flag = "--all-branches" if all_branches else "--branch"
            if not repo_name:
                typer.echo(f"❌ Error: {flag} requires a repository name", err=True)
                typer.echo(f"\nUsage: dbx sync <repo-name> {flag}")
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
                from dbx_python_cli.utils.repo import find_all_repos_by_name

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
                typer.echo("\nUse 'dbx list' to see available repositories")
                raise typer.Exit(1)

            _sync_all_branches(
                repo_info,
                config,
                verbose,
                force,
                dry_run,
                no_ci,
                branch_filter=branch or None,
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
            from dbx_python_cli.utils.repo import find_all_repos_by_name

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
                typer.echo(f"\nClone the repository using: dbx clone -g {group}")
                raise typer.Exit(1)

            _sync_repository(
                repo_info["path"],
                repo_info["name"],
                verbose,
                force,
                dry_run,
                upstream_branch=get_upstream_branch(config, group, repo_info["name"]),
            )

            if dry_run:
                typer.echo("\n✨ Dry run complete!")
            else:
                typer.echo("\n✨ Done!")
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
                typer.echo(f"\nClone repositories using: dbx clone -g {group}")
                raise typer.Exit(1)

            _sync_repo_list(
                group_repos,
                f"Syncing {len(group_repos)} repository(ies) in group '{group}':\n",
                ctx,
                verbose,
                force,
                dry_run,
            )
            return

        # Handle single repo sync
        if not repo_name:
            typer.echo("❌ Error: Repository name or group required", err=True)
            typer.echo("\nUsage: dbx sync <repo-name>")
            typer.echo("   or: dbx sync -g <group>")
            typer.echo("   or: dbx sync -g <group> <repo-name>")
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
                typer.echo("\nUse 'dbx list' to see available repositories")
                raise typer.Exit(1)
        else:
            repo_info = find_repo_by_name(repo_name, base_dir, config)
            if not repo_info:
                typer.echo(f"❌ Error: Repository '{repo_name}' not found", err=True)
                typer.echo("\nUse 'dbx list' to see available repositories")
                raise typer.Exit(1)

        _sync_repository(
            repo_info["path"],
            repo_info["name"],
            verbose,
            force,
            dry_run,
            upstream_branch=get_upstream_branch(
                config, repo_info.get("group", ""), repo_info["name"]
            ),
        )

        if dry_run:
            typer.echo("\n✨ Dry run complete!")
        else:
            typer.echo("\n✨ Done!")

    except Exception as e:
        typer.echo(f"❌ Error: {e}", err=True)
        raise typer.Exit(1)


def _sync_repository(
    repo_path: Path,
    repo_name: str,
    verbose: bool = False,
    force: bool = False,
    dry_run: bool = False,
    upstream_branch: str | None = None,
    abort_on_conflict: bool = False,
) -> str:
    """Sync a single repository with upstream.

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
    """
    if dry_run:
        typer.echo(f"🔍 Checking {repo_name}")
    else:
        typer.echo(f"🔄 Syncing {repo_name}")

    if verbose:
        typer.echo(f"[verbose] Repository path: {repo_path}")
        if force:
            typer.echo("[verbose] Force push enabled")
        if dry_run:
            typer.echo("[verbose] Dry run mode enabled")

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
            typer.echo(
                "⚠️  No 'upstream' remote found (skipping)",
                err=True,
            )
            return "skipped"

    except subprocess.CalledProcessError as e:
        typer.echo(
            f"❌ Failed to check remotes: {e.stderr}",
            err=True,
        )
        return "failed"

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
            typer.echo(
                "⚠️  Not on a branch (detached HEAD), skipping",
                err=True,
            )
            return "skipped"

        if verbose:
            typer.echo(f"[verbose] Current branch: {current_branch}")

    except subprocess.CalledProcessError as e:
        typer.echo(
            f"❌ Failed to get current branch: {e.stderr}",
            err=True,
        )
        return "failed"

    # Fetch from upstream
    try:
        if verbose:
            typer.echo("[verbose] Fetching from upstream...")

        subprocess.run(
            ["git", "-C", str(repo_path), "fetch", "upstream"],
            check=True,
            capture_output=not verbose,
            text=True,
        )

    except subprocess.CalledProcessError as e:
        typer.echo(
            f"❌ Failed to fetch from upstream: {e.stderr if not verbose else ''}",
            err=True,
        )
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
            typer.echo(f"[verbose] Main branch detected, rebasing to {rebase_target}")
    elif upstream_branch:
        rebase_target = f"upstream/{upstream_branch}"
        if verbose:
            typer.echo(
                f"[verbose] Using configured upstream_branch, rebasing to {rebase_target}"
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
                typer.echo(
                    f"[verbose] Upstream has matching branch, rebasing to {rebase_target}"
                )
        except subprocess.CalledProcessError:
            # No matching upstream branch — fall back to upstream's default branch
            upstream_default = _get_upstream_default_branch(repo_path, verbose)
            if not upstream_default:
                # Fallback to trying common default branches
                if verbose:
                    typer.echo(
                        "[verbose] Could not detect upstream default, trying main/master..."
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
                    typer.echo(
                        "❌ Could not determine upstream default branch",
                        err=True,
                    )
                    return "failed"

            rebase_target = f"upstream/{upstream_default}"
            if verbose:
                typer.echo(
                    f"[verbose] Feature branch detected, rebasing to {rebase_target}"
                )

    # If dry-run, compare commits and show what would happen
    if dry_run:
        _show_commit_comparison(
            repo_path, repo_name, current_branch, rebase_target, verbose
        )
        return "dry_run"

    # Rebase on target branch
    try:
        if verbose:
            typer.echo(f"[verbose] Rebasing on {rebase_target}...")

        subprocess.run(
            ["git", "-C", str(repo_path), "rebase", rebase_target],
            check=True,
            capture_output=not verbose,
            text=True,
        )

    except subprocess.CalledProcessError as e:
        typer.echo(
            f"❌ Failed to rebase {current_branch} on {rebase_target}",
            err=True,
        )
        if not verbose and e.stderr:
            typer.echo(f"  {e.stderr.strip()}", err=True)

        if abort_on_conflict:
            # Leave the repo in a clean state so callers that iterate over
            # multiple branches (dbx sync --all-branches) can continue and
            # restore the original branch. Point the user at a manual rebase.
            subprocess.run(
                ["git", "-C", str(repo_path), "rebase", "--abort"],
                capture_output=True,
                text=True,
            )
            typer.echo(
                f"  Rebase aborted. Resolve manually: cd {repo_path} && "
                f"git switch {current_branch} && git rebase {rebase_target}",
                err=True,
            )
        else:
            typer.echo(
                f"  You may need to resolve conflicts manually in {repo_path}",
                err=True,
            )
        return "failed"

    # Push to origin
    try:
        if verbose:
            push_type = "force pushing" if force else "pushing"
            typer.echo(
                f"[verbose] {push_type.capitalize()} to origin/{current_branch}..."
            )

        push_cmd = ["git", "-C", str(repo_path), "push"]
        if force:
            push_cmd.append("--force-with-lease")
        push_cmd.extend(["origin", current_branch])

        subprocess.run(
            push_cmd,
            check=True,
            capture_output=not verbose,
            text=True,
        )

        typer.echo("✅ Synced and pushed successfully")
        return "synced"

    except subprocess.CalledProcessError as e:
        typer.echo(
            f"⚠️  Synced but failed to push to origin/{current_branch}",
            err=True,
        )
        if not verbose and e.stderr:
            typer.echo(f"  {e.stderr.strip()}", err=True)
        typer.echo(
            f"  Try running: dbx sync {repo_name} --force",
            err=True,
        )
        return "failed"


def _get_upstream_default_branch(repo_path: Path, verbose: bool = False) -> str | None:
    """Get the default branch of the upstream remote.

    Args:
        repo_path: Path to the repository
        verbose: Whether to print verbose output

    Returns:
        str: The default branch name (e.g., 'main', 'master'), or None if not found
    """
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
                typer.echo(
                    f"[verbose] Detected upstream default branch: {default_branch}"
                )
            return default_branch
    except subprocess.CalledProcessError:
        # symbolic-ref might fail if upstream/HEAD is not set
        # Try to set it by running remote show
        try:
            if verbose:
                typer.echo("[verbose] Attempting to detect upstream default branch...")
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
                        typer.echo(
                            f"[verbose] Detected upstream default branch: {default_branch}"
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
):
    """Show comparison between upstream and origin commits.

    Args:
        repo_path: Path to the repository
        repo_name: Name of the repository
        current_branch: Current branch name
        rebase_target: Target branch to rebase onto (e.g., 'upstream/main')
        verbose: Whether to print verbose output
    """
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
            typer.echo(
                f"⚠️  No origin/{current_branch} branch found",
                err=True,
            )
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
            typer.echo(f"✅ Already up to date with {rebase_target}")
        else:
            status_parts = []
            if commits_behind > 0:
                status_parts.append(
                    f"{commits_behind} commit(s) behind {rebase_target}"
                )
            if commits_ahead > 0:
                status_parts.append(f"{commits_ahead} commit(s) ahead")

            status = ", ".join(status_parts)
            typer.echo(f"📊 {status}")

            # Show commit details if verbose or if there are commits
            if verbose or commits_behind > 0 or commits_ahead > 0:
                # Show commits that would be applied from upstream
                if commits_behind > 0:
                    if commits_behind > 10:
                        typer.echo(
                            f"\nCommits from {rebase_target} that would be applied"
                            f" (first 10 of {commits_behind}):"
                        )
                    else:
                        typer.echo(
                            f"\nCommits from {rebase_target} that would be applied:"
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
                            typer.echo(f"  + {line}")

                # Show commits in origin that would be rebased
                if commits_ahead > 0:
                    if commits_ahead > 10:
                        typer.echo(
                            f"\nCommits in origin/{current_branch} that would be rebased"
                            f" (first 10 of {commits_ahead}):"
                        )
                    else:
                        typer.echo(
                            f"\nCommits in origin/{current_branch} that would be rebased:"
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
                            typer.echo(f"  * {line}")

                typer.echo("")  # Empty line for spacing

    except subprocess.CalledProcessError as e:
        typer.echo(
            f"❌ Failed to compare commits: {e.stderr if e.stderr else 'Unknown error'}",
            err=True,
        )
