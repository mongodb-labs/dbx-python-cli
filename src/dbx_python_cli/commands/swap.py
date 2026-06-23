"""Swap command for swapping origin and upstream remotes."""

import subprocess
from pathlib import Path

import typer

from dbx_python_cli.utils.repo import (
    find_repo_by_name,
    find_repo_by_path,
    get_base_dir,
    get_config,
    is_path_like,
)

app = typer.Typer(
    help="Swap origin and upstream git remotes",
    no_args_is_help=True,
    invoke_without_command=True,
    context_settings={
        "allow_interspersed_args": True,
        "help_option_names": ["-h", "--help"],
    },
)


def _get_remote_url(repo_path: Path, remote: str) -> str | None:
    """Return the URL for a remote, or None if the remote doesn't exist."""
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", remote],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return None


def _set_remote_url(repo_path: Path, remote: str, url: str) -> None:
    subprocess.run(
        ["git", "remote", "set-url", remote, url],
        cwd=repo_path,
        check=True,
    )


def _swap_remotes(
    repo_path: Path, repo_name: str, verbose: bool, dry_run: bool
) -> bool:
    """Swap origin and upstream for a single repo. Returns True on success."""
    origin_url = _get_remote_url(repo_path, "origin")
    upstream_url = _get_remote_url(repo_path, "upstream")

    if not origin_url:
        typer.echo(f"❌ {repo_name}: no 'origin' remote found", err=True)
        return False
    if not upstream_url:
        typer.echo(f"❌ {repo_name}: no 'upstream' remote found", err=True)
        return False

    if verbose or dry_run:
        typer.echo(f"  origin:   {origin_url}")
        typer.echo(f"  upstream: {upstream_url}")

    if dry_run:
        typer.echo(f"  → would set origin={upstream_url}, upstream={origin_url}")
        return True

    _set_remote_url(repo_path, "origin", upstream_url)
    _set_remote_url(repo_path, "upstream", origin_url)
    typer.echo(
        f"🔄 {repo_name}: swapped — origin={upstream_url}, upstream={origin_url}"
    )
    return True


@app.callback()
def swap_callback(
    ctx: typer.Context,
    repo_name: str = typer.Argument(
        None,
        help="Repository name or '.' for the current directory",
    ),
    group: str = typer.Option(
        None,
        "--group",
        "-g",
        help="Swap remotes in all repositories in a group",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show what would be swapped without making changes",
    ),
):
    """Swap origin and upstream git remotes in a repository.

    Usage::

        dbx swap <repo_name>          # Swap by name
        dbx swap .                    # Swap in the current directory
        dbx swap -g <group>           # Swap all repos in a group

    Examples::

        dbx swap mongo-python-driver
        dbx swap .
        dbx swap -g pymongo --dry-run
    """
    verbose = ctx.obj.get("verbose", False) if ctx.obj else False

    try:
        config = get_config()
        base_dir = get_base_dir(config)
    except Exception as e:
        typer.echo(f"❌ Error: {e}", err=True)
        raise typer.Exit(1)

    # Group mode
    if group:
        from dbx_python_cli.utils.repo import find_all_repos

        all_repos = find_all_repos(base_dir, config)
        group_repos = [r for r in all_repos if r["group"] == group]
        if not group_repos:
            typer.echo(
                f"❌ Error: No cloned repositories found in group '{group}'", err=True
            )
            raise typer.Exit(1)
        typer.echo(
            f"{'[dry-run] ' if dry_run else ''}Swapping remotes in {len(group_repos)} repo(s) in group '{group}':\n"
        )
        for r in sorted(group_repos, key=lambda x: x["name"]):
            if verbose or dry_run:
                typer.echo(f"📦 {r['name']}:")
            _swap_remotes(r["path"], r["name"], verbose, dry_run)
        return

    # Single repo mode
    if not repo_name:
        typer.echo("❌ Error: Repository name or -g <group> required", err=True)
        raise typer.Exit(1)

    _is_path_like = is_path_like(repo_name)

    if _is_path_like:
        repo_info = find_repo_by_path(repo_name, base_dir, config)
        if not repo_info:
            typer.echo(
                f"❌ Error: No managed repository found at '{Path(repo_name).resolve()}'",
                err=True,
            )
            raise typer.Exit(1)
    else:
        repo_info = find_repo_by_name(repo_name, base_dir, config)
        if not repo_info:
            typer.echo(f"❌ Error: Repository '{repo_name}' not found", err=True)
            typer.echo("\nUse 'dbx list' to see available repositories")
            raise typer.Exit(1)

    if dry_run or verbose:
        typer.echo(f"📦 {repo_info['name']}:")
    if not _swap_remotes(repo_info["path"], repo_info["name"], verbose, dry_run):
        raise typer.Exit(1)
