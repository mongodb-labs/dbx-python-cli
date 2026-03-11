"""Tests for the branch command module."""

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

    # Create a project (without .git)
    projects_dir = repos_dir / "projects"
    projects_dir.mkdir()
    project1 = projects_dir / "test-project"
    project1.mkdir()
    (project1 / "pyproject.toml").write_text("[project]\nname = 'test-project'\n")

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


def test_branch_help():
    """Test that the branch help command works."""
    result = runner.invoke(app, ["branch", "--help"])
    assert result.exit_code == 0
    output = strip_ansi(result.stdout)
    assert "Git branch commands" in output


def test_branch_no_repo_name(tmp_path, temp_repos_dir, mock_config):
    """Test that branch without repo name shows help."""
    with patch(
        "dbx_python_cli.commands.branch.get_base_dir", return_value=temp_repos_dir
    ):
        with patch("dbx_python_cli.commands.branch.get_config", return_value={}):
            result = runner.invoke(app, ["branch"])
            # Typer exits with code 2 when showing help due to no_args_is_help=True
            assert result.exit_code == 2
            # Should show help/usage
            output = result.stdout + result.stderr
            assert "Usage:" in output


def test_branch_repo_not_found(tmp_path, temp_repos_dir, mock_config):
    """Test that branch with non-existent repo shows error."""
    with patch(
        "dbx_python_cli.commands.branch.get_base_dir", return_value=temp_repos_dir
    ):
        with patch("dbx_python_cli.commands.branch.get_config", return_value={}):
            result = runner.invoke(app, ["branch", "nonexistent-repo"])
            assert result.exit_code == 1
            # Error messages can be in stdout or stderr
            output = result.stdout + result.stderr
            assert "not found" in output or "available repositories" in output


def test_branch_without_args(tmp_path, temp_repos_dir, mock_config):
    """Test running branch without arguments."""
    with patch(
        "dbx_python_cli.commands.branch.get_base_dir", return_value=temp_repos_dir
    ):
        with patch("dbx_python_cli.commands.branch.get_config", return_value={}):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0)
                result = runner.invoke(app, ["branch", "mongo-python-driver"])
                assert result.exit_code == 0
                assert "mongo-python-driver:" in result.stdout
                mock_run.assert_called_once()
                args = mock_run.call_args[0][0]
                assert args == ["git", "--no-pager", "branch"]


def test_branch_with_args(tmp_path, temp_repos_dir, mock_config):
    """Test running branch with arguments (use -r for remote branches)."""
    with patch(
        "dbx_python_cli.commands.branch.get_base_dir", return_value=temp_repos_dir
    ):
        with patch("dbx_python_cli.commands.branch.get_config", return_value={}):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0)
                result = runner.invoke(app, ["branch", "mongo-python-driver", "-r"])
                assert result.exit_code == 0
                assert "git branch -r" in result.stdout
                mock_run.assert_called_once()
                args = mock_run.call_args[0][0]
                assert args == ["git", "--no-pager", "branch", "-r"]


def test_branch_with_group(tmp_path, temp_repos_dir, mock_config):
    """Test running branch with a group."""
    config = {
        "repo": {
            "base_dir": str(temp_repos_dir),
            "groups": {
                "pymongo": {
                    "repos": [
                        "https://github.com/mongodb/mongo-python-driver.git",
                        "https://github.com/mongodb/specifications.git",
                    ]
                }
            },
        }
    }
    with patch(
        "dbx_python_cli.commands.branch.get_base_dir", return_value=temp_repos_dir
    ):
        with patch("dbx_python_cli.commands.branch.get_config", return_value=config):
            with patch(
                "dbx_python_cli.commands.branch.get_repo_groups",
                return_value=config["repo"]["groups"],
            ):
                with patch("subprocess.run") as mock_run:
                    mock_run.return_value = MagicMock(
                        returncode=0, stdout="  main\n* feature\n", stderr=""
                    )
                    result = runner.invoke(app, ["branch", "-g", "pymongo"])
                    assert result.exit_code == 0
                    assert "Running git branch in 2 repository(ies)" in result.stdout
                    assert mock_run.call_count == 2


def test_branch_with_nonexistent_group(tmp_path, temp_repos_dir, mock_config):
    """Test running branch with a non-existent group."""
    config = {
        "repo": {
            "base_dir": str(temp_repos_dir),
            "groups": {"pymongo": {"repos": []}},
        }
    }
    with patch(
        "dbx_python_cli.commands.branch.get_base_dir", return_value=temp_repos_dir
    ):
        with patch("dbx_python_cli.commands.branch.get_config", return_value=config):
            with patch(
                "dbx_python_cli.commands.branch.get_repo_groups",
                return_value=config["repo"]["groups"],
            ):
                result = runner.invoke(app, ["branch", "-g", "nonexistent"])
                assert result.exit_code == 1
                output = result.stdout + result.stderr
                assert "not found" in output


def test_verbose_flag_with_branch_command(tmp_path, temp_repos_dir, mock_config):
    """Test that verbose flag shows detailed output and all branches."""
    with patch(
        "dbx_python_cli.commands.branch.get_base_dir", return_value=temp_repos_dir
    ):
        with patch("dbx_python_cli.commands.branch.get_config", return_value={}):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0)
                result = runner.invoke(app, ["-v", "branch", "mongo-python-driver"])
                assert result.exit_code == 0
                output = strip_ansi(result.stdout)
                assert "[verbose]" in output
                assert "Running command:" in output
                assert "git branch -a" in output
                args = mock_run.call_args[0][0]
                assert args == ["git", "--no-pager", "branch", "-a"]


def test_branch_with_all_flag(tmp_path, temp_repos_dir, mock_config):
    """Test that -a triggers all-groups mode (use -v for showing all branches)."""
    config = {
        "repo": {
            "base_dir": str(temp_repos_dir),
            "groups": {
                "pymongo": {
                    "repos": ["https://github.com/mongodb/mongo-python-driver.git"]
                }
            },
        }
    }
    with patch(
        "dbx_python_cli.commands.branch.get_base_dir", return_value=temp_repos_dir
    ):
        with patch("dbx_python_cli.commands.branch.get_config", return_value=config):
            with patch(
                "dbx_python_cli.commands.branch.get_repo_groups",
                return_value=config["repo"]["groups"],
            ):
                with patch(
                    "dbx_python_cli.commands.branch.get_global_groups", return_value=[]
                ):
                    with patch("subprocess.run") as mock_run:
                        mock_run.return_value = MagicMock(
                            returncode=0, stdout="  main\n* feature\n", stderr=""
                        )
                        result = runner.invoke(app, ["branch", "-a"])
                        assert result.exit_code == 0
                        # Should show branches for all groups
                        assert "Running git branch in" in result.stdout
                        assert "group(s)" in result.stdout


def test_verbose_flag_shows_all_branches(tmp_path, temp_repos_dir, mock_config):
    """Test that dbx -v branch shows all branches (local and remote) via -a flag."""
    with patch(
        "dbx_python_cli.commands.branch.get_base_dir", return_value=temp_repos_dir
    ):
        with patch("dbx_python_cli.commands.branch.get_config", return_value={}):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0)
                result = runner.invoke(app, ["-v", "branch", "mongo-python-driver"])
                assert result.exit_code == 0
                assert "git branch -a" in result.stdout
                mock_run.assert_called_once()
                args = mock_run.call_args[0][0]
                assert args == ["git", "--no-pager", "branch", "-a"]


def test_branch_with_group_and_verbose(tmp_path, temp_repos_dir, mock_config):
    """Test running branch with a group and verbose mode (shows all branches)."""
    config = {
        "repo": {
            "base_dir": str(temp_repos_dir),
            "groups": {
                "pymongo": {
                    "repos": [
                        "https://github.com/mongodb/mongo-python-driver.git",
                        "https://github.com/mongodb/specifications.git",
                    ]
                }
            },
        }
    }
    with patch(
        "dbx_python_cli.commands.branch.get_base_dir", return_value=temp_repos_dir
    ):
        with patch("dbx_python_cli.commands.branch.get_config", return_value=config):
            with patch(
                "dbx_python_cli.commands.branch.get_repo_groups",
                return_value=config["repo"]["groups"],
            ):
                with patch("subprocess.run") as mock_run:
                    mock_run.return_value = MagicMock(
                        returncode=0, stdout="  main\n* feature\n", stderr=""
                    )
                    result = runner.invoke(app, ["-v", "branch", "-g", "pymongo"])
                    assert result.exit_code == 0
                    assert "Running git branch in 2 repository(ies)" in result.stdout
                    assert "git branch -a" in result.stdout
                    assert mock_run.call_count == 2
                    # Check that both calls used -a flag and color
                    for call in mock_run.call_args_list:
                        args = call[0][0]
                        assert args == [
                            "git",
                            "--no-pager",
                            "-c",
                            "color.branch=always",
                            "branch",
                            "-a",
                        ]


def test_branch_all_groups(tmp_path, temp_repos_dir, mock_config):
    """Test running branch with -a flag to show branches for all groups."""
    config = {
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
            },
        }
    }

    # Create django group directory and repo
    django_dir = temp_repos_dir / "django"
    django_dir.mkdir()
    django_repo = django_dir / "django-mongodb-backend"
    django_repo.mkdir()
    (django_repo / ".git").mkdir()

    with patch(
        "dbx_python_cli.commands.branch.get_base_dir", return_value=temp_repos_dir
    ):
        with patch("dbx_python_cli.commands.branch.get_config", return_value=config):
            with patch(
                "dbx_python_cli.commands.branch.get_repo_groups",
                return_value=config["repo"]["groups"],
            ):
                with patch(
                    "dbx_python_cli.commands.branch.get_global_groups", return_value=[]
                ):
                    with patch("subprocess.run") as mock_run:
                        mock_run.return_value = MagicMock(
                            returncode=0, stdout="  main\n* feature\n", stderr=""
                        )
                        result = runner.invoke(app, ["branch", "-a"])
                        assert result.exit_code == 0
                        # Should run on all repos across all groups (2 pymongo + 1 django = 3)
                        assert (
                            "Running git branch in 3 repository(ies) across 2 group(s)"
                            in result.stdout
                        )
                        assert mock_run.call_count == 3


def test_branch_all_groups_excludes_global(tmp_path, temp_repos_dir, mock_config):
    """Test that -a excludes global groups."""
    config = {
        "repo": {
            "base_dir": str(temp_repos_dir),
            "global_groups": ["global"],
            "groups": {
                "global": {
                    "repos": ["https://github.com/mongodb/mongo-python-driver.git"]
                },
                "pymongo": {"repos": ["https://github.com/mongodb/specifications.git"]},
            },
        }
    }

    with patch(
        "dbx_python_cli.commands.branch.get_base_dir", return_value=temp_repos_dir
    ):
        with patch("dbx_python_cli.commands.branch.get_config", return_value=config):
            with patch(
                "dbx_python_cli.commands.branch.get_repo_groups",
                return_value=config["repo"]["groups"],
            ):
                with patch(
                    "dbx_python_cli.commands.branch.get_global_groups",
                    return_value=["global"],
                ):
                    with patch("subprocess.run") as mock_run:
                        mock_run.return_value = MagicMock(
                            returncode=0, stdout="  main\n* feature\n", stderr=""
                        )
                        result = runner.invoke(app, ["branch", "-a"])
                        assert result.exit_code == 0
                        # Should only run on pymongo group (2 repos), not global
                        assert (
                            "Running git branch in 2 repository(ies) across 1 group(s)"
                            in result.stdout
                        )
                        assert mock_run.call_count == 2
