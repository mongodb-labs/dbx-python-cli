"""Fixtures for integration tests."""

import subprocess

import pytest


@pytest.fixture
def integration_workspace(tmp_path):
    """Create a temporary workspace for integration tests."""
    workspace = tmp_path / "integration_workspace"
    workspace.mkdir()
    return workspace


@pytest.fixture
def test_git_repo(tmp_path):
    """Create a real test git repository."""
    repo_dir = tmp_path / "test_repo"
    repo_dir.mkdir()

    # Initialize git repo
    subprocess.run(["git", "init"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=repo_dir,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=repo_dir,
        check=True,
        capture_output=True,
    )

    # Create a simple Python project
    (repo_dir / "README.md").write_text("# Test Repository\n")
    (repo_dir / "pyproject.toml").write_text(
        """[project]
name = "test-repo"
version = "0.1.0"
description = "Test repository"
requires-python = ">=3.8"
dependencies = []

[project.optional-dependencies]
test = ["pytest"]
dev = ["ruff"]
"""
    )

    # Create initial commit
    subprocess.run(["git", "add", "."], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=repo_dir,
        check=True,
        capture_output=True,
    )

    return repo_dir


@pytest.fixture
def test_config_file(tmp_path, test_git_repo):
    """Create a test configuration file."""
    config_dir = tmp_path / ".config" / "drivers-python-cli"
    config_dir.mkdir(parents=True)
    config_path = config_dir / "config.toml"

    base_dir = tmp_path / "repos"
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
    return config_path


@pytest.fixture
def bare_git_repo(tmp_path):
    """Create a bare git repository that can be cloned from."""
    bare_repo = tmp_path / "bare_repo.git"
    bare_repo.mkdir()

    # Initialize bare repo
    subprocess.run(
        ["git", "init", "--bare"], cwd=bare_repo, check=True, capture_output=True
    )

    # Create a temporary repo to push to the bare repo
    temp_repo = tmp_path / "temp_repo"
    temp_repo.mkdir()

    subprocess.run(
        ["git", "init", "-b", "main"], cwd=temp_repo, check=True, capture_output=True
    )
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

    # Create content
    (temp_repo / "README.md").write_text("# Test Bare Repository\n")
    (temp_repo / "pyproject.toml").write_text(
        """[project]
name = "test-bare-repo"
version = "0.1.0"
"""
    )

    subprocess.run(["git", "add", "."], cwd=temp_repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=temp_repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "remote", "add", "origin", str(bare_repo)],
        cwd=temp_repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "push", "-u", "origin", "main"],
        cwd=temp_repo,
        check=True,
        capture_output=True,
    )

    # Set the default branch in the bare repo to main
    subprocess.run(
        ["git", "symbolic-ref", "HEAD", "refs/heads/main"],
        cwd=bare_repo,
        check=True,
        capture_output=True,
    )

    return bare_repo
