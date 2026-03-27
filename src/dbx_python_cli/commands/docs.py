"""Docs command for documentation management."""

import json
import subprocess
import webbrowser
from pathlib import Path

import typer

from dbx_python_cli.utils.repo import (
    find_all_repos,
    find_repo_by_name,
    get_base_dir,
    get_config,
    get_global_groups,
)

DBX_DOCS_URL = "https://dbx-python-cli.readthedocs.io/"

app = typer.Typer(
    help="Documentation commands",
    no_args_is_help=True,
    invoke_without_command=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)


def has_docs(repo_path: Path) -> bool:
    """Check if a repository has documentation.

    Looks for common documentation indicators:
    - docs/ directory with conf.py (Sphinx)
    - doc/ directory with conf.py (Sphinx)
    - docs/ directory with mkdocs.yml (MkDocs)
    """
    docs_dir = repo_path / "docs"
    doc_dir = repo_path / "doc"

    # Check for Sphinx docs
    if docs_dir.exists() and (docs_dir / "conf.py").exists():
        return True
    if doc_dir.exists() and (doc_dir / "conf.py").exists():
        return True

    # Check for MkDocs
    if (repo_path / "mkdocs.yml").exists():
        return True

    return False


def get_docs_dir(repo_path: Path) -> Path | None:
    """Get the documentation directory for a repository."""
    docs_dir = repo_path / "docs"
    doc_dir = repo_path / "doc"

    if docs_dir.exists() and (docs_dir / "conf.py").exists():
        return docs_dir
    if doc_dir.exists() and (doc_dir / "conf.py").exists():
        return doc_dir

    return None


def _list_repos_with_docs(ctx: typer.Context):
    """List all repositories that have documentation - internal function."""
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

    # Get all repos and filter for those with docs, excluding global groups
    all_repos = find_all_repos(base_dir, config)
    global_group_names = set(get_global_groups(config))
    repos_with_docs = [
        repo
        for repo in all_repos
        if has_docs(repo["path"]) and repo["group"] not in global_group_names
    ]

    if not repos_with_docs:
        typer.echo("No repositories with documentation found.")
        typer.echo("\nClone repositories using: dbx clone -g <group>")
        return

    # Group repos by their group
    repos_by_group: dict[str, list[dict]] = {}
    for repo in repos_with_docs:
        group = repo["group"]
        if group not in repos_by_group:
            repos_by_group[group] = []
        repos_by_group[group].append(repo)

    typer.echo(f"{typer.style('Repositories with documentation:', bold=True)}\n")

    for group_name in sorted(repos_by_group.keys()):
        typer.echo(f"  {typer.style(group_name, fg=typer.colors.CYAN)}:")
        for repo in sorted(repos_by_group[group_name], key=lambda r: r["name"]):
            typer.echo(f"    • {repo['name']}")

    total = len(repos_with_docs)
    typer.echo(f"\n{total} repositor{'y' if total == 1 else 'ies'} with documentation")
    typer.echo("\nRun 'dbx docs build <repo_name>' to build docs locally")
    typer.echo("Run 'dbx docs open <repo_name>' to open built docs")


@app.command(name="list")
def list_command(ctx: typer.Context):
    """List all repositories that have documentation.

    Shows all cloned repositories that have a docs/ or doc/ directory
    with Sphinx configuration, organized by group.

    Examples::

        dbx docs list    # List repos with documentation
    """
    _list_repos_with_docs(ctx)


@app.command(name="open")
def open_command(
    ctx: typer.Context,
    repo_name: str = typer.Argument(
        None, help="Repository name to open docs for (omit for dbx docs)"
    ),
):
    """Open documentation in a web browser.

    Without a repo name, opens the dbx documentation on Read the Docs.
    With a repo name, opens the locally built documentation.

    Examples::

        dbx docs open                    # Open dbx docs on Read the Docs
        dbx docs open mongo-python-driver  # Open local built docs
    """
    verbose = ctx.obj.get("verbose", False) if ctx.obj else False

    # If no repo name, open dbx docs
    if not repo_name:
        typer.echo(f"📖 Opening dbx docs: {DBX_DOCS_URL}")
        webbrowser.open(DBX_DOCS_URL)
        return

    try:
        config = get_config()
        base_dir = get_base_dir(config)
        if verbose:
            typer.echo(f"[verbose] Using base directory: {base_dir}")
    except Exception as e:
        typer.echo(f"❌ Error: {e}", err=True)
        raise typer.Exit(1)

    # Find the repository
    repo = find_repo_by_name(repo_name, base_dir, config)
    if not repo:
        typer.echo(f"❌ Error: Repository '{repo_name}' not found", err=True)
        typer.echo("\nRun 'dbx list' to see available repositories")
        raise typer.Exit(1)

    repo_path = Path(repo["path"])
    docs_dir = get_docs_dir(repo_path)

    if not docs_dir:
        typer.echo(f"❌ Error: No documentation found in {repo_path}", err=True)
        typer.echo("\nRun 'dbx docs list' to see repositories with documentation")
        raise typer.Exit(1)

    # Check for built docs
    build_dir = docs_dir / "_build" / "html"
    if not build_dir.exists() or not (build_dir / "index.html").exists():
        typer.echo("❌ Error: Documentation not built yet", err=True)
        typer.echo(f"\nRun 'dbx docs build {repo_name}' first to build the docs")
        raise typer.Exit(1)

    index_path = build_dir / "index.html"
    docs_url = f"file://{index_path}"

    typer.echo(f"📖 Opening docs for {repo_name}: {docs_url}")
    webbrowser.open(docs_url)


@app.command(name="build")
def build_command(
    ctx: typer.Context,
    repo_name: str = typer.Argument(..., help="Repository name to build docs for"),
):
    """Build documentation for a repository.

    Builds Sphinx documentation for the specified repository.
    The built docs will be in <repo>/docs/_build/html/

    Examples::

        dbx docs build mongo-python-driver  # Build docs
    """
    verbose = ctx.obj.get("verbose", False) if ctx.obj else False

    try:
        config = get_config()
        base_dir = get_base_dir(config)
        if verbose:
            typer.echo(f"[verbose] Using base directory: {base_dir}")
    except Exception as e:
        typer.echo(f"❌ Error: {e}", err=True)
        raise typer.Exit(1)

    # Find the repository
    repo = find_repo_by_name(repo_name, base_dir, config)
    if not repo:
        typer.echo(f"❌ Error: Repository '{repo_name}' not found", err=True)
        typer.echo("\nRun 'dbx list' to see available repositories")
        raise typer.Exit(1)

    repo_path = Path(repo["path"])
    docs_dir = get_docs_dir(repo_path)

    if not docs_dir:
        typer.echo(f"❌ Error: No documentation found in {repo_path}", err=True)
        typer.echo("\nRun 'dbx docs list' to see repositories with documentation")
        raise typer.Exit(1)

    typer.echo(f"📖 Building documentation for {repo_name}...")
    typer.echo(f"   Docs directory: {docs_dir}\n")

    # Build using sphinx
    build_cmd = ["python", "-m", "sphinx", "-b", "html", ".", "_build/html"]

    if verbose:
        typer.echo(f"[verbose] Running command: {' '.join(build_cmd)}")
        typer.echo(f"[verbose] Working directory: {docs_dir}\n")

    result = subprocess.run(
        build_cmd,
        cwd=str(docs_dir),
        check=False,
    )

    if result.returncode != 0:
        typer.echo("\n❌ Documentation build failed", err=True)
        raise typer.Exit(result.returncode)

    build_dir = docs_dir / "_build" / "html"
    typer.echo("\n✅ Documentation built successfully!")
    typer.echo(f"   Output: {build_dir}")
    typer.echo(f"\nRun 'dbx docs open {repo_name}' to view the docs")


@app.callback(invoke_without_command=True)
def docs_callback(
    ctx: typer.Context,
):
    """Documentation commands for repositories.

    Usage::

        dbx docs list                      # List repos with docs
        dbx docs open                      # Open dbx docs
        dbx docs open <repo_name>          # Open local built docs
        dbx docs build <repo_name>         # Build docs locally

    Examples::

        dbx docs list
        dbx docs open mongo-python-driver
        dbx docs build mongo-python-driver
    """
    # If a subcommand was invoked, skip the callback logic
    if ctx.invoked_subcommand is not None:
        return

    # No subcommand - show help (handled by no_args_is_help=True)
    pass
