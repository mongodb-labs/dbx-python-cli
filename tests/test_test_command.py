"""Tests for the test command module."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from dbx_python_cli.cli import app

runner = CliRunner()


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

    repo3 = django_dir / "django"
    repo3.mkdir()
    (repo3 / ".git").mkdir()

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

[repo.groups.django]
repos = [
    "https://github.com/django/django.git",
]
"""
    config_path.write_text(config_content)
    return config_path


def test_test_help():
    """Test that the test help command works."""
    result = runner.invoke(app, ["test", "--help"])
    assert result.exit_code == 0
    assert "Test commands" in result.stdout


def test_test_no_args_shows_error():
    """Test that test without args shows help."""
    result = runner.invoke(app, ["test"])
    # Typer exits with code 2 when showing help due to no_args_is_help=True
    assert result.exit_code == 2
    # Should show help/usage
    output = result.stdout + result.stderr
    assert "Usage:" in output


def test_test_nonexistent_repo(mock_config, temp_repos_dir):
    """Test that test fails with nonexistent repository."""
    with patch("dbx_python_cli.utils.repo.get_config_path") as mock_get_path:
        mock_get_path.return_value = mock_config

        result = runner.invoke(app, ["test", "nonexistent-repo"])
        assert result.exit_code == 1
        output = result.stdout + result.stderr
        assert "Repository 'nonexistent-repo' not found" in output


def test_test_dot_from_repo_root(mock_config, temp_repos_dir, monkeypatch):
    """Test that '.' resolves to the repo at the current directory."""
    repo_dir = temp_repos_dir / "pymongo" / "mongo-python-driver"

    monkeypatch.chdir(repo_dir)

    with patch("dbx_python_cli.utils.repo.get_config_path") as mock_get_path:
        with patch("dbx_python_cli.commands.test.get_venv_info") as mock_venv:
            with patch("subprocess.run") as mock_run:
                with patch.dict("os.environ", {"MONGODB_URI": "mongodb://localhost:27017"}):
                    mock_get_path.return_value = mock_config
                    mock_venv.return_value = ("python", "venv")

                    mock_result = MagicMock()
                    mock_result.returncode = 0
                    mock_run.return_value = mock_result

                    result = runner.invoke(app, ["test", "."])
                    assert result.exit_code == 0
                    assert "Running pytest" in result.stdout
                    assert "Tests passed in mongo-python-driver" in result.stdout


def test_test_dot_not_in_managed_repo(mock_config, temp_repos_dir, monkeypatch):
    """Test that '.' in an unmanaged directory gives a clear error."""
    unrelated = temp_repos_dir / "unrelated"
    unrelated.mkdir()
    monkeypatch.chdir(unrelated)

    with patch("dbx_python_cli.utils.repo.get_config_path") as mock_get_path:
        mock_get_path.return_value = mock_config

        result = runner.invoke(app, ["test", "."])
        assert result.exit_code == 1
        output = result.stdout + result.stderr
        assert "No managed repository found" in output


def test_test_runs_pytest_success(mock_config, temp_repos_dir):
    """Test that test runs pytest successfully."""
    with patch("dbx_python_cli.utils.repo.get_config_path") as mock_get_path:
        with patch("dbx_python_cli.commands.test.get_venv_info") as mock_venv:
            with patch("subprocess.run") as mock_run:
                with patch.dict(
                    "os.environ", {"MONGODB_URI": "mongodb://localhost:27017"}
                ):
                    mock_get_path.return_value = mock_config
                    mock_venv.return_value = ("python", "venv")

                    # Mock successful pytest run
                    mock_result = MagicMock()
                    mock_result.returncode = 0
                    mock_run.return_value = mock_result

                    result = runner.invoke(app, ["test", "mongo-python-driver"])
                    assert result.exit_code == 0
                    assert "Running pytest" in result.stdout
                    assert "Tests passed" in result.stdout

                    # Verify pytest was called with correct arguments
                    mock_run.assert_called_once()
                    call_args = mock_run.call_args
                    assert call_args[0][0] == ["python", "-m", "pytest"]
                assert "mongo-python-driver" in str(call_args[1]["cwd"])


def test_test_runs_pytest_failure(mock_config, temp_repos_dir):
    """Test that test handles pytest failures."""
    with patch("dbx_python_cli.utils.repo.get_config_path") as mock_get_path:
        with patch("dbx_python_cli.commands.test.get_venv_info") as mock_venv:
            with patch("subprocess.run") as mock_run:
                with patch.dict(
                    "os.environ", {"MONGODB_URI": "mongodb://localhost:27017"}
                ):
                    mock_get_path.return_value = mock_config
                    mock_venv.return_value = ("python", "venv")

                    # Mock failed pytest run
                    mock_result = MagicMock()
                    mock_result.returncode = 1
                    mock_run.return_value = mock_result

                    result = runner.invoke(app, ["test", "mongo-python-driver"])
                    assert result.exit_code == 1
                    assert "Running pytest" in result.stdout
                    output = result.stdout + result.stderr
                    assert "Tests failed" in output


def test_test_with_custom_test_runner(tmp_path):
    """Test that test uses custom test runner when configured."""
    # Create temp repos directory
    repos_dir = tmp_path / "repos"
    repos_dir.mkdir(parents=True)

    # Create django group and repo
    django_dir = repos_dir / "django"
    django_dir.mkdir()

    django_repo = django_dir / "django"
    django_repo.mkdir()
    (django_repo / ".git").mkdir()

    # Create custom test runner script
    tests_dir = django_repo / "tests"
    tests_dir.mkdir()
    test_runner = tests_dir / "runtests.py"
    test_runner.write_text("# Custom test runner")

    # Create django_test project so we don't trigger auto-creation
    django_test_dir = repos_dir / "projects" / "django_test"
    django_test_dir.mkdir(parents=True)
    (django_test_dir / "manage.py").write_text("")

    # Create config with custom test runner
    config_dir = tmp_path / ".config" / "dbx-python-cli"
    config_dir.mkdir(parents=True)
    config_path = config_dir / "config.toml"
    repos_dir_str = str(repos_dir).replace("\\", "/")
    config_content = f"""
[repo]
base_dir = "{repos_dir_str}"

[repo.groups.django]
repos = [
    "https://github.com/django/django.git",
]

[repo.groups.django.test_runner]
django = "tests/runtests.py"
"""
    config_path.write_text(config_content)

    with patch("dbx_python_cli.utils.repo.get_config_path") as mock_get_path:
        with patch("dbx_python_cli.commands.test.get_venv_info") as mock_venv:
            with patch("subprocess.run") as mock_run:
                with patch.dict(
                    "os.environ", {"MONGODB_URI": "mongodb://localhost:27017"}
                ):
                    mock_get_path.return_value = config_path
                    mock_venv.return_value = ("python", "venv")

                    # Mock successful test run
                    mock_result = MagicMock()
                    mock_result.returncode = 0
                    mock_run.return_value = mock_result

                    result = runner.invoke(app, ["test", "-y", "django"])
                    assert result.exit_code == 0
                    assert "Running tests/runtests.py" in result.stdout
                    assert "Tests passed" in result.stdout

                    # Verify custom test runner was called with injected --settings
                    mock_run.assert_called_once()
                    call_args = mock_run.call_args
                    assert "runtests.py" in call_args[0][0][1]
                    assert "--settings" in call_args[0][0]
                assert "django_test.settings.django_test" in call_args[0][0]
                assert "django" in str(call_args[1]["cwd"])


def test_test_with_custom_test_runner_not_found(tmp_path):
    """Test that test fails when custom test runner doesn't exist."""
    # Create temp repos directory
    repos_dir = tmp_path / "repos"
    repos_dir.mkdir(parents=True)

    # Create django group and repo
    django_dir = repos_dir / "django"
    django_dir.mkdir()

    django_repo = django_dir / "django"
    django_repo.mkdir()
    (django_repo / ".git").mkdir()

    # Don't create the test runner script

    # Create config with custom test runner
    config_dir = tmp_path / ".config" / "dbx-python-cli"
    config_dir.mkdir(parents=True)
    config_path = config_dir / "config.toml"
    repos_dir_str = str(repos_dir).replace("\\", "/")
    config_content = f"""
[repo]
base_dir = "{repos_dir_str}"

[repo.groups.django]
repos = [
    "https://github.com/django/django.git",
]

[repo.groups.django.test_runner]
django = "tests/runtests.py"
"""
    config_path.write_text(config_content)

    with patch("dbx_python_cli.utils.repo.get_config_path") as mock_get_path:
        with patch("dbx_python_cli.commands.test.get_venv_info") as mock_venv:
            mock_get_path.return_value = config_path
            mock_venv.return_value = ("python", "venv")

            result = runner.invoke(app, ["test", "-y", "django"])
            assert result.exit_code == 1
            output = result.stdout + result.stderr
            assert "Test runner not found" in output


def test_test_fallback_to_pytest_when_no_test_runner(mock_config, temp_repos_dir):
    """Test that test falls back to pytest when no custom test runner is configured."""
    with patch("dbx_python_cli.utils.repo.get_config_path") as mock_get_path:
        with patch("dbx_python_cli.commands.test.get_venv_info") as mock_venv:
            with patch("subprocess.run") as mock_run:
                with patch.dict(
                    "os.environ", {"MONGODB_URI": "mongodb://localhost:27017"}
                ):
                    mock_get_path.return_value = mock_config
                    mock_venv.return_value = ("python", "venv")

                    # Mock successful pytest run
                    mock_result = MagicMock()
                    mock_result.returncode = 0
                    mock_run.return_value = mock_result

                    result = runner.invoke(app, ["test", "django"])
                    assert result.exit_code == 0
                    assert "Running pytest" in result.stdout

                    # Verify pytest was called (not custom runner)
                    mock_run.assert_called_once()
                    call_args = mock_run.call_args
                    assert call_args[0][0] == ["python", "-m", "pytest"]


def test_test_with_custom_test_runner_and_args(tmp_path):
    """Test that test passes arguments to custom test runner."""
    # Create temp repos directory
    repos_dir = tmp_path / "repos"
    repos_dir.mkdir(parents=True)

    # Create django group and repo
    django_dir = repos_dir / "django"
    django_dir.mkdir()

    django_repo = django_dir / "django"
    django_repo.mkdir()
    (django_repo / ".git").mkdir()

    # Create custom test runner script
    tests_dir = django_repo / "tests"
    tests_dir.mkdir()
    test_runner = tests_dir / "runtests.py"
    test_runner.write_text("# Custom test runner")

    # Create django_test project so we don't trigger auto-creation
    django_test_dir = repos_dir / "projects" / "django_test"
    django_test_dir.mkdir(parents=True)
    (django_test_dir / "manage.py").write_text("")

    # Create config with custom test runner
    config_dir = tmp_path / ".config" / "dbx-python-cli"
    config_dir.mkdir(parents=True)
    config_path = config_dir / "config.toml"
    repos_dir_str = str(repos_dir).replace("\\", "/")
    config_content = f"""
[repo]
base_dir = "{repos_dir_str}"

[repo.groups.django]
repos = [
    "https://github.com/django/django.git",
]

[repo.groups.django.test_runner]
django = "tests/runtests.py"
"""
    config_path.write_text(config_content)

    with patch("dbx_python_cli.utils.repo.get_config_path") as mock_get_path:
        with patch("dbx_python_cli.commands.test.get_venv_info") as mock_venv:
            with patch("subprocess.run") as mock_run:
                with patch.dict(
                    "os.environ", {"MONGODB_URI": "mongodb://localhost:27017"}
                ):
                    mock_get_path.return_value = config_path
                    mock_venv.return_value = ("python", "venv")

                    # Mock successful test run
                    mock_result = MagicMock()
                    mock_result.returncode = 0
                    mock_run.return_value = mock_result

                    result = runner.invoke(
                        app, ["test", "-y", "django", "--verbose", "--parallel"]
                    )
                    assert result.exit_code == 0
                    # --settings is prepended before user args
                    assert (
                        "Running tests/runtests.py --settings django_test.settings.django_test --verbose --parallel"
                        in result.stdout
                    )

                    # Verify custom test runner was called with args
                    mock_run.assert_called_once()
                    call_args = mock_run.call_args
                    assert "runtests.py" in call_args[0][0][1]
                    assert "--settings" in call_args[0][0]
                assert "django_test.settings.django_test" in call_args[0][0]
                assert "--verbose" in call_args[0][0]
                assert "--parallel" in call_args[0][0]


def test_test_django_creates_project_if_missing(tmp_path):
    """Test that dbx test django creates the django_test project if it doesn't exist."""
    # Create temp repos directory
    repos_dir = tmp_path / "repos"
    repos_dir.mkdir(parents=True)

    # Create django group and repo
    django_dir = repos_dir / "django"
    django_dir.mkdir()

    django_repo = django_dir / "django"
    django_repo.mkdir()
    (django_repo / ".git").mkdir()

    # Create custom test runner script
    tests_dir = django_repo / "tests"
    tests_dir.mkdir()
    (tests_dir / "runtests.py").write_text("# Custom test runner")

    # Note: do NOT create projects/django_test — this is the key condition

    # Create config with custom test runner
    config_dir = tmp_path / ".config" / "dbx-python-cli"
    config_dir.mkdir(parents=True)
    config_path = config_dir / "config.toml"
    repos_dir_str = str(repos_dir).replace("\\", "/")
    config_content = f"""
[repo]
base_dir = "{repos_dir_str}"

[repo.groups.django]
repos = [
    "https://github.com/django/django.git",
]

[repo.groups.django.test_runner]
django = "tests/runtests.py"
"""
    config_path.write_text(config_content)

    with patch("dbx_python_cli.utils.repo.get_config_path") as mock_get_path:
        with patch("dbx_python_cli.commands.test.get_venv_info") as mock_venv:
            with patch("subprocess.run") as mock_run:
                with patch(
                    "dbx_python_cli.commands.test.add_project"
                ) as mock_add_project:
                    with patch.dict(
                        "os.environ", {"MONGODB_URI": "mongodb://localhost:27017"}
                    ):
                        mock_get_path.return_value = config_path
                        mock_venv.return_value = ("python", "venv")

                        # Mock successful test run
                        mock_result = MagicMock()
                        mock_result.returncode = 0
                        mock_run.return_value = mock_result
                        mock_add_project.return_value = None  # success, no exception

                        result = runner.invoke(app, ["test", "-y", "django"])
                        assert result.exit_code == 0

                        # Verify add_project was called to create the missing project
                        # Uses auto_install=False so add_project falls back to sys.executable
                        # (which has Django installed) instead of the test repo's venv.
                        mock_add_project.assert_called_once_with(
                            "django_test",
                            directory=None,
                            base_dir=None,
                            add_frontend=True,
                            auto_install=False,
                        )
                    assert "django_test project not found" in result.stdout


def test_test_with_pytest_and_args(mock_config, temp_repos_dir):
    """Test that test passes arguments to pytest."""
    with patch("dbx_python_cli.utils.repo.get_config_path") as mock_get_path:
        with patch("dbx_python_cli.commands.test.get_venv_info") as mock_venv:
            with patch("subprocess.run") as mock_run:
                with patch.dict(
                    "os.environ", {"MONGODB_URI": "mongodb://localhost:27017"}
                ):
                    mock_get_path.return_value = mock_config
                    mock_venv.return_value = ("python", "venv")

                    # Mock successful pytest run
                    mock_result = MagicMock()
                    mock_result.returncode = 0
                    mock_run.return_value = mock_result

                    result = runner.invoke(
                        app, ["test", "mongo-python-driver", "-x", "--tb=short"]
                    )
                    assert result.exit_code == 0
                    assert "Running pytest -x --tb=short" in result.stdout

                    # Verify pytest was called with args
                    mock_run.assert_called_once()
                    call_args = mock_run.call_args
                    assert call_args[0][0] == [
                        "python",
                        "-m",
                        "pytest",
                        "-x",
                        "--tb=short",
                    ]


def test_test_env_vars(tmp_path, temp_repos_dir):
    """Test that environment variables are set for test runs."""
    config_dir = tmp_path / ".config" / "dbx-python-cli"
    config_dir.mkdir(parents=True)
    config_path = config_dir / "config.toml"
    repos_dir_str = str(temp_repos_dir).replace("\\", "/")

    config_content = f"""
[repo]
base_dir = "{repos_dir_str}"

[repo.groups.pymongo]
repos = [
    "https://github.com/mongodb/mongo-python-driver.git",
]

[repo.groups.pymongo.test_env]
mongo-python-driver = {{ DRIVERS_TOOLS = "{{base_dir}}/{{group}}/drivers-evergreen-tools" }}
"""
    config_path.write_text(config_content)

    with patch("dbx_python_cli.utils.repo.get_config_path") as mock_get_path:
        with patch("dbx_python_cli.commands.test.get_venv_info") as mock_venv:
            with patch("subprocess.run") as mock_run:
                with patch.dict(
                    "os.environ", {"MONGODB_URI": "mongodb://localhost:27017"}
                ):
                    mock_get_path.return_value = config_path
                    mock_venv.return_value = ("python", "venv")

                    # Mock successful test run
                    mock_result = MagicMock()
                    mock_result.returncode = 0
                    mock_run.return_value = mock_result

                    result = runner.invoke(app, ["test", "mongo-python-driver"])
                    assert result.exit_code == 0

                    # Verify subprocess.run was called with env containing DRIVERS_TOOLS
                    mock_run.assert_called_once()
                    call_args = mock_run.call_args
                    env = call_args[1]["env"]
                    assert "DRIVERS_TOOLS" in env
                    expected_path = str(
                        Path(temp_repos_dir) / "pymongo" / "drivers-evergreen-tools"
                    )
                    assert env["DRIVERS_TOOLS"] == expected_path


def test_test_with_multiple_env_vars(tmp_path, temp_repos_dir):
    """Test that multiple environment variables can be set."""
    config_dir = tmp_path / ".config" / "dbx-python-cli"
    config_dir.mkdir(parents=True)
    config_path = config_dir / "config.toml"
    repos_dir_str = str(temp_repos_dir).replace("\\", "/")

    config_content = f"""
[repo]
base_dir = "{repos_dir_str}"

[repo.groups.pymongo]
repos = [
    "https://github.com/mongodb/mongo-python-driver.git",
]

[repo.groups.pymongo.test_env]
mongo-python-driver = {{ DRIVERS_TOOLS = "{{base_dir}}/{{group}}/drivers-evergreen-tools", TEST_VAR = "test_value" }}
"""
    config_path.write_text(config_content)

    with patch("dbx_python_cli.utils.repo.get_config_path") as mock_get_path:
        with patch("dbx_python_cli.commands.test.get_venv_info") as mock_venv:
            with patch("subprocess.run") as mock_run:
                with patch.dict(
                    "os.environ", {"MONGODB_URI": "mongodb://localhost:27017"}
                ):
                    mock_get_path.return_value = config_path
                    mock_venv.return_value = ("python", "venv")

                    # Mock successful test run
                    mock_result = MagicMock()
                    mock_result.returncode = 0
                    mock_run.return_value = mock_result

                    result = runner.invoke(app, ["test", "mongo-python-driver"])
                    assert result.exit_code == 0

                    # Verify subprocess.run was called with both env vars
                    mock_run.assert_called_once()
                    call_args = mock_run.call_args
                    env = call_args[1]["env"]
                    assert "DRIVERS_TOOLS" in env
                    assert "TEST_VAR" in env
                    assert env["TEST_VAR"] == "test_value"


def test_test_env_vars_verbose_output(tmp_path, temp_repos_dir):
    """Test that environment variables are shown in verbose mode."""
    config_dir = tmp_path / ".config" / "dbx-python-cli"
    config_dir.mkdir(parents=True)
    config_path = config_dir / "config.toml"
    repos_dir_str = str(temp_repos_dir).replace("\\", "/")

    config_content = f"""
[repo]
base_dir = "{repos_dir_str}"

[repo.groups.pymongo]
repos = [
    "https://github.com/mongodb/mongo-python-driver.git",
]

[repo.groups.pymongo.test_env]
mongo-python-driver = {{ DRIVERS_TOOLS = "{{base_dir}}/{{group}}/drivers-evergreen-tools" }}
"""
    config_path.write_text(config_content)

    with patch("dbx_python_cli.utils.repo.get_config_path") as mock_get_path:
        with patch("dbx_python_cli.commands.test.get_venv_info") as mock_venv:
            with patch("subprocess.run") as mock_run:
                with patch.dict(
                    "os.environ", {"MONGODB_URI": "mongodb://localhost:27017"}
                ):
                    mock_get_path.return_value = config_path
                    mock_venv.return_value = ("python", "venv")

                    # Mock successful test run
                    mock_result = MagicMock()
                    mock_result.returncode = 0
                    mock_run.return_value = mock_result

                    result = runner.invoke(
                        app, ["--verbose", "test", "mongo-python-driver"]
                    )
                    assert result.exit_code == 0
                    assert "Environment variables:" in result.stdout
                    assert "DRIVERS_TOOLS=" in result.stdout


def test_test_with_group_flag(mock_config, temp_repos_dir):
    """Test that test with -g flag runs in the specified group's repo."""
    with patch("dbx_python_cli.utils.repo.get_config_path") as mock_get_path:
        with patch("dbx_python_cli.commands.test.get_venv_info") as mock_venv:
            with patch("subprocess.run") as mock_run:
                with patch.dict(
                    "os.environ", {"MONGODB_URI": "mongodb://localhost:27017"}
                ):
                    mock_get_path.return_value = mock_config
                    mock_venv.return_value = ("python", "group")

                    # Mock successful pytest run
                    mock_result = MagicMock()
                    mock_result.returncode = 0
                    mock_run.return_value = mock_result

                    result = runner.invoke(app, ["test", "-g", "django", "django"])
                    assert result.exit_code == 0
                    assert "Running pytest" in result.stdout

                    # Verify the working directory is the django repo in the django group
                    call_kwargs = mock_run.call_args[1]
                    cwd = call_kwargs["cwd"]
                    assert cwd.endswith("django/django") or cwd.endswith(
                        "django\\django"
                    )


def test_test_with_group_flag_repo_not_in_group(mock_config, temp_repos_dir):
    """Test that test with -g flag fails if repo not in specified group."""
    with patch("dbx_python_cli.utils.repo.get_config_path") as mock_get_path:
        mock_get_path.return_value = mock_config

        # Try to find mongo-python-driver in django group (it's in pymongo group)
        result = runner.invoke(app, ["test", "-g", "django", "mongo-python-driver"])
        assert result.exit_code == 1
        output = result.stdout + result.stderr
        assert "Repository 'mongo-python-driver' not found in group 'django'" in output
