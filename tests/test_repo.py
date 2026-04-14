"""Tests for the repo command module."""

import subprocess
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from dbx_python_cli.cli import app

runner = CliRunner()


@pytest.fixture
def temp_config_dir(tmp_path):
    """Create a temporary config directory."""
    config_dir = tmp_path / ".config" / "dbx-python-cli"
    config_dir.mkdir(parents=True)
    return config_dir


@pytest.fixture
def temp_repos_dir(tmp_path):
    """Create a temporary repos directory."""
    repos_dir = tmp_path / "repos"
    repos_dir.mkdir(parents=True)
    return repos_dir


@pytest.fixture
def mock_config(temp_config_dir, temp_repos_dir):
    """Create a mock config file."""
    config_path = temp_config_dir / "config.toml"
    # Convert path to use forward slashes for TOML compatibility on Windows
    repos_dir_str = str(temp_repos_dir).replace("\\", "/")
    config_content = f"""
[repo]
base_dir = "{repos_dir_str}"

[repo.groups.test]
repos = [
    "https://github.com/test/repo1.git",
    "https://github.com/test/repo2.git",
]
"""
    config_path.write_text(config_content)
    return config_path


def test_repo_help():
    """Test that the clone and sync commands are available."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "clone" in result.stdout
    assert "sync" in result.stdout


def test_repo_list_no_repos():
    """Test that 'dbx list' shows message when no repos are cloned."""
    with patch("dbx_python_cli.commands.list.get_config") as mock_config:
        with patch("dbx_python_cli.commands.list.list_repos") as mock_find:
            mock_config.return_value = {"repo": {"base_dir": "/tmp/test"}}
            mock_find.return_value = ""
            result = runner.invoke(app, ["list"])
            assert result.exit_code == 0
            assert "No repositories found" in result.stdout
            assert "Base directory:" in result.stdout


def test_repo_list_with_repos():
    """Test that 'dbx list' lists all cloned repositories."""
    with patch("dbx_python_cli.commands.list.get_config") as mock_config:
        with patch("dbx_python_cli.commands.list.list_repos") as mock_find:
            mock_config.return_value = {"repo": {"base_dir": "/tmp/test"}}
            mock_find.return_value = (
                "├── django/\n│   └── ✓ django\n"
                "├── pymongo/\n│   └── ✓ mongo-python-driver"
            )
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


def test_repo_list_long_form():
    """Test that 'dbx list' works (long form test)."""
    with patch("dbx_python_cli.commands.list.get_config") as mock_config:
        with patch("dbx_python_cli.commands.list.list_repos") as mock_find:
            mock_config.return_value = {"repo": {"base_dir": "/tmp/test"}}
            mock_find.return_value = ""
            result = runner.invoke(app, ["list"])
            assert result.exit_code == 0
            assert "No repositories found" in result.stdout


def test_repo_init_creates_config(tmp_path):
    """Test that config init creates a config file."""
    with patch("dbx_python_cli.commands.config.get_config_path") as mock_get_path:
        config_path = tmp_path / "config.toml"
        mock_get_path.return_value = config_path

        result = runner.invoke(app, ["config", "init"])
        assert result.exit_code == 0
        assert config_path.exists()
        assert "Configuration file created" in result.stdout


def test_repo_init_existing_config_no_overwrite(tmp_path):
    """Test that config init doesn't overwrite existing config without confirmation."""
    with patch("dbx_python_cli.commands.config.get_config_path") as mock_get_path:
        config_path = tmp_path / "config.toml"
        config_path.write_text("existing content")
        mock_get_path.return_value = config_path

        # Simulate user saying "no" to overwrite
        result = runner.invoke(app, ["config", "init"], input="n\n")
        assert result.exit_code == 0
        assert "already exists" in result.stdout
        assert "Aborted" in result.stdout


def test_repo_init_existing_config_with_yes_flag(tmp_path):
    """Test that config init --yes overwrites existing config without prompting."""
    with patch("dbx_python_cli.commands.config.get_config_path") as mock_get_path:
        config_path = tmp_path / "config.toml"
        config_path.write_text("existing content")
        mock_get_path.return_value = config_path

        # Use --yes flag to skip confirmation
        result = runner.invoke(app, ["config", "init", "--yes"])
        assert result.exit_code == 0
        assert "Configuration file created" in result.stdout
        # Should not contain "Aborted" since we skipped the prompt
        assert "Aborted" not in result.stdout


def test_repo_init_with_remove_base_dir(tmp_path):
    """Test that config init --remove-base-dir removes the base_dir directory."""
    with patch("dbx_python_cli.commands.config.get_config_path") as mock_get_path:
        config_path = tmp_path / "config.toml"
        mock_get_path.return_value = config_path

        # Create a base_dir directory to be removed
        base_dir = tmp_path / "test_base_dir"
        base_dir.mkdir()
        (base_dir / "test_file.txt").write_text("test content")

        # Patch the default config to use our test base_dir
        with patch(
            "dbx_python_cli.commands.config.get_default_config_path"
        ) as mock_default:
            default_config = tmp_path / "default_config.toml"
            # Convert path to use forward slashes for TOML compatibility on Windows
            base_dir_str = str(base_dir).replace("\\", "/")
            default_config.write_text(f"""
[repo]
base_dir = "{base_dir_str}"
fork_user = "testuser"

[repo.groups.test]
repos = ["https://github.com/test/repo.git"]
""")
            mock_default.return_value = default_config

            # Verify base_dir exists before
            assert base_dir.exists()

            # Use --remove-base-dir flag with --yes to skip confirmation
            result = runner.invoke(
                app, ["config", "init", "--remove-base-dir", "--yes"]
            )
            assert result.exit_code == 0
            assert config_path.exists()
            assert "Configuration file created" in result.stdout
            assert "Removed directory" in result.stdout

            # Verify base_dir was removed from filesystem
            assert not base_dir.exists()


def test_config_show_displays_test_runner(tmp_path):
    """Test that config show displays custom test runner configuration."""
    config_path = tmp_path / "config.toml"
    repos_dir_str = str(tmp_path / "repos").replace("\\", "/")
    config_content = f"""
[repo]
base_dir = "{repos_dir_str}"

[repo.groups.django]
repos = [
    "git@github.com:django/django.git",
]

[repo.groups.django.test_runner]
django = "tests/runtests.py"

[repo.groups.pymongo]
repos = [
    "git@github.com:mongodb/mongo-python-driver.git",
]
"""
    config_path.write_text(config_content)

    with patch("dbx_python_cli.commands.config.get_config_path") as mock_get_path:
        mock_get_path.return_value = config_path

        result = runner.invoke(app, ["config", "show"])
        assert result.exit_code == 0
        assert "Test runner:" in result.stdout
        assert "django: tests/runtests.py" in result.stdout
        # pymongo group should not show test runners since it doesn't have any
        assert "pymongo" in result.stdout


def test_config_show_displays_install_dirs(tmp_path):
    """Test that config show displays install_dirs configuration."""
    config_path = tmp_path / "config.toml"
    repos_dir_str = str(tmp_path / "repos").replace("\\", "/")
    config_content = f"""
[repo]
base_dir = "{repos_dir_str}"

[repo.groups.langchain]
repos = [
    "git@github.com:langchain-ai/langchain-mongodb.git",
]

[repo.groups.langchain.install_dirs]
langchain-mongodb = [
    "libs/langchain-mongodb/",
    "libs/langgraph-checkpoint-mongodb/",
]
"""
    config_path.write_text(config_content)

    with patch("dbx_python_cli.commands.config.get_config_path") as mock_get_path:
        mock_get_path.return_value = config_path

        result = runner.invoke(app, ["config", "show"])
        assert result.exit_code == 0
        assert "Install dirs:" in result.stdout
        assert "langchain-mongodb:" in result.stdout
        assert "libs/langchain-mongodb/" in result.stdout
        assert "libs/langgraph-checkpoint-mongodb/" in result.stdout


def test_config_show_displays_test_env(tmp_path):
    """Test that config show displays test environment variables configuration."""
    config_path = tmp_path / "config.toml"
    repos_dir_str = str(tmp_path / "repos").replace("\\", "/")
    config_content = f"""
[repo]
base_dir = "{repos_dir_str}"

[repo.groups.pymongo]
repos = [
    "git@github.com:mongodb/mongo-python-driver.git",
]

[repo.groups.pymongo.test_env]
mongo-python-driver = {{ DRIVERS_TOOLS = "{{base_dir}}/{{group}}/drivers-evergreen-tools", TEST_VAR = "test_value" }}
"""
    config_path.write_text(config_content)

    with patch("dbx_python_cli.commands.config.get_config_path") as mock_get_path:
        with patch("dbx_python_cli.utils.repo.get_config_path") as mock_get_path2:
            mock_get_path.return_value = config_path
            mock_get_path2.return_value = config_path

            result = runner.invoke(app, ["config", "show"])
            assert result.exit_code == 0
            assert "Test env:" in result.stdout
            assert "mongo-python-driver:" in result.stdout
            assert (
                "DRIVERS_TOOLS={base_dir}/{group}/drivers-evergreen-tools"
                in result.stdout
            )
            assert "TEST_VAR=test_value" in result.stdout


def test_repo_clone_help():
    """Test that the repo clone help command works."""
    result = runner.invoke(app, ["clone", "--help"])
    assert result.exit_code == 0
    assert "Clone repositories" in result.stdout


def test_repo_clone_invalid_group(tmp_path, mock_config):
    """Test that repo clone fails with invalid group."""
    with patch("dbx_python_cli.utils.repo.get_config_path") as mock_get_path:
        mock_get_path.return_value = mock_config

        result = runner.invoke(app, ["clone", "-g", "nonexistent"])
        assert result.exit_code == 1
        output = result.stdout + result.stderr
        assert "Group 'nonexistent' not found" in output


def test_repo_clone_success(tmp_path, mock_config, temp_repos_dir):
    """Test successful repo clone."""
    with patch("dbx_python_cli.utils.repo.get_config_path") as mock_get_path:
        with patch("dbx_python_cli.commands.clone.subprocess.run") as mock_run:
            mock_get_path.return_value = mock_config
            mock_run.return_value = MagicMock(returncode=0)

            result = runner.invoke(app, ["clone", "-g", "test"])
            assert result.exit_code == 0
            assert "Cloning 2 repository(ies)" in result.stdout
            assert "test" in result.stdout


def test_repo_clone_creates_group_directory(tmp_path, mock_config, temp_repos_dir):
    """Test that repo clone creates group subdirectory."""
    with patch("dbx_python_cli.utils.repo.get_config_path") as mock_get_path:
        with patch("dbx_python_cli.commands.clone.subprocess.run") as mock_run:
            mock_get_path.return_value = mock_config
            mock_run.return_value = MagicMock(returncode=0)

            result = runner.invoke(app, ["clone", "-g", "test"])
            assert result.exit_code == 0

            # Check that group directory was created
            group_dir = temp_repos_dir / "test"
            assert group_dir.exists()
            assert group_dir.is_dir()


def test_repo_clone_skips_existing(tmp_path, mock_config, temp_repos_dir):
    """Test that repo clone skips existing repositories."""
    with patch("dbx_python_cli.utils.repo.get_config_path") as mock_get_path:
        mock_get_path.return_value = mock_config

        # Create existing repo
        group_dir = temp_repos_dir / "test"
        group_dir.mkdir(parents=True)
        existing_repo = group_dir / "repo1"
        existing_repo.mkdir()

        with patch("dbx_python_cli.commands.clone.subprocess.run"):
            result = runner.invoke(app, ["clone", "-g", "test"])
            assert result.exit_code == 0
            assert "already exists" in result.stdout


def test_repo_clone_git_failure(mock_config, temp_repos_dir):
    """Test that repo clone handles git clone failures gracefully."""
    import subprocess

    with patch("dbx_python_cli.utils.repo.get_config_path") as mock_get_path:
        mock_get_path.return_value = mock_config

        # Mock subprocess.run to raise CalledProcessError
        with patch("dbx_python_cli.commands.clone.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(
                1, "git clone", stderr="fatal: repository not found"
            )
            result = runner.invoke(app, ["clone", "-g", "test"])
            # Should still exit 0 (doesn't fail the whole command)
            assert result.exit_code == 0
            # Check stderr for error message
            output = result.stdout + result.stderr
            assert "Failed to clone" in output


def test_repo_clone_empty_repos_list(temp_config_dir, temp_repos_dir):
    """Test that repo clone handles groups with no repos defined."""
    config_path = temp_config_dir / "config.toml"
    repos_dir_str = str(temp_repos_dir).replace("\\", "/")
    config_content = f"""
[repo]
base_dir = "{repos_dir_str}"

[repo.groups.empty]
repos = []
"""
    config_path.write_text(config_content)

    with patch("dbx_python_cli.utils.repo.get_config_path") as mock_get_path:
        mock_get_path.return_value = config_path
        result = runner.invoke(app, ["clone", "-g", "empty"])
        assert result.exit_code == 1
        # Check both stdout and stderr
        output = result.stdout + result.stderr
        assert "No repositories found in group 'empty'" in output


def test_get_config_fallback_to_default(temp_config_dir):
    """Test that get_config falls back to default config when user config doesn't exist."""
    from dbx_python_cli.utils.repo import get_config

    # Don't create user config, should fall back to package default
    with patch("dbx_python_cli.utils.repo.get_config_path") as mock_get_path:
        # Point to non-existent user config
        mock_get_path.return_value = temp_config_dir / "nonexistent.toml"
        config = get_config()
        # Should have loaded the default config which has repo.groups structure
        assert "repo" in config
        assert "groups" in config["repo"]
        assert "pymongo" in config["repo"]["groups"]


def test_repo_clone_no_group_shows_error(mock_config):
    """Test that repo clone without -g shows help."""
    with patch("dbx_python_cli.utils.repo.get_config_path") as mock_get_path:
        mock_get_path.return_value = mock_config

        result = runner.invoke(app, ["clone"])
        # With no_args_is_help=True, shows help with exit code 2
        assert result.exit_code == 2
        output = result.stdout + result.stderr
        assert "Clone repositories" in output


def test_repo_clone_multiple_groups(tmp_path, temp_repos_dir):
    """Test cloning multiple groups at once."""
    config_path = tmp_path / ".config" / "dbx-python-cli" / "config.toml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    repos_dir_str = str(temp_repos_dir).replace("\\", "/")
    config_content = f"""
[repo]
base_dir = "{repos_dir_str}"

[repo.groups.django]
repos = [
    "https://github.com/django/django.git",
]

[repo.groups.pymongo]
repos = [
    "https://github.com/mongodb/mongo-python-driver.git",
]
"""
    config_path.write_text(config_content)

    with patch("dbx_python_cli.utils.repo.get_config_path") as mock_get_path:
        with patch("dbx_python_cli.commands.clone.subprocess.run") as mock_run:
            mock_get_path.return_value = config_path
            mock_run.return_value = MagicMock(returncode=0)

            result = runner.invoke(app, ["clone", "-g", "django", "-g", "pymongo"])
            assert result.exit_code == 0

            # Check that both groups are mentioned in output
            assert "django" in result.stdout
            assert "pymongo" in result.stdout

            # Check that both group directories were created
            django_dir = temp_repos_dir / "django"
            pymongo_dir = temp_repos_dir / "pymongo"
            assert django_dir.exists()
            assert pymongo_dir.exists()

            # Verify git clone was called for both repos
            clone_calls = [
                call for call in mock_run.call_args_list if call[0][0][1] == "clone"
            ]
            assert len(clone_calls) == 2

            # Check that the final summary message appears for multiple groups
            assert "All done!" in result.stdout
            assert "2 groups" in result.stdout


def test_repo_clone_multiple_groups_csv(tmp_path, temp_repos_dir):
    """Test cloning multiple groups using comma-separated values."""
    config_path = tmp_path / ".config" / "dbx-python-cli" / "config.toml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    repos_dir_str = str(temp_repos_dir).replace("\\", "/")
    config_content = f"""
[repo]
base_dir = "{repos_dir_str}"

[repo.groups.django]
repos = [
    "https://github.com/django/django.git",
]

[repo.groups.pymongo]
repos = [
    "https://github.com/mongodb/mongo-python-driver.git",
]
"""
    config_path.write_text(config_content)

    with patch("dbx_python_cli.utils.repo.get_config_path") as mock_get_path:
        with patch("dbx_python_cli.commands.clone.subprocess.run") as mock_run:
            mock_get_path.return_value = config_path
            mock_run.return_value = MagicMock(returncode=0)

            # Test CSV format: -g django,pymongo
            result = runner.invoke(app, ["clone", "-g", "django,pymongo"])
            assert result.exit_code == 0

            # Check that both groups are mentioned in output
            assert "django" in result.stdout
            assert "pymongo" in result.stdout

            # Check that both group directories were created
            django_dir = temp_repos_dir / "django"
            pymongo_dir = temp_repos_dir / "pymongo"
            assert django_dir.exists()
            assert pymongo_dir.exists()

            # Verify git clone was called for both repos
            clone_calls = [
                call for call in mock_run.call_args_list if call[0][0][1] == "clone"
            ]
            assert len(clone_calls) == 2

            # Check that the final summary message appears for multiple groups
            assert "All done!" in result.stdout
            assert "2 groups" in result.stdout


def test_repo_clone_single_repo_by_name(tmp_path, temp_repos_dir):
    """Test cloning a single repository by name."""
    config_path = tmp_path / ".config" / "dbx-python-cli" / "config.toml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    repos_dir_str = str(temp_repos_dir).replace("\\", "/")
    config_content = f"""
[repo]
base_dir = "{repos_dir_str}"

[repo.groups.django]
repos = [
    "git@github.com:mongodb-labs/django-mongodb-backend.git",
    "git@github.com:mongodb-labs/django-mongodb-extensions.git",
]

[repo.groups.pymongo]
repos = [
    "git@github.com:mongodb/mongo-python-driver.git",
]
"""
    config_path.write_text(config_content)

    with patch("dbx_python_cli.utils.repo.get_config_path") as mock_get_path:
        with patch("dbx_python_cli.commands.clone.subprocess.run") as mock_run:
            mock_get_path.return_value = config_path
            mock_run.return_value = MagicMock(returncode=0)

            result = runner.invoke(app, ["clone", "django-mongodb-backend"])
            assert result.exit_code == 0
            assert "django-mongodb-backend" in result.stdout

            # Verify git clone was called
            clone_calls = [
                call for call in mock_run.call_args_list if call[0][0][1] == "clone"
            ]
            assert len(clone_calls) == 1
            assert "django-mongodb-backend.git" in clone_calls[0][0][0][2]


def test_repo_clone_single_repo_not_found(tmp_path, temp_repos_dir):
    """Test cloning a repository that doesn't exist."""
    config_path = tmp_path / ".config" / "dbx-python-cli" / "config.toml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    repos_dir_str = str(temp_repos_dir).replace("\\", "/")
    config_content = f"""
[repo]
base_dir = "{repos_dir_str}"

[repo.groups.django]
repos = [
    "git@github.com:mongodb-labs/django-mongodb-backend.git",
]
"""
    config_path.write_text(config_content)

    with patch("dbx_python_cli.utils.repo.get_config_path") as mock_get_path:
        mock_get_path.return_value = config_path

        result = runner.invoke(app, ["clone", "nonexistent-repo"])
        assert result.exit_code == 1
        output = result.stdout + result.stderr
        assert "not found in any group" in output


def test_repo_clone_single_repo_with_fork(tmp_path, temp_repos_dir):
    """Test cloning a single repository with --fork-user <username> flag."""
    config_path = tmp_path / ".config" / "dbx-python-cli" / "config.toml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    repos_dir_str = str(temp_repos_dir).replace("\\", "/")
    config_content = f"""
[repo]
base_dir = "{repos_dir_str}"

[repo.groups.django]
repos = [
    "git@github.com:mongodb-labs/django-mongodb-backend.git",
]
"""
    config_path.write_text(config_content)

    with patch("dbx_python_cli.utils.repo.get_config_path") as mock_get_path:
        with patch("dbx_python_cli.commands.clone.subprocess.run") as mock_run:
            mock_get_path.return_value = config_path
            mock_run.return_value = MagicMock(returncode=0)

            # Options must come before positional arguments with allow_interspersed_args=False
            result = runner.invoke(
                app, ["clone", "--fork-user", "aclark4life", "django-mongodb-backend"]
            )
            assert result.exit_code == 0
            assert "aclark4life's fork" in result.stdout

            # Verify git clone was called with fork URL
            clone_calls = [
                call for call in mock_run.call_args_list if call[0][0][1] == "clone"
            ]
            assert len(clone_calls) == 1
            assert "aclark4life/django-mongodb-backend.git" in clone_calls[0][0][0][2]

            # Verify upstream remote was added
            remote_calls = [
                call for call in mock_run.call_args_list if "remote" in call[0][0]
            ]
            assert len(remote_calls) == 1


def test_repo_clone_with_fork_user(tmp_path, temp_repos_dir):
    """Test cloning with --fork-user <username> flag and explicit username."""
    config_path = tmp_path / ".config" / "dbx-python-cli" / "config.toml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    repos_dir_str = str(temp_repos_dir).replace("\\", "/")
    config_content = f"""
[repo]
base_dir = "{repos_dir_str}"

[repo.groups.test]
repos = [
    "git@github.com:mongodb/mongo-python-driver.git",
]
"""
    config_path.write_text(config_content)

    with patch("dbx_python_cli.utils.repo.get_config_path") as mock_get_path:
        with patch("dbx_python_cli.commands.clone.subprocess.run") as mock_run:
            mock_get_path.return_value = config_path
            mock_run.return_value = MagicMock(returncode=0)

            result = runner.invoke(
                app, ["clone", "-g", "test", "--fork-user", "aclark4life"]
            )
            assert result.exit_code == 0
            assert "aclark4life's fork" in result.stdout

            # Verify git clone was called with fork URL
            clone_calls = [
                call for call in mock_run.call_args_list if call[0][0][1] == "clone"
            ]
            assert len(clone_calls) == 1
            assert "aclark4life/mongo-python-driver.git" in clone_calls[0][0][0][2]

            # Verify upstream remote was added
            remote_calls = [
                call for call in mock_run.call_args_list if "remote" in call[0][0]
            ]
            assert len(remote_calls) == 1
            remote_cmd = remote_calls[0][0][0]
            assert "add" in remote_cmd
            assert "upstream" in remote_cmd
            assert "git@github.com:mongodb/mongo-python-driver.git" in remote_cmd


def test_repo_clone_with_fork_from_config(tmp_path, temp_repos_dir):
    """Test cloning with --fork flag using fork_user from config."""
    config_path = tmp_path / ".config" / "dbx-python-cli" / "config.toml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    repos_dir_str = str(temp_repos_dir).replace("\\", "/")
    config_content = f"""
[repo]
base_dir = "{repos_dir_str}"
fork_user = "aclark4life"

[repo.groups.test]
repos = [
    "git@github.com:mongodb/mongo-python-driver.git",
]
"""
    config_path.write_text(config_content)

    with patch("dbx_python_cli.utils.repo.get_config_path") as mock_get_path:
        with patch("dbx_python_cli.commands.clone.subprocess.run") as mock_run:
            mock_get_path.return_value = config_path
            mock_run.return_value = MagicMock(returncode=0)

            # Use --fork to use config default
            result = runner.invoke(app, ["clone", "-g", "test", "--fork"])
            assert result.exit_code == 0
            assert "aclark4life's fork" in result.stdout


def test_repo_clone_fork_without_config_shows_warning(tmp_path, temp_repos_dir):
    """Test that --fork without config fork_user shows warning and falls back to upstream clone."""
    config_path = tmp_path / ".config" / "dbx-python-cli" / "config.toml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    repos_dir_str = str(temp_repos_dir).replace("\\", "/")
    config_content = f"""
[repo]
base_dir = "{repos_dir_str}"

[repo.groups.test]
repos = [
    "git@github.com:mongodb/mongo-python-driver.git",
]
"""
    config_path.write_text(config_content)

    with patch("dbx_python_cli.utils.repo.get_config_path") as mock_get_path:
        with patch("dbx_python_cli.commands.clone.subprocess.run") as mock_run:
            mock_get_path.return_value = config_path
            mock_run.return_value = MagicMock(returncode=0)

            result = runner.invoke(app, ["clone", "-g", "test", "--fork"])
            assert result.exit_code == 0

            # Verify warning message is shown (in stderr or combined output)
            combined_output = result.stdout + result.stderr
            assert (
                "Warning: --fork is enabled but fork_user is not set in config"
                in combined_output
            )

            # Verify git clone was called with upstream URL (not a fork)
            clone_calls = [
                call for call in mock_run.call_args_list if call[0][0][1] == "clone"
            ]
            assert len(clone_calls) == 1
            # Should clone from upstream (mongodb/mongo-python-driver), not a fork
            assert "mongodb/mongo-python-driver.git" in clone_calls[0][0][0][2]


def test_repo_clone_fork_https_url(tmp_path, temp_repos_dir):
    """Test cloning with --fork-user <username> flag using HTTPS URL."""
    config_path = tmp_path / ".config" / "dbx-python-cli" / "config.toml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    repos_dir_str = str(temp_repos_dir).replace("\\", "/")
    config_content = f"""
[repo]
base_dir = "{repos_dir_str}"

[repo.groups.test]
repos = [
    "https://github.com/mongodb/mongo-python-driver.git",
]
"""
    config_path.write_text(config_content)

    with patch("dbx_python_cli.utils.repo.get_config_path") as mock_get_path:
        with patch("dbx_python_cli.commands.clone.subprocess.run") as mock_run:
            mock_get_path.return_value = config_path
            mock_run.return_value = MagicMock(returncode=0)

            result = runner.invoke(
                app, ["clone", "-g", "test", "--fork-user", "aclark4life"]
            )
            assert result.exit_code == 0

            # Verify git clone was called with fork URL (HTTPS format)
            clone_calls = [
                call for call in mock_run.call_args_list if call[0][0][1] == "clone"
            ]
            assert len(clone_calls) == 1
            assert "aclark4life/mongo-python-driver.git" in clone_calls[0][0][0][2]


def test_repo_clone_fork_fallback_when_fork_not_found(tmp_path, temp_repos_dir):
    """Test that clone falls back to upstream when fork doesn't exist."""
    config_path = tmp_path / ".config" / "dbx-python-cli" / "config.toml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    repos_dir_str = str(temp_repos_dir).replace("\\", "/")
    config_content = f"""
[repo]
base_dir = "{repos_dir_str}"

[repo.groups.test]
repos = [
    "git@github.com:mongodb/mongo-python-driver.git",
]
"""
    config_path.write_text(config_content)

    with patch("dbx_python_cli.utils.repo.get_config_path") as mock_get_path:
        with patch("dbx_python_cli.commands.clone.subprocess.run") as mock_run:
            mock_get_path.return_value = config_path

            # Simulate fork clone failing, upstream clone succeeding
            def run_side_effect(*args, **kwargs):
                cmd = args[0]
                if cmd[1] == "clone":
                    clone_url = cmd[2]
                    # Fork clone fails
                    if "aclark4life" in clone_url:
                        raise subprocess.CalledProcessError(
                            128, cmd, stderr="Repository not found"
                        )
                    # Upstream clone succeeds
                    return MagicMock(returncode=0)
                # Other commands (remote add, venv, etc.) succeed
                return MagicMock(returncode=0)

            mock_run.side_effect = run_side_effect

            result = runner.invoke(
                app, ["clone", "-g", "test", "--fork-user", "aclark4life"]
            )
            assert result.exit_code == 0

            # Verify both fork and upstream clone were attempted
            clone_calls = [
                call for call in mock_run.call_args_list if call[0][0][1] == "clone"
            ]
            assert len(clone_calls) == 2
            # First attempt should be fork
            assert "aclark4life/mongo-python-driver.git" in clone_calls[0][0][0][2]
            # Second attempt should be upstream
            assert "mongodb/mongo-python-driver.git" in clone_calls[1][0][0][2]

            # Verify success message mentions fork not found
            assert "fork not found" in result.stdout


def test_repo_sync_help():
    """Test that the repo sync help command works."""
    result = runner.invoke(app, ["sync", "--help"])
    assert result.exit_code == 0
    assert "Sync repositories with upstream" in result.stdout


def test_repo_sync_single_repo(tmp_path, temp_repos_dir):
    """Test syncing a single repository."""
    config_path = tmp_path / ".config" / "dbx-python-cli" / "config.toml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    repos_dir_str = str(temp_repos_dir).replace("\\", "/")
    config_content = f"""
[repo]
base_dir = "{repos_dir_str}"

[repo.groups.test]
repos = [
    "git@github.com:mongodb/mongo-python-driver.git",
]
"""
    config_path.write_text(config_content)

    # Create mock repository
    group_dir = temp_repos_dir / "test"
    repo_dir = group_dir / "mongo-python-driver"
    repo_dir.mkdir(parents=True)
    (repo_dir / ".git").mkdir()

    with patch("dbx_python_cli.utils.repo.get_config_path") as mock_get_path:
        with patch("dbx_python_cli.commands.sync.subprocess.run") as mock_run:
            mock_get_path.return_value = config_path

            # Mock git commands
            def mock_run_side_effect(*args, **kwargs):
                cmd = args[0]
                if "remote" in cmd and "add" not in cmd:
                    # git remote command (list remotes)
                    result = subprocess.CompletedProcess(
                        cmd, 0, stdout="origin\nupstream\n", stderr=""
                    )
                    return result
                elif "branch" in cmd and "--show-current" in cmd:
                    # git branch --show-current
                    result = subprocess.CompletedProcess(
                        cmd, 0, stdout="main\n", stderr=""
                    )
                    return result
                else:
                    # Other commands (fetch, rebase, push)
                    result = subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
                    return result

            mock_run.side_effect = mock_run_side_effect

            result = runner.invoke(app, ["sync", "mongo-python-driver"])
            assert result.exit_code == 0
            assert "Syncing mongo-python-driver" in result.stdout
            assert "Synced and pushed successfully" in result.stdout

            # Verify git commands were called
            calls = mock_run.call_args_list
            # Should have: remote, branch --show-current, fetch, rebase, push
            assert len(calls) >= 5

            # Verify push was called
            push_calls = [call for call in calls if "push" in call[0][0]]
            assert len(push_calls) == 1
            assert "origin" in push_calls[0][0][0]
            assert "main" in push_calls[0][0][0]


def test_repo_sync_dot_from_repo_root(tmp_path, temp_repos_dir, monkeypatch):
    """Test syncing with '.' resolves to the repo at the current directory."""
    config_path = tmp_path / ".config" / "dbx-python-cli" / "config.toml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    repos_dir_str = str(temp_repos_dir).replace("\\", "/")
    config_content = f"""
[repo]
base_dir = "{repos_dir_str}"

[repo.groups.test]
repos = [
    "git@github.com:mongodb/mongo-python-driver.git",
]
"""
    config_path.write_text(config_content)

    # Create mock repository
    group_dir = temp_repos_dir / "test"
    repo_dir = group_dir / "mongo-python-driver"
    repo_dir.mkdir(parents=True)
    (repo_dir / ".git").mkdir()

    # Change into the repo root so that "." resolves to it
    monkeypatch.chdir(repo_dir)

    with patch("dbx_python_cli.utils.repo.get_config_path") as mock_get_path:
        with patch("dbx_python_cli.commands.sync.subprocess.run") as mock_run:
            mock_get_path.return_value = config_path

            def mock_run_side_effect(*args, **kwargs):
                cmd = args[0]
                if "remote" in cmd and "add" not in cmd:
                    return subprocess.CompletedProcess(
                        cmd, 0, stdout="origin\nupstream\n", stderr=""
                    )
                elif "branch" in cmd and "--show-current" in cmd:
                    return subprocess.CompletedProcess(cmd, 0, stdout="main\n", stderr="")
                else:
                    return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

            mock_run.side_effect = mock_run_side_effect

            result = runner.invoke(app, ["sync", "."])
            assert result.exit_code == 0
            assert "Syncing mongo-python-driver" in result.stdout
            assert "Synced and pushed successfully" in result.stdout


def test_repo_sync_dot_from_repo_subdirectory(tmp_path, temp_repos_dir, monkeypatch):
    """Test that '.' resolves correctly when run from inside a repo subdirectory."""
    config_path = tmp_path / ".config" / "dbx-python-cli" / "config.toml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    repos_dir_str = str(temp_repos_dir).replace("\\", "/")
    config_content = f"""
[repo]
base_dir = "{repos_dir_str}"

[repo.groups.test]
repos = [
    "git@github.com:mongodb/mongo-python-driver.git",
]
"""
    config_path.write_text(config_content)

    # Create mock repository with a subdirectory
    group_dir = temp_repos_dir / "test"
    repo_dir = group_dir / "mongo-python-driver"
    subdir = repo_dir / "src" / "pymongo"
    subdir.mkdir(parents=True)
    (repo_dir / ".git").mkdir()

    # Change into a subdirectory of the repo
    monkeypatch.chdir(subdir)

    with patch("dbx_python_cli.utils.repo.get_config_path") as mock_get_path:
        with patch("dbx_python_cli.commands.sync.subprocess.run") as mock_run:
            mock_get_path.return_value = config_path

            def mock_run_side_effect(*args, **kwargs):
                cmd = args[0]
                if "remote" in cmd and "add" not in cmd:
                    return subprocess.CompletedProcess(
                        cmd, 0, stdout="origin\nupstream\n", stderr=""
                    )
                elif "branch" in cmd and "--show-current" in cmd:
                    return subprocess.CompletedProcess(cmd, 0, stdout="main\n", stderr="")
                else:
                    return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

            mock_run.side_effect = mock_run_side_effect

            result = runner.invoke(app, ["sync", "."])
            assert result.exit_code == 0
            assert "Syncing mongo-python-driver" in result.stdout
            assert "Synced and pushed successfully" in result.stdout


def test_repo_sync_dot_not_in_managed_repo(tmp_path, temp_repos_dir, monkeypatch):
    """Test that '.' in an unmanaged directory gives a clear error."""
    config_path = tmp_path / ".config" / "dbx-python-cli" / "config.toml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    repos_dir_str = str(temp_repos_dir).replace("\\", "/")
    config_content = f"""
[repo]
base_dir = "{repos_dir_str}"

[repo.groups.test]
repos = [
    "git@github.com:mongodb/mongo-python-driver.git",
]
"""
    config_path.write_text(config_content)

    # Change into a directory that is NOT a managed repo
    unrelated_dir = tmp_path / "unrelated"
    unrelated_dir.mkdir()
    monkeypatch.chdir(unrelated_dir)

    with patch("dbx_python_cli.utils.repo.get_config_path") as mock_get_path:
        mock_get_path.return_value = config_path

        result = runner.invoke(app, ["sync", "."])
        assert result.exit_code == 1
        output = result.stdout + result.stderr
        assert "No managed repository found" in output


def test_repo_sync_group(tmp_path, temp_repos_dir):
    """Test syncing all repositories in a group."""
    config_path = tmp_path / ".config" / "dbx-python-cli" / "config.toml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    repos_dir_str = str(temp_repos_dir).replace("\\", "/")
    config_content = f"""
[repo]
base_dir = "{repos_dir_str}"

[repo.groups.test]
repos = [
    "git@github.com:mongodb/mongo-python-driver.git",
    "git@github.com:mongodb/specifications.git",
]
"""
    config_path.write_text(config_content)

    # Create mock repositories
    group_dir = temp_repos_dir / "test"
    for repo_name in ["mongo-python-driver", "specifications"]:
        repo_dir = group_dir / repo_name
        repo_dir.mkdir(parents=True)
        (repo_dir / ".git").mkdir()

    with patch("dbx_python_cli.utils.repo.get_config_path") as mock_get_path:
        with patch("dbx_python_cli.commands.sync.subprocess.run") as mock_run:
            mock_get_path.return_value = config_path

            # Mock git commands
            def mock_run_side_effect(*args, **kwargs):
                cmd = args[0]
                if "remote" in cmd and "add" not in cmd:
                    result = subprocess.CompletedProcess(
                        cmd, 0, stdout="origin\nupstream\n", stderr=""
                    )
                    return result
                elif "branch" in cmd and "--show-current" in cmd:
                    result = subprocess.CompletedProcess(
                        cmd, 0, stdout="main\n", stderr=""
                    )
                    return result
                else:
                    result = subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
                    return result

            mock_run.side_effect = mock_run_side_effect

            result = runner.invoke(app, ["sync", "-g", "test"])
            assert result.exit_code == 0
            assert "Syncing 2 repository(ies)" in result.stdout
            assert "mongo-python-driver" in result.stdout
            assert "specifications" in result.stdout
            assert "Synced and pushed successfully" in result.stdout

            # Verify push was called for both repos
            calls = mock_run.call_args_list
            push_calls = [call for call in calls if "push" in call[0][0]]
            assert len(push_calls) == 2  # One for each repo


def test_repo_sync_no_upstream_remote(tmp_path, temp_repos_dir):
    """Test syncing a repository without upstream remote."""
    config_path = tmp_path / ".config" / "dbx-python-cli" / "config.toml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    repos_dir_str = str(temp_repos_dir).replace("\\", "/")
    config_content = f"""
[repo]
base_dir = "{repos_dir_str}"

[repo.groups.test]
repos = [
    "git@github.com:mongodb/mongo-python-driver.git",
]
"""
    config_path.write_text(config_content)

    # Create mock repository
    group_dir = temp_repos_dir / "test"
    repo_dir = group_dir / "mongo-python-driver"
    repo_dir.mkdir(parents=True)
    (repo_dir / ".git").mkdir()

    with patch("dbx_python_cli.utils.repo.get_config_path") as mock_get_path:
        with patch("dbx_python_cli.commands.sync.subprocess.run") as mock_run:
            mock_get_path.return_value = config_path

            # Mock git remote to return only origin (no upstream)
            def mock_run_side_effect(*args, **kwargs):
                cmd = args[0]
                if "remote" in cmd and "add" not in cmd:
                    result = subprocess.CompletedProcess(
                        cmd, 0, stdout="origin\n", stderr=""
                    )
                    return result
                else:
                    result = subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
                    return result

            mock_run.side_effect = mock_run_side_effect

            result = runner.invoke(app, ["sync", "mongo-python-driver"])
            assert result.exit_code == 0
            # The warning message goes to stderr
            output = result.stdout + result.stderr
            assert "No 'upstream' remote found" in output


def test_repo_sync_no_args_shows_error(tmp_path, temp_repos_dir):
    """Test that repo sync without args shows error."""
    config_path = tmp_path / ".config" / "dbx-python-cli" / "config.toml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    repos_dir_str = str(temp_repos_dir).replace("\\", "/")
    config_content = f"""
[repo]
base_dir = "{repos_dir_str}"

[repo.groups.test]
repos = []
"""
    config_path.write_text(config_content)

    with patch("dbx_python_cli.utils.repo.get_config_path") as mock_get_path:
        mock_get_path.return_value = config_path

        result = runner.invoke(app, ["sync"])
        # With no_args_is_help=True, shows help with exit code 2
        assert result.exit_code == 2
        output = result.stdout + result.stderr
        assert "Sync repositories with upstream" in output


def test_repo_sync_feature_branch_to_upstream_main(tmp_path, temp_repos_dir):
    """Test syncing a feature branch rebases to upstream/main."""
    config_path = tmp_path / ".config" / "dbx-python-cli" / "config.toml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    repos_dir_str = str(temp_repos_dir).replace("\\", "/")
    config_content = f"""
[repo]
base_dir = "{repos_dir_str}"

[repo.groups.test]
repos = [
    "git@github.com:mongodb/mongo-python-driver.git",
]
"""
    config_path.write_text(config_content)

    # Create mock repository
    group_dir = temp_repos_dir / "test"
    repo_dir = group_dir / "mongo-python-driver"
    repo_dir.mkdir(parents=True)
    (repo_dir / ".git").mkdir()

    with patch("dbx_python_cli.utils.repo.get_config_path") as mock_get_path:
        with patch("dbx_python_cli.commands.sync.subprocess.run") as mock_run:
            mock_get_path.return_value = config_path

            # Mock git commands
            def mock_run_side_effect(*args, **kwargs):
                cmd = args[0]
                if "remote" in cmd and "add" not in cmd and "show" not in cmd:
                    # git remote command (list remotes)
                    result = subprocess.CompletedProcess(
                        cmd, 0, stdout="origin\nupstream\n", stderr=""
                    )
                    return result
                elif "branch" in cmd and "--show-current" in cmd:
                    # git branch --show-current - return feature branch
                    result = subprocess.CompletedProcess(
                        cmd, 0, stdout="feature-branch\n", stderr=""
                    )
                    return result
                elif "symbolic-ref" in cmd:
                    # git symbolic-ref refs/remotes/upstream/HEAD
                    result = subprocess.CompletedProcess(
                        cmd, 0, stdout="refs/remotes/upstream/main\n", stderr=""
                    )
                    return result
                elif "rebase" in cmd:
                    # Verify we're rebasing to upstream/main, not upstream/feature-branch
                    assert "upstream/main" in cmd
                    result = subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
                    return result
                else:
                    # Other commands (fetch, push)
                    result = subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
                    return result

            mock_run.side_effect = mock_run_side_effect

            result = runner.invoke(app, ["sync", "mongo-python-driver"])
            assert result.exit_code == 0
            assert "Syncing mongo-python-driver" in result.stdout
            assert "Synced and pushed successfully" in result.stdout

            # Verify rebase was called with upstream/main
            calls = mock_run.call_args_list
            rebase_calls = [call for call in calls if "rebase" in call[0][0]]
            assert len(rebase_calls) == 1
            assert "upstream/main" in rebase_calls[0][0][0]


def test_repo_sync_feature_branch_fallback_to_main(tmp_path, temp_repos_dir):
    """Test syncing a feature branch falls back to main when symbolic-ref fails."""
    config_path = tmp_path / ".config" / "dbx-python-cli" / "config.toml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    repos_dir_str = str(temp_repos_dir).replace("\\", "/")
    config_content = f"""
[repo]
base_dir = "{repos_dir_str}"

[repo.groups.test]
repos = [
    "git@github.com:mongodb/mongo-python-driver.git",
]
"""
    config_path.write_text(config_content)

    # Create mock repository
    group_dir = temp_repos_dir / "test"
    repo_dir = group_dir / "mongo-python-driver"
    repo_dir.mkdir(parents=True)
    (repo_dir / ".git").mkdir()

    with patch("dbx_python_cli.utils.repo.get_config_path") as mock_get_path:
        with patch("dbx_python_cli.commands.sync.subprocess.run") as mock_run:
            mock_get_path.return_value = config_path

            # Mock git commands
            def mock_run_side_effect(*args, **kwargs):
                cmd = args[0]
                if "remote" in cmd and "add" not in cmd and "show" not in cmd:
                    # git remote command (list remotes)
                    result = subprocess.CompletedProcess(
                        cmd, 0, stdout="origin\nupstream\n", stderr=""
                    )
                    return result
                elif "branch" in cmd and "--show-current" in cmd:
                    # git branch --show-current - return feature branch
                    result = subprocess.CompletedProcess(
                        cmd, 0, stdout="feature-branch\n", stderr=""
                    )
                    return result
                elif "symbolic-ref" in cmd:
                    # Fail symbolic-ref (upstream/HEAD not set)
                    raise subprocess.CalledProcessError(1, cmd, stderr="not found")
                elif "remote" in cmd and "show" in cmd:
                    # git remote show upstream - return main as default
                    result = subprocess.CompletedProcess(
                        cmd, 0, stdout="  HEAD branch: main\n", stderr=""
                    )
                    return result
                elif "rebase" in cmd:
                    # Verify we're rebasing to upstream/main
                    assert "upstream/main" in cmd
                    result = subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
                    return result
                else:
                    # Other commands (fetch, push)
                    result = subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
                    return result

            mock_run.side_effect = mock_run_side_effect

            result = runner.invoke(app, ["sync", "mongo-python-driver"])
            assert result.exit_code == 0
            assert "Syncing mongo-python-driver" in result.stdout
            assert "Synced and pushed successfully" in result.stdout

            # Verify rebase was called with upstream/main
            calls = mock_run.call_args_list
            rebase_calls = [call for call in calls if "rebase" in call[0][0]]
            assert len(rebase_calls) == 1
            assert "upstream/main" in rebase_calls[0][0][0]


def test_repo_sync_main_branch_to_upstream_main(tmp_path, temp_repos_dir):
    """Test syncing main branch still rebases to upstream/main (not changed)."""
    config_path = tmp_path / ".config" / "dbx-python-cli" / "config.toml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    repos_dir_str = str(temp_repos_dir).replace("\\", "/")
    config_content = f"""
[repo]
base_dir = "{repos_dir_str}"

[repo.groups.test]
repos = [
    "git@github.com:mongodb/mongo-python-driver.git",
]
"""
    config_path.write_text(config_content)

    # Create mock repository
    group_dir = temp_repos_dir / "test"
    repo_dir = group_dir / "mongo-python-driver"
    repo_dir.mkdir(parents=True)
    (repo_dir / ".git").mkdir()

    with patch("dbx_python_cli.utils.repo.get_config_path") as mock_get_path:
        with patch("dbx_python_cli.commands.sync.subprocess.run") as mock_run:
            mock_get_path.return_value = config_path

            # Mock git commands
            def mock_run_side_effect(*args, **kwargs):
                cmd = args[0]
                if "remote" in cmd and "add" not in cmd:
                    # git remote command (list remotes)
                    result = subprocess.CompletedProcess(
                        cmd, 0, stdout="origin\nupstream\n", stderr=""
                    )
                    return result
                elif "branch" in cmd and "--show-current" in cmd:
                    # git branch --show-current - return main
                    result = subprocess.CompletedProcess(
                        cmd, 0, stdout="main\n", stderr=""
                    )
                    return result
                elif "rebase" in cmd:
                    # Verify we're rebasing to upstream/main
                    assert "upstream/main" in cmd
                    result = subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
                    return result
                else:
                    # Other commands (fetch, push)
                    result = subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
                    return result

            mock_run.side_effect = mock_run_side_effect

            result = runner.invoke(app, ["sync", "mongo-python-driver"])
            assert result.exit_code == 0
            assert "Syncing mongo-python-driver" in result.stdout
            assert "Synced and pushed successfully" in result.stdout

            # Verify rebase was called with upstream/main
            calls = mock_run.call_args_list
            rebase_calls = [call for call in calls if "rebase" in call[0][0]]
            assert len(rebase_calls) == 1
            assert "upstream/main" in rebase_calls[0][0][0]


def test_repo_sync_single_repo_dry_run(tmp_path, temp_repos_dir):
    """Test syncing a single repository with --dry-run flag."""
    config_path = tmp_path / ".config" / "dbx-python-cli" / "config.toml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    repos_dir_str = str(temp_repos_dir).replace("\\", "/")
    config_content = f"""
[repo]
base_dir = "{repos_dir_str}"

[repo.groups.pymongo]
repos = ["git@github.com:mongodb/mongo-python-driver.git"]
"""
    config_path.write_text(config_content)

    # Create repo directory
    pymongo_dir = temp_repos_dir / "pymongo"
    pymongo_dir.mkdir()
    repo_dir = pymongo_dir / "mongo-python-driver"
    repo_dir.mkdir()
    (repo_dir / ".git").mkdir()

    with patch("dbx_python_cli.utils.repo.get_config_path") as mock_get_path:
        mock_get_path.return_value = config_path

        with patch("subprocess.run") as mock_run:
            # Mock git commands
            def mock_subprocess(*args, **kwargs):
                cmd = args[0]
                if "remote" in cmd:
                    return MagicMock(returncode=0, stdout="origin\nupstream\n")
                elif "rev-parse" in cmd and "--abbrev-ref" in cmd:
                    return MagicMock(returncode=0, stdout="main\n")
                elif "symbolic-ref" in cmd:
                    return MagicMock(
                        returncode=0, stdout="refs/remotes/upstream/main\n"
                    )
                elif "rev-list" in cmd:
                    # Simulate commits to sync
                    return MagicMock(returncode=0, stdout="abc123\ndef456\n")
                elif "log" in cmd:
                    return MagicMock(
                        returncode=0, stdout="commit abc123\ncommit def456\n"
                    )
                return MagicMock(returncode=0, stdout="")

            mock_run.side_effect = mock_subprocess

            result = runner.invoke(app, ["sync", "mongo-python-driver", "--dry-run"])
            assert result.exit_code == 0
            assert "Checking mongo-python-driver" in result.stdout
            assert "Dry run complete!" in result.stdout

            # Verify no rebase or push commands were executed
            calls = mock_run.call_args_list
            rebase_calls = [call for call in calls if "rebase" in call[0][0]]
            push_calls = [call for call in calls if "push" in call[0][0]]
            assert len(rebase_calls) == 0
            assert len(push_calls) == 0


def test_repo_sync_single_repo_in_group(tmp_path, temp_repos_dir):
    """Test syncing a single repository within a specific group."""
    config_path = tmp_path / ".config" / "dbx-python-cli" / "config.toml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    repos_dir_str = str(temp_repos_dir).replace("\\", "/")
    config_content = f"""
[repo]
base_dir = "{repos_dir_str}"

[repo.groups.pymongo]
repos = [
    "git@github.com:mongodb/mongo-python-driver.git",
    "git@github.com:mongodb/specifications.git"
]
"""
    config_path.write_text(config_content)

    # Create pymongo group directory with two repos
    pymongo_dir = temp_repos_dir / "pymongo"
    pymongo_dir.mkdir()

    # Create mongo-python-driver repo
    driver_repo = pymongo_dir / "mongo-python-driver"
    driver_repo.mkdir()
    (driver_repo / ".git").mkdir()

    # Create specifications repo
    specs_repo = pymongo_dir / "specifications"
    specs_repo.mkdir()
    (specs_repo / ".git").mkdir()

    with patch("dbx_python_cli.utils.repo.get_config_path") as mock_get_path:
        mock_get_path.return_value = config_path

        with patch("subprocess.run") as mock_run:
            # Mock git commands
            def mock_subprocess(*args, **kwargs):
                cmd = args[0]
                if "remote" in cmd:
                    return MagicMock(returncode=0, stdout="origin\nupstream\n")
                elif "rev-parse" in cmd and "--abbrev-ref" in cmd:
                    return MagicMock(returncode=0, stdout="main\n")
                elif "symbolic-ref" in cmd:
                    return MagicMock(
                        returncode=0, stdout="refs/remotes/upstream/main\n"
                    )
                elif "rev-list" in cmd:
                    return MagicMock(returncode=0, stdout="abc123\n")
                elif "log" in cmd:
                    return MagicMock(returncode=0, stdout="commit abc123\n")
                return MagicMock(returncode=0, stdout="")

            mock_run.side_effect = mock_subprocess

            # Sync only mongo-python-driver in pymongo group
            result = runner.invoke(
                app, ["sync", "-g", "pymongo", "mongo-python-driver", "--dry-run"]
            )
            assert result.exit_code == 0
            assert "Checking mongo-python-driver" in result.stdout
            assert "Dry run complete!" in result.stdout

            # Should NOT mention specifications
            assert "specifications" not in result.stdout.lower()

            # Verify no rebase or push commands were executed (dry-run)
            calls = mock_run.call_args_list
            rebase_calls = [call for call in calls if "rebase" in call[0][0]]
            push_calls = [call for call in calls if "push" in call[0][0]]
            assert len(rebase_calls) == 0
            assert len(push_calls) == 0


def test_install_multiple_groups_csv(tmp_path):
    """Test installing group with dependency groups using multiple -g flags."""
    config_path = tmp_path / ".config" / "dbx-python-cli" / "config.toml"
    config_path.parent.mkdir(parents=True, exist_ok=True)

    # Create base directory structure
    base_dir = tmp_path / "repos"
    base_dir.mkdir()

    # Create django group with a repo
    django_dir = base_dir / "django"
    django_dir.mkdir()
    django_repo = django_dir / "django"
    django_repo.mkdir()
    (django_repo / ".git").mkdir()
    (django_repo / "pyproject.toml").write_text("""
[project]
name = "django"

[dependency-groups]
dev = ["pytest>=7.0"]
test = ["coverage>=6.0"]
""")

    # Create config
    base_dir_str = str(base_dir).replace("\\", "/")
    config_content = f"""
[repo]
base_dir = "{base_dir_str}"

[repo.groups.django]
repos = [
    "https://github.com/django/django.git",
]
"""
    config_path.write_text(config_content)

    with patch("dbx_python_cli.utils.repo.get_config_path") as mock_get_path:
        with patch("dbx_python_cli.commands.install.get_venv_info") as mock_venv:
            with patch("dbx_python_cli.commands.install.subprocess.run") as mock_run:
                mock_get_path.return_value = config_path
                mock_venv.return_value = ("python", "venv")
                # Mock successful installation
                mock_run.return_value = type(
                    "obj", (object,), {"returncode": 0, "stdout": "", "stderr": ""}
                )()

                # Test new format: -g django -g dev (first -g is group, second -g is dependency group)
                result = runner.invoke(app, ["install", "-g", "django", "-g", "dev"])
                if result.exit_code != 0:
                    print(f"STDOUT: {result.stdout}")
                    print(f"STDERR: {result.stderr}")
                assert result.exit_code == 0

                # Check that django group is mentioned in output
                assert "django" in result.stdout.lower()

                # Check for success message
                assert "installed successfully" in result.stdout.lower()

                # Verify uv pip install was called for the repo
                install_calls = [
                    call
                    for call in mock_run.call_args_list
                    if len(call[0]) > 0 and "uv" in call[0][0] and "pip" in call[0][0]
                ]
                assert len(install_calls) >= 1

                # Verify that dependency group was installed
                group_calls = [
                    call
                    for call in mock_run.call_args_list
                    if len(call[0]) > 0 and "--group" in call[0][0]
                ]
                assert len(group_calls) >= 1
                # Check that 'dev' group was specified
                assert any("dev" in str(call) for call in group_calls)
