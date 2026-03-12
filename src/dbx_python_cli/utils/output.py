"""Output utilities for formatting and pagination."""

import shutil
import subprocess
import sys

import typer


def paginate_output(output: str, use_pager: bool = False):
    """Display output using a pager if requested and available.

    Args:
        output: The text to display
        use_pager: Whether to use a pager (from -p flag or command default)

    The function will use 'less -R' if:
    - use_pager is True
    - stdout is a terminal (not piped)
    - 'less' is available on the system

    Otherwise, it will print directly to stdout.
    """
    # Only paginate if explicitly requested and stdout is a terminal
    if use_pager and sys.stdout.isatty() and shutil.which("less"):
        subprocess.run(["less", "-R"], input=output, text=True)
    else:
        typer.echo(output)


def should_use_pager(ctx: typer.Context, command_default: bool = False) -> bool:
    """Determine if pager should be used based on context and command default.

    Args:
        ctx: Typer context containing the pager flag
        command_default: Whether this command uses pager by default

    Returns:
        True if pager should be used, False otherwise
    """
    # Check if -p flag was explicitly set
    if ctx.obj and ctx.obj.get("pager", False):
        return True

    # Otherwise use the command's default behavior
    return command_default
