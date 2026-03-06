"""Just command for running just commands in repositories."""

import os
import subprocess
from pathlib import Path

import typer

from dbx_python_cli.commands.repo_utils import (
    find_all_repos,
    find_repo_by_name,
    get_base_dir,
    get_config,
    get_test_env_vars,
)

# Create a Typer app that will act as a single command
app = typer.Typer(
    help="Just commands",
    no_args_is_help=True,
    invoke_without_command=True,
    context_settings={
        "allow_interspersed_args": False,
        "help_option_names": ["-h", "--help"],
    },
)


def has_justfile(repo_path: Path) -> bool:
    """Check if a repository has a justfile."""
    return (repo_path / "justfile").exists() or (repo_path / "Justfile").exists()


def _list_repos_with_justfiles(ctx: typer.Context):
    """List all repositories that have justfiles - internal function."""
    # Get verbose flag from parent context
    verbose = ctx.obj.get("verbose", False) if ctx.obj else False

    try:
        config = get_config()
        base_dir = get_base_dir(config)
        if verbose:
            typer.echo(f"[verbose] Using base directory: {base_dir}")
            typer.echo(f"[verbose] Config: {config}\n")
    except Exception as e:
        typer.echo(f"❌ Error: {e}", err=True)
        raise typer.Exit(1)

    # Get all repos and filter for those with justfiles
    all_repos = find_all_repos(base_dir)
    repos_with_justfiles = [repo for repo in all_repos if has_justfile(repo["path"])]

    if not repos_with_justfiles:
        typer.echo("No repositories with justfiles found.")
        typer.echo("\nClone repositories using: dbx clone -g <group>")
        return

    # Group repos by their group
    repos_by_group: dict[str, list[dict]] = {}
    for repo in repos_with_justfiles:
        group = repo["group"]
        if group not in repos_by_group:
            repos_by_group[group] = []
        repos_by_group[group].append(repo)

    typer.echo(f"{typer.style('Repositories with justfiles:', bold=True)}\n")

    for group_name in sorted(repos_by_group.keys()):
        typer.echo(f"  {typer.style(group_name, fg=typer.colors.CYAN)}:")
        for repo in sorted(repos_by_group[group_name], key=lambda r: r["name"]):
            typer.echo(f"    • {repo['name']}")

    total = len(repos_with_justfiles)
    typer.echo(f"\n{total} repositor{'y' if total == 1 else 'ies'} with justfiles")
    typer.echo("\nRun 'dbx just <repo_name>' to see available just commands")


def _run_just_in_repo(ctx: typer.Context, repo_name: str, just_args: list[str] | None):
    """Run just commands in a repository - shared logic."""
    # Get verbose flag from parent context
    verbose = ctx.obj.get("verbose", False) if ctx.obj else False

    # just_args will be None if not provided, or a list of strings if provided
    if just_args is None:
        just_args = []

    try:
        config = get_config()
        base_dir = get_base_dir(config)
        if verbose:
            typer.echo(f"[verbose] Using base directory: {base_dir}")
            typer.echo(f"[verbose] Config: {config}\n")
    except Exception as e:
        typer.echo(f"❌ Error: {e}", err=True)
        raise typer.Exit(1)

    # Find the repository
    repo = find_repo_by_name(repo_name, base_dir)
    if not repo:
        typer.echo(f"❌ Error: Repository '{repo_name}' not found", err=True)
        typer.echo("\nRun 'dbx list' to see available repositories")
        raise typer.Exit(1)

    repo_path = Path(repo["path"])

    # Check if justfile exists
    if not has_justfile(repo_path):
        typer.echo(f"⚠️  Warning: No justfile found in {repo_path}", err=True)
        typer.echo("This repository may not use just for task automation.", err=True)
        raise typer.Exit(1)

    # Build just command
    just_cmd = ["just"]
    if just_args:
        just_cmd.extend(just_args)
        typer.echo(f"Running 'just {' '.join(just_args)}' in {repo_path}...\n")
    else:
        typer.echo(f"Running 'just' in {repo_path}...\n")

    # Get environment variables for just run
    just_env = os.environ.copy()
    env_vars = get_test_env_vars(config, repo["group"], repo_name, base_dir)

    if env_vars:
        just_env.update(env_vars)
        if verbose:
            typer.echo("[verbose] Environment variables:")
            for key, value in env_vars.items():
                typer.echo(f"[verbose]   {key}={value}")
            typer.echo()

    if verbose:
        typer.echo(f"[verbose] Running command: {' '.join(just_cmd)}")
        typer.echo(f"[verbose] Working directory: {repo_path}\n")

    # Run just in the repository
    result = subprocess.run(
        just_cmd,
        cwd=str(repo_path),
        env=just_env,
        check=False,
    )

    if result.returncode != 0:
        raise typer.Exit(result.returncode)


@app.command(name="list")
def list_command(ctx: typer.Context):
    """List all repositories that have justfiles.

    Shows all cloned repositories that have a justfile or Justfile,
    organized by group.

    Examples::

        dbx just list    # List repos with justfiles
    """
    _list_repos_with_justfiles(ctx)


@app.callback(invoke_without_command=True)
def just_callback(
    ctx: typer.Context,
    repo_name: str = typer.Argument(None, help="Repository name to run just in"),
    just_args: list[str] = typer.Argument(
        None,
        help="Just command and arguments to run (e.g., 'lint', 'test -v'). If not provided, runs 'just' without arguments to show available commands.",
    ),
):
    """Run just commands in a cloned repository.

    Usage::

        dbx just <repo_name> [just_command] [args...]
        dbx just list                         # List repos with justfiles

    If a just command is provided after the repo name, it will be executed.
    If no just command is provided, 'just' will be run without arguments to show available commands.

    Examples::

        dbx just mongo-python-driver          # Show available just commands
        dbx just mongo-python-driver lint     # Run 'just lint'
        dbx just mongo-python-driver test -v  # Run 'just test -v'
        dbx just list                         # List repos with justfiles
    """
    # If a subcommand was invoked (like 'list'), skip the callback logic
    if ctx.invoked_subcommand is not None:
        return

    # Handle 'list' as a special case - it's a subcommand, not a repo name
    if repo_name == "list":
        _list_repos_with_justfiles(ctx)
        return

    # Require repo_name
    if not repo_name:
        typer.echo("❌ Error: Repository name is required", err=True)
        typer.echo("\nUsage: dbx just <repo_name> [just_command]")
        typer.echo("   or: dbx just list")
        raise typer.Exit(1)

    # Run just in the repository
    _run_just_in_repo(ctx, repo_name, just_args)
