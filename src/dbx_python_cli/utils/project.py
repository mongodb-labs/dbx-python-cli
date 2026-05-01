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
    default_env = config.get("project", {}).get("default_env", {})

    # Build list of library path variables to check
    library_vars = [
        "PYMONGOCRYPT_LIB",
        "DYLD_LIBRARY_PATH",
        "LD_LIBRARY_PATH",
        "CRYPT_SHARED_LIB_PATH",
    ]
    if include_dyld_fallback:
        library_vars.insert(2, "DYLD_FALLBACK_LIBRARY_PATH")

    # Set library paths for libmongocrypt (Queryable Encryption support)
    for var in library_vars:
        if var not in env and var in default_env:
            value = os.path.expanduser(default_env[var])
            # For library file paths, check if the file exists
            if var in ["PYMONGOCRYPT_LIB", "CRYPT_SHARED_LIB_PATH"]:
                if Path(value).exists():
                    env[var] = value
                    typer.echo(f"🔧 Using {var} from config: {value}")
                # Skip warning - user may not need QE
            else:
                # For library directory paths, set them even if directory doesn't exist yet
                env[var] = value
                typer.echo(f"🔧 Using {var} from config: {value}")

    # Default to project_name.py settings if not specified
    settings_module = settings if settings else ctx.name
    env["DJANGO_SETTINGS_MODULE"] = f"{ctx.name}.settings.{settings_module}"
    env["PYTHONPATH"] = str(ctx.project_path) + os.pathsep + env.get("PYTHONPATH", "")
    typer.echo(f"🔧 Using DJANGO_SETTINGS_MODULE={env['DJANGO_SETTINGS_MODULE']}")

    return env
