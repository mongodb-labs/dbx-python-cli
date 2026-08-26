"""Helpers shared by the release-oriented commands (``dbx sync``, ``dbx backports``).

Both need to locate the newest release tag of a series and to tell a substantive
commit apart from branch mechanics, so those two pieces live here rather than
being imported across command modules.
"""

import re
import subprocess

# Django's stable branches follow a tight commit-subject convention, which is
# enough to sort the release-gap report into "act on this" and "branch
# mechanics". Ordered most- to least-urgent; the report prints them in this
# order and hides ``chore`` unless asked.
BUCKETS = (
    ("security", "🔴 security"),
    ("fix", "🔧 fixes"),
    ("other", "❓ unclassified"),
    ("chore", "🧹 chores"),
)

_SECURITY_RE = re.compile(r"^Fixed CVE-\d{4}-\d+", re.IGNORECASE)
_FIX_RE = re.compile(r"^Fixed #\d+")
_CHORE_RES = (
    # "Added CVE-x, CVE-y to security archive." names CVEs but is a docs commit,
    # so it has to be matched before anything keying off "CVE".
    re.compile(r"^Added CVE-.*security archive", re.IGNORECASE),
    re.compile(r"^Post-release version bump"),
    re.compile(r"^Bumped (version|minimum)"),
    re.compile(r"^Added (stub )?release note"),
    re.compile(r"^Added release date"),
    re.compile(r"^Updated translations"),
    re.compile(r"^Updated ticket"),
    re.compile(r"^Fixed typo"),
    # A "Refs #NNNN" follow-up amends a fix that is already listed on its own.
    re.compile(r"^Refs #\d+"),
)

# django-mongodb-backend's own release mechanics and dependency churn. These are
# cut on each branch independently and are never backport candidates.
_BACKEND_CHORE_RES = (
    re.compile(r"^BUMP "),
    re.compile(r"^Bump version", re.IGNORECASE),
    re.compile(r"^Bump the actions group", re.IGNORECASE),
    re.compile(r"^Bump [\w/.-]+ from ", re.IGNORECASE),
    re.compile(r"^Bump to ", re.IGNORECASE),
    re.compile(r"\bSBOM\b"),
    re.compile(r"^Add(ed)? stub release notes", re.IGNORECASE),
    re.compile(r"release date", re.IGNORECASE),
    re.compile(r"^Prep [\d.]+ release", re.IGNORECASE),
    re.compile(r"CODEOWNERS"),
    # Moving main onto the next Django feature release is the opposite of a
    # backport: it is exactly what the release branch exists to be spared.
    re.compile(r"^Update to Django \d", re.IGNORECASE),
)

# Backend subjects usually lead with a Jira ticket, e.g. "INTPYTHON-1050 " or
# "PYTHON-5579: ", which would otherwise defeat the anchored chore patterns.
_TICKET_PREFIX_RE = re.compile(r"^(INTPYTHON|PYTHON)-\d+:?\s+", re.IGNORECASE)


def classify_commit(subject):
    """Bucket an upstream commit subject as security/fix/chore/other.

    Heuristic, and deliberately conservative: anything that does not match a
    known convention lands in ``other`` and stays visible, so a change in
    upstream's commit style shows up as unclassified commits rather than
    silently vanishing from the report.
    """
    # Stable-branch commits are prefixed with the series, e.g. "[6.0.x] ".
    subject = re.sub(r"^\[[0-9]+\.[0-9]+\.x\]\s*", "", subject).strip()
    for pattern in _CHORE_RES:
        if pattern.search(subject):
            return "chore"
    if _SECURITY_RE.search(subject):
        return "security"
    if _FIX_RE.search(subject):
        return "fix"
    return "other"


def is_release_chore(subject):
    """True when a backend commit is release mechanics rather than a change.

    Version bumps, stub release notes, SBOM updates and dependency bumps are cut
    on each branch independently, so they are never worth backporting.
    """
    subject = _TICKET_PREFIX_RE.sub("", subject).strip()
    return any(pattern.search(subject) for pattern in _BACKEND_CHORE_RES)


def latest_release_tag(release_path, series):
    """Return ``(tag, iso_date)`` for the highest ``<series>.<patch>`` tag, or None."""
    try:
        tags = git_out(release_path, ["tag", "-l", f"{series}.*"])
    except subprocess.CalledProcessError:
        return None

    pattern = re.compile(rf"^{re.escape(series)}\.(\d+)$")
    matched = [(int(m.group(1)), t) for t in tags.split() if (m := pattern.match(t))]
    if not matched:
        return None

    tag = max(matched)[1]
    try:
        date = git_out(release_path, ["log", "-1", "--format=%cI", tag])
    except subprocess.CalledProcessError:
        return None
    return tag, date


def git_out(path, args, check=True):
    """Run git in ``path`` and return its stdout, stripped."""
    return subprocess.run(
        ["git", "-C", str(path), *args],
        check=check,
        capture_output=True,
        text=True,
    ).stdout.strip()
