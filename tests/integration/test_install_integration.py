"""Integration tests for install commands."""

import subprocess
from unittest.mock import patch

from typer.testing import CliRunner

from drivers_python_cli.cli import app

runner = CliRunner()


def test_install_real_package(tmp_path, test_git_repo):
    """Test installing a real package with uv."""
    config_dir = tmp_path / ".config" / "drivers-python-cli"
    config_dir.mkdir(parents=True)
    config_path = config_dir / "config.toml"

    base_dir = tmp_path / "repos"
    base_dir.mkdir()
    test_group = base_dir / "test"
    test_group.mkdir()

    # Clone the test repo
    cloned_repo = test_group / "test_repo"
    subprocess.run(
        ["git", "clone", str(test_git_repo), str(cloned_repo)],
        check=True,
        capture_output=True,
    )

    base_dir_str = str(base_dir).replace("\\", "/")
    test_repo_str = str(test_git_repo).replace("\\", "/")

    config_content = f"""[repo]
base_dir = "{base_dir_str}"

[repo.groups.test]
repos = [
    "{test_repo_str}",
]
"""
    config_path.write_text(config_content)

    # Create a venv for the group
    venv_dir = test_group / ".venv"
    subprocess.run(
        ["python", "-m", "venv", str(venv_dir)], check=True, capture_output=True
    )

    with patch("drivers_python_cli.utils.repo.get_config_path") as mock_get_path:
        mock_get_path.return_value = config_path

        result = runner.invoke(app, ["install", "test_repo"])
        if result.exit_code != 0:
            print(f"STDOUT: {result.stdout}")
            print(f"STDERR: {result.stderr}")
            print(f"Exception: {result.exception}")
        assert result.exit_code == 0
        assert "Installing test_repo" in result.stdout or "Installing" in result.stdout


def test_install_with_extras(tmp_path, test_git_repo):
    """Test installing with extras."""
    config_dir = tmp_path / ".config" / "drivers-python-cli"
    config_dir.mkdir(parents=True)
    config_path = config_dir / "config.toml"

    base_dir = tmp_path / "repos"
    base_dir.mkdir()
    test_group = base_dir / "test"
    test_group.mkdir()

    # Clone the test repo
    cloned_repo = test_group / "test_repo"
    subprocess.run(
        ["git", "clone", str(test_git_repo), str(cloned_repo)],
        check=True,
        capture_output=True,
    )

    base_dir_str = str(base_dir).replace("\\", "/")
    test_repo_str = str(test_git_repo).replace("\\", "/")

    config_content = f"""[repo]
base_dir = "{base_dir_str}"

[repo.groups.test]
repos = [
    "{test_repo_str}",
]
"""
    config_path.write_text(config_content)

    # Create a venv for the group
    venv_dir = test_group / ".venv"
    subprocess.run(
        ["python", "-m", "venv", str(venv_dir)], check=True, capture_output=True
    )

    with patch("drivers_python_cli.utils.repo.get_config_path") as mock_get_path:
        mock_get_path.return_value = config_path

        result = runner.invoke(app, ["install", "test_repo", "-e", "test"])
        assert result.exit_code == 0
        assert "Installing" in result.stdout


def test_install_group_level(tmp_path, test_git_repo):
    """Test installing all repos in a group."""
    config_dir = tmp_path / ".config" / "drivers-python-cli"
    config_dir.mkdir(parents=True)
    config_path = config_dir / "config.toml"

    base_dir = tmp_path / "repos"
    base_dir.mkdir()
    test_group = base_dir / "test"
    test_group.mkdir()

    # Clone the test repo
    cloned_repo = test_group / "test_repo"
    subprocess.run(
        ["git", "clone", str(test_git_repo), str(cloned_repo)],
        check=True,
        capture_output=True,
    )

    base_dir_str = str(base_dir).replace("\\", "/")
    test_repo_str = str(test_git_repo).replace("\\", "/")

    config_content = f"""[repo]
base_dir = "{base_dir_str}"

[repo.groups.test]
repos = [
    "{test_repo_str}",
]
"""
    config_path.write_text(config_content)

    # Create a venv for the group
    venv_dir = test_group / ".venv"
    subprocess.run(
        ["python", "-m", "venv", str(venv_dir)], check=True, capture_output=True
    )

    with patch("drivers_python_cli.utils.repo.get_config_path") as mock_get_path:
        mock_get_path.return_value = config_path

        result = runner.invoke(app, ["install", "-g", "test"])
        assert result.exit_code == 0
        assert "Installing all repositories in group 'test'" in result.stdout
