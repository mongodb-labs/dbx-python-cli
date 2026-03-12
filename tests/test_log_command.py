"""Tests for the log command."""

import pytest
from typer.testing import CliRunner
from unittest.mock import patch, MagicMock

from dbx_python_cli.cli import app

runner = CliRunner()


@pytest.fixture
def temp_repos_dir(tmp_path):
    """Create a temporary repos directory with test structure."""
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
                        "git@github.com:mongodb/mongo-python-driver.git",
                        "git@github.com:mongodb/specifications.git",
                    ]
                },
                "langchain": {
                    "repos": [
                        "https://github.com/langchain-ai/langchain.git",
                    ]
                },
            },
        }
    }


def test_log_help():
    """Test log help command."""
    result = runner.invoke(app, ["log", "--help"])
    assert result.exit_code == 0
    assert "Show git commit logs" in result.stdout


def test_log_no_repo_name(temp_repos_dir, mock_config):
    """Test log without repo name shows error."""
    with patch("dbx_python_cli.commands.log.get_config", return_value=mock_config):
        with patch(
            "dbx_python_cli.commands.log.get_base_dir", return_value=temp_repos_dir
        ):
            result = runner.invoke(app, ["log"])
            # Typer exits with code 2 for missing arguments
            assert result.exit_code == 2


def test_log_repo_not_found(temp_repos_dir, mock_config):
    """Test log with non-existent repository."""
    with patch("dbx_python_cli.commands.log.get_config", return_value=mock_config):
        with patch(
            "dbx_python_cli.commands.log.get_base_dir", return_value=temp_repos_dir
        ):
            result = runner.invoke(app, ["log", "nonexistent"])
            assert result.exit_code == 1
            # Check that helpful message is shown
            assert "dbx list" in result.stdout


def test_log_basic(tmp_path, temp_repos_dir, mock_config):
    """Test basic log of a repository."""
    with patch("dbx_python_cli.commands.log.get_base_dir", return_value=temp_repos_dir):
        with patch("dbx_python_cli.commands.log.get_config", return_value=mock_config):
            with patch("dbx_python_cli.commands.log.subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stdout="test log output")
                result = runner.invoke(app, ["log", "mongo-python-driver"])
                assert result.exit_code == 0
                assert "mongo-python-driver" in result.stdout
                # Verify git log was called with correct arguments
                # Should be called twice: once for git log, once for pagination (or just echo)
                assert mock_run.call_count >= 1
                # Check the first call (git log)
                first_call = mock_run.call_args_list[0]
                assert first_call[0][0] == [
                    "git",
                    "--no-pager",
                    "log",
                    "--color=always",
                ]  # Default: entire log (no limit)


def test_log_with_number(tmp_path, temp_repos_dir, mock_config):
    """Test log with custom number of commits."""
    with patch("dbx_python_cli.commands.log.get_base_dir", return_value=temp_repos_dir):
        with patch("dbx_python_cli.commands.log.get_config", return_value=mock_config):
            with patch("dbx_python_cli.commands.log.subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stdout="test log output")
                result = runner.invoke(app, ["log", "mongo-python-driver", "-n", "5"])
                assert result.exit_code == 0
                # Verify git log was called with -n 5
                first_call = mock_run.call_args_list[0]
                assert first_call[0][0] == [
                    "git",
                    "--no-pager",
                    "log",
                    "--color=always",
                    "-n",
                    "5",
                ]


def test_log_with_oneline(tmp_path, temp_repos_dir, mock_config):
    """Test log with oneline format."""
    with patch("dbx_python_cli.commands.log.get_base_dir", return_value=temp_repos_dir):
        with patch("dbx_python_cli.commands.log.get_config", return_value=mock_config):
            with patch("dbx_python_cli.commands.log.subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stdout="test log output")
                result = runner.invoke(app, ["log", "mongo-python-driver", "--oneline"])
                assert result.exit_code == 0
                assert "oneline" in result.stdout
                # Verify git log was called with --oneline
                first_call = mock_run.call_args_list[0]
                assert first_call[0][0] == [
                    "git",
                    "--no-pager",
                    "log",
                    "--color=always",
                    "--oneline",
                ]


def test_log_with_group(tmp_path, temp_repos_dir, mock_config):
    """Test log with group option."""
    with patch("dbx_python_cli.commands.log.get_base_dir", return_value=temp_repos_dir):
        with patch("dbx_python_cli.commands.log.get_config", return_value=mock_config):
            with patch("dbx_python_cli.commands.log.subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stdout="test log output")
                result = runner.invoke(app, ["log", "-g", "pymongo"])
                assert result.exit_code == 0
                assert "pymongo" in result.stdout
                # Should call git log twice (2 repos in group) plus pagination
                assert mock_run.call_count >= 2


def test_log_with_nonexistent_group(tmp_path, temp_repos_dir, mock_config):
    """Test log with non-existent group."""
    with patch("dbx_python_cli.commands.log.get_base_dir", return_value=temp_repos_dir):
        with patch("dbx_python_cli.commands.log.get_config", return_value=mock_config):
            result = runner.invoke(app, ["log", "-g", "nonexistent"])
            assert result.exit_code == 1


def test_log_not_git_repo(tmp_path, temp_repos_dir, mock_config):
    """Test log on a directory that's not a git repo."""
    # Create a non-git directory
    non_git_dir = temp_repos_dir / "pymongo" / "not-a-repo"
    non_git_dir.mkdir()

    with patch("dbx_python_cli.commands.log.get_base_dir", return_value=temp_repos_dir):
        with patch("dbx_python_cli.commands.log.get_config", return_value=mock_config):
            # Manually add the non-git repo to the list
            with patch(
                "dbx_python_cli.commands.log.find_repo_by_name",
                return_value={
                    "name": "not-a-repo",
                    "path": non_git_dir,
                    "group": "pymongo",
                },
            ):
                result = runner.invoke(app, ["log", "not-a-repo"])
                assert result.exit_code == 0
                # Error messages go to stderr, check result.output which includes both stdout and stderr
                assert (
                    "Not a git repository" in result.output
                    or "skipping" in result.output
                )


def test_verbose_flag_with_log_command(tmp_path, temp_repos_dir, mock_config):
    """Test verbose flag with log command."""
    with patch("dbx_python_cli.commands.log.get_base_dir", return_value=temp_repos_dir):
        with patch("dbx_python_cli.commands.log.get_config", return_value=mock_config):
            with patch("dbx_python_cli.commands.log.subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stdout="test log output")
                result = runner.invoke(app, ["--verbose", "log", "mongo-python-driver"])
                assert result.exit_code == 0
                assert "[verbose]" in result.stdout


def test_log_with_number_and_oneline(tmp_path, temp_repos_dir, mock_config):
    """Test log with both number and oneline options."""
    with patch("dbx_python_cli.commands.log.get_base_dir", return_value=temp_repos_dir):
        with patch("dbx_python_cli.commands.log.get_config", return_value=mock_config):
            with patch("dbx_python_cli.commands.log.subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stdout="test log output")
                result = runner.invoke(
                    app, ["log", "mongo-python-driver", "-n", "20", "--oneline"]
                )
                assert result.exit_code == 0
                # Verify git log was called with both options
                first_call = mock_run.call_args_list[0]
                assert first_call[0][0] == [
                    "git",
                    "--no-pager",
                    "log",
                    "--color=always",
                    "-n",
                    "20",
                    "--oneline",
                ]


def test_log_with_group_and_number(tmp_path, temp_repos_dir, mock_config):
    """Test log with group and custom number."""
    with patch("dbx_python_cli.commands.log.get_base_dir", return_value=temp_repos_dir):
        with patch("dbx_python_cli.commands.log.get_config", return_value=mock_config):
            with patch("dbx_python_cli.commands.log.subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stdout="test log output")
                result = runner.invoke(app, ["log", "-g", "pymongo", "-n", "3"])
                assert result.exit_code == 0
                # Should call git log twice with -n3 (plus pagination)
                assert mock_run.call_count >= 2
                # Check the first two calls are git log commands
                for i in range(2):
                    call = mock_run.call_args_list[i]
                    assert call[0][0] == [
                        "git",
                        "--no-pager",
                        "log",
                        "--color=always",
                        "-n",
                        "3",
                    ]
