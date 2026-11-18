"""Tests for the infra command."""

import re
from unittest.mock import patch

from typer.testing import CliRunner

from drivers_python_cli.cli import app
from drivers_python_cli.utils.infra import parse_suite_registry

runner = CliRunner()


def strip_ansi(text):
    """Remove ANSI escape sequences from text."""
    ansi_escape = re.compile(r"\x1b\[[0-9;]*m")
    return ansi_escape.sub("", text)


UTILS_PY = """
TEST_SUITE_MAP = {
    "atlas_connect": "atlas_connect",
    "auth_oidc": "auth_oidc",
    "default": "",
    "enterprise_auth": "auth",
    "load_balancer": "load_balancer",
    "ocsp": "ocsp",
}

EXTRA_TESTS = ["aws_lambda", "doctest"]

NO_RUN_ORCHESTRATION = ["atlas_connect", "auth_oidc", "ocsp"]
"""

OVERLAY = {
    "infra": {
        "mongo-python-driver": {
            "load_balancer": {"requires_tools": ["haproxy"]},
            "enterprise_auth": {"evergreen_only": True},
            "atlas_connect": {"vaults": ["drivers/atlas_connect"]},
            "ocsp": {"env_names": ["ORCHESTRATION_FILE"]},
            "auth_oidc": {
                "notes": "eks needs drivers-test-secrets-role access.",
                "links": {"aws-secrets": "https://wiki.corp.mongodb.com/example"},
            },
        }
    }
}


def make_repo(tmp_path, with_registry=True):
    """Create a fake mongo-python-driver checkout and return (config, base_dir)."""
    base_dir = tmp_path / "base"
    repo_dir = base_dir / "pymongo" / "mongo-python-driver"
    (repo_dir / ".evergreen" / "scripts").mkdir(parents=True)
    (repo_dir / ".git").mkdir()
    if with_registry:
        (repo_dir / ".evergreen" / "scripts" / "utils.py").write_text(UTILS_PY)

    drivers_tools = tmp_path / "drivers-evergreen-tools"
    drivers_tools.mkdir()

    config = {
        "repo": {
            "base_dir": str(base_dir),
            "groups": {
                "pymongo": {
                    "repos": ["git@github.com:mongodb/mongo-python-driver.git"],
                    "test_env": {
                        "mongo-python-driver": {"DRIVERS_TOOLS": str(drivers_tools)}
                    },
                }
            },
        },
        **OVERLAY,
    }
    return config, base_dir


def test_infra_help():
    """Test infra command help."""
    result = runner.invoke(app, ["infra", "--help"])
    assert result.exit_code == 0
    assert "infrastructure requirements" in result.stdout


def test_parse_suite_registry(tmp_path):
    """parse_suite_registry reads the registry without importing it."""
    repo = tmp_path / "repo"
    (repo / ".evergreen" / "scripts").mkdir(parents=True)
    (repo / ".evergreen" / "scripts" / "utils.py").write_text(UTILS_PY)
    registry = parse_suite_registry(repo)
    assert registry["suites"]["load_balancer"] == "load_balancer"
    assert "aws_lambda" in registry["extra"]
    assert "ocsp" in registry["no_orchestration"]


def test_parse_suite_registry_missing(tmp_path):
    """parse_suite_registry returns None without a registry file."""
    assert parse_suite_registry(tmp_path) is None


def test_infra_list_suites(tmp_path):
    """infra list shows suites plus overlay facts."""
    config, _ = make_repo(tmp_path)
    with patch("drivers_python_cli.commands.infra.get_config") as mock_config:
        mock_config.return_value = config
        result = runner.invoke(app, ["infra", "list", "mongo-python-driver"])
    assert result.exit_code == 0
    output = strip_ansi(result.stdout)
    assert "Test suites for mongo-python-driver (8)" in output
    assert "load_balancer" in output
    assert "haproxy" in output
    assert "evergreen-only" in output
    assert "drivers/atlas_connect" in output


def test_infra_list_suite_detail(tmp_path):
    """infra list <suite> shows marker, notes, and links."""
    config, _ = make_repo(tmp_path)
    with patch("drivers_python_cli.commands.infra.get_config") as mock_config:
        mock_config.return_value = config
        result = runner.invoke(
            app, ["infra", "list", "mongo-python-driver", "auth_oidc"]
        )
    assert result.exit_code == 0
    output = strip_ansi(result.stdout)
    assert "pytest marker: auth_oidc" in output
    assert "no run-server step" in output
    assert "eks needs drivers-test-secrets-role access" in output
    assert "https://wiki.corp.mongodb.com/example" in output


def test_infra_list_unknown_suite(tmp_path):
    """infra list with an unknown suite exits 1."""
    config, _ = make_repo(tmp_path)
    with patch("drivers_python_cli.commands.infra.get_config") as mock_config:
        mock_config.return_value = config
        result = runner.invoke(app, ["infra", "list", "mongo-python-driver", "nope"])
    assert result.exit_code == 1


def test_infra_list_no_registry_no_overlay(tmp_path):
    """infra list exits 1 when there is no registry and no overlay."""
    config, _ = make_repo(tmp_path, with_registry=False)
    config = {"repo": config["repo"]}
    with patch("drivers_python_cli.commands.infra.get_config") as mock_config:
        mock_config.return_value = config
        result = runner.invoke(app, ["infra", "list", "mongo-python-driver"])
    assert result.exit_code == 1
    assert "No test suite registry" in result.stdout


def test_infra_check_pass(tmp_path):
    """infra check exits 0 when everything passes."""
    config, _ = make_repo(tmp_path)
    with (
        patch("drivers_python_cli.commands.infra.get_config") as mock_config,
        patch(
            "drivers_python_cli.utils.infra.check_aws_credentials",
            return_value=(
                True,
                "authenticated (account 857654397073, role drivers-test-secrets-role)",
            ),
        ),
        patch(
            "drivers_python_cli.utils.infra.check_tool",
            return_value=(True, "/usr/bin/just"),
        ),
    ):
        mock_config.return_value = config
        result = runner.invoke(app, ["infra", "check", "mongo-python-driver"])
    assert result.exit_code == 0
    assert "All checks passed" in strip_ansi(result.stdout)


def test_infra_check_missing_tool(tmp_path):
    """infra check exits 1 and names the missing tool."""
    config, _ = make_repo(tmp_path)

    def fake_check_tool(name):
        return (
            (False, f"{name} not found on PATH")
            if name == "haproxy"
            else (True, f"/usr/bin/{name}")
        )

    with (
        patch("drivers_python_cli.commands.infra.get_config") as mock_config,
        patch("drivers_python_cli.utils.infra.check_tool", side_effect=fake_check_tool),
    ):
        mock_config.return_value = config
        result = runner.invoke(
            app, ["infra", "check", "mongo-python-driver", "load_balancer"]
        )
    assert result.exit_code == 1
    output = strip_ansi(result.stdout)
    assert "haproxy" in output
    assert "1 check(s) failed" in output


def test_infra_check_env_var_never_prints_value(tmp_path, monkeypatch):
    """infra check reports env vars as set with length, never the value."""
    config, _ = make_repo(tmp_path)
    monkeypatch.setenv("ORCHESTRATION_FILE", "super-secret-orchestration")
    with (
        patch("drivers_python_cli.commands.infra.get_config") as mock_config,
        patch(
            "drivers_python_cli.utils.infra.check_aws_credentials",
            return_value=(False, "skip"),
        ),
        patch(
            "drivers_python_cli.utils.infra.check_tool",
            return_value=(True, "/usr/bin/just"),
        ),
    ):
        mock_config.return_value = config
        result = runner.invoke(app, ["infra", "check", "mongo-python-driver", "ocsp"])
    output = strip_ansi(result.stdout)
    assert "set (26 chars)" in output
    assert "super-secret-orchestration" not in output


def test_infra_check_evergreen_only(tmp_path):
    """infra check flags evergreen-only suites on non-Evergreen hosts."""
    config, _ = make_repo(tmp_path)
    with (
        patch("drivers_python_cli.commands.infra.get_config") as mock_config,
        patch(
            "drivers_python_cli.utils.infra.check_aws_credentials",
            return_value=(False, "skip"),
        ),
        patch(
            "drivers_python_cli.utils.infra.check_tool",
            return_value=(True, "/usr/bin/just"),
        ),
        patch("drivers_python_cli.utils.infra.is_evergreen_host", return_value=False),
    ):
        mock_config.return_value = config
        result = runner.invoke(
            app, ["infra", "check", "mongo-python-driver", "enterprise_auth"]
        )
    assert result.exit_code == 1
    assert "evergreen-only suite" in strip_ansi(result.stdout)


def test_infra_check_unknown_suite(tmp_path):
    """infra check with an unknown suite exits 1."""
    config, _ = make_repo(tmp_path)
    with patch("drivers_python_cli.commands.infra.get_config") as mock_config:
        mock_config.return_value = config
        result = runner.invoke(app, ["infra", "check", "mongo-python-driver", "nope"])
    assert result.exit_code == 1
    assert "unknown suite" in result.output + (result.stderr or "")


ABX_WORKFLOW = """
name: release
on: workflow_dispatch
jobs:
  sign:
    steps:
      - uses: mongodb-labs/abx-release-tools/actions/setup@9d8e5070f37497b4d2d0239c80d65eacc096fdbc
        with:
          aws_role_arn: ${{ vars.AWS_SIGNING_ROLE_ARN }}
          aws_region_name: ${{ vars.AWS_SIGNING_REGION }}
          aws_secret_id: ${{ vars.AWS_SIGNING_SECRET_ID }}
      - uses: mongodb-labs/abx-release-tools/actions/gpg-sign@main
  publish:
    steps:
      - uses: mongodb-labs/abx-release-tools/actions/python/publish@9d8e5070f37497b4d2d0239c80d65eacc096fdbc
"""

ABX_WORKFLOW_CLEAN = """
name: release
on: workflow_dispatch
jobs:
  publish:
    permissions:
      id-token: write
    steps:
      - uses: mongodb-labs/abx-release-tools/actions/setup@9d8e5070f37497b4d2d0239c80d65eacc096fdbc
      - uses: mongodb-labs/abx-release-tools/actions/python/publish@9d8e5070f37497b4d2d0239c80d65eacc096fdbc
"""


def make_abx_repo(tmp_path, workflow=ABX_WORKFLOW):
    """Create a fake strands-mongodb checkout with an ABX release workflow."""
    base_dir = tmp_path / "base"
    repo_dir = base_dir / "abx" / "strands-mongodb"
    (repo_dir / ".github" / "workflows").mkdir(parents=True)
    (repo_dir / ".git").mkdir()
    (repo_dir / ".github" / "workflows" / "release-python.yml").write_text(workflow)
    config = {
        "repo": {
            "base_dir": str(base_dir),
            "groups": {
                "abx": {"repos": ["git@github.com:mongodb/strands-mongodb.git"]}
            },
        }
    }
    return config, base_dir


def test_parse_release_workflows(tmp_path):
    """parse_release_workflows extracts actions, pins, vars, and permissions."""
    from drivers_python_cli.utils.infra import parse_release_workflows

    _config, base_dir = make_abx_repo(tmp_path)
    abx = parse_release_workflows(base_dir / "abx" / "strands-mongodb")
    assert abx is not None
    assert "setup" in abx["actions"]
    assert abx["actions"]["setup"]["pinned"] is True
    assert abx["unpinned"] == ["gpg-sign"]
    assert "AWS_SIGNING_SECRET_ID" in abx["vars"]
    assert abx["files"][0]["id_token_write"] is False


def test_parse_release_workflows_absent(tmp_path):
    """parse_release_workflows returns None without ABX workflow references."""
    from pathlib import Path

    from drivers_python_cli.utils.infra import parse_release_workflows

    config, _ = make_repo(tmp_path)
    repo = Path(config["repo"]["base_dir"]) / "pymongo" / "mongo-python-driver"
    assert parse_release_workflows(repo) is None


def test_infra_list_abx(tmp_path):
    """infra list shows ABX release domains for repos without a suite registry."""
    config, _ = make_abx_repo(tmp_path)
    with patch("drivers_python_cli.commands.infra.get_config") as mock_config:
        mock_config.return_value = config
        result = runner.invoke(app, ["infra", "list", "strands-mongodb"])
    assert result.exit_code == 0
    output = strip_ansi(result.stdout)
    assert "Release workflows for strands-mongodb" in output
    assert "python/publish [pinned]" in output
    assert "gpg-sign [UNPINNED]" in output
    assert "AWS_SIGNING_SECRET_ID" in output


def test_infra_check_abx_failures(tmp_path):
    """infra check flags unpinned actions and missing id-token permission."""
    config, _ = make_abx_repo(tmp_path)
    with (
        patch("drivers_python_cli.commands.infra.get_config") as mock_config,
        patch(
            "drivers_python_cli.utils.infra.check_tool",
            return_value=(True, "/usr/bin/just"),
        ),
    ):
        mock_config.return_value = config
        result = runner.invoke(app, ["infra", "check", "strands-mongodb"])
    assert result.exit_code == 1
    output = strip_ansi(result.stdout)
    assert "not pinned to a commit SHA" in output
    assert "publishes but has no id-token: write" in output


def test_infra_check_abx_clean(tmp_path):
    """infra check passes for a pinned workflow with id-token permission."""
    config, _ = make_abx_repo(tmp_path, workflow=ABX_WORKFLOW_CLEAN)
    with (
        patch("drivers_python_cli.commands.infra.get_config") as mock_config,
        patch(
            "drivers_python_cli.utils.infra.check_tool",
            return_value=(True, "/usr/bin/just"),
        ),
    ):
        mock_config.return_value = config
        result = runner.invoke(app, ["infra", "check", "strands-mongodb"])
    assert result.exit_code == 0
    assert "All checks passed" in strip_ansi(result.stdout)


ABX_WORKFLOW_LOCAL = """
name: release
on: workflow_dispatch
jobs:
  sign:
    permissions:
      id-token: write
    steps:
      - uses: $/.github/actions/release-setup
        with:
          aws_role_arn: ${{ secrets.AWS_SIGNING_ROLE_ARN }}
          aws_secret_id: ${{ secrets.AWS_SIGNING_SECRET_ID }}
      - uses: ./.github/actions/sign-artifacts
  publish:
    permissions:
      id-token: write
    steps:
      - uses: pypa/gh-action-pypi-publish@dc37677b2e1c63e2034f94d8a5b11f265b73ba33
"""


def test_infra_list_local_release_actions(tmp_path):
    """infra list shows repo-local composite actions and secrets."""
    config, _ = make_abx_repo(tmp_path, workflow=ABX_WORKFLOW_LOCAL)
    with patch("drivers_python_cli.commands.infra.get_config") as mock_config:
        mock_config.return_value = config
        result = runner.invoke(app, ["infra", "list", "strands-mongodb"])
    assert result.exit_code == 0
    output = strip_ansi(result.stdout)
    assert "local actions: release-setup, sign-artifacts" in output
    assert "repo secrets: AWS_SIGNING_ROLE_ARN, AWS_SIGNING_SECRET_ID" in output
    assert "id-token: write" in output


def test_infra_check_local_release_actions_pass(tmp_path):
    """A local-action release with id-token permission passes."""
    config, _ = make_abx_repo(tmp_path, workflow=ABX_WORKFLOW_LOCAL)
    with (
        patch("drivers_python_cli.commands.infra.get_config") as mock_config,
        patch(
            "drivers_python_cli.utils.infra.check_tool",
            return_value=(True, "/usr/bin/just"),
        ),
    ):
        mock_config.return_value = config
        result = runner.invoke(app, ["infra", "check", "strands-mongodb"])
    assert result.exit_code == 0
    assert "All checks passed" in strip_ansi(result.stdout)


def test_infra_list_release_section_after_suites_and_no_abx_docs(tmp_path):
    """Release section follows the suite list and only cites ABX docs for ABX repos."""
    config, base_dir = make_repo(tmp_path)
    config["infra"]["mongo-python-driver"]["mod_wsgi"] = {"requires_tools": ["docker"]}
    workflows = base_dir / "pymongo" / "mongo-python-driver" / ".github" / "workflows"
    workflows.mkdir(parents=True)
    (workflows / "release-python.yml").write_text(
        "jobs:\n"
        "  publish:\n"
        "    permissions:\n"
        "      id-token: write\n"
        "    steps:\n"
        "      - uses: pypa/gh-agent-pypi-publish@dc37677b2e1c63e2034f94d8a5b11f265b73ba33\n"
    )
    with patch("drivers_python_cli.commands.infra.get_config") as mock_config:
        mock_config.return_value = config
        result = runner.invoke(app, ["infra", "list", "mongo-python-driver"])
    assert result.exit_code == 0
    output = strip_ansi(result.stdout)
    assert "abx-release-tools.readthedocs.io" not in output
    assert output.index("load_balancer") < output.index("Release workflows for")
    assert output.index("mod_wsgi") < output.index("Release workflows for")
