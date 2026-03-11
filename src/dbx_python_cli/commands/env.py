"""Virtual environment management commands."""

import subprocess

import typer

from dbx_python_cli.utils.repo import (
    get_base_dir,
    get_config,
    get_global_groups,
    get_python_version,
    get_repo_groups,
)

app = typer.Typer(
    help="Virtual environment management commands",
    context_settings={"help_option_names": ["-h", "--help"]},
    no_args_is_help=True,
)


@app.command()
def init(
    ctx: typer.Context,
    repo: str = typer.Argument(
        None,
        help="Repository name to create venv for (optional, creates venv in repo directory)",
    ),
    group: str = typer.Option(
        None,
        "--group",
        "-g",
        help="Repository group (creates venv in group directory, or specifies which group to find repo in)",
    ),
    python: str = typer.Option(
        None,
        "--python",
        "-p",
        help="Python version to use (e.g., 3.11, 3.12)",
    ),
    list_groups: bool = typer.Option(
        False,
        "--list",
        "-l",
        help="List all available groups",
    ),
):
    """Create a virtual environment.

    By default, creates a venv in the base directory (shared across all repos).
    Use --group to create a venv in a specific group directory.
    Use a positional repo argument to create a venv in an individual repo directory.
    Use both --group and repo to create a venv for a repo within a specific group.
    """
    # Get verbose flag from parent context
    verbose = ctx.obj.get("verbose", False) if ctx.obj else False

    try:
        config = get_config()
        base_dir = get_base_dir(config)
        groups = get_repo_groups(config)
        global_group_names = set(get_global_groups(config))

        if verbose:
            typer.echo(f"[verbose] Using base directory: {base_dir}")
            typer.echo(f"[verbose] Available groups: {sorted(groups)}\n")

        # Handle --list flag
        if list_groups:
            non_global_groups = {
                k: v for k, v in groups.items() if k not in global_group_names
            }
            if not non_global_groups:
                typer.echo("No groups found in configuration.")
                return

            typer.echo("Available groups:\n")
            for group_name in sorted(non_global_groups.keys()):
                group_dir = base_dir / group_name
                venv_path = group_dir / ".venv"
                if venv_path.exists():
                    typer.echo(f"  • {group_name} (venv exists)")
                else:
                    typer.echo(f"  • {group_name} (no venv)")
            return

        # Determine what type of venv to create
        if repo and group:
            # Create venv in individual repo directory within a specific group
            from dbx_python_cli.utils.repo import find_all_repos_by_name

            # Validate group exists
            if group in global_group_names:
                typer.echo(
                    f"❌ Error: '{group}' is a global group used only for config — it has no group directory.",
                    err=True,
                )
                raise typer.Exit(1)
            if group not in groups:
                typer.echo(
                    f"❌ Error: Group '{group}' not found in configuration.", err=True
                )
                typer.echo(f"Available groups: {', '.join(groups.keys())}", err=True)
                raise typer.Exit(1)

            # Find repo within the specified group
            matching_repos = find_all_repos_by_name(repo, base_dir)
            repo_info = None
            for r in matching_repos:
                if r["group"] == group:
                    repo_info = r
                    break

            if not repo_info:
                typer.echo(
                    f"❌ Error: Repository '{repo}' not found in group '{group}'",
                    err=True,
                )
                typer.echo(
                    f"\nClone the repository first with: dbx clone -g {group}", err=True
                )
                raise typer.Exit(1)

            venv_path = repo_info["path"] / ".venv"
            location_desc = f"repository '{repo}' in group '{group}'"
            working_dir = repo_info["path"]

        elif repo:
            # Create venv in individual repo directory
            from dbx_python_cli.utils.repo import find_repo_by_name

            repo_info = find_repo_by_name(repo, base_dir, config)
            if not repo_info:
                typer.echo(f"❌ Error: Repository '{repo}' not found", err=True)
                typer.echo(
                    "\nClone the repository first with: dbx clone <repo>", err=True
                )
                raise typer.Exit(1)

            venv_path = repo_info["path"] / ".venv"
            location_desc = f"repository '{repo}'"
            working_dir = repo_info["path"]

        elif group:
            # Create venv in group directory
            if group in global_group_names:
                typer.echo(
                    f"❌ Error: '{group}' is a global group used only for config — it has no group venv.",
                    err=True,
                )
                raise typer.Exit(1)
            if group not in groups:
                typer.echo(
                    f"❌ Error: Group '{group}' not found in configuration.", err=True
                )
                typer.echo(f"Available groups: {', '.join(groups.keys())}", err=True)
                raise typer.Exit(1)

            group_dir = base_dir / group
            venv_path = group_dir / ".venv"
            location_desc = f"group '{group}'"
            working_dir = group_dir

        else:
            # Create venv in base directory (default)
            venv_path = base_dir / ".venv"
            location_desc = "base directory"
            working_dir = base_dir

        # Check if venv already exists
        if venv_path.exists():
            typer.echo(f"Virtual environment already exists at {venv_path}")
            overwrite = typer.confirm("Do you want to recreate it?")
            if not overwrite:
                typer.echo("Aborted.")
                raise typer.Exit(0)
            # Remove existing venv
            import shutil

            shutil.rmtree(venv_path)

        # Ensure working directory exists
        if not working_dir.exists():
            if verbose:
                typer.echo(f"[verbose] Creating directory: {working_dir}\n")
            working_dir.mkdir(parents=True, exist_ok=True)

        # Determine Python version: CLI flag > config > default
        effective_python = python
        if not effective_python and group:
            effective_python = get_python_version(config, group)

        # Create venv using uv
        if effective_python:
            typer.echo(
                f"Creating virtual environment for {location_desc} at {venv_path} (Python {effective_python})...\n"
            )
        else:
            typer.echo(
                f"Creating virtual environment for {location_desc} at {venv_path}...\n"
            )

        venv_cmd = ["uv", "venv", str(venv_path), "--no-python-downloads"]
        if effective_python:
            venv_cmd.extend(["--python", effective_python])

        if verbose:
            typer.echo(f"[verbose] Running command: {' '.join(venv_cmd)}")
            typer.echo(f"[verbose] Working directory: {working_dir}\n")

        result = subprocess.run(
            venv_cmd,
            cwd=str(working_dir),
            check=False,
            capture_output=not verbose,
            text=True,
        )

        if result.returncode != 0:
            typer.echo("❌ Failed to create virtual environment", err=True)
            if not verbose and result.stderr:
                typer.echo(result.stderr, err=True)
            raise typer.Exit(1)

        typer.echo(f"✅ Virtual environment created at {venv_path}")
        typer.echo(f"\nTo activate: source {venv_path}/bin/activate")
        typer.echo("Or use: dbx install <repo> to install dependencies using this venv")

    except typer.Exit:
        raise
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


@app.command()
def list(ctx: typer.Context):
    """List all virtual environments (base, group, and repo level)."""
    # Get verbose flag from parent context
    verbose = ctx.obj.get("verbose", False) if ctx.obj else False

    try:
        config = get_config()
        base_dir = get_base_dir(config)
        groups = get_repo_groups(config)
        global_group_names = set(get_global_groups(config))
        from dbx_python_cli.utils.repo import find_all_repos

        if verbose:
            typer.echo(f"[verbose] Using base directory: {base_dir}\n")

        typer.echo("Virtual environments:\n")

        found_any = False

        # Check base directory venv
        base_venv_path = base_dir / ".venv"
        if base_venv_path.exists():
            found_any = True
            python_path = base_venv_path / "bin" / "python"
            if python_path.exists():
                # Get Python version
                result = subprocess.run(
                    [str(python_path), "--version"],
                    capture_output=True,
                    text=True,
                )
                version = result.stdout.strip() if result.returncode == 0 else "unknown"
                typer.echo(f"  ✅ [BASE]: {base_venv_path} ({version})")
            else:
                typer.echo(f"  ⚠️  [BASE]: {base_venv_path} (invalid)")
        else:
            typer.echo("  ❌ [BASE]: No venv (create with: dbx env init)")

        # Check group-level venvs (skip global groups — they have no group directory)
        typer.echo("\n  Group venvs:")
        for group_name in sorted(
            k for k in groups.keys() if k not in global_group_names
        ):
            group_dir = base_dir / group_name
            venv_path = group_dir / ".venv"

            if venv_path.exists():
                found_any = True
                python_path = venv_path / "bin" / "python"
                if python_path.exists():
                    # Get Python version
                    result = subprocess.run(
                        [str(python_path), "--version"],
                        capture_output=True,
                        text=True,
                    )
                    version = (
                        result.stdout.strip() if result.returncode == 0 else "unknown"
                    )
                    typer.echo(f"    ✅ {group_name}: {venv_path} ({version})")
                else:
                    typer.echo(f"    ⚠️  {group_name}: {venv_path} (invalid)")
            else:
                typer.echo(
                    f"    ❌ {group_name}: No venv (create with: dbx env init -g {group_name})"
                )

        # Check repo-level venvs
        all_repos = find_all_repos(base_dir)
        repo_venvs = []
        for repo in all_repos:
            repo_venv_path = repo["path"] / ".venv"
            if repo_venv_path.exists():
                repo_venvs.append((repo["name"], repo["group"], repo_venv_path))
                found_any = True

        if repo_venvs:
            typer.echo("\n  Repository venvs:")
            for repo_name, group_name, venv_path in sorted(repo_venvs):
                python_path = venv_path / "bin" / "python"
                if python_path.exists():
                    # Get Python version
                    result = subprocess.run(
                        [str(python_path), "--version"],
                        capture_output=True,
                        text=True,
                    )
                    version = (
                        result.stdout.strip() if result.returncode == 0 else "unknown"
                    )
                    typer.echo(
                        f"    ✅ {repo_name} ({group_name}): {venv_path} ({version})"
                    )
                else:
                    typer.echo(
                        f"    ⚠️  {repo_name} ({group_name}): {venv_path} (invalid)"
                    )

        if not found_any:
            typer.echo("\n  No virtual environments found.")
            typer.echo("\nCreate one with:")
            typer.echo("  dbx env init              (base dir)")
            typer.echo("  dbx env init -g <group>   (group)")
            typer.echo("  dbx env init <repo>       (individual repo)")

    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


@app.command()
def remove(
    ctx: typer.Context,
    repo: str = typer.Argument(
        None,
        help="Repository name to remove venv for (optional, removes venv from repo directory)",
    ),
    group: str = typer.Option(
        None,
        "--group",
        "-g",
        help="Repository group (removes venv from group directory, or specifies which group to find repo in)",
    ),
    list_groups: bool = typer.Option(
        False,
        "--list",
        "-l",
        help="List all available groups",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Skip confirmation prompt",
    ),
):
    """Remove a virtual environment.

    By default, removes the venv from the base directory.
    Use --group to remove a venv from a specific group directory.
    Use a positional repo argument to remove a venv from an individual repo directory.
    Use both --group and repo to remove a venv for a repo within a specific group.
    """
    # Get verbose flag from parent context
    verbose = ctx.obj.get("verbose", False) if ctx.obj else False

    try:
        config = get_config()
        base_dir = get_base_dir(config)
        groups = get_repo_groups(config)
        global_group_names = set(get_global_groups(config))

        if verbose:
            typer.echo(f"[verbose] Using base directory: {base_dir}")
            typer.echo(f"[verbose] Available groups: {sorted(groups)}\n")

        # Handle --list flag
        if list_groups:
            non_global_groups = {
                k: v for k, v in groups.items() if k not in global_group_names
            }
            if not non_global_groups:
                typer.echo("No groups found in configuration.")
                return

            typer.echo("Available groups:\n")
            for group_name in sorted(non_global_groups.keys()):
                group_dir = base_dir / group_name
                venv_path = group_dir / ".venv"
                if venv_path.exists():
                    typer.echo(f"  • {group_name} (venv exists)")
                else:
                    typer.echo(f"  • {group_name} (no venv)")
            return

        # Determine what type of venv to remove
        if repo and group:
            # Remove venv from individual repo directory within a specific group
            from dbx_python_cli.utils.repo import find_all_repos_by_name

            # Validate group exists
            if group in global_group_names:
                typer.echo(
                    f"❌ Error: '{group}' is a global group used only for config — it has no group directory.",
                    err=True,
                )
                raise typer.Exit(1)
            if group not in groups:
                typer.echo(
                    f"❌ Error: Group '{group}' not found in configuration.", err=True
                )
                typer.echo(f"Available groups: {', '.join(groups.keys())}", err=True)
                raise typer.Exit(1)

            # Find repo within the specified group
            matching_repos = find_all_repos_by_name(repo, base_dir)
            repo_info = None
            for r in matching_repos:
                if r["group"] == group:
                    repo_info = r
                    break

            if not repo_info:
                typer.echo(
                    f"❌ Error: Repository '{repo}' not found in group '{group}'",
                    err=True,
                )
                raise typer.Exit(1)

            venv_path = repo_info["path"] / ".venv"
            location_desc = f"repository '{repo}' in group '{group}'"
            recreate_cmd = f"dbx env init -g {group} {repo}"

        elif repo:
            # Remove venv from individual repo directory
            from dbx_python_cli.utils.repo import find_repo_by_name

            repo_info = find_repo_by_name(repo, base_dir, config)
            if not repo_info:
                typer.echo(f"❌ Error: Repository '{repo}' not found", err=True)
                raise typer.Exit(1)

            venv_path = repo_info["path"] / ".venv"
            location_desc = f"repository '{repo}'"
            recreate_cmd = f"dbx env init {repo}"

        elif group:
            # Remove venv from group directory
            if group in global_group_names:
                typer.echo(
                    f"❌ Error: '{group}' is a global group used only for config — it has no group venv.",
                    err=True,
                )
                raise typer.Exit(1)
            if group not in groups:
                typer.echo(
                    f"❌ Error: Group '{group}' not found in configuration.", err=True
                )
                typer.echo(f"Available groups: {', '.join(groups.keys())}", err=True)
                raise typer.Exit(1)

            group_dir = base_dir / group
            if not group_dir.exists():
                typer.echo(
                    f"❌ Error: Group directory '{group_dir}' does not exist.", err=True
                )
                raise typer.Exit(1)

            venv_path = group_dir / ".venv"
            location_desc = f"group '{group}'"
            recreate_cmd = f"dbx env init -g {group}"

        else:
            # Remove venv from base directory (default)
            venv_path = base_dir / ".venv"
            location_desc = "base directory"
            recreate_cmd = "dbx env init"

        # Check if venv exists
        if not venv_path.exists():
            typer.echo(f"No virtual environment found at {venv_path}")
            typer.echo(f"Nothing to remove for {location_desc}.")
            raise typer.Exit(0)

        # Confirm removal unless --force is used
        if not force:
            typer.echo(f"About to remove virtual environment at: {venv_path}")
            confirm = typer.confirm("Are you sure you want to remove this venv?")
            if not confirm:
                typer.echo("Aborted.")
                raise typer.Exit(0)

        # Remove venv
        import shutil

        if verbose:
            typer.echo(f"[verbose] Removing directory: {venv_path}\n")

        shutil.rmtree(venv_path)
        typer.echo(f"✅ Virtual environment removed: {venv_path}")
        typer.echo(f"\nTo recreate: {recreate_cmd}")

    except typer.Exit:
        raise
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)
