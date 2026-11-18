"""Tests for the open command."""

import pytest
from typer.testing import CliRunner
from unittest.mock import patch, MagicMock

from drivers_python_cli.cli import app

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


def test_open_help():
    """Test open help command."""
    result = runner.invoke(app, ["open", "--help"])
    assert result.exit_code == 0
    assert "Open repositories in web browser" in result.stdout


def test_open_no_repo_name(temp_repos_dir, mock_config):
    """Test open without repo name shows error."""
    with patch("drivers_python_cli.commands.open.get_config", return_value=mock_config):
        with patch(
            "drivers_python_cli.commands.open.get_base_dir", return_value=temp_repos_dir
        ):
            result = runner.invoke(app, ["open"])
            # Typer exits with code 2 for missing arguments
            assert result.exit_code == 2


def test_open_repo_not_found(temp_repos_dir, mock_config):
    """Test open with non-existent repository."""
    with patch("drivers_python_cli.commands.open.get_config", return_value=mock_config):
        with patch(
            "drivers_python_cli.commands.open.get_base_dir", return_value=temp_repos_dir
        ):
            result = runner.invoke(app, ["open", "nonexistent"])
            assert result.exit_code == 1
            # Check that helpful message is shown
            assert "dpy list" in result.stdout


def test_open_basic(tmp_path, temp_repos_dir, mock_config):
    """Test basic open of a repository."""
    with patch(
        "drivers_python_cli.commands.open.get_base_dir", return_value=temp_repos_dir
    ):
        with patch(
            "drivers_python_cli.commands.open.get_config", return_value=mock_config
        ):
            with patch("drivers_python_cli.commands.open.subprocess.run") as mock_run:
                # Mock git remote get-url to return a URL
                mock_run.return_value = MagicMock(
                    returncode=0,
                    stdout="git@github.com:mongodb/mongo-python-driver.git\n",
                )
                with patch(
                    "drivers_python_cli.commands.open.webbrowser.open"
                ) as mock_browser:
                    result = runner.invoke(app, ["open", "mongo-python-driver"])
                    assert result.exit_code == 0
                    assert "mongo-python-driver" in result.stdout
                    # Verify browser was opened with correct URL
                    mock_browser.assert_called_once_with(
                        "https://github.com/mongodb/mongo-python-driver"
                    )


def test_open_with_https_url(tmp_path, temp_repos_dir, mock_config):
    """Test open with HTTPS git URL."""
    with patch(
        "drivers_python_cli.commands.open.get_base_dir", return_value=temp_repos_dir
    ):
        with patch(
            "drivers_python_cli.commands.open.get_config", return_value=mock_config
        ):
            with patch("drivers_python_cli.commands.open.subprocess.run") as mock_run:
                # Mock git remote get-url to return an HTTPS URL
                mock_run.return_value = MagicMock(
                    returncode=0,
                    stdout="https://github.com/mongodb/mongo-python-driver.git\n",
                )
                with patch(
                    "drivers_python_cli.commands.open.webbrowser.open"
                ) as mock_browser:
                    result = runner.invoke(app, ["open", "mongo-python-driver"])
                    assert result.exit_code == 0
                    # Verify browser was opened with correct URL (without .git)
                    mock_browser.assert_called_once_with(
                        "https://github.com/mongodb/mongo-python-driver"
                    )


def test_open_no_origin_remote(tmp_path, temp_repos_dir, mock_config):
    """Test open when repository has no origin remote."""
    with patch(
        "drivers_python_cli.commands.open.get_base_dir", return_value=temp_repos_dir
    ):
        with patch(
            "drivers_python_cli.commands.open.get_config", return_value=mock_config
        ):
            with patch(
                "drivers_python_cli.commands.open._get_git_remote_url",
                return_value=None,
            ):
                result = runner.invoke(app, ["open", "mongo-python-driver"])
                assert result.exit_code == 1


def test_open_with_group(tmp_path, temp_repos_dir, mock_config):
    """Test open with group option."""
    with patch(
        "drivers_python_cli.commands.open.get_base_dir", return_value=temp_repos_dir
    ):
        with patch(
            "drivers_python_cli.commands.open.get_config", return_value=mock_config
        ):
            with patch("drivers_python_cli.commands.open.subprocess.run") as mock_run:
                # Mock git remote get-url to return different URLs for different repos
                def mock_git_remote(cmd, **kwargs):
                    if "mongo-python-driver" in str(cmd):
                        return MagicMock(
                            returncode=0,
                            stdout="git@github.com:mongodb/mongo-python-driver.git\n",
                        )
                    elif "specifications" in str(cmd):
                        return MagicMock(
                            returncode=0,
                            stdout="git@github.com:mongodb/specifications.git\n",
                        )
                    return MagicMock(returncode=1, stdout="")

                mock_run.side_effect = mock_git_remote

                with patch(
                    "drivers_python_cli.commands.open.webbrowser.open"
                ) as mock_browser:
                    result = runner.invoke(app, ["open", "-g", "pymongo"])
                    assert result.exit_code == 0
                    assert "pymongo" in result.stdout
                    # Should open 2 repos
                    assert mock_browser.call_count == 2
                    # Check URLs
                    calls = [call[0][0] for call in mock_browser.call_args_list]
                    assert "https://github.com/mongodb/mongo-python-driver" in calls
                    assert "https://github.com/mongodb/specifications" in calls


def test_open_with_group_fork_urls(tmp_path, temp_repos_dir, mock_config):
    """Test open with group option uses fork URLs when repos were cloned with --fork."""
    with patch(
        "drivers_python_cli.commands.open.get_base_dir", return_value=temp_repos_dir
    ):
        with patch(
            "drivers_python_cli.commands.open.get_config", return_value=mock_config
        ):
            with patch("drivers_python_cli.commands.open.subprocess.run") as mock_run:
                # Mock git remote get-url to return fork URLs
                def mock_git_remote(cmd, **kwargs):
                    if "mongo-python-driver" in str(cmd):
                        return MagicMock(
                            returncode=0,
                            stdout="git@github.com:aclark4life/mongo-python-driver.git\n",
                        )
                    elif "specifications" in str(cmd):
                        return MagicMock(
                            returncode=0,
                            stdout="git@github.com:aclark4life/specifications.git\n",
                        )
                    return MagicMock(returncode=1, stdout="")

                mock_run.side_effect = mock_git_remote

                with patch(
                    "drivers_python_cli.commands.open.webbrowser.open"
                ) as mock_browser:
                    result = runner.invoke(app, ["open", "-g", "pymongo"])
                    assert result.exit_code == 0
                    assert "pymongo" in result.stdout
                    # Should open 2 repos
                    assert mock_browser.call_count == 2
                    # Check that fork URLs are used
                    calls = [call[0][0] for call in mock_browser.call_args_list]
                    assert "https://github.com/aclark4life/mongo-python-driver" in calls
                    assert "https://github.com/aclark4life/specifications" in calls


def test_open_with_nonexistent_group(tmp_path, temp_repos_dir, mock_config):
    """Test open with non-existent group."""
    with patch(
        "drivers_python_cli.commands.open.get_base_dir", return_value=temp_repos_dir
    ):
        with patch(
            "drivers_python_cli.commands.open.get_config", return_value=mock_config
        ):
            result = runner.invoke(app, ["open", "-g", "nonexistent"])
            assert result.exit_code == 1


def test_verbose_flag_with_open_command(tmp_path, temp_repos_dir, mock_config):
    """Test verbose flag with open command."""
    with patch(
        "drivers_python_cli.commands.open.get_base_dir", return_value=temp_repos_dir
    ):
        with patch(
            "drivers_python_cli.commands.open.get_config", return_value=mock_config
        ):
            with patch("drivers_python_cli.commands.open.subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(
                    returncode=0,
                    stdout="git@github.com:mongodb/mongo-python-driver.git\n",
                )
                with patch("drivers_python_cli.commands.open.webbrowser.open"):
                    result = runner.invoke(
                        app, ["--verbose", "open", "mongo-python-driver"]
                    )
                    assert result.exit_code == 0
                    assert "[verbose]" in result.stdout


def test_convert_git_url_to_browser_url():
    """Test URL conversion helper function."""
    from drivers_python_cli.commands.open import _convert_git_url_to_browser_url

    # SSH format
    assert (
        _convert_git_url_to_browser_url(
            "git@github.com:mongodb/mongo-python-driver.git"
        )
        == "https://github.com/mongodb/mongo-python-driver"
    )

    # HTTPS format
    assert (
        _convert_git_url_to_browser_url(
            "https://github.com/mongodb/mongo-python-driver.git"
        )
        == "https://github.com/mongodb/mongo-python-driver"
    )

    # Without .git suffix
    assert (
        _convert_git_url_to_browser_url("git@github.com:mongodb/mongo-python-driver")
        == "https://github.com/mongodb/mongo-python-driver"
    )

    # GitLab SSH format
    assert (
        _convert_git_url_to_browser_url("git@gitlab.com:group/project.git")
        == "https://gitlab.com/group/project"
    )


def test_extract_repo_name_from_url():
    """Test repo name extraction helper function."""
    from drivers_python_cli.commands.open import _extract_repo_name_from_url

    assert (
        _extract_repo_name_from_url("git@github.com:mongodb/mongo-python-driver.git")
        == "mongo-python-driver"
    )

    assert (
        _extract_repo_name_from_url(
            "https://github.com/mongodb/mongo-python-driver.git"
        )
        == "mongo-python-driver"
    )

    assert (
        _extract_repo_name_from_url("git@github.com:mongodb/mongo-python-driver")
        == "mongo-python-driver"
    )
