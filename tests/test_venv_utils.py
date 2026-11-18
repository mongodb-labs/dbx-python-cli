"""Tests for the venv_utils module."""

import platform

import pytest
import typer

from drivers_python_cli.utils.venv import get_venv_info, get_venv_python


@pytest.fixture
def temp_group_with_venv(tmp_path):
    """Create a temporary group directory with a venv."""
    group_dir = tmp_path / "group_with_venv"
    group_dir.mkdir()

    # Create a mock venv structure (platform-specific)
    venv_dir = group_dir / ".venv"
    venv_dir.mkdir()

    # Windows uses Scripts/python.exe, Unix uses bin/python
    if platform.system() == "Windows":
        bin_dir = venv_dir / "Scripts"
        bin_dir.mkdir()
        python_path = bin_dir / "python.exe"
    else:
        bin_dir = venv_dir / "bin"
        bin_dir.mkdir()
        python_path = bin_dir / "python"

    python_path.write_text("#!/usr/bin/env python3\n")
    if platform.system() != "Windows":
        python_path.chmod(0o755)

    return group_dir


@pytest.fixture
def temp_repo_dir(tmp_path):
    """Create a temporary repo directory."""
    repo_dir = tmp_path / "test_repo"
    repo_dir.mkdir(parents=True)
    return repo_dir


def test_get_venv_python_with_group_venv(temp_repo_dir, temp_group_with_venv):
    """Test get_venv_python when group venv exists."""
    python_path = get_venv_python(temp_repo_dir, temp_group_with_venv)

    # Expected path is platform-specific
    if platform.system() == "Windows":
        expected = str(temp_group_with_venv / ".venv" / "Scripts" / "python.exe")
    else:
        expected = str(temp_group_with_venv / ".venv" / "bin" / "python")

    assert python_path == expected


def test_get_venv_python_no_group_path(temp_repo_dir):
    """Test get_venv_python when no group path is provided."""
    python_path = get_venv_python(temp_repo_dir, group_path=None)

    assert python_path == "python"


def test_get_venv_python_group_venv_not_exists(temp_repo_dir, tmp_path):
    """Test get_venv_python when group venv doesn't exist."""
    group_dir = tmp_path / "group_without_venv"
    group_dir.mkdir()

    python_path = get_venv_python(temp_repo_dir, group_dir)

    assert python_path == "python"


def test_get_venv_python_fallback_to_system(temp_repo_dir):
    """Test get_venv_python falls back to system python."""
    # No group path provided
    python_path = get_venv_python(temp_repo_dir)

    assert python_path == "python"


def test_get_venv_info_with_group_venv(temp_repo_dir, temp_group_with_venv):
    """Test get_venv_info when group venv exists."""
    python_path, venv_type = get_venv_info(temp_repo_dir, temp_group_with_venv)

    # Expected path is platform-specific
    if platform.system() == "Windows":
        expected = str(temp_group_with_venv / ".venv" / "Scripts" / "python.exe")
    else:
        expected = str(temp_group_with_venv / ".venv" / "bin" / "python")

    assert python_path == expected
    assert venv_type == "group"


def test_get_venv_info_no_group_path(temp_repo_dir):
    """Test get_venv_info when no group path is provided."""
    # When no group path is provided and we're not in a venv, it should raise an error
    # This test will only pass if we're already in a venv (which is typical in CI)
    # Otherwise it will raise typer.Exit
    try:
        python_path, venv_type = get_venv_info(temp_repo_dir, group_path=None)
        # If we get here, we're in a venv
        assert python_path  # Not empty
        assert venv_type == "venv"
    except typer.Exit:
        # Expected when not in a venv
        pass


def test_get_venv_info_group_venv_not_exists(temp_repo_dir, tmp_path):
    """Test get_venv_info when group venv doesn't exist."""
    group_dir = tmp_path / "group_without_venv"
    group_dir.mkdir()

    # When group venv doesn't exist and we're not in a venv, it should raise an error
    try:
        python_path, venv_type = get_venv_info(temp_repo_dir, group_dir)
        # If we get here, we're in a venv
        assert python_path  # Not empty
        assert venv_type == "venv"
    except typer.Exit:
        # Expected when not in a venv
        pass


def test_get_venv_info_raises_on_system_python(temp_repo_dir):
    """Test get_venv_info raises error when system python is detected."""
    # When no venv is found, it should raise typer.Exit
    try:
        python_path, venv_type = get_venv_info(temp_repo_dir)
        # If we get here, we're in a venv (typical in CI)
        assert python_path  # Not empty
        assert venv_type == "venv"
    except typer.Exit:
        # Expected when not in a venv - this is the new behavior
        pass


def test_get_venv_python_with_pathlib_path(tmp_path):
    """Test get_venv_python works with pathlib Path objects."""
    group_dir = tmp_path / "test_group"
    group_dir.mkdir()

    # Create platform-specific venv structure
    if platform.system() == "Windows":
        venv_dir = group_dir / ".venv" / "Scripts"
        venv_dir.mkdir(parents=True)
        python_path = venv_dir / "python.exe"
    else:
        venv_dir = group_dir / ".venv" / "bin"
        venv_dir.mkdir(parents=True)
        python_path = venv_dir / "python"

    python_path.write_text("#!/usr/bin/env python3\n")

    repo_dir = group_dir / "test_repo"
    repo_dir.mkdir()

    result = get_venv_python(repo_dir, group_dir)

    assert isinstance(result, str)
    assert result == str(python_path)


def test_get_venv_info_with_pathlib_path(tmp_path):
    """Test get_venv_info works with pathlib Path objects."""
    group_dir = tmp_path / "test_group"
    group_dir.mkdir()

    # Create platform-specific venv structure
    if platform.system() == "Windows":
        venv_dir = group_dir / ".venv" / "Scripts"
        venv_dir.mkdir(parents=True)
        python_path = venv_dir / "python.exe"
    else:
        venv_dir = group_dir / ".venv" / "bin"
        venv_dir.mkdir(parents=True)
        python_path = venv_dir / "python"

    python_path.write_text("#!/usr/bin/env python3\n")

    repo_dir = group_dir / "test_repo"
    repo_dir.mkdir()

    python_result, venv_type = get_venv_info(repo_dir, group_dir)

    assert isinstance(python_result, str)
    assert python_result == str(python_path)
    assert venv_type == "group"


def test_venv_priority_repo_over_group(tmp_path):
    """Test that repo-level venv takes priority over group-level venv."""
    # Create group directory with venv
    group_dir = tmp_path / "test_group"
    group_dir.mkdir()

    if platform.system() == "Windows":
        group_venv = group_dir / ".venv" / "Scripts"
        group_venv.mkdir(parents=True)
        group_python = group_venv / "python.exe"
    else:
        group_venv = group_dir / ".venv" / "bin"
        group_venv.mkdir(parents=True)
        group_python = group_venv / "python"

    group_python.write_text("#!/usr/bin/env python3\n")

    # Create repo directory with venv
    repo_dir = group_dir / "test_repo"
    repo_dir.mkdir()

    if platform.system() == "Windows":
        repo_venv = repo_dir / ".venv" / "Scripts"
        repo_venv.mkdir(parents=True)
        repo_python = repo_venv / "python.exe"
    else:
        repo_venv = repo_dir / ".venv" / "bin"
        repo_venv.mkdir(parents=True)
        repo_python = repo_venv / "python"

    repo_python.write_text("#!/usr/bin/env python3\n")

    # Test get_venv_python
    python_path = get_venv_python(repo_dir, group_dir)
    assert python_path == str(repo_python)

    # Test get_venv_info
    python_path, venv_type = get_venv_info(repo_dir, group_dir)
    assert python_path == str(repo_python)
    assert venv_type == "repo"


def test_venv_priority_repo_over_base(tmp_path):
    """Test that repo-level venv takes priority over base-level venv."""
    # Create base directory with venv
    base_dir = tmp_path / "base"
    base_dir.mkdir()

    if platform.system() == "Windows":
        base_venv = base_dir / ".venv" / "Scripts"
        base_venv.mkdir(parents=True)
        base_python = base_venv / "python.exe"
    else:
        base_venv = base_dir / ".venv" / "bin"
        base_venv.mkdir(parents=True)
        base_python = base_venv / "python"

    base_python.write_text("#!/usr/bin/env python3\n")

    # Create group directory (no venv)
    group_dir = base_dir / "test_group"
    group_dir.mkdir()

    # Create repo directory with venv
    repo_dir = group_dir / "test_repo"
    repo_dir.mkdir()

    if platform.system() == "Windows":
        repo_venv = repo_dir / ".venv" / "Scripts"
        repo_venv.mkdir(parents=True)
        repo_python = repo_venv / "python.exe"
    else:
        repo_venv = repo_dir / ".venv" / "bin"
        repo_venv.mkdir(parents=True)
        repo_python = repo_venv / "python"

    repo_python.write_text("#!/usr/bin/env python3\n")

    # Test get_venv_python
    python_path = get_venv_python(repo_dir, group_dir, base_dir)
    assert python_path == str(repo_python)

    # Test get_venv_info
    python_path, venv_type = get_venv_info(repo_dir, group_dir, base_dir)
    assert python_path == str(repo_python)
    assert venv_type == "repo"


def test_venv_priority_group_over_base(tmp_path):
    """Test that group-level venv takes priority over base-level venv."""
    # Create base directory with venv
    base_dir = tmp_path / "base"
    base_dir.mkdir()

    if platform.system() == "Windows":
        base_venv = base_dir / ".venv" / "Scripts"
        base_venv.mkdir(parents=True)
        base_python = base_venv / "python.exe"
    else:
        base_venv = base_dir / ".venv" / "bin"
        base_venv.mkdir(parents=True)
        base_python = base_venv / "python"

    base_python.write_text("#!/usr/bin/env python3\n")

    # Create group directory with venv
    group_dir = base_dir / "test_group"
    group_dir.mkdir()

    if platform.system() == "Windows":
        group_venv = group_dir / ".venv" / "Scripts"
        group_venv.mkdir(parents=True)
        group_python = group_venv / "python.exe"
    else:
        group_venv = group_dir / ".venv" / "bin"
        group_venv.mkdir(parents=True)
        group_python = group_venv / "python"

    group_python.write_text("#!/usr/bin/env python3\n")

    # Create repo directory (no venv)
    repo_dir = group_dir / "test_repo"
    repo_dir.mkdir()

    # Test get_venv_python
    python_path = get_venv_python(repo_dir, group_dir, base_dir)
    assert python_path == str(group_python)

    # Test get_venv_info
    python_path, venv_type = get_venv_info(repo_dir, group_dir, base_dir)
    assert python_path == str(group_python)
    assert venv_type == "group"


def test_get_venv_info_auto_detects_single_existing_venv(tmp_path):
    """Test that get_venv_info auto-uses a venv found by _find_existing_venvs
    when no venv is specified via the normal priority chain and exactly one
    existing venv is present under base_path."""
    import platform
    from unittest.mock import patch

    base_dir = tmp_path / "base"
    base_dir.mkdir()

    # Create a single group-level venv (simulates django/.venv)
    group_dir = base_dir / "django"
    group_dir.mkdir()
    if platform.system() == "Windows":
        venv_bin = group_dir / ".venv" / "Scripts"
        venv_bin.mkdir(parents=True)
        auto_python = venv_bin / "python.exe"
    else:
        venv_bin = group_dir / ".venv" / "bin"
        venv_bin.mkdir(parents=True)
        auto_python = venv_bin / "python"
    auto_python.write_text("#!/usr/bin/env python3\n")

    # Patch _is_venv so the currently-running Python is not mistaken for a
    # venv python (avoids environment-dependent test behaviour).
    with patch("drivers_python_cli.utils.venv._is_venv", return_value=False):
        python_result, venv_type = get_venv_info(None, None, base_path=base_dir)

    assert python_result == str(auto_python)
    assert venv_type == "venv"


def test_get_venv_info_no_auto_detect_when_multiple_venvs(tmp_path):
    """Test that get_venv_info does NOT auto-use when multiple venvs exist."""
    import platform
    from unittest.mock import patch

    base_dir = tmp_path / "base"
    base_dir.mkdir()

    # Create two group-level venvs
    for group_name in ("django", "flask"):
        group_dir = base_dir / group_name
        group_dir.mkdir()
        if platform.system() == "Windows":
            venv_bin = group_dir / ".venv" / "Scripts"
            venv_bin.mkdir(parents=True)
            (venv_bin / "python.exe").write_text("#!/usr/bin/env python3\n")
        else:
            venv_bin = group_dir / ".venv" / "bin"
            venv_bin.mkdir(parents=True)
            (venv_bin / "python").write_text("#!/usr/bin/env python3\n")

    with patch("drivers_python_cli.utils.venv._is_venv", return_value=False):
        with pytest.raises(typer.Exit):
            get_venv_info(None, None, base_path=base_dir)


def test_venv_priority_all_three_levels(tmp_path):
    """Test priority when all three levels (repo, group, base) have venvs."""
    # Create base directory with venv
    base_dir = tmp_path / "base"
    base_dir.mkdir()

    if platform.system() == "Windows":
        base_venv = base_dir / ".venv" / "Scripts"
        base_venv.mkdir(parents=True)
        base_python = base_venv / "python.exe"
    else:
        base_venv = base_dir / ".venv" / "bin"
        base_venv.mkdir(parents=True)
        base_python = base_venv / "python"

    base_python.write_text("#!/usr/bin/env python3\n")

    # Create group directory with venv
    group_dir = base_dir / "test_group"
    group_dir.mkdir()

    if platform.system() == "Windows":
        group_venv = group_dir / ".venv" / "Scripts"
        group_venv.mkdir(parents=True)
        group_python = group_venv / "python.exe"
    else:
        group_venv = group_dir / ".venv" / "bin"
        group_venv.mkdir(parents=True)
        group_python = group_venv / "python"

    group_python.write_text("#!/usr/bin/env python3\n")

    # Create repo directory with venv
    repo_dir = group_dir / "test_repo"
    repo_dir.mkdir()

    if platform.system() == "Windows":
        repo_venv = repo_dir / ".venv" / "Scripts"
        repo_venv.mkdir(parents=True)
        repo_python = repo_venv / "python.exe"
    else:
        repo_venv = repo_dir / ".venv" / "bin"
        repo_venv.mkdir(parents=True)
        repo_python = repo_venv / "python"

    repo_python.write_text("#!/usr/bin/env python3\n")

    # Test get_venv_python - should use repo-level (most specific)
    python_path = get_venv_python(repo_dir, group_dir, base_dir)
    assert python_path == str(repo_python)

    # Test get_venv_info - should use repo-level (most specific)
    python_path, venv_type = get_venv_info(repo_dir, group_dir, base_dir)
    assert python_path == str(repo_python)
    assert venv_type == "repo"
