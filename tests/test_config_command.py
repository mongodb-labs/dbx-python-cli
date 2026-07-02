"""Tests for the `dbx config validate` command."""

from unittest.mock import patch

from typer.testing import CliRunner

from dbx_python_cli.cli import app

runner = CliRunner()


def _validate(config):
    with patch("dbx_python_cli.commands.config.get_config", return_value=config):
        return runner.invoke(app, ["config", "validate"])


def test_validate_minimal_valid_config():
    """A minimal valid config reports no issues."""
    config = {"repo": {"base_dir": "~/Developer/mongodb", "groups": {}}}
    result = _validate(config)
    assert result.exit_code == 0
    assert "no unknown or deprecated keys" in result.stdout


def test_validate_all_known_group_keys_accepted():
    """Every documented per-group key, including sync_after_clone, passes validation."""
    config = {
        "repo": {
            "base_dir": "~/Developer/mongodb",
            "groups": {
                "pymongo": {
                    "repos": ["git@github.com:mongodb/mongo-python-driver.git"],
                    "python_version": "3.13",
                    "preferred_branch": {},
                    "no_fork": [],
                    "upstream": {},
                    "upstream_branch": {},
                    "sync_after_clone": ["mongo-python-driver"],
                    "install_extras": {},
                    "install_groups": {},
                    "install_dirs": {},
                    "build_commands": {},
                    "skip_install": [],
                    "test_runner": {},
                    "test_runner_args": {},
                    "test_env": {},
                    "sys_path": {},
                }
            },
        }
    }
    result = _validate(config)
    assert result.exit_code == 0
    assert "no unknown or deprecated keys" in result.stdout


def test_validate_flags_unknown_group_key():
    """An unrecognized per-group key is reported as unknown."""
    config = {
        "repo": {
            "base_dir": "~/Developer/mongodb",
            "groups": {"pymongo": {"repos": [], "totally_made_up_key": True}},
        }
    }
    result = _validate(config)
    assert result.exit_code == 1
    assert "[unknown] [repo.groups.pymongo] key: totally_made_up_key" in result.stdout


def test_validate_missing_base_dir_is_error():
    """Missing base_dir under [repo] is reported as an error, not just a warning."""
    config = {"repo": {"groups": {}}}
    result = _validate(config)
    assert result.exit_code == 1
    assert "missing required key: base_dir" in result.stdout


def test_validate_flags_unknown_top_level_key():
    """An unrecognized top-level section is reported as unknown."""
    config = {
        "repo": {"base_dir": "~/Developer/mongodb", "groups": {}},
        "made_up_section": {},
    }
    result = _validate(config)
    assert result.exit_code == 1
    assert "[unknown] top-level key: [made_up_section]" in result.stdout
