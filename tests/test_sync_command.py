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


def test_branch_series_derives_release_series():
    from dbx_python_cli.commands.sync import _branch_series

    assert _branch_series("mongodb-5.2.x") == "5.2"
    assert _branch_series("mongodb-6.0.x") == "6.0"
    assert _branch_series("main") is None


def _completed(cmd, stdout=""):
    return subprocess.CompletedProcess(cmd, 0, stdout=stdout, stderr="")


def test_latest_release_tag_picks_highest_patch_numerically():
    """5.2.10 must beat 5.2.4 (lexical sorting would pick 5.2.4)."""
    from dbx_python_cli.commands.sync import _latest_release_tag

    def side_effect(cmd, **kwargs):
        if "tag" in cmd:
            return _completed(cmd, "5.2.0\n5.2.4\n5.2.10\n5.2.0b1\n")
        return _completed(cmd, "2026-08-24T10:00:00-04:00")

    with mock.patch(
        "dbx_python_cli.commands.sync.subprocess.run", side_effect=side_effect
    ):
        assert _latest_release_tag("/repo", "5.2") == (
            "5.2.10",
            "2026-08-24T10:00:00-04:00",
        )


def test_latest_release_tag_none_when_series_unreleased():
    from dbx_python_cli.commands.sync import _latest_release_tag

    with mock.patch(
        "dbx_python_cli.commands.sync.subprocess.run",
        side_effect=lambda cmd, **kw: _completed(cmd, ""),
    ):
        assert _latest_release_tag("/repo", "6.2") is None


def test_classify_cycle_picks_earliest_matching_forkpoint():
    """A commit is in the X.Y cycle when it is an ancestor of stable/X.Y.x's fork
    point but of no earlier one; anything past every fork point is in-development."""
    from dbx_python_cli.commands.sync import _classify_cycle

    cycles = [((6, 0), "6.0", "fp60"), ((6, 1), "6.1", "fp61")]
    # "old" predates both fork points, "mid" only fp61, "new" neither.
    ancestors = {("old", "fp60"), ("old", "fp61"), ("mid", "fp61")}

    def side_effect(cmd, **kwargs):
        sha, forkpoint = cmd[-2], cmd[-1]
        code = 0 if (sha, forkpoint) in ancestors else 1
        return subprocess.CompletedProcess(cmd, code, stdout="", stderr="")

    with mock.patch(
        "dbx_python_cli.commands.sync.subprocess.run", side_effect=side_effect
    ):
        cache = {}
        assert _classify_cycle("/p", "old", cycles, "6.2", cache) == "6.0"
        assert _classify_cycle("/p", "mid", cycles, "6.2", cache) == "6.1"
        assert _classify_cycle("/p", "new", cycles, "6.2", cache) == "6.2"
    # Cached results are reused without shelling out again.
    with mock.patch("dbx_python_cli.commands.sync.subprocess.run") as run:
        assert _classify_cycle("/p", "mid", cycles, "6.2", cache) == "6.1"
        run.assert_not_called()


def _report_git_stub(commits_by_ref, tags="5.2.4\n"):
    """Stub git for _print_backport_report: cycles, tags, and per-ref commit logs."""

    def side_effect(cmd, **kwargs):
        if "for-each-ref" in cmd:
            return _completed(cmd, "upstream/stable/5.2.x\nupstream/stable/6.0.x\n")
        if "merge-base" in cmd and "--is-ancestor" in cmd:
            # Source shas prefixed "abc" belong to an already-cut cycle.
            code = 0 if cmd[-2].startswith("abc") else 1
            return subprocess.CompletedProcess(cmd, code, stdout="", stderr="")
        if "merge-base" in cmd:
            return _completed(cmd, f"fp-{cmd[-1]}")
        if "show" in cmd:
            return _completed(cmd, "VERSION = (6, 2, 0, 'alpha', 0)")
        if "tag" in cmd:
            return _completed(cmd, tags)
        if "log" in cmd and "-1" in cmd:
            return _completed(cmd, "2026-08-24T10:00:00-04:00")
        if "log" in cmd:
            ref = next(a for a in cmd if a.startswith("upstream/"))
            return _completed(cmd, commits_by_ref.get(ref, ""))
        return _completed(cmd)

    return side_effect


def _run_report(side_effect, mapping, config=None):
    from dbx_python_cli.commands import sync

    repo_info = {"path": "/repos/django", "name": "django", "group": "django"}
    with (
        mock.patch(
            "dbx_python_cli.utils.repo.get_release_repo",
            return_value="django-mongodb-backend",
        ),
        mock.patch(
            "dbx_python_cli.utils.repo.find_repo_by_name",
            return_value={"path": "/repos/django-mongodb-backend"},
        ),
        mock.patch("dbx_python_cli.utils.repo.get_base_dir", return_value="/repos"),
        mock.patch(
            "dbx_python_cli.commands.sync.subprocess.run", side_effect=side_effect
        ),
    ):
        sync._print_backport_report(
            repo_info, config or {}, mapping, list(mapping.keys())
        )


def test_print_backport_report_lists_new_commits_with_cycle_labels(capsys):
    commit = (
        "\x01deadbeefcafe\x02deadbee\x022026-08-25\x02"
        "[5.2.x] Fixed CVE-2026-1 -- Something.\x02"
        "Backport of abc1234def from main."
    )
    unannotated = (
        "\x01aaaabbbbcccc\x02aaaabbb\x022026-08-25\x02"
        "[5.2.x] Post-release version bump.\x02"
    )
    _run_report(
        _report_git_stub({"upstream/stable/5.2.x": commit + unannotated}),
        {"mongodb-5.2.x": "stable/5.2.x"},
    )
    out = capsys.readouterr().out
    assert "django-mongodb-backend 5.2.4 (2026-08-24)" in out
    assert "2 new commit(s)" in out
    assert "[5.2 cycle] deadbee 2026-08-25 [5.2.x] Fixed CVE-2026-1" in out
    assert "[unannotated] aaaabbb" in out


def test_print_backport_report_reports_clean_branch(capsys):
    _run_report(_report_git_stub({}), {"mongodb-5.2.x": "stable/5.2.x"})
    out = capsys.readouterr().out
    assert "nothing new upstream" in out


def test_print_backport_report_notes_unreleased_series(capsys):
    _run_report(
        _report_git_stub({}, tags=""),
        {"mongodb-6.2.x": "main"},
    )
    assert (
        "No 6.2.* release tag in django-mongodb-backend yet" in capsys.readouterr().out
    )


def test_print_backport_report_skips_without_release_repo(capsys):
    from dbx_python_cli.commands import sync

    with (
        mock.patch("dbx_python_cli.utils.repo.get_release_repo", return_value=None),
        mock.patch("dbx_python_cli.commands.sync.subprocess.run") as run,
    ):
        sync._print_backport_report(
            {"path": "/p", "name": "django", "group": "django"},
            {},
            {"mongodb-5.2.x": "stable/5.2.x"},
            ["mongodb-5.2.x"],
        )
    run.assert_not_called()
    assert capsys.readouterr().out == ""
