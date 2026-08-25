"""Tests for the worktree command module and worktree utilities."""

import subprocess
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from dbx_python_cli.cli import app
from dbx_python_cli.utils.repo import is_worktree, should_create_upstream_worktree
from dbx_python_cli.utils.worktree import (
    add_worktree,
    branch_to_label,
    get_remote_head_branch,
    get_worktree_dir,
    has_remote,
    list_worktrees,
    local_branch_exists,
    remove_worktree,
)

runner = CliRunner()


def _git(*args, cwd):
    """Run a git command, raising on failure."""
    return subprocess.run(
        ["git", *args], cwd=str(cwd), check=True, capture_output=True, text=True
    )


@pytest.fixture
def fork_and_upstream(tmp_path):
    """Build a real fork clone with an ``upstream`` remote in ``base_dir/django``.

    Worktree behaviour depends on git's own bookkeeping (``.git`` as a file,
    ``.git/worktrees`` registrations, refusing a branch checked out twice), so
    these tests drive real repositories rather than mocking subprocess.
    """
    base_dir = tmp_path / "repos"
    group_dir = base_dir / "django"
    group_dir.mkdir(parents=True)

    origin = tmp_path / "origin.git"
    _git("init", "-q", "--bare", str(origin), cwd=tmp_path)

    seed = tmp_path / "seed"
    _git("clone", "-q", str(origin), str(seed), cwd=tmp_path)
    _git("commit", "-q", "--allow-empty", "-m", "init", cwd=seed)
    _git("push", "-q", "origin", "HEAD:main", cwd=seed)

    fork = group_dir / "django"
    _git("clone", "-q", str(origin), str(fork), cwd=tmp_path)
    _git("remote", "add", "upstream", str(origin), cwd=fork)
    _git("fetch", "-q", "upstream", cwd=fork)

    return {"base_dir": base_dir, "fork": fork, "group_dir": group_dir}


@pytest.fixture
def config(fork_and_upstream):
    """Config pointing at the fixture's base_dir with the django group."""
    return {
        "repo": {
            "base_dir": str(fork_and_upstream["base_dir"]),
            "groups": {
                "django": {
                    "repos": ["git@github.com:mongodb-forks/django.git"],
                    "upstream_worktree": ["django"],
                }
            },
        }
    }


# --- utils/worktree.py -------------------------------------------------------


def test_get_worktree_dir_grouped(tmp_path):
    assert get_worktree_dir(tmp_path, "django", "django") == (
        tmp_path / "django" / "django-upstream"
    )


def test_get_worktree_dir_flat(tmp_path):
    assert get_worktree_dir(tmp_path, "django", "django", flat=True) == (
        tmp_path / "django-upstream"
    )


def test_get_worktree_dir_custom_label(tmp_path):
    assert get_worktree_dir(tmp_path, "django", "django", label="6-1") == (
        tmp_path / "django" / "django-6-1"
    )


def test_branch_to_label_flattens_slashes():
    assert branch_to_label("stable/6.1.x") == "stable-6.1.x"
    assert branch_to_label("main") == "main"


def test_has_remote(fork_and_upstream):
    fork = fork_and_upstream["fork"]
    assert has_remote(fork, "upstream") is True
    assert has_remote(fork, "nope") is False


def test_get_remote_head_branch(fork_and_upstream):
    assert get_remote_head_branch(fork_and_upstream["fork"], "upstream") == "main"


def test_get_remote_head_branch_unknown_remote(fork_and_upstream):
    assert get_remote_head_branch(fork_and_upstream["fork"], "missing") is None


def test_local_branch_exists(fork_and_upstream):
    fork = fork_and_upstream["fork"]
    assert local_branch_exists(fork, "main") is True
    assert local_branch_exists(fork, "does-not-exist") is False


def test_add_and_remove_worktree(fork_and_upstream):
    fork = fork_and_upstream["fork"]
    path = fork_and_upstream["group_dir"] / "django-upstream"

    ok, message = add_worktree(fork, path, "upstream-main", start_point="upstream/main")
    assert ok, message
    assert path.exists()
    # A linked worktree has .git as a file, not a directory.
    assert is_worktree(path) is True
    assert is_worktree(fork) is False

    branches = {w["path"].name: w["branch"] for w in list_worktrees(fork)}
    assert branches == {"django": "main", "django-upstream": "upstream-main"}

    ok, message = remove_worktree(fork, path)
    assert ok, message
    assert not path.exists()
    assert [w["path"].name for w in list_worktrees(fork)] == ["django"]


def test_add_worktree_rejects_branch_checked_out_elsewhere(fork_and_upstream):
    """git refuses to check out `main` twice; the failure is surfaced, not hidden."""
    fork = fork_and_upstream["fork"]
    path = fork_and_upstream["group_dir"] / "django-main"

    ok, message = add_worktree(fork, path, "main")
    assert ok is False
    assert "main" in message
    assert not path.exists()


def test_list_worktrees_on_non_repo(tmp_path):
    assert list_worktrees(tmp_path) == []


# --- config ------------------------------------------------------------------


def test_should_create_upstream_worktree(config):
    assert should_create_upstream_worktree(config, "django", "django") is True
    assert should_create_upstream_worktree(config, "django", "other") is False
    assert should_create_upstream_worktree(config, "missing-group", "django") is False


# --- dbx worktree ------------------------------------------------------------


def test_worktree_add_upstream(config, fork_and_upstream):
    with patch("dbx_python_cli.commands.worktree.get_config", return_value=config):
        result = runner.invoke(app, ["worktree", "add", "django", "--upstream"])

    assert result.exit_code == 0, result.output
    assert "worktree added" in result.output
    assert (fork_and_upstream["group_dir"] / "django-upstream").exists()


def test_worktree_add_upstream_twice_fails(config, fork_and_upstream):
    with patch("dbx_python_cli.commands.worktree.get_config", return_value=config):
        runner.invoke(app, ["worktree", "add", "django", "--upstream"])
        result = runner.invoke(app, ["worktree", "add", "django", "--upstream"])

    assert result.exit_code == 1
    assert "already exists" in result.output


def test_worktree_add_requires_branch_or_upstream(config):
    with patch("dbx_python_cli.commands.worktree.get_config", return_value=config):
        result = runner.invoke(app, ["worktree", "add", "django"])

    assert result.exit_code == 1
    assert "--upstream" in result.output


def test_worktree_add_unknown_repo(config):
    with patch("dbx_python_cli.commands.worktree.get_config", return_value=config):
        result = runner.invoke(app, ["worktree", "add", "nope", "--upstream"])

    assert result.exit_code == 1
    assert "not found" in result.output


def test_worktree_add_without_upstream_remote(config, fork_and_upstream):
    _git("remote", "remove", "upstream", cwd=fork_and_upstream["fork"])
    with patch("dbx_python_cli.commands.worktree.get_config", return_value=config):
        result = runner.invoke(app, ["worktree", "add", "django", "--upstream"])

    assert result.exit_code == 1
    assert "upstream" in result.output


def test_worktree_list(config, fork_and_upstream):
    with patch("dbx_python_cli.commands.worktree.get_config", return_value=config):
        runner.invoke(app, ["worktree", "add", "django", "--upstream"])
        result = runner.invoke(app, ["worktree", "list", "django"])

    assert result.exit_code == 0, result.output
    assert "django-upstream" in result.output
    assert "upstream-main" in result.output


def test_worktree_remove(config, fork_and_upstream):
    path = fork_and_upstream["group_dir"] / "django-upstream"
    with patch("dbx_python_cli.commands.worktree.get_config", return_value=config):
        runner.invoke(app, ["worktree", "add", "django", "--upstream"])
        assert path.exists()
        result = runner.invoke(app, ["worktree", "remove", "django"])

    assert result.exit_code == 0, result.output
    assert not path.exists()


def test_worktree_remove_missing(config):
    with patch("dbx_python_cli.commands.worktree.get_config", return_value=config):
        result = runner.invoke(app, ["worktree", "remove", "django"])

    assert result.exit_code == 1
    assert "no worktree" in result.output


def test_worktree_commands_reject_a_worktree_as_target(config, fork_and_upstream):
    """`django-upstream` is a worktree, not a clone, so it is not a valid target."""
    with patch("dbx_python_cli.commands.worktree.get_config", return_value=config):
        runner.invoke(app, ["worktree", "add", "django", "--upstream"])
        result = runner.invoke(app, ["worktree", "list", "django-upstream"])

    assert result.exit_code == 1
    assert "is itself a worktree" in result.output


# --- worktrees are excluded from mutating bulk commands ----------------------


def test_sync_skips_a_worktree(config, fork_and_upstream):
    """Rebasing a worktree onto upstream and force-pushing would corrupt the fork."""
    from dbx_python_cli.commands.sync import _sync_repository

    path = fork_and_upstream["group_dir"] / "django-upstream"
    ok, message = add_worktree(
        fork_and_upstream["fork"], path, "upstream-main", start_point="upstream/main"
    )
    assert ok, message

    with patch("dbx_python_cli.commands.sync.subprocess.run") as mock_run:
        status = _sync_repository(path, "django-upstream")

    assert status == "skipped"
    # The guard must short-circuit before any git command runs.
    mock_run.assert_not_called()


def test_sync_does_not_skip_a_primary_clone(fork_and_upstream):
    from dbx_python_cli.commands.sync import _sync_repository

    with patch("dbx_python_cli.commands.sync.subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = ""
        mock_run.return_value.stderr = ""
        _sync_repository(fork_and_upstream["fork"], "django", dry_run=True)

    assert mock_run.called


def test_switch_group_skips_worktrees(config, fork_and_upstream):
    """A bulk switch must not touch worktrees; git allows one checkout per branch."""
    add_worktree(
        fork_and_upstream["fork"],
        fork_and_upstream["group_dir"] / "django-upstream",
        "upstream-main",
        start_point="upstream/main",
    )

    with (
        patch("dbx_python_cli.commands.switch.get_config", return_value=config),
        patch("dbx_python_cli.commands.switch._run_git_switch") as mock_switch,
    ):
        result = runner.invoke(app, ["switch", "-g", "django", "main"])

    assert result.exit_code == 0, result.output
    switched = [call.args[1] for call in mock_switch.call_args_list]
    assert switched == ["django"]
    assert "django-upstream" not in switched
