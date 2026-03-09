"""Clone command for cloning repositories."""

import subprocess
from pathlib import Path

import typer

from dbx_python_cli.commands import repo_utils as repo
from dbx_python_cli.commands.repo_utils import switch_to_branch as _switch_to_branch


def auto_install_repo(
    repo_path: Path,
    repo_name: str,
    group_name: str,
    base_dir: Path,
    verbose: bool = False,
):
    """
    Automatically install a cloned repository.

    Args:
        repo_path: Path to the cloned repository
        repo_name: Name of the repository
        group_name: Name of the group the repo belongs to
        base_dir: Path to the base directory
        verbose: Whether to show verbose output
    """
    from dbx_python_cli.commands.install import (
        _effective_install_args,
        install_package,
        run_build_commands,
    )
    from dbx_python_cli.commands.repo_utils import (
        get_build_commands,
        get_install_dirs,
        should_skip_install,
    )
    from dbx_python_cli.commands.venv_utils import get_venv_info

    try:
        config = repo.get_config()

        # Check if this repo should skip installation
        if should_skip_install(config, group_name, repo_name):
            if verbose:
                typer.echo(
                    f"  [verbose] Skipping install for {repo_name} (configured in skip_install)"
                )
            return "skipped"

        # Get venv info - will use base venv if exists, then repo venv, then group venv, otherwise any active venv
        python_path, venv_type = get_venv_info(
            repo_path, repo_path.parent, base_path=base_dir
        )

        if verbose:
            typer.echo(f"  [verbose] Venv type: {venv_type}, Python: {python_path}")

        # Check if this repo needs build commands
        build_commands = get_build_commands(config, group_name, repo_name)
        if build_commands:
            if verbose:
                typer.echo(f"  [verbose] Running build commands for {repo_name}")
            if not run_build_commands(repo_path, build_commands, verbose=verbose):
                typer.echo(
                    f"  ⚠️  Build failed for {repo_name}, skipping install", err=True
                )
                return False

        # Check if this repo has install_dirs (multiple packages in subdirectories)
        install_dirs = get_install_dirs(config, group_name, repo_name)

        # Apply config default extras/groups
        eff_extras, eff_groups = _effective_install_args(
            config, group_name, repo_name, None, None
        )

        if install_dirs:
            # Install from subdirectories
            if verbose:
                typer.echo(
                    f"  [verbose] Installing {len(install_dirs)} package(s) from subdirectories"
                )

            for install_dir in install_dirs:
                result = install_package(
                    repo_path,
                    python_path,
                    install_dir=install_dir,
                    extras=eff_extras,
                    groups=eff_groups,
                    verbose=verbose,
                )
                if result != "success":
                    return False
        else:
            # Regular repo: install from root
            result = install_package(
                repo_path,
                python_path,
                install_dir=None,
                extras=eff_extras,
                groups=eff_groups,
                verbose=verbose,
            )
            if result != "success":
                return False

        return True
    except Exception as e:
        if verbose:
            typer.echo(f"  [verbose] Auto-install failed: {e}", err=True)
        return False


def ensure_group_venv(
    group_dir: Path,
    group_name: str,
    verbose: bool = False,
    python_version: str = None,
) -> bool:
    """
    Ensure a group-level virtual environment exists, creating one if needed.

    Args:
        group_dir: Path to the group directory
        group_name: Name of the group
        verbose: Whether to show verbose output
        python_version: Python version to use (e.g., '3.13'), or None for system default

    Returns:
        True if venv exists or was created successfully, False otherwise
    """
    venv_path = group_dir / ".venv"

    if venv_path.exists():
        typer.echo(f"  🐍 Using existing venv: {venv_path}")
        return True

    if python_version:
        typer.echo(
            f"  🐍 Creating virtual environment for group '{group_name}' (Python {python_version})..."
        )
    else:
        typer.echo(f"  🐍 Creating virtual environment for group '{group_name}'...")

    venv_cmd = ["uv", "venv", str(venv_path), "--no-python-downloads"]
    if python_version:
        venv_cmd.extend(["--python", python_version])

    if verbose:
        typer.echo(f"  [verbose] Running command: {' '.join(venv_cmd)}")
        typer.echo(f"  [verbose] Working directory: {group_dir}")

    result = subprocess.run(
        venv_cmd,
        cwd=str(group_dir),
        check=False,
        capture_output=not verbose,
        text=True,
    )

    if result.returncode != 0:
        typer.echo(
            f"  ⚠️  Failed to create virtual environment for group '{group_name}'",
            err=True,
        )
        if not verbose and result.stderr:
            typer.echo(result.stderr, err=True)
        return False

    typer.echo(f"  ✅ Virtual environment created at {venv_path}")
    return True


app = typer.Typer(
    help="Clone repositories",
    no_args_is_help=True,
    invoke_without_command=True,
    context_settings={
        "allow_interspersed_args": False,
        "help_option_names": ["-h", "--help"],
    },
)


@app.callback()
def clone_callback(
    ctx: typer.Context,
    repo_name: str = typer.Argument(
        None,
        help="Repository name to clone (e.g., django-mongodb-backend)",
    ),
    group: list[str] = typer.Option(
        None,
        "--group",
        "-g",
        help="Repository group(s) to clone (e.g., pymongo, langchain, django). Can be specified multiple times or as comma-separated values.",
    ),
    all_groups: bool = typer.Option(
        False,
        "--all",
        "-a",
        help="Clone all groups from configuration",
    ),
    fork: bool = typer.Option(
        True,
        "--fork",
        help="Clone from your fork instead of upstream (uses fork_user from config)",
    ),
    fork_user: str = typer.Option(
        None,
        "--fork-user",
        help="GitHub username for fork (overrides --fork and config fork_user)",
    ),
    no_install: bool = typer.Option(
        False,
        "--no-install",
        help="Skip automatic installation after cloning",
    ),
):
    """Clone a repository by name, all repositories from one or more groups, or all groups."""
    # Get verbose flag from parent context
    verbose = ctx.obj.get("verbose", False) if ctx.obj else False

    try:
        config = repo.get_config()
        base_dir = repo.get_base_dir(config)
        groups = repo.get_repo_groups(config)

        if verbose:
            typer.echo(f"[verbose] Using base directory: {base_dir}")
            typer.echo(f"[verbose] Available groups: {list(groups.keys())}\n")

        # Handle individual repo clone
        if repo_name:
            # Find the repo in all groups
            found_repo = None
            found_group = None

            for group_name, group_config in groups.items():
                for repo_url in group_config.get("repos", []):
                    # Extract repo name from URL
                    url_repo_name = repo_url.split("/")[-1].replace(".git", "")
                    if url_repo_name == repo_name:
                        found_repo = repo_url
                        found_group = group_name
                        break
                if found_repo:
                    break

            if not found_repo:
                typer.echo(
                    f"❌ Error: Repository '{repo_name}' not found in any group.",
                    err=True,
                )
                typer.echo("\nUse 'dbx list' to see available groups and repositories")
                raise typer.Exit(1)

            # Clone single repo
            repos_to_clone = {found_group: [found_repo]}

            if verbose:
                typer.echo(f"[verbose] Found '{repo_name}' in group '{found_group}'")

        # Handle clone all groups
        elif all_groups:
            repos_to_clone = {}

            # Clone all groups from configuration
            for group_name in groups.keys():
                group_repos = groups[group_name].get("repos", [])
                if group_repos:
                    repos_to_clone[group_name] = group_repos

            if not repos_to_clone:
                typer.echo("❌ Error: No groups found in configuration.", err=True)
                raise typer.Exit(1)

            # Append global-group repos to every non-global group being cloned.
            global_group_names = repo.get_global_groups(config)
            if global_group_names:
                global_urls = []
                for gname in global_group_names:
                    if gname in groups:
                        global_urls.extend(groups[gname].get("repos", []))

                if global_urls:
                    for target_group in list(repos_to_clone.keys()):
                        if target_group not in global_group_names:
                            existing_urls = set(repos_to_clone[target_group])
                            for url in global_urls:
                                if url not in existing_urls:
                                    repos_to_clone[target_group].append(url)
                                    existing_urls.add(url)

        # Handle group clone (can be multiple groups)
        elif group:
            repos_to_clone = {}

            # Parse comma-separated values
            group_names = []
            for g in group:
                # Split by comma and strip whitespace
                group_names.extend(
                    [name.strip() for name in g.split(",") if name.strip()]
                )

            # Validate all groups first
            for group_name in group_names:
                if group_name not in groups:
                    typer.echo(
                        f"❌ Error: Group '{group_name}' not found in configuration.",
                        err=True,
                    )
                    typer.echo(
                        f"Available groups: {', '.join(groups.keys())}", err=True
                    )
                    raise typer.Exit(1)

                group_repos = groups[group_name].get("repos", [])
                if not group_repos:
                    typer.echo(
                        f"❌ Error: No repositories found in group '{group_name}'.",
                        err=True,
                    )
                    raise typer.Exit(1)

                repos_to_clone[group_name] = group_repos

            # Append global-group repos to every non-global group being cloned.
            # This means e.g. `dbx clone -g django` will also clone
            # mongo-python-driver into the django/ directory.
            global_group_names = repo.get_global_groups(config)
            if global_group_names:
                global_urls = []
                for gname in global_group_names:
                    if gname in groups:
                        global_urls.extend(groups[gname].get("repos", []))

                if global_urls:
                    for target_group in list(repos_to_clone.keys()):
                        if target_group not in global_group_names:
                            existing_urls = set(repos_to_clone[target_group])
                            for url in global_urls:
                                if url not in existing_urls:
                                    repos_to_clone[target_group].append(url)
                                    existing_urls.add(url)

        else:
            typer.echo("❌ Error: Repository name or group required", err=True)
            typer.echo("\nUsage: dbx clone <repo-name>")
            typer.echo("   or: dbx clone -g <group>")
            typer.echo("   or: dbx clone -g <group1> -g <group2>")
            typer.echo("   or: dbx clone -g <group1>,<group2>")
            typer.echo("   or: dbx clone -a")
            raise typer.Exit(1)

        # Handle fork options
        effective_fork_user = None
        if fork_user:
            # --fork-user takes precedence
            effective_fork_user = fork_user
        elif fork:
            # --fork flag uses config, falls back to upstream if not set
            effective_fork_user = config.get("repo", {}).get("fork_user")
            if not effective_fork_user:
                typer.echo(
                    "⚠️  Warning: --fork is enabled but fork_user is not set in config",
                    err=True,
                )
                typer.echo(
                    "   Cloning from upstream instead. To use fork workflow, either:",
                    err=True,
                )
                typer.echo(
                    "   1. Set fork_user in config: dbx config set repo.fork_user <your-github-username>",
                    err=True,
                )
                typer.echo(
                    "   2. Use --fork-user flag: dbx clone -g <group> --fork-user <your-github-username>",
                    err=True,
                )
                typer.echo(
                    "   3. Disable fork: dbx clone -g <group> --no-fork\n", err=True
                )

        if effective_fork_user and verbose:
            typer.echo(
                f"[verbose] Using fork workflow with user: {effective_fork_user}\n"
            )

        # Track successfully cloned repos for auto-install
        cloned_repos = []

        # Process each group
        for group_name, repos in repos_to_clone.items():
            # Create group directory under base directory
            group_dir = base_dir / group_name
            group_dir.mkdir(parents=True, exist_ok=True)

            # Display appropriate message
            if len(repos) == 1:
                single_repo_name = repos[0].split("/")[-1].replace(".git", "")
                if effective_fork_user:
                    typer.echo(
                        f"Cloning {single_repo_name} from {effective_fork_user}'s fork to {group_dir}"
                    )
                else:
                    typer.echo(f"Cloning {single_repo_name} to {group_dir}")
            else:
                if effective_fork_user:
                    typer.echo(
                        f"Cloning {len(repos)} repository(ies) from {effective_fork_user}'s forks to {group_dir}"
                    )
                else:
                    typer.echo(
                        f"Cloning {len(repos)} repository(ies) from group '{group_name}' to {group_dir}"
                    )

            for repo_url in repos:
                # Extract repository name from URL
                repo_name = repo_url.split("/")[-1].replace(".git", "")
                repo_path = group_dir / repo_name

                if repo_path.exists():
                    typer.echo(f"  ⏭️  {repo_name} already exists, skipping")
                    preferred_branch = repo.get_preferred_branch(
                        config, group_name, repo_name
                    )
                    if preferred_branch:
                        _switch_to_branch(repo_path, preferred_branch, verbose)
                    continue

                # Determine clone URL and upstream URL
                if effective_fork_user:
                    # Replace the org/user in the URL with the fork user
                    # Handle both SSH and HTTPS URLs
                    clone_url = repo_url
                    upstream_url = repo_url

                    if "git@github.com:" in repo_url:
                        # SSH format: git@github.com:org/repo.git
                        parts = repo_url.split(":")
                        if len(parts) == 2:
                            repo_part = parts[1].split("/", 1)
                            if len(repo_part) == 2:
                                clone_url = f"git@github.com:{effective_fork_user}/{repo_part[1]}"
                    elif "github.com/" in repo_url:
                        # HTTPS format: https://github.com/org/repo.git
                        parts = repo_url.split("github.com/")
                        if len(parts) == 2:
                            repo_part = parts[1].split("/", 1)
                            if len(repo_part) == 2:
                                clone_url = f"{parts[0]}github.com/{effective_fork_user}/{repo_part[1]}"
                else:
                    clone_url = repo_url
                    upstream_url = None

                typer.echo(f"  📦 Cloning {repo_name}...")
                if verbose:
                    typer.echo(f"  [verbose] Clone URL: {clone_url}")
                    if effective_fork_user:
                        typer.echo(f"  [verbose] Upstream URL: {upstream_url}")
                    typer.echo(f"  [verbose] Destination: {repo_path}")

                clone_success = False
                try:
                    # Clone the repository
                    subprocess.run(
                        ["git", "clone", clone_url, str(repo_path)],
                        check=True,
                        capture_output=not verbose,
                        text=True,
                    )
                    clone_success = True

                    # If using fork workflow, add upstream remote
                    if effective_fork_user:
                        subprocess.run(
                            [
                                "git",
                                "-C",
                                str(repo_path),
                                "remote",
                                "add",
                                "upstream",
                                upstream_url,
                            ],
                            check=True,
                            capture_output=True,
                            text=True,
                        )

                        # Fetch upstream to compare commits
                        try:
                            subprocess.run(
                                ["git", "-C", str(repo_path), "fetch", "upstream"],
                                check=True,
                                capture_output=True,
                                text=True,
                            )

                            # Get the default branch name from upstream
                            result = subprocess.run(
                                [
                                    "git",
                                    "-C",
                                    str(repo_path),
                                    "symbolic-ref",
                                    "refs/remotes/upstream/HEAD",
                                ],
                                capture_output=True,
                                text=True,
                            )

                            if result and result.returncode == 0:
                                upstream_branch = result.stdout.strip().split("/")[-1]
                            else:
                                # Fallback to main/master
                                upstream_branch = "main"

                            # Count commits ahead
                            result = subprocess.run(
                                [
                                    "git",
                                    "-C",
                                    str(repo_path),
                                    "rev-list",
                                    "--count",
                                    f"upstream/{upstream_branch}..HEAD",
                                ],
                                capture_output=True,
                                text=True,
                            )

                            if result and result.returncode == 0:
                                commits_ahead = int(result.stdout.strip())
                                if commits_ahead > 0:
                                    typer.echo(
                                        f"  ✅ {repo_name} cloned from fork (upstream remote added, {commits_ahead} commit{'s' if commits_ahead != 1 else ''} ahead)"
                                    )
                                else:
                                    typer.echo(
                                        f"  ✅ {repo_name} cloned from fork (upstream remote added, up to date)"
                                    )
                            else:
                                typer.echo(
                                    f"  ✅ {repo_name} cloned from fork (upstream remote added)"
                                )
                        except (subprocess.CalledProcessError, AttributeError):
                            # If fetch or comparison fails, just show basic message
                            typer.echo(
                                f"  ✅ {repo_name} cloned from fork (upstream remote added)"
                            )
                    else:
                        typer.echo(f"  ✅ {repo_name} cloned successfully")

                    # Switch to preferred branch if configured
                    if clone_success:
                        preferred_branch = repo.get_preferred_branch(
                            config, group_name, repo_name
                        )
                        if verbose:
                            typer.echo(
                                f"  [verbose] Preferred branch for {repo_name}: {preferred_branch}"
                            )
                        if preferred_branch:
                            _switch_to_branch(repo_path, preferred_branch, verbose)

                    # Track successful clone for auto-install
                    if clone_success:
                        cloned_repos.append(
                            {
                                "name": repo_name,
                                "path": repo_path,
                                "group": group_name,
                            }
                        )

                except subprocess.CalledProcessError as e:
                    # If fork clone failed, try falling back to upstream
                    if effective_fork_user and upstream_url:
                        if verbose:
                            typer.echo(
                                "  [verbose] Fork clone failed, falling back to upstream"
                            )
                        try:
                            subprocess.run(
                                ["git", "clone", upstream_url, str(repo_path)],
                                check=True,
                                capture_output=not verbose,
                                text=True,
                            )
                            typer.echo(
                                f"  ✅ {repo_name} cloned from upstream (fork not found)"
                            )

                            # Switch to preferred branch if configured
                            preferred_branch = repo.get_preferred_branch(
                                config, group_name, repo_name
                            )
                            if verbose:
                                typer.echo(
                                    f"  [verbose] Preferred branch for {repo_name}: {preferred_branch}"
                                )
                            if preferred_branch:
                                _switch_to_branch(repo_path, preferred_branch, verbose)

                            # Track successful clone from upstream fallback
                            cloned_repos.append(
                                {
                                    "name": repo_name,
                                    "path": repo_path,
                                    "group": group_name,
                                }
                            )
                        except subprocess.CalledProcessError as upstream_error:
                            typer.echo(
                                f"  ❌ Failed to clone {repo_name}: {upstream_error.stderr if not verbose else ''}",
                                err=True,
                            )
                    else:
                        typer.echo(
                            f"  ❌ Failed to clone {repo_name}: {e.stderr if not verbose else ''}",
                            err=True,
                        )

            typer.echo(f"\n✨ Done! Repositories cloned to {group_dir}")

        # Final summary message
        total_groups = len(repos_to_clone)
        if total_groups > 1:
            typer.echo(
                f"\n🎉 All done! Cloned repositories from {total_groups} groups."
            )

        # Auto-install cloned repositories unless --no-install is specified
        if not no_install and cloned_repos:
            typer.echo("\n📦 Installing cloned repositories...")

            # Ensure each group has a venv before installing
            unique_groups: dict[str, Path] = {}
            for repo_info in cloned_repos:
                gname = repo_info["group"]
                if gname not in unique_groups:
                    unique_groups[gname] = base_dir / gname

            for gname, gdir in unique_groups.items():
                python_version = repo.get_python_version(config, gname)
                ensure_group_venv(
                    gdir, gname, verbose=verbose, python_version=python_version
                )

            installed_count = 0
            skipped_count = 0

            for repo_info in cloned_repos:
                if verbose:
                    typer.echo(f"\n  Installing {repo_info['name']}...")
                else:
                    typer.echo(f"  📦 Installing {repo_info['name']}...")

                result = auto_install_repo(
                    repo_info["path"],
                    repo_info["name"],
                    repo_info["group"],
                    base_dir,
                    verbose=verbose,
                )

                if result == "skipped":
                    typer.echo(
                        f"  ⏭️  {repo_info['name']} skipped (configured in skip_install)"
                    )
                    skipped_count += 1
                elif result:
                    typer.echo(f"  ✅ {repo_info['name']} installed successfully")
                    installed_count += 1
                else:
                    if verbose:
                        typer.echo(f"  ⏭️  {repo_info['name']} skipped (install failed)")
                    skipped_count += 1

                # Run prek install if .pre-commit-config.yaml exists
                if (repo_info["path"] / ".pre-commit-config.yaml").exists():
                    typer.echo(f"  🪝 Running prek install for {repo_info['name']}...")
                    prek_result = subprocess.run(
                        ["prek", "install"],
                        cwd=str(repo_info["path"]),
                        check=False,
                        capture_output=not verbose,
                        text=True,
                    )
                    if prek_result.returncode == 0:
                        typer.echo(
                            f"  ✅ Pre-commit hooks installed for {repo_info['name']}"
                        )
                    else:
                        typer.echo(
                            f"  ⚠️  prek install failed for {repo_info['name']}",
                            err=True,
                        )
                        if not verbose and prek_result.stderr:
                            typer.echo(prek_result.stderr, err=True)

            if installed_count > 0:
                typer.echo(f"\n✨ Installed {installed_count} repository(ies)")
            if skipped_count > 0:
                typer.echo(f"⏭️  Skipped {skipped_count} repository(ies)")
                typer.echo(
                    "\nTip: Run 'dbx install <repo>' to install skipped repositories manually"
                )

    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)
