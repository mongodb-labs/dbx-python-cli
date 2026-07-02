"""Status command for showing git status (and log) of repositories."""

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
    help="Show git status (or log) of repositories",
    no_args_is_help=True,
    invoke_without_command=True,
    context_settings={
        "allow_interspersed_args": True,
        "ignore_unknown_options": True,
        "help_option_names": ["-h", "--help"],
    },
)


@app.callback()
def status_callback(
    ctx: typer.Context,
    repo_name: str = typer.Argument(None, help="Repository name to show status for"),
    git_args: list[str] = typer.Argument(
        None,
        help="With --log, extra git log arguments (e.g. '-n 5', '--oneline', '--graph').",
    ),
    group: str = typer.Option(
        None,
        "--group",
        "-g",
        help="Show status/log for all repositories in a group",
    ),
    short: bool = typer.Option(
        False,
        "--short",
        "-s",
        help="Show short-format status output",
    ),
    log: bool = typer.Option(
        False,
        "--log",
        "-l",
        help="Show git commit log instead of status",
    ),
    all_groups: bool = typer.Option(
        False,
        "--all",
        "-a",
        help="With --log, show logs for all cloned repositories across all groups",
    ),
    project: str = typer.Option(
        None,
        "--project",
        help="With --log, show logs for a project",
    ),
):
    """Show git status — or, with ``--log``, git commit logs — of repositories.

    Usage::

        dbx status <repo_name>                   # Status of a single repository
        dbx status -g <group_name>               # Status of all repos in a group
        dbx status --short <repo_name>           # Short-format status
        dbx status --log <repo_name> [git_args]  # Commit log of a repository
        dbx status --log -g <group> [git_args]   # Commit log for all repos in a group
        dbx status --log -a [git_args]           # Commit log for all cloned repos
        dbx status --log --project <p> [git_args] # Commit log for a project

    Examples::

        dbx status django-mongodb-backend            # Status of a single repo
        dbx status -g django                          # Status of all repos in django group
        dbx status --short django-mongodb-backend     # Short-format status
        dbx status --log mongo-python-driver -n 5     # Last 5 commits
        dbx status --log -g pymongo --oneline -n 5    # Last 5 commits, oneline, whole group
        dbx status --log -a --oneline -n 5            # Last 5 commits across all repos
    """
    # Get verbose flag from parent context
    verbose = ctx.obj.get("verbose", False) if ctx.obj else False

    if git_args is None:
        git_args = []

    # Log-only options are meaningless for plain status.
    if not log and (all_groups or project or git_args):
        typer.echo(
            "❌ Error: --all, --project and extra git args require --log", err=True
        )
        raise typer.Exit(1)

    # In log mode a leading positional that looks like a flag (e.g. -n) belongs
    # to git, not to us — shift it into git_args (mirrors group/project usage).
    if log and repo_name and repo_name.startswith("-"):
        git_args.insert(0, repo_name)
        repo_name = None

    try:
        config = get_config()
        base_dir = get_base_dir(config)
        if verbose:
            typer.echo(f"[verbose] Using base directory: {base_dir}")
            typer.echo(f"[verbose] Config:\n{json.dumps(config, indent=4)}\n")
    except Exception as e:
        typer.echo(f"❌ Error: {e}", err=True)
        raise typer.Exit(1)

    if log:
        _run_log(
            ctx,
            config,
            base_dir,
            repo_name,
            git_args,
            group,
            all_groups,
            project,
            verbose,
        )
        return

    # ----- status mode -----

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
        all_repos_list = find_all_repos(base_dir, config)
        group_repos = [r for r in all_repos_list if r["group"] == group]

        if not group_repos:
            typer.echo(
                f"❌ Error: No repositories found for group '{group}'.", err=True
            )
            typer.echo(f"\nClone repositories using: dbx clone -g {group}")
            raise typer.Exit(1)

        # If repo_name is provided, filter to only that repo within the group
        if repo_name:
            group_repos = [r for r in group_repos if r["name"] == repo_name]
            if not group_repos:
                typer.echo(
                    f"❌ Error: Repository '{repo_name}' not found in group '{group}'.",
                    err=True,
                )
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
    repo = find_repo_by_name(repo_name, base_dir, config)
    if not repo:
        typer.echo(f"❌ Error: Repository '{repo_name}' not found", err=True)
        typer.echo("\nRun 'dbx list' to see available repositories")
        raise typer.Exit(1)

    repo_path = Path(repo["path"])
    _run_git_status(repo_path, repo_name, short, verbose)


def _run_log(
    ctx,
    config,
    base_dir,
    repo_name,
    git_args,
    group,
    all_groups,
    project,
    verbose,
):
    """Show git commit logs for a repo, group, all groups, or a project."""
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

        output_parts = [
            f"Showing logs for {len(target_repos)} repository(ies) across {len(non_global_groups)} group(s):\n"
        ]

        for repo_info in target_repos:
            log_output = _get_git_log_output(
                repo_info["path"], repo_info["name"], git_args, verbose
            )
            if log_output:
                output_parts.append(log_output)

        use_pager = should_use_pager(ctx, command_default=False)
        paginate_output("\n".join(output_parts), use_pager)
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

        output_parts = [
            f"Showing logs for {len(group_repos)} repository(ies) in group '{group}':\n"
        ]

        for repo_info in group_repos:
            log_output = _get_git_log_output(
                repo_info["path"], repo_info["name"], git_args, verbose
            )
            if log_output:
                output_parts.append(log_output)

        use_pager = should_use_pager(ctx, command_default=False)
        paginate_output("\n".join(output_parts), use_pager)
        return

    # Handle project option
    if project:
        projects_dir = get_projects_dir(base_dir, is_flat_mode(config))
        project_path = projects_dir / project

        if not project_path.exists():
            typer.echo(
                f"❌ Error: Project '{project}' not found at {project_path}", err=True
            )
            raise typer.Exit(1)

        log_output = _get_git_log_output(project_path, project, git_args, verbose)
        if log_output:
            use_pager = should_use_pager(ctx, command_default=False)
            paginate_output(log_output, use_pager)
        return

    # Require repo_name if not using group and not using project
    if not repo_name:
        typer.echo("❌ Error: Repository name, group, or project is required", err=True)
        typer.echo("\nUsage: dbx status --log <repo_name> [git_args...]")
        typer.echo("   or: dbx status --log -g <group> [git_args...]")
        typer.echo("   or: dbx status --log -a [git_args...]")
        typer.echo("   or: dbx status --log --project <project> [git_args...]")
        raise typer.Exit(1)

    # Find the repository
    repo = find_repo_by_name(repo_name, base_dir, config)
    if not repo:
        typer.echo(f"❌ Error: Repository '{repo_name}' not found", err=True)
        typer.echo("\nRun 'dbx list' to see available repositories")
        raise typer.Exit(1)

    repo_path = Path(repo["path"])
    log_output = _get_git_log_output(repo_path, repo_name, git_args, verbose)
    if log_output:
        use_pager = should_use_pager(ctx, command_default=False)
        paginate_output(log_output, use_pager)


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


def _get_git_log_output(
    repo_path: Path, name: str, git_args: list[str], verbose: bool = False
) -> str:
    """Get git log output from a repository or project."""
    # Check if it's a git repository
    if not (repo_path / ".git").exists():
        return f"⚠️  {name}: Not a git repository (skipping)\n"

    # Build git log command
    git_cmd = ["git", "--no-pager", "log", "--color=always"] + git_args

    # Build header
    separator = "─" * 60
    output_parts = [separator]
    if git_args:
        output_parts.append(f"📜 {name}: git log {' '.join(git_args)}")
    else:
        output_parts.append(f"📜 {name}: git log")
    output_parts.append(separator)

    if verbose:
        output_parts.append(f"[verbose] Running command: {' '.join(git_cmd)}")
        output_parts.append(f"[verbose] Working directory: {repo_path}\n")

    # Run git log in the repository and capture output
    result = subprocess.run(
        git_cmd,
        cwd=str(repo_path),
        check=False,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        output_parts.append(f"⚠️  {name}: git log failed")
    else:
        output_parts.append(result.stdout)

    return "\n".join(output_parts)
