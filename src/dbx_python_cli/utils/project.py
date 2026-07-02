"""Project management utilities.

This module provides helper functions for Django project management,
including project path resolution, venv detection with Django-specific
fallback, and environment setup for Django commands.

These utilities are used by `dbx project` commands.
"""

import os
from pathlib import Path
from typing import Optional

import typer

from dbx_python_cli.commands.mongodb import ensure_mongodb
from dbx_python_cli.utils.repo import (
    get_base_dir,
    get_config,
    get_projects_dir,
    is_flat_mode,
)
from dbx_python_cli.utils.venv import get_venv_info


LIBMONGOCRYPT_VARS = (
    "PYMONGOCRYPT_LIB",
    "DYLD_LIBRARY_PATH",
    "DYLD_FALLBACK_LIBRARY_PATH",
    "LD_LIBRARY_PATH",
    "CRYPT_SHARED_LIB_PATH",
)
_LIBMONGOCRYPT_FILE_VARS = ("PYMONGOCRYPT_LIB", "CRYPT_SHARED_LIB_PATH")


def apply_libmongocrypt_env(
    env: dict,
    config: dict,
    *,
    include_dyld_fallback: bool = True,
    base_dir: Optional[Path] = None,
    verbose: bool = False,
) -> dict:
    """Merge libmongocrypt env vars from [project.default_env] into env.

    Existing keys in env are never overwritten. File-style vars
    (PYMONGOCRYPT_LIB, CRYPT_SHARED_LIB_PATH) are only set if the file
    exists; directory-style vars are set as-is. If PYMONGOCRYPT_LIB is
    missing from config but a libmongocrypt clone is built at
    base_dir/libmongocrypt/cmake-build/libmongocrypt.{dylib,so}, it is
    auto-populated. CRYPT_SHARED_LIB_PATH is never auto-derived.
    """
    default_env = config.get("project", {}).get("default_env", {})
    vars_to_check = [
        v
        for v in LIBMONGOCRYPT_VARS
        if include_dyld_fallback or v != "DYLD_FALLBACK_LIBRARY_PATH"
    ]
    for var in vars_to_check:
        if var in env:
            continue
        if var in default_env:
            value = os.path.expanduser(default_env[var])
            if var in _LIBMONGOCRYPT_FILE_VARS:
                if Path(value).exists():
                    env[var] = value
                    if verbose:
                        typer.echo(f"🔧 Using {var} from config: {value}")
            else:
                env[var] = value
                if verbose:
                    typer.echo(f"🔧 Using {var} from config: {value}")
    if "PYMONGOCRYPT_LIB" not in env and base_dir is not None:
        for suffix in ("libmongocrypt.dylib", "libmongocrypt.so"):
            candidate = Path(base_dir) / "libmongocrypt" / "cmake-build" / suffix
            if candidate.exists():
                env["PYMONGOCRYPT_LIB"] = str(candidate)
                typer.echo(f"🔧 Auto-detected PYMONGOCRYPT_LIB: {candidate}")
                break
    return env


def validate_qe_env(
    config: dict,
    *,
    base_dir: Optional[Path] = None,
    fatal: bool = False,
) -> list:
    """Return list of problems with QE env vars; optionally raise typer.Exit(1)."""
    default_env = config.get("project", {}).get("default_env", {})
    problems: list = []
    for var in _LIBMONGOCRYPT_FILE_VARS:
        if var not in default_env:
            if (
                var == "PYMONGOCRYPT_LIB"
                and base_dir is not None
                and any(
                    (Path(base_dir) / "libmongocrypt" / "cmake-build" / s).exists()
                    for s in ("libmongocrypt.dylib", "libmongocrypt.so")
                )
            ):
                continue
            problems.append(f"{var} not set in [project.default_env]")
            continue
        path = Path(os.path.expanduser(default_env[var]))
        if not path.exists():
            problems.append(f"{var} points at {path} but it does not exist")
    if problems:
        for p in problems:
            typer.echo(f"⚠️  QE env: {p}", err=True)
        if fatal:
            typer.echo(
                "❌ Queryable Encryption requires PYMONGOCRYPT_LIB and CRYPT_SHARED_LIB_PATH.\n"
                "   Configure them in ~/.config/dbx-python-cli/config.toml under [project.default_env].",
                err=True,
            )
            raise typer.Exit(1)
    return problems


def _get_config_repo_names(config: dict) -> set:
    """Return repo names declared in config groups (derived from URLs, not filesystem scan)."""
    names = set()
    for group_cfg in config.get("repo", {}).get("groups", {}).values():
        for url in group_cfg.get("repos", []):
            names.add(url.rstrip("/").split("/")[-1].replace(".git", ""))
    return names


def get_newest_project(
    projects_dir: Path, exclude_names: Optional[set] = None
) -> tuple[str, Path]:
    """
    Get the newest project from the projects directory.

    Returns:
        tuple: (project_name, project_path)

    Raises:
        typer.Exit: If no projects are found
    """
    if not projects_dir.exists():
        typer.echo(f"❌ Projects directory not found at {projects_dir}", err=True)
        typer.echo("\nCreate a project using: dbx project add <name>")
        raise typer.Exit(code=1)

    exclude = exclude_names or set()
    projects = []
    for item in projects_dir.iterdir():
        if item.is_dir() and item.name not in exclude and (item / "manage.py").exists():
            projects.append(item)

    if not projects:
        typer.echo(f"❌ No projects found in {projects_dir}", err=True)
        typer.echo("\nCreate a project using: dbx project add <name>")
        raise typer.Exit(code=1)

    # Sort by modification time (newest first)
    projects.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    project_path = projects[0]
    project_name = project_path.name

    return project_name, project_path


class ProjectContext:
    """Container for resolved project information."""

    def __init__(
        self,
        name: str,
        project_path: Path,
        base_dir: Optional[Path],
        projects_dir: Optional[Path],
    ):
        self.name = name
        self.project_path = project_path
        self.base_dir = base_dir
        self.projects_dir = projects_dir


def resolve_project_path(
    name: Optional[str],
    directory: Optional[Path],
    require_exists: bool = True,
) -> ProjectContext:
    """
    Resolve project path from name and directory arguments.

    This helper consolidates the common pattern of resolving a project's location
    from CLI arguments, including the "newest project" fallback when no name is provided.

    Args:
        name: Project name (optional, will use newest project if None and directory is None)
        directory: Custom directory where the project is located (optional)
        require_exists: If True, raises typer.Exit if project doesn't exist

    Returns:
        ProjectContext with resolved name, project_path, base_dir, and projects_dir

    Raises:
        typer.Exit: If project name is required but not provided, or if project doesn't exist
    """
    base_dir = None
    projects_dir = None

    if directory is None:
        config = get_config()
        base_dir = get_base_dir(config)
        projects_dir = get_projects_dir(base_dir, is_flat_mode(config))

        # If no name provided, find the newest project (exclude tracked repos)
        if name is None:
            tracked_repos = _get_config_repo_names(config)
            name, project_path = get_newest_project(
                projects_dir, exclude_names=tracked_repos
            )
            typer.echo(f"ℹ️  No project specified, using newest: '{name}'")
        else:
            project_path = projects_dir / name
    else:
        if name is None:
            typer.echo("❌ Project name is required when using --directory", err=True)
            raise typer.Exit(code=1)
        project_path = directory / name

    if require_exists and not project_path.exists():
        typer.echo(f"❌ Project '{name}' not found at {project_path}", err=True)
        typer.echo(
            f"\n💡 Maybe you meant: dbx project manage <project_name> {name}",
            err=True,
        )
        raise typer.Exit(code=1)

    return ProjectContext(name, project_path, base_dir, projects_dir)


def get_django_python_path(
    ctx: ProjectContext,
    directory: Optional[Path],
) -> tuple[str, str]:
    """
    Get the Python path for Django commands, with Django group venv fallback.

    Checks in priority order (most specific to least specific):
    1. project-level venv  (project_path/.venv)
    2. group-level venv    (projects_dir/.venv OR directory/.venv)
    3. django group venv   (base_dir/django/.venv)
    4. base-level venv     (base_dir/.venv, only when using config path)
    5. activated / PATH venv

    Args:
        ctx: ProjectContext from resolve_project_path
        directory: The original directory argument from CLI

    Returns:
        tuple: (python_path, venv_type)

    Raises:
        typer.Exit: If no suitable venv is found
    """
    if directory is None:
        fallback_paths = None
        if ctx.base_dir is not None:
            django_group_path = ctx.base_dir / "django"
            if django_group_path.exists():
                fallback_paths = [django_group_path]

        return get_venv_info(
            ctx.project_path,
            ctx.projects_dir,
            base_path=ctx.base_dir,
            fallback_paths=fallback_paths,
        )
    else:
        return get_venv_info(ctx.project_path, ctx.project_path.parent, base_path=None)


def setup_django_command_env(
    ctx: ProjectContext,
    typer_ctx: typer.Context,
    mongodb_uri: Optional[str] = None,
    settings: Optional[str] = None,
    include_dyld_fallback: bool = True,
) -> dict:
    """
    Set up the environment for running Django commands.

    This helper consolidates the common pattern of:
    - Setting up MONGODB_URI (explicit or via ensure_mongodb)
    - Setting library paths for libmongocrypt (Queryable Encryption)
    - Setting DJANGO_SETTINGS_MODULE
    - Setting PYTHONPATH

    Args:
        ctx: ProjectContext from resolve_project_path
        typer_ctx: The typer Context for accessing CLI overrides
        mongodb_uri: Optional explicit MongoDB URI (takes precedence)
        settings: Optional settings module name (defaults to project name)
        include_dyld_fallback: Whether to include DYLD_FALLBACK_LIBRARY_PATH

    Returns:
        dict: Environment dictionary ready for subprocess calls
    """
    env = os.environ.copy()

    # Handle MongoDB URI: explicit flag takes precedence
    if mongodb_uri:
        typer.echo(f"🔗 Using MongoDB URI: {mongodb_uri}")
        env["MONGODB_URI"] = mongodb_uri
    else:
        # Get CLI overrides from context
        backend_override = (
            typer_ctx.obj.get("mongodb_backend") if typer_ctx.obj else None
        )
        edition_override = (
            typer_ctx.obj.get("mongodb_edition") if typer_ctx.obj else None
        )

        # Ensure MongoDB is available (starts mongodb-runner if needed)
        env = ensure_mongodb(env, backend_override, edition_override)

    # Check for default environment variables from config
    config = get_config()

    # Set library paths for libmongocrypt (Queryable Encryption support)
    apply_libmongocrypt_env(
        env,
        config,
        include_dyld_fallback=include_dyld_fallback,
        base_dir=ctx.base_dir,
        verbose=True,
    )

    # Default to project_name.py settings if not specified; fall back to dev/base
    # for projects that use a different convention (e.g. wagtail-mongodb-project).
    settings_module = settings if settings else ctx.name
    if not (
        ctx.project_path / ctx.name / "settings" / f"{settings_module}.py"
    ).exists():
        for fallback in ("dev", "base"):
            if (ctx.project_path / ctx.name / "settings" / f"{fallback}.py").exists():
                if settings:
                    typer.echo(
                        f"⚠️  Settings module '{settings}' not found, falling back to '{fallback}'",
                        err=True,
                    )
                settings_module = fallback
                break
    env["DJANGO_SETTINGS_MODULE"] = f"{ctx.name}.settings.{settings_module}"
    # Prepend the project path; avoid a trailing separator when PYTHONPATH is
    # empty, since an empty entry is interpreted as the current directory.
    existing_pythonpath = env.get("PYTHONPATH", "")
    if existing_pythonpath:
        env["PYTHONPATH"] = str(ctx.project_path) + os.pathsep + existing_pythonpath
    else:
        env["PYTHONPATH"] = str(ctx.project_path)
    typer.echo(f"🔧 Using DJANGO_SETTINGS_MODULE={env['DJANGO_SETTINGS_MODULE']}")

    return env
