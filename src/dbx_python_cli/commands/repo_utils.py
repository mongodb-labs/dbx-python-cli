"""Repository utilities and helper functions."""

import subprocess
import tomllib
from pathlib import Path
from collections import defaultdict

import typer


def get_config_path():
    """Get the path to the user config file."""
    config_dir = Path.home() / ".config" / "dbx-python-cli"
    return config_dir / "config.toml"


def get_default_config_path():
    """Get the path to the default config file shipped with the package."""
    return Path(__file__).parent.parent / "config.toml"


def get_config():
    """Load configuration from user config or default config."""
    user_config_path = get_config_path()
    default_config_path = get_default_config_path()

    # Try user config first
    if user_config_path.exists():
        with open(user_config_path, "rb") as f:
            return tomllib.load(f)

    # Fall back to default config
    if default_config_path.exists():
        with open(default_config_path, "rb") as f:
            return tomllib.load(f)

    # If neither exists, return empty config
    return {}


def get_base_dir(config):
    """Get the base directory for cloning repos."""
    base_dir = config.get("repo", {}).get("base_dir", "~/repos")
    return Path(base_dir).expanduser()


def get_repo_groups(config):
    """Get repository groups from config."""
    return config.get("repo", {}).get("groups", {})


def get_global_groups(config):
    """
    Get the list of global group names from config.

    Repos in global groups are installed into every other group's venv
    automatically when running ``dbx install -g <group>``.

    Returns:
        list: Group names listed under ``repo.global_groups``, or an empty list.
    """
    return config.get("repo", {}).get("global_groups", [])


def get_install_dirs(config, group_name, repo_name):
    """
    Get install directories for a repository.

    For repos with packages in subdirectories, returns a list of subdirectories to install.
    For regular repos, returns None (install from root).

    Args:
        config: Configuration dictionary
        group_name: Name of the group (e.g., 'langchain')
        repo_name: Name of the repository (e.g., 'langchain-mongodb')

    Returns:
        list: List of install directories, or None if packages are at the root
    """
    groups = get_repo_groups(config)
    if group_name not in groups:
        return None

    install_dirs_config = groups[group_name].get("install_dirs", {})
    return install_dirs_config.get(repo_name)


def get_build_commands(config, group_name, repo_name):
    """
    Get build commands for a repository.

    For repos that need a build step before installation (e.g., cmake builds),
    returns a list of shell commands to run.

    Args:
        config: Configuration dictionary
        group_name: Name of the group (e.g., 'django')
        repo_name: Name of the repository (e.g., 'libmongocrypt')

    Returns:
        list: List of build commands, or None if no build needed
    """
    groups = get_repo_groups(config)
    if group_name not in groups:
        return None

    build_commands_config = groups[group_name].get("build_commands", {})
    return build_commands_config.get(repo_name)


def get_test_runner(config, group_name, repo_name):
    """
    Get test runner configuration for a repository.

    Returns the test runner command/script if configured, otherwise None (use pytest).

    Args:
        config: Configuration dictionary
        group_name: Name of the group (e.g., 'django')
        repo_name: Name of the repository (e.g., 'django')

    Returns:
        str: Test runner path/command, or None for default pytest
    """
    groups = get_repo_groups(config)
    if group_name not in groups:
        return None

    test_runner_config = groups[group_name].get("test_runner", {})
    return test_runner_config.get(repo_name)


def get_install_extras(config, group_name, repo_name):
    """
    Get default extras to install for a repository.

    Args:
        config: Configuration dictionary
        group_name: Name of the group (e.g., 'langchain')
        repo_name: Name of the repository (e.g., 'langchain-mongodb')

    Returns:
        list: List of extras to install by default, or empty list
    """
    groups = get_repo_groups(config)
    if group_name not in groups:
        return []

    install_extras_config = groups[group_name].get("install_extras", {})
    return install_extras_config.get(repo_name, [])


def get_install_groups(config, group_name, repo_name):
    """
    Get default dependency groups to install for a repository.

    Args:
        config: Configuration dictionary
        group_name: Name of the group (e.g., 'langchain')
        repo_name: Name of the repository (e.g., 'langchain-mongodb')

    Returns:
        list: List of dependency groups to install by default, or empty list
    """
    groups = get_repo_groups(config)
    if group_name not in groups:
        return []

    install_groups_config = groups[group_name].get("install_groups", {})
    return install_groups_config.get(repo_name, [])


def get_test_runner_args(config, group_name, repo_name):
    """
    Get default arguments for a custom test runner.

    Args:
        config: Configuration dictionary
        group_name: Name of the group (e.g., 'django')
        repo_name: Name of the repository (e.g., 'django')

    Returns:
        list: List of default args to pass to the test runner, or empty list
    """
    groups = get_repo_groups(config)
    if group_name not in groups:
        return []

    test_runner_args_config = groups[group_name].get("test_runner_args", {})
    return test_runner_args_config.get(repo_name, [])


def get_python_version(config, group_name):
    """
    Get the Python version to use for a group's virtual environment.

    When configured, ``dbx clone`` and ``dbx env init`` will use this Python
    version when creating the group's venv.

    Args:
        config: Configuration dictionary
        group_name: Name of the group (e.g., 'django')

    Returns:
        str: Python version string (e.g., '3.12'), or None to use system default
    """
    groups = get_repo_groups(config)
    if group_name not in groups:
        return None

    return groups[group_name].get("python_version")


def get_preferred_branch(config, group_name, repo_name):
    """
    Get the preferred branch to switch to after cloning a repository.

    When configured, ``dbx clone`` will run ``git switch <branch>`` immediately
    after a successful clone, so the working tree starts on the right branch
    without any manual step.

    Args:
        config: Configuration dictionary
        group_name: Name of the group (e.g., 'django')
        repo_name: Name of the repository (e.g., 'django')

    Returns:
        str: Branch name to switch to, or None if no preferred branch is configured
    """
    groups = get_repo_groups(config)
    if group_name not in groups:
        return None

    # Try preferred_branch first (new name), fall back to default_branch (old name) for backwards compatibility
    preferred_branch_config = groups[group_name].get("preferred_branch", {})
    if not preferred_branch_config:
        preferred_branch_config = groups[group_name].get("default_branch", {})
    return preferred_branch_config.get(repo_name)


def switch_to_branch(repo_path: Path, branch_name: str, verbose: bool = False) -> bool:
    """
    Switch to a branch in a cloned repository.

    Runs ``git switch <branch_name>`` in *repo_path*.  Failures are reported as
    warnings rather than hard errors so that the caller's workflow is not
    interrupted.

    Args:
        repo_path: Path to the repository
        branch_name: Branch to switch to
        verbose: Whether to show verbose output

    Returns:
        True if the switch succeeded, False otherwise
    """
    if verbose:
        typer.echo(f"  [verbose] Switching to branch '{branch_name}'")

    try:
        result = subprocess.run(
            ["git", "-C", str(repo_path), "switch", branch_name],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            typer.echo(f"  🔀 Switched to branch '{branch_name}'")
            return True
        else:
            typer.echo(
                f"  ⚠️  Could not switch to branch '{branch_name}': "
                f"{result.stderr.strip() or 'unknown error'}",
                err=True,
            )
            return False
    except Exception as exc:
        typer.echo(
            f"  ⚠️  Could not switch to branch '{branch_name}': {exc}",
            err=True,
        )
        return False


def get_test_env_vars(config, group_name, repo_name, base_dir):
    """
    Get environment variables for test runs.

    Returns a dictionary of environment variables to set when running tests.
    Supports both group-level and repo-specific environment variables.

    When no repo-specific entry is found in the repo's own group, falls back
    to checking global groups (listed under ``repo.global_groups``), so that
    repos cloned from a global group into another group still pick up their
    test environment configuration.

    Args:
        config: Configuration dictionary
        group_name: Name of the group (e.g., 'pymongo')
        repo_name: Name of the repository (e.g., 'mongo-python-driver')
        base_dir: Base directory path for resolving relative paths

    Returns:
        dict: Dictionary of environment variable names to values
    """
    groups = get_repo_groups(config)

    env_vars = {}

    def _collect_env(grp_name):
        """Collect group-level and repo-specific env vars for a given group."""
        if grp_name not in groups:
            return {}
        result = {}
        group_env_config = groups[grp_name].get("test_env", {})
        if isinstance(group_env_config, dict):
            for key, value in group_env_config.items():
                if not isinstance(value, dict):
                    result[key] = _expand_env_var_value(value, base_dir, grp_name)
        repo_env_config = group_env_config.get(repo_name, {})
        if isinstance(repo_env_config, dict):
            for key, value in repo_env_config.items():
                result[key] = _expand_env_var_value(value, base_dir, grp_name)
        return result

    # Collect from the repo's own group first
    env_vars = _collect_env(group_name)

    # If nothing found, fall back to global groups so repos cloned into a
    # different group still pick up their test_env configuration.
    if not env_vars:
        for gname in get_global_groups(config):
            fallback = _collect_env(gname)
            if fallback:
                env_vars = fallback
                break

    return env_vars


def _expand_env_var_value(value, base_dir, group_name):
    """
    Expand special placeholders in environment variable values.

    Supports:
    - {base_dir}: Expands to the base directory path
    - {group}: Expands to the group name
    - ~: Expands to user home directory

    Args:
        value: The environment variable value (string)
        base_dir: Base directory path
        group_name: Name of the group

    Returns:
        str: Expanded value
    """
    if not isinstance(value, str):
        return str(value)

    # Expand placeholders
    expanded = value.replace("{base_dir}", str(base_dir))
    expanded = expanded.replace("{group}", group_name)

    # Expand user home directory
    expanded = str(Path(expanded).expanduser())

    return expanded


def extract_repo_name_from_url(url):
    """
    Extract repository name from a git URL.

    Args:
        url: Git URL (e.g., "git@github.com:mongodb/mongo-python-driver.git")

    Returns:
        str: Repository name (e.g., "mongo-python-driver")
    """
    # Handle both SSH and HTTPS URLs
    # SSH: git@github.com:mongodb/mongo-python-driver.git
    # HTTPS: https://github.com/mongodb/mongo-python-driver.git
    if url.endswith(".git"):
        url = url[:-4]
    return url.split("/")[-1]


def find_all_repos(base_dir):
    """
    Find all cloned repositories in the base directory.

    Args:
        base_dir: Path to the base directory containing group subdirectories

    Returns:
        list: List of dictionaries with 'name', 'path', and 'group' keys
    """
    repos = []
    if not base_dir.exists():
        return repos

    # Look for repos in group subdirectories
    for group_dir in base_dir.iterdir():
        if group_dir.is_dir():
            for repo_dir in group_dir.iterdir():
                if repo_dir.is_dir():
                    # Check if it's a git repo
                    if (repo_dir / ".git").exists():
                        repos.append(
                            {
                                "name": repo_dir.name,
                                "path": repo_dir,
                                "group": group_dir.name,
                            }
                        )
                    # Also check if it's a project (has pyproject.toml but no .git)
                    # This allows projects to be found by install command
                    elif (
                        group_dir.name == "projects"
                        and (repo_dir / "pyproject.toml").exists()
                    ):
                        repos.append(
                            {
                                "name": repo_dir.name,
                                "path": repo_dir,
                                "group": "projects",
                            }
                        )
    return repos


def find_repo_by_name(repo_name, base_dir):
    """
    Find a repository by name in the base directory.

    Args:
        repo_name: Name of the repository to find
        base_dir: Path to the base directory containing group subdirectories

    Returns:
        dict: Dictionary with 'name', 'path', and 'group' keys, or None if not found
    """
    all_repos = find_all_repos(base_dir)
    for repo in all_repos:
        if repo["name"] == repo_name:
            return repo
    return None


def list_repos(base_dir, format_style="default", config=None):
    """
    List all repositories in a formatted way.

    Args:
        base_dir: Path to the base directory containing group subdirectories
        format_style: Output format style ('default', 'tree', 'grouped', or 'simple')
        config: Optional config dict to compare available vs cloned repos

    Returns:
        str: Formatted list of repositories
    """
    repos = find_all_repos(base_dir)

    # If config is provided, get available repos from config
    available_repos = {}
    global_group_names = set()
    global_repo_names = []
    if config:
        groups = config.get("repo", {}).get("groups", {})
        global_group_names = set(get_global_groups(config))

        # Collect repo names from global groups first
        for gname in global_group_names:
            if gname in groups:
                for url in groups[gname].get("repos", []):
                    global_repo_names.append(extract_repo_name_from_url(url))

        # Build available_repos for non-global groups only
        for group_name, group_config in groups.items():
            if group_name in global_group_names:
                # Global groups are not cloned to their own directory — skip them
                continue
            repo_urls = group_config.get("repos", [])
            for url in repo_urls:
                repo_name = extract_repo_name_from_url(url)
                if group_name not in available_repos:
                    available_repos[group_name] = []
                available_repos[group_name].append(repo_name)

        # Inject global repos into every non-global group's available list
        for group_name in available_repos:
            for repo_name in global_repo_names:
                if repo_name not in available_repos[group_name]:
                    available_repos[group_name].append(repo_name)

    # If no repos cloned and no config, return None
    if not repos and not available_repos:
        return None

    if format_style == "tree":
        # Tree format with group as parent
        # Build cloned repos dict
        cloned = defaultdict(list)
        for repo in sorted(repos, key=lambda r: (r["group"], r["name"])):
            cloned[repo["group"]].append(repo["name"])

        # Merge available and cloned groups, excluding global groups
        # (global repos are cloned into target group directories, not their own directory)
        all_groups = (
            set(cloned.keys()) | set(available_repos.keys())
        ) - global_group_names

        lines = []
        sorted_groups = sorted(all_groups)
        for i, group in enumerate(sorted_groups):
            is_last_group = i == len(sorted_groups) - 1
            group_prefix = "└──" if is_last_group else "├──"
            lines.append(f"{group_prefix} {group}/")

            # Get all repos for this group (available and cloned)
            available_in_group = set(available_repos.get(group, []))
            cloned_in_group = set(cloned.get(group, []))
            all_repos_in_group = sorted(available_in_group | cloned_in_group)

            for j, repo_name in enumerate(all_repos_in_group):
                is_last_repo = j == len(all_repos_in_group) - 1
                continuation = "    " if is_last_group else "│   "
                repo_prefix = "└──" if is_last_repo else "├──"

                # Add status indicator if config is provided
                if config:
                    is_cloned = repo_name in cloned_in_group
                    is_available = repo_name in available_in_group
                    if is_cloned and is_available:
                        status = "✓"  # Cloned
                    elif is_cloned and not is_available:
                        status = "?"  # Cloned but not in config
                    else:
                        status = "○"  # Available but not cloned
                    lines.append(f"{continuation}{repo_prefix} {status} {repo_name}")
                else:
                    lines.append(f"{continuation}{repo_prefix} {repo_name}")
        return "\n".join(lines)

    elif format_style == "grouped":
        # Group repos by group name
        grouped = defaultdict(list)
        for repo in sorted(repos, key=lambda r: (r["group"], r["name"])):
            grouped[repo["group"]].append(repo["name"])

        lines = []
        for group in sorted(grouped.keys()):
            lines.append(f"  [{group}]")
            for repo_name in grouped[group]:
                lines.append(f"    • {repo_name}")
        return "\n".join(lines)

    elif format_style == "simple":
        # Simple list with group in parentheses
        lines = []
        for repo in sorted(repos, key=lambda r: (r["group"], r["name"])):
            lines.append(f"  • {repo['name']} ({repo['group']})")
        return "\n".join(lines)

    else:  # default - use tree format
        # Default format: tree structure
        # Build cloned repos dict
        cloned = defaultdict(list)
        for repo in sorted(repos, key=lambda r: (r["group"], r["name"])):
            cloned[repo["group"]].append(repo["name"])

        # Merge available and cloned groups, excluding global groups
        # (global repos are cloned into target group directories, not their own directory)
        all_groups = (
            set(cloned.keys()) | set(available_repos.keys())
        ) - global_group_names

        lines = []
        sorted_groups = sorted(all_groups)
        for i, group in enumerate(sorted_groups):
            is_last_group = i == len(sorted_groups) - 1
            group_prefix = "└──" if is_last_group else "├──"
            group_label = typer.style(f"{group}/", fg=typer.colors.CYAN, bold=True)
            lines.append(f"{group_prefix} {group_label}")

            # Get all repos for this group (available and cloned)
            available_in_group = set(available_repos.get(group, []))
            cloned_in_group = set(cloned.get(group, []))
            all_repos_in_group = sorted(available_in_group | cloned_in_group)

            for j, repo_name in enumerate(all_repos_in_group):
                is_last_repo = j == len(all_repos_in_group) - 1
                continuation = "    " if is_last_group else "│   "
                repo_prefix = "└──" if is_last_repo else "├──"

                # Add status indicator if config is provided
                if config:
                    is_cloned = repo_name in cloned_in_group
                    is_available = repo_name in available_in_group
                    if is_cloned and is_available:
                        status = typer.style("✓", fg=typer.colors.GREEN)
                    elif is_cloned and not is_available:
                        status = typer.style("?", fg=typer.colors.MAGENTA)
                    else:
                        status = typer.style("○", fg=typer.colors.YELLOW)
                    lines.append(f"{continuation}{repo_prefix} {status} {repo_name}")
                else:
                    lines.append(f"{continuation}{repo_prefix} {repo_name}")
        return "\n".join(lines)
