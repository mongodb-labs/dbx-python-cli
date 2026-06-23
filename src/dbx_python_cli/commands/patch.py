"""Patch command for creating Evergreen patches."""

import subprocess
from pathlib import Path

import typer

from dbx_python_cli.utils.repo import (
    find_repo_by_name,
    find_repo_by_path,
    get_base_dir,
    get_config,
    get_evergreen_project_name,
    is_path_like,
)

app = typer.Typer(
    help="Create Evergreen patches",
    no_args_is_help=True,
    invoke_without_command=True,
    context_settings={
        "allow_interspersed_args": True,
        "help_option_names": ["-h", "--help"],
    },
)


@app.callback()
def patch_callback(
    ctx: typer.Context,
    repo_name: str = typer.Argument(
        None,
        help="Repository name to patch (e.g., mongo-python-driver)",
    ),
    patch_args: list[str] = typer.Argument(
        None,
        help="Additional arguments to pass to evergreen patch",
    ),
):
    """Create an Evergreen patch for a repository.

    Usage::

        dbx patch <repo_name>
        dbx patch .                          # Use current directory

    Examples::

        dbx patch mongo-python-driver        # Patch mongo-python-driver
        dbx patch .                          # Patch repo in current directory
    """
    verbose = ctx.obj.get("verbose", False) if ctx.obj else False

    if not repo_name:
        typer.echo("❌ Error: Repository name is required", err=True)
        typer.echo("\nUsage: dbx patch <repo-name>")
        raise typer.Exit(1)

    if patch_args is None:
        patch_args = []

    try:
        config = get_config()
        base_dir = get_base_dir(config)

        if verbose:
            typer.echo(f"[verbose] Using base directory: {base_dir}")

        _is_path_like = is_path_like(repo_name)

        if _is_path_like:
            repo = find_repo_by_path(repo_name, base_dir, config)
            if not repo:
                typer.echo(
                    f"❌ Error: No managed repository found at '{Path(repo_name).resolve()}'",
                    err=True,
                )
                typer.echo("\nUse 'dbx list' to see available repositories")
                raise typer.Exit(1)
            repo_name = repo["name"]
        else:
            repo = find_repo_by_name(repo_name, base_dir, config)
            if not repo:
                typer.echo(f"❌ Error: Repository '{repo_name}' not found", err=True)
                typer.echo("\nUse 'dbx list' to see available repositories")
                raise typer.Exit(1)

        project_name = get_evergreen_project_name(config, repo_name)
        if not project_name:
            typer.echo(
                f"❌ Error: No evergreen project_name configured for '{repo_name}'",
                err=True,
            )
            typer.echo(
                f'\nAdd to config.toml:\n  [evergreen.{repo_name}]\n  project_name = "<evg-project>"',
                err=True,
            )
            raise typer.Exit(1)

        cmd = ["evergreen", "patch", "-p", project_name, "-u"] + list(patch_args)

        if verbose:
            typer.echo(f"[verbose] Running command: {' '.join(cmd)}")
            typer.echo(f"[verbose] Working directory: {repo['path']}\n")

        typer.echo(
            f"🌲 Running evergreen patch for {repo_name} (project: {project_name})..."
        )

        result = subprocess.run(cmd, cwd=str(repo["path"]), check=False)

        if result.returncode != 0:
            raise typer.Exit(result.returncode)

    except typer.Exit:
        raise
    except Exception as e:
        typer.echo(f"❌ Error: {e}", err=True)
        raise typer.Exit(1)
