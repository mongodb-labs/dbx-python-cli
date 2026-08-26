"""Regression tests for CLI-level contracts that are easy to break silently.

Each test here pins behaviour that was previously broken in a way the rest of
the suite could not see: a flag that does not exist, a flag declared twice, or a
deliberate typer.Exit reported as an internal error.
"""

import click
import pytest
from typer.main import get_command
from typer.testing import CliRunner

from dbx_python_cli.cli import app

runner = CliRunner()


def _walk_commands(command, path=("dbx",)):
    yield path, command
    if isinstance(command, click.Group):
        for name, sub in command.commands.items():
            yield from _walk_commands(sub, (*path, name))


def test_no_command_declares_a_flag_twice():
    """Two params sharing a flag string make one of them silently unreachable.

    `dbx sync` declared --all twice (all-groups and all-commits); click bound
    --all to the later one, so the documented `dbx sync --all` became a no-op.
    """
    import warnings

    duplicates = []
    for path, command in _walk_commands(get_command(app)):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            command.make_parser(click.Context(command))
        for warning in caught:
            if "used more than once" in str(warning.message):
                duplicates.append((" ".join(path), str(warning.message)))
    assert duplicates == []


@pytest.mark.parametrize(
    "args",
    [
        ["clone", "--no-fork", "--help"],
        ["clone", "--fork", "--help"],
    ],
)
def test_clone_fork_flag_has_both_polarities(args):
    """--no-fork is advertised by clone's own error text, so it has to exist."""
    result = runner.invoke(app, args)
    assert result.exit_code == 0


def test_project_open_dash_h_shows_help():
    """-h is reserved for --help; `open` must not claim it for --host."""
    result = runner.invoke(app, ["project", "open", "-h"])
    assert result.exit_code == 0
    assert "Usage" in result.stdout


def test_sync_all_commits_flag_is_distinct_from_all():
    result = runner.invoke(app, ["sync", "--help"])
    assert result.exit_code == 0
    assert "--all-commits" in result.stdout


@pytest.mark.parametrize(
    ("command", "module"),
    [
        ("sync", "dbx_python_cli.commands.sync"),
        ("clone", "dbx_python_cli.commands.clone"),
    ],
)
def test_deliberate_exit_is_not_reported_as_an_internal_error(
    command, module, monkeypatch
):
    """typer.Exit subclasses RuntimeError, so a broad `except Exception` in the
    command body used to catch it and append a bogus "Error: 1" line."""
    import importlib

    mod = importlib.import_module(module)
    config = {"repo": {"base_dir": "/nonexistent-dbx-test", "groups": {}}}
    monkeypatch.setattr(mod.repo, "get_config", lambda: config)

    result = runner.invoke(app, [command, "-g", "nosuchgroup"])
    assert result.exit_code == 1
    output = result.output + (result.stderr if result.stderr_bytes else "")
    assert "not found in configuration" in output
    assert "Error: 1" not in output
