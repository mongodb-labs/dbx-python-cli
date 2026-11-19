CI Status
=========

``dpy ci`` checks Evergreen and GitHub Actions for one branch and prints a
single summary. It answers one question: *is CI green for this branch*.

.. code-block:: bash

   dpy ci
   dpy ci mongo-python-driver
   dpy ci --branch mongodb-6.0.x
   dpy ci --json

The command defaults to the repository that contains the current directory and
to the checked-out branch. Use ``--branch`` when HEAD is detached.

What it checks
--------------

**GitHub Actions.** The command reads the ``upstream`` remote, or ``origin``
when there is no ``upstream``. It finds the PR for the branch and shows each
status check. When there is no PR, it shows the recent workflow runs for the
branch. A fork checkout therefore reports checks on the canonical repository,
not on the personal fork.

**Evergreen.** The command reads ``project_name`` from
``[evergreen.<repo>]`` in ``config.toml``. It lists your recent patches and
keeps the ones whose project and git branch match. Each patch prints its
status and a Spruce link. The newest patch decides the Evergreen ``Overall``
state, so an old failed patch does not keep a retried branch red.

.. code-block:: toml

   [evergreen.mongo-python-driver]
   project_name = "mongo-python-driver"

Multi-system output
-------------------

The two systems stay separate in the output. Each system prints its own
``Overall`` line, then the command prints a combined ``Overall`` line:

.. code-block:: text

   CI status: mongo-python-driver (branch: feature-branch)
   ╭──────── GitHub Actions: mongodb/mongo-python-driver (upstream) ────────╮
   │ PR #3237 · open · PYTHON-6183 Reject non-string filename               │
   │   https://github.com/mongodb/mongo-python-driver/pull/3237              │
   │                                                                         │
   │ ✅ test                                                                 │
   │                                                                         │
   │ Overall  ✅ success                                                     │
   ╰─────────────────────────────────────────────────────────────────────────╯
   ╭────────────────────── Evergreen: mongo-python-driver ───────────────────╮
   │ ⏳ Patch 1625 · started                                                 │
   │   'mongodb/mongo-python-driver' pull request #3237                      │
   │   https://spruce.mongodb.com/patch/6afe556ff40207000769d8bd             │
   │                                                                         │
   │ Overall  ⏳ pending                                                     │
   ╰─────────────────────────────────────────────────────────────────────────╯
   ╭────────────────────────────── Overall ─────────────────────────────────╮
   │ Combined  ⏳ pending                                                    │
   ╰─────────────────────────────────────────────────────────────────────────╯

Each system is a panel. The border and status text use colour: green for
success, red for failure, yellow for pending, and dim for unknown. Status
values are ``success``, ``failure``, ``pending``, and ``unknown``.

Options
-------

* ``<repo_name>`` - Repository name or path. Defaults to the current directory.
* ``-b, --branch <branch>`` - Branch to check. Defaults to the current branch.
* ``-n, --limit <count>`` - Number of workflow runs or patches to show. Default: 5.
* ``--json`` - Print a machine-readable report. No other text goes to stdout.

JSON output
-----------

``--json`` prints one object with ``repo``, ``branch``, ``github``,
``evergreen``, and ``overall`` keys. Each system object holds its own result
and an ``error`` field. A system that is not configured reports an error, but
the other system still runs.

Exit codes
----------

* ``0`` - No failure was found, or one system succeeded while the other was
  unavailable.
* ``1`` - A check failed, or neither system could be checked.

Limitations
-----------

Evergreen data comes from ``evergreen list-patches``, which lists patches you
created. Patches from other authors do not appear. GitHub Actions data needs
the ``gh`` CLI. Evergreen data needs the ``evergreen`` CLI.
