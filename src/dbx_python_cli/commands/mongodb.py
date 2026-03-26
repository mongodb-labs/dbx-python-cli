"""MongoDB management utilities.

This module provides functions to ensure MongoDB is available for Django projects
and tests. It supports multiple backends:
- mongodb-runner (default): Uses npx mongodb-runner to manage MongoDB
- docker: Uses standard MongoDB Docker images (community or enterprise)
- atlas-local: Uses MongoDB Atlas Local Docker image

These utilities are used by both `dbx project` commands and `dbx test` commands.
"""

import re
import subprocess
import time

import typer

from dbx_python_cli.utils.repo import get_config

# Global variables to track if we started mongodb-runner, docker, or atlas-local
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
    Start MongoDB using mongodb-runner (via npx).

    Args:
        env: Environment dictionary to update with MONGODB_URI
        config: Configuration dictionary

    Returns:
        Updated environment dictionary with MONGODB_URI set

    Raises:
        typer.Exit: If mongodb-runner fails to start
    """
    global _mongodb_runner_started

    # Get mongodb-runner configuration
    runner_config = config.get("project", {}).get("mongodb", {}).get("runner", {})
    port = runner_config.get("port")  # Let mongodb-runner choose if not specified
    topology = runner_config.get("topology", "standalone")
    version = runner_config.get("version")  # Use default if not specified
    edition = config.get("project", {}).get("mongodb", {}).get("edition", "community")

    typer.echo(f"⚠️  MONGODB_URI is not set. Checking for mongodb-runner ({edition})...")

    # First check if mongodb-runner is already running (use 'ls' command)
    try:
        ls_result = subprocess.run(
            ["npx", "mongodb-runner", "ls"],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if ls_result.returncode == 0 and ls_result.stdout.strip():
            # Extract MONGODB_URI from ls output (first running instance)
            stdout = ls_result.stdout
            uri_match = re.search(r"(mongodb://[^\s]+)", stdout)
            if uri_match:
                mongodb_uri = uri_match.group(1)
                env["MONGODB_URI"] = mongodb_uri
                typer.echo(f"✅ Found running mongodb-runner: {mongodb_uri}")
                return env
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass  # mongodb-runner not available or not running

    # Try to start mongodb-runner
    typer.echo(f"🚀 Starting mongodb-runner with {edition} edition...")

    try:
        # Build mongodb-runner start command
        start_cmd = ["npx", "mongodb-runner", "start", "--topology", topology]
        if port:
            start_cmd.extend(["--port", str(port)])
        if version:
            start_cmd.extend(["--version", version])
        if edition == "enterprise":
            start_cmd.append("--enterprise")

        result = subprocess.run(
            start_cmd,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout for downloads
        )

        if result.returncode != 0:
            typer.echo(f"❌ Failed to start mongodb-runner: {result.stderr}", err=True)
            typer.echo("no db running", err=True)
            raise typer.Exit(code=1)

        # Get the list of running instances to find the URI
        ls_result = subprocess.run(
            ["npx", "mongodb-runner", "ls"],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if ls_result.returncode == 0 and ls_result.stdout.strip():
            stdout = ls_result.stdout
            uri_match = re.search(r"(mongodb://[^\s]+)", stdout)
            if uri_match:
                mongodb_uri = uri_match.group(1)
                env["MONGODB_URI"] = mongodb_uri
                _mongodb_runner_started = True
                typer.echo("✅ mongodb-runner started successfully")
                typer.echo(f"🔗 Using MongoDB URI: {mongodb_uri}")
                return env

        typer.echo("❌ Could not determine MongoDB URI from mongodb-runner", err=True)
        typer.echo("no db running", err=True)
        raise typer.Exit(code=1)

    except subprocess.TimeoutExpired:
        typer.echo("❌ mongodb-runner timed out", err=True)
        typer.echo("no db running", err=True)
        raise typer.Exit(code=1)
    except FileNotFoundError:
        typer.echo("❌ npx command not found. Cannot use mongodb-runner.", err=True)
        typer.echo("💡 Install Node.js/npm: https://nodejs.org/", err=True)
        typer.echo("no db running", err=True)
        raise typer.Exit(code=1)
    except Exception as e:
        typer.echo(f"❌ Failed to start mongodb-runner: {e}", err=True)
        typer.echo("no db running", err=True)
        raise typer.Exit(code=1)


def ensure_mongodb(
    env: dict,
    backend_override: str | None = None,
    edition_override: str | None = None,
) -> dict:
    """
    Ensure MongoDB is available for the application.

    If MONGODB_URI is already set in the environment, returns immediately.
    Otherwise, attempts to start MongoDB using the configured backend.

    Args:
        env: Environment dictionary to check/update
        backend_override: Override the configured backend (runner, docker, atlas-local)
        edition_override: Override the configured edition (community, enterprise)

    Returns:
        Updated environment dictionary with MONGODB_URI set

    Raises:
        typer.Exit: If MongoDB cannot be started
    """
    import os

    # If MONGODB_URI is already set, use it
    if "MONGODB_URI" in env:
        typer.echo(f"✅ Using existing MONGODB_URI: {env['MONGODB_URI']}")
        return env

    # Check if MONGODB_URI is set in the environment
    if "MONGODB_URI" in os.environ:
        env["MONGODB_URI"] = os.environ["MONGODB_URI"]
        typer.echo(f"✅ Using MONGODB_URI from environment: {env['MONGODB_URI']}")
        return env

    # Get configuration
    config = get_config()

    # Check for default MONGODB_URI in config
    default_env = config.get("project", {}).get("default_env", {})
    default_uri = default_env.get("MONGODB_URI")
    if default_uri:
        typer.echo(f"🔗 Using default MongoDB URI from config: {default_uri}")
        env["MONGODB_URI"] = default_uri
        return env

    mongodb_config = config.get("project", {}).get("mongodb", {})

    # Determine backend (CLI override > config > default)
    backend = backend_override or mongodb_config.get("backend", "runner")

    # Apply edition override if provided
    if edition_override:
        if "project" not in config:
            config["project"] = {}
        if "mongodb" not in config["project"]:
            config["project"]["mongodb"] = {}
        config["project"]["mongodb"]["edition"] = edition_override

    # Start MongoDB based on backend
    if backend == "runner":
        return ensure_mongodb_runner(env, config)
    elif backend == "docker":
        return ensure_mongodb_docker(env, config)
    elif backend == "atlas-local":
        return ensure_mongodb_atlas_local(env, config)
    else:
        typer.echo(
            f"❌ Unknown MongoDB backend '{backend}'. Valid options: runner, docker, atlas-local",
            err=True,
        )
        raise typer.Exit(code=1)
