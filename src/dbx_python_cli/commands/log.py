"""Log command for showing git commit logs."""

import json
import subprocess
from pathlib import Path

import typer

from dbx_python_cli.utils.repo import get_base_dir, get_config, get_repo_groups
from dbx_python_cli.utils.repo import find_all_repos, find_repo_by_name

# Create a Typer app that will act as a single command
app = typer.Typer(
    help="Show git commit logs",
    no_args_is_help=True,
    invoke_without_command=True,
    context_settings={
        "allow_interspersed_args": True,
        "ignore_unknown_options": True,
        "help_option_names": ["-h", "--help"],
    },
)


@app.callback()
def log_callback(
    ctx: typer.Context,
    repo_name: str = typer.Argument(None, help="Repository name to show logs for"),
    git_args: list[str] = typer.Argument(
        None,
        help="Git log arguments to run (e.g., '-n 5', '--oneline', '--graph'). If not provided, runs 'git log -n 1'.",
    ),
    group: str = typer.Option(
        None,
        "--group",
        "-g",
        help="Show logs for all repositories in a group",
    ),
    project: str = typer.Option(
        None,
        "--project",
        help="Show logs for a project",
    ),
):
    """Show git commit logs from a repository or group of repositories.

    Usage::

        dbx log <repo_name> [git_args...]
        dbx log -g <group> [git_args...]
        dbx log --project <project> [git_args...]

    Examples::

        dbx log mongo-python-driver                    # Show last 10 commits
        dbx log mongo-python-driver -n 5               # Show last 5 commits
        dbx log mongo-python-driver --oneline          # Show in oneline format
        dbx log mongo-python-driver --graph -n 5       # Show graph with last 5 commits
        dbx log -g pymongo -n 20                       # Show last 20 commits for all repos
        dbx log -g pymongo --oneline -n 5              # Show last 5 commits in oneline format
        dbx log --project myproject -n 5               # Show last 5 commits for a project
    """
    # Get verbose flag from parent context
    verbose = ctx.obj.get("verbose", False) if ctx.obj else False

    # git_args will be None if not provided, or a list of strings if provided
    if git_args is None:
        git_args = []

    # Handle case where repo_name is actually a git argument (starts with -)
    # This happens when using -g or --project options with git args like -n
    if repo_name and repo_name.startswith("-"):
        git_args.insert(0, repo_name)
        repo_name = None

    # If no args provided, default to showing last 1 commit
    if not git_args:
        git_args = ["-n", "1"]

    try:
        config = get_config()
        base_dir = get_base_dir(config)
        if verbose:
            typer.echo(f"[verbose] Using base directory: {base_dir}")
            typer.echo(f"[verbose] Config:\n{json.dumps(config, indent=4)}\n")
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
        all_repos = find_all_repos(base_dir)
        group_repos = [r for r in all_repos if r["group"] == group]

        if not group_repos:
            typer.echo(
                f"❌ Error: No repositories found for group '{group}'.", err=True
            )
            typer.echo(f"\nClone repositories using: dbx clone -g {group}")
            raise typer.Exit(1)

        typer.echo(
            f"Showing logs for {len(group_repos)} repository(ies) in group '{group}':\n"
        )

        for repo_info in group_repos:
            _run_git_log(repo_info["path"], repo_info["name"], git_args, verbose)

        return

    # Handle project option
    if project:
        projects_dir = base_dir / "projects"
        project_path = projects_dir / project

        if not project_path.exists():
            typer.echo(
                f"❌ Error: Project '{project}' not found at {project_path}", err=True
            )
            raise typer.Exit(1)

        _run_git_log(project_path, project, git_args, verbose)
        return

    # Require repo_name if not using group and not using project
    if not repo_name:
        typer.echo("❌ Error: Repository name, group, or project is required", err=True)
        typer.echo("\nUsage: dbx log <repo_name> [git_args...]")
        typer.echo("   or: dbx log -g <group> [git_args...]")
        typer.echo("   or: dbx log --project <project> [git_args...]")
        raise typer.Exit(1)

    # Find the repository
    repo = find_repo_by_name(repo_name, base_dir, config)
    if not repo:
        typer.echo(f"❌ Error: Repository '{repo_name}' not found", err=True)
        typer.echo("\nRun 'dbx list' to see available repositories")
        raise typer.Exit(1)

    repo_path = Path(repo["path"])
    _run_git_log(repo_path, repo_name, git_args, verbose)


def _run_git_log(
    repo_path: Path, name: str, git_args: list[str], verbose: bool = False
):
    """Run git log in a repository or project."""
    # Check if it's a git repository
    if not (repo_path / ".git").exists():
        typer.echo(f"⚠️  {name}: Not a git repository (skipping)", err=True)
        return

    # Build git log command
    git_cmd = ["git", "--no-pager", "log"] + git_args

    # Display what we're doing
    separator = "─" * 60
    typer.echo(separator)
    if git_args:
        typer.echo(f"📜 {name}: git log {' '.join(git_args)}")
    else:
        typer.echo(f"📜 {name}: git log")
    typer.echo(separator)

    if verbose:
        typer.echo(f"[verbose] Running command: {' '.join(git_cmd)}")
        typer.echo(f"[verbose] Working directory: {repo_path}\n")

    # Run git log in the repository
    result = subprocess.run(
        git_cmd,
        cwd=str(repo_path),
        check=False,
    )

    if result.returncode != 0:
        typer.echo(f"⚠️  {name}: git log failed", err=True)
