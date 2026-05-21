"""Tests for the swap command module."""

import re
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from dbx_python_cli.cli import app

runner = CliRunner()


def strip_ansi(text):
    """Remove ANSI escape sequences from text."""
    return re.compile(r"\x1b\[[0-9;]*m").sub("", text)


@pytest.fixture
def mock_config(tmp_path):
    repos_dir = tmp_path / "repos"
    repos_dir.mkdir()
    pymongo_dir = repos_dir / "pymongo"
    pymongo_dir.mkdir()
    repo_dir = pymongo_dir / "mongo-python-driver"
    repo_dir.mkdir()
    (repo_dir / ".git").mkdir()
    return {
        "config": {
            "repo": {
                "base_dir": str(repos_dir),
                "groups": {
                    "pymongo": {
                        "repos": ["git@github.com:mongodb/mongo-python-driver.git"]
                    }
                },
            }
        },
        "base_dir": repos_dir,
        "repo_dir": repo_dir,
    }


def _make_run_side_effect(origin_url, upstream_url):
    """Return a side_effect for subprocess.run that fakes git remote get-url."""

    def side_effect(cmd, **kwargs):
        mock = MagicMock()
        mock.returncode = 0
        if cmd[:3] == ["git", "remote", "get-url"]:
            remote = cmd[3]
            if remote == "origin":
                mock.stdout = origin_url + "\n"
            elif remote == "upstream":
                mock.stdout = upstream_url + "\n"
        return mock

    return side_effect


class TestSwapByName:
    def test_swap_success(self, mock_config):
        origin = "git@github.com:aclark4life/mongo-python-driver.git"
        upstream = "git@github.com:mongodb/mongo-python-driver.git"

        with (
            patch(
                "dbx_python_cli.commands.swap.get_config",
                return_value=mock_config["config"],
            ),
            patch(
                "dbx_python_cli.commands.swap.get_base_dir",
                return_value=mock_config["base_dir"],
            ),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.side_effect = _make_run_side_effect(origin, upstream)
            result = runner.invoke(app, ["swap", "mongo-python-driver"])

        assert result.exit_code == 0
        output = strip_ansi(result.output)
        assert "swapped" in output
        assert upstream in output
        assert origin in output

    def test_swap_missing_upstream(self, mock_config):
        def side_effect(cmd, **kwargs):
            mock = MagicMock()
            if cmd[:3] == ["git", "remote", "get-url"]:
                remote = cmd[3]
                if remote == "origin":
                    mock.returncode = 0
                    mock.stdout = "git@github.com:fork/repo.git\n"
                    return mock
                raise Exception("no upstream")  # triggers CalledProcessError path

        with (
            patch(
                "dbx_python_cli.commands.swap.get_config",
                return_value=mock_config["config"],
            ),
            patch(
                "dbx_python_cli.commands.swap.get_base_dir",
                return_value=mock_config["base_dir"],
            ),
            patch(
                "dbx_python_cli.commands.swap._get_remote_url",
                side_effect=lambda path, remote: (
                    "git@github.com:fork/repo.git" if remote == "origin" else None
                ),
            ),
        ):
            result = runner.invoke(app, ["swap", "mongo-python-driver"])

        assert result.exit_code != 0
        assert "upstream" in result.output

    def test_swap_repo_not_found(self, mock_config):
        with (
            patch(
                "dbx_python_cli.commands.swap.get_config",
                return_value=mock_config["config"],
            ),
            patch(
                "dbx_python_cli.commands.swap.get_base_dir",
                return_value=mock_config["base_dir"],
            ),
        ):
            result = runner.invoke(app, ["swap", "nonexistent-repo"])

        assert result.exit_code != 0
        assert "not found" in result.output


class TestSwapDryRun:
    def test_dry_run_shows_no_change(self, mock_config):
        origin = "git@github.com:fork/repo.git"
        upstream = "git@github.com:mongodb/repo.git"

        with (
            patch(
                "dbx_python_cli.commands.swap.get_config",
                return_value=mock_config["config"],
            ),
            patch(
                "dbx_python_cli.commands.swap.get_base_dir",
                return_value=mock_config["base_dir"],
            ),
            patch(
                "dbx_python_cli.commands.swap._get_remote_url",
                side_effect=lambda path, remote: (
                    origin if remote == "origin" else upstream
                ),
            ),
            patch("dbx_python_cli.commands.swap._set_remote_url") as mock_set,
        ):
            result = runner.invoke(app, ["swap", "mongo-python-driver", "--dry-run"])

        assert result.exit_code == 0
        mock_set.assert_not_called()
        assert "would set" in result.output


class TestSwapByGroup:
    def test_swap_group(self, mock_config):
        origin = "git@github.com:fork/repo.git"
        upstream = "git@github.com:mongodb/repo.git"

        with (
            patch(
                "dbx_python_cli.commands.swap.get_config",
                return_value=mock_config["config"],
            ),
            patch(
                "dbx_python_cli.commands.swap.get_base_dir",
                return_value=mock_config["base_dir"],
            ),
            patch(
                "dbx_python_cli.commands.swap._get_remote_url",
                side_effect=lambda path, remote: (
                    origin if remote == "origin" else upstream
                ),
            ),
            patch("dbx_python_cli.commands.swap._set_remote_url"),
        ):
            result = runner.invoke(app, ["swap", "-g", "pymongo"])

        assert result.exit_code == 0
        output = strip_ansi(result.output)
        assert "swapped" in output

    def test_swap_group_not_found(self, mock_config):
        with (
            patch(
                "dbx_python_cli.commands.swap.get_config",
                return_value=mock_config["config"],
            ),
            patch(
                "dbx_python_cli.commands.swap.get_base_dir",
                return_value=mock_config["base_dir"],
            ),
        ):
            result = runner.invoke(app, ["swap", "-g", "nonexistent"])

        assert result.exit_code != 0
        assert "nonexistent" in result.output


class TestSwapByPath:
    def test_swap_dot(self, mock_config, monkeypatch):
        """dbx swap . resolves the current directory to a repo."""
        origin = "git@github.com:fork/repo.git"
        upstream = "git@github.com:mongodb/repo.git"
        monkeypatch.chdir(mock_config["repo_dir"])

        with (
            patch(
                "dbx_python_cli.commands.swap.get_config",
                return_value=mock_config["config"],
            ),
            patch(
                "dbx_python_cli.commands.swap.get_base_dir",
                return_value=mock_config["base_dir"],
            ),
            patch(
                "dbx_python_cli.commands.swap._get_remote_url",
                side_effect=lambda path, remote: (
                    origin if remote == "origin" else upstream
                ),
            ),
            patch("dbx_python_cli.commands.swap._set_remote_url"),
        ):
            result = runner.invoke(app, ["swap", "."])

        assert result.exit_code == 0
        output = strip_ansi(result.output)
        assert "swapped" in output
