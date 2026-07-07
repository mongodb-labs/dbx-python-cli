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

   # Map each local (fork) branch to the upstream branch it tracks
   [repo.groups.django.upstream_branch]
   django = {"mongodb-6.2.x" = "stable/6.2.x", "mongodb-6.1.x" = "stable/6.1.x", "mongodb-6.0.x" = "stable/6.0.x", "mongodb-5.2.x" = "stable/5.2.x", "mongodb-5.1.x" = "stable/5.1.x"}

   # Branch checked out automatically right after cloning
   [repo.groups.django.preferred_branch]
   django = "mongodb-6.0.x"

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
rebases it onto its configured upstream target, pushes, and restores the branch
you started on:

.. code-block:: bash

   # Preview what would change on every mapped branch
   dbx sync django --all-branches --dry-run

   # Rebase and push every mapped branch
   dbx sync django --all-branches
   dbx sync django -b              # short form

This is equivalent to switching to ``mongodb-6.2.x``, ``mongodb-6.1.x``,
``mongodb-6.0.x``, … in turn and running ``dbx sync django`` on each. The
working tree must be clean (each branch is checked out via ``git switch``), and
only branches present in the ``upstream_branch`` mapping are synced.

Resolve any rebase conflicts manually as they arise, then re-run
``dbx sync django --all-branches`` (already-synced branches are fast no-ops) to
finish pushing the remaining branches.

Adding a new release branch
----------------------------

When Django cuts a new stable branch (for example ``stable/6.3.x``) and you
create a matching ``mongodb-6.3.x`` fork branch, add the mapping to
``upstream_branch`` so ``dbx sync`` knows where to rebase it:

.. code-block:: toml

   [repo.groups.django.upstream_branch]
   django = {"mongodb-6.3.x" = "stable/6.3.x", "mongodb-6.2.x" = "stable/6.2.x", ...}

Until the mapping exists, ``dbx sync`` cannot determine the correct upstream
target for that branch and falls back to upstream's default-branch detection,
which is almost certainly not what you want for a release branch.

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
suite plus the geo, Atlas, and encryption feature sets. They all follow the
same shape:

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
