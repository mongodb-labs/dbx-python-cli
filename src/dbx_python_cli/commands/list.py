"""List command for listing repositories."""

import json
import subprocess

import typer

from dbx_python_cli.utils.repo import (
    get_base_dir,
    get_config,
    get_group_dir,
    get_repo_groups,
    is_flat_mode,
    list_repos,
)

# Create a Typer app that will act as a single command
app = typer.Typer(
    help="List repositories",
    no_args_is_help=False,
    invoke_without_command=True,
    context_settings={
        "allow_interspersed_args": False,
        "help_option_names": ["-h", "--help"],
    },
)


def _repo_branch_status(repo_path):
    """Return (branch, ahead, behind) for a cloned repo using cached remote state."""
    try:
        branch = (
            subprocess.run(
                ["git", "-C", str(repo_path), "branch", "--show-current"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
            or "(detached)"
        )
    except subprocess.CalledProcessError:
        return "(unknown)", None, None

    try:
        remotes = (
            subprocess.run(
                ["git", "-C", str(repo_path), "remote"],
                capture_output=True,
                text=True,
                check=True,
            )
            .stdout.strip()
            .split()
        )
    except subprocess.CalledProcessError:
        return branch, None, None

    if "upstream" not in remotes:
        return branch, None, None

    try:
        ahead = int(
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(repo_path),
                    "rev-list",
                    "--count",
                    f"upstream/{branch}..HEAD",
                ],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
        )
        behind = int(
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(repo_path),
                    "rev-list",
                    "--count",
                    f"HEAD..upstream/{branch}",
                ],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
        )
        return branch, ahead, behind
    except subprocess.CalledProcessError:
        return branch, None, None


def _format_upstream_status(ahead, behind):
    if ahead is None:
        return typer.style("no upstream remote", dim=True)
    if ahead == 0 and behind == 0:
        return typer.style("up to date", fg=typer.colors.GREEN)
    parts = []
    if behind:
        parts.append(typer.style(f"↓{behind} behind", fg=typer.colors.RED))
    if ahead:
        parts.append(typer.style(f"↑{ahead} ahead", fg=typer.colors.YELLOW))
    return "  ".join(parts)


@app.callback()
def list_callback(
    ctx: typer.Context,
    group: list[str] = typer.Option(
        None,
        "--group",
        "-g",
        help="Filter to one or more groups (can be repeated or comma-separated)",
    ),
    branches: bool = typer.Option(
        False,
        "--branches",
        "-b",
        help="Show current branch and upstream sync status for each repo",
    ),
):
    """List all repositories (cloned and available).

    Shows a tree view of all repository groups with status indicators:
    - ✓ = cloned
    - ○ = available to clone
    - ? = cloned but not in config

    Examples::

        dbx list                        # List all repositories
        dbx list -g django              # Filter to django group
        dbx list -g django --branches   # Show branch + upstream status
    """
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

    # Parse comma-separated group names
    group_filter = set()
    for g in group or []:
        group_filter.update(name.strip() for name in g.split(",") if name.strip())

    if branches:
        flat = is_flat_mode(config)
        groups = get_repo_groups(config)
        target_groups = {
            k: v for k, v in groups.items() if not group_filter or k in group_filter
        }

        if not target_groups:
            typer.echo(f"❌ Group(s) not found: {', '.join(group_filter)}", err=True)
            raise typer.Exit(1)

        typer.echo(f"{typer.style('Base directory:', bold=True)} {base_dir}\n")

        repo_col = 28
        branch_col = 22

        for group_name, group_cfg in target_groups.items():
            group_dir = get_group_dir(base_dir, group_name, flat)
            typer.echo(typer.style(f"{group_name}/", bold=True))
            for repo_url in group_cfg.get("repos", []):
                repo_name = repo_url.split("/")[-1].replace(".git", "")
                repo_path = group_dir / repo_name
                if repo_path.exists() and (repo_path / ".git").exists():
                    icon = typer.style("✓", fg=typer.colors.GREEN)
                    branch, ahead, behind = _repo_branch_status(repo_path)
                    upstream_str = _format_upstream_status(ahead, behind)
                    name_col = f"  {icon} {repo_name}".ljust(repo_col)
                    branch_part = branch.ljust(branch_col)
                    typer.echo(f"{name_col}  {branch_part}  {upstream_str}")
                else:
                    icon = typer.style("○", fg=typer.colors.YELLOW)
                    typer.echo(f"  {icon} {typer.style(repo_name, dim=True)}")
            typer.echo()
        return

    formatted_output = list_repos(base_dir, config=config)

    if not formatted_output:
        typer.echo(f"Base directory: {base_dir}\n")
        typer.echo("No repositories found.")
        typer.echo("\nClone repositories using: dbx clone -g <group>")
        return

    typer.echo(f"{typer.style('Base directory:', bold=True)} {base_dir}\n")
    typer.echo(f"{typer.style('Repository status:', bold=True)}\n")
    typer.echo(formatted_output)
    cloned_label = typer.style("✓", fg=typer.colors.GREEN)
    available_label = typer.style("○", fg=typer.colors.YELLOW)
    unknown_label = typer.style("?", fg=typer.colors.MAGENTA)
    typer.echo(
        f"\nLegend: {cloned_label} = cloned, {available_label} = available to clone, {unknown_label} = cloned but not in config"
    )
