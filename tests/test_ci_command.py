"""Tests for the ci command."""

import json
import subprocess
from unittest.mock import patch

from typer.testing import CliRunner

from drivers_python_cli.cli import app

runner = CliRunner()


def make_env(tmp_path, with_evergreen=True):
    """Create a fake mongo-python-driver checkout and return its config."""
    base_dir = tmp_path / "repos"
    repo_dir = base_dir / "pymongo" / "mongo-python-driver"
    (repo_dir / ".git").mkdir(parents=True)

    config = {
        "repo": {
            "base_dir": str(base_dir),
            "groups": {
                "pymongo": {"repos": ["git@github.com:mongodb/mongo-python-driver.git"]}
            },
        }
    }
    if with_evergreen:
        config["evergreen"] = {
            "mongo-python-driver": {"project_name": "mongo-python-driver"}
        }
    return config, repo_dir


def completed(cmd, stdout="", stderr="", returncode=0):
    return subprocess.CompletedProcess(
        args=cmd, returncode=returncode, stdout=stdout, stderr=stderr
    )


def fake_run(
    pr=None,
    checks=None,
    runs=None,
    patches=None,
    branch="feature-branch",
    returncode=0,
):
    """Return a _run replacement that answers git, gh, and evergreen calls."""
    pr = pr if pr is not None else []
    checks = checks if checks is not None else []
    runs = runs if runs is not None else []
    patches = patches if patches is not None else []

    def _run(cmd, cwd=None, allow_failure=False):
        if cmd[:2] == ["git", "rev-parse"]:
            return completed(cmd, stdout=branch + "\n")
        if cmd[:3] == ["git", "remote", "get-url"]:
            if cmd[3] == "origin":
                return completed(
                    cmd,
                    stdout="git@github.com:aclark4life/mongo-python-driver.git\n",
                )
            if cmd[3] == "upstream":
                return completed(
                    cmd, stdout="git@github.com:mongodb/mongo-python-driver.git\n"
                )
            return completed(cmd, stderr="error: no such remote", returncode=2)
        if cmd[:2] == ["gh", "pr"] and cmd[2] == "list":
            return completed(cmd, stdout=json.dumps(pr))
        if cmd[:3] == ["gh", "pr", "checks"]:
            return completed(cmd, stdout=json.dumps(checks), returncode=returncode)
        if cmd[:3] == ["gh", "run", "list"]:
            return completed(cmd, stdout=json.dumps(runs))
        if cmd[:2] == ["evergreen", "list-patches"]:
            return completed(cmd, stdout=json.dumps(patches))
        if cmd[:3] == ["evergreen", "client", "get-ui-url"]:
            return completed(cmd, stdout="https://spruce.mongodb.com\n")
        raise AssertionError(f"unexpected command: {cmd}")

    return _run


PR = {
    "number": 3237,
    "state": "OPEN",
    "title": "PYTHON-6183 Reject non-string filename",
    "url": "https://github.com/mongodb/mongo-python-driver/pull/3237",
    "headRefOid": "abc123",
    "headRefName": "feature-branch",
}

CHECKS = [
    {
        "name": "test",
        "state": "SUCCESS",
        "bucket": "pass",
        "link": "",
        "description": "",
    },
]

RUNS = [
    {
        "databaseId": 1,
        "name": "CI",
        "workflowName": "CI",
        "status": "completed",
        "conclusion": "success",
        "event": "push",
        "url": "https://github.com/mongodb/mongo-python-driver/actions/runs/1",
        "createdAt": "2026-11-18T00:00:00Z",
    }
]

PATCHES = [
    {
        "patch_id": "6afe556ff40207000769d8bd",
        "patch_number": 1625,
        "project_id": "mongo-python-driver",
        "branch_name": "feature-branch",
        "status": "started",
        "description": "'mongodb/mongo-python-driver' pull request #3237",
        "create_time": "2026-11-19T01:48:31.634Z",
        "finish_time": None,
    },
    {
        "patch_id": "older-failed",
        "patch_number": 1624,
        "project_id": "mongo-python-driver",
        "branch_name": "feature-branch",
        "status": "failed",
        "description": "same branch, earlier patch",
    },
    {
        "patch_id": "other",
        "patch_number": 1600,
        "project_id": "mongo-python-driver",
        "branch_name": "other-branch",
        "status": "failed",
        "description": "unrelated patch",
    },
    {
        "patch_id": "wrong-project",
        "patch_number": 1601,
        "project_id": "django-mongodb-backend",
        "branch_name": "feature-branch",
        "status": "failed",
        "description": "other project",
    },
]


def invoke(config, args, run):
    with (
        patch("drivers_python_cli.commands.ci.get_config", return_value=config),
        patch("drivers_python_cli.commands.ci.shutil.which", return_value="/bin/x"),
        patch("drivers_python_cli.commands.ci._run", side_effect=run),
    ):
        return runner.invoke(app, ["ci", *args])


def test_ci_help():
    result = runner.invoke(app, ["ci", "--help"])
    assert result.exit_code == 0
    assert "Evergreen" in result.stdout
    assert "GitHub Actions" in result.stdout


def test_ci_reports_both_systems(tmp_path):
    config, _ = make_env(tmp_path)
    result = invoke(
        config,
        ["--json", "mongo-python-driver"],
        fake_run(pr=[PR], checks=CHECKS, patches=PATCHES),
    )

    assert result.exit_code == 0
    report = json.loads(result.stdout)
    assert report["branch"] == "feature-branch"
    assert report["github"]["target"] == "mongodb/mongo-python-driver"
    assert report["github"]["remote"] == "upstream"
    assert report["github"]["pr"]["number"] == 3237
    assert report["github"]["overall"] == "success"
    assert report["evergreen"]["project"] == "mongo-python-driver"
    assert [p["patch_number"] for p in report["evergreen"]["patches"]] == [1625, 1624]
    # Older failed patches are history; the newest patch decides the state.
    assert report["evergreen"]["overall"] == "pending"
    assert report["overall"] == "pending"


def test_ci_failure_exits_one(tmp_path):
    config, _ = make_env(tmp_path)
    failing = [dict(CHECKS[0], state="FAILURE", bucket="fail")]
    result = invoke(
        config,
        ["--json", "mongo-python-driver"],
        fake_run(pr=[PR], checks=failing, patches=PATCHES),
    )

    assert result.exit_code == 1
    report = json.loads(result.stdout)
    assert report["github"]["overall"] == "failure"
    assert report["overall"] == "failure"


def test_ci_without_pr_uses_recent_runs(tmp_path):
    config, _ = make_env(tmp_path)
    result = invoke(
        config,
        ["--json", "mongo-python-driver"],
        fake_run(runs=RUNS, patches=PATCHES),
    )

    assert result.exit_code == 0
    report = json.loads(result.stdout)
    assert report["github"]["pr"] is None
    assert report["github"]["runs"][0]["workflowName"] == "CI"
    assert report["github"]["overall"] == "success"


def test_ci_human_output(tmp_path):
    config, _ = make_env(tmp_path)
    result = invoke(
        config,
        ["mongo-python-driver"],
        fake_run(pr=[PR], checks=CHECKS, patches=PATCHES),
    )

    assert result.exit_code == 0
    assert "CI status: mongo-python-driver (branch: feature-branch)" in result.stdout
    assert "GitHub Actions: mongodb/mongo-python-driver (upstream)" in result.stdout
    assert "PR #3237" in result.stdout
    assert "Evergreen: mongo-python-driver" in result.stdout
    assert "Patch 1625" in result.stdout


def test_ci_detached_head_requires_branch(tmp_path):
    config, _ = make_env(tmp_path)
    result = invoke(config, ["mongo-python-driver"], fake_run(branch="HEAD"))

    assert result.exit_code == 1
    assert "cannot determine the current branch" in result.output


def test_ci_without_evergreen_project(tmp_path):
    config, _ = make_env(tmp_path, with_evergreen=False)
    result = invoke(
        config,
        ["--json", "mongo-python-driver"],
        fake_run(pr=[PR], checks=CHECKS),
    )

    assert result.exit_code == 0
    report = json.loads(result.stdout)
    assert report["evergreen"]["project"] is None
    assert report["evergreen"]["overall"] == "unknown"
    assert "project_name" in report["evergreen"]["error"]


def test_ci_missing_gh_is_reported(tmp_path):
    config, _ = make_env(tmp_path)

    def which(name):
        return None if name == "gh" else "/bin/x"

    with (
        patch("drivers_python_cli.commands.ci.get_config", return_value=config),
        patch("drivers_python_cli.commands.ci.shutil.which", side_effect=which),
        patch(
            "drivers_python_cli.commands.ci._run",
            side_effect=fake_run(patches=PATCHES),
        ),
    ):
        result = runner.invoke(app, ["ci", "--json", "mongo-python-driver"])

    report = json.loads(result.stdout)
    assert "gh not found" in report["github"]["error"]
    assert report["evergreen"]["overall"] == "pending"


def test_pr_checks_no_checks_reported_is_empty(monkeypatch):
    """gh pr checks exits non-zero when a PR has no checks; keep the report."""
    from drivers_python_cli.commands import ci

    def fake(cmd, cwd=None, allow_failure=False):
        return completed(
            cmd,
            stdout="",
            stderr="no checks reported on the 'feature' branch",
            returncode=1,
        )

    monkeypatch.setattr(ci, "_run", fake)
    assert ci._pr_checks("o/r", 1) == []


def test_pr_checks_parses_json_despite_failing_exit_code(monkeypatch):
    from drivers_python_cli.commands import ci

    def fake(cmd, cwd=None, allow_failure=False):
        return completed(cmd, stdout=json.dumps(CHECKS), returncode=1)

    monkeypatch.setattr(ci, "_run", fake)
    assert ci._pr_checks("o/r", 1) == CHECKS


def test_github_repo_from_url():
    from drivers_python_cli.commands import ci

    assert (
        ci._github_repo_from_url("git@github.com:mongodb/mongo-python-driver.git")
        == "mongodb/mongo-python-driver"
    )
    assert (
        ci._github_repo_from_url("https://github.com/mongodb/mongo-python-driver.git")
        == "mongodb/mongo-python-driver"
    )
    assert ci._github_repo_from_url("") is None
