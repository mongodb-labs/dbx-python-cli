"""Tests for the remove command module."""

import re
from unittest.mock import patch

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

    # Group 2: django
    django_dir = repos_dir / "django"
    django_dir.mkdir()

    repo3 = django_dir / "django-mongodb-backend"
    repo3.mkdir()
    (repo3 / ".git").mkdir()

    return repos_dir


@pytest.fixture
def mock_config(tmp_path, temp_repos_dir):
    """Mock configuration."""
    return {
        "repo": {
            "base_dir": str(temp_repos_dir),
            "groups": {
                "pymongo": {
                    "repos": [
                        "https://github.com/mongodb/mongo-python-driver.git",
                        "https://github.com/mongodb/specifications.git",
                    ]
                },
                "django": {
                    "repos": [
                        "https://github.com/mongodb-labs/django-mongodb-backend.git",
                    ]
                },
                "langchain": {
                    "repos": [
                        "https://github.com/langchain-ai/langchain-mongodb.git",
                    ]
                },
            },
        }
    }


def test_remove_single_repo_with_confirmation_no(mock_config, temp_repos_dir):
    """Test removing a single repo with confirmation declined."""
    with patch(
        "dbx_python_cli.commands.remove.repo.get_config", return_value=mock_config
    ):
        # Simulate user saying "no" to confirmation
        result = runner.invoke(app, ["remove", "mongo-python-driver"], input="n\n")
        assert result.exit_code == 0
        output = strip_ansi(result.stdout)
        assert "Removal cancelled" in output
        # Verify repo still exists
        assert (temp_repos_dir / "pymongo" / "mongo-python-driver").exists()


def test_remove_single_repo_with_force(mock_config, temp_repos_dir):
    """Test removing a single repo with --force flag."""
    with patch(
        "dbx_python_cli.commands.remove.repo.get_config", return_value=mock_config
    ):
        # Options must come before positional arguments with allow_interspersed_args=False
        result = runner.invoke(app, ["remove", "--force", "mongo-python-driver"])
        assert result.exit_code == 0
        output = strip_ansi(result.stdout)
        assert "Successfully removed 1 repository(ies)" in output
        assert "Removed mongo-python-driver (pymongo)" in output
        # Verify repo was removed
        assert not (temp_repos_dir / "pymongo" / "mongo-python-driver").exists()
        # Verify group directory still exists
        assert (temp_repos_dir / "pymongo").exists()


def test_remove_multiple_repos_with_force(mock_config, temp_repos_dir):
    """Test removing multiple repos with --force flag."""
    with patch(
        "dbx_python_cli.commands.remove.repo.get_config", return_value=mock_config
    ):
        result = runner.invoke(
            app,
            ["remove", "--force", "mongo-python-driver", "specifications"],
        )
        assert result.exit_code == 0
        output = strip_ansi(result.stdout)
        assert "Successfully removed 2 repository(ies)" in output
        # Verify repos were removed
        assert not (temp_repos_dir / "pymongo" / "mongo-python-driver").exists()
        assert not (temp_repos_dir / "pymongo" / "specifications").exists()


def test_remove_group_with_confirmation_yes(mock_config, temp_repos_dir):
    """Test removing all repos in a group with confirmation accepted."""
    with patch(
        "dbx_python_cli.commands.remove.repo.get_config", return_value=mock_config
    ):
        # Simulate user saying "yes" to confirmation
        result = runner.invoke(app, ["remove", "-g", "django"], input="y\n")
        assert result.exit_code == 0
        output = strip_ansi(result.stdout)
        assert "Successfully removed 1 repository(ies)" in output
        # Verify repo and group directory were removed
        assert not (temp_repos_dir / "django" / "django-mongodb-backend").exists()
        assert not (temp_repos_dir / "django").exists()


def test_remove_group_with_force(mock_config, temp_repos_dir):
    """Test removing all repos in a group with --force flag."""
    with patch(
        "dbx_python_cli.commands.remove.repo.get_config", return_value=mock_config
    ):
        result = runner.invoke(app, ["remove", "-g", "pymongo", "--force"])
        assert result.exit_code == 0
        output = strip_ansi(result.stdout)
        assert "Successfully removed 2 repository(ies)" in output
        # Verify repos and group directory were removed
        assert not (temp_repos_dir / "pymongo" / "mongo-python-driver").exists()
        assert not (temp_repos_dir / "pymongo" / "specifications").exists()
        assert not (temp_repos_dir / "pymongo").exists()


def test_remove_nonexistent_repo(mock_config):
    """Test removing a non-existent repo."""
    with patch(
        "dbx_python_cli.commands.remove.repo.get_config", return_value=mock_config
    ):
        result = runner.invoke(app, ["remove", "nonexistent"])
        assert result.exit_code == 1
        stderr = strip_ansi(result.stderr)
        stdout = strip_ansi(result.stdout)
        assert "Repository 'nonexistent' not found" in stderr
        assert "dbx list" in stdout


def test_remove_nonexistent_group(mock_config):
    """Test removing repos from a non-existent group."""
    with patch(
        "dbx_python_cli.commands.remove.repo.get_config", return_value=mock_config
    ):
        result = runner.invoke(app, ["remove", "-g", "nonexistent"])
        assert result.exit_code == 1
        stderr = strip_ansi(result.stderr)
        assert "No repositories found in group 'nonexistent'" in stderr


def test_remove_no_args(mock_config):
    """Test remove command without arguments shows help."""
    with patch(
        "dbx_python_cli.commands.remove.repo.get_config", return_value=mock_config
    ):
        result = runner.invoke(app, ["remove"])
        # With no_args_is_help=True, shows help with exit code 2
        assert result.exit_code == 2
        output = strip_ansi(result.stdout)
        assert "Remove repositories or repository groups" in output


def test_remove_repo_with_group_flag(mock_config, temp_repos_dir):
    """Test removing a repo with -G flag to specify group."""
    # Create a duplicate repo in another group
    langchain_dir = temp_repos_dir / "langchain"
    langchain_dir.mkdir()
    duplicate_repo = langchain_dir / "mongo-python-driver"
    duplicate_repo.mkdir()
    (duplicate_repo / ".git").mkdir()

    with patch(
        "dbx_python_cli.commands.remove.repo.get_config", return_value=mock_config
    ):
        # Remove from langchain group specifically
        # Options must come before positional arguments with allow_interspersed_args=False
        result = runner.invoke(
            app, ["remove", "--force", "-G", "langchain", "mongo-python-driver"]
        )
        assert result.exit_code == 0
        output = strip_ansi(result.stdout)
        assert "Removed mongo-python-driver (langchain)" in output
        # Verify only langchain version was removed
        assert not (temp_repos_dir / "langchain" / "mongo-python-driver").exists()
        assert (temp_repos_dir / "pymongo" / "mongo-python-driver").exists()


def test_remove_repo_in_multiple_groups_warning(mock_config, temp_repos_dir):
    """Test warning when removing a repo that exists in multiple groups."""
    # Create a duplicate repo in another group
    langchain_dir = temp_repos_dir / "langchain"
    langchain_dir.mkdir()
    duplicate_repo = langchain_dir / "mongo-python-driver"
    duplicate_repo.mkdir()
    (duplicate_repo / ".git").mkdir()

    with patch(
        "dbx_python_cli.commands.remove.repo.get_config", return_value=mock_config
    ):
        # Remove without -G flag should warn
        result = runner.invoke(app, ["remove", "--force", "mongo-python-driver"])
        assert result.exit_code == 0
        stderr = strip_ansi(result.stderr)
        assert "found in multiple groups" in stderr
        assert "Use -G to specify a different group" in stderr


def test_remove_both_repo_and_group_flag_error(mock_config):
    """Test error when specifying both repo names and -g flag."""
    with patch(
        "dbx_python_cli.commands.remove.repo.get_config", return_value=mock_config
    ):
        # Options must come before positional arguments with allow_interspersed_args=False
        result = runner.invoke(app, ["remove", "-g", "pymongo", "mongo-python-driver"])
        assert result.exit_code == 1
        stderr = strip_ansi(result.stderr)
        assert "Cannot specify both repository names and -g flag" in stderr


def test_remove_clone_also_removes_its_worktrees(mock_config, temp_repos_dir):
    """Removing a primary clone must take its linked worktrees with it.

    A worktree's .git file points into the clone's object store, so deleting the
    clone alone left a directory where every git command fails and which no dbx
    command could clean up.
    """
    clone = temp_repos_dir / "django" / "django-mongodb-backend"
    worktree = temp_repos_dir / "django" / "django-mongodb-backend-upstream"
    worktree.mkdir()
    (worktree / ".git").write_text(f"gitdir: {clone}/.git/worktrees/upstream\n")

    removed = []

    def fake_remove_worktree(repo_path, worktree_path, force=False, verbose=False):
        removed.append(("worktree", str(worktree_path)))
        return True, ""

    with patch(
        "dbx_python_cli.commands.remove.repo.get_config", return_value=mock_config
    ):
        with patch(
            "dbx_python_cli.commands.remove.list_worktrees",
            return_value=[
                {"path": clone, "branch": "main", "head": None, "bare": False},
                {"path": worktree, "branch": "upstream", "head": None, "bare": False},
            ],
        ):
            with patch(
                "dbx_python_cli.commands.remove.remove_worktree",
                side_effect=fake_remove_worktree,
            ):
                with patch("dbx_python_cli.commands.remove.prune_worktrees"):
                    with patch("shutil.rmtree") as mock_rmtree:
                        result = runner.invoke(
                            app, ["remove", "-f", "django-mongodb-backend"]
                        )

    output = strip_ansi(result.stdout)
    assert result.exit_code == 0, output
    assert "Also removing worktree 'django-mongodb-backend-upstream'" in output
    # The worktree went through `git worktree remove`, not a blind rmtree...
    assert removed == [("worktree", str(worktree))]
    # ...and the clone itself was still removed.
    assert [str(c[0][0]) for c in mock_rmtree.call_args_list] == [str(clone)]


def test_remove_skips_clone_when_its_worktree_cannot_be_removed(
    mock_config, temp_repos_dir
):
    """If the worktree survives, deleting the clone would break it — so don't."""
    clone = temp_repos_dir / "django" / "django-mongodb-backend"
    worktree = temp_repos_dir / "django" / "django-mongodb-backend-upstream"
    worktree.mkdir()
    (worktree / ".git").write_text(f"gitdir: {clone}/.git/worktrees/upstream\n")

    with patch(
        "dbx_python_cli.commands.remove.repo.get_config", return_value=mock_config
    ):
        with patch(
            "dbx_python_cli.commands.remove.list_worktrees",
            return_value=[
                {"path": clone, "branch": "main", "head": None, "bare": False},
                {"path": worktree, "branch": "upstream", "head": None, "bare": False},
            ],
        ):
            with patch(
                "dbx_python_cli.commands.remove.remove_worktree",
                return_value=(False, "worktree contains modified files"),
            ):
                with patch("dbx_python_cli.commands.remove.prune_worktrees"):
                    with patch("shutil.rmtree") as mock_rmtree:
                        result = runner.invoke(
                            app, ["remove", "-f", "django-mongodb-backend"]
                        )

    output = strip_ansi(result.stdout) + (result.stderr if result.stderr_bytes else "")
    assert result.exit_code == 1
    assert "Skipping django-mongodb-backend" in output
    mock_rmtree.assert_not_called()


def test_remove_group_lists_non_repo_contents_before_deleting(
    mock_config, temp_repos_dir
):
    """`remove -g` rmtree's the whole group dir, including the group venv.

    The confirmation prompt listed only repositories, so the group-level venv
    was deleted without ever being mentioned.
    """
    group_venv = temp_repos_dir / "pymongo" / ".venv"
    group_venv.mkdir()

    with patch(
        "dbx_python_cli.commands.remove.repo.get_config", return_value=mock_config
    ):
        with patch("dbx_python_cli.commands.remove.list_worktrees", return_value=[]):
            result = runner.invoke(app, ["remove", "-g", "pymongo", "--dry-run"])

    output = strip_ansi(result.stdout)
    assert result.exit_code == 0, output
    assert "also deletes the group directory" in output
    assert ".venv" in output
    assert "Dry run" in output
    # Dry run really did not delete anything.
    assert group_venv.exists()
