"""Tests for the sync command's downstream CI re-run helpers."""

import subprocess
from unittest import mock

from dbx_python_cli.commands.sync import (
    _gh_error_message,
    _pr_state,
    _rerun_pr_ci,
    _retry_evergreen,
)


def _json_stub(responses):
    """Build a `_gh_json` stub returning canned values per `gh` subcommand."""

    def _gh_json(args):
        if args[0] == "pr":
            return responses["pr"]
        return responses["runs"]

    return _gh_json


def test_gh_error_message_extracts_api_message():
    stderr = (
        '{"message":"Unable to retry this workflow run because it was created '
        'over a month ago","status":"403"}\n'
        "gh: Unable to retry this workflow run because it was created over a "
        "month ago (HTTP 403)\n"
    )
    assert _gh_error_message(stderr) == (
        "Unable to retry this workflow run because it was created over a "
        "month ago (HTTP 403)"
    )


def test_gh_error_message_handles_empty():
    assert _gh_error_message("") == ""
    assert _gh_error_message(None) == ""


def test_pr_state_returns_none_on_error():
    def _gh_json(args):
        raise subprocess.CalledProcessError(1, "gh", stderr="boom")

    assert _pr_state("o/r", 1, _gh_json) is None


def test_rerun_pr_ci_skips_closed_pr(capsys):
    _gh_json = _json_stub({"pr": {"state": "CLOSED", "headRefOid": "abc"}, "runs": [1]})
    with mock.patch("subprocess.run") as run:
        _rerun_pr_ci("o/r", 535, "mongodb-6.2.x", False, _gh_json)
    run.assert_not_called()
    err = capsys.readouterr().err
    assert "PR is closed" in err
    assert "ci_rerun mapping" in err


def test_rerun_pr_ci_reports_real_reason_when_runs_too_old(capsys):
    _gh_json = _json_stub(
        {"pr": {"state": "OPEN", "headRefOid": "abc"}, "runs": [1, 2]}
    )
    stderr = (
        "gh: Unable to retry this workflow run because it was created over a "
        "month ago (HTTP 403)\n"
    )
    with mock.patch(
        "subprocess.run",
        side_effect=subprocess.CalledProcessError(1, "gh", stderr=stderr),
    ):
        _rerun_pr_ci("o/r", 422, "mongodb-6.1.x", False, _gh_json)
    err = capsys.readouterr().err
    assert "no runs re-queued: Unable to retry" in err
    # The old message guessed "already running or no permission"; the hint must
    # point at the actual fix instead.
    assert "no permission" not in err
    assert "30-day retry window" in err


def test_rerun_pr_ci_reports_success(capsys):
    _gh_json = _json_stub(
        {"pr": {"state": "OPEN", "headRefOid": "abc"}, "runs": [1, 2]}
    )
    with mock.patch("subprocess.run"):
        _rerun_pr_ci("o/r", 562, "mongodb-5.2.x", False, _gh_json)
    assert "✓ queued (2 workflow run(s))" in capsys.readouterr().out


def test_retry_evergreen_skips_closed_pr(capsys):
    _gh_json = _json_stub({"pr": {"state": "MERGED"}, "runs": []})
    with mock.patch("subprocess.run") as run:
        _retry_evergreen("o/r", 535, "mongodb-6.2.x", False, _gh_json)
    run.assert_not_called()
    assert "PR is merged" in capsys.readouterr().err


def test_retry_evergreen_comments_on_open_pr(capsys):
    _gh_json = _json_stub({"pr": {"state": "OPEN"}, "runs": []})
    with mock.patch("subprocess.run") as run:
        _retry_evergreen("o/r", 562, "mongodb-5.2.x", False, _gh_json)
    assert "evergreen retry" in run.call_args.args[0]
    assert "✓ commented 'evergreen retry'" in capsys.readouterr().out
