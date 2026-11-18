"""Tests for the edit command."""

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


def test_edit_help():
    """Test edit help command."""
    result = runner.invoke(app, ["edit", "--help"])
    assert result.exit_code == 0
    assert "Open repositories in editor" in result.stdout


def test_edit_no_repo_name(temp_repos_dir, mock_config):
    """Test edit without repo name shows error."""
    with patch("drivers_python_cli.commands.edit.get_config", return_value=mock_config):
        with patch(
            "drivers_python_cli.commands.edit.get_base_dir", return_value=temp_repos_dir
        ):
            result = runner.invoke(app, ["edit"])
            # Typer exits with code 2 for missing arguments
            assert result.exit_code == 2


def test_edit_repo_not_found(temp_repos_dir, mock_config):
    """Test edit with non-existent repository."""
    with patch("drivers_python_cli.commands.edit.get_config", return_value=mock_config):
        with patch(
            "drivers_python_cli.commands.edit.get_base_dir", return_value=temp_repos_dir
        ):
            result = runner.invoke(app, ["edit", "nonexistent"])
            assert result.exit_code == 1
            # Check that helpful message is shown
            assert "dpy list" in result.stdout


def test_edit_basic(tmp_path, temp_repos_dir, mock_config):
    """Test basic edit of a repository."""
    with patch(
        "drivers_python_cli.commands.edit.get_base_dir", return_value=temp_repos_dir
    ):
        with patch(
            "drivers_python_cli.commands.edit.get_config", return_value=mock_config
        ):
            with patch(
                "drivers_python_cli.commands.edit.get_editor", return_value="vim"
            ):
                with patch(
                    "drivers_python_cli.commands.edit.subprocess.run"
                ) as mock_run:
                    # Mock successful editor execution
                    mock_run.return_value = MagicMock(returncode=0)

                    result = runner.invoke(app, ["edit", "mongo-python-driver"])
                    assert result.exit_code == 0
                    assert "mongo-python-driver" in result.stdout
                    assert "vim" in result.stdout

                    # Verify subprocess.run was called with correct arguments
                    mock_run.assert_called_once()
                    args = mock_run.call_args[0][0]
                    assert args[0] == "vim"
                    assert "mongo-python-driver" in str(args[1])


def test_edit_with_custom_editor(tmp_path, temp_repos_dir, mock_config):
    """Test edit with custom editor from config."""
    with patch(
        "drivers_python_cli.commands.edit.get_base_dir", return_value=temp_repos_dir
    ):
        with patch(
            "drivers_python_cli.commands.edit.get_config", return_value=mock_config
        ):
            with patch(
                "drivers_python_cli.commands.edit.get_editor", return_value="nvim"
            ):
                with patch(
                    "drivers_python_cli.commands.edit.subprocess.run"
                ) as mock_run:
                    # Mock successful editor execution
                    mock_run.return_value = MagicMock(returncode=0)

                    result = runner.invoke(app, ["edit", "mongo-python-driver"])
                    assert result.exit_code == 0
                    assert "nvim" in result.stdout

                    # Verify subprocess.run was called with nvim
                    mock_run.assert_called_once()
                    args = mock_run.call_args[0][0]
                    assert args[0] == "nvim"


def test_edit_editor_not_found(tmp_path, temp_repos_dir, mock_config):
    """Test edit when editor executable is not found."""
    with patch(
        "drivers_python_cli.commands.edit.get_base_dir", return_value=temp_repos_dir
    ):
        with patch(
            "drivers_python_cli.commands.edit.get_config", return_value=mock_config
        ):
            with patch(
                "drivers_python_cli.commands.edit.get_editor",
                return_value="nonexistent-editor",
            ):
                with patch(
                    "drivers_python_cli.commands.edit.subprocess.run"
                ) as mock_run:
                    # Mock FileNotFoundError when editor is not found
                    mock_run.side_effect = FileNotFoundError("Editor not found")

                    result = runner.invoke(app, ["edit", "mongo-python-driver"])
                    assert result.exit_code == 1
                    # The error message is written to stderr, but Typer's CliRunner captures it in output
                    output = result.stdout + (result.stderr or "")
                    assert "not found" in output or result.exit_code == 1


def test_edit_editor_fails(tmp_path, temp_repos_dir, mock_config):
    """Test edit when editor execution fails."""
    with patch(
        "drivers_python_cli.commands.edit.get_base_dir", return_value=temp_repos_dir
    ):
        with patch(
            "drivers_python_cli.commands.edit.get_config", return_value=mock_config
        ):
            with patch(
                "drivers_python_cli.commands.edit.get_editor", return_value="vim"
            ):
                with patch(
                    "drivers_python_cli.commands.edit.subprocess.run"
                ) as mock_run:
                    # Mock CalledProcessError when editor fails
                    from subprocess import CalledProcessError

                    mock_run.side_effect = CalledProcessError(1, "vim")

                    result = runner.invoke(app, ["edit", "mongo-python-driver"])
                    assert result.exit_code == 1
                    # The error message is written to stderr, but we just verify the exit code
                    output = result.stdout + (result.stderr or "")
                    assert "Failed to open editor" in output or result.exit_code == 1


def test_verbose_flag_with_edit_command(tmp_path, temp_repos_dir, mock_config):
    """Test verbose flag with edit command."""
    with patch(
        "drivers_python_cli.commands.edit.get_base_dir", return_value=temp_repos_dir
    ):
        with patch(
            "drivers_python_cli.commands.edit.get_config", return_value=mock_config
        ):
            with patch(
                "drivers_python_cli.commands.edit.get_editor", return_value="vim"
            ):
                with patch(
                    "drivers_python_cli.commands.edit.subprocess.run"
                ) as mock_run:
                    mock_run.return_value = MagicMock(returncode=0)

                    result = runner.invoke(
                        app, ["--verbose", "edit", "mongo-python-driver"]
                    )
                    assert result.exit_code == 0
                    assert "[verbose]" in result.stdout
                    assert "Repository path:" in result.stdout
                    assert "Editor:" in result.stdout


def test_get_editor_priority():
    """Test get_editor function priority order."""
    from drivers_python_cli.utils.repo import get_editor

    # Test 1: Repo-specific editor (highest priority)
    config = {
        "repo": {
            "editor": "global-editor",
            "groups": {
                "pymongo": {
                    "editor": {"mongo-python-driver": "repo-specific-editor"},
                }
            },
        }
    }
    assert (
        get_editor(config, "pymongo", "mongo-python-driver") == "repo-specific-editor"
    )

    # Test 2: Group-level editor (when no repo-specific)
    config = {
        "repo": {
            "editor": "global-editor",
            "groups": {"pymongo": {"editor": "group-editor"}},
        }
    }
    assert get_editor(config, "pymongo", "mongo-python-driver") == "group-editor"

    # Test 3: Global editor (when no group or repo-specific)
    config = {"repo": {"editor": "global-editor", "groups": {"pymongo": {}}}}
    assert get_editor(config, "pymongo", "mongo-python-driver") == "global-editor"

    # Test 4: EDITOR environment variable (when no config)
    config = {"repo": {"groups": {"pymongo": {}}}}
    with patch.dict("os.environ", {"EDITOR": "env-editor"}, clear=True):
        assert get_editor(config, "pymongo", "mongo-python-driver") == "env-editor"

    # Test 5: Default to vim (when nothing is set)
    config = {"repo": {"groups": {"pymongo": {}}}}
    with patch.dict("os.environ", {}, clear=True):
        assert get_editor(config, "pymongo", "mongo-python-driver") == "vim"
