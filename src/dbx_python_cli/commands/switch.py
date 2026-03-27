"""Switch command for switching git branches in repositories."""

import json
import subprocess
from pathlib import Path

import typer

from dbx_python_cli.utils.repo import get_base_dir, get_config, get_repo_groups
from dbx_python_cli.utils.repo import find_all_repos, find_repo_by_name

# Create a Typer app that will act as a single command
app = typer.Typer(
    help="Git branch switching commands",
    no_args_is_help=True,
    invoke_without_command=True,
    context_settings={
        "allow_interspersed_args": False,
        "help_option_names": ["-h", "--help"],
    },
)


@app.callback()
def switch_callback(
    ctx: typer.Context,
    repo_name: str = typer.Argument(None, help="Repository name to switch branches in"),
    branch_name: str = typer.Argument(None, help="Branch name to switch to"),
    list_repos: bool = typer.Option(
        False,
        "--list",
        "-l",
        help="Show repository status (cloned vs available)",
    ),
    group: str = typer.Option(
        None,
        "--group",
        "-g",
        help="Switch branches in all repositories in a group",
    ),
    project: str = typer.Option(
        None,
        "--project",
        "-p",
        help="Switch branches in a specific project",
    ),
    create: bool = typer.Option(
        False,
        "--create",
        "-c",
        help="Create the branch if it doesn't exist",
    ),
):
    """Switch to a branch in a cloned repository, group of repositories, or project.

    Usage::

        dbx switch <repo_name> <branch_name>
        dbx switch -g <group_name> <branch_name>
        dbx switch -p <project_name> <branch_name>

    Examples::

        dbx switch mongo-python-driver PYTHON-5683       # Switch to branch
        dbx switch mongo-python-driver main              # Switch to main
        dbx switch -c mongo-python-driver feature-123    # Create and switch to new branch
        dbx switch -g pymongo PYTHON-5683                # Switch all repos in group
        dbx switch -p myproject feature-branch           # Switch project branch
    """
    # Get verbose flag from parent context
    verbose = ctx.obj.get("verbose", False) if ctx.obj else False

    try:
        config = get_config()
        base_dir = get_base_dir(config)
        if verbose:
            typer.echo(f"[verbose] Using base directory: {base_dir}")
            typer.echo(f"[verbose] Config:\n{json.dumps(config, indent=4)}\n")
    except Exception as e:
        typer.echo(f"❌ Error: {e}", err=True)
        raise typer.Exit(1)

    # Handle --list flag
    if list_repos:
        from dbx_python_cli.utils.repo import list_repos as list_repos_func

        output = list_repos_func(base_dir, config=config)
        if output:
            typer.echo(f"Base directory: {base_dir}\n")
            typer.echo(output)
            typer.echo(
                "\nLegend: ✓ = cloned, ○ = available to clone, ? = cloned but not in config"
            )
        else:
            typer.echo(f"Base directory: {base_dir}\n")
            typer.echo("No repositories found.")
            typer.echo("\nClone repositories using: dbx clone -g <group>")
        return

    # Handle group option
    if group:
        # When using -g, the first positional arg is the branch name
        actual_branch_name = repo_name if repo_name else branch_name
        if not actual_branch_name:
            typer.echo("❌ Error: Branch name is required", err=True)
            typer.echo("\nUsage: dbx switch -g <group> <branch_name>")
            raise typer.Exit(1)

        groups = get_repo_groups(config)
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

        typer.echo(
            f"Switching to branch '{actual_branch_name}' in {len(group_repos)} repository(ies) in group '{group}':\n"
        )

        for repo_info in group_repos:
            _run_git_switch(
                repo_info["path"],
                repo_info["name"],
                actual_branch_name,
                create,
                verbose,
            )

        return

    # Handle project option
    if project:
        # When using -p, the first positional arg is the branch name
        actual_branch_name = repo_name if repo_name else branch_name
        if not actual_branch_name:
            typer.echo("❌ Error: Branch name is required", err=True)
            typer.echo("\nUsage: dbx switch -p <project> <branch_name>")
            raise typer.Exit(1)

        projects_dir = base_dir / "projects"
        project_path = projects_dir / project

        if not project_path.exists():
            typer.echo(
                f"❌ Error: Project '{project}' not found at {project_path}", err=True
            )
            raise typer.Exit(1)

        _run_git_switch(project_path, project, actual_branch_name, create, verbose)
        return

    # Require repo_name and branch_name if not listing, not using group, and not using project
    if not repo_name or not branch_name:
        typer.echo("❌ Error: Repository name and branch name are required", err=True)
        typer.echo("\nUsage: dbx switch <repo_name> <branch_name>")
        typer.echo("   or: dbx switch -g <group> <branch_name>")
        typer.echo("   or: dbx switch -p <project> <branch_name>")
        typer.echo("   or: dbx switch --list")
        raise typer.Exit(1)

    # Find the repository
    repo = find_repo_by_name(repo_name, base_dir, config)
    if not repo:
        typer.echo(f"❌ Error: Repository '{repo_name}' not found", err=True)
        typer.echo("\nRun 'dbx switch --list' to see available repositories")
        raise typer.Exit(1)

    repo_path = Path(repo["path"])
    _run_git_switch(repo_path, repo_name, branch_name, create, verbose)


def _run_git_switch(
    repo_path: Path,
    name: str,
    branch_name: str,
    create: bool = False,
    verbose: bool = False,
):
    """Switch to a branch in a repository or project."""
    # Check if it's a git repository
    if not (repo_path / ".git").exists():
        typer.echo(f"⚠️  {name}: Not a git repository (skipping)", err=True)
        return

    # Build git switch command
    if create:
        git_cmd = ["git", "switch", "-c", branch_name]
        typer.echo(f"🔀 {name}: Creating and switching to branch '{branch_name}'")
    else:
        git_cmd = ["git", "switch", branch_name]
        typer.echo(f"🔀 {name}: Switching to branch '{branch_name}'")

    if verbose:
        typer.echo(f"[verbose] Running command: {' '.join(git_cmd)}")
        typer.echo(f"[verbose] Working directory: {repo_path}\n")

    # Run git switch in the repository
    result = subprocess.run(
        git_cmd,
        cwd=str(repo_path),
        check=False,
        capture_output=True,
        text=True,
    )

    if result.returncode == 0:
        typer.echo(f"✅ {name}: Successfully switched to '{branch_name}'")

        # Check if the branch is tracking a remote branch
        tracking_result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"],
            cwd=str(repo_path),
            check=False,
            capture_output=True,
            text=True,
        )

        if tracking_result.returncode == 0 and tracking_result.stdout.strip():
            tracking_branch = tracking_result.stdout.strip()
            typer.echo(f"   📍 Tracking: {tracking_branch}")
        elif verbose:
            typer.echo("   ℹ️  Not tracking any remote branch")
    else:
        typer.echo(f"❌ {name}: Failed to switch to '{branch_name}'", err=True)
        if result.stderr:
            # Show the error message from git
            error_msg = result.stderr.strip()
            typer.echo(f"   {error_msg}", err=True)
