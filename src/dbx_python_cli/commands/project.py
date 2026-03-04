"""Project management commands."""

import os
import random
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

import typer

try:
    import importlib.resources as resources
except ImportError:
    import importlib_resources as resources

from dbx_python_cli.commands.repo_utils import get_base_dir, get_config
from dbx_python_cli.commands.venv_utils import get_venv_info
from dbx_python_cli.commands.install import install_package, install_frontend_if_exists

# Global variable to track if we started mongodb-runner, docker, or atlas-local
_mongodb_runner_started = False
_docker_started = False
_atlas_local_started = False


def ensure_mongodb_docker(env: dict, config: dict) -> dict:
    """
    Start MongoDB using standard Docker images (community or enterprise).

    Args:
        env: Environment dictionary to update with MONGODB_URI
        config: Configuration dictionary

    Returns:
        Updated environment dictionary with MONGODB_URI set

    Raises:
        typer.Exit: If Docker is not available or MongoDB fails to start
    """
    global _docker_started

    # Get configuration
    mongodb_config = config.get("project", {}).get("mongodb", {})
    edition = mongodb_config.get("edition", "community")
    docker_config = mongodb_config.get("docker", {})

    # Determine image based on edition if not explicitly set
    if "image" in docker_config:
        image = docker_config["image"]
    else:
        if edition == "enterprise":
            image = "mongodb/mongodb-enterprise-server"
        else:
            image = "mongodb/mongodb-community-server"

    tag = docker_config.get("tag", "latest")
    container_name = docker_config.get("container_name", "dbx-mongodb")
    port = docker_config.get("port", 27017)
    replset = docker_config.get("replset")
    docker_options = docker_config.get("docker_options", [])

    full_image = f"{image}:{tag}"
    edition_label = "Enterprise" if edition == "enterprise" else "Community"
    topology_label = "Replica Set" if replset else "Standalone"

    typer.echo(
        f"⚠️  MONGODB_URI is not set. Checking for Docker MongoDB ({edition_label}, {topology_label})..."
    )

    try:
        # Check if docker is available
        docker_check = subprocess.run(
            ["which", "docker"],
            capture_output=True,
            text=True,
        )
        if docker_check.returncode != 0:
            typer.echo(
                "❌ docker is not available. Cannot use Docker MongoDB.", err=True
            )
            typer.echo(
                "💡 Install Docker: https://docs.docker.com/get-docker/", err=True
            )
            typer.echo("no db running", err=True)
            raise typer.Exit(code=1)

        # Check if container is already running
        ps_result = subprocess.run(
            [
                "docker",
                "ps",
                "--filter",
                f"name={container_name}",
                "--format",
                "{{.Names}}",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if ps_result.returncode == 0 and container_name in ps_result.stdout:
            # Container is running, check if it's healthy
            mongodb_uri = f"mongodb://localhost:{port}"
            if replset:
                mongodb_uri += f"/?replicaSet={replset}"
            env["MONGODB_URI"] = mongodb_uri
            typer.echo(f"✅ Found running Docker MongoDB container: {container_name}")
            typer.echo(f"🔗 Using MongoDB URI: {mongodb_uri}")
            return env

        # Check if container exists but is stopped
        ps_all_result = subprocess.run(
            [
                "docker",
                "ps",
                "-a",
                "--filter",
                f"name={container_name}",
                "--format",
                "{{.Names}}",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if ps_all_result.returncode == 0 and container_name in ps_all_result.stdout:
            # Container exists but is stopped, start it
            typer.echo(
                f"🚀 Starting existing Docker MongoDB container: {container_name}..."
            )
            start_result = subprocess.run(
                ["docker", "start", container_name],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if start_result.returncode != 0:
                typer.echo(
                    f"❌ Failed to start Docker MongoDB container: {start_result.stderr}",
                    err=True,
                )
                typer.echo("no db running", err=True)
                raise typer.Exit(code=1)
        else:
            # No container exists, create and start a new one
            typer.echo(
                f"🚀 Starting new Docker MongoDB container with image: {full_image}..."
            )

            # Build docker run command
            docker_cmd = [
                "docker",
                "run",
                "-d",
                "--name",
                container_name,
                "-p",
                f"{port}:27017",
            ]

            # Add any additional docker options
            docker_cmd.extend(docker_options)

            # Add the image
            docker_cmd.append(full_image)

            # Add replica set configuration if specified
            if replset:
                docker_cmd.extend(["--replSet", replset])

            run_result = subprocess.run(
                docker_cmd,
                capture_output=True,
                text=True,
                timeout=120,
            )

            if run_result.returncode != 0:
                typer.echo(
                    f"❌ Failed to start Docker MongoDB: {run_result.stderr}", err=True
                )
                typer.echo("no db running", err=True)
                raise typer.Exit(code=1)

        # Wait a moment for MongoDB to start
        import time

        typer.echo("⏳ Waiting for MongoDB to start...")
        time.sleep(5)

        # If replica set is configured, initialize it
        if replset:
            typer.echo(f"⏳ Initializing replica set '{replset}'...")
            init_result = subprocess.run(
                [
                    "docker",
                    "exec",
                    container_name,
                    "mongosh",
                    "--quiet",
                    "--eval",
                    f"rs.initiate({{_id: '{replset}', members: [{{_id: 0, host: 'localhost:27017'}}]}})",
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if init_result.returncode != 0:
                typer.echo(
                    f"⚠️  Warning: Failed to initialize replica set: {init_result.stderr}",
                    err=True,
                )
            else:
                typer.echo(f"✅ Replica set '{replset}' initialized successfully")
                # Wait a bit more for replica set to stabilize
                time.sleep(3)

        mongodb_uri = f"mongodb://localhost:{port}"
        if replset:
            mongodb_uri += f"/?replicaSet={replset}"

        env["MONGODB_URI"] = mongodb_uri
        _docker_started = True
        typer.echo(
            f"✅ Docker MongoDB {edition_label} ({topology_label}) started successfully"
        )
        typer.echo(f"🔗 Using MongoDB URI: {mongodb_uri}")
        return env

    except subprocess.TimeoutExpired:
        typer.echo("❌ Docker command timed out", err=True)
        typer.echo("no db running", err=True)
        raise typer.Exit(code=1)
    except FileNotFoundError:
        typer.echo("❌ docker command not found. Cannot use Docker MongoDB.", err=True)
        typer.echo("💡 Install Docker: https://docs.docker.com/get-docker/", err=True)
        typer.echo("no db running", err=True)
        raise typer.Exit(code=1)
    except Exception as e:
        typer.echo(f"❌ Failed to start Docker MongoDB: {e}", err=True)
        typer.echo("no db running", err=True)
        raise typer.Exit(code=1)


def ensure_mongodb_atlas_local(env: dict, config: dict) -> dict:
    """
    Start MongoDB using Atlas Local Docker image.

    Args:
        env: Environment dictionary to update with MONGODB_URI
        config: Configuration dictionary

    Returns:
        Updated environment dictionary with MONGODB_URI set

    Raises:
        typer.Exit: If Docker is not available or Atlas Local fails to start
    """
    global _atlas_local_started

    # Get Atlas Local configuration
    atlas_config = config.get("project", {}).get("mongodb", {}).get("atlas_local", {})
    image = atlas_config.get("image", "mongodb/mongodb-atlas-local")
    tag = atlas_config.get("tag", "latest")
    container_name = atlas_config.get("container_name", "dbx-atlas-local")
    port = atlas_config.get("port", 27017)
    docker_options = atlas_config.get("docker_options", [])

    full_image = f"{image}:{tag}"

    typer.echo("⚠️  MONGODB_URI is not set. Checking for Atlas Local...")

    try:
        # Check if docker is available
        docker_check = subprocess.run(
            ["which", "docker"],
            capture_output=True,
            text=True,
        )
        if docker_check.returncode != 0:
            typer.echo("❌ docker is not available. Cannot use Atlas Local.", err=True)
            typer.echo(
                "💡 Install Docker: https://docs.docker.com/get-docker/", err=True
            )
            typer.echo("no db running", err=True)
            raise typer.Exit(code=1)

        # Check if container is already running
        ps_result = subprocess.run(
            [
                "docker",
                "ps",
                "--filter",
                f"name={container_name}",
                "--format",
                "{{.Names}}",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if ps_result.returncode == 0 and container_name in ps_result.stdout:
            # Container is running, check if it's healthy
            health_result = subprocess.run(
                [
                    "docker",
                    "inspect",
                    "--format",
                    "{{.State.Health.Status}}",
                    container_name,
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )

            health_status = (
                health_result.stdout.strip()
                if health_result.returncode == 0
                else "unknown"
            )

            if health_status == "healthy":
                # Atlas Local runs as a replica set with internal hostname
                # Use directConnection=true to bypass replica set discovery
                mongodb_uri = f"mongodb://localhost:{port}/?directConnection=true"
                env["MONGODB_URI"] = mongodb_uri
                typer.echo(f"✅ Found running Atlas Local container: {container_name}")
                typer.echo(f"🔗 Using MongoDB URI: {mongodb_uri}")
                return env
            elif health_status == "starting":
                typer.echo(
                    "⏳ Atlas Local container is starting, waiting for healthy status..."
                )
                # Wait for container to become healthy (max 60 seconds)
                for _ in range(30):
                    import time

                    time.sleep(2)
                    health_result = subprocess.run(
                        [
                            "docker",
                            "inspect",
                            "--format",
                            "{{.State.Health.Status}}",
                            container_name,
                        ],
                        capture_output=True,
                        text=True,
                        timeout=10,
                    )
                    if (
                        health_result.returncode == 0
                        and health_result.stdout.strip() == "healthy"
                    ):
                        # Atlas Local runs as a replica set with internal hostname
                        # Use directConnection=true to bypass replica set discovery
                        mongodb_uri = (
                            f"mongodb://localhost:{port}/?directConnection=true"
                        )
                        env["MONGODB_URI"] = mongodb_uri
                        typer.echo("✅ Atlas Local container is now healthy")
                        typer.echo(f"🔗 Using MongoDB URI: {mongodb_uri}")
                        return env

                typer.echo(
                    "❌ Atlas Local container did not become healthy in time", err=True
                )
                typer.echo("no db running", err=True)
                raise typer.Exit(code=1)

        # Check if container exists but is stopped
        ps_all_result = subprocess.run(
            [
                "docker",
                "ps",
                "-a",
                "--filter",
                f"name={container_name}",
                "--format",
                "{{.Names}}",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if ps_all_result.returncode == 0 and container_name in ps_all_result.stdout:
            # Container exists but is stopped, start it
            typer.echo(
                f"🚀 Starting existing Atlas Local container: {container_name}..."
            )
            start_result = subprocess.run(
                ["docker", "start", container_name],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if start_result.returncode != 0:
                typer.echo(
                    f"❌ Failed to start Atlas Local container: {start_result.stderr}",
                    err=True,
                )
                typer.echo("no db running", err=True)
                raise typer.Exit(code=1)
        else:
            # No container exists, create and start a new one
            typer.echo(
                f"🚀 Starting new Atlas Local container with image: {full_image}..."
            )

            # Build docker run command
            docker_cmd = [
                "docker",
                "run",
                "-d",
                "--name",
                container_name,
                "-p",
                f"{port}:27017",
            ]

            # Add any additional docker options
            docker_cmd.extend(docker_options)

            # Add the image
            docker_cmd.append(full_image)

            run_result = subprocess.run(
                docker_cmd,
                capture_output=True,
                text=True,
                timeout=120,
            )

            if run_result.returncode != 0:
                typer.echo(
                    f"❌ Failed to start Atlas Local: {run_result.stderr}", err=True
                )
                typer.echo("no db running", err=True)
                raise typer.Exit(code=1)

        # Wait for container to become healthy
        typer.echo("⏳ Waiting for Atlas Local to become healthy...")
        for _ in range(60):  # Wait up to 2 minutes
            import time

            time.sleep(2)
            health_result = subprocess.run(
                [
                    "docker",
                    "inspect",
                    "--format",
                    "{{.State.Health.Status}}",
                    container_name,
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if (
                health_result.returncode == 0
                and health_result.stdout.strip() == "healthy"
            ):
                # Atlas Local runs as a replica set with internal hostname
                # Use directConnection=true to bypass replica set discovery
                mongodb_uri = f"mongodb://localhost:{port}/?directConnection=true"
                env["MONGODB_URI"] = mongodb_uri
                _atlas_local_started = True
                typer.echo("✅ Atlas Local started successfully")
                typer.echo(f"🔗 Using MongoDB URI: {mongodb_uri}")
                return env

        typer.echo("❌ Atlas Local did not become healthy in time", err=True)
        typer.echo("💡 Check container logs: docker logs " + container_name, err=True)
        typer.echo("no db running", err=True)
        raise typer.Exit(code=1)

    except subprocess.TimeoutExpired:
        typer.echo("❌ Docker command timed out", err=True)
        typer.echo("no db running", err=True)
        raise typer.Exit(code=1)
    except FileNotFoundError:
        typer.echo("❌ docker command not found. Cannot use Atlas Local.", err=True)
        typer.echo("💡 Install Docker: https://docs.docker.com/get-docker/", err=True)
        typer.echo("no db running", err=True)
        raise typer.Exit(code=1)
    except Exception as e:
        typer.echo(f"❌ Failed to start Atlas Local: {e}", err=True)
        typer.echo("no db running", err=True)
        raise typer.Exit(code=1)


def ensure_mongodb_runner(env: dict, config: dict) -> dict:
    """
    Start MongoDB using mongodb-runner.

    Args:
        env: Environment dictionary to update with MONGODB_URI
        config: Configuration dictionary

    Returns:
        Updated environment dictionary with MONGODB_URI set

    Raises:
        typer.Exit: If npx is not available or mongodb-runner fails to start
    """
    global _mongodb_runner_started

    # Get configuration
    mongodb_config = config.get("project", {}).get("mongodb", {})
    edition = mongodb_config.get("edition", "community")
    runner_config = mongodb_config.get("mongodb_runner", {})
    topology = runner_config.get("topology", "standalone")
    shards = runner_config.get("shards")
    secondaries = runner_config.get("secondaries")
    arbiters = runner_config.get("arbiters")
    additional_options = runner_config.get("options", [])

    edition_label = "Enterprise" if edition == "enterprise" else "Community"
    topology_label = topology.capitalize()
    typer.echo(
        f"⚠️  MONGODB_URI is not set. Checking for mongodb-runner ({edition_label}, {topology_label})..."
    )

    try:
        # Check if npx is available
        npx_check = subprocess.run(
            ["which", "npx"],
            capture_output=True,
            text=True,
        )
        if npx_check.returncode != 0:
            typer.echo("❌ npx is not available. Cannot use mongodb-runner.", err=True)
            typer.echo("no db running", err=True)
            raise typer.Exit(code=1)

        # Check if mongodb-runner is already running
        ls_result = subprocess.run(
            ["npx", "mongodb-runner", "ls"],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if ls_result.returncode == 0 and ls_result.stdout.strip():
            # Parse the first running instance's URI
            uri_match = re.search(r"(mongodb://[^\s]+)", ls_result.stdout)
            if uri_match:
                mongodb_uri = uri_match.group(1).rstrip("/")
                env["MONGODB_URI"] = mongodb_uri
                typer.echo("✅ Found running mongodb-runner instance")
                typer.echo(f"🔗 Using MongoDB URI: {mongodb_uri}")
                return env

        # No running instance, start a new one
        typer.echo(
            f"🚀 Starting MongoDB {edition_label} ({topology_label}) with mongodb-runner..."
        )

        # Build command with options
        cmd = ["npx", "mongodb-runner", "start"]

        # Add topology
        if topology and topology != "standalone":
            cmd.extend(["-t", topology])

        # Add enterprise flag if needed
        if edition == "enterprise":
            cmd.append("--enterprise")

        # Add topology-specific options
        if shards is not None and topology == "sharded":
            cmd.extend(["--shards", str(shards)])

        if secondaries is not None and topology in ["replset", "sharded"]:
            cmd.extend(["--secondaries", str(secondaries)])

        if arbiters is not None and topology in ["replset", "sharded"]:
            cmd.extend(["--arbiters", str(arbiters)])

        # Add any additional options from config
        cmd.extend(additional_options)

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,  # 2 minute timeout for download/start
        )

        if result.returncode != 0:
            typer.echo(f"❌ mongodb-runner failed to start: {result.stderr}", err=True)
            typer.echo("no db running", err=True)
            raise typer.Exit(code=1)

        # Parse the MongoDB URI from mongodb-runner output
        # Output format includes "mongodb://127.0.0.1:PORT/" on multiple lines
        mongodb_uri = None
        output = result.stdout + result.stderr
        # Look for mongodb:// URI in the output
        uri_match = re.search(r"(mongodb://[^\s]+)", output)
        if uri_match:
            mongodb_uri = uri_match.group(1).rstrip("/")
        else:
            # Fallback to default if we can't parse the output
            mongodb_uri = "mongodb://localhost:27017"
            typer.echo(
                "⚠️  Could not parse mongodb-runner output, using default URI",
                err=True,
            )

        env["MONGODB_URI"] = mongodb_uri
        _mongodb_runner_started = True
        typer.echo("✅ MongoDB started successfully with mongodb-runner")
        typer.echo(f"🔗 Using MongoDB URI: {mongodb_uri}")
        return env

    except subprocess.TimeoutExpired:
        typer.echo("❌ mongodb-runner timed out", err=True)
        typer.echo("no db running", err=True)
        raise typer.Exit(code=1)
    except FileNotFoundError:
        typer.echo("❌ npx command not found. Cannot start mongodb-runner.", err=True)
        typer.echo("no db running", err=True)
        raise typer.Exit(code=1)
    except Exception as e:
        typer.echo(f"❌ Failed to start mongodb-runner: {e}", err=True)
        typer.echo("no db running", err=True)
        raise typer.Exit(code=1)


def ensure_mongodb(
    env: dict, backend_override: str = None, edition_override: str = None
) -> dict:
    """
    Ensure MongoDB is available.

    Checks for MONGODB_URI in the environment. If not set:
    1. Check config for backend preference (mongodb-runner, docker, or atlas-local)
    2. Try to start MongoDB using the configured backend
    3. If backend fails, exit with "no db running"

    Args:
        env: Environment dictionary to update with MONGODB_URI
        backend_override: Optional backend override from CLI flag
        edition_override: Optional edition override from CLI flag

    Returns:
        Updated environment dictionary with MONGODB_URI set

    Raises:
        typer.Exit: If no MongoDB is available and configured backend fails
    """
    if "MONGODB_URI" in env and env["MONGODB_URI"]:
        typer.echo(f"🔗 Using MONGODB_URI from environment: {env['MONGODB_URI']}")
        return env

    # Check for default MONGODB_URI in config
    config = get_config()
    default_env = config.get("project", {}).get("default_env", {})
    default_uri = default_env.get("MONGODB_URI")

    if default_uri:
        typer.echo(f"🔗 Using default MongoDB URI from config: {default_uri}")
        env["MONGODB_URI"] = default_uri
        return env

    # Apply CLI overrides to config
    mongodb_config = config.get("project", {}).get("mongodb", {}).copy()

    # Override backend if provided via CLI
    if backend_override:
        mongodb_config["backend"] = backend_override
        typer.echo(f"🔧 Using backend from CLI: {backend_override}")

    # Override edition if provided via CLI
    if edition_override:
        mongodb_config["edition"] = edition_override
        typer.echo(f"🔧 Using edition from CLI: {edition_override}")

    # Update config with overrides
    config_with_overrides = config.copy()
    if "project" not in config_with_overrides:
        config_with_overrides["project"] = {}
    config_with_overrides["project"]["mongodb"] = mongodb_config

    # Check which backend to use
    backend = mongodb_config.get("backend", "mongodb-runner")

    if backend == "atlas-local":
        return ensure_mongodb_atlas_local(env, config_with_overrides)
    elif backend == "docker":
        return ensure_mongodb_docker(env, config_with_overrides)
    else:
        return ensure_mongodb_runner(env, config_with_overrides)


app = typer.Typer(
    help="💚 Project management commands",
    context_settings={"help_option_names": ["-h", "--help"]},
    no_args_is_help=True,
)


def get_newest_project(projects_dir: Path) -> tuple[str, Path]:
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

    # Find all projects (directories with pyproject.toml)
    projects = []
    for item in projects_dir.iterdir():
        if item.is_dir() and (item / "pyproject.toml").exists():
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
    projects_dir = base_dir / "projects"

    if not projects_dir.exists():
        typer.echo(f"Projects directory: {projects_dir}\n")
        typer.echo("No projects directory found.")
        typer.echo("\nCreate a project using: dbx project add <name>")
        raise typer.Exit(0)

    # Find all projects (directories with pyproject.toml)
    projects = []
    for item in projects_dir.iterdir():
        if item.is_dir() and (item / "pyproject.toml").exists():
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
):
    """
    Create a new Django project using bundled templates.
    Frontend is added by default. Use --no-frontend to skip frontend creation.

    Projects are created in base_dir/projects/ by default.
    If no name is provided, a random name is generated.

    Examples::

        dbx project add                    # Create with random name (includes frontend)
        dbx project add myproject          # Create with explicit name (includes frontend)
        dbx project add myproject --no-frontend  # Create without frontend
        dbx project add -d ~/custom/path   # Create with random name in custom directory
        dbx project add myproject -d ~/custom/path  # Create in custom directory
        dbx project add myproject --base-dir ~/path/to/myproject  # Create directly at ~/path/to/myproject
    """
    # Determine project directory and name
    use_base_dir_override = False
    if directory is None:
        config = get_config()
        if base_dir is None:
            # Use base_dir/projects/name as default when using config
            if name is None:
                name = generate_random_project_name()
                typer.echo(f"🎲 Generated random project name: {name}")
            base_dir = get_base_dir(config)
            projects_dir = base_dir / "projects"
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
        try:
            if directory is None and not use_base_dir_override:
                # Using config-based base_dir/projects/name
                # Check: projects_dir/.venv → base_dir/.venv → activated
                python_path, venv_type = get_venv_info(
                    None, projects_dir, base_path=base_dir
                )
            else:
                # Using custom --directory or --base-dir override
                # Check: activated venv only
                python_path, venv_type = get_venv_info(None, None, base_path=None)

            # Show which venv is being used
            if venv_type == "group":
                typer.echo(f"✅ Using projects group venv: {projects_dir}/.venv\n")
            elif venv_type == "base":
                typer.echo(f"✅ Using base venv: {base_dir}/.venv\n")
            elif venv_type == "venv":
                typer.echo(f"✅ Using activated venv: {python_path}\n")
        except typer.Exit:
            if not auto_install:
                # When --no-install is given we only need django-admin to scaffold
                # the project — no installation step runs, so a dedicated venv is
                # not required.  Fall back to the current interpreter; django-admin
                # will be available as long as Django is installed in this env.
                python_path = sys.executable
            else:
                # Installation requires a proper venv.  Re-raise the error.
                raise

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

        # When using --base-dir override, create project in current directory (.)
        # Otherwise, let django-admin create the directory
        if use_base_dir_override:
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
    _create_pyproject_toml(project_path, name, settings_path)

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

            # Get the virtual environment info
            # This will raise an error if no venv is found
            python_path, venv_type = get_venv_info(
                project_path, None, base_path=repos_base_dir
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


def _create_pyproject_toml(
    project_path: Path, project_name: str, settings_path: str = "settings.base"
):
    """Create a pyproject.toml file for the Django project."""
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
    "django-debug-toolbar",
    "django-mongodb-backend",
    "python-webpack-boilerplate",
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


def _add_frontend(
    project_name: str,
    directory: Path = Path("."),
    python_path: str = None,
):
    """
    Internal helper to create a frontend app inside an existing project.

    ``python_path`` should be the Python executable inside the target venv.
    When provided, python -m django is used to ensure the correct Django
    is invoked even when the venv is not activated in the calling shell.
    """
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

    # Use the provided python_path or fall back to system python
    effective_python = python_path if python_path else "python"

    # Locate the Django app template directory in package resources
    with resources.path(
        "dbx_python_cli.templates", "frontend_template"
    ) as template_path:
        # Use python -m django to ensure we use the correct venv's Django
        cmd = [
            effective_python,
            "-m",
            "django",
            "startapp",
            "--template",
            str(template_path),
            name,
            str(project_path),
        ]
        subprocess.run(cmd, check=True)


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
    # Determine project directory
    if directory is None:
        # Use base_dir/projects/ as default
        config = get_config()
        base_dir = get_base_dir(config)
        projects_dir = base_dir / "projects"

        # If no name provided, find the newest project
        if name is None:
            name, target = get_newest_project(projects_dir)
            typer.echo(f"ℹ️  No project specified, using newest: '{name}'")
        else:
            target = projects_dir / name
    else:
        if name is None:
            typer.echo("❌ Project name is required when using --directory", err=True)
            raise typer.Exit(code=1)
        target = directory / name

    if not target.exists() or not target.is_dir():
        typer.echo(f"❌ Project {name} does not exist at {target}.", err=True)
        return

    # Try to uninstall the package from the current environment before
    # removing the project directory. Failures here are non-fatal so that
    # filesystem cleanup still proceeds.
    uninstall_cmd = [sys.executable, "-m", "pip", "uninstall", "-y", name]
    typer.echo(f"📦 Uninstalling project package '{name}' with pip")
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

    shutil.rmtree(target)
    typer.echo(f"🗑️ Removed project {name}")

    # If using default projects directory, check if it's now empty and remove it
    if directory is None:
        # Check if projects_dir is empty (no directories with pyproject.toml)
        remaining_projects = []
        if projects_dir.exists():
            for item in projects_dir.iterdir():
                if item.is_dir() and (item / "pyproject.toml").exists():
                    remaining_projects.append(item)

        # If no projects remain, remove the projects directory
        if not remaining_projects and projects_dir.exists():
            # Check if directory is completely empty or only has hidden files
            all_items = list(projects_dir.iterdir())
            if not all_items:
                shutil.rmtree(projects_dir)
                typer.echo(f"🗑️ Removed empty projects directory: {projects_dir}")


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
    import os
    import signal

    # Determine project directory
    # Initialise here so they are in scope for the venv detection below
    base_dir = None
    projects_dir = None

    if directory is None:
        # Use base_dir/projects/ as default
        config = get_config()
        base_dir = get_base_dir(config)
        projects_dir = base_dir / "projects"

        # If no name provided, find the newest project
        if name is None:
            name, project_path = get_newest_project(projects_dir)
            typer.echo(f"ℹ️  No project specified, using newest: '{name}'")
        else:
            project_path = projects_dir / name
    else:
        if name is None:
            typer.echo("❌ Project name is required when using --directory", err=True)
            raise typer.Exit(code=1)
        project_path = directory / name

    if not project_path.exists():
        typer.echo(f"❌ Project '{name}' not found at {project_path}", err=True)
        raise typer.Exit(code=1)

    # Detect the project venv so we use the right Python for manage.py.
    # For Django projects, we need to check the django group venv as well.
    # Priority order:
    #   1. project-level venv  (project_path/.venv)
    #   2. group-level venv    (projects_dir/.venv  OR  directory/.venv)
    #   3. django group venv   (base_dir/django/.venv) - for Django projects
    #   4. base-level venv     (base_dir/.venv, only when using config path)
    #   5. activated / PATH venv
    python_path = None
    venv_type = None

    try:
        if directory is None:
            # First try the standard venv detection (project, projects group, base)
            python_path, venv_type = get_venv_info(
                project_path, projects_dir, base_path=base_dir
            )

            # If we fell back to an activated venv, check if django group venv exists
            # and prefer that for Django projects
            if venv_type == "venv":
                django_group_path = base_dir / "django"
                if django_group_path.exists():
                    django_venv_python = django_group_path / ".venv" / "bin" / "python"
                    if django_venv_python.exists():
                        python_path = str(django_venv_python)
                        venv_type = "group"
                        typer.echo(
                            f"✅ Using Django group venv: {django_group_path}/.venv"
                        )
        else:
            python_path, venv_type = get_venv_info(
                project_path, project_path.parent, base_path=None
            )
    except typer.Exit:
        raise

    # Check if the project is installed in the venv
    # This is important when using the Django group venv
    pyproject_path = project_path / "pyproject.toml"
    if pyproject_path.exists():
        # Check if the project is installed by trying to import it
        # We need to clear PYTHONPATH and run from a different directory to check actual installation
        module_name = name.replace("-", "_")
        check_env = os.environ.copy()
        check_env.pop(
            "PYTHONPATH", None
        )  # Remove PYTHONPATH to check actual installation
        check_cmd = [
            python_path,
            "-c",
            f"import importlib.util; import sys; sys.exit(0 if importlib.util.find_spec('{module_name}') else 1)",
        ]
        # Run from /tmp to avoid Python adding the current directory to sys.path
        result = subprocess.run(
            check_cmd, capture_output=True, env=check_env, cwd="/tmp"
        )

        if result.returncode != 0:
            # Project not installed, install it
            typer.echo(f"📦 Installing project dependencies for '{name}'...")
            install_result = install_package(
                project_path,
                python_path,
                install_dir=None,
                extras=None,
                groups=None,
                verbose=False,
            )
            if install_result != "success":
                typer.echo(
                    f"⚠️  Warning: Failed to install project '{name}'. Some dependencies may be missing.",
                    err=True,
                )

    # Check if frontend exists
    frontend_path = project_path / "frontend"
    has_frontend = frontend_path.exists() and (frontend_path / "package.json").exists()

    typer.echo(f"🚀 Running project '{name}' on http://{host}:{port}")

    # Set up environment
    env = os.environ.copy()

    # Get CLI overrides from context
    backend_override = ctx.obj.get("mongodb_backend") if ctx.obj else None
    edition_override = ctx.obj.get("mongodb_edition") if ctx.obj else None

    # Ensure MongoDB is available (starts mongodb-runner if needed)
    env = ensure_mongodb(env, backend_override, edition_override)

    # Check for default environment variables from config
    config = get_config()
    default_env = config.get("project", {}).get("default_env", {})

    # Set library paths for libmongocrypt (Queryable Encryption support)
    for var in [
        "PYMONGOCRYPT_LIB",
        "DYLD_LIBRARY_PATH",
        "LD_LIBRARY_PATH",
        "CRYPT_SHARED_LIB_PATH",
    ]:
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
    settings_module = settings if settings else name
    env["DJANGO_SETTINGS_MODULE"] = f"{name}.settings.{settings_module}"
    env["PYTHONPATH"] = str(project_path) + os.pathsep + env.get("PYTHONPATH", "")
    typer.echo(f"🔧 Using DJANGO_SETTINGS_MODULE={env['DJANGO_SETTINGS_MODULE']}")

    # Prepend venv bin dir to PATH so the correct manage.py / Django runtime is used
    venv_bin = str(Path(python_path).parent)
    env["PATH"] = f"{venv_bin}{os.pathsep}{env.get('PATH', '')}"

    if has_frontend:
        # Ensure frontend is installed
        typer.echo("📦 Checking frontend dependencies...")
        try:
            _install_npm(name, directory=project_path.parent)
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
                cwd=project_path,
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
                cwd=project_path,
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
    import os

    if args is None:
        args = []

    # Determine project directory
    # Initialise here so they are in scope for the venv detection below
    base_dir = None
    projects_dir = None

    if directory is None:
        config = get_config()
        base_dir = get_base_dir(config)
        projects_dir = base_dir / "projects"

        # If no name provided, find the newest project
        if name is None:
            name, project_path = get_newest_project(projects_dir)
            typer.echo(f"ℹ️  No project specified, using newest: '{name}'")
        else:
            project_path = projects_dir / name
    else:
        if name is None:
            typer.echo("❌ Project name is required when using --directory", err=True)
            raise typer.Exit(code=1)
        project_path = directory / name

    if not project_path.exists():
        typer.echo(f"❌ Project '{name}' not found at {project_path}", err=True)
        raise typer.Exit(code=1)

    # Detect the project venv so we use the right Python for django-admin.
    # For Django projects, we need to check the django group venv as well.
    # Priority order:
    #   1. project-level venv  (project_path/.venv)
    #   2. group-level venv    (projects_dir/.venv  OR  directory/.venv)
    #   3. django group venv   (base_dir/django/.venv) - for Django projects
    #   4. base-level venv     (base_dir/.venv, only when using config path)
    #   5. activated / PATH venv
    python_path = None
    venv_type = None

    try:
        if directory is None:
            # First try the standard venv detection (project, projects group, base)
            python_path, venv_type = get_venv_info(
                project_path, projects_dir, base_path=base_dir
            )

            # If we fell back to an activated venv, check if django group venv exists
            # and prefer that for Django projects
            if venv_type == "venv":
                django_group_path = base_dir / "django"
                if django_group_path.exists():
                    django_venv_python = django_group_path / ".venv" / "bin" / "python"
                    if django_venv_python.exists():
                        python_path = str(django_venv_python)
                        venv_type = "group"
                        typer.echo(
                            f"✅ Using Django group venv: {django_group_path}/.venv"
                        )
        else:
            python_path, venv_type = get_venv_info(
                project_path, project_path.parent, base_path=None
            )
    except typer.Exit:
        raise

    # Set up environment
    env = os.environ.copy()

    # Handle MongoDB URI: explicit flag takes precedence
    if mongodb_uri:
        typer.echo(f"🔗 Using MongoDB URI: {mongodb_uri}")
        env["MONGODB_URI"] = mongodb_uri
    else:
        # Get CLI overrides from context
        backend_override = ctx.obj.get("mongodb_backend") if ctx.obj else None
        edition_override = ctx.obj.get("mongodb_edition") if ctx.obj else None

        # Ensure MongoDB is available (starts mongodb-runner if needed)
        env = ensure_mongodb(env, backend_override, edition_override)

    # Check for default environment variables from config
    config = get_config()
    default_env = config.get("project", {}).get("default_env", {})

    # Set library paths for libmongocrypt (Queryable Encryption support)
    for var in [
        "PYMONGOCRYPT_LIB",
        "DYLD_LIBRARY_PATH",
        "LD_LIBRARY_PATH",
        "CRYPT_SHARED_LIB_PATH",
    ]:
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
    settings_module = settings if settings else name
    env["DJANGO_SETTINGS_MODULE"] = f"{name}.settings.{settings_module}"
    env["PYTHONPATH"] = str(project_path) + os.pathsep + env.get("PYTHONPATH", "")
    typer.echo(f"🔧 Using DJANGO_SETTINGS_MODULE={env['DJANGO_SETTINGS_MODULE']}")

    # Build command - use python -m django to ensure we use the correct venv's Django
    cmd_args = []
    if command:
        cmd_args.append(command)
        if database:
            cmd_args.append(f"--database={database}")
        cmd_args.extend(args)
        typer.echo(f"⚙️  Running: {python_path} -m django {' '.join(cmd_args)}")
    else:
        typer.echo(f"ℹ️  Running: {python_path} -m django")

    try:
        subprocess.run(
            [python_path, "-m", "django", *cmd_args],
            cwd=project_path.parent,
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
    import os

    if not email:
        email = os.getenv("PROJECT_EMAIL", "admin@example.com")

    # Determine project directory
    # Initialise here so they are in scope for the venv detection below
    base_dir = None
    projects_dir = None

    if directory is None:
        config = get_config()
        base_dir = get_base_dir(config)
        projects_dir = base_dir / "projects"

        # If no name provided, find the newest project
        if name is None:
            name, project_path = get_newest_project(projects_dir)
            typer.echo(f"ℹ️  No project specified, using newest: '{name}'")
        else:
            project_path = projects_dir / name
    else:
        if name is None:
            typer.echo("❌ Project name is required when using --directory", err=True)
            raise typer.Exit(code=1)
        project_path = directory / name

    typer.echo(f"👑 Creating Django superuser '{username}' for project '{name}'")

    if not project_path.exists():
        typer.echo(f"❌ Project '{name}' not found at {project_path}", err=True)
        raise typer.Exit(code=1)

    # Detect the project venv so we use the right Python for django-admin.
    # For Django projects, we need to check the django group venv as well.
    # Priority order:
    #   1. project-level venv  (project_path/.venv)
    #   2. group-level venv    (projects_dir/.venv  OR  directory/.venv)
    #   3. django group venv   (base_dir/django/.venv) - for Django projects
    #   4. base-level venv     (base_dir/.venv, only when using config path)
    #   5. activated / PATH venv
    python_path = None
    venv_type = None

    try:
        if directory is None:
            # First try the standard venv detection (project, projects group, base)
            python_path, venv_type = get_venv_info(
                project_path, projects_dir, base_path=base_dir
            )

            # If we fell back to an activated venv, check if django group venv exists
            # and prefer that for Django projects
            if venv_type == "venv":
                django_group_path = base_dir / "django"
                if django_group_path.exists():
                    django_venv_python = django_group_path / ".venv" / "bin" / "python"
                    if django_venv_python.exists():
                        python_path = str(django_venv_python)
                        venv_type = "group"
                        typer.echo(
                            f"✅ Using Django group venv: {django_group_path}/.venv"
                        )
        else:
            python_path, venv_type = get_venv_info(
                project_path, project_path.parent, base_path=None
            )
    except typer.Exit:
        raise

    # Set up environment
    env = os.environ.copy()

    # Handle MongoDB URI: explicit flag takes precedence
    if mongodb_uri:
        typer.echo(f"🔗 Using MongoDB URI: {mongodb_uri}")
        env["MONGODB_URI"] = mongodb_uri
    else:
        # Get CLI overrides from context
        backend_override = ctx.obj.get("mongodb_backend") if ctx.obj else None
        edition_override = ctx.obj.get("mongodb_edition") if ctx.obj else None

        # Ensure MongoDB is available (starts mongodb-runner if needed)
        env = ensure_mongodb(env, backend_override, edition_override)

    # Check for default environment variables from config
    config = get_config()
    default_env = config.get("project", {}).get("default_env", {})

    # Set library paths for libmongocrypt (Queryable Encryption support)
    for var in [
        "PYMONGOCRYPT_LIB",
        "DYLD_LIBRARY_PATH",
        "LD_LIBRARY_PATH",
        "CRYPT_SHARED_LIB_PATH",
    ]:
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

    env["DJANGO_SUPERUSER_PASSWORD"] = password

    # Default to project_name.py settings if not specified
    settings_module = settings if settings else name
    env["DJANGO_SETTINGS_MODULE"] = f"{name}.settings.{settings_module}"
    env["PYTHONPATH"] = str(project_path) + os.pathsep + env.get("PYTHONPATH", "")
    typer.echo(f"🔧 Using DJANGO_SETTINGS_MODULE={env['DJANGO_SETTINGS_MODULE']}")

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
            cwd=project_path.parent,
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
    import os

    # Determine project directory
    # Initialise here so they are in scope for the venv detection below
    base_dir = None
    projects_dir = None

    if directory is None:
        config = get_config()
        base_dir = get_base_dir(config)
        projects_dir = base_dir / "projects"

        # If no name provided, find the newest project
        if name is None:
            name, project_path = get_newest_project(projects_dir)
            typer.echo(f"ℹ️  No project specified, using newest: '{name}'")
        else:
            project_path = projects_dir / name
    else:
        if name is None:
            typer.echo("❌ Project name is required when using --directory", err=True)
            raise typer.Exit(code=1)
        project_path = directory / name

    if not project_path.exists():
        typer.echo(f"❌ Project '{name}' not found at {project_path}", err=True)
        raise typer.Exit(code=1)

    # Detect the project venv so we use the right Python for django-admin.
    # For Django projects, we need to check the django group venv as well.
    # Priority order:
    #   1. project-level venv  (project_path/.venv)
    #   2. group-level venv    (projects_dir/.venv  OR  directory/.venv)
    #   3. django group venv   (base_dir/django/.venv) - for Django projects
    #   4. base-level venv     (base_dir/.venv, only when using config path)
    #   5. activated / PATH venv
    python_path = None
    venv_type = None

    try:
        if directory is None:
            # First try the standard venv detection (project, projects group, base)
            python_path, venv_type = get_venv_info(
                project_path, projects_dir, base_path=base_dir
            )

            # If we fell back to an activated venv, check if django group venv exists
            # and prefer that for Django projects
            if venv_type == "venv":
                django_group_path = base_dir / "django"
                if django_group_path.exists():
                    django_venv_python = django_group_path / ".venv" / "bin" / "python"
                    if django_venv_python.exists():
                        python_path = str(django_venv_python)
                        venv_type = "group"
                        typer.echo(
                            f"✅ Using Django group venv: {django_group_path}/.venv"
                        )
        else:
            python_path, venv_type = get_venv_info(
                project_path, project_path.parent, base_path=None
            )
    except typer.Exit:
        raise

    # Set up environment
    env = os.environ.copy()

    # Handle MongoDB URI: explicit flag takes precedence
    if mongodb_uri:
        typer.echo(f"🔗 Using MongoDB URI: {mongodb_uri}")
        env["MONGODB_URI"] = mongodb_uri
    else:
        # Get CLI overrides from context
        backend_override = ctx.obj.get("mongodb_backend") if ctx.obj else None
        edition_override = ctx.obj.get("mongodb_edition") if ctx.obj else None

        # Ensure MongoDB is available (starts mongodb-runner if needed)
        env = ensure_mongodb(env, backend_override, edition_override)

    # Check for default environment variables from config
    config = get_config()
    default_env = config.get("project", {}).get("default_env", {})

    # Set library paths for libmongocrypt (Queryable Encryption support)
    for var in [
        "PYMONGOCRYPT_LIB",
        "DYLD_LIBRARY_PATH",
        "LD_LIBRARY_PATH",
        "CRYPT_SHARED_LIB_PATH",
    ]:
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
    settings_module = settings if settings else name
    env["DJANGO_SETTINGS_MODULE"] = f"{name}.settings.{settings_module}"
    env["PYTHONPATH"] = str(project_path) + os.pathsep + env.get("PYTHONPATH", "")
    typer.echo(f"🔧 Using DJANGO_SETTINGS_MODULE={env['DJANGO_SETTINGS_MODULE']}")

    # Build migrate command - use python -m django to ensure we use the correct venv's Django
    cmd = [python_path, "-m", "django", "migrate"]
    if database:
        cmd.append(f"--database={database}")
        typer.echo(f"🗄️  Running migrations for database: {database}")
    else:
        typer.echo(f"🗄️  Running migrations for project '{name}'")

    try:
        subprocess.run(
            cmd,
            cwd=project_path.parent,
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
    Edit project settings file with your default editor.

    Opens the project's settings file using the editor specified in the EDITOR
    environment variable. If EDITOR is not set, falls back to common editors
    (vim, nano, vi) or uses 'open' on macOS.

    If no project name is provided, uses the most recently created project.

    Examples::

        dbx project edit                      # Edit newest project's settings
        dbx project edit myproject            # Edit myproject's settings
        dbx project edit myproject --settings base  # Edit base settings
        dbx project edit myproject -s qe      # Edit qe settings
        EDITOR=code dbx project edit          # Open with VS Code
    """
    # Determine project directory
    if directory is None:
        config = get_config()
        base_dir = get_base_dir(config)
        projects_dir = base_dir / "projects"

        # If no name provided, find the newest project
        if name is None:
            name, project_path = get_newest_project(projects_dir)
            typer.echo(f"ℹ️  No project specified, using newest: '{name}'")
        else:
            project_path = projects_dir / name
    else:
        if name is None:
            typer.echo("❌ Project name is required when using --directory", err=True)
            raise typer.Exit(code=1)
        project_path = directory / name

    if not project_path.exists():
        typer.echo(f"❌ Project '{name}' not found at {project_path}", err=True)
        raise typer.Exit(code=1)

    # Determine which settings file to edit
    settings_module = settings if settings else name
    settings_file = project_path / name / "settings" / f"{settings_module}.py"

    if not settings_file.exists():
        typer.echo(f"❌ Settings file not found: {settings_file}", err=True)
        typer.echo(f"\nAvailable settings files in {project_path / name / 'settings'}:")
        settings_dir = project_path / name / "settings"
        if settings_dir.exists():
            for file in settings_dir.glob("*.py"):
                if file.name != "__init__.py":
                    typer.echo(f"  • {file.stem}")
        raise typer.Exit(code=1)

    # Get editor from environment variable
    editor = os.environ.get("EDITOR")

    if not editor:
        # Try common editors in order of preference
        common_editors = ["vim", "nano", "vi"]
        for candidate in common_editors:
            try:
                # Check if editor exists in PATH
                subprocess.run(
                    ["which", candidate],
                    check=True,
                    capture_output=True,
                )
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

    typer.echo(f"📝 Opening {settings_file} with {editor}...")

    try:
        # Open the editor
        result = subprocess.run([editor, str(settings_file)])

        if result.returncode == 0:
            typer.echo("✅ Settings file saved")
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
