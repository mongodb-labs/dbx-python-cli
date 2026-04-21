"""Sync command for syncing repositories with upstream."""

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
):
    """Sync repository with upstream by fetching, rebasing, and pushing.

    Rebase behavior:

    - Main/master branches: Rebases to upstream/main or upstream/master
    - Feature branches: Rebases to upstream's default branch (main/master)

    This allows you to keep your main branch in sync with upstream/main,
    while also keeping feature branches up-to-date with the latest upstream changes.

    Usage::

        dbx sync <repo_name>                    # Sync a single repository
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
    )

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
            target_repos = [r for r in all_repos if r["group"] in non_global_groups]

            if not target_repos:
                typer.echo("❌ Error: No repositories found in any group.", err=True)
                typer.echo("\nClone repositories using: dbx clone -a")
                raise typer.Exit(1)

            # Check if pager is requested
            use_pager = should_use_pager(ctx, command_default=False)

            # Only capture output if pager is requested
            if use_pager:
                output_buffer = io.StringIO()
                old_stdout = sys.stdout
                old_stderr = sys.stderr
                sys.stdout = output_buffer
                sys.stderr = output_buffer

            try:
                typer.echo(
                    f"Syncing {len(target_repos)} repository(ies) across {len(non_global_groups)} group(s):\n"
                )

                synced_count = 0
                skipped_count = 0
                for i, repo_info in enumerate(target_repos):
                    # Add separator between repos (not before first or after last)
                    if i > 0:
                        typer.echo("─" * 60)
                    status = _sync_repository(
                        repo_info["path"], repo_info["name"], verbose, force, dry_run
                    )
                    if status == "skipped":
                        skipped_count += 1
                    elif status in ("synced", "dry_run"):
                        synced_count += 1

                if dry_run:
                    summary = (
                        f"\n✨ Dry run complete! Checked {synced_count} repository(ies)"
                    )
                else:
                    summary = f"\n✨ Done! Synced {synced_count} repository(ies)"
                if skipped_count:
                    summary += f", skipped {skipped_count}"
                typer.echo(summary)
            finally:
                if use_pager:
                    sys.stdout = old_stdout
                    sys.stderr = old_stderr

            # Display output with pagination if requested
            if use_pager:
                output = output_buffer.getvalue()
                paginate_output(output, use_pager)
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
                repo_info["path"], repo_info["name"], verbose, force, dry_run
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
            group_repos = [r for r in all_repos if r["group"] == group]

            if not group_repos:
                typer.echo(
                    f"❌ Error: No repositories found for group '{group}'.", err=True
                )
                typer.echo(f"\nClone repositories using: dbx clone -g {group}")
                raise typer.Exit(1)

            # Check if pager is requested
            use_pager = should_use_pager(ctx, command_default=False)

            # Only capture output if pager is requested
            if use_pager:
                output_buffer = io.StringIO()
                old_stdout = sys.stdout
                old_stderr = sys.stderr
                sys.stdout = output_buffer
                sys.stderr = output_buffer

            try:
                typer.echo(
                    f"Syncing {len(group_repos)} repository(ies) in group '{group}':\n"
                )

                synced_count = 0
                skipped_count = 0
                for i, repo_info in enumerate(group_repos):
                    # Add separator between repos (not before first or after last)
                    if i > 0:
                        typer.echo("─" * 60)
                    status = _sync_repository(
                        repo_info["path"], repo_info["name"], verbose, force, dry_run
                    )
                    if status == "skipped":
                        skipped_count += 1
                    elif status in ("synced", "dry_run"):
                        synced_count += 1

                if dry_run:
                    summary = (
                        f"\n✨ Dry run complete! Checked {synced_count} repository(ies)"
                    )
                else:
                    summary = f"\n✨ Done! Synced {synced_count} repository(ies)"
                if skipped_count:
                    summary += f", skipped {skipped_count}"
                typer.echo(summary)
            finally:
                if use_pager:
                    sys.stdout = old_stdout
                    sys.stderr = old_stderr

            # Display output with pagination if requested
            if use_pager:
                output = output_buffer.getvalue()
                paginate_output(output, use_pager)
            return

        # Handle single repo sync
        if not repo_name:
            typer.echo("❌ Error: Repository name or group required", err=True)
            typer.echo("\nUsage: dbx sync <repo-name>")
            typer.echo("   or: dbx sync -g <group>")
            typer.echo("   or: dbx sync -g <group> <repo-name>")
            raise typer.Exit(1)

        # Detect path-like inputs: ".", "..", absolute paths, relative paths with /
        _is_path_like = (
            repo_name in (".", "..")
            or repo_name.startswith(("./", "../", "/", "~/"))
            or "/" in repo_name
            or Path(repo_name).is_dir()
        )

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

        _sync_repository(repo_info["path"], repo_info["name"], verbose, force, dry_run)

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
) -> str:
    """Sync a single repository with upstream.

    For main/master branches: rebases to upstream/<branch_name>
    For feature branches: rebases to upstream's default branch (main/master)

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
    # For feature branches: rebase to upstream's default branch
    if current_branch in ["main", "master"]:
        rebase_target = f"upstream/{current_branch}"
        if verbose:
            typer.echo(f"[verbose] Main branch detected, rebasing to {rebase_target}")
    else:
        # Get upstream's default branch
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
            f"❌ Failed to rebase on {rebase_target}",
            err=True,
        )
        if not verbose and e.stderr:
            typer.echo(f"  {e.stderr.strip()}", err=True)
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
        return "synced"


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
                    typer.echo(f"\nCommits from {rebase_target} that would be applied:")
                    result = subprocess.run(
                        [
                            "git",
                            "-C",
                            str(repo_path),
                            "log",
                            "--oneline",
                            "--no-decorate",
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
