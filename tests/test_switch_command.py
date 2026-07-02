"""Tests for the switch command module."""

import re
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from dbx_python_cli.cli import app

runner = CliRunner()


def strip_ansi(text):
    """Remove ANSI escape sequences from text."""
    ansi_escape = re.compile(r"\x1b\[[0-9;]*m")
    return ansi_escape.sub("", text)


@pytest.fixture
def temp_repos_dir(tmp_path):
    """Create a temporary repos directory with mock repositories."""
    repos_dir = tmp_path / "repos"
    repos_dir.mkdir(parents=True)

    # Create mock repository structure
    # Group 1: pymongo
    pymongo_dir = repos_dir / "pymongo"
    pymongo_dir.mkdir()

    repo1 = pymongo_dir / "mongo-python-driver"
    repo1.mkdir()
    (repo1 / ".git").mkdir()

    repo2 = pymongo_dir / "specifications"
    repo2.mkdir()
    (repo2 / ".git").mkdir()

    # Create a project (with .git)
    projects_dir = repos_dir / "projects"
    projects_dir.mkdir()
    project1 = projects_dir / "test-project"
    project1.mkdir()
    (project1 / ".git").mkdir()
    (project1 / "pyproject.toml").write_text("[project]\nname = 'test-project'\n")

    return repos_dir


@pytest.fixture
def mock_config(tmp_path, temp_repos_dir):
    """Create a mock configuration."""
    return {
        "repo": {
            "base_dir": str(temp_repos_dir),
            "groups": {
                "pymongo": {
                    "repos": [
                        "https://github.com/mongodb/mongo-python-driver",
                        "https://github.com/mongodb/specifications",
                    ]
                },
                "langchain": {
                    "repos": [
                        "https://github.com/langchain-ai/langchain",
                    ]
                },
            },
        }
    }


def test_switch_help():
    """Test switch help command."""
    result = runner.invoke(app, ["switch", "--help"])
    assert result.exit_code == 0
    assert "Git branch switching and listing commands" in result.stdout
    assert "repo_name" in result.stdout.lower()
    assert "branch_name" in result.stdout.lower()


def test_switch_list_no_repos(tmp_path):
    """Test switch --list with no repositories."""
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()

    mock_config = {"repo": {"base_dir": str(empty_dir), "groups": {}}}

    with patch("dbx_python_cli.commands.switch.get_config", return_value=mock_config):
        with patch(
            "dbx_python_cli.commands.switch.get_base_dir", return_value=empty_dir
        ):
            result = runner.invoke(app, ["switch", "--list"])
            assert result.exit_code == 0
            assert "No repositories found" in result.stdout


def test_switch_list_shows_repos(temp_repos_dir, mock_config):
    """Test switch --list shows available repositories."""
    with patch("dbx_python_cli.commands.switch.get_config", return_value=mock_config):
        with patch(
            "dbx_python_cli.commands.switch.get_base_dir", return_value=temp_repos_dir
        ):
            result = runner.invoke(app, ["switch", "--list"])
            assert result.exit_code == 0
            assert "mongo-python-driver" in result.stdout
            assert "specifications" in result.stdout


def test_switch_no_repo_name(temp_repos_dir, mock_config):
    """Test switch without repo name shows error."""
    with patch("dbx_python_cli.commands.switch.get_config", return_value=mock_config):
        with patch(
            "dbx_python_cli.commands.switch.get_base_dir", return_value=temp_repos_dir
        ):
            result = runner.invoke(app, ["switch"])
            # Typer exits with code 2 for missing arguments
            assert result.exit_code == 2


def test_switch_no_branch_name(temp_repos_dir, mock_config):
    """Test switch without branch name shows error."""
    with patch("dbx_python_cli.commands.switch.get_config", return_value=mock_config):
        with patch(
            "dbx_python_cli.commands.switch.get_base_dir", return_value=temp_repos_dir
        ):
            result = runner.invoke(app, ["switch", "mongo-python-driver"])
            assert result.exit_code == 1
            # Check that usage message is shown
            assert "Usage: dbx switch" in result.stdout


def test_switch_repo_not_found(temp_repos_dir, mock_config):
    """Test switch with non-existent repository."""
    with patch("dbx_python_cli.commands.switch.get_config", return_value=mock_config):
        with patch(
            "dbx_python_cli.commands.switch.get_base_dir", return_value=temp_repos_dir
        ):
            result = runner.invoke(app, ["switch", "nonexistent", "main"])
            assert result.exit_code == 1
            # Check that helpful message is shown
            assert "dbx switch --list" in result.stdout


def test_switch_basic(tmp_path, temp_repos_dir, mock_config):
    """Test basic switch to a branch."""
    with patch(
        "dbx_python_cli.commands.switch.get_base_dir", return_value=temp_repos_dir
    ):
        with patch(
            "dbx_python_cli.commands.switch.get_config", return_value=mock_config
        ):
            with patch("dbx_python_cli.commands.switch.subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stderr="")
                result = runner.invoke(
                    app, ["switch", "mongo-python-driver", "PYTHON-5683"]
                )
                assert result.exit_code == 0
                assert "mongo-python-driver" in result.stdout
                assert "PYTHON-5683" in result.stdout
                assert mock_run.call_count == 2
                args = mock_run.call_args_list[0][0][0]
                assert args == ["git", "switch", "PYTHON-5683"]


def test_switch_with_create_flag(tmp_path, temp_repos_dir, mock_config):
    """Test switch with --create flag."""
    with patch(
        "dbx_python_cli.commands.switch.get_base_dir", return_value=temp_repos_dir
    ):
        with patch(
            "dbx_python_cli.commands.switch.get_config", return_value=mock_config
        ):
            with patch("dbx_python_cli.commands.switch.subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stderr="")
                result = runner.invoke(
                    app, ["switch", "--create", "mongo-python-driver", "feature-123"]
                )
                assert result.exit_code == 0
                assert "Creating and switching" in result.stdout
                assert mock_run.call_count == 2
                args = mock_run.call_args_list[0][0][0]
                assert args == ["git", "switch", "-c", "feature-123"]


def test_switch_with_group(tmp_path, temp_repos_dir, mock_config):
    """Test switch with a group."""
    with patch(
        "dbx_python_cli.commands.switch.get_base_dir", return_value=temp_repos_dir
    ):
        with patch(
            "dbx_python_cli.commands.switch.get_config", return_value=mock_config
        ):
            with patch("dbx_python_cli.commands.switch.subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stderr="")
                result = runner.invoke(app, ["switch", "-g", "pymongo", "main"])
                assert result.exit_code == 0
                assert "pymongo" in result.stdout
                # Should be called 4 times (2 repos × 2 calls each: git switch + rev-parse)
                assert mock_run.call_count == 4


def test_switch_with_nonexistent_group(tmp_path, temp_repos_dir, mock_config):
    """Test switch with non-existent group."""
    with patch(
        "dbx_python_cli.commands.switch.get_base_dir", return_value=temp_repos_dir
    ):
        with patch(
            "dbx_python_cli.commands.switch.get_config", return_value=mock_config
        ):
            result = runner.invoke(app, ["switch", "-g", "nonexistent", "main"])
            assert result.exit_code == 1


def test_switch_with_project(tmp_path, temp_repos_dir, mock_config):
    """Test switch with a project."""
    with patch(
        "dbx_python_cli.commands.switch.get_base_dir", return_value=temp_repos_dir
    ):
        with patch(
            "dbx_python_cli.commands.switch.get_config", return_value=mock_config
        ):
            with patch("dbx_python_cli.commands.switch.subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stderr="")
                result = runner.invoke(app, ["switch", "-p", "test-project", "feature"])
                assert result.exit_code == 0
                assert "test-project" in result.stdout
                assert mock_run.call_count == 2


def test_switch_failure(tmp_path, temp_repos_dir, mock_config):
    """Test switch when git command fails."""
    with patch(
        "dbx_python_cli.commands.switch.get_base_dir", return_value=temp_repos_dir
    ):
        with patch(
            "dbx_python_cli.commands.switch.get_config", return_value=mock_config
        ):
            with patch("dbx_python_cli.commands.switch.subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(
                    returncode=1,
                    stderr="error: pathspec 'nonexistent-branch' did not match any file(s) known to git",
                )
                result = runner.invoke(
                    app, ["switch", "mongo-python-driver", "nonexistent-branch"]
                )
                assert result.exit_code == 0  # Command itself succeeds, but git fails
                # Check that the switch was attempted
                assert "Switching to branch" in result.stdout
                # Verify subprocess.run was called with correct arguments
                mock_run.assert_called_once()
                args = mock_run.call_args[0][0]
                assert args == ["git", "switch", "nonexistent-branch"]


def test_verbose_flag_with_switch_command(tmp_path, temp_repos_dir, mock_config):
    """Test verbose flag with switch command."""
    with patch(
        "dbx_python_cli.commands.switch.get_base_dir", return_value=temp_repos_dir
    ):
        with patch(
            "dbx_python_cli.commands.switch.get_config", return_value=mock_config
        ):
            with patch("dbx_python_cli.commands.switch.subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stderr="")
                result = runner.invoke(
                    app, ["-v", "switch", "mongo-python-driver", "main"]
                )
                assert result.exit_code == 0
                assert "[verbose]" in result.stdout
