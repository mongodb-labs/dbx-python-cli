"""Tests for the just command module."""

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
    # Create a justfile
    (repo1 / "justfile").write_text("test:\n\techo 'Running tests'\n")

    repo2 = pymongo_dir / "specifications"
    repo2.mkdir()
    (repo2 / ".git").mkdir()
    # No justfile for this repo

    return repos_dir


@pytest.fixture
def mock_config(tmp_path, temp_repos_dir):
    """Create a mock config file."""
    config_dir = tmp_path / ".config" / "dbx-python-cli"
    config_dir.mkdir(parents=True)
    config_path = config_dir / "config.toml"
    # Convert path to use forward slashes for TOML compatibility on Windows
    repos_dir_str = str(temp_repos_dir).replace("\\", "/")
    config_content = f"""
[repo]
base_dir = "{repos_dir_str}"

[repo.groups.pymongo]
repos = [
    "https://github.com/mongodb/mongo-python-driver.git",
    "https://github.com/mongodb/specifications.git",
]
"""
    config_path.write_text(config_content)
    return config_path


def test_just_help():
    """Test that the just help command works."""
    result = runner.invoke(app, ["just", "--help"])
    assert result.exit_code == 0
    output = strip_ansi(result.stdout)
    assert "Just commands" in output


def test_just_no_repo_name(tmp_path, temp_repos_dir, mock_config):
    """Test that just without repo name shows help."""
    with patch(
        "dbx_python_cli.commands.just.get_base_dir", return_value=temp_repos_dir
    ):
        with patch("dbx_python_cli.commands.just.get_config", return_value={}):
            result = runner.invoke(app, ["just"])
            # Typer exits with code 2 when showing help due to no_args_is_help=True
            assert result.exit_code == 2
            # Should show help/usage
            output = result.stdout + result.stderr
            assert "Usage:" in output


def test_just_repo_not_found(tmp_path, temp_repos_dir, mock_config):
    """Test that just with non-existent repo shows error."""
    with patch(
        "dbx_python_cli.commands.just.get_base_dir", return_value=temp_repos_dir
    ):
        with patch("dbx_python_cli.commands.just.get_config", return_value={}):
            result = runner.invoke(app, ["just", "nonexistent-repo"])
            assert result.exit_code == 1
            # Error messages can be in stdout or stderr
            output = result.stdout + result.stderr
            assert "not found" in output or "available repositories" in output


def test_just_no_justfile(tmp_path, temp_repos_dir, mock_config):
    """Test that just with repo without justfile shows warning."""
    with patch(
        "dbx_python_cli.commands.just.get_base_dir", return_value=temp_repos_dir
    ):
        with patch("dbx_python_cli.commands.just.get_config", return_value={}):
            result = runner.invoke(app, ["just", "specifications"])
            assert result.exit_code == 1
            # Error messages can be in stdout or stderr
            output = result.stdout + result.stderr
            assert "No justfile found" in output or "justfile" in output.lower()


def test_just_without_command(tmp_path, temp_repos_dir, mock_config):
    """Test running just without a command."""
    with patch(
        "dbx_python_cli.commands.just.get_base_dir", return_value=temp_repos_dir
    ):
        with patch("dbx_python_cli.commands.just.get_config", return_value={}):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0)
                result = runner.invoke(app, ["just", "mongo-python-driver"])
                assert result.exit_code == 0
                assert "Running 'just' in" in result.stdout
                mock_run.assert_called_once()
                args = mock_run.call_args[0][0]
                assert args == ["just"]


def test_just_with_command(tmp_path, temp_repos_dir, mock_config):
    """Test running just with a command."""
    with patch(
        "dbx_python_cli.commands.just.get_base_dir", return_value=temp_repos_dir
    ):
        with patch("dbx_python_cli.commands.just.get_config", return_value={}):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0)
                result = runner.invoke(app, ["just", "mongo-python-driver", "test"])
                assert result.exit_code == 0
                assert "Running 'just test' in" in result.stdout
                mock_run.assert_called_once()
                args = mock_run.call_args[0][0]
                assert args == ["just", "test"]


def test_just_with_command_and_args(tmp_path, temp_repos_dir, mock_config):
    """Test running just with a command and arguments."""
    with patch(
        "dbx_python_cli.commands.just.get_base_dir", return_value=temp_repos_dir
    ):
        with patch("dbx_python_cli.commands.just.get_config", return_value={}):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0)
                result = runner.invoke(
                    app, ["just", "mongo-python-driver", "test", "-v"]
                )
                assert result.exit_code == 0
                assert "Running 'just test -v' in" in result.stdout
                mock_run.assert_called_once()
                args = mock_run.call_args[0][0]
                assert args == ["just", "test", "-v"]


def test_verbose_flag_with_just_command(tmp_path, temp_repos_dir, mock_config):
    """Test that verbose flag shows detailed output."""
    with patch(
        "dbx_python_cli.commands.just.get_base_dir", return_value=temp_repos_dir
    ):
        with patch("dbx_python_cli.commands.just.get_config", return_value={}):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0)
                result = runner.invoke(
                    app, ["-v", "just", "mongo-python-driver", "test"]
                )
                assert result.exit_code == 0
                output = strip_ansi(result.stdout)
                assert "[verbose]" in output
                assert "Running command:" in output


def test_just_list_shows_repos_with_justfiles(tmp_path, temp_repos_dir, mock_config):
    """Test that 'just list' shows repositories with justfiles."""
    with patch(
        "dbx_python_cli.commands.just.get_base_dir", return_value=temp_repos_dir
    ):
        with patch("dbx_python_cli.commands.just.get_config", return_value={}):
            result = runner.invoke(app, ["just", "list"])
            assert result.exit_code == 0
            output = strip_ansi(result.stdout)
            # Should show mongo-python-driver (has justfile)
            assert "mongo-python-driver" in output
            # Should NOT show specifications (no justfile)
            assert "specifications" not in output
            # Should show count
            assert "1 repository with justfiles" in output


def test_just_list_no_repos_with_justfiles(tmp_path):
    """Test that 'just list' shows message when no repos have justfiles."""
    # Create a repos dir with no justfiles
    repos_dir = tmp_path / "repos"
    repos_dir.mkdir(parents=True)

    # Create a repo without justfile
    pymongo_dir = repos_dir / "pymongo"
    pymongo_dir.mkdir()
    repo1 = pymongo_dir / "some-repo"
    repo1.mkdir()
    (repo1 / ".git").mkdir()
    # No justfile

    with patch("dbx_python_cli.commands.just.get_base_dir", return_value=repos_dir):
        with patch("dbx_python_cli.commands.just.get_config", return_value={}):
            result = runner.invoke(app, ["just", "list"])
            assert result.exit_code == 0
            output = strip_ansi(result.stdout)
            assert "No repositories with justfiles found" in output


def test_just_list_multiple_repos(tmp_path):
    """Test that 'just list' shows multiple repos across groups."""
    repos_dir = tmp_path / "repos"
    repos_dir.mkdir(parents=True)

    # Create multiple repos with justfiles in different groups
    group1_dir = repos_dir / "group1"
    group1_dir.mkdir()
    repo1 = group1_dir / "repo-a"
    repo1.mkdir()
    (repo1 / ".git").mkdir()
    (repo1 / "justfile").write_text("test:\n\techo test\n")

    group2_dir = repos_dir / "group2"
    group2_dir.mkdir()
    repo2 = group2_dir / "repo-b"
    repo2.mkdir()
    (repo2 / ".git").mkdir()
    (repo2 / "Justfile").write_text("lint:\n\techo lint\n")  # Capital J

    with patch("dbx_python_cli.commands.just.get_base_dir", return_value=repos_dir):
        with patch("dbx_python_cli.commands.just.get_config", return_value={}):
            result = runner.invoke(app, ["just", "list"])
            assert result.exit_code == 0
            output = strip_ansi(result.stdout)
            assert "repo-a" in output
            assert "repo-b" in output
            assert "group1" in output
            assert "group2" in output
            assert "2 repositories with justfiles" in output
