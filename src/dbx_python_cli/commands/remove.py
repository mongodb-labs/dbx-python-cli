"""Remove command for removing repositories or repository groups."""

import json
import shutil
from pathlib import Path
from typing import List, Optional

import typer

from dbx_python_cli.utils import repo
from dbx_python_cli.utils.worktree import (
    list_worktrees,
    prune_worktrees,
    remove_worktree,
)


def _attached_worktrees(repo_info, already_selected):
    """Return repo_info dicts for the linked worktrees of a primary clone.

    A worktree's ``.git`` file points into its clone's object store, so deleting
    the clone on its own leaves the worktree directory intact but permanently
    broken — and unreachable by ``dbx worktree remove``, which needs the clone.
    Removing a clone therefore has to take its worktrees with it.
    """
    repo_path = Path(repo_info["path"])
    selected = {Path(r["path"]).resolve() for r in already_selected}

    found = []
    for entry in list_worktrees(repo_path):
        path = Path(entry["path"])
        if path.resolve() == repo_path.resolve() or path.resolve() in selected:
            continue
        if not path.exists():
            continue
        found.append(
            {
                "name": path.name,
                "path": path,
                "group": repo_info.get("group", ""),
                "worktree": True,
            }
        )
    return found


def _group_dir_extras(group_dir, repos_to_remove):
    """Return entries in a group directory that are not one of the listed repos.

    Removing a group deletes the whole directory, which also holds the
    group-level ``.venv`` that ``dbx clone`` creates plus anything else the user
    left there. Those are not repositories, so they never appear in the repo
    list — name them explicitly rather than deleting them unannounced.
    """
    if not group_dir.exists():
        return []
    repo_paths = {Path(r["path"]).resolve() for r in repos_to_remove}
    return sorted(
        entry for entry in group_dir.iterdir() if entry.resolve() not in repo_paths
    )


app = typer.Typer(
    help="Remove repositories or repository groups",
    no_args_is_help=True,
    invoke_without_command=True,
    context_settings={
        "allow_interspersed_args": False,
        "help_option_names": ["-h", "--help"],
    },
)


@app.callback()
def remove_callback(
    ctx: typer.Context,
    repo_names: Optional[List[str]] = typer.Argument(
        None,
        help="Repository name(s) to remove (e.g., mongo-python-driver)",
    ),
    group: Optional[str] = typer.Option(
        None,
        "--group",
        "-g",
        help="Remove all repositories in this group (e.g., pymongo, langchain)",
    ),
    repo_group: Optional[str] = typer.Option(
        None,
        "-G",
        help="Specify which group to use when repo exists in multiple groups",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        "-y",
        help="Skip confirmation prompt",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show what would be removed without deleting anything",
    ),
):
    """Remove repositories or repository groups.

    Examples::

        dbx remove mongo-python-driver              # Remove a single repo
        dbx remove repo1 repo2 repo3                # Remove multiple repos
        dbx remove mongo-python-driver -G langchain # Remove from specific group
        dbx remove -g pymongo                       # Remove all repos in group
        dbx remove -g pymongo -f                    # Remove without confirmation
    """
    # Get verbose flag from parent context
    verbose = ctx.obj.get("verbose", False) if ctx.obj else False

    try:
        config = repo.get_config()
        base_dir = repo.get_base_dir(config)
        flat = repo.is_flat_mode(config)
        if verbose:
            typer.echo(f"[verbose] Using base directory: {base_dir}")
            typer.echo(f"[verbose] Config:\n{json.dumps(config, indent=4)}\n")
    except Exception as e:
        typer.echo(f"❌ Error: {e}", err=True)
        raise typer.Exit(1)

    # Import repo utilities
    from dbx_python_cli.utils.repo import find_all_repos

    # Get all repos
    all_repos = find_all_repos(base_dir, config)

    # Determine what to remove
    repos_to_remove = []

    # Case 1: Remove all repos in a group (-g flag)
    if group:
        if repo_names:
            typer.echo(
                "❌ Error: Cannot specify both repository names and -g flag", err=True
            )
            raise typer.Exit(1)

        # Find all repos in the group
        group_repos = [r for r in all_repos if r["group"] == group]

        if not group_repos:
            typer.echo(f"❌ Error: No repositories found in group '{group}'", err=True)
            typer.echo("\nRun 'dbx list' to see available repositories")
            raise typer.Exit(1)

        repos_to_remove = group_repos

    # Case 2: Remove specific repo(s)
    elif repo_names:
        for repo_name in repo_names:
            # If -G flag is specified, look only in that group
            if repo_group:
                matching_repos = [
                    r
                    for r in all_repos
                    if r["name"] == repo_name and r["group"] == repo_group
                ]
                if not matching_repos:
                    typer.echo(
                        f"❌ Error: Repository '{repo_name}' not found in group '{repo_group}'",
                        err=True,
                    )
                    typer.echo("\nRun 'dbx list' to see available repositories")
                    raise typer.Exit(1)
                repos_to_remove.append(matching_repos[0])
            else:
                # Find all repos with this name
                matching_repos = [r for r in all_repos if r["name"] == repo_name]

                if not matching_repos:
                    typer.echo(
                        f"❌ Error: Repository '{repo_name}' not found", err=True
                    )
                    typer.echo("\nRun 'dbx list' to see available repositories")
                    raise typer.Exit(1)

                # If repo exists in multiple groups, warn and use first match
                if len(matching_repos) > 1:
                    groups = [r["group"] for r in matching_repos]
                    typer.echo(
                        f"⚠️  Warning: Repository '{repo_name}' found in multiple groups: {', '.join(groups)}",
                        err=True,
                    )
                    typer.echo(
                        f"⚠️  Using '{matching_repos[0]['group']}' group. Use -G to specify a different group.\n",
                        err=True,
                    )

                repos_to_remove.append(matching_repos[0])

    else:
        typer.echo("❌ Error: Repository name(s) or group required", err=True)
        typer.echo("\nUsage: dbx remove <repo_name> [<repo_name> ...]")
        typer.echo("   or: dbx remove -g <group>")
        typer.echo("   or: dbx list")
        raise typer.Exit(1)

    # Pull in the worktrees attached to any primary clone being removed. Left
    # behind, they would point at a deleted object store and no dbx command
    # could clean them up.
    for repo_info in list(repos_to_remove):
        if repo_info.get("worktree"):
            continue
        for worktree_info in _attached_worktrees(repo_info, repos_to_remove):
            typer.echo(
                f"ℹ️  Also removing worktree '{worktree_info['name']}' "
                f"(attached to {repo_info['name']})"
            )
            repos_to_remove.append(worktree_info)

    # Show what will be removed
    typer.echo(f"📦 Repositories to remove: {len(repos_to_remove)}\n")
    for repo_info in repos_to_remove:
        label = " [worktree]" if repo_info.get("worktree") else ""
        typer.echo(f"  • {repo_info['name']} ({repo_info['group']}){label}")
        if verbose:
            typer.echo(f"    Path: {repo_info['path']}")

    # Removing a group deletes its whole directory, including anything in it
    # that is not a repository (notably the group-level venv).
    group_extras = []
    if group and not flat:
        group_extras = _group_dir_extras(base_dir / group, repos_to_remove)
        if group_extras:
            typer.echo(
                f"\n⚠️  Removing group '{group}' also deletes the group directory "
                f"{base_dir / group}, including:"
            )
            for entry in group_extras:
                typer.echo(f"  • {entry.name}")

    # Short-circuit for dry run — print list and exit without deleting
    if dry_run:
        typer.echo("\n🔍 Dry run — no repositories were removed.")
        return

    # Confirm removal unless --force is used
    if not force:
        typer.echo()
        confirm = typer.confirm(
            "⚠️  Are you sure you want to remove these repositories?",
            default=False,
        )
        if not confirm:
            typer.echo("❌ Removal cancelled")
            raise typer.Exit(0)

    # Remove the repositories
    removed_count = 0
    failed_count = 0

    typer.echo()
    # Remove worktrees before their primary clones: `git worktree remove` needs
    # the clone's .git directory, and deleting the clone first would strand the
    # worktree with a dangling gitdir pointer.
    repos_to_remove = sorted(
        repos_to_remove, key=lambda r: not r.get("worktree", False)
    )
    # Paths whose worktree removal failed. Deleting the clone anyway would
    # strand them with a dangling gitdir, so its removal is skipped instead.
    failed_worktrees = []
    for repo_info in repos_to_remove:
        repo_path = Path(repo_info["path"])
        try:
            if repo_info.get("worktree"):
                if verbose:
                    typer.echo(f"[verbose] Removing worktree: {repo_path}")
                # --force: the confirmation prompt above is the safety gate, and
                # git otherwise refuses whenever the worktree is dirty.
                ok, message = remove_worktree(
                    repo_path, repo_path, force=True, verbose=verbose
                )
                if not ok:
                    failed_worktrees.append(repo_path.resolve())
                    raise RuntimeError(message)
            else:
                still_attached = {
                    Path(w["path"]).resolve()
                    for w in _attached_worktrees(repo_info, [])
                }
                if still_attached & set(failed_worktrees):
                    typer.echo(
                        f"⏭️  Skipping {repo_info['name']}: its worktree(s) could not "
                        f"be removed, and deleting the clone would break them",
                        err=True,
                    )
                    failed_count += 1
                    continue
                if verbose:
                    typer.echo(f"[verbose] Removing directory: {repo_path}")
                # Drop registrations for worktrees removed above so the clone's
                # metadata is consistent if anything later inspects it.
                prune_worktrees(repo_path, verbose=verbose)
                shutil.rmtree(repo_path)
            typer.echo(f"✅ Removed {repo_info['name']} ({repo_info['group']})")
            removed_count += 1
        except Exception as e:
            typer.echo(f"❌ Failed to remove {repo_info['name']}: {e}", err=True)
            failed_count += 1

    # Summary
    typer.echo()
    if removed_count > 0:
        typer.echo(f"✅ Successfully removed {removed_count} repository(ies)")
    if failed_count > 0:
        typer.echo(f"❌ Failed to remove {failed_count} repository(ies)")
        raise typer.Exit(1)

    # When removing an entire group, also remove the group directory itself
    # (not applicable in flat mode — repos live directly in base_dir). Anything
    # in it that is not a repo was listed as `group_extras` before confirming.
    # Unreachable when failed_count > 0: that path exits above.
    if group and not flat:
        group_dir = base_dir / group
        if group_dir.exists():
            try:
                if verbose:
                    typer.echo(f"[verbose] Removing group directory: {group_dir}")
                shutil.rmtree(group_dir)
                typer.echo(f"✅ Removed group directory {group_dir}")
            except Exception as e:
                typer.echo(f"❌ Failed to remove group directory: {e}", err=True)
                raise typer.Exit(1)
