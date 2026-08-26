"""Tests for the backports command."""

import subprocess
from unittest import mock

import pytest
from typer.testing import CliRunner

from dbx_python_cli.commands import backports
from dbx_python_cli.utils.release import is_release_chore

runner = CliRunner()


def _completed(cmd, stdout=""):
    return subprocess.CompletedProcess(cmd, 0, stdout=stdout, stderr="")


@pytest.mark.parametrize(
    ("subject", "expected"),
    [
        ("BUMP 6.2.0.dev0", True),
        ("INTPYTHON-1050 Bump version to 6.1.0 (#615)", True),
        ("Bump the actions group with 2 updates (#619)", True),
        ("Bump actions/setup-python from 6.2.0 to 6.3.0", True),
        ("Update SBOM after dependency changes (#613)", True),
        ("Add stub release notes for 5.2.4", True),
        ("Correct 5.2.3 release date", True),
        ("INTPYTHON-940 Prep 6.0.3 release (#514)", True),
        ("Remove timgraham from CODEOWNERS (#600)", True),
        # Moving main to the next feature release is what a release branch exists
        # to be spared, so it is never a backport candidate.
        ("INTPYTHON-1006 Update to Django 6.1 (#608)", True),
        # Real changes stay candidates.
        ("INTPYTHON-1005 Make makemigrations order embedded model creation", False),
        (
            "INTPYTHON-950 Prevent transaction.atomic() swallowing commit exceptions",
            False,
        ),
        ("Fix columns order in aggregation queries", False),
    ],
)
def test_is_release_chore(subject, expected):
    assert is_release_chore(subject) is expected


def _git_stub(log_lines, tags="5.2.4\n", branches="upstream/5.2.x\n"):
    """Stub git for the backports command: branch list, tags, and the cherry log."""

    def side_effect(cmd, **kwargs):
        if "for-each-ref" in cmd:
            return _completed(cmd, branches)
        if "tag" in cmd:
            return _completed(cmd, tags)
        if "log" in cmd and "-1" in cmd:
            return _completed(cmd, "2026-08-24T10:00:00-04:00")
        if "log" in cmd:
            return _completed(cmd, log_lines)
        return _completed(cmd)

    return side_effect


def _invoke(side_effect, args=()):
    with (
        mock.patch("dbx_python_cli.utils.repo.get_config", return_value={}),
        mock.patch("dbx_python_cli.utils.repo.get_base_dir", return_value="/repos"),
        mock.patch(
            "dbx_python_cli.utils.repo.find_repo_by_name",
            return_value={
                "name": "backend",
                "path": "/repos/backend",
                "group": "django",
            },
        ),
        mock.patch(
            "dbx_python_cli.utils.release.subprocess.run", side_effect=side_effect
        ),
    ):
        return runner.invoke(backports.app, ["backend", *args])


_FIX = "><\x01aaaaaaa\x012026-08-25\x01INTPYTHON-1 Fix a real bug"
_CHORE = "><\x01bbbbbbb\x012026-08-25\x01BUMP 5.2.5.dev0"
_ALREADY = "=<\x01ccccccc\x012026-08-25\x01INTPYTHON-2 Already backported"


def _log(*lines):
    # git writes the left/right marker then the format string; the stub feeds the
    # command the same shape, one commit per line.
    return "\n".join(line.replace("><", ">") for line in lines) + "\n"


def test_lists_candidates_since_the_last_release_tag():
    result = _invoke(_git_stub(_log(_FIX)))
    assert result.exit_code == 0
    assert "since 5.2.4 (2026-08-24)" in result.stdout
    assert "1 candidate(s)" in result.stdout
    assert "aaaaaaa" in result.stdout


def test_hides_release_chores():
    result = _invoke(_git_stub(_log(_FIX, _CHORE)))
    assert "1 candidate(s)" in result.stdout
    assert "bbbbbbb" not in result.stdout
    assert "(1 release chore(s) hidden — pass --all)" in result.stdout


def test_all_shows_chores():
    result = _invoke(_git_stub(_log(_FIX, _CHORE)), ["--all"])
    assert "since the branch point" in result.stdout
    assert "bbbbbbb" in result.stdout


def test_skips_commits_already_on_the_target_branch():
    """A "=" marker means an equivalent patch is already there."""
    result = _invoke(_git_stub(_log(_ALREADY)))
    assert "nothing to backport" in result.stdout
    assert "ccccccc" not in result.stdout


def test_reports_clean_branch():
    result = _invoke(_git_stub(""))
    assert "✅ nothing to backport" in result.stdout


def test_skips_branch_without_a_release_tag():
    """A dead branch has no tag; falling back to the branch point would flood."""
    result = _invoke(_git_stub(_log(_FIX), tags=""))
    assert "No 5.2.* release tag — skipping" in result.stdout
    assert "aaaaaaa" not in result.stdout


def test_since_overrides_the_tag_window():
    result = _invoke(_git_stub(_log(_FIX), tags=""), ["--since", "2026-01-01"])
    assert "since 2026-01-01" in result.stdout
    assert "aaaaaaa" in result.stdout


def test_warns_about_an_unknown_target_branch():
    result = _invoke(_git_stub("", branches="upstream/5.2.x\n"), ["--to", "9.9.x"])
    assert "No upstream/9.9.x branch found" in result.stdout


def test_orders_branches_newest_first():
    branches = "upstream/5.2.x\nupstream/6.0.x\nupstream/main\n"
    result = _invoke(_git_stub("", branches=branches))
    assert result.stdout.index("🌿 6.0.x") < result.stdout.index("🌿 5.2.x")
    assert "🌿 main" not in result.stdout


def test_since_accepts_a_tag_and_resolves_it_to_a_date():
    """--since is documented as "a git ref or date".

    git log --since only understands dates and silently misreads a tag as one
    ("5.2.3" parses as a 2003 date), which left the window unbounded while the
    command still reported "since 5.2.3". Refs are resolved to a commit date.
    """
    seen = {}

    def side_effect(cmd, **kwargs):
        if "rev-parse" in cmd:
            return _completed(cmd, "deadbeef")
        if "for-each-ref" in cmd:
            return _completed(cmd, "upstream/5.2.x\n")
        if "log" in cmd and "-1" in cmd:
            return _completed(cmd, "2026-05-01T09:00:00-04:00")
        if "log" in cmd:
            seen["log_cmd"] = cmd
            return _completed(cmd, _log(_FIX))
        return _completed(cmd)

    result = _invoke(side_effect, ["--since", "5.2.3"])
    assert result.exit_code == 0
    # The tag is echoed with the date it resolved to...
    assert "since 5.2.3 (2026-05-01)" in result.stdout
    # ...and git received the date, not the tag.
    assert "--since=2026-05-01T09:00:00-04:00" in seen["log_cmd"]
    assert "--since=5.2.3" not in seen["log_cmd"]


def test_since_passes_a_plain_date_through_untouched():
    """A value that is not a ref is left for git's own approxidate parser."""
    seen = {}

    def side_effect(cmd, **kwargs):
        if "rev-parse" in cmd:
            raise subprocess.CalledProcessError(1, cmd, stderr="not a ref")
        if "for-each-ref" in cmd:
            return _completed(cmd, "upstream/5.2.x\n")
        if "log" in cmd and "-1" in cmd:
            return _completed(cmd, "2026-08-24T10:00:00-04:00")
        if "log" in cmd:
            seen["log_cmd"] = cmd
            return _completed(cmd, _log(_FIX))
        return _completed(cmd)

    result = _invoke(side_effect, ["--since", "2 weeks ago"])
    assert result.exit_code == 0
    assert "since 2 weeks ago" in result.stdout
    assert "--since=2 weeks ago" in seen["log_cmd"]
