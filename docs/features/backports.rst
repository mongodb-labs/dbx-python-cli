===========================
Finding backport candidates
===========================

``dbx backports`` lists commits on a development branch that have not reached a
release branch — the raw material for the next "Backports for X.Y.Z" pull
request::

   dbx backports django-mongodb-backend

.. code-block:: text

   📋 Backport candidates from upstream/main:

   🌿 6.0.x
      since 6.0.4 (2026-07-14)
      ✅ nothing to backport (7 release chore(s) skipped)
   🌿 5.2.x
      since 5.2.4 (2026-08-24)
      ✅ nothing to backport (1 release chore(s) skipped)
   🌿 5.1.x
      ⚠️  No 5.1.* release tag — skipping (pass --since or --all to list anyway)

This is a different question from the one :doc:`the sync release-gap report
<django-fork>` answers. That report compares the *Django fork* against a
released *backend* tag, to tell you whether the released backend is missing
upstream fixes. This command compares a repo's own ``main`` against its own
release branches, to tell you what still needs cherry-picking.

Why the window matters
======================

Candidates are bounded by the target branch's **latest release tag**, not by the
branch point. On ``django-mongodb-backend`` the difference is stark: since the
5.2.x branch point there are 164 commits missing from ``5.2.x`` (82 after
filtering release chores), nearly all of them feature work that policy forbids
on an LTS branch. Since the ``5.2.4`` tag there is one.

The older commits are not candidates because they were already triaged when the
previous backport PR was assembled — each was either taken or deliberately
skipped. Re-listing them buries the handful of commits that are actually new.

.. warning::

   The window is also load-bearing for correctness, not just brevity. Backports
   are typically squashed into a single commit (for example
   ``INTPYTHON-528 Backports for 5.2.4 LTS (#607)``), so the individual ``main``
   commits they carried have no matching patch-id. ``git log --cherry-mark``
   detects only 6 of the 164 as already-present. Bounding by the release tag
   sidesteps that: everything the squashed PR carried predates the tag.

   The cost is that a fix which *should* have been backported before the last
   release and was missed will not appear. Use ``--since`` or ``--all`` when
   hunting for one.

Options
=======

``--to <branch>``
   Restrict to one release branch. Repeatable. Defaults to every ``X.Y.x``
   branch on the remote, newest first.

``--from <branch>``
   Branch the candidates are taken from. Defaults to ``main``.

``--since <ref-or-date>``
   Widen the window past the last release tag.

``--all``
   Go back to the branch point and include release chores.

``--remote <name>``
   Remote to read branches from. Defaults to ``upstream``.

``--no-fetch``
   Skip the fetch. The command fetches first by default because a stale clone
   under-reports, which is the dangerous direction — a fix that landed today
   would simply not appear.

Branches with no release tag are skipped rather than falling back to the branch
point, which on a long-dead branch means hundreds of lines that were never
candidates.

What gets filtered
==================

Release chores are hidden and reported as a count: version bumps (including
ticket-prefixed ones like ``INTPYTHON-1050 Bump version to 6.1.0``), dependabot
and actions bumps, SBOM updates, stub release notes, release dates, release
prep, ``CODEOWNERS`` edits, and ``Update to Django X.Y`` — moving ``main`` onto
the next feature release is precisely what a release branch exists to be spared.

Everything else is shown. The command deliberately does **not** try to decide
whether a change is eligible for a given branch: per
``docs/internals/release-process.rst`` in the backend, only security fixes and
data-loss bugs belong on LTS branches, and nothing in a commit subject reliably
marks those. The documented signal is the pull request description, but that
convention is followed by roughly 4 of the last 60 merged PRs and there is no
backport label, so keying off it would report an empty list and look
authoritative. Read the candidates against the policy yourself.
