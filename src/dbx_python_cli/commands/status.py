"""Status command for showing git status of repositories."""

import subprocess
from pathlib import Path

import typer

from dbx_python_cli.commands.repo_utils import (
    find_all_repos,
    find_repo_by_name,
    get_base_dir,
    get_config,
    get_repo_groups,
)

# Create a Typer app that will act as a single command
app = typer.Typer(
    help="🛠️ Show git status of repositories",
    no_args_is_help=True,
    invoke_without_command=True,
    context_settings={
        "allow_interspersed_args": False,
        "help_option_names": ["-h", "--help"],
    },
)


@app.callback()
def status_callback(
    ctx: typer.Context,
    repo_name: str = typer.Argument(None, help="Repository name to show status for"),
    group: str = typer.Option(
        None,
        "--group",
        "-g",
        help="Show status for all repositories in a group",
    ),
    short: bool = typer.Option(
        False,
        "--short",
        "-s",
        help="Show short-format status output",
    ),
):
    """Show git status of repositories.

    Usage::

        dbx status <repo_name>           # Show status of a single repository
        dbx status -g <group_name>       # Show status of all repos in a group

    Examples::

        dbx status django-mongodb-backend        # Show status of single repo
        dbx status -g django                     # Show status of all repos in django group
        dbx status --short django-mongodb-backend # Show short-format status
    """
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

    # Handle group option
    if group:
        groups = get_repo_groups(config)
        if group not in groups:
            typer.echo(
                f"❌ Error: Group '{group}' not found in configuration.", err=True
            )
            typer.echo(f"Available groups: {', '.join(groups.keys())}", err=True)
            raise typer.Exit(1)

        # Find all repos in the group
        all_repos_list = find_all_repos(base_dir)
        group_repos = [r for r in all_repos_list if r["group"] == group]

        if not group_repos:
            typer.echo(
                f"❌ Error: No repositories found for group '{group}'.", err=True
            )
            typer.echo(f"\nClone repositories using: dbx clone -g {group}")
            raise typer.Exit(1)

        typer.echo(
            f"Showing status for {len(group_repos)} repository(ies) in group '{group}':\n"
        )

        for repo_info in group_repos:
            _run_git_status(repo_info["path"], repo_info["name"], short, verbose)
            typer.echo("")  # Add blank line between repos

        return

    # Require repo_name if not using group
    if not repo_name:
        typer.echo("❌ Error: Repository name or group is required", err=True)
        typer.echo("\nUsage: dbx status <repo_name>")
        typer.echo("   or: dbx status -g <group>")
        raise typer.Exit(1)

    # Find the repository
    repo = find_repo_by_name(repo_name, base_dir)
    if not repo:
        typer.echo(f"❌ Error: Repository '{repo_name}' not found", err=True)
        typer.echo("\nRun 'dbx list' to see available repositories")
        raise typer.Exit(1)

    repo_path = Path(repo["path"])
    _run_git_status(repo_path, repo_name, short, verbose)


def _run_git_status(
    repo_path: Path, name: str, short: bool = False, verbose: bool = False
):
    """Run git status in a repository."""
    # Check if it's a git repository
    if not (repo_path / ".git").exists():
        typer.echo(f"⚠️  {name}: Not a git repository (skipping)", err=True)
        return

    # Build git status command
    git_cmd = ["git", "status"]
    if short:
        git_cmd.append("--short")

    separator = "─" * 60
    typer.echo(separator)
    typer.echo(f"📊 {name}:")
    typer.echo(separator)

    if verbose:
        typer.echo(f"[verbose] Running command: {' '.join(git_cmd)}")
        typer.echo(f"[verbose] Working directory: {repo_path}\n")

    # Run git status in the repository
    result = subprocess.run(
        git_cmd,
        cwd=str(repo_path),
        check=False,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        typer.echo(
            f"❌ {name}: git status failed with exit code {result.returncode}",
            err=True,
        )
        if result.stderr:
            typer.echo(f"   {result.stderr.strip()}", err=True)
    else:
        # Show output
        if result.stdout.strip():
            typer.echo(result.stdout.strip())
        else:
            typer.echo("Working tree clean")
