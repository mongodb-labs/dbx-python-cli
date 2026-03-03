"""Branch command for running git branch in repositories."""

import subprocess
from pathlib import Path

import typer

from dbx_python_cli.commands.repo_utils import get_base_dir, get_config, get_repo_groups
from dbx_python_cli.commands.repo_utils import find_all_repos, find_repo_by_name

# Create a Typer app that will act as a single command
app = typer.Typer(
    help="🔀 Git branch commands",
    no_args_is_help=True,
    invoke_without_command=True,
    context_settings={
        "allow_interspersed_args": True,
        "ignore_unknown_options": True,
        "help_option_names": ["-h", "--help"],
    },
)


@app.callback()
def branch_callback(
    ctx: typer.Context,
    repo_name: str = typer.Argument(None, help="Repository name to run git branch in"),
    git_args: list[str] = typer.Argument(
        None,
        help="Git branch arguments to run (e.g., '-r', '-v', '--merged'). If not provided, runs 'git branch' without arguments.",
    ),
    group: str = typer.Option(
        None,
        "--group",
        "-g",
        help="Run git branch in all repositories in a group",
    ),
):
    """Run git branch in a cloned repository or group of repositories.

    Usage::

        dbx branch <repo_name> [git_args...]
        dbx branch -g <group_name> [git_args...]

    Examples::

        dbx branch mongo-python-driver                 # Show local branches
        dbx -v branch mongo-python-driver              # Show all branches (local and remote)
        dbx branch mongo-python-driver -d feature      # Delete branch 'feature'
        dbx branch mongo-python-driver -D feature      # Force delete branch 'feature'
        dbx branch -g pymongo                          # Show branches for all repos in group
        dbx -v branch -g pymongo                       # Show all branches for all repos in group
        dbx branch -g pymongo -d old-feature           # Delete 'old-feature' in all repos
    """
    # Get verbose flag from parent context
    verbose = ctx.obj.get("verbose", False) if ctx.obj else False

    # git_args will be None if not provided, or a list of strings if provided
    if git_args is None:
        git_args = []

    # Handle case where repo_name is actually a git argument (starts with -)
    # This happens when using -g option with git args like -d
    if repo_name and repo_name.startswith("-"):
        git_args.insert(0, repo_name)
        repo_name = None

    # Add -a flag when verbose mode is active to show all branches
    if verbose and "-a" not in git_args:
        git_args.insert(0, "-a")

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
        all_repos = find_all_repos(base_dir)
        group_repos = [r for r in all_repos if r["group"] == group]

        if not group_repos:
            typer.echo(
                f"❌ Error: No repositories found for group '{group}'.", err=True
            )
            typer.echo(f"\nClone repositories using: dbx clone -g {group}")
            raise typer.Exit(1)

        typer.echo(
            f"Running git branch in {len(group_repos)} repository(ies) in group '{group}':\n"
        )

        for repo_info in group_repos:
            _run_git_branch(repo_info["path"], repo_info["name"], git_args, verbose)

        return

    # Require repo_name if not using group
    if not repo_name:
        typer.echo("❌ Error: Repository name or group is required", err=True)
        typer.echo("\nUsage: dbx branch <repo_name> [git_args...]")
        typer.echo("   or: dbx branch -g <group> [git_args...]")
        raise typer.Exit(1)

    # Find the repository
    repo = find_repo_by_name(repo_name, base_dir)
    if not repo:
        typer.echo(f"❌ Error: Repository '{repo_name}' not found", err=True)
        typer.echo("\nRun 'dbx list' to see available repositories")
        raise typer.Exit(1)

    repo_path = Path(repo["path"])
    _run_git_branch(repo_path, repo_name, git_args, verbose)


def _run_git_branch(
    repo_path: Path, name: str, git_args: list[str], verbose: bool = False
):
    """Run git branch in a repository or project."""
    # Check if it's a git repository
    if not (repo_path / ".git").exists():
        typer.echo(f"⚠️  {name}: Not a git repository (skipping)", err=True)
        return

    # Build git branch command with --no-pager to avoid pager issues
    git_cmd = ["git", "--no-pager", "branch"]
    separator = "─" * 60
    typer.echo(separator)
    if git_args:
        git_cmd.extend(git_args)
        typer.echo(f"🌿 {name}: git branch {' '.join(git_args)}")
    else:
        typer.echo(f"🌿 {name}:")
    typer.echo(separator)

    if verbose:
        typer.echo(f"[verbose] Running command: {' '.join(git_cmd)}")
        typer.echo(f"[verbose] Working directory: {repo_path}\n")

    # Run git branch in the repository
    result = subprocess.run(
        git_cmd,
        cwd=str(repo_path),
        check=False,
    )

    if result.returncode != 0:
        typer.echo(
            f"❌ {name}: git branch failed with exit code {result.returncode}", err=True
        )
