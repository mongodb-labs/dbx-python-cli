"""Main CLI entry point for dbx."""

import subprocess
from pathlib import Path

import typer

from dbx_python_cli.commands import (
    branch,
    clone,
    config,
    docs,
    edit,
    env,
    install,
    just,
    list,
    log,
    open,
    project,
    remove,
    status,
    switch,
    sync,
    test,
)


def get_git_hash():
    """Get the current git commit hash."""
    try:
        # Get the directory where this file is located
        cli_dir = Path(__file__).parent
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=cli_dir,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "dev"


def get_help_text():
    """Get help text with git hash."""
    git_hash = get_git_hash()
    return f"A command line tool for DBX Python development tasks. AI first. De-siloing happens here. (build: {git_hash})"


app = typer.Typer(
    help=get_help_text(),
    context_settings={"help_option_names": ["-h", "--help"]},
    no_args_is_help=True,
)

# Add subcommands (alphabetically sorted)
app.add_typer(branch.app, name="branch")
app.add_typer(clone.app, name="clone")
app.add_typer(config.app, name="config")
app.add_typer(docs.app, name="docs")
app.add_typer(edit.app, name="edit")
app.add_typer(env.app, name="env")
app.add_typer(install.app, name="install")
app.add_typer(just.app, name="just")
app.add_typer(list.app, name="list")
app.add_typer(log.app, name="log")
app.add_typer(open.app, name="open")
app.add_typer(project.app, name="project")
app.add_typer(remove.app, name="remove")
app.add_typer(status.app, name="status")
app.add_typer(switch.app, name="switch")
app.add_typer(sync.app, name="sync")
app.add_typer(test.app, name="test")


def version_callback(value: bool):
    """Show version and exit."""
    if value:
        git_hash = get_git_hash()
        typer.echo(f"dbx, version 0.1.0 ({git_hash})")
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: bool = typer.Option(
        None,
        "--version",
        callback=version_callback,
        is_eager=True,
        help="Show the version and exit.",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show more detailed output.",
    ),
    backend: str = typer.Option(
        None,
        "--backend",
        help="MongoDB backend to use: mongodb-runner, docker, or atlas-local (overrides config)",
    ),
    edition: str = typer.Option(
        None,
        "--edition",
        help="MongoDB edition to use: community or enterprise (overrides config)",
    ),
):
    """A command line tool for DBX Python development tasks."""
    # Store flags in context for subcommands to access
    ctx.obj = {
        "verbose": verbose,
        "mongodb_backend": backend,
        "mongodb_edition": edition,
    }


if __name__ == "__main__":
    app()
