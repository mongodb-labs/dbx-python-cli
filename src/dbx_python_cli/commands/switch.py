"""Switch command for switching (and listing) git branches in repositories."""

import json
import subprocess
from pathlib import Path

import typer

from dbx_python_cli.utils.output import paginate_output, should_use_pager
from dbx_python_cli.utils.repo import (
    find_all_repos,
    find_repo_by_name,
    get_base_dir,
    get_config,
    get_global_groups,
    get_projects_dir,
    get_repo_groups,
    is_flat_mode,
)

# Create a Typer app that will act as a single command
app = typer.Typer(
    help="Git branch switching and listing commands",
    no_args_is_help=True,
    invoke_without_command=True,
    context_settings={
        "allow_interspersed_args": True,
        "ignore_unknown_options": True,
        "help_option_names": ["-h", "--help"],
    },
)

# git branch flags that mutate state; `-a` cannot be combined with these.
_MUTATING_BRANCH_FLAGS = {
    "-d",
    "-D",
    "--delete",
    "-m",
    "-M",
    "--move",
    "-c",
    "-C",
    "--copy",
    "-u",
    "--set-upstream-to",
    "--unset-upstream",
    "--edit-description",
}


@app.callback()
def switch_callback(
    ctx: typer.Context,
    repo_name: str = typer.Argument(None, help="Repository name to switch branches in"),
    branch_name: str = typer.Argument(None, help="Branch name to switch to"),
    git_args: list[str] = typer.Argument(
        None,
        help="With --branches, extra git branch arguments (e.g. '-r', '--merged', '-D old').",
    ),
    list_repos: bool = typer.Option(
        False,
        "--list",
        "-l",
        help="Show repository status (cloned vs available)",
    ),
    branches: bool = typer.Option(
        False,
        "--branches",
        "-b",
        help="List/manage branches (runs 'git branch') instead of switching",
    ),
    group: str = typer.Option(
        None,
        "--group",
        "-g",
        help="Switch/list branches in all repositories in a group",
    ),
    all_groups: bool = typer.Option(
        False,
        "--all",
        "-a",
        help="With --branches, run 'git branch' in all repositories across all groups",
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
    """Switch to a branch, or list branches (``--branches``), across repositories.

    Usage::

        dbx switch <repo_name> <branch_name>
        dbx switch -g <group_name> <branch_name>
        dbx switch -p <project_name> <branch_name>
        dbx switch --list
        dbx switch --branches <repo_name> [git_args...]
        dbx switch --branches -g <group> [git_args...]
        dbx switch --branches -a [git_args...]

    Examples::

        dbx switch mongo-python-driver PYTHON-5683       # Switch to branch
        dbx switch -c mongo-python-driver feature-123    # Create and switch to new branch
        dbx switch -g pymongo PYTHON-5683                # Switch all repos in group
        dbx switch --list                                # List repositories
        dbx switch --branches mongo-python-driver        # Show local branches
        dbx switch --branches -g pymongo                 # Show branches for a group
        dbx switch --branches mongo-python-driver -D old # Delete branch 'old'
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

    if git_args is None:
        git_args = []

    if branches:
        _run_branches(
            ctx,
            config,
            base_dir,
            repo_name,
            branch_name,
            git_args,
            group,
            all_groups,
            verbose,
        )
        return

    # ----- switch mode -----
    if all_groups or git_args:
        typer.echo("❌ Error: --all and extra git args require --branches", err=True)
        raise typer.Exit(1)

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

        projects_dir = get_projects_dir(base_dir, is_flat_mode(config))
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


def _run_branches(
    ctx,
    config,
    base_dir,
    repo_name,
    branch_name,
    git_args,
    group,
    all_groups,
    verbose,
):
    """Run 'git branch' across a repo, group, or all groups."""
    # Reassemble the git branch arguments from the positionals. When a group or
    # --all target is given, none of the positionals name a repo — they are all
    # git args. Otherwise the first positional is the repo.
    if group or all_groups:
        branch_args = [a for a in (repo_name, branch_name) if a] + list(git_args)
        target_repo = None
    else:
        target_repo = repo_name
        branch_args = [a for a in (branch_name,) if a] + list(git_args)

    # Show all branches under verbose, but only for plain listings — `-a` is
    # rejected by git alongside mutating operations like -d/-D/-m/-c.
    is_mutating = any(a in _MUTATING_BRANCH_FLAGS for a in branch_args)
    if verbose and not is_mutating and "-a" not in branch_args:
        branch_args.insert(0, "-a")

    # Handle all groups option
    if all_groups:
        groups = get_repo_groups(config)
        global_group_names = get_global_groups(config)
        non_global_groups = [g for g in groups.keys() if g not in global_group_names]

        if not non_global_groups:
            typer.echo("❌ Error: No groups found in configuration.", err=True)
            raise typer.Exit(1)

        all_repos = find_all_repos(base_dir, config)
        target_repos = [r for r in all_repos if r["group"] in non_global_groups]

        if not target_repos:
            typer.echo("❌ Error: No repositories found in any group.", err=True)
            typer.echo("\nClone repositories using: dbx clone -a")
            raise typer.Exit(1)

        # Organize repos by group
        repos_by_group = {}
        for repo_info in target_repos:
            group_name = repo_info["group"]
            repos_by_group.setdefault(group_name, []).append(repo_info)

        output_buffer = [
            f"Running git branch in {len(target_repos)} repository(ies) across {len(non_global_groups)} group(s):\n"
        ]

        for group_name in sorted(repos_by_group.keys()):
            group_repos = repos_by_group[group_name]
            output_buffer.append(
                f"\n{'═' * 80}\n📁 GROUP: {group_name} ({len(group_repos)} repository(ies))\n{'═' * 80}"
            )
            for repo_info in group_repos:
                output = _run_git_branch_to_string(
                    repo_info["path"], repo_info["name"], branch_args, verbose
                )
                if output:
                    output_buffer.append(output)

        use_pager = should_use_pager(ctx, command_default=False)
        paginate_output("\n".join(output_buffer), use_pager)
        return

    # Handle group option
    if group:
        groups = get_repo_groups(config)
        if group not in groups:
            typer.echo(
                f"❌ Error: Group '{group}' not found in configuration.", err=True
            )
            typer.echo(f"Available groups: {', '.join(groups.keys())}", err=True)
            raise typer.Exit(1)

        all_repos = find_all_repos(base_dir, config)
        group_repos = [r for r in all_repos if r["group"] == group]

        if not group_repos:
            typer.echo(
                f"❌ Error: No repositories found for group '{group}'.", err=True
            )
            typer.echo(f"\nClone repositories using: dbx clone -g {group}")
            raise typer.Exit(1)

        output_buffer = [
            f"Running git branch in {len(group_repos)} repository(ies) in group '{group}':\n"
        ]

        for repo_info in group_repos:
            output = _run_git_branch_to_string(
                repo_info["path"], repo_info["name"], branch_args, verbose
            )
            if output:
                output_buffer.append(output)

        use_pager = should_use_pager(ctx, command_default=False)
        paginate_output("\n".join(output_buffer), use_pager)
        return

    # Require a repo target if not using group or all_groups
    if not target_repo:
        typer.echo("❌ Error: Repository name, group, or --all is required", err=True)
        typer.echo("\nUsage: dbx switch --branches <repo_name> [git_args...]")
        typer.echo("   or: dbx switch --branches -g <group> [git_args...]")
        typer.echo("   or: dbx switch --branches -a [git_args...]")
        raise typer.Exit(1)

    repo = find_repo_by_name(target_repo, base_dir, config)
    if not repo:
        typer.echo(f"❌ Error: Repository '{target_repo}' not found", err=True)
        typer.echo("\nRun 'dbx list' to see available repositories")
        raise typer.Exit(1)

    _run_git_branch(Path(repo["path"]), target_repo, branch_args, verbose)


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


def _run_git_branch_to_string(
    repo_path: Path, name: str, git_args: list[str], verbose: bool = False
) -> str:
    """Run git branch in a repository and return output as a string."""
    # Check if it's a git repository
    if not (repo_path / ".git").exists():
        return f"⚠️  {name}: Not a git repository (skipping)\n"

    # Build git branch command with --no-pager and force color output
    git_cmd = ["git", "--no-pager", "-c", "color.branch=always", "branch"]
    separator = "─" * 60

    output_lines = [separator]
    if git_args:
        git_cmd.extend(git_args)
        output_lines.append(f"🌿 {name}: git branch {' '.join(git_args)}")
    else:
        output_lines.append(f"🌿 {name}:")
    output_lines.append(separator)

    if verbose:
        output_lines.append(f"[verbose] Running command: {' '.join(git_cmd)}")
        output_lines.append(f"[verbose] Working directory: {repo_path}\n")

    # Run git branch in the repository and capture output
    result = subprocess.run(
        git_cmd,
        cwd=str(repo_path),
        check=False,
        capture_output=True,
        text=True,
    )

    if result.returncode == 0:
        output_lines.append(result.stdout.rstrip())
    else:
        output_lines.append(
            f"❌ {name}: git branch failed with exit code {result.returncode}"
        )
        if result.stderr:
            output_lines.append(result.stderr.rstrip())

    return "\n".join(output_lines)
