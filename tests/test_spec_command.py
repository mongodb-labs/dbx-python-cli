"""Tests for the spec command."""

import re
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from dbx_python_cli.cli import app

runner = CliRunner()

SAMPLE_PATCH = """\
diff --git a/test/crud/foo.json b/test/crud/foo.json
index abc123..def456 100644
--- a/test/crud/foo.json
+++ b/test/crud/foo.json
@@ -1,3 +1,3 @@
-old line
+new line
"""


@pytest.fixture
def temp_repos_dir(tmp_path):
    """Create a temporary repos directory with mock repositories."""
    repos_dir = tmp_path / "repos"
    repos_dir.mkdir()

    # Driver repo with resync-specs.sh and spec-patch/
    driver_repo = repos_dir / "mongo-python-driver"
    driver_repo.mkdir()
    (driver_repo / ".git").mkdir()
    evergreen_dir = driver_repo / ".evergreen"
    evergreen_dir.mkdir()
    resync_script = evergreen_dir / "resync-specs.sh"
    resync_script.write_text("#!/bin/bash\necho syncing\n")
    resync_script.chmod(0o755)
    patch_dir = evergreen_dir / "spec-patch"
    patch_dir.mkdir()

    # Specifications repo with source/ directory
    specs_repo = repos_dir / "specifications"
    specs_repo.mkdir()
    (specs_repo / ".git").mkdir()
    source_dir = specs_repo / "source"
    source_dir.mkdir()
    for name in ["crud", "sessions", "transactions", "change-streams"]:
        (source_dir / name).mkdir()

    return repos_dir


@pytest.fixture
def mock_config(tmp_path, temp_repos_dir):
    """Create a mock config file with flat layout."""
    config_dir = tmp_path / ".config" / "dbx-python-cli"
    config_dir.mkdir(parents=True)
    config_path = config_dir / "config.toml"
    repos_dir_str = str(temp_repos_dir).replace("\\", "/")
    config_path.write_text(f"""
[repo]
base_dir = "{repos_dir_str}"
flat = true

[repo.groups.pymongo]
repos = [
    "https://github.com/mongodb/mongo-python-driver.git",
    "https://github.com/mongodb/specifications.git",
]
""")
    return config_path


@pytest.fixture
def mock_config_with_patches(tmp_path, temp_repos_dir):
    """Config with pre-populated patch files in the driver repo."""
    patch_dir = temp_repos_dir / "mongo-python-driver" / ".evergreen" / "spec-patch"
    (patch_dir / "PYTHON-1234.patch").write_text(SAMPLE_PATCH)
    (patch_dir / "PYTHON-5678.patch").write_text(
        "diff --git a/test/sessions/bar.json b/test/sessions/bar.json\n"
        "index 000..111 100644\n--- a/test/sessions/bar.json\n+++ b/test/sessions/bar.json\n"
        "@@ -1 +1 @@\n-x\n+y\n"
    )

    config_dir = tmp_path / ".config" / "dbx-python-cli"
    config_dir.mkdir(parents=True)
    config_path = config_dir / "config.toml"
    repos_dir_str = str(temp_repos_dir).replace("\\", "/")
    config_path.write_text(f"""
[repo]
base_dir = "{repos_dir_str}"
flat = true

[repo.groups.pymongo]
repos = [
    "https://github.com/mongodb/mongo-python-driver.git",
    "https://github.com/mongodb/specifications.git",
]
""")
    return config_path


# ---------------------------------------------------------------------------
# Help
# ---------------------------------------------------------------------------


def test_spec_help():
    result = runner.invoke(app, ["spec", "--help"])
    assert result.exit_code == 0
    assert "sync" in result.output
    assert "list" in result.output
    assert "patch" in result.output


def test_spec_patch_help():
    result = runner.invoke(app, ["spec", "patch", "--help"])
    assert result.exit_code == 0
    assert "list" in result.output
    assert "create" in result.output
    assert "remove" in result.output
    assert "apply" in result.output


# ---------------------------------------------------------------------------
# dbx spec sync
# ---------------------------------------------------------------------------


def test_spec_sync_help():
    result = runner.invoke(app, ["spec", "sync", "--help"])
    assert result.exit_code == 0
    # Strip ANSI escape codes before checking (macOS runners may inject them)
    clean = re.sub(r"\x1b\[[0-9;]*m", "", result.output)
    assert "--repo" in clean
    assert "--block" in clean
    assert "--dry-run" in clean
    assert "--apply-patches" in clean


def test_spec_sync_dry_run(mock_config):
    with patch("dbx_python_cli.utils.repo.get_config_path", return_value=mock_config):
        result = runner.invoke(app, ["spec", "sync", "--dry-run"])
    assert result.exit_code == 0
    assert "Would run" in result.output
    assert "resync-specs.sh" in result.output


def test_spec_sync_dry_run_with_specs(mock_config):
    with patch("dbx_python_cli.utils.repo.get_config_path", return_value=mock_config):
        result = runner.invoke(app, ["spec", "sync", "crud", "sessions", "--dry-run"])
    assert result.exit_code == 0
    assert "crud" in result.output
    assert "sessions" in result.output


def test_spec_sync_dry_run_with_block(mock_config):
    with patch("dbx_python_cli.utils.repo.get_config_path", return_value=mock_config):
        result = runner.invoke(
            app, ["spec", "sync", "crud", "-b", "unified", "--dry-run"]
        )
    assert result.exit_code == 0
    assert "-b" in result.output
    assert "unified" in result.output


def test_spec_sync_dry_run_shows_patch_count(mock_config_with_patches):
    with patch(
        "dbx_python_cli.utils.repo.get_config_path",
        return_value=mock_config_with_patches,
    ):
        result = runner.invoke(app, ["spec", "sync", "--dry-run"])
    assert result.exit_code == 0
    assert "2" in result.output
    assert "patch" in result.output.lower()


def test_spec_sync_missing_specs_repo(tmp_path):
    repos_dir = tmp_path / "empty_repos"
    repos_dir.mkdir()
    driver_repo = repos_dir / "mongo-python-driver"
    driver_repo.mkdir()
    (driver_repo / ".git").mkdir()
    (driver_repo / ".evergreen").mkdir()

    config_dir = tmp_path / ".config2" / "dbx-python-cli"
    config_dir.mkdir(parents=True)
    config_path = config_dir / "config.toml"
    config_path.write_text(f"""
[repo]
base_dir = "{str(repos_dir).replace(chr(92), "/")}"
flat = true

[repo.groups.pymongo]
repos = ["https://github.com/mongodb/mongo-python-driver.git"]
""")
    with patch("dbx_python_cli.utils.repo.get_config_path", return_value=config_path):
        result = runner.invoke(app, ["spec", "sync", "--dry-run"])
    assert result.exit_code != 0


def test_spec_sync_missing_driver_repo(mock_config):
    with patch("dbx_python_cli.utils.repo.get_config_path", return_value=mock_config):
        result = runner.invoke(
            app, ["spec", "sync", "-r", "nonexistent-repo", "--dry-run"]
        )
    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# dbx spec list
# ---------------------------------------------------------------------------


def test_spec_list(mock_config):
    with patch("dbx_python_cli.utils.repo.get_config_path", return_value=mock_config):
        result = runner.invoke(app, ["spec", "list"])
    assert result.exit_code == 0
    assert "crud" in result.output
    assert "sessions" in result.output
    assert "transactions" in result.output
    assert "change-streams" in result.output


def test_spec_list_with_specs_dir(temp_repos_dir):
    specs_path = str(temp_repos_dir / "specifications")
    result = runner.invoke(app, ["spec", "list", "--specs-dir", specs_path])
    assert result.exit_code == 0
    assert "crud" in result.output


# ---------------------------------------------------------------------------
# dbx spec patch list
# ---------------------------------------------------------------------------


def test_patch_list_empty(mock_config):
    with patch("dbx_python_cli.utils.repo.get_config_path", return_value=mock_config):
        result = runner.invoke(app, ["spec", "patch", "list"])
    assert result.exit_code == 0
    assert "No patch files" in result.output


def test_patch_list_with_patches(mock_config_with_patches):
    with patch(
        "dbx_python_cli.utils.repo.get_config_path",
        return_value=mock_config_with_patches,
    ):
        result = runner.invoke(app, ["spec", "patch", "list"])
    assert result.exit_code == 0
    assert "PYTHON-1234" in result.output
    assert "PYTHON-5678" in result.output


def test_patch_list_verbose_shows_files(mock_config_with_patches):
    with patch(
        "dbx_python_cli.utils.repo.get_config_path",
        return_value=mock_config_with_patches,
    ):
        result = runner.invoke(app, ["-v", "spec", "patch", "list"])
    assert result.exit_code == 0
    assert "test/crud/foo.json" in result.output


def test_patch_list_missing_driver_repo(mock_config):
    with patch("dbx_python_cli.utils.repo.get_config_path", return_value=mock_config):
        result = runner.invoke(app, ["spec", "patch", "list", "-r", "nonexistent"])
    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# dbx spec patch create
# ---------------------------------------------------------------------------


def test_patch_create_dry_run(mock_config, temp_repos_dir):
    with patch("dbx_python_cli.utils.repo.get_config_path", return_value=mock_config):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = SAMPLE_PATCH
            result = runner.invoke(
                app, ["spec", "patch", "create", "PYTHON-9999", "--dry-run"]
            )
    assert result.exit_code == 0
    assert "Would write" in result.output
    assert "PYTHON-9999" in result.output
    assert "diff --git" in result.output


def test_patch_create_writes_file(mock_config, temp_repos_dir):
    patch_path = (
        temp_repos_dir
        / "mongo-python-driver"
        / ".evergreen"
        / "spec-patch"
        / "PYTHON-9999.patch"
    )
    with patch("dbx_python_cli.utils.repo.get_config_path", return_value=mock_config):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = SAMPLE_PATCH
            result = runner.invoke(app, ["spec", "patch", "create", "PYTHON-9999"])
    assert result.exit_code == 0
    assert patch_path.exists()
    assert "Created" in result.output


def test_patch_create_empty_diff(mock_config):
    with patch("dbx_python_cli.utils.repo.get_config_path", return_value=mock_config):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = ""
            result = runner.invoke(app, ["spec", "patch", "create", "PYTHON-9999"])
    assert result.exit_code != 0
    assert "empty" in result.output.lower()


def test_patch_create_already_exists(mock_config_with_patches):
    with patch(
        "dbx_python_cli.utils.repo.get_config_path",
        return_value=mock_config_with_patches,
    ):
        result = runner.invoke(app, ["spec", "patch", "create", "PYTHON-1234"])
    assert result.exit_code != 0
    assert "already exists" in result.output


# ---------------------------------------------------------------------------
# dbx spec patch remove
# ---------------------------------------------------------------------------


def test_patch_remove(mock_config_with_patches, temp_repos_dir):
    patch_path = (
        temp_repos_dir
        / "mongo-python-driver"
        / ".evergreen"
        / "spec-patch"
        / "PYTHON-1234.patch"
    )
    assert patch_path.exists()
    with patch(
        "dbx_python_cli.utils.repo.get_config_path",
        return_value=mock_config_with_patches,
    ):
        result = runner.invoke(app, ["spec", "patch", "remove", "PYTHON-1234"])
    assert result.exit_code == 0
    assert not patch_path.exists()
    assert "Removed" in result.output


def test_patch_remove_not_found(mock_config):
    with patch("dbx_python_cli.utils.repo.get_config_path", return_value=mock_config):
        result = runner.invoke(app, ["spec", "patch", "remove", "PYTHON-9999"])
    assert result.exit_code != 0
    assert "not found" in result.output.lower()


# ---------------------------------------------------------------------------
# dbx spec patch apply
# ---------------------------------------------------------------------------


def test_patch_apply_dry_run(mock_config_with_patches):
    with patch(
        "dbx_python_cli.utils.repo.get_config_path",
        return_value=mock_config_with_patches,
    ):
        result = runner.invoke(app, ["spec", "patch", "apply", "--dry-run"])
    assert result.exit_code == 0
    assert "PYTHON-1234" in result.output
    assert "PYTHON-5678" in result.output


def test_patch_apply_no_patches(mock_config):
    with patch("dbx_python_cli.utils.repo.get_config_path", return_value=mock_config):
        result = runner.invoke(app, ["spec", "patch", "apply"])
    assert result.exit_code == 0
    assert "No patch files" in result.output


def test_patch_apply_runs_git(mock_config_with_patches):
    with patch(
        "dbx_python_cli.utils.repo.get_config_path",
        return_value=mock_config_with_patches,
    ):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stderr = ""
            result = runner.invoke(app, ["spec", "patch", "apply"])
    assert result.exit_code == 0
    assert "All patches applied" in result.output
    called_cmd = mock_run.call_args[0][0]
    assert "git" in called_cmd
    assert "apply" in called_cmd
    assert "-R" in called_cmd
