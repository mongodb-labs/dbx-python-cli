"""Remove command for removing repositories or repository groups."""

import json
import shutil
from pathlib import Path
from typing import List, Optional

import typer

from dbx_python_cli.utils import repo

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

    # Show what will be removed
    typer.echo(f"📦 Repositories to remove: {len(repos_to_remove)}\n")
    for repo_info in repos_to_remove:
        typer.echo(f"  • {repo_info['name']} ({repo_info['group']})")
        if verbose:
            typer.echo(f"    Path: {repo_info['path']}")

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
    for repo_info in repos_to_remove:
        repo_path = Path(repo_info["path"])
        try:
            if verbose:
                typer.echo(f"[verbose] Removing directory: {repo_path}")

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
    # (not applicable in flat mode — repos live directly in base_dir)
    if group and not flat and failed_count == 0:
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
