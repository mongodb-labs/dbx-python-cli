"""Integration tests for repo commands."""

import subprocess
from unittest.mock import patch

from typer.testing import CliRunner

from dbx_python_cli.cli import app

runner = CliRunner()


def test_repo_clone_real_git_repo(tmp_path, bare_git_repo):
    """Test cloning a real git repository."""
    config_dir = tmp_path / ".config" / "dbx-python-cli"
    config_dir.mkdir(parents=True)
    config_path = config_dir / "config.toml"

    base_dir = tmp_path / "repos"
    base_dir_str = str(base_dir).replace("\\", "/")
    bare_repo_str = str(bare_git_repo).replace("\\", "/")

    config_content = f"""[repo]
base_dir = "{base_dir_str}"

[repo.groups.test]
repos = [
    "{bare_repo_str}",
]
"""
    config_path.write_text(config_content)

    with patch("dbx_python_cli.utils.repo.get_config_path") as mock_get_path:
        mock_get_path.return_value = config_path

        result = runner.invoke(app, ["clone", "-g", "test"])
        assert result.exit_code == 0
        assert "Cloning bare_repo to" in result.stdout
        assert "bare_repo cloned successfully" in result.stdout

        # Verify the repo was actually cloned
        cloned_repo = base_dir / "test" / "bare_repo"
        assert cloned_repo.exists()
        assert (cloned_repo / ".git").exists()
        assert (cloned_repo / "README.md").exists()


def test_repo_clone_skip_existing(tmp_path, bare_git_repo):
    """Test that cloning skips already cloned repos."""
    config_dir = tmp_path / ".config" / "dbx-python-cli"
    config_dir.mkdir(parents=True)
    config_path = config_dir / "config.toml"

    base_dir = tmp_path / "repos"
    base_dir.mkdir()
    test_group = base_dir / "test"
    test_group.mkdir()

    bare_repo_str = str(bare_git_repo).replace("\\", "/")
    base_dir_str = str(base_dir).replace("\\", "/")

    config_content = f"""[repo]
base_dir = "{base_dir_str}"

[repo.groups.test]
repos = [
    "{bare_repo_str}",
]
"""
    config_path.write_text(config_content)

    # Clone the repo first
    cloned_repo = test_group / "bare_repo"
    subprocess.run(
        ["git", "clone", str(bare_git_repo), str(cloned_repo)],
        check=True,
        capture_output=True,
    )

    with patch("dbx_python_cli.utils.repo.get_config_path") as mock_get_path:
        mock_get_path.return_value = config_path

        result = runner.invoke(app, ["clone", "-g", "test"])
        assert result.exit_code == 0
        assert "already exists" in result.stdout


def test_repo_sync_real_repo(tmp_path, bare_git_repo):
    """Test syncing a real repository."""
    config_dir = tmp_path / ".config" / "dbx-python-cli"
    config_dir.mkdir(parents=True)
    config_path = config_dir / "config.toml"

    base_dir = tmp_path / "repos"
    base_dir.mkdir()
    test_group = base_dir / "test"
    test_group.mkdir()

    bare_repo_str = str(bare_git_repo).replace("\\", "/")
    base_dir_str = str(base_dir).replace("\\", "/")

    config_content = f"""[repo]
base_dir = "{base_dir_str}"

[repo.groups.test]
repos = [
    "{bare_repo_str}",
]
"""
    config_path.write_text(config_content)

    # Clone the repo first
    cloned_repo = test_group / "bare_repo"
    subprocess.run(
        ["git", "clone", str(bare_git_repo), str(cloned_repo)],
        check=True,
        capture_output=True,
    )

    # Add upstream remote
    subprocess.run(
        ["git", "remote", "add", "upstream", str(bare_git_repo)],
        cwd=cloned_repo,
        check=True,
        capture_output=True,
    )

    # Make a change in the bare repo
    temp_repo = tmp_path / "temp_for_update"
    subprocess.run(
        ["git", "clone", str(bare_git_repo), str(temp_repo)],
        check=True,
        capture_output=True,
    )
    # Configure git user for this repo
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=temp_repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=temp_repo,
        check=True,
        capture_output=True,
    )
    (temp_repo / "new_file.txt").write_text("new content")
    subprocess.run(["git", "add", "."], cwd=temp_repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Add new file"],
        cwd=temp_repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(["git", "push"], cwd=temp_repo, check=True, capture_output=True)

    with patch("dbx_python_cli.utils.repo.get_config_path") as mock_get_path:
        mock_get_path.return_value = config_path

        result = runner.invoke(app, ["sync", "bare_repo"])
        assert result.exit_code == 0
        assert "Syncing bare_repo" in result.stdout
        assert "Synced and pushed successfully" in result.stdout

        # Verify the new file was pulled
        assert (cloned_repo / "new_file.txt").exists()
