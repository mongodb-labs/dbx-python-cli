"""Open command for opening repositories in a web browser."""

import json
import subprocess
import webbrowser
from pathlib import Path

import typer

from dbx_python_cli.utils.repo import get_base_dir, get_config, get_repo_groups
from dbx_python_cli.utils.repo import find_repo_by_name

# Create a Typer app that will act as a single command
app = typer.Typer(
    help="Open repositories in web browser",
    no_args_is_help=True,
    invoke_without_command=True,
    context_settings={
        "allow_interspersed_args": False,
        "help_option_names": ["-h", "--help"],
    },
)


@app.callback()
def open_callback(
    ctx: typer.Context,
    repo_name: str = typer.Argument(None, help="Repository name to open in browser"),
    group: str = typer.Option(
        None,
        "--group",
        "-g",
        help="Open all repositories in a group",
    ),
):
    """Open a repository or group of repositories in a web browser.

    Usage::

        dbx open <repo_name>
        dbx open -g <group_name>

    Examples::

        dbx open mongo-python-driver    # Open repo in browser
        dbx open -g pymongo              # Open all repos in group
    """
    # Get verbose flag from parent context
    verbose = ctx.obj.get("verbose", False) if ctx.obj else False

    try:
        config = get_config()
        base_dir = get_base_dir(config)
        if verbose:
            typer.echo(f"[verbose] Using base directory: {base_dir}")
            typer.echo(f"[verbose] Config:\n{json.dumps(config, indent=4)}\n")

        # Handle group option
        if group:
            groups = get_repo_groups(config)
            if group not in groups:
                typer.echo(
                    f"❌ Error: Group '{group}' not found in configuration.", err=True
                )
                typer.echo(f"Available groups: {', '.join(groups.keys())}", err=True)
                raise typer.Exit(1)

            # Get all repos in the group from config
            group_config = groups[group]
            repo_urls = group_config.get("repos", [])

            if not repo_urls:
                typer.echo(
                    f"❌ Error: No repositories found in group '{group}'.", err=True
                )
                raise typer.Exit(1)

            typer.echo(
                f"Opening {len(repo_urls)} repository(ies) in group '{group}':\n"
            )

            for repo_url in repo_urls:
                repo_name = _extract_repo_name_from_url(repo_url)

                # Try to find the cloned repo and get its origin URL
                # This allows us to open fork URLs if the repo was cloned with --fork
                repo = find_repo_by_name(repo_name, base_dir, config)
                if repo:
                    repo_path = Path(repo["path"])
                    origin_url = _get_git_remote_url(repo_path, "origin", verbose)
                    if origin_url:
                        # Use the actual origin URL from the cloned repo
                        browser_url = _convert_git_url_to_browser_url(origin_url)
                        if verbose:
                            typer.echo(f"[verbose] Found cloned repo at: {repo_path}")
                            typer.echo(f"[verbose] Origin URL: {origin_url}")
                    else:
                        # Fallback to config URL if no origin found
                        browser_url = _convert_git_url_to_browser_url(repo_url)
                        if verbose:
                            typer.echo(
                                "[verbose] No origin remote found, using config URL"
                            )
                else:
                    # Repo not cloned, use config URL
                    browser_url = _convert_git_url_to_browser_url(repo_url)
                    if verbose:
                        typer.echo("[verbose] Repo not cloned, using config URL")

                if verbose:
                    typer.echo(f"[verbose] Git URL: {repo_url}")
                    typer.echo(f"[verbose] Browser URL: {browser_url}")

                typer.echo(f"  🌐 Opening {repo_name}...")
                webbrowser.open(browser_url)

            typer.echo(f"\n✨ Opened {len(repo_urls)} repository(ies) in your browser")
            return

        # Require repo_name if not using group
        if not repo_name:
            typer.echo("❌ Error: Repository name or group is required", err=True)
            typer.echo("\nUsage: dbx open <repo_name>")
            typer.echo("   or: dbx open -g <group>")
            raise typer.Exit(1)

        # Find the repository
        repo = find_repo_by_name(repo_name, base_dir, config)
        if not repo:
            typer.echo(f"❌ Error: Repository '{repo_name}' not found", err=True)
            typer.echo("\nRun 'dbx list' to see available repositories")
            raise typer.Exit(1)

        repo_path = Path(repo["path"])

        # Get the origin remote URL
        origin_url = _get_git_remote_url(repo_path, "origin", verbose)

        if not origin_url:
            typer.echo(f"❌ Error: No 'origin' remote found for {repo_name}", err=True)
            raise typer.Exit(1)

        # Convert git URL to browser URL
        browser_url = _convert_git_url_to_browser_url(origin_url)

        if verbose:
            typer.echo(f"[verbose] Git URL: {origin_url}")
            typer.echo(f"[verbose] Browser URL: {browser_url}")

        typer.echo(f"🌐 Opening {repo_name} in your browser...")
        webbrowser.open(browser_url)
        typer.echo(f"✨ Opened {browser_url}")

    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


def _get_git_remote_url(
    repo_path: Path, remote_name: str = "origin", verbose: bool = False
):
    """Get the URL of a git remote.

    Args:
        repo_path: Path to the repository
        remote_name: Name of the remote (default: "origin")
        verbose: Whether to print verbose output

    Returns:
        str: The remote URL, or None if not found
    """
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_path), "remote", "get-url", remote_name],
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return None


def _convert_git_url_to_browser_url(git_url: str) -> str:
    """Convert a git URL to a browser URL.

    Args:
        git_url: Git URL (SSH or HTTPS format)

    Returns:
        str: Browser-friendly HTTPS URL

    Examples::

        git@github.com:mongodb/mongo-python-driver.git -> https://github.com/mongodb/mongo-python-driver
        https://github.com/mongodb/mongo-python-driver.git -> https://github.com/mongodb/mongo-python-driver
    """
    # Remove .git suffix if present
    if git_url.endswith(".git"):
        git_url = git_url[:-4]

    # Convert SSH format to HTTPS
    if git_url.startswith("git@"):
        # git@github.com:mongodb/mongo-python-driver -> https://github.com/mongodb/mongo-python-driver
        git_url = git_url.replace("git@", "https://")
        git_url = git_url.replace(".com:", ".com/")
        git_url = git_url.replace(".org:", ".org/")

    return git_url


def _extract_repo_name_from_url(url: str) -> str:
    """Extract repository name from a git URL.

    Args:
        url: Git URL

    Returns:
        str: Repository name
    """
    if url.endswith(".git"):
        url = url[:-4]
    return url.split("/")[-1]
