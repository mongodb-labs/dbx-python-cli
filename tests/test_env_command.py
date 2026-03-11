"""Tests for the env command module."""

from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from dbx_python_cli.cli import app

runner = CliRunner()


@pytest.fixture
def temp_config_dir(tmp_path):
    """Create a temporary config directory."""
    config_dir = tmp_path / ".config" / "dbx-python-cli"
    config_dir.mkdir(parents=True)
    return config_dir


@pytest.fixture
def temp_repos_dir(tmp_path):
    """Create a temporary repos directory."""
    repos_dir = tmp_path / "repos"
    repos_dir.mkdir(parents=True)
    return repos_dir


@pytest.fixture
def mock_config(temp_config_dir, temp_repos_dir):
    """Create a mock config file."""
    config_path = temp_config_dir / "config.toml"
    # Convert path to use forward slashes for TOML compatibility on Windows
    repos_dir_str = str(temp_repos_dir).replace("\\", "/")
    config_content = f"""
[repo]
base_dir = "{repos_dir_str}"

[repo.groups.pymongo]
repos = [
    "git@github.com:mongodb/mongo-python-driver.git",
]

[repo.groups.langchain]
repos = [
    "git@github.com:langchain-ai/langchain-mongodb.git",
]
"""
    config_path.write_text(config_content)
    return config_path


def test_env_help():
    """Test that the env help command works."""
    result = runner.invoke(app, ["env", "--help"])
    assert result.exit_code == 0
    assert "Virtual environment management commands" in result.stdout


def test_env_init_list_groups(mock_config, temp_repos_dir):
    """Test that env init --list shows available groups."""
    with patch("dbx_python_cli.utils.repo.get_config_path") as mock_get_path:
        mock_get_path.return_value = mock_config

        # Create one group directory with venv
        pymongo_dir = temp_repos_dir / "pymongo"
        pymongo_dir.mkdir(parents=True)
        venv_dir = pymongo_dir / ".venv"
        venv_dir.mkdir()

        result = runner.invoke(app, ["env", "init", "--list"])
        assert result.exit_code == 0
        assert "Available groups:" in result.stdout
        assert "pymongo" in result.stdout
        assert "venv exists" in result.stdout
        assert "langchain" in result.stdout
        assert "no venv" in result.stdout


def test_env_init_list_groups_short_form(mock_config):
    """Test that env init -l works as shortcut for --list."""
    with patch("dbx_python_cli.utils.repo.get_config_path") as mock_get_path:
        mock_get_path.return_value = mock_config

        result = runner.invoke(app, ["env", "init", "-l"])
        assert result.exit_code == 0
        assert "Available groups:" in result.stdout
        assert "pymongo" in result.stdout
        assert "langchain" in result.stdout


def test_env_init_no_group_shows_error(mock_config, temp_repos_dir):
    """Test that env init without arguments creates base dir venv."""
    with patch("dbx_python_cli.utils.repo.get_config_path") as mock_get_path:
        with patch("subprocess.run") as mock_run:
            mock_get_path.return_value = mock_config
            mock_run.return_value.returncode = 0

            result = runner.invoke(app, ["env", "init"])
            assert result.exit_code == 0
            assert "Creating virtual environment" in result.stdout
            assert "Virtual environment created" in result.stdout


def test_env_init_invalid_group(mock_config):
    """Test that env init with invalid group shows error."""
    with patch("dbx_python_cli.utils.repo.get_config_path") as mock_get_path:
        mock_get_path.return_value = mock_config

        result = runner.invoke(app, ["env", "init", "-g", "nonexistent"])
        assert result.exit_code == 1
        output = result.stdout + result.stderr
        assert "not found in configuration" in output


def test_env_init_group_dir_not_exists(mock_config, temp_repos_dir):
    """Test that env init creates group directory if it doesn't exist."""
    with patch("dbx_python_cli.utils.repo.get_config_path") as mock_get_path:
        with patch("subprocess.run") as mock_run:
            mock_get_path.return_value = mock_config
            mock_run.return_value.returncode = 0

            # Group directory doesn't exist yet
            pymongo_dir = temp_repos_dir / "pymongo"
            assert not pymongo_dir.exists()

            result = runner.invoke(app, ["env", "init", "-g", "pymongo"])
            assert result.exit_code == 0
            assert "Creating virtual environment" in result.stdout
            assert "Virtual environment created" in result.stdout

            # Verify directory was created
            assert pymongo_dir.exists()


def test_env_init_creates_venv(mock_config, temp_repos_dir):
    """Test that env init creates a virtual environment."""
    with patch("dbx_python_cli.utils.repo.get_config_path") as mock_get_path:
        with patch("subprocess.run") as mock_run:
            mock_get_path.return_value = mock_config
            mock_run.return_value.returncode = 0

            # Create group directory
            pymongo_dir = temp_repos_dir / "pymongo"
            pymongo_dir.mkdir(parents=True)

            result = runner.invoke(app, ["env", "init", "-g", "pymongo"])
            assert result.exit_code == 0
            assert "Creating virtual environment" in result.stdout
            assert "Virtual environment created" in result.stdout

            # Verify uv venv was called
            mock_run.assert_called_once()
            call_args = mock_run.call_args[0][0]
            assert call_args[0] == "uv"
            assert call_args[1] == "venv"


def test_env_init_with_python_version(mock_config, temp_repos_dir):
    """Test that env init accepts python version."""
    with patch("dbx_python_cli.utils.repo.get_config_path") as mock_get_path:
        with patch("subprocess.run") as mock_run:
            mock_get_path.return_value = mock_config
            mock_run.return_value.returncode = 0

            # Create group directory
            pymongo_dir = temp_repos_dir / "pymongo"
            pymongo_dir.mkdir(parents=True)

            result = runner.invoke(app, ["env", "init", "-g", "pymongo", "-p", "3.11"])
            assert result.exit_code == 0

            # Verify python version was passed
            call_args = mock_run.call_args[0][0]
            assert "--python" in call_args
            assert "3.11" in call_args


def test_env_init_venv_exists_no_overwrite(mock_config, temp_repos_dir):
    """Test that env init doesn't overwrite existing venv without confirmation."""
    with patch("dbx_python_cli.utils.repo.get_config_path") as mock_get_path:
        mock_get_path.return_value = mock_config

        # Create group directory with existing venv
        pymongo_dir = temp_repos_dir / "pymongo"
        pymongo_dir.mkdir(parents=True)
        venv_dir = pymongo_dir / ".venv"
        venv_dir.mkdir()

        # Simulate user saying "no" to overwrite
        result = runner.invoke(app, ["env", "init", "-g", "pymongo"], input="n\n")
        assert result.exit_code == 0
        assert "already exists" in result.stdout
        assert "Aborted" in result.stdout


def test_env_init_venv_exists_with_overwrite(mock_config, temp_repos_dir):
    """Test that env init overwrites existing venv with confirmation."""
    with patch("dbx_python_cli.utils.repo.get_config_path") as mock_get_path:
        with patch("subprocess.run") as mock_run:
            mock_get_path.return_value = mock_config
            mock_run.return_value.returncode = 0

            # Create group directory with existing venv
            pymongo_dir = temp_repos_dir / "pymongo"
            pymongo_dir.mkdir(parents=True)
            venv_dir = pymongo_dir / ".venv"
            venv_dir.mkdir()
            (venv_dir / "test_file").write_text("test")

            # Simulate user saying "yes" to overwrite
            result = runner.invoke(app, ["env", "init", "-g", "pymongo"], input="y\n")
            assert result.exit_code == 0
            assert "Virtual environment created" in result.stdout


def test_env_init_creation_failure(mock_config, temp_repos_dir):
    """Test that env init handles venv creation failure."""
    with patch("dbx_python_cli.utils.repo.get_config_path") as mock_get_path:
        with patch("subprocess.run") as mock_run:
            mock_get_path.return_value = mock_config
            mock_run.return_value.returncode = 1
            mock_run.return_value.stderr = "Error creating venv"

            # Create group directory
            pymongo_dir = temp_repos_dir / "pymongo"
            pymongo_dir.mkdir(parents=True)

            result = runner.invoke(app, ["env", "init", "-g", "pymongo"])
            assert result.exit_code == 1
            output = result.stdout + result.stderr
            assert "Failed to create virtual environment" in output


def test_env_list_no_venvs(mock_config, temp_repos_dir):
    """Test env list when no venvs exist."""
    with patch("dbx_python_cli.utils.repo.get_config_path") as mock_get_path:
        mock_get_path.return_value = mock_config

        # Create group directories without venvs
        (temp_repos_dir / "pymongo").mkdir(parents=True)
        (temp_repos_dir / "langchain").mkdir(parents=True)

        result = runner.invoke(app, ["env", "list"])
        assert result.exit_code == 0
        assert "Virtual environments:" in result.stdout
        assert "No virtual environments found" in result.stdout


def test_env_list_with_venvs(mock_config, temp_repos_dir):
    """Test env list when venvs exist."""
    with patch("dbx_python_cli.utils.repo.get_config_path") as mock_get_path:
        with patch("subprocess.run") as mock_run:
            mock_get_path.return_value = mock_config
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "Python 3.11.0"

            # Create group directories with venvs
            pymongo_dir = temp_repos_dir / "pymongo"
            pymongo_dir.mkdir(parents=True)
            venv_dir = pymongo_dir / ".venv" / "bin"
            venv_dir.mkdir(parents=True)
            (venv_dir / "python").write_text("#!/usr/bin/env python3\n")

            result = runner.invoke(app, ["env", "list"])
            assert result.exit_code == 0
            assert "Virtual environments:" in result.stdout
            assert "pymongo" in result.stdout
            assert "Python 3.11.0" in result.stdout


def test_env_list_mixed_venvs(mock_config, temp_repos_dir):
    """Test env list with some groups having venvs and some not."""
    with patch("dbx_python_cli.utils.repo.get_config_path") as mock_get_path:
        with patch("subprocess.run") as mock_run:
            mock_get_path.return_value = mock_config
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "Python 3.11.0"

            # Create pymongo with venv
            pymongo_dir = temp_repos_dir / "pymongo"
            pymongo_dir.mkdir(parents=True)
            venv_dir = pymongo_dir / ".venv" / "bin"
            venv_dir.mkdir(parents=True)
            (venv_dir / "python").write_text("#!/usr/bin/env python3\n")

            # Create langchain without venv
            (temp_repos_dir / "langchain").mkdir(parents=True)

            result = runner.invoke(app, ["env", "list"])
            assert result.exit_code == 0
            assert "pymongo" in result.stdout
            assert "langchain" in result.stdout
            assert "No venv" in result.stdout


def test_env_list_invalid_venv(mock_config, temp_repos_dir):
    """Test env list with invalid venv (missing python)."""
    with patch("dbx_python_cli.utils.repo.get_config_path") as mock_get_path:
        mock_get_path.return_value = mock_config

        # Create group directory with venv but no python executable
        pymongo_dir = temp_repos_dir / "pymongo"
        pymongo_dir.mkdir(parents=True)
        venv_dir = pymongo_dir / ".venv"
        venv_dir.mkdir()

        result = runner.invoke(app, ["env", "list"])
        assert result.exit_code == 0
        assert "pymongo" in result.stdout
        assert "invalid" in result.stdout


def test_env_remove_list_groups(mock_config, temp_repos_dir):
    """Test env remove --list shows available groups."""
    with patch("dbx_python_cli.utils.repo.get_config_path") as mock_get_path:
        mock_get_path.return_value = mock_config

        # Create group directories
        (temp_repos_dir / "pymongo").mkdir(parents=True)
        (temp_repos_dir / "langchain").mkdir(parents=True)

        result = runner.invoke(app, ["env", "remove", "--list"])
        assert result.exit_code == 0
        assert "Available groups:" in result.stdout
        assert "pymongo" in result.stdout
        assert "langchain" in result.stdout


def test_env_remove_no_group_shows_error(mock_config, temp_repos_dir):
    """Test env remove without arguments removes base dir venv."""
    with patch("dbx_python_cli.utils.repo.get_config_path") as mock_get_path:
        mock_get_path.return_value = mock_config

        # Create base dir venv
        venv_dir = temp_repos_dir / ".venv"
        venv_dir.mkdir()

        # Simulate user saying "yes" to remove
        result = runner.invoke(app, ["env", "remove"], input="y\n")
        assert result.exit_code == 0
        assert "Virtual environment removed" in result.stdout
        assert not venv_dir.exists()


def test_env_remove_invalid_group(mock_config):
    """Test env remove with invalid group shows error."""
    with patch("dbx_python_cli.utils.repo.get_config_path") as mock_get_path:
        mock_get_path.return_value = mock_config

        result = runner.invoke(app, ["env", "remove", "-g", "invalid"])
        assert result.exit_code == 1
        output = result.stdout + result.stderr
        assert "not found in configuration" in output


def test_env_remove_group_dir_not_exists(mock_config, temp_repos_dir):
    """Test env remove when group directory doesn't exist."""
    with patch("dbx_python_cli.utils.repo.get_config_path") as mock_get_path:
        mock_get_path.return_value = mock_config

        result = runner.invoke(app, ["env", "remove", "-g", "pymongo"])
        assert result.exit_code == 1
        output = result.stdout + result.stderr
        assert "does not exist" in output


def test_env_remove_no_venv_exists(mock_config, temp_repos_dir):
    """Test env remove when no venv exists."""
    with patch("dbx_python_cli.utils.repo.get_config_path") as mock_get_path:
        mock_get_path.return_value = mock_config

        # Create group directory without venv
        pymongo_dir = temp_repos_dir / "pymongo"
        pymongo_dir.mkdir(parents=True)

        result = runner.invoke(app, ["env", "remove", "-g", "pymongo"])
        assert result.exit_code == 0
        assert "No virtual environment found" in result.stdout
        assert "Nothing to remove" in result.stdout


def test_env_remove_with_confirmation_yes(mock_config, temp_repos_dir):
    """Test env remove with user confirming yes."""
    with patch("dbx_python_cli.utils.repo.get_config_path") as mock_get_path:
        mock_get_path.return_value = mock_config

        # Create group directory with venv
        pymongo_dir = temp_repos_dir / "pymongo"
        pymongo_dir.mkdir(parents=True)
        venv_dir = pymongo_dir / ".venv"
        venv_dir.mkdir()

        # Simulate user saying "yes" to remove
        result = runner.invoke(app, ["env", "remove", "-g", "pymongo"], input="y\n")
        assert result.exit_code == 0
        assert "Virtual environment removed" in result.stdout
        assert not venv_dir.exists()


def test_env_remove_with_confirmation_no(mock_config, temp_repos_dir):
    """Test env remove with user declining."""
    with patch("dbx_python_cli.utils.repo.get_config_path") as mock_get_path:
        mock_get_path.return_value = mock_config

        # Create group directory with venv
        pymongo_dir = temp_repos_dir / "pymongo"
        pymongo_dir.mkdir(parents=True)
        venv_dir = pymongo_dir / ".venv"
        venv_dir.mkdir()

        # Simulate user saying "no" to remove
        result = runner.invoke(app, ["env", "remove", "-g", "pymongo"], input="n\n")
        assert result.exit_code == 0
        assert "Aborted" in result.stdout
        assert venv_dir.exists()


def test_env_remove_with_force_flag(mock_config, temp_repos_dir):
    """Test env remove with --force flag skips confirmation."""
    with patch("dbx_python_cli.utils.repo.get_config_path") as mock_get_path:
        mock_get_path.return_value = mock_config

        # Create group directory with venv
        pymongo_dir = temp_repos_dir / "pymongo"
        pymongo_dir.mkdir(parents=True)
        venv_dir = pymongo_dir / ".venv"
        venv_dir.mkdir()

        result = runner.invoke(app, ["env", "remove", "-g", "pymongo", "--force"])
        assert result.exit_code == 0
        assert "Virtual environment removed" in result.stdout
        assert not venv_dir.exists()


def test_env_init_repo_with_group(temp_repos_dir, mock_config):
    """Test env init with both repo and group specified."""
    with patch("dbx_python_cli.utils.repo.get_config_path") as mock_get_path:
        mock_get_path.return_value = mock_config

        # Create group directory and repo
        pymongo_dir = temp_repos_dir / "pymongo"
        pymongo_dir.mkdir(parents=True)
        repo_dir = pymongo_dir / "mongo-python-driver"
        repo_dir.mkdir()
        (repo_dir / ".git").mkdir()

        # Mock subprocess.run to simulate successful venv creation
        with patch("subprocess.run") as mock_run:
            # Create the .venv directory to simulate successful creation
            def create_venv(*args, **kwargs):
                venv_path = repo_dir / ".venv"
                venv_path.mkdir(exist_ok=True)
                return type("obj", (object,), {"returncode": 0})()

            mock_run.side_effect = create_venv

            result = runner.invoke(
                app, ["env", "init", "-g", "pymongo", "mongo-python-driver"]
            )
            assert result.exit_code == 0
            assert "Creating virtual environment" in result.stdout
            assert (
                "repository 'mongo-python-driver' in group 'pymongo'" in result.stdout
            )
            # Verify venv was created in the repo directory
            assert (repo_dir / ".venv").exists()


def test_env_remove_repo_with_group(temp_repos_dir, mock_config):
    """Test env remove with both repo and group specified."""
    with patch("dbx_python_cli.utils.repo.get_config_path") as mock_get_path:
        mock_get_path.return_value = mock_config

        # Create group directory, repo, and venv
        pymongo_dir = temp_repos_dir / "pymongo"
        pymongo_dir.mkdir(parents=True)
        repo_dir = pymongo_dir / "mongo-python-driver"
        repo_dir.mkdir()
        (repo_dir / ".git").mkdir()
        venv_dir = repo_dir / ".venv"
        venv_dir.mkdir()

        result = runner.invoke(
            app, ["env", "remove", "-g", "pymongo", "mongo-python-driver", "--force"]
        )
        assert result.exit_code == 0
        assert "Virtual environment removed" in result.stdout
        assert not venv_dir.exists()


def test_env_init_repo_with_group_not_found(temp_repos_dir, mock_config):
    """Test env init with repo not found in specified group."""
    with patch("dbx_python_cli.utils.repo.get_config_path") as mock_get_path:
        mock_get_path.return_value = mock_config

        # Create group directory but not the repo
        pymongo_dir = temp_repos_dir / "pymongo"
        pymongo_dir.mkdir(parents=True)

        result = runner.invoke(
            app, ["env", "init", "-g", "pymongo", "nonexistent-repo"]
        )
        assert result.exit_code == 1
        output = result.stdout + (result.stderr or "")
        assert "Repository 'nonexistent-repo' not found in group 'pymongo'" in output


def test_env_remove_repo_with_group_not_found(temp_repos_dir, mock_config):
    """Test env remove with repo not found in specified group."""
    with patch("dbx_python_cli.utils.repo.get_config_path") as mock_get_path:
        mock_get_path.return_value = mock_config

        # Create group directory but not the repo
        pymongo_dir = temp_repos_dir / "pymongo"
        pymongo_dir.mkdir(parents=True)

        result = runner.invoke(
            app, ["env", "remove", "-g", "pymongo", "nonexistent-repo", "--force"]
        )
        assert result.exit_code == 1
        output = result.stdout + (result.stderr or "")
        assert "Repository 'nonexistent-repo' not found in group 'pymongo'" in output
