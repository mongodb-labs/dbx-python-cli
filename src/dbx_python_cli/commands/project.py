"""Project management commands."""

import os
import random
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

import typer

try:
    import importlib.resources as resources
except ImportError:
    import importlib_resources as resources

from dbx_python_cli.commands.install import (
    install_frontend_if_exists,
    install_package,
)
from dbx_python_cli.utils.project import (
    get_django_python_path,
    resolve_project_path,
    setup_django_command_env,
)
from dbx_python_cli.utils.repo import (
    get_base_dir,
    get_config,
    get_projects_dir,
    get_python_version,
    is_flat_mode,
)
from dbx_python_cli.utils.venv import get_venv_info


app = typer.Typer(
    help="💚 Project management commands",
    context_settings={"help_option_names": ["-h", "--help"]},
    no_args_is_help=True,
)


@app.callback(invoke_without_command=True)
def project_callback(
    ctx: typer.Context,
):
    """Project management commands."""
    if not os.getenv("MONGODB_URI"):
        typer.echo("⚠️  Warning: MONGODB_URI is not set.", err=True)


@app.command("list")
def list_projects():
    """List all projects in the projects directory."""
    config = get_config()
    base_dir = get_base_dir(config)
    projects_dir = get_projects_dir(base_dir, is_flat_mode(config))

    if not projects_dir.exists():
        typer.echo(f"Projects directory: {projects_dir}\n")
        typer.echo("No projects directory found.")
        typer.echo("\nCreate a project using: dbx project add <name>")
        raise typer.Exit(0)

    # Find all projects (directories with pyproject.toml)
    projects = []
    for item in projects_dir.iterdir():
        if item.is_dir() and (item / "manage.py").exists():
            projects.append(item.name)

    if not projects:
        typer.echo(f"Projects directory: {projects_dir}\n")
        typer.echo("No projects found.")
        typer.echo("\nCreate a project using: dbx project add <name>")
        raise typer.Exit(0)

    typer.echo(f"Projects directory: {projects_dir}\n")
    typer.echo(f"Found {len(projects)} project(s):\n")
    for project in sorted(projects):
        project_path = projects_dir / project
        has_frontend = (project_path / "frontend").exists()
        frontend_marker = " 🎨" if has_frontend else ""
        typer.echo(f"  • {project}{frontend_marker}")

    if any((projects_dir / p / "frontend").exists() for p in projects):
        typer.echo("\n🎨 = has frontend")


@app.command("install")
def install_project(
    name: str = typer.Argument(None, help="Project name (defaults to newest project)"),
    directory: Path = typer.Option(
        None,
        "--directory",
        "-d",
        help="Custom directory where the project is located (defaults to base_dir/projects/)",
    ),
    extras: str = typer.Option(
        None,
        "--extras",
        "-e",
        help="Comma-separated extras to install (e.g., 'test,dev')",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show verbose output",
    ),
):
    """
    Install a Django project's dependencies.

    If no project name is provided, uses the most recently created project.

    Examples::

        dbx project install                    # Install newest project
        dbx project install myproject          # Install specific project
        dbx project install myproject -e test  # Install with extras
    """
    # Resolve project path
    proj = resolve_project_path(name, directory)

    python_path, venv_type = get_django_python_path(proj, directory)

    typer.echo(f"📦 Installing project '{proj.name}'...")
    typer.echo(f"   Project path: {proj.project_path}")
    typer.echo(f"   Using {venv_type} venv")

    # Install the project
    result = install_package(
        proj.project_path,
        python_path,
        install_dir=None,
        extras=extras,
        groups=None,
        verbose=verbose,
    )

    if result == "failed":
        raise typer.Exit(1)
    elif result == "skipped":
        return

    typer.echo(f"\n✅ Project '{proj.name}' installed successfully!")

    # Check for frontend and install if present
    install_frontend_if_exists(proj.project_path, verbose=verbose)


# Constants for random name generation
ADJECTIVES = [
    "happy",
    "sunny",
    "clever",
    "brave",
    "calm",
    "bright",
    "swift",
    "gentle",
    "mighty",
    "noble",
    "quiet",
    "wise",
    "bold",
    "keen",
    "lively",
    "merry",
    "proud",
    "quick",
    "smart",
    "strong",
]
NOUNS = [
    "panda",
    "eagle",
    "tiger",
    "dragon",
    "phoenix",
    "falcon",
    "wolf",
    "bear",
    "lion",
    "hawk",
    "owl",
    "fox",
    "deer",
    "otter",
    "seal",
    "whale",
    "shark",
    "raven",
    "cobra",
    "lynx",
]


def generate_random_project_name():
    """Generate a random project name using adjectives and nouns."""
    adjective = random.choice(ADJECTIVES)
    noun = random.choice(NOUNS)
    return f"{adjective}_{noun}"


@app.command("add")
def add_project(
    name: str = typer.Argument(
        None, help="Project name (optional, generates random name if not provided)"
    ),
    directory: Path = typer.Option(
        None,
        "--directory",
        "-d",
        help="Custom directory to create the project in (defaults to base_dir/projects/)",
    ),
    base_dir: Path = typer.Option(
        None,
        "--base-dir",
        help="Use this as the project root directory. Only used when --directory is not specified.",
    ),
    add_frontend: bool = typer.Option(
        True,
        "--add-frontend/--no-frontend",
        "-f/-F",
        help="Add frontend (default: True)",
    ),
    add_wagtail: bool = typer.Option(
        False,
        "--wagtail/--no-wagtail",
        "-w/-W",
        help="Enable Wagtail CMS (default: False)",
    ),
    add_qe: bool = typer.Option(
        False,
        "--qe/--no-qe",
        "-q/-Q",
        help="Enable Queryable Encryption (default: False)",
    ),
    auto_install: bool = typer.Option(
        True,
        "--install/--no-install",
        help="Automatically install the project after creation (default: True)",
    ),
    python_path_override: Optional[str] = typer.Option(
        None,
        "--python-path",
        hidden=True,
        help="Override the Python executable used for django-admin (bypasses venv detection).",
    ),
    with_repos: List[str] = typer.Option(
        [],
        "--with",
        help="Install a local clone into the project venv after creation (repeatable).",
    ),
):
    """
    Create a new Django project using bundled templates.
    Frontend is added by default. Use --no-frontend to skip frontend creation.
    Use --wagtail to enable Wagtail CMS. Use --qe to enable Queryable Encryption.
    Flags can be stacked: --qe --wagtail enables a Wagtail site with QE.

    Projects are created in base_dir/projects/ by default.
    If no name is provided, a random name is generated.

    Examples::

        dbx project add                          # Create with random name (includes frontend)
        dbx project add myproject                # Create with explicit name (includes frontend)
        dbx project add myproject --no-frontend  # Create without frontend
        dbx project add myproject --wagtail      # Create with Wagtail CMS enabled
        dbx project add myproject --qe           # Create with Queryable Encryption enabled
        dbx project add myproject --qe --wagtail # Create with QE + Wagtail
        dbx project add -d ~/custom/path         # Create with random name in custom directory
        dbx project add myproject -d ~/custom/path        # Create in custom directory
        dbx project add myproject --base-dir ~/path/to/myproject  # Create directly at path
        dbx project add myproject --with medical-records           # Install a local clone
        dbx project add myproject --with django --with django-mongodb-extensions
    """
    # Normalize parameters when called programmatically (not via CLI).
    # When called directly, typer.Option/Argument defaults are OptionInfo/ArgumentInfo objects.
    if not isinstance(name, (str, type(None))):
        name = None
    if not isinstance(directory, (Path, type(None))):
        directory = None
    if not isinstance(base_dir, (Path, type(None))):
        base_dir = None
    if not isinstance(add_frontend, bool):
        add_frontend = True
    if not isinstance(add_wagtail, bool):
        add_wagtail = False
    if not isinstance(add_qe, bool):
        add_qe = False
    if not isinstance(auto_install, bool):
        auto_install = True
    if not isinstance(python_path_override, (str, type(None))):
        python_path_override = None
    if not isinstance(with_repos, list):
        with_repos = []

    # Determine project directory and name
    config = get_config()
    use_base_dir_override = False
    if directory is None:
        if base_dir is None:
            # Use base_dir/projects/name as default when using config
            if name is None:
                name = generate_random_project_name()
                typer.echo(f"🎲 Generated random project name: {name}")
            base_dir = get_base_dir(config)
            projects_dir = get_projects_dir(base_dir, is_flat_mode(config))
            projects_dir.mkdir(parents=True, exist_ok=True)
            project_path = projects_dir / name
        else:
            # When --base-dir is specified, create project in that existing directory
            use_base_dir_override = True
            project_path = base_dir.expanduser()
            # Ensure the directory exists
            project_path.mkdir(parents=True, exist_ok=True)
            # Use the provided name, or extract from path if not provided
            if name is None:
                name = project_path.name
    else:
        if name is None:
            name = generate_random_project_name()
            typer.echo(f"🎲 Generated random project name: {name}")
        project_path = directory / name

    # Use project name as default settings module
    settings_path = f"settings.{name}"

    # Only check if project exists when NOT using --base-dir override
    if not use_base_dir_override and project_path.exists():
        typer.echo(f"❌ Project '{name}' already exists at {project_path}", err=True)
        raise typer.Exit(code=1)

    # When using --base-dir, check if manage.py already exists
    if use_base_dir_override and (project_path / "manage.py").exists():
        typer.echo(
            f"❌ Project already exists at {project_path} (manage.py found)", err=True
        )
        raise typer.Exit(code=1)

    # Check for virtual environment before running django-admin
    # For project creation, check parent directories only (project doesn't exist yet)
    # Check in order: projects group-level → base-level → activated venv
    if python_path_override is not None:
        # Caller already determined the venv (e.g. from `dbx test django`); use it directly.
        python_path = python_path_override
    else:
        config_python_version = get_python_version(config)
        need_new_venv = False
        try:
            if directory is None and not use_base_dir_override:
                # Using config-based base_dir/projects/name
                # Check: projects_dir/.venv → django group/.venv → base_dir/.venv → activated
                django_group_path = base_dir / "django"
                fallback_paths = (
                    [django_group_path] if django_group_path.exists() else None
                )
                python_path, venv_type = get_venv_info(
                    None,
                    projects_dir,
                    base_path=base_dir,
                    fallback_paths=fallback_paths,
                )
            else:
                # Using custom --directory or --base-dir override
                # Check: activated venv only
                python_path, venv_type = get_venv_info(None, None, base_path=None)

            # If config pins a Python version, reject found venvs that don't match
            if config_python_version and auto_install:
                found_ver = _venv_python_version(python_path)
                if found_ver and found_ver != config_python_version:
                    typer.echo(
                        f"⚠️  Found Python {found_ver} venv but config requires "
                        f"{config_python_version} — creating project-specific venv.\n"
                    )
                    need_new_venv = True

            if not need_new_venv:
                if venv_type == "group":
                    typer.echo(
                        f"✅ Using group venv: {Path(python_path).parent.parent}\n"
                    )
                elif venv_type == "base":
                    typer.echo(f"✅ Using base venv: {base_dir}/.venv\n")
                elif venv_type == "venv":
                    typer.echo(f"✅ Using activated venv: {python_path}\n")
        except typer.Exit:
            need_new_venv = True

        if need_new_venv:
            if not auto_install:
                # When --no-install is given we only need django-admin to scaffold
                # the project — no installation step runs, so a dedicated venv is
                # not required.  Fall back to the current interpreter; django-admin
                # will be available as long as Django is installed in this env.
                python_path = sys.executable
            else:
                # No suitable venv found — create one with the configured Python version.
                if directory is None and not use_base_dir_override:
                    venv_parent = projects_dir
                elif use_base_dir_override:
                    venv_parent = project_path.parent
                else:
                    venv_parent = directory
                typer.echo(
                    "⚙️  Creating virtual environment"
                    + (
                        f" (Python {config_python_version})"
                        if config_python_version
                        else ""
                    )
                    + f" at {venv_parent / '.venv'}..."
                )
                python_path = _create_venv(
                    venv_parent / ".venv",
                    python_version=config_python_version,
                )
                venv_type = "group"

    # Ensure Django is importable in the venv — install it if not.
    # This handles both freshly created venvs and existing venvs that predate
    # any project setup (e.g. a venv created by a previous failed run).
    if python_path_override is None and auto_install:
        django_check = subprocess.run(
            [python_path, "-c", "import django"],
            capture_output=True,
            check=False,
        )
        if django_check.returncode != 0:
            _bootstrap_venv(python_path)

    with resources.path(
        "dbx_python_cli.templates", "project_template"
    ) as template_path:
        # Use python -m django to ensure we use the correct venv's Django
        cmd = [
            python_path,
            "-m",
            "django",
            "startproject",
            "--template",
            str(template_path),
            "--name",
            "justfile",
            name,
        ]

        # When using --base-dir override, or when project_path.parent is base_dir
        # (flat mode), create the project dir first and run django-admin in it with
        # "." so that base_dir never ends up on sys.path (which would let the cloned
        # django/ repo shadow the installed package).
        _flat = is_flat_mode(get_config())
        if use_base_dir_override or _flat:
            project_path.mkdir(parents=True, exist_ok=True)
            cmd.append(".")
            cwd = str(project_path)
        else:
            cwd = str(project_path.parent)

        typer.echo(f"📦 Creating project: {name}")

        # Run django in a way that surfaces a clean, user-friendly error
        # instead of a full Python traceback when Django is missing or
        # misconfigured in the current environment.
        try:
            result = subprocess.run(
                cmd,
                check=False,
                capture_output=True,
                text=True,
                cwd=cwd,
            )
        except FileNotFoundError:
            typer.echo(
                f"❌ Python not found at '{python_path}'. Make sure the venv exists "
                "and Django is installed.",
                err=True,
            )
            raise typer.Exit(code=1)

        if result.returncode != 0:
            # Try to show a concise reason (e.g. "ModuleNotFoundError: No module named 'django'")
            reason = None
            if result.stderr:
                lines = [
                    line.strip() for line in result.stderr.splitlines() if line.strip()
                ]
                if lines:
                    reason = lines[-1]

            typer.echo(
                "❌ Failed to create project. "
                "This usually means Django is not installed or is misconfigured "
                "in the current Python environment.",
                err=True,
            )
            if reason:
                typer.echo(f"   Reason: {reason}", err=True)

            # Also show stdout if available for debugging
            if result.stdout:
                typer.echo(f"   Output: {result.stdout.strip()}", err=True)

            raise typer.Exit(code=result.returncode)

    # Verify the project directory was created
    if not project_path.exists():
        typer.echo(
            f"❌ Project directory was not created at {project_path}. "
            "The command may have failed silently.",
            err=True,
        )
        if result.stdout:
            typer.echo(f"   stdout: {result.stdout.strip()}", err=True)
        if result.stderr:
            typer.echo(f"   stderr: {result.stderr.strip()}", err=True)
        raise typer.Exit(code=1)

    # Add pyproject.toml after project creation
    _create_pyproject_toml(
        project_path, name, settings_path, wagtail=add_wagtail, qe=add_qe
    )

    # Enable Wagtail CMS if requested
    if add_wagtail:
        typer.echo(f"🌿 Enabling Wagtail CMS for project '{name}'...")
        try:
            _enable_wagtail(project_path, name)
        except Exception as e:
            typer.echo(
                f"⚠️  Project created successfully, but Wagtail setup failed: {e}",
                err=True,
            )

    # Enable Queryable Encryption if requested
    if add_qe:
        typer.echo(f"🔐 Enabling Queryable Encryption for project '{name}'...")
        try:
            _enable_qe(project_path, name)
        except Exception as e:
            typer.echo(
                f"⚠️  Project created successfully, but QE setup failed: {e}",
                err=True,
            )

    # Create frontend by default (unless --no-frontend is specified)
    if add_frontend:
        typer.echo(f"🎨 Adding frontend to project '{name}'...")
        try:
            # Call the internal frontend create helper
            # Pass the parent directory of project_path and the venv python so
            # the helper uses the correct Django.
            _add_frontend(name, project_path.parent, python_path=python_path)
        except Exception as e:
            typer.echo(
                f"⚠️  Project created successfully, but frontend creation failed: {e}",
                err=True,
            )

    # Automatically install the project if requested
    if auto_install:
        typer.echo(f"\n📦 Installing project '{name}'...")
        try:
            # Get the repos base directory for venv detection
            repos_config = get_config()
            repos_base_dir = get_base_dir(repos_config)

            # Get the virtual environment info, checking most specific to least specific:
            # project → projects group → django group → base
            projects_dir = get_projects_dir(repos_base_dir, is_flat_mode(repos_config))
            django_group_path = repos_base_dir / "django"
            fallback_paths = [django_group_path] if django_group_path.exists() else None
            python_path, venv_type = get_venv_info(
                project_path,
                projects_dir if projects_dir.exists() else None,
                base_path=repos_base_dir,
                fallback_paths=fallback_paths,
            )

            # Install the Python package
            result = install_package(
                project_path,
                python_path,
                install_dir=None,
                extras=None,
                groups=None,
                verbose=False,
            )

            if result == "success":
                typer.echo("✅ Python package installed successfully")
            elif result == "skipped":
                typer.echo(
                    "⚠️  Installation skipped (no pyproject.toml found)", err=True
                )
            else:
                typer.echo("⚠️  Python package installation failed", err=True)

            # Install frontend dependencies if frontend exists
            if add_frontend:
                frontend_installed = install_frontend_if_exists(
                    project_path, verbose=False
                )
                if not frontend_installed and (project_path / "frontend").exists():
                    typer.echo(
                        "⚠️  Frontend installation failed or npm not found",
                        err=True,
                    )
        except Exception as e:
            typer.echo(
                f"⚠️  Project created successfully, but installation failed: {e}",
                err=True,
            )

    if with_repos:
        try:
            _install_with_repos(with_repos, python_path)
        except Exception as e:
            typer.echo(f"⚠️  --with install failed: {e}", err=True)

    if add_qe:
        try:
            _ensure_package_installed(
                "medical_records", python_path, get_base_dir(get_config())
            )
        except Exception as e:
            typer.echo(f"⚠️  Failed to install medical-records: {e}", err=True)


def _venv_python_version(python_path: str) -> Optional[str]:
    """Return the 'major.minor' Python version for a given executable, or None on error."""
    result = subprocess.run(
        [
            python_path,
            "-c",
            "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def _install_with_repos(
    repo_names: List[str], python_path: str, verbose: bool = False
) -> None:
    """Install local clones into the project venv by name."""
    from dbx_python_cli.utils.repo import find_repo_by_name, is_flat_mode

    config = get_config()
    base_dir = get_base_dir(config)
    flat = is_flat_mode(config)
    for repo_name in repo_names:
        repo_info = find_repo_by_name(repo_name, base_dir, config)
        if not repo_info:
            clone_path = _clone_repo_from_config(
                repo_name, base_dir, config, flat, verbose
            )
            if clone_path is None:
                typer.echo(
                    f"⚠️  Clone '{repo_name}' not found locally and not in repos config — skipping.",
                    err=True,
                )
                continue
        else:
            clone_path = repo_info["path"]
        typer.echo(f"📦 Installing '{repo_name}' from local clone at {clone_path}...")
        result = install_package(
            clone_path,
            python_path,
            install_dir=None,
            extras=None,
            groups=None,
            verbose=verbose,
        )
        if result == "success":
            typer.echo(f"✅ '{repo_name}' installed")
        elif result == "failed":
            typer.echo(f"⚠️  Failed to install '{repo_name}'", err=True)


def _clone_repo_from_config(
    repo_name: str,
    base_dir: Path,
    config: dict,
    flat: bool,
    verbose: bool = False,
) -> Optional[Path]:
    """Clone a repo by name if it appears in a config group. Returns the clone path, or None."""
    from dbx_python_cli.utils.repo import get_group_dir, get_repo_groups

    groups = get_repo_groups(config)
    found_url = None
    found_group = None

    for group_name, group_config in groups.items():
        for repo_url in group_config.get("repos", []):
            if repo_url.split("/")[-1].replace(".git", "") == repo_name:
                found_url = repo_url
                found_group = group_name
                break
        if found_url:
            break

    if not found_url:
        return None

    group_dir = get_group_dir(base_dir, found_group, flat)
    repo_path = group_dir / repo_name
    group_dir.mkdir(parents=True, exist_ok=True)

    typer.echo(f"  📥 Cloning '{repo_name}' from config (group: {found_group})...")
    try:
        subprocess.run(
            ["git", "clone", found_url, str(repo_path)],
            check=True,
            capture_output=not verbose,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        typer.echo(f"❌ Failed to clone '{repo_name}': {e}", err=True)
        return None

    return repo_path


def _create_venv(venv_path: Path, python_version: Optional[str] = None) -> str:
    """Create a venv with uv and return the python executable path."""
    import platform

    cmd = ["uv", "venv", str(venv_path), "--no-python-downloads"]
    if python_version:
        cmd += ["--python", python_version]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        typer.echo("❌ Failed to create virtual environment", err=True)
        if result.stderr:
            typer.echo(result.stderr.strip(), err=True)
        raise typer.Exit(1)
    typer.echo(f"✅ Created virtual environment at {venv_path}")
    python_subpath = (
        "Scripts/python.exe" if platform.system() == "Windows" else "bin/python"
    )
    return str(venv_path / python_subpath)


def _bootstrap_venv(python_path: str) -> None:
    """Install Django into a freshly created venv so django-admin startproject can run."""
    typer.echo("📦 Installing Django into new virtual environment...")
    result = subprocess.run(
        ["uv", "pip", "install", "django", "--python", python_path],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        typer.echo("❌ Failed to install Django", err=True)
        if result.stderr:
            typer.echo(result.stderr.strip(), err=True)
        raise typer.Exit(1)
    typer.echo("✅ Django installed")


def _fix_broken_editable_installs(
    python_path: str, project_path: Path, verbose: bool = False
) -> None:
    """Reinstall any declared dependency that has a stale editable-install dist-info.

    Scoped to the project's declared dependencies so that old removed projects
    (which also leave behind dist-info entries) are never touched.

    uv considers a package satisfied if its dist-info exists, even when the source
    directory the editable install pointed to has been deleted. This leaves the package
    unimportable while uv's resolver thinks it's fine.
    """
    import json
    import re
    import tomllib

    pyproject = project_path / "pyproject.toml"
    if not pyproject.exists():
        return

    try:
        with open(pyproject, "rb") as f:
            toml_data = tomllib.load(f)
    except Exception:
        return

    raw_deps = toml_data.get("project", {}).get("dependencies", [])
    if not raw_deps:
        return

    # Build a set of normalised names (both hyphen and underscore forms) so we
    # can match dist-info directory names regardless of normalisation.
    declared: set[str] = set()
    for dep in raw_deps:
        name = re.split(r"[>=<!;\[\s]", dep, maxsplit=1)[0].strip()
        declared.add(name.lower().replace("-", "_"))
        declared.add(name.lower().replace("_", "-"))

    site_result = subprocess.run(
        [python_path, "-c", "import site; print(site.getsitepackages()[0])"],
        capture_output=True,
        text=True,
        check=False,
    )
    if site_result.returncode != 0:
        return

    site_packages = Path(site_result.stdout.strip())
    if not site_packages.exists():
        return

    for dist_info in site_packages.glob("*.dist-info"):
        pkg_raw = dist_info.stem.rsplit("-", 1)[0]
        if (
            pkg_raw.lower() not in declared
            and pkg_raw.lower().replace("_", "-") not in declared
            and pkg_raw.lower().replace("-", "_") not in declared
        ):
            continue  # not a declared dependency of this project

        direct_url = dist_info / "direct_url.json"
        if not direct_url.exists():
            continue
        try:
            data = json.loads(direct_url.read_text())
        except Exception:
            continue
        if not data.get("dir_info", {}).get("editable"):
            continue
        url = data.get("url", "")
        if not url.startswith("file://"):
            continue
        source_path = Path(url[len("file://") :])
        if source_path.exists() and (
            (source_path / "pyproject.toml").exists()
            or (source_path / "setup.py").exists()
        ):
            continue  # source is still a valid installable package

        top_level = dist_info / "top_level.txt"
        if not top_level.exists():
            continue
        modules = [m.strip() for m in top_level.read_text().splitlines() if m.strip()]
        if not modules:
            continue

        check = subprocess.run(
            [python_path, "-c", f"import {modules[0]}"],
            capture_output=True,
            cwd="/tmp",
            check=False,
        )
        if check.returncode == 0:
            continue

        pkg_name = pkg_raw.replace("_", "-")
        typer.echo(f"🔧 Reinstalling broken editable install: {pkg_name}")
        subprocess.run(
            ["uv", "pip", "install", "--reinstall", "--python", python_path, pkg_name],
            capture_output=not verbose,
            text=True,
            check=False,
        )


def _ensure_package_installed(
    import_name: str,
    python_path: str,
    base_dir,
    verbose: bool = False,
) -> None:
    """Ensure a package is installed, preferring a local clone over PyPI.

    Checks if already importable; if not, looks for a local clone at
    base_dir/<repo-name> (flat layout) or base_dir/django/<repo-name>
    (group layout), then falls back to installing from PyPI.
    """
    check = subprocess.run(
        [python_path, "-c", f"import {import_name}"],
        capture_output=True,
        cwd="/tmp",
    )
    if check.returncode == 0:
        return

    repo_name = import_name.replace("_", "-")

    if base_dir is not None:
        for clone_path in [
            Path(base_dir) / repo_name,
            Path(base_dir) / "django" / repo_name,
        ]:
            if clone_path.exists() and (
                (clone_path / "pyproject.toml").exists()
                or (clone_path / "setup.py").exists()
            ):
                typer.echo(
                    f"📦 Installing {repo_name} from local clone at {clone_path}..."
                )
                subprocess.run(
                    [
                        "uv",
                        "pip",
                        "install",
                        "--reinstall",
                        "--python",
                        python_path,
                        "-e",
                        str(clone_path),
                    ],
                    capture_output=not verbose,
                    check=False,
                )
                return

    # Use --reinstall to override any stale editable installs pointing to a
    # deleted source directory (uv skips reinstall otherwise, leaving a broken .pth).
    typer.echo(f"📦 Installing {repo_name} from PyPI...")
    result = subprocess.run(
        ["uv", "pip", "install", "--reinstall", "--python", python_path, repo_name],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        typer.echo(f"⚠️  Failed to install {repo_name} from PyPI:", err=True)
        if result.stderr:
            typer.echo(result.stderr.strip(), err=True)


def _create_pyproject_toml(
    project_path: Path,
    project_name: str,
    settings_path: str = "settings.base",
    wagtail: bool = False,
    qe: bool = False,
):
    """Create a pyproject.toml file for the Django project."""
    base_deps = [
        '"django-debug-toolbar"',
        '"django-mongodb-backend"',
        '"django-mongodb-extensions"',
        '"python-webpack-boilerplate"',
    ]
    if wagtail:
        base_deps.append('"wagtail"')
    if qe:
        base_deps.append('"pymongocrypt"')
    deps_str = ",\n    ".join(base_deps)

    pyproject_content = f"""[build-system]
requires = ["setuptools", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "{project_name}"
version = "0.1.0"
description = "A Django project built with DBX Python CLI"
authors = [
    {{name = "Your Name", email = "your.email@example.com"}},
]
dependencies = [
    {deps_str},
]

[project.optional-dependencies]
dev = [
    "django-debug-toolbar",
]
test = [
    "pytest",
    "pytest-django",
    "ruff",
]
encryption = [
    "pymongocrypt",
]
postgres = [
    "dj-database-url",
    "psycopg[binary]",
]
wagtail = [
    "wagtail",
]

[tool.pytest.ini_options]
DJANGO_SETTINGS_MODULE = "{project_name}.{settings_path}"
python_files = ["tests.py", "test_*.py", "*_tests.py"]

[tool.setuptools]
packages = ["{project_name}"]
"""

    pyproject_path = project_path / "pyproject.toml"
    try:
        pyproject_path.write_text(pyproject_content)
        typer.echo(
            f"✅ Created pyproject.toml for '{project_name}' with settings: {settings_path}"
        )
    except Exception as e:
        typer.echo(f"⚠️  Failed to create pyproject.toml: {e}", err=True)


def _enable_wagtail(project_path: Path, project_name: str) -> None:
    """Uncomment the Wagtail block in settings and append Wagtail URL patterns."""
    settings_file = project_path / project_name / "settings" / f"{project_name}.py"
    if settings_file.exists():
        content = settings_file.read_text()
        content = content.replace(
            "# from .wagtail import *  # noqa\n"
            "# INSTALLED_APPS += WAGTAIL_INSTALLED_APPS  # noqa: F405\n"
            "# MIDDLEWARE += WAGTAIL_MIDDLEWARE  # noqa: F405\n"
            "# MIGRATION_MODULES.update(WAGTAIL_MIGRATION_MODULES)  # noqa: F405",
            "from .wagtail import *  # noqa\n"
            "INSTALLED_APPS += WAGTAIL_INSTALLED_APPS  # noqa: F405\n"
            "MIDDLEWARE += WAGTAIL_MIDDLEWARE  # noqa: F405\n"
            "MIGRATION_MODULES.update(WAGTAIL_MIGRATION_MODULES)  # noqa: F405",
        )
        settings_file.write_text(content)

    urls_file = project_path / project_name / "urls.py"
    if urls_file.exists():
        wagtail_block = (
            "\n\n# Wagtail CMS\n"
            "from django.conf import settings\n"
            "from django.conf.urls.static import static\n"
            "from django.urls import include\n"
            "from wagtail import urls as wagtail_urls\n"
            f"from {project_name}.wagtail_urls import admin as wagtailadmin_urls\n"
            f"from {project_name}.wagtail_urls import documents as wagtaildocs_urls\n"
            "\n"
            "urlpatterns += [\n"
            '    path("cms/", include(wagtailadmin_urls)),\n'
            '    path("documents/", include(wagtaildocs_urls)),\n'
            '    path("", include(wagtail_urls)),\n'
            "] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)\n"
        )
        with open(urls_file, "a") as f:
            f.write(wagtail_block)


def _enable_qe(project_path: Path, project_name: str) -> None:
    """Uncomment the QE block in settings."""
    settings_file = project_path / project_name / "settings" / f"{project_name}.py"
    if settings_file.exists():
        content = settings_file.read_text()
        content = content.replace(
            "# from .qe import *  # noqa\n"
            "# INSTALLED_APPS += QE_INSTALLED_APPS  # noqa: F405",
            "from .qe import *  # noqa\n"
            "INSTALLED_APPS += QE_INSTALLED_APPS  # noqa: F405",
        )
        settings_file.write_text(content)


def _setup_wagtail_initial_data(
    python_path: str,
    proj,
    env: dict,
    verbose: bool = False,
) -> None:
    """Create Wagtail root page and default site if Wagtail is enabled and they don't exist.

    When MIGRATION_MODULES points to empty directories Django uses syncdb, which
    creates collections/tables but skips RunPython data migrations.  Wagtail's
    0001 migration normally creates the root Page and a default Site; without
    them the admin home view cannot build the 'wagtailadmin_explore' URL.
    """
    script_lines = [
        "import sys, django",
        "try:",
        "    django.setup()",
        "    from wagtail.models import Page",
        "    if not Page.objects.filter(depth=1).exists():",
        "        from django.conf import settings as _s",
        "        from django.contrib.contenttypes.models import ContentType",
        "        from wagtail.models import Locale, Site",
        "        lang = (getattr(_s, 'LANGUAGE_CODE', 'en') or 'en').split('-')[0][:2]",
        "        locale, _ = Locale.objects.get_or_create(language_code=lang)",
        "        page_ct, _ = ContentType.objects.get_or_create(app_label='wagtailcore', model='page')",
        "        root = Page.add_root(title='Root', slug='root', content_type=page_ct, locale=locale)",
        "        home = root.add_child(instance=Page(title='Home', slug='home', content_type=page_ct, locale=locale))",
        "        print('wagtail_root_created')",
        "        if not Site.objects.exists():",
        "            Site.objects.create(hostname='localhost', root_page=home, is_default_site=True)",
        "            print('wagtail_site_created')",
        "except ImportError:",
        "    pass",
        "except Exception as e:",
        "    print('wagtail_setup_error:' + str(e), file=sys.stderr)",
    ]
    result = subprocess.run(
        [python_path, "-c", "\n".join(script_lines)],
        cwd=str(proj.project_path),
        env=env,
        capture_output=True,
        text=True,
    )
    stdout = result.stdout or ""
    stderr = result.stderr or ""
    if "wagtail_root_created" in stdout:
        typer.echo("✅ Created Wagtail root page")
    if "wagtail_site_created" in stdout:
        typer.echo("✅ Created Wagtail default site")
    if "wagtail_setup_error:" in stderr:
        msg = stderr.split("wagtail_setup_error:")[-1].strip()
        typer.echo(f"⚠️  Wagtail initial data setup failed: {msg}", err=True)


def _add_frontend(
    project_name: str,
    directory: Path = Path("."),
    python_path: str = None,
):
    """
    Internal helper to create a frontend app inside an existing project.

    Copies the frontend_template/app_name/ directory directly to
    project_path/frontend/ — no Django startapp needed since the template
    contains no Django template variables.
    """
    import shutil

    project_path = directory / project_name
    name = "frontend"
    if not project_path.exists() or not project_path.is_dir():
        typer.echo(f"❌ Project '{project_name}' not found at {project_path}", err=True)
        raise typer.Exit(code=1)
    # Destination for new app
    app_path = project_path / name
    if app_path.exists():
        typer.echo(
            f"❌ App '{name}' already exists in project '{project_name}'", err=True
        )
        raise typer.Exit(code=1)
    typer.echo(f"📦 Creating app '{name}' in project '{project_name}'")

    with resources.path(
        "dbx_python_cli.templates", "frontend_template"
    ) as template_path:
        src = Path(template_path) / "app_name"
        shutil.copytree(src, app_path)


def _drop_project_databases(proj, python_path: str) -> None:
    """Drop all MongoDB databases declared in the project's Django settings."""
    import json as _json

    from dbx_python_cli.commands.mongodb import ensure_mongodb

    env = os.environ.copy()
    env["DJANGO_SETTINGS_MODULE"] = f"{proj.name}.settings.{proj.name}"
    env["PYTHONPATH"] = str(proj.project_path)

    try:
        env = ensure_mongodb(env)
    except Exception:
        pass

    script = "\n".join(
        [
            "import json, django, pymongo",
            "django.setup()",
            "from django.conf import settings",
            "dropped = []",
            "for cfg in settings.DATABASES.values():",
            "    if 'django_mongodb_backend' in cfg.get('ENGINE', '') and cfg.get('NAME'):",
            "        pymongo.MongoClient(cfg['HOST']).drop_database(cfg['NAME'])",
            "        dropped.append(cfg['NAME'])",
            "print(json.dumps(dropped))",
        ]
    )
    result = subprocess.run(
        [python_path, "-c", script],
        cwd=proj.project_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip().splitlines()
        msg = stderr[-1] if stderr else "unknown error"
        typer.echo(f"⚠️  Database drop script failed: {msg}", err=True)
        return
    try:
        dropped = _json.loads(result.stdout)
    except ValueError:
        return
    for name in dropped:
        typer.echo(f"🗑️  Dropped database '{name}'")


@app.command("remove")
def remove_project(
    name: str = typer.Argument(None, help="Project name (defaults to newest project)"),
    directory: Path = typer.Option(
        None,
        "--directory",
        "-d",
        help="Custom directory where the project is located (defaults to base_dir/projects/)",
    ),
):
    """Delete a Django project by name.

    If no project name is provided, removes the most recently created project.
    This will first attempt to uninstall the project package using pip in the
    current Python environment, then remove the project directory.

    Examples::

        dbx project remove                # Remove newest project
        dbx project remove myproject      # Remove specific project
    """
    # Resolve project path (don't require exists - we check manually for better error message)
    proj = resolve_project_path(name, directory, require_exists=False)

    if not proj.project_path.exists() or not proj.project_path.is_dir():
        typer.echo(
            f"❌ Project {proj.name} does not exist at {proj.project_path}.", err=True
        )
        return

    # Drop MongoDB databases associated with the project (non-fatal)
    try:
        python_path, _ = get_django_python_path(proj, directory)
        _drop_project_databases(proj, python_path)
    except Exception as e:
        typer.echo(f"⚠️  Could not drop databases: {e}", err=True)

    # Try to uninstall the package from the current environment before
    # removing the project directory. Failures here are non-fatal so that
    # filesystem cleanup still proceeds.
    uninstall_cmd = [sys.executable, "-m", "pip", "uninstall", "-y", proj.name]
    typer.echo(f"📦 Uninstalling project package '{proj.name}' with pip")
    try:
        result = subprocess.run(uninstall_cmd, check=False)
        if result.returncode != 0:
            typer.echo(
                f"⚠️ pip uninstall exited with code {result.returncode}. "
                "Proceeding to remove project files.",
                err=True,
            )
    except FileNotFoundError:
        typer.echo(
            "⚠️ Could not run pip to uninstall the project package. "
            "Proceeding to remove project files.",
            err=True,
        )

    shutil.rmtree(proj.project_path)
    typer.echo(f"🗑️ Removed project {proj.name}")

    # If using default projects directory, check if it's now empty and remove it
    # Skip in flat mode — projects_dir IS base_dir and must never be deleted
    _config = get_config()
    if (
        directory is None
        and proj.projects_dir is not None
        and not is_flat_mode(_config)
    ):
        # Check if projects_dir is empty (no directories with pyproject.toml)
        remaining_projects = []
        if proj.projects_dir.exists():
            for item in proj.projects_dir.iterdir():
                if item.is_dir() and (item / "manage.py").exists():
                    remaining_projects.append(item)

        # If no projects remain, remove the projects directory
        if not remaining_projects and proj.projects_dir.exists():
            # Check if directory is completely empty or only has hidden files
            all_items = list(proj.projects_dir.iterdir())
            if not all_items:
                shutil.rmtree(proj.projects_dir)
                typer.echo(f"🗑️ Removed empty projects directory: {proj.projects_dir}")


@app.command("run")
def run_project(
    ctx: typer.Context,
    name: str = typer.Argument(None, help="Project name (defaults to newest project)"),
    directory: Path = typer.Option(
        None,
        "--directory",
        "-d",
        help="Custom directory where the project is located (defaults to base_dir/projects/)",
    ),
    host: str = typer.Option(
        "127.0.0.1",
        "--host",
        help="Host to bind the Django server to",
    ),
    port: int = typer.Option(
        8000,
        "--port",
        "-p",
        help="Port to bind the Django server to",
    ),
    settings: str = typer.Option(
        None,
        "--settings",
        "-s",
        help="Settings configuration name to use (defaults to project name, e.g., 'base', 'qe')",
    ),
):
    """
    Run a Django project with manage.py runserver.

    If no project name is provided, runs the most recently created project.
    If a frontend directory exists, it will be run automatically alongside the Django server.

    Examples::

        dbx project run                      # Run newest project
        dbx project run myproject
        dbx project run myproject --settings base
        dbx project run myproject -s qe --port 8080
    """
    import signal

    verbose = ctx.obj.get("verbose", False) if ctx.obj else False

    # Resolve project path and get venv
    proj = resolve_project_path(name, directory)
    python_path, venv_type = get_django_python_path(proj, directory)

    # Always sync project dependencies before starting to ensure all declared
    # dependencies (including ones added after the project was first installed)
    # are present in the venv. uv pip install is fast and idempotent.
    pyproject_path = proj.project_path / "pyproject.toml"
    if pyproject_path.exists():
        typer.echo(f"📦 Syncing project dependencies for '{proj.name}'...")
        install_result = install_package(
            proj.project_path,
            python_path,
            install_dir=None,
            extras=None,
            groups=None,
            verbose=verbose,
        )
        if install_result == "failed":
            typer.echo(
                f"⚠️  Warning: Failed to install project '{proj.name}'. Some dependencies may be missing.",
                err=True,
            )

    # Fix any declared dependency that has a stale editable-install dist-info.
    # Scoped to this project's pyproject.toml so removed projects in the same
    # venv are never accidentally reinstalled.
    _fix_broken_editable_installs(python_path, proj.project_path, verbose)

    # Ensure django_mongodb_extensions is available: prefer a local clone over PyPI.
    _ensure_package_installed(
        "django_mongodb_extensions", python_path, proj.base_dir, verbose
    )

    # Check if frontend exists
    frontend_path = proj.project_path / "frontend"
    has_frontend = frontend_path.exists() and (frontend_path / "package.json").exists()

    # Ensure the frontend build directory exists so Django's staticfiles system
    # check (W004) doesn't fire before webpack has had a chance to create it.
    if has_frontend:
        (frontend_path / "build").mkdir(exist_ok=True)

    typer.echo(f"🚀 Running project '{proj.name}' on http://{host}:{port}")

    # Set up environment
    env = setup_django_command_env(proj, ctx, settings=settings)

    # Prepend venv bin dir to PATH so the correct manage.py / Django runtime is used
    venv_bin = str(Path(python_path).parent)
    env["PATH"] = f"{venv_bin}{os.pathsep}{env.get('PATH', '')}"

    # Run migrations before starting server
    typer.echo(f"🗄️  Running migrations for project '{proj.name}'")
    migrate_env = setup_django_command_env(
        proj, ctx, settings=settings, include_dyld_fallback=False
    )
    result = subprocess.run(
        [python_path, "-m", "django", "migrate"],
        cwd=proj.project_path,
        env=migrate_env,
        check=False,
        capture_output=not verbose,
        text=True,
    )
    if result.returncode != 0:
        typer.echo(f"❌ Migrations failed with exit code {result.returncode}", err=True)
        if verbose and result.stderr:
            typer.echo(result.stderr, err=True)
        elif not verbose and result.stderr:
            # Show the last few non-blank lines so the real error isn't hidden
            # behind a warning printed earlier in the same stderr stream.
            lines = [ln for ln in result.stderr.strip().splitlines() if ln.strip()]
            for line in lines[-3:]:
                typer.echo(f"   {line}", err=True)
        raise typer.Exit(code=result.returncode)
    typer.echo("✅ Migrations completed successfully")

    # Migrate the encrypted database if the project has one configured (e.g. QE projects)
    has_encrypted_db = subprocess.run(
        [
            python_path,
            "-c",
            "import django; django.setup(); from django.conf import settings; "
            "exit(0 if 'encrypted' in settings.DATABASES else 1)",
        ],
        cwd=proj.project_path,
        env=migrate_env,
        check=False,
        capture_output=True,
    )
    if has_encrypted_db.returncode == 0:
        typer.echo("🔐 Running migrations for encrypted database")
        enc_result = subprocess.run(
            [python_path, "-m", "django", "migrate", "--database", "encrypted"],
            cwd=proj.project_path,
            env=migrate_env,
            check=False,
            capture_output=not verbose,
            text=True,
        )
        if enc_result.returncode != 0:
            typer.echo("⚠️  Encrypted database migration failed", err=True)
            if enc_result.stderr:
                lines = [
                    ln for ln in enc_result.stderr.strip().splitlines() if ln.strip()
                ]
                for line in lines[-3:]:
                    typer.echo(f"   {line}", err=True)
        else:
            typer.echo("✅ Encrypted database migrations completed successfully")

    # Create initial Wagtail data (root page + default site) if Wagtail is installed
    _setup_wagtail_initial_data(python_path, proj, migrate_env, verbose)

    # Create superuser (non-fatal if already exists)
    su_email = os.getenv("PROJECT_EMAIL", "admin@example.com")
    typer.echo("👑 Creating Django superuser 'admin'")
    su_env = setup_django_command_env(
        proj, ctx, settings=settings, include_dyld_fallback=False
    )
    su_env["DJANGO_SUPERUSER_PASSWORD"] = "admin"
    su_result = subprocess.run(
        [
            python_path,
            "-m",
            "django",
            "createsuperuser",
            "--noinput",
            "--username=admin",
            f"--email={su_email}",
        ],
        cwd=proj.project_path,
        env=su_env,
        capture_output=not verbose,
    )
    if su_result.returncode == 0:
        typer.echo("✅ Superuser 'admin' created successfully")
    else:
        typer.echo("ℹ️  Superuser 'admin' already exists, skipping")

    if has_frontend:
        # Ensure frontend is installed
        typer.echo("📦 Checking frontend dependencies...")
        try:
            _install_npm(proj.name, directory=proj.project_path.parent)
        except Exception as e:
            typer.echo(f"⚠️  Frontend installation check failed: {e}", err=True)
            # Continue anyway - frontend might already be installed

        # Start frontend process in background
        typer.echo("🎨 Starting frontend development server...")
        frontend_proc = subprocess.Popen(
            ["npm", "run", "watch"],
            cwd=frontend_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # Handle CTRL-C to kill both processes
        def signal_handler(signum, frame):
            typer.echo("\n🛑 Stopping servers...")
            frontend_proc.terminate()
            raise KeyboardInterrupt

        signal.signal(signal.SIGINT, signal_handler)

        try:
            typer.echo("🌐 Starting Django development server...")
            subprocess.run(
                [python_path, "manage.py", "runserver", f"{host}:{port}"],
                cwd=proj.project_path,
                env=env,
                check=True,
            )
        except KeyboardInterrupt:
            typer.echo("\n✅ Servers stopped")
        finally:
            if frontend_proc.poll() is None:
                frontend_proc.terminate()
                frontend_proc.wait()
    else:
        # No frontend - just run Django
        try:
            typer.echo("🌐 Starting Django development server...")
            subprocess.run(
                [python_path, "manage.py", "runserver", f"{host}:{port}"],
                cwd=proj.project_path,
                env=env,
                check=True,
            )
        except KeyboardInterrupt:
            typer.echo("\n✅ Server stopped")


@app.command("open")
def open_browser(
    host: str = typer.Option("localhost", "--host", "-h", help="Host to open"),
    port: int = typer.Option(8000, "--port", "-p", help="Port to open"),
):
    """
    Open localhost in the browser.

    Examples::

        dbx project open                    # Opens http://localhost:8000
        dbx project open --port 3000        # Opens http://localhost:3000
        dbx project open --host 127.0.0.1   # Opens http://127.0.0.1:8000
    """
    import webbrowser

    url = f"http://{host}:{port}"
    typer.echo(f"🌐 Opening {url} in browser...")

    try:
        webbrowser.open(url)
        typer.echo(f"✅ Opened {url}")
    except Exception as e:
        typer.echo(f"❌ Failed to open browser: {e}", err=True)
        raise typer.Exit(code=1)


@app.command("manage")
def manage(
    ctx: typer.Context,
    name: str = typer.Argument(None, help="Project name (defaults to newest project)"),
    command: str = typer.Argument(None, help="Django management command to run"),
    args: list[str] = typer.Argument(None, help="Additional arguments for the command"),
    directory: Path = typer.Option(
        None,
        "--directory",
        "-d",
        help="Custom directory where the project is located (defaults to base_dir/projects/)",
    ),
    mongodb_uri: str = typer.Option(
        None, "--mongodb-uri", help="MongoDB connection URI"
    ),
    database: str = typer.Option(
        None,
        "--database",
        help="Specify the database to use",
    ),
    settings: str = typer.Option(
        None,
        "--settings",
        "-s",
        help="Settings configuration name to use (defaults to project name)",
    ),
):
    """
    Run any Django management command for a project.

    If no project name is provided, uses the most recently created project.

    Examples::

        dbx project manage shell                # Run shell on newest project
        dbx project manage myproject shell
        dbx project manage myproject createsuperuser
        dbx project manage myproject --mongodb-uri mongodb+srv://user:pwd@cluster
        dbx project manage myproject --settings base shell
        dbx project manage myproject migrate --database default
    """
    if args is None:
        args = []

    # Resolve project path and get venv
    proj = resolve_project_path(name, directory)
    python_path, venv_type = get_django_python_path(proj, directory)

    # Set up environment
    env = setup_django_command_env(
        proj, ctx, mongodb_uri=mongodb_uri, settings=settings
    )

    # Build command - use manage.py so project-specific management commands are discovered
    manage_py = proj.project_path / "manage.py"
    cmd_args = []
    if command:
        cmd_args.append(command)
        if database:
            cmd_args.append(f"--database={database}")
        cmd_args.extend(args)
        typer.echo(f"⚙️  Running: {python_path} manage.py {' '.join(cmd_args)}")
    else:
        typer.echo(f"ℹ️  Running: {python_path} manage.py")

    try:
        subprocess.run(
            [python_path, str(manage_py), *cmd_args],
            cwd=proj.project_path,
            env=env,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        typer.echo(f"❌ Command failed with exit code {e.returncode}", err=True)
        raise typer.Exit(code=e.returncode)
    except FileNotFoundError:
        typer.echo(
            f"❌ Python not found at '{python_path}'. Make sure the venv exists.",
            err=True,
        )
        raise typer.Exit(code=1)


@app.command("su")
def create_superuser(
    ctx: typer.Context,
    name: str = typer.Argument(None, help="Project name (defaults to newest project)"),
    directory: Path = typer.Option(
        None,
        "--directory",
        "-d",
        help="Custom directory where the project is located (defaults to base_dir/projects/)",
    ),
    username: str = typer.Option(
        "admin", "--username", "-u", help="Superuser username"
    ),
    password: str = typer.Option(
        "admin", "--password", "-p", help="Superuser password"
    ),
    email: str = typer.Option(
        None,
        "--email",
        "-e",
        help="Superuser email (defaults to $PROJECT_EMAIL if set)",
    ),
    mongodb_uri: str = typer.Option(
        None,
        "--mongodb-uri",
        help="Optional MongoDB connection URI. Falls back to $MONGODB_URI if not provided.",
    ),
    settings: str = typer.Option(
        None,
        "--settings",
        "-s",
        help="Settings configuration name to use (defaults to project name)",
    ),
):
    """
    Create a Django superuser with no interaction required.

    If no project name is provided, uses the most recently created project.

    Examples::

        dbx project su                          # Create superuser on newest project
        dbx project su myproject
        dbx project su myproject --settings base
        dbx project su myproject -u myuser -p mypass
        dbx project su myproject -e admin@example.com
    """
    if not email:
        email = os.getenv("PROJECT_EMAIL", "admin@example.com")

    # Resolve project path and get venv
    proj = resolve_project_path(name, directory)
    python_path, venv_type = get_django_python_path(proj, directory)

    typer.echo(f"👑 Creating Django superuser '{username}' for project '{proj.name}'")

    # Set up environment (without DYLD_FALLBACK_LIBRARY_PATH for su command)
    env = setup_django_command_env(
        proj,
        ctx,
        mongodb_uri=mongodb_uri,
        settings=settings,
        include_dyld_fallback=False,
    )
    env["DJANGO_SUPERUSER_PASSWORD"] = password

    # Use python -m django to ensure we use the correct venv's Django
    try:
        subprocess.run(
            [
                python_path,
                "-m",
                "django",
                "createsuperuser",
                "--noinput",
                f"--username={username}",
                f"--email={email}",
            ],
            cwd=proj.project_path,
            env=env,
            check=True,
        )
        typer.echo(f"✅ Superuser '{username}' created successfully")
    except subprocess.CalledProcessError as e:
        typer.echo(f"❌ Command failed with exit code {e.returncode}", err=True)
        raise typer.Exit(code=e.returncode)
    except FileNotFoundError:
        typer.echo(
            f"❌ Python not found at '{python_path}'. Make sure the venv exists.",
            err=True,
        )
        raise typer.Exit(code=1)


@app.command("migrate")
def migrate_project(
    ctx: typer.Context,
    name: str = typer.Argument(None, help="Project name (defaults to newest project)"),
    directory: Path = typer.Option(
        None,
        "--directory",
        "-d",
        help="Custom directory where the project is located (defaults to base_dir/projects/)",
    ),
    database: str = typer.Option(
        None,
        "--database",
        help="Specify the database to migrate (e.g., 'default', 'encrypted')",
    ),
    mongodb_uri: str = typer.Option(
        None,
        "--mongodb-uri",
        help="Optional MongoDB connection URI. Falls back to $MONGODB_URI if not provided.",
    ),
    settings: str = typer.Option(
        None,
        "--settings",
        "-s",
        help="Settings configuration name to use (defaults to project name)",
    ),
):
    """
    Run Django migrations on a project.

    If no project name is provided, uses the most recently created project.

    Examples::

        dbx project migrate                          # Migrate newest project
        dbx project migrate myproject
        dbx project migrate myproject --settings base
        dbx project migrate myproject --database encrypted
    """
    # Resolve project path and get venv
    proj = resolve_project_path(name, directory)
    python_path, venv_type = get_django_python_path(proj, directory)

    # Set up environment (without DYLD_FALLBACK_LIBRARY_PATH for migrate command)
    env = setup_django_command_env(
        proj,
        ctx,
        mongodb_uri=mongodb_uri,
        settings=settings,
        include_dyld_fallback=False,
    )

    # Build migrate command - use python -m django to ensure we use the correct venv's Django
    cmd = [python_path, "-m", "django", "migrate"]
    if database:
        cmd.append(f"--database={database}")
        typer.echo(f"🗄️  Running migrations for database: {database}")
    else:
        typer.echo(f"🗄️  Running migrations for project '{proj.name}'")

    try:
        subprocess.run(
            cmd,
            cwd=proj.project_path,
            env=env,
            check=True,
        )
        typer.echo("✅ Migrations completed successfully")
    except subprocess.CalledProcessError as e:
        typer.echo(f"❌ Command failed with exit code {e.returncode}", err=True)
        raise typer.Exit(code=e.returncode)
    except FileNotFoundError:
        typer.echo(
            f"❌ Python not found at '{python_path}'. Make sure the venv exists.",
            err=True,
        )
        raise typer.Exit(code=1)


@app.command("edit")
def edit_project(
    name: str = typer.Argument(None, help="Project name (defaults to newest project)"),
    directory: Path = typer.Option(
        None,
        "--directory",
        "-d",
        help="Custom directory where the project is located (defaults to base_dir/projects/)",
    ),
    settings: str = typer.Option(
        None,
        "--settings",
        "-s",
        help="Settings configuration name to edit (e.g., 'base', 'qe', or project name). Defaults to project name.",
    ),
):
    """
    Edit project settings files with your default editor.

    Opens all files in the project's settings/ directory by default. Pass
    --settings to open a single specific file instead.

    Uses the editor from the EDITOR environment variable; falls back to vim,
    nano, vi, or 'open' on macOS.

    If no project name is provided, uses the most recently created project.

    Examples::

        dbx project edit                      # Edit all settings files
        dbx project edit myproject            # Edit myproject's settings files
        dbx project edit myproject --settings base  # Edit only base settings
        dbx project edit myproject -s qe      # Edit only qe settings
        EDITOR=code dbx project edit          # Open with VS Code
    """
    # Resolve project path
    proj = resolve_project_path(name, directory)

    settings_dir = proj.project_path / proj.name / "settings"

    if settings:
        # Single file requested via --settings
        settings_file = settings_dir / f"{settings}.py"
        if not settings_file.exists():
            typer.echo(f"❌ Settings file not found: {settings_file}", err=True)
            typer.echo(f"\nAvailable settings files in {settings_dir}:")
            if settings_dir.exists():
                for f in sorted(settings_dir.glob("*.py")):
                    if f.name != "__init__.py":
                        typer.echo(f"  • {f.stem}")
            raise typer.Exit(code=1)
        files_to_edit = [settings_file]
    else:
        # Open all settings files (excluding __init__.py)
        if not settings_dir.exists():
            typer.echo(f"❌ Settings directory not found: {settings_dir}", err=True)
            raise typer.Exit(code=1)
        files_to_edit = sorted(
            f for f in settings_dir.glob("*.py") if f.name != "__init__.py"
        )
        if not files_to_edit:
            typer.echo(f"❌ No settings files found in {settings_dir}", err=True)
            raise typer.Exit(code=1)

    # Get editor from environment variable
    editor = os.environ.get("EDITOR")

    if not editor:
        # Try common editors in order of preference
        common_editors = ["vim", "nano", "vi"]
        for candidate in common_editors:
            try:
                subprocess.run(["which", candidate], check=True, capture_output=True)
                editor = candidate
                break
            except subprocess.CalledProcessError:
                continue

        # If no common editor found, try 'open' on macOS
        if not editor:
            import platform

            if platform.system() == "Darwin":
                editor = "open"
            else:
                typer.echo(
                    "❌ No editor found. Please set the EDITOR environment variable.",
                    err=True,
                )
                typer.echo("\nExample: export EDITOR=nano")
                raise typer.Exit(1)

    label = (
        files_to_edit[0].name
        if len(files_to_edit) == 1
        else f"{len(files_to_edit)} settings files"
    )
    typer.echo(f"📝 Opening {label} with {editor}...")

    try:
        result = subprocess.run([editor] + [str(f) for f in files_to_edit])

        if result.returncode == 0:
            typer.echo("✅ Settings files saved")
        else:
            typer.echo(
                f"⚠️  Editor exited with code {result.returncode}",
                err=True,
            )
            raise typer.Exit(result.returncode)
    except FileNotFoundError:
        typer.echo(
            f"❌ Editor '{editor}' not found. Please check your EDITOR environment variable.",
            err=True,
        )
        raise typer.Exit(1)
    except KeyboardInterrupt:
        typer.echo("\n⚠️  Editing cancelled")
        raise typer.Exit(130)


def _install_npm(
    project_name: str,
    frontend_dir: str = "frontend",
    directory: Path = Path("."),
    clean: bool = False,
):
    """
    Internal helper to install npm dependencies in the frontend directory.
    """
    project_path = directory / project_name
    if not project_path.exists():
        typer.echo(
            f"❌ Project '{project_name}' does not exist at {project_path}", err=True
        )
        raise typer.Exit(code=1)

    frontend_path = project_path / frontend_dir
    if not frontend_path.exists():
        typer.echo(
            f"❌ Frontend directory '{frontend_dir}' not found at {frontend_path}",
            err=True,
        )
        raise typer.Exit(code=1)

    package_json = frontend_path / "package.json"
    if not package_json.exists():
        typer.echo(f"❌ package.json not found in {frontend_path}", err=True)
        raise typer.Exit(code=1)

    if clean:
        typer.echo(f"🧹 Cleaning node_modules and package-lock.json in {frontend_path}")
        node_modules = frontend_path / "node_modules"
        package_lock = frontend_path / "package-lock.json"

        if node_modules.exists():
            shutil.rmtree(node_modules)
            typer.echo("  ✓ Removed node_modules")

        if package_lock.exists():
            package_lock.unlink()
            typer.echo("  ✓ Removed package-lock.json")

    typer.echo(f"📦 Installing npm dependencies in {frontend_path}")

    try:
        subprocess.run(["npm", "install"], cwd=frontend_path, check=True)
        typer.echo("✅ Dependencies installed successfully")
    except subprocess.CalledProcessError as e:
        typer.echo(f"❌ npm install failed with exit code {e.returncode}", err=True)
        raise typer.Exit(code=e.returncode)
    except FileNotFoundError:
        typer.echo(
            "❌ npm not found. Please ensure Node.js and npm are installed.", err=True
        )
        raise typer.Exit(code=1)
