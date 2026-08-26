Django Fork Maintenance
=======================

The ``mongodb-forks/django`` repository is a long-lived organisation fork of
``django/django``. Unlike a personal contributor fork, it carries several
MongoDB-specific branches that each track a different upstream Django release
branch, and it needs to be re-synced periodically as new Django patch releases
land. This page describes how ``dbx`` is configured to manage that fork and the
day-to-day maintenance workflow.

How the fork is configured
---------------------------

The Django fork lives in the ``django`` group and is set up entirely through
config — no ``--fork-user`` flag is needed, because the fork is owned by an
organisation rather than a personal account:

.. code-block:: toml

   [repo.groups.django]
   repos = [
       "git@github.com:mongodb-forks/django.git",
       "git@github.com:mongodb-labs/django-mongodb-backend.git",
       "git@github.com:mongodb-labs/django-mongodb-extensions.git",
       "git@github.com:mongodb-labs/django-mongodb-project.git",
   ]

   # Clone mongodb-forks/django directly even when --fork is active
   no_fork = ["django"]

   # Auto-add an `upstream` remote pointing at the canonical Django repo
   [repo.groups.django.upstream]
   django = "git@github.com:django/django.git"

   # Map each local (fork) branch to the upstream branch it tracks.
   # Branches tracking a released Django version map to its stable/<version>.x
   # branch; the in-development version tracks Django's main branch.
   [repo.groups.django.upstream_branch]
   django = {"mongodb-6.2.x" = "main", "mongodb-6.1.x" = "stable/6.1.x", "mongodb-6.0.x" = "stable/6.0.x", "mongodb-5.2.x" = "stable/5.2.x"}

   # Branch checked out automatically right after cloning
   [repo.groups.django.preferred_branch]
   django = "mongodb-6.0.x"

   # Add a `django-upstream` worktree on clone so the fork and upstream Django
   # can both be worked on from one clone
   upstream_worktree = ["django"]

Each key plays a specific role in fork maintenance:

``no_fork``
   Lists repos that should be cloned verbatim even when ``--fork`` is active.
   Because ``mongodb-forks/django`` is *already* a fork, it must not have the
   personal ``fork_user`` substituted into its URL.

``upstream``
   Maps the repo to the URL of the canonical upstream (``django/django``). On
   clone, ``dbx`` adds this as an ``upstream`` remote automatically, so no
   ``--fork-user`` flag is required. See :ref:`config-driven-upstream`.

``upstream_branch``
   Maps each local fork branch to the upstream branch it rebases against. The
   MongoDB branch names (``mongodb-6.0.x``) differ from the upstream Django
   branch names (``stable/6.0.x``), so this mapping tells ``dbx sync`` which
   target to rebase onto based on the branch currently checked out. The dict
   form is what makes multi-branch maintenance work — each branch resolves to
   its own upstream target.

``preferred_branch``
   The branch ``dbx clone`` switches to automatically after cloning.

``upstream_worktree``
   Lists repos that get a sibling git worktree checked out on the upstream
   default branch immediately after cloning. See
   :ref:`django-fork-upstream-worktree`.

Cloning the fork
----------------

Clone the whole group (upstream remote and preferred branch are configured
automatically):

.. code-block:: bash

   dbx clone -g django

   # Verify the remotes were set up
   cd ~/Developer/mongodb/django/django
   git remote -v
   # origin    git@github.com:mongodb-forks/django.git (fetch)
   # upstream  git@github.com:django/django.git (fetch)

To clone only the Django fork itself:

.. code-block:: bash

   dbx clone django

.. _django-fork-upstream-worktree:

Developing against the fork and upstream from one clone
-------------------------------------------------------

Fork maintenance regularly needs both sides at once: reading upstream Django to
see what changed, and editing the fork branch to adapt to it. A second clone
would mean a second full fetch of Django's history and two object stores to keep
current.

A git *worktree* avoids that. One clone can have several branches checked out at
the same time, each in its own directory, all sharing a single ``.git`` object
store. Because ``upstream_worktree = ["django"]`` is set, ``dbx clone`` creates
one automatically:

.. code-block:: text

   ~/Developer/mongodb/django/
     django/            # primary clone, on mongodb-6.0.x (origin = mongodb-forks)
     django-upstream/   # worktree, on upstream-main (tracks upstream/main)

The worktree's branch is named ``upstream-<default branch>`` rather than just
``main``, so it cannot collide with a branch of the same name already tracking
``origin`` in the fork.

Fetching in either directory updates the shared object store, so comparisons
between the two are local and immediate:

.. code-block:: bash

   cd ~/Developer/mongodb/django/django
   git log upstream-main..mongodb-6.0.x        # what the fork adds
   git diff upstream-main -- django/db/models  # what the fork changed

Managing worktrees manually
~~~~~~~~~~~~~~~~~~~~~~~~~~~

``dbx worktree`` manages worktrees for any repo, whether or not
``upstream_worktree`` is configured:

.. code-block:: bash

   # Add the upstream worktree (django-upstream, on the upstream default branch)
   dbx worktree add django --upstream

   # Check out a specific upstream branch (django-stable-6.1.x)
   dbx worktree add django stable/6.1.x --upstream

   # Check out an existing fork branch alongside the current one
   dbx worktree add django mongodb-6.2.x

   # Override the directory suffix
   dbx worktree add django stable/6.1.x --upstream --label 61

   # Show every checkout attached to the clone (* marks the primary one)
   dbx worktree list django

   # Remove by directory suffix (defaults to `upstream`)
   dbx worktree remove django
   dbx worktree remove django 61 --force

Removal goes through ``git worktree remove`` so the registration inside the
primary clone is cleaned up too; deleting the directory by hand would leave a
stale entry that blocks recreating the worktree later. ``dbx remove`` handles
this as well, removing worktrees before the clone they belong to.

A branch can only be checked out in one worktree at a time. ``dbx worktree add``
reports git's refusal rather than working around it, so the fork branch you are
editing is never silently moved out from under you.

.. note::

   ``django-upstream`` is skipped by ``dbx sync``, ``dbx switch -g django`` and
   ``dbx install -g django`` — see :ref:`upstream-worktrees` for why. It still
   appears in ``dbx status``, ``dbx log`` and ``dbx branch``, which only read.

   In particular, the fork clone stays the installed one: a Django worktree has
   the same package name, so installing it would replace the fork checkout as
   the live ``django`` package in the group venv.

Syncing a branch with upstream
------------------------------

``dbx sync`` fetches from ``upstream``, rebases the current branch onto its
mapped upstream branch, and pushes the result back to ``origin``. Because the
upstream target is resolved from ``upstream_branch`` based on the branch that
is checked out, maintenance is simply "check out a branch, sync it":

.. code-block:: bash

   cd ~/Developer/mongodb/django/django

   # Bring mongodb-6.0.x up to date with the latest Django stable/6.0.x
   git switch mongodb-6.0.x
   dbx sync django
   # Fetches upstream, rebases mongodb-6.0.x onto upstream/stable/6.0.x, pushes to origin

   # Repeat for the next release branch
   git switch mongodb-5.2.x
   dbx sync django
   # Rebases mongodb-5.2.x onto upstream/stable/5.2.x, pushes to origin

Always preview first with ``--dry-run`` — it shows the commits that would be
applied from upstream and the commits that would be rebased on top:

.. code-block:: bash

   dbx sync django --dry-run

If a branch has already been pushed and rebased, the follow-up push may be
rejected; re-run with ``--force`` (which uses ``--force-with-lease`` for
safety):

.. code-block:: bash

   dbx sync django --force

Refreshing every release branch
-------------------------------

When a new round of Django patch releases lands upstream, every MongoDB branch
needs to be rebased. The ``--all-branches`` (``-b``) flag walks the repo's
``upstream_branch`` mapping for you — it checks out each mapped branch in turn,
rebases it onto its configured upstream target, force-pushes, and restores the
branch you started on. Because rebasing rewrites history, ``--all-branches``
force-pushes by default (using the safe ``--force-with-lease``); you do not need
to pass ``--force``:

.. code-block:: bash

   # Preview what would change on every mapped branch
   dbx sync django --all-branches --dry-run

   # Rebase and push every mapped branch
   dbx sync django --all-branches
   dbx sync django -b              # short form

This is equivalent to switching to ``mongodb-6.1.x``, ``mongodb-6.0.x``,
``mongodb-5.2.x``, … in turn and running ``dbx sync django`` on each. The
working tree must be clean for a real sync (each branch is checked out via
``git switch``), and only branches present in the ``upstream_branch`` mapping
are synced.

To sync only a subset of the mapped branches instead of all of them, use
``--branch`` (``-B``). It behaves exactly like ``--all-branches`` — same
rebase/force-push/restore flow, same ``--dry-run`` and ``--no-ci`` support —
but restricts the run to the named branch(es). The flag is repeatable, and each
name must exist in the ``upstream_branch`` mapping:

.. code-block:: bash

   # Sync just one release branch
   dbx sync django -B mongodb-6.0.x

   # Sync a few, in the given order
   dbx sync django -B mongodb-6.0.x -B mongodb-6.1.x

   # Preview a single branch without touching the tree
   dbx sync django -B mongodb-6.0.x --dry-run

Combined with ``--dry-run``, ``--all-branches`` previews every mapped branch
*without* checking any of them out: it fetches upstream once and compares each
branch's ``origin`` ref against its configured upstream target directly. Because
nothing is checked out, the preview works even when the working tree is dirty
and never disturbs the branch you have open.

If a branch fails to rebase (for example, conflicts, or an upstream target that
no longer exists), that branch's rebase is **aborted** so the working tree stays
clean and the remaining branches are still processed — one bad branch does not
leave a rebase in progress that blocks the rest. At the end, the failed branches
are listed so you can rebase them manually:

.. code-block:: text

   ⚠️  Rebase these branch(es) manually: mongodb-6.0.x

   # then, for each listed branch:
   cd ~/Developer/mongodb/django/django
   git switch mongodb-6.0.x
   git rebase upstream/stable/6.0.x   # resolve conflicts, then git rebase --continue

Once resolved, re-run ``dbx sync django --all-branches`` (already-synced
branches are fast no-ops) to push the remaining branches.

Re-running downstream CI
~~~~~~~~~~~~~~~~~~~~~~~~~~

Because the backend's PR workflows check out the fork branch at a pinned
``ref:`` at CI runtime (see `How the fork branches are tested in backend PRs`_),
force-pushing a rebased fork branch does **not** re-trigger those workflows — so
a rebase that breaks the adapted tests would go unnoticed until the next push to
the PR. To close that gap, after a successful ``--all-branches`` sync ``dbx sync``
re-runs the backend CI for each branch that rebased, via the ``ci_rerun`` mapping.

The mapping is keyed per fork branch (only branches that actually rebased are
processed — a branch that failed or was skipped triggers nothing). Each value
maps an ``owner/name`` GitHub repo to a target that is **either**:

- an **integer PR number** — re-runs the workflow runs attached to that PR
  (needs an open PR with a prior run; updates the PR's own status checks), or
- a **string git ref** — dispatches the repo's ``test-python*`` workflows on that
  backend branch via ``workflow_dispatch`` (no PR needed). Each backend branch
  pins the fork branch it tests via ``ref:``, so the backend ref selects which
  fork branch is exercised — e.g. the backend's ``main`` pins ``mongodb-6.0.x``.
  See `Which backend branch pins which fork branch`_ for the full mapping.
  Only ``test-python*`` workflows that actually declare a ``workflow_dispatch``
  trigger are dispatched; any that don't (push/schedule/pull_request only) are
  reported as ``skipped (no workflow_dispatch trigger)`` instead of failing.
  Stale registry entries — workflows whose file has been renamed or deleted and
  no longer exists at the ref — are likewise reported as
  ``skipped (not present on <ref>)`` rather than attempted, or
- an **object** ``{pr = <n>, evergreen = true}`` — re-runs PR ``<n>``'s workflow
  runs (exactly as the integer form) **and** re-triggers that PR's Evergreen
  patch by commenting ``evergreen retry`` on it. This is needed because
  Evergreen's PR patch, like the GitHub Actions workflows, checks out the fork
  branch at a pinned ref, so a rebased fork branch does not re-run Evergreen on
  its own. Set ``evergreen = false`` (or use the bare integer) to re-run only
  GitHub Actions.

.. code-block:: toml

   [repo.groups.django.ci_rerun.django]
   "mongodb-6.0.x" = {"mongodb/django-mongodb-backend" = "main"}   # dispatch, no PR
   "mongodb-6.1.x" = {"mongodb/django-mongodb-backend" = 1111}     # re-run PR #1111 (Actions only)
   "mongodb-5.2.x" = {"mongodb/django-mongodb-backend" = 2222}
   # Re-run Actions AND re-trigger Evergreen on PR #3333:
   "mongodb-6.2.x" = {"mongodb/django-mongodb-backend" = {pr = 3333, evergreen = true}}

The PR numbers above are placeholders — substitute the real ones in your own
config. They have to stay integers: an integer is read as a PR number and a
quoted string as a git ref, so ``"1111"`` would mean something entirely
different. See ``[repo.groups.django.ci_rerun.django]`` in the bundled
``config.toml`` for the current live mapping.

.. code-block:: text

   ✨ Done! Synced 3 branch(es)

   ♻️  mongodb-6.0.x → dispatching CI on mongodb/django-mongodb-backend@main...
      test-python.yml ✓ queued
      test-python-geo.yml ✓ queued
      test-python-replica.yml — skipped (no workflow_dispatch trigger)
      test-python1.yml — skipped (not present on main)
   ♻️  mongodb-6.1.x → re-running CI on mongodb/django-mongodb-backend#1111...
      #1111 ✓ queued (4 workflow run(s))
   ♻️  mongodb-6.2.x → re-running CI on mongodb/django-mongodb-backend#3333...
      #3333 ✓ queued (4 workflow run(s))
   ♻️  mongodb-6.2.x → retrying Evergreen on mongodb/django-mongodb-backend#3333...
      #3333 ✓ commented 'evergreen retry'

This uses the ``gh`` CLI (GitHub CLI), so ``gh`` must be installed and
authenticated. It is best-effort: a missing ``gh``, an unconfigured ``ci_rerun``
mapping, or a GitHub API error is reported as a warning and never fails the
sync. The Evergreen retry uses the same ``gh`` CLI (it posts an ``evergreen
retry`` PR comment, which Evergreen watches for), so no Evergreen token or CLI
is required. Pass ``--no-ci`` to skip all of the above (Actions re-runs and
Evergreen retries alike), and note it is skipped automatically for ``--dry-run``
and when no branch actually synced.

.. note::

   The two mechanisms report results in different places. A **PR re-run** updates
   the PR's own status checks, so the result shows up on the PR. A
   **``workflow_dispatch`` run** is standalone — it appears under the repo's
   **Actions** tab, not as a status check on any PR — so after a dispatch you
   check the run there rather than on a PR.

Choosing between the two: use a **PR number** for branches that have an open PR
you want to keep green/red (the run attaches to that PR); use a **ref** to
validate a rebase with no PR involved, or when no suitable PR run exists yet
(for example the backend's ``main``, which pins ``mongodb-6.0.x``).

.. warning::

   **A re-run only revalidates the PR as it currently stands.** ``ci_rerun``
   re-runs the existing workflow runs on the target PR; it does not update that
   PR first. If the PR's head branch has fallen behind its base, the re-run
   faithfully reproduces the stale result — including failures that were already
   fixed on the base branch. A red check after a re-run is therefore not
   necessarily caused by the fork rebase.

   Before trusting a re-run, confirm the target PR is current::

      gh api repos/mongodb/django-mongodb-backend/compare/<base>...<owner>:<repo>:<head> \
        -q '"ahead=\(.ahead_by) behind=\(.behind_by) \(.status)"'

   A non-zero ``behind`` means the PR needs rebasing on its base before its
   checks mean anything. Note that ``mergeable: MERGEABLE`` does **not** imply
   the branch is current — it only means there are no merge conflicts, so a
   badly stale PR still reports as mergeable.

   This bites documentation checks in particular: the backend builds its docs
   with ``sphinx -W`` (warnings as errors), so a docs fix that has landed on the
   base branch will keep failing on every stale PR until each one is rebased.

Spotting upstream fixes released after the backend
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Rebasing a fork branch aligns it with upstream's *current* tip, which says
nothing about whether the **released** backend contains those commits. A
security fix backported to Django's ``stable/5.2.x`` the day after
django-mongodb-backend 5.2.4 shipped is on the fork branch, in CI, and absent
from every installed copy of the backend — and nothing in the sync output would
have said so.

So after a successful ``--all-branches`` (or ``--branch``) sync, ``dbx sync``
compares each mapped branch's upstream target against the highest release tag of
the same series in the group's ``release_repo`` and lists what upstream has that
the release does not:

.. code-block:: text

   📋 Upstream commits since the latest django-mongodb-backend release:

   🌿 mongodb-6.0.x → upstream/stable/6.0.x
      django-mongodb-backend 6.0.4 (2026-07-14) … upstream tip
      25 new commit(s): 4 security, 10 fixes, 5 unclassified, 6 chores
      🔴 security
        [6.2 cycle] 13debb622a 2026-08-04 [6.0.x] Fixed CVE-2026-15920 -- Made display_for_field() validate URLs before rendering admin links.
        ...
      🔧 fixes
        [6.2 cycle] 6dbc7498b1 2026-07-31 [6.0.x] Fixed #37235 -- Added compatibility for sqlparse 0.5.5.
        ...
      ❓ unclassified
        [6.2 cycle] 994db70ddb 2026-07-14 [6.0.x] Closed temporary files in GDALRasterTests.
      (6 more hidden — pass --all)

   🌿 mongodb-5.2.x → upstream/stable/5.2.x
      django-mongodb-backend 5.2.4 (2026-08-24) … upstream tip
      ✅ nothing new upstream

Finding the release candidates
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The commits are bucketed by subject so the release-decision material is not
buried in version bumps and translation updates:

``🔴 security``
   Subjects matching ``Fixed CVE-YYYY-NNNNN``. These are the commits that make
   a patch release urgent.

``🔧 fixes``
   Subjects matching ``Fixed #NNNNN``. Together with the security bucket this is
   the release-notes candidate set for the next patch release of that series.

``❓ unclassified``
   Everything that matches no known convention. Shown by default and on purpose
   — see the caveat below.

``🧹 chores``
   Version bumps, stub release notes, release dates, translation updates,
   ``Refs #NNNNN`` follow-ups to a fix that is already listed on its own, and
   ``Added CVE-… to security archive`` (which names CVEs but only edits a docs
   page). Hidden by default and reported as a count.

Two flags tune the listing:

``--all``
   List every commit, including the chores. Overrides ``--security-only``.

``--security-only``
   List only the CVE fixes — the "do I need to cut a release right now?" check.
   Note this is a filter, not a judgement: a plain ``Fixed #NNNNN`` can be
   release-worthy too, which is why the default sorts security first rather than
   hiding everything else.

Combined with ``--dry-run`` these make the report a read-only query::

   dbx sync django --all-branches --dry-run                  # what is pending?
   dbx sync django --all-branches --dry-run --security-only  # anything urgent?
   dbx sync django --all-branches --dry-run --all            # the full list

To judge a commit, take the short sha into the fork clone as usual
(``git -C <fork> show <sha>``); the report prints sha, date and subject
precisely so it hands off to normal git.

.. warning::

   The bucketing is a heuristic keyed to Django's *current* commit-subject
   conventions, and it is deliberately conservative: anything unrecognised lands
   in ``unclassified`` and stays visible rather than being quietly filed as a
   chore. Expect real commits there — "Fixed minor typos in docs and
   docstrings" and "Closed temporary files in GDALRasterTests" both land in
   ``unclassified`` today, because narrowing the chore patterns enough to catch
   them would risk hiding genuine fixes.

   The summary line always counts ``len(commits)`` independently of the buckets,
   so if upstream changes its conventions the total still moves and a spike in
   ``unclassified`` is the signal that the patterns need revisiting.

   Bucketing changes only *presentation*. It does not make the report more
   correct: "new" is still computed by committer date against the release tag,
   so if a listed commit looks like it should already be released, confirm with
   ``git -C <release-repo> tag --contains <sha>`` before acting on it.

The release series comes from the branch name (``mongodb-5.2.x`` → the highest
``5.2.<patch>`` tag), so no extra per-branch configuration is needed; a branch
tracking an unreleased version (``mongodb-6.2.x`` → ``main``) reports that no
tag exists yet. The comparison uses committer dates, so a commit is "new" when
it landed on the stable branch after the release tag was cut.

Each commit is labelled with the upstream **dev cycle** it was backported from.
Django annotates every backport with ``Backport of <sha> from main.``, so the
source commit's position on ``main`` — relative to the fork points of the
``upstream/stable/X.Y.x`` branches — identifies the cycle it was written in.
A ``[6.2 cycle]`` label on a ``stable/5.2.x`` commit is normal and simply means
the fix was authored during 6.2 development and backported to 5.2; commits with
no annotation (version bumps, per-branch release chores) are labelled
``[unannotated]``.

Configure the release repo per synced repo:

.. code-block:: toml

   [repo.groups.django.release_repo]
   django = "django-mongodb-backend"

The report is best-effort and never fails the sync: an unset ``release_repo``,
an un-cloned release repo, or a git error is reported as a warning and skipped.
It fetches tags in the release repo first so a stale clone does not over-report.
Pass ``--no-backport-report`` to skip it entirely, and note it also runs under
``--dry-run`` (where it is the only thing that touches the network beyond the
single upstream fetch).

Adding a new release branch
----------------------------

A fork branch that tracks an unreleased Django version maps to Django's
``main`` branch. For example ``mongodb-6.2.x`` currently tracks ``main``
because Django 6.2 has not been released:

.. code-block:: toml

   [repo.groups.django.upstream_branch]
   django = {"mongodb-6.2.x" = "main", "mongodb-6.1.x" = "stable/6.1.x", ...}

Once Django cuts the matching stable branch (for example ``stable/6.2.x``),
update the mapping to point at it:

.. code-block:: toml

   [repo.groups.django.upstream_branch]
   django = {"mongodb-6.2.x" = "stable/6.2.x", "mongodb-6.1.x" = "stable/6.1.x", ...}

Until a mapping exists, ``dbx sync`` cannot determine the correct upstream
target for that branch and falls back to upstream's default-branch detection,
which is almost certainly not what you want for a release branch.

Only map branches whose upstream target actually exists. A branch pointing at a
``stable/<version>.x`` that has not been branched yet (a Django version still in
development on ``main``) or one that has been deleted upstream (an end-of-life
release) will fail to rebase under ``dbx sync``. When a Django release reaches
end of life and its ``stable`` branch is removed, drop the corresponding entry
from the mapping.

Running the Django test suite
-----------------------------

The Django fork uses its own test runner rather than pytest. This is wired up
through ``test_runner`` / ``test_runner_args`` in the group config:

.. code-block:: toml

   [repo.groups.django.test_runner]
   django = "tests/runtests.py"

   [repo.groups.django.test_runner_args]
   django = ["-v", "2"]

so ``dbx test django`` invokes ``tests/runtests.py`` with the configured
arguments. See :doc:`testing` for details on how custom test runners are
resolved and how to pass additional arguments.

How the fork branches are tested in backend PRs
-----------------------------------------------

Keeping the fork branches rebased matters because they are the code under test
in every ``django-mongodb-backend`` pull request. The backend's PR CI does not
test against upstream Django — it checks out the corresponding branch of the
``mongodb-forks/django`` fork and runs Django's own test suite against MongoDB,
using ``django-mongodb-backend`` as the database engine. See the open PRs at
https://github.com/mongodb/django-mongodb-backend/pulls.

Each PR triggers several GitHub Actions test workflows
(``.github/workflows/test-python*.yml`` in the backend repo), covering the core
suite plus the geo, Atlas, and encryption feature sets. Those workflows also
declare ``workflow_dispatch``, so they can be run manually (with no PR) on any
backend branch — this is what the ``ci_rerun`` "ref" form uses (see `Re-running
downstream CI`_). They all follow the same shape:

1. Check out ``django-mongodb-backend`` and install it (``pip install -e .``).
2. Check out ``mongodb-forks/django`` at the fork branch for the Django release
   under test (e.g. ``ref: mongodb-6.0.x``) into a ``django_repo/`` directory,
   then install it and Django's test requirements.
3. Copy the backend's settings files (``mongodb_settings.py``, the encryption
   settings, etc.) and its ``runtests.py`` into ``django_repo/tests/``.
4. Start MongoDB and run Django's suite via
   ``python3 django_repo/tests/runtests_.py``.

In other words, the fork branch supplies the (lightly adapted) Django test
suite, and the backend supplies the database engine and settings. The
``ref:`` in those workflows pins the exact fork branch, so:

- A rebased fork branch is what the backend PRs actually exercise — if a rebase
  breaks the adapted tests, it surfaces as failures on backend PRs, not on the
  fork itself.
- When the backend adds support for a new Django feature release, the fork
  needs a matching ``mongodb-<version>.x`` branch (see
  `Adding a new release branch`_) and the workflows' ``ref:`` is bumped to it.
- Because each backend branch's workflow pins its own fork ``ref:``, dispatching
  a workflow on a given backend ref exercises the fork branch that ref pins — the
  basis for the ``ci_rerun`` "ref" form (e.g. the backend's ``main`` pins
  ``mongodb-6.1.x``, and its ``6.0.x`` branch pins ``mongodb-6.0.x``).

Which backend branch pins which fork branch
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The pinned pairs, and which ``test-python*`` workflows exist on each backend
branch (older release branches predate the geo, Atlas, and encryption
workflows):

.. list-table::
   :header-rows: 1
   :widths: 20 22 58

   * - Backend branch
     - Pinned fork ``ref:``
     - ``test-python*`` workflows present
   * - ``main``
     - ``mongodb-6.1.x``
     - ``test-python``, ``-geo``, ``-atlas``, ``-encryption``
   * - ``6.0.x``
     - ``mongodb-6.0.x``
     - ``test-python``, ``-geo``, ``-atlas``, ``-encryption``
   * - ``5.2.x``
     - ``mongodb-5.2.x``
     - ``test-python``, ``-geo``, ``-atlas``
   * - ``5.1.x``
     - ``mongodb-5.1.x``
     - ``test-python``
   * - ``5.0.x``
     - ``mongodb-5.0.x``
     - ``test-python``

This table is a snapshot — the ``ref:`` values are bumped as the backend moves
to newer Django releases, so confirm against the workflow files before relying
on it. To check a single branch:

.. code-block:: bash

   git show upstream/main:.github/workflows/test-python.yml | grep -A2 "mongodb-forks/django"

Two consequences for validating a rebase:

- **Only the pinned pairs are reachable.** The workflows take no
  ``workflow_dispatch`` inputs — the fork ``ref:`` is hardcoded — so there is no
  way to dispatch, say, the backend's ``main`` against ``mongodb-5.2.x``. To
  exercise a fork branch through backend CI you dispatch on the backend branch
  that pins it, which means one dispatch per branch and no arbitrary
  (backend, fork branch) combinations. Testing an unpinned pair requires either
  editing the ``ref:`` on a scratch backend branch or reproducing the run
  locally (below).
- **Fork branches with no live upstream target are never re-triggered.**
  ``mongodb-5.0.x`` and ``mongodb-5.1.x`` exist on the fork but are deliberately
  absent from the ``upstream_branch`` mapping, because Django's
  ``stable/5.0.x`` / ``stable/5.1.x`` are gone (end of life). ``--all-branches``
  therefore never rebases them and their ``ci_rerun`` entries would never fire —
  correctly, since those branches are frozen. Only the mapped branches need
  ``ci_rerun`` coverage.

To reproduce a backend PR run locally against a fork branch you have rebased,
mirror those steps: check out the fork branch in your ``django`` group clone,
install it alongside ``django-mongodb-backend``, copy the backend's settings /
``runtests.py`` into ``tests/``, and run the suite against a local MongoDB (see
:doc:`mongodb-runner`).

Related configuration
----------------------

The backend repositories in the ``django`` group have their own maintenance
touches — for example, ``django-mongodb-backend`` is listed in
``sync_after_clone`` so it is synced with upstream immediately after cloning.
See :ref:`sync-after-clone` and :ref:`config-driven-upstream` in
:doc:`repo-management` for the full reference on these keys.
