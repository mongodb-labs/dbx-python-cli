"""Utilities for virtual environment detection and management."""

import platform
import subprocess
import sys

import typer


def _get_python_path():
    """
    Get the actual path to the Python executable.

    Returns:
        str: Full path to the Python executable
    """
    try:
        # Windows uses 'where', Unix uses 'which'
        cmd = "where" if platform.system() == "Windows" else "which"
        result = subprocess.run(
            [cmd, "python"],
            capture_output=True,
            text=True,
            check=True,
        )
        # 'where' on Windows can return multiple paths, take the first one
        output = result.stdout.strip()
        return output.split("\n")[0] if output else sys.executable
    except (subprocess.CalledProcessError, FileNotFoundError):
        # Fallback to sys.executable if command fails
        return sys.executable


def _is_venv(python_path):
    """
    Check if a Python executable is in a virtual environment.

    Args:
        python_path: Path to Python executable

    Returns:
        bool: True if in a venv, False otherwise
    """
    try:
        result = subprocess.run(
            [
                python_path,
                "-c",
                "import sys; print(hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix))",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip().lower() == "true"
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def get_venv_python(repo_path, group_path=None, base_path=None):
    """
    Get the Python executable from a venv.

    Checks in priority order (most specific to least specific):
    1. Repository-level venv: <repo_path>/.venv/bin/python
    2. Group-level venv: <group_path>/.venv/bin/python (if group_path provided)
    3. Base directory venv: <base_path>/.venv/bin/python (if base_path provided)
    4. System Python: "python" (fallback)

    Args:
        repo_path: Path to the repository
        group_path: Path to the group directory (optional)
        base_path: Path to the base directory (optional)

    Returns:
        str: Path to Python executable or "python" as fallback
    """
    # Windows uses Scripts/python.exe, Unix uses bin/python
    if platform.system() == "Windows":
        python_subpath = "Scripts/python.exe"
    else:
        python_subpath = "bin/python"

    # Check repository-level venv (most specific)
    if repo_path:
        repo_venv_python = repo_path / ".venv" / python_subpath
        if repo_venv_python.exists():
            return str(repo_venv_python)

    # Check group-level venv if group_path provided
    if group_path:
        group_venv_python = group_path / ".venv" / python_subpath
        if group_venv_python.exists():
            return str(group_venv_python)

    # Check base directory venv if base_path provided (least specific)
    if base_path:
        base_venv_python = base_path / ".venv" / python_subpath
        if base_venv_python.exists():
            return str(base_venv_python)

    # Fallback to system Python
    return "python"


def _find_existing_venvs(base_path):
    """
    Find all existing virtual environments in the base directory.

    Args:
        base_path: Path to the base directory

    Returns:
        list: List of tuples (venv_name, venv_path) for existing venvs
    """
    from pathlib import Path

    existing_venvs = []

    if not base_path or not Path(base_path).exists():
        return existing_venvs

    base_dir = Path(base_path)

    # Check base venv
    base_venv = base_dir / ".venv"
    if base_venv.exists():
        existing_venvs.append(("base", base_venv))

    # Check group venvs
    for item in base_dir.iterdir():
        if item.is_dir():
            group_venv = item / ".venv"
            if group_venv.exists():
                existing_venvs.append((f"{item.name} group", group_venv))

    return existing_venvs


def get_venv_info(repo_path, group_path=None, base_path=None, fallback_paths=None):
    """
    Get information about which venv will be used.

    Checks in priority order (most specific to least specific):
    1. Repository-level venv
    2. Group-level venv
    3. Fallback group venvs (e.g. django group for projects), if provided
    4. Base directory venv
    5. Activated venv

    Args:
        repo_path: Path to the repository
        group_path: Path to the primary group directory (optional)
        base_path: Path to the base directory (optional)
        fallback_paths: Additional group paths to check before base_path (optional)

    Returns:
        tuple: (python_path, venv_type) where venv_type is "base", "repo", "group", or "venv"

    Raises:
        typer.Exit: If no virtual environment is found (system Python detected)
    """
    # Windows uses Scripts/python.exe, Unix uses bin/python
    if platform.system() == "Windows":
        python_subpath = "Scripts/python.exe"
    else:
        python_subpath = "bin/python"

    # Check repository-level venv (most specific)
    if repo_path:
        repo_venv_python = repo_path / ".venv" / python_subpath
        if repo_venv_python.exists():
            return str(repo_venv_python), "repo"

    # Check group-level venv if group_path provided
    if group_path:
        group_venv_python = group_path / ".venv" / python_subpath
        if group_venv_python.exists():
            return str(group_venv_python), "group"

    # Check fallback group paths (more specific than base, e.g. django group for projects)
    if fallback_paths:
        for fpath in fallback_paths:
            fallback_python = fpath / ".venv" / python_subpath
            if fallback_python.exists():
                return str(fallback_python), "group"

    # Check base directory venv if base_path provided (least specific)
    if base_path:
        base_venv_python = base_path / ".venv" / python_subpath
        if base_venv_python.exists():
            return str(base_venv_python), "base"

    # Check sys.executable first — it is always the interpreter running the
    # current process and is the most reliable signal that we are already
    # inside a venv (e.g. pytest running in CI with an activated .venv).
    if _is_venv(sys.executable):
        return sys.executable, "venv"

    # Also check the Python found on PATH in case a different venv is activated
    # in the shell but sys.executable points elsewhere.
    python_path = _get_python_path()
    if python_path != sys.executable and _is_venv(python_path):
        return python_path, "venv"

    # Find existing venvs once — used for both auto-detection and error messages
    existing_venvs = _find_existing_venvs(base_path)

    # Auto-use if exactly one existing venv is found, so callers don't need an
    # activated shell environment when the venv location is unambiguous.
    if len(existing_venvs) == 1:
        venv_name, venv_path = existing_venvs[0]
        auto_python = venv_path / python_subpath
        if auto_python.exists():
            typer.echo(f"✅ Auto-detected venv ({venv_name}): {venv_path}")
            return str(auto_python), "venv"

    # System Python detected - error out
    typer.echo(
        "❌ Error: No virtual environment found. Installation to system Python is not allowed.",
        err=True,
    )
    typer.echo("\nTo fix this, create a virtual environment:", err=True)
    typer.echo("  dbx env init              (base dir - recommended)", err=True)

    if group_path:
        group_name = group_path.name
        typer.echo(f"  dbx env init -g {group_name}  (group level)", err=True)

    if repo_path:
        repo_name = repo_path.name
        typer.echo(f"  dbx env init {repo_name}      (repo level)", err=True)

    # Suggest existing venvs to activate (already computed above)
    if existing_venvs:
        typer.echo("\nOr activate an existing virtual environment:", err=True)
        for venv_name, venv_path in existing_venvs:
            typer.echo(f"  source {venv_path}/bin/activate  # {venv_name}", err=True)
    else:
        typer.echo(
            "\nOr activate an existing virtual environment before running dbx install.",
            err=True,
        )

    raise typer.Exit(1)
