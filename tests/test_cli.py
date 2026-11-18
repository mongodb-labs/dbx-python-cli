"""Tests for the CLI module."""

import re

from typer.testing import CliRunner

from drivers_python_cli.cli import app

runner = CliRunner()


def strip_ansi(text):
    """Remove ANSI escape sequences from text."""
    ansi_escape = re.compile(r"\x1b\[[0-9;]*m")
    return ansi_escape.sub("", text)


def test_app_help():
    """Test that the CLI help command works."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "A command line tool for Drivers Python development tasks" in result.stdout


def test_app_version():
    """Test that the CLI version command works."""
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "dpy, version 0.1.0" in result.stdout


def test_app_no_args():
    """Test that the CLI shows help when run without arguments."""
    result = runner.invoke(app, [])
    # Typer returns exit code 2 when no command is provided (shows help)
    assert result.exit_code == 2


def test_verbose_flag_in_help():
    """Test that the verbose flag appears in help."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    output = strip_ansi(result.stdout)
    assert "--verbose" in output
    assert "-v" in output
    assert "Show more detailed output" in output


def test_verbose_flag_with_test_command():
    """Test that verbose flag works with test command."""
    from unittest.mock import patch

    with patch("drivers_python_cli.utils.repo.get_config_path") as _mock_path:
        with patch("drivers_python_cli.commands.test.get_config") as mock_config:
            mock_config.return_value = {"repo": {"base_dir": "/tmp/test"}}
            result = runner.invoke(app, ["-v", "test", "--list"])
            assert result.exit_code == 0
            assert "[verbose]" in result.stdout


def test_verbose_flag_with_install_command():
    """Test that verbose flag works with install command."""
    from unittest.mock import patch

    with patch("drivers_python_cli.utils.repo.get_config_path") as _mock_path:
        with patch("drivers_python_cli.commands.install.get_config") as mock_config:
            mock_config.return_value = {"repo": {"base_dir": "/tmp/test"}}
            result = runner.invoke(app, ["-v", "install", "--list"])
            assert result.exit_code == 0
            assert "[verbose]" in result.stdout


def test_list_command_no_repos():
    """Test that the list command shows message when no repos are cloned."""
    from unittest.mock import patch

    with patch("drivers_python_cli.commands.list.get_config") as mock_config:
        with patch("drivers_python_cli.commands.list.list_repos") as mock_list:
            mock_config.return_value = {"repo": {"base_dir": "/tmp/test"}}
            mock_list.return_value = ""
            result = runner.invoke(app, ["list"])
            assert result.exit_code == 0
            assert "No repositories found" in result.stdout
            assert "Base directory:" in result.stdout


def test_list_command_with_repos():
    """Test that the list command lists all cloned repositories."""
    from unittest.mock import patch

    with patch("drivers_python_cli.commands.list.get_config") as mock_config:
        with patch("drivers_python_cli.commands.list.list_repos") as mock_list:
            mock_config.return_value = {"repo": {"base_dir": "/tmp/test"}}
            mock_list.return_value = "├── django/\n│   └── ✓ django\n└── pymongo/\n    └── ✓ mongo-python-driver"
            result = runner.invoke(app, ["list"])
            assert result.exit_code == 0
            assert "Repository status:" in result.stdout
            # Check for tree format
            assert "django/" in result.stdout
            assert "pymongo/" in result.stdout
            assert "django" in result.stdout
            assert "mongo-python-driver" in result.stdout
            assert "├──" in result.stdout or "└──" in result.stdout
            # Check for legend
            assert "Legend:" in result.stdout


def test_list_command_in_help():
    """Test that the list command appears in help."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    output = strip_ansi(result.stdout)
    assert "list" in output.lower()
    assert "List repositories" in output
