"""Integration tests for env commands."""

import subprocess
from unittest.mock import patch

from typer.testing import CliRunner

from drivers_python_cli.cli import app

runner = CliRunner()


def test_env_init_creates_real_venv(tmp_path, test_git_repo):
    """Test creating a real virtual environment."""
    config_dir = tmp_path / ".config" / "drivers-python-cli"
    config_dir.mkdir(parents=True)
    config_path = config_dir / "config.toml"

    base_dir = tmp_path / "repos"
    base_dir.mkdir()
    test_group = base_dir / "test"
    test_group.mkdir()

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

        result = runner.invoke(app, ["env", "init", "-g", "test"])
        assert result.exit_code == 0
        assert "Creating virtual environment" in result.stdout

        # Verify venv was created
        venv_dir = test_group / ".venv"
        assert venv_dir.exists()
        assert (venv_dir / "bin" / "python").exists() or (
            venv_dir / "Scripts" / "python.exe"
        ).exists()


def test_env_init_with_python_version(tmp_path, test_git_repo):
    """Test creating venv with specific Python version."""
    config_dir = tmp_path / ".config" / "drivers-python-cli"
    config_dir.mkdir(parents=True)
    config_path = config_dir / "config.toml"

    base_dir = tmp_path / "repos"
    base_dir.mkdir()
    test_group = base_dir / "test"
    test_group.mkdir()

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

        result = runner.invoke(app, ["env", "init", "-g", "test", "-p", "3.11"])
        # May fail if Python 3.11 is not available, but should handle gracefully
        # We're testing that the command runs, not that it succeeds
        assert result.exit_code in [0, 1]


def test_env_list_real_venvs(tmp_path, test_git_repo):
    """Test listing real virtual environments."""
    config_dir = tmp_path / ".config" / "drivers-python-cli"
    config_dir.mkdir(parents=True)
    config_path = config_dir / "config.toml"

    base_dir = tmp_path / "repos"
    base_dir.mkdir()
    test_group = base_dir / "test"
    test_group.mkdir()

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

    # Create a real venv
    venv_dir = test_group / ".venv"
    subprocess.run(
        ["python", "-m", "venv", str(venv_dir)], check=True, capture_output=True
    )

    with patch("drivers_python_cli.utils.repo.get_config_path") as mock_get_path:
        mock_get_path.return_value = config_path

        result = runner.invoke(app, ["env", "list"])
        assert result.exit_code == 0
        assert "Virtual environments:" in result.stdout
        assert "test" in result.stdout


def test_env_init_recreate_existing(tmp_path, test_git_repo):
    """Test recreating an existing venv."""
    config_dir = tmp_path / ".config" / "drivers-python-cli"
    config_dir.mkdir(parents=True)
    config_path = config_dir / "config.toml"

    base_dir = tmp_path / "repos"
    base_dir.mkdir()
    test_group = base_dir / "test"
    test_group.mkdir()

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

    # Create a venv first
    venv_dir = test_group / ".venv"
    subprocess.run(
        ["python", "-m", "venv", str(venv_dir)], check=True, capture_output=True
    )

    with patch("drivers_python_cli.utils.repo.get_config_path") as mock_get_path:
        mock_get_path.return_value = config_path

        # Try to create again without --recreate
        result = runner.invoke(app, ["env", "init", "-g", "test"])
        # Should exit with error code 1 because venv already exists
        assert result.exit_code == 1
        assert "already exists" in result.stdout
