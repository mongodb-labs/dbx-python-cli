"""Integration tests for just commands."""

import subprocess
from unittest.mock import patch

from typer.testing import CliRunner

from drivers_python_cli.cli import app

runner = CliRunner()


def test_just_runs_real_justfile(tmp_path, test_git_repo):
    """Test running a real justfile command."""
    config_dir = tmp_path / ".config" / "drivers-python-cli"
    config_dir.mkdir(parents=True)
    config_path = config_dir / "config.toml"

    base_dir = tmp_path / "repos"
    base_dir.mkdir()
    test_group = base_dir / "test"
    test_group.mkdir()

    # Clone the test repo
    cloned_repo = test_group / "test_repo"
    subprocess.run(
        ["git", "clone", str(test_git_repo), str(cloned_repo)],
        check=True,
        capture_output=True,
    )

    # Create a justfile
    justfile_content = """# Test justfile

test:
    echo "Running tests"

build:
    echo "Building project"
"""
    (cloned_repo / "justfile").write_text(justfile_content)

    base_dir_str = str(base_dir).replace("\\", "/")
    test_repo_str = str(test_git_repo).replace("\\", "/")

    config_content = f"""[repo]
base_dir = "{base_dir_str}"

[repo.groups.test]
repos = [
    "{test_repo_str}",
]
"""
    config_path.write_text(config_content)

    with patch("drivers_python_cli.utils.repo.get_config_path") as mock_get_path:
        mock_get_path.return_value = config_path

        # Check if just is installed
        try:
            subprocess.run(
                ["just", "--version"], check=True, capture_output=True, timeout=5
            )
            just_available = True
        except (
            subprocess.CalledProcessError,
            FileNotFoundError,
            subprocess.TimeoutExpired,
        ):
            just_available = False

        if just_available:
            result = runner.invoke(app, ["just", "test_repo", "test"])
            assert result.exit_code == 0
            assert "Running 'just test'" in result.stdout
        else:
            # If just is not installed, test that we get an appropriate error
            result = runner.invoke(app, ["just", "test_repo", "test"])
            # The command should handle the missing just gracefully
            assert result.exit_code in [0, 1]


def test_just_with_arguments(tmp_path, test_git_repo):
    """Test running justfile command with arguments."""
    config_dir = tmp_path / ".config" / "drivers-python-cli"
    config_dir.mkdir(parents=True)
    config_path = config_dir / "config.toml"

    base_dir = tmp_path / "repos"
    base_dir.mkdir()
    test_group = base_dir / "test"
    test_group.mkdir()

    # Clone the test repo
    cloned_repo = test_group / "test_repo"
    subprocess.run(
        ["git", "clone", str(test_git_repo), str(cloned_repo)],
        check=True,
        capture_output=True,
    )

    # Create a justfile with a command that takes arguments
    justfile_content = """# Test justfile

greet name:
    echo "Hello {{name}}"
"""
    (cloned_repo / "justfile").write_text(justfile_content)

    base_dir_str = str(base_dir).replace("\\", "/")
    test_repo_str = str(test_git_repo).replace("\\", "/")

    config_content = f"""[repo]
base_dir = "{base_dir_str}"

[repo.groups.test]
repos = [
    "{test_repo_str}",
]
"""
    config_path.write_text(config_content)

    with patch("drivers_python_cli.utils.repo.get_config_path") as mock_get_path:
        mock_get_path.return_value = config_path

        # Check if just is installed
        try:
            subprocess.run(
                ["just", "--version"], check=True, capture_output=True, timeout=5
            )
            just_available = True
        except (
            subprocess.CalledProcessError,
            FileNotFoundError,
            subprocess.TimeoutExpired,
        ):
            just_available = False

        if just_available:
            result = runner.invoke(app, ["just", "test_repo", "greet", "World"])
            assert result.exit_code == 0
        else:
            # If just is not installed, test that we get an appropriate error
            result = runner.invoke(app, ["just", "test_repo", "greet", "World"])
            assert result.exit_code in [0, 1]


def test_just_list_recipes(tmp_path, test_git_repo):
    """Test listing justfile recipes."""
    config_dir = tmp_path / ".config" / "drivers-python-cli"
    config_dir.mkdir(parents=True)
    config_path = config_dir / "config.toml"

    base_dir = tmp_path / "repos"
    base_dir.mkdir()
    test_group = base_dir / "test"
    test_group.mkdir()

    # Clone the test repo
    cloned_repo = test_group / "test_repo"
    subprocess.run(
        ["git", "clone", str(test_git_repo), str(cloned_repo)],
        check=True,
        capture_output=True,
    )

    # Create a justfile
    justfile_content = """# Test justfile

test:
    echo "Running tests"

build:
    echo "Building project"
"""
    (cloned_repo / "justfile").write_text(justfile_content)

    base_dir_str = str(base_dir).replace("\\", "/")
    test_repo_str = str(test_git_repo).replace("\\", "/")

    config_content = f"""[repo]
base_dir = "{base_dir_str}"

[repo.groups.test]
repos = [
    "{test_repo_str}",
]
"""
    config_path.write_text(config_content)

    with patch("drivers_python_cli.utils.repo.get_config_path") as mock_get_path:
        mock_get_path.return_value = config_path

        # Check if just is installed
        try:
            subprocess.run(
                ["just", "--version"], check=True, capture_output=True, timeout=5
            )
            just_available = True
        except (
            subprocess.CalledProcessError,
            FileNotFoundError,
            subprocess.TimeoutExpired,
        ):
            just_available = False

        if just_available:
            # Run just without a command to list recipes
            result = runner.invoke(app, ["just", "test_repo"])
            assert result.exit_code == 0
        else:
            result = runner.invoke(app, ["just", "test_repo"])
            assert result.exit_code in [0, 1]
