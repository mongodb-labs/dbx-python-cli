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


# ---------------------------------------------------------------------------
# dbx spec status — unit helpers
# ---------------------------------------------------------------------------

SAMPLE_RESYNC_SCRIPT = """\
#!/bin/bash
set -eu
PYMONGO=$(dirname "$(cd "$(dirname "$0")"; pwd)")
SPECS=${MDB_SPECS:-~/Work/specifications}

for spec in "$@"
do
  case "$spec" in
    auth)
      cpjson auth/tests auth
      ;;
    bson-binary-vector|bson_binary_vector)
      cpjson bson-binary-vector/tests bson_binary_vector
      ;;
    sdam|SDAM|server-discovery-and-monitoring)
      cpjson server-discovery-and-monitoring/tests/errors \\
      discovery_and_monitoring/errors
      cpjson server-discovery-and-monitoring/tests/rs \\
      discovery_and_monitoring/rs
      ;;
    crud|CRUD)
      cpjson crud/tests crud
      ;;
    *)
      echo "Unknown spec"; exit 1
      ;;
  esac
done
"""


def test_parse_resync_script_basic(tmp_path):
    from dbx_python_cli.commands.spec import _parse_resync_script

    script = tmp_path / "resync-specs.sh"
    script.write_text(SAMPLE_RESYNC_SCRIPT)
    result = _parse_resync_script(script)

    assert "auth" in result
    assert result["auth"] == [("auth/tests", "auth")]

    assert "bson-binary-vector" in result
    assert result["bson-binary-vector"] == [
        ("bson-binary-vector/tests", "bson_binary_vector")
    ]

    assert "crud" in result
    assert result["crud"] == [("crud/tests", "crud")]


def test_parse_resync_script_multiline_cpjson(tmp_path):
    """cpjson calls split across lines via backslash continuations are joined."""
    from dbx_python_cli.commands.spec import _parse_resync_script

    script = tmp_path / "resync-specs.sh"
    script.write_text(SAMPLE_RESYNC_SCRIPT)
    result = _parse_resync_script(script)

    assert "sdam" in result
    assert (
        "server-discovery-and-monitoring/tests/errors",
        "discovery_and_monitoring/errors",
    ) in result["sdam"]
    assert (
        "server-discovery-and-monitoring/tests/rs",
        "discovery_and_monitoring/rs",
    ) in result["sdam"]


def test_parse_resync_script_skips_default_case(tmp_path):
    from dbx_python_cli.commands.spec import _parse_resync_script

    script = tmp_path / "resync-specs.sh"
    script.write_text(SAMPLE_RESYNC_SCRIPT)
    result = _parse_resync_script(script)

    # '*' default case should not appear
    assert "*" not in result


def test_parse_resync_script_missing_file(tmp_path):
    from dbx_python_cli.commands.spec import _parse_resync_script

    result = _parse_resync_script(tmp_path / "nonexistent.sh")
    assert result == {}


def test_spec_is_stale_missing_dst(tmp_path):
    from dbx_python_cli.commands.spec import _spec_is_stale

    src_dir = tmp_path / "specs" / "auth" / "tests"
    src_dir.mkdir(parents=True)
    (src_dir / "foo.json").write_text('{"a": 1}')

    driver_test = tmp_path / "driver" / "test"
    driver_test.mkdir(parents=True)
    # auth dir intentionally NOT created in driver

    stale, reason = _spec_is_stale(
        tmp_path / "specs",
        driver_test,
        [("auth/tests", "auth")],
    )
    assert stale is True
    assert "missing" in reason


def test_spec_is_stale_content_differs(tmp_path):
    from dbx_python_cli.commands.spec import _spec_is_stale

    src_dir = tmp_path / "specs" / "crud" / "tests"
    src_dir.mkdir(parents=True)
    (src_dir / "foo.json").write_text('{"new": true}')

    dst_dir = tmp_path / "driver" / "test" / "crud"
    dst_dir.mkdir(parents=True)
    (dst_dir / "foo.json").write_text('{"old": true}')

    stale, reason = _spec_is_stale(
        tmp_path / "specs",
        tmp_path / "driver" / "test",
        [("crud/tests", "crud")],
    )
    assert stale is True
    assert "differs" in reason


def test_spec_is_stale_up_to_date(tmp_path):
    from dbx_python_cli.commands.spec import _spec_is_stale

    content = '{"same": true}'
    src_dir = tmp_path / "specs" / "auth" / "tests"
    src_dir.mkdir(parents=True)
    (src_dir / "foo.json").write_text(content)

    dst_dir = tmp_path / "driver" / "test" / "auth"
    dst_dir.mkdir(parents=True)
    (dst_dir / "foo.json").write_text(content)

    stale, _ = _spec_is_stale(
        tmp_path / "specs",
        tmp_path / "driver" / "test",
        [("auth/tests", "auth")],
    )
    assert stale is False


def test_spec_is_stale_new_file_in_src(tmp_path):
    from dbx_python_cli.commands.spec import _spec_is_stale

    src_dir = tmp_path / "specs" / "crud" / "tests"
    src_dir.mkdir(parents=True)
    (src_dir / "existing.json").write_text('{"x": 1}')
    (src_dir / "new-file.json").write_text('{"y": 2}')

    dst_dir = tmp_path / "driver" / "test" / "crud"
    dst_dir.mkdir(parents=True)
    (dst_dir / "existing.json").write_text('{"x": 1}')
    # new-file.json intentionally absent from driver

    stale, reason = _spec_is_stale(
        tmp_path / "specs",
        tmp_path / "driver" / "test",
        [("crud/tests", "crud")],
    )
    assert stale is True
    assert "new file" in reason


def test_spec_is_stale_src_missing_skips(tmp_path):
    """If the source directory doesn't exist, skip and report not stale."""
    from dbx_python_cli.commands.spec import _spec_is_stale

    driver_test = tmp_path / "driver" / "test"
    driver_test.mkdir(parents=True)

    stale, _ = _spec_is_stale(
        tmp_path / "specs",  # source dir does not exist
        driver_test,
        [("nonexistent-spec/tests", "nonexistent")],
    )
    assert stale is False


# ---------------------------------------------------------------------------
# dbx spec status — integration (CLI)
# ---------------------------------------------------------------------------


def _make_status_repos(tmp_path, content_same=True):
    """Build a minimal repo layout for spec status tests.

    Returns (repos_dir, config_path).
    """
    repos_dir = tmp_path / "repos"
    repos_dir.mkdir()

    # Driver repo
    driver = repos_dir / "mongo-python-driver"
    driver.mkdir()
    (driver / ".git").mkdir()
    ev_dir = driver / ".evergreen"
    ev_dir.mkdir()
    resync = ev_dir / "resync-specs.sh"
    resync.write_text(SAMPLE_RESYNC_SCRIPT)
    resync.chmod(0o755)
    (ev_dir / "spec-patch").mkdir()

    # Driver test dir
    test_dir = driver / "test"
    auth_dst = test_dir / "auth"
    auth_dst.mkdir(parents=True)
    auth_json = '{"spec": "auth"}' if content_same else '{"spec": "old"}'
    (auth_dst / "auth.json").write_text(auth_json)

    # Specs repo
    specs = repos_dir / "specifications"
    specs.mkdir()
    (specs / ".git").mkdir()
    src_auth = specs / "source" / "auth" / "tests"
    src_auth.mkdir(parents=True)
    (src_auth / "auth.json").write_text('{"spec": "auth"}')

    # Config
    cfg_dir = tmp_path / ".config" / "dbx-python-cli"
    cfg_dir.mkdir(parents=True)
    cfg = cfg_dir / "config.toml"
    repos_str = str(repos_dir).replace("\\", "/")
    cfg.write_text(f"""
[repo]
base_dir = "{repos_str}"
flat = true

[repo.groups.pymongo]
repos = [
    "https://github.com/mongodb/mongo-python-driver.git",
    "https://github.com/mongodb/specifications.git",
]
""")
    return repos_dir, cfg


def test_spec_status_all_up_to_date(tmp_path):
    _, cfg = _make_status_repos(tmp_path, content_same=True)
    with (
        patch("dbx_python_cli.utils.repo.get_config_path", return_value=cfg),
        patch(
            "dbx_python_cli.commands.spec._get_current_branch",
            return_value="spec-resync-test",
        ),
        patch(
            "dbx_python_cli.commands.spec._find_recent_resync_commits",
            return_value=["abc1234 resync: auth (2 days ago)"],
        ),
        patch(
            "dbx_python_cli.commands.spec._commit_relative_date",
            return_value="2 days ago",
        ),
    ):
        result = runner.invoke(app, ["spec", "status"])
    assert result.exit_code == 0
    assert "All checked specs are up to date" in result.output


def test_spec_status_stale_spec(tmp_path):
    _, cfg = _make_status_repos(tmp_path, content_same=False)
    with (
        patch("dbx_python_cli.utils.repo.get_config_path", return_value=cfg),
        patch(
            "dbx_python_cli.commands.spec._get_current_branch",
            return_value="spec-resync-test",
        ),
        patch(
            "dbx_python_cli.commands.spec._find_recent_resync_commits",
            return_value=["abc1234 resync: auth"],
        ),
        patch(
            "dbx_python_cli.commands.spec._commit_relative_date",
            return_value="5 days ago",
        ),
    ):
        result = runner.invoke(app, ["spec", "status"])
    assert result.exit_code == 0
    assert "dbx spec sync auth" in result.output


def test_spec_status_no_resync_commit(tmp_path):
    _, cfg = _make_status_repos(tmp_path, content_same=True)
    with (
        patch("dbx_python_cli.utils.repo.get_config_path", return_value=cfg),
        patch(
            "dbx_python_cli.commands.spec._get_current_branch",
            return_value="some-unrelated-branch",
        ),
        patch(
            "dbx_python_cli.commands.spec._find_recent_resync_commits",
            return_value=[],
        ),
    ):
        result = runner.invoke(app, ["spec", "status"])
    assert result.exit_code == 0
    assert "No resync commit" in result.output
    assert "does not look like a spec-resync branch" in result.output


def test_spec_status_branch_icon(tmp_path):
    _, cfg = _make_status_repos(tmp_path, content_same=True)
    with (
        patch("dbx_python_cli.utils.repo.get_config_path", return_value=cfg),
        patch(
            "dbx_python_cli.commands.spec._get_current_branch",
            return_value="spec-resync-2026-05",
        ),
        patch(
            "dbx_python_cli.commands.spec._find_recent_resync_commits",
            return_value=["abc resync all"],
        ),
        patch(
            "dbx_python_cli.commands.spec._commit_relative_date",
            return_value="1 day ago",
        ),
    ):
        result = runner.invoke(app, ["spec", "status"])
    assert result.exit_code == 0
    assert "✓" in result.output


def test_spec_status_suggests_combined_command(tmp_path):
    """When multiple specs are stale the footer lists them in one command."""
    _, cfg = _make_status_repos(tmp_path, content_same=False)
    with (
        patch("dbx_python_cli.utils.repo.get_config_path", return_value=cfg),
        patch(
            "dbx_python_cli.commands.spec._get_current_branch",
            return_value="spec-resync-test",
        ),
        patch(
            "dbx_python_cli.commands.spec._find_recent_resync_commits",
            return_value=["abc resync"],
        ),
        patch(
            "dbx_python_cli.commands.spec._commit_relative_date",
            return_value="1 day ago",
        ),
    ):
        result = runner.invoke(app, ["spec", "status"])
    assert result.exit_code == 0
    assert "dbx spec sync" in result.output
    assert "Sync remaining specs" in result.output


def test_commit_spec_dirs(tmp_path):
    """_commit_spec_dirs extracts unique test subdirs from a real git commit."""
    from dbx_python_cli.commands.spec import _commit_spec_dirs
    from unittest.mock import patch, MagicMock

    mock_result = MagicMock()
    mock_result.stdout = (
        "test/crud/foo.json\n"
        "test/crud/bar.json\n"
        "test/sessions/baz.json\n"
        ".evergreen/resync-specs.sh\n"  # non-test file should be ignored
        "test/auth/qux.json\n"
    )

    with patch("subprocess.run", return_value=mock_result):
        dirs = _commit_spec_dirs(tmp_path, "abc1234")

    assert dirs == ["auth", "crud", "sessions"]


def test_commit_spec_dirs_no_test_files(tmp_path):
    from dbx_python_cli.commands.spec import _commit_spec_dirs
    from unittest.mock import patch, MagicMock

    mock_result = MagicMock()
    mock_result.stdout = ".evergreen/resync-specs.sh\n"

    with patch("subprocess.run", return_value=mock_result):
        dirs = _commit_spec_dirs(tmp_path, "abc1234")

    assert dirs == []


def test_spec_status_shows_specs_touched(tmp_path):
    _, cfg = _make_status_repos(tmp_path, content_same=True)
    with (
        patch("dbx_python_cli.utils.repo.get_config_path", return_value=cfg),
        patch(
            "dbx_python_cli.commands.spec._get_current_branch",
            return_value="spec-resync-test",
        ),
        patch(
            "dbx_python_cli.commands.spec._find_recent_resync_commits",
            return_value=["abc1234 resyncing specs 05-18-2026"],
        ),
        patch(
            "dbx_python_cli.commands.spec._commit_relative_date",
            return_value="3 days ago",
        ),
        patch(
            "dbx_python_cli.commands.spec._commit_spec_dirs",
            return_value=["auth", "crud", "sessions"],
        ),
    ):
        result = runner.invoke(app, ["spec", "status"])
    assert result.exit_code == 0
    assert "Specs touched: auth, crud, sessions" in result.output


def test_commit_spec_dirs_requires_subdir(tmp_path):
    """Files directly in test/ (no subdir) should not appear in the result."""
    from dbx_python_cli.commands.spec import _commit_spec_dirs
    from unittest.mock import patch, MagicMock

    mock_result = MagicMock()
    mock_result.stdout = (
        "test/test_database.py\n"  # file directly in test/ — should be skipped
        "test/crud/foo.json\n"  # proper spec subdir — should be included
    )

    with patch("subprocess.run", return_value=mock_result):
        dirs = _commit_spec_dirs(tmp_path, "abc1234")

    assert "test_database.py" not in dirs
    assert "crud" in dirs


def test_spec_status_shows_pr_summary(tmp_path):
    _, cfg = _make_status_repos(tmp_path, content_same=True)
    with (
        patch("dbx_python_cli.utils.repo.get_config_path", return_value=cfg),
        patch(
            "dbx_python_cli.commands.spec._get_current_branch",
            return_value="spec-resync-test",
        ),
        patch(
            "dbx_python_cli.commands.spec._find_recent_resync_commits",
            return_value=["abc1234 resyncing specs"],
        ),
        patch(
            "dbx_python_cli.commands.spec._commit_relative_date",
            return_value="1 day ago",
        ),
        patch(
            "dbx_python_cli.commands.spec._commit_spec_dirs",
            return_value=["auth", "crud"],
        ),
        patch(
            "dbx_python_cli.commands.spec._branch_summary",
            return_value=(["auth", "crud", "sessions"], 3),
        ),
    ):
        result = runner.invoke(app, ["spec", "status"])
    assert result.exit_code == 0
    assert "PR summary" in result.output
    assert "3 commits ahead of main" in result.output
    assert "Specs synced so far: auth, crud, sessions" in result.output


def test_spec_status_verify_section_no_stale(tmp_path):
    """When nothing is stale, shows 'Nothing outstanding' message."""
    _, cfg = _make_status_repos(tmp_path, content_same=True)
    with (
        patch("dbx_python_cli.utils.repo.get_config_path", return_value=cfg),
        patch(
            "dbx_python_cli.commands.spec._get_current_branch",
            return_value="spec-resync-test",
        ),
        patch(
            "dbx_python_cli.commands.spec._find_recent_resync_commits",
            return_value=["abc resyncing specs"],
        ),
        patch(
            "dbx_python_cli.commands.spec._commit_relative_date",
            return_value="1 day ago",
        ),
        patch(
            "dbx_python_cli.commands.spec._commit_spec_dirs",
            return_value=["auth"],
        ),
        patch(
            "dbx_python_cli.commands.spec._branch_summary",
            return_value=(["auth"], 1),
        ),
    ):
        result = runner.invoke(app, ["spec", "status"])
    assert result.exit_code == 0
    assert "Nothing outstanding" in result.output


def test_patch_dir_map(tmp_path):
    """_patch_dir_map returns a dir→tickets reverse map from patch files."""
    from dbx_python_cli.commands.spec import _patch_dir_map

    patch_dir = tmp_path / "spec-patch"
    patch_dir.mkdir()
    (patch_dir / "PYTHON-1234.patch").write_text(
        "diff --git a/test/crud/foo.json b/test/crud/foo.json\n"
        "diff --git a/test/unified-test-format/bar.json b/test/unified-test-format/bar.json\n"
    )
    (patch_dir / "PYTHON-5678.patch").write_text(
        "diff --git a/test/crud/baz.json b/test/crud/baz.json\n"
    )

    result = _patch_dir_map(patch_dir)

    assert "crud" in result
    assert "PYTHON-1234" in result["crud"]
    assert "PYTHON-5678" in result["crud"]
    assert "unified-test-format" in result
    assert result["unified-test-format"] == ["PYTHON-1234"]


def test_spec_status_annotates_patches(tmp_path):
    """Stale specs that have an active patch should show the ticket."""
    _, cfg = _make_status_repos(tmp_path, content_same=False)

    # Add a patch covering the auth test dir
    patch_dir = tmp_path / "repos" / "mongo-python-driver" / ".evergreen" / "spec-patch"
    (patch_dir / "PYTHON-9999.patch").write_text(
        "diff --git a/test/auth/auth.json b/test/auth/auth.json\n"
        "index abc..def 100644\n"
        "--- a/test/auth/auth.json\n"
        "+++ b/test/auth/auth.json\n"
        "@@ -1 +1 @@\n"
        "-old\n"
        "+new\n"
    )

    with (
        patch("dbx_python_cli.utils.repo.get_config_path", return_value=cfg),
        patch(
            "dbx_python_cli.commands.spec._get_current_branch",
            return_value="spec-resync-test",
        ),
        patch(
            "dbx_python_cli.commands.spec._find_recent_resync_commits",
            return_value=["abc resyncing"],
        ),
        patch(
            "dbx_python_cli.commands.spec._commit_relative_date",
            return_value="1 day ago",
        ),
        patch("dbx_python_cli.commands.spec._commit_spec_dirs", return_value=[]),
        patch("dbx_python_cli.commands.spec._branch_summary", return_value=([], 0)),
    ):
        result = runner.invoke(app, ["spec", "status"])

    assert result.exit_code == 0
    assert "PYTHON-9999" in result.output
    assert "🩹" in result.output


def test_spec_status_shows_removable_patches(tmp_path):
    """Patches whose source files no longer exist in specs should be flagged."""
    _, cfg = _make_status_repos(tmp_path, content_same=True)

    patch_dir = tmp_path / "repos" / "mongo-python-driver" / ".evergreen" / "spec-patch"
    # This patch references a file that does NOT exist in the specs repo
    (patch_dir / "PYTHON-GONE.patch").write_text(
        "diff --git a/test/auth/deleted-test.json b/test/auth/deleted-test.json\n"
        "index abc..def 100644\n"
        "--- a/test/auth/deleted-test.json\n"
        "+++ /dev/null\n"
        "@@ -1 +0,0 @@\n"
        "-{}\n"
    )

    with (
        patch("dbx_python_cli.utils.repo.get_config_path", return_value=cfg),
        patch(
            "dbx_python_cli.commands.spec._get_current_branch",
            return_value="spec-resync-test",
        ),
        patch(
            "dbx_python_cli.commands.spec._find_recent_resync_commits",
            return_value=["abc resyncing"],
        ),
        patch(
            "dbx_python_cli.commands.spec._commit_relative_date",
            return_value="1 day ago",
        ),
        patch("dbx_python_cli.commands.spec._commit_spec_dirs", return_value=[]),
        patch("dbx_python_cli.commands.spec._branch_summary", return_value=([], 0)),
    ):
        result = runner.invoke(app, ["spec", "status"])

    assert result.exit_code == 0
    assert "PYTHON-GONE.patch" in result.output
    assert "removable" in result.output.lower()


def test_spec_status_no_removable_patches_when_files_exist(tmp_path):
    """Patches whose source files still exist should NOT be flagged as removable."""
    _, cfg = _make_status_repos(tmp_path, content_same=True)

    patch_dir = tmp_path / "repos" / "mongo-python-driver" / ".evergreen" / "spec-patch"
    # This patch references auth.json which DOES exist in the specs repo
    (patch_dir / "PYTHON-KEEP.patch").write_text(
        "diff --git a/test/auth/auth.json b/test/auth/auth.json\n"
        "index abc..def 100644\n"
        "--- a/test/auth/auth.json\n"
        "+++ /dev/null\n"
        "@@ -1 +0,0 @@\n"
        '-{"spec": "auth"}\n'
    )

    with (
        patch("dbx_python_cli.utils.repo.get_config_path", return_value=cfg),
        patch(
            "dbx_python_cli.commands.spec._get_current_branch",
            return_value="spec-resync-test",
        ),
        patch(
            "dbx_python_cli.commands.spec._find_recent_resync_commits",
            return_value=["abc resyncing"],
        ),
        patch(
            "dbx_python_cli.commands.spec._commit_relative_date",
            return_value="1 day ago",
        ),
        patch("dbx_python_cli.commands.spec._commit_spec_dirs", return_value=[]),
        patch("dbx_python_cli.commands.spec._branch_summary", return_value=([], 0)),
    ):
        result = runner.invoke(app, ["spec", "status"])

    assert result.exit_code == 0
    assert "may be removable" not in result.output
    assert "PYTHON-KEEP.patch" not in result.output
