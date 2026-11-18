Spec Sync
=========

The ``dpy spec`` command streamlines syncing spec tests from the `MongoDB specifications repository <https://github.com/mongodb/specifications>`_ into a driver repo, and managing the patch files that exclude tests for not-yet-implemented features.

Background
----------

Driver repos like ``mongo-python-driver`` carry a copy of the spec tests defined in the central ``specifications`` repository. Keeping them in sync requires running a shell script (``resync-specs.sh``) that lives inside ``.evergreen/`` of the driver repo, with the ``MDB_SPECS`` environment variable pointing at a local clone of the specifications repo.

When a spec introduces tests for features that haven't been implemented yet, those tests are excluded via patch files in ``.evergreen/spec-patch/``. After each sync, ``git apply -R`` is run on every ``PYTHON-XXXX.patch`` file to reverse the unwanted changes.

The manual process documented in ``CONTRIBUTING.md`` looks like this:

.. code-block:: bash

   # One-time clone of the specs repo (if not already present)
   git clone git@github.com:mongodb/specifications.git ~/specifications

   # Every time you want to sync
   export MDB_SPECS=~/specifications
   cd ~/mongo-python-driver/.evergreen
   ./resync-specs.sh -b "<regex>" spec1 spec2 ...

   # Apply patches manually
   git apply -R --allow-empty --whitespace=fix .evergreen/spec-patch/*.patch

``dpy spec`` eliminates the manual steps by auto-detecting both repos from your existing dpy config and running the script for you, and ``dpy spec patch`` gives you full lifecycle management over the patch files.

How It Improves on the Manual Workflow
---------------------------------------

+--------------------------------+-----------------------------------------------+----------------------------------------------+
| Task                           | Manual                                        | With ``dpy spec``                            |
+================================+===============================================+==============================================+
| Locate the specs repo          | Remember/export ``MDB_SPECS`` path            | Auto-detected from config                    |
+--------------------------------+-----------------------------------------------+----------------------------------------------+
| Navigate to the script         | ``cd ~/mongo-python-driver/.evergreen``       | Not required                                 |
+--------------------------------+-----------------------------------------------+----------------------------------------------+
| Sync all specs                 | ``./resync-specs.sh``                         | ``dpy spec sync``                            |
+--------------------------------+-----------------------------------------------+----------------------------------------------+
| Sync specific specs            | ``./resync-specs.sh crud sessions``           | ``dpy spec sync crud sessions``              |
+--------------------------------+-----------------------------------------------+----------------------------------------------+
| Block files by pattern         | ``./resync-specs.sh -b "unified" crud``       | ``dpy spec sync crud -b "unified"``          |
+--------------------------------+-----------------------------------------------+----------------------------------------------+
| Sync and apply patches         | Run script, then ``git apply -R ...``         | ``dpy spec sync --apply-patches``            |
+--------------------------------+-----------------------------------------------+----------------------------------------------+
| Target a different driver repo | Repeat the ``cd``/``export`` dance            | ``dpy spec sync -r django-mongodb-backend``  |
+--------------------------------+-----------------------------------------------+----------------------------------------------+
| Preview without running        | No built-in option                            | ``dpy spec sync --dry-run``                  |
+--------------------------------+-----------------------------------------------+----------------------------------------------+
| Discover available specs       | Browse the ``specifications`` repo on disk    | ``dpy spec list``                            |
+--------------------------------+-----------------------------------------------+----------------------------------------------+
| See active patches             | ``ls .evergreen/spec-patch/``                 | ``dpy spec patch list``                      |
+--------------------------------+-----------------------------------------------+----------------------------------------------+
| Create a patch file            | Manually write/save a git diff                | ``dpy spec patch create PYTHON-XXXX``        |
+--------------------------------+-----------------------------------------------+----------------------------------------------+
| Remove a resolved patch        | ``rm .evergreen/spec-patch/PYTHON-XXXX.patch``| ``dpy spec patch remove PYTHON-XXXX``        |
+--------------------------------+-----------------------------------------------+----------------------------------------------+
| Check which specs need syncing  | Manually diff repo directories               | ``dpy spec status``                          |
+--------------------------------+-----------------------------------------------+----------------------------------------------+
| Apply all patches              | ``git apply -R --allow-empty ...``            | ``dpy spec patch apply``                     |
+--------------------------------+-----------------------------------------------+----------------------------------------------+

Prerequisites
-------------

Both repos must be cloned locally. If you use the default config, the ``specifications`` repo is part of the ``pymongo`` group:

.. code-block:: bash

   # Clone the pymongo group (includes specifications)
   dpy clone -g pymongo

Commands
--------

dpy spec sync
~~~~~~~~~~~~~

Runs ``.evergreen/resync-specs.sh`` in the driver repo with ``MDB_SPECS`` pointing at the specifications repo. After syncing, active patches are listed automatically so you know what will be excluded.

.. code-block:: bash

   # Sync all specs
   dpy spec sync

   # Sync specific specs by name
   dpy spec sync crud sessions change-streams

   # Exclude files matching a regex (passed as -b to resync-specs.sh)
   dpy spec sync crud -b "unified"

   # Sync and immediately apply all patches in one shot
   dpy spec sync crud --apply-patches

   # Target a different driver repo
   dpy spec sync -r django-mongodb-backend

   # Preview the exact command without running it
   dpy spec sync crud --dry-run

   # Use a custom path for the specifications repo
   dpy spec sync --specs-dir ~/my-specs crud

**Options:**

.. code-block:: text

   SPECS              Spec names to sync (e.g. crud transactions). Syncs all if omitted.
   -r, --repo         Driver repository to target [default: mongo-python-driver]
   -b, --block        Regex pattern passed to resync-specs.sh -b to exclude matching files
   --specs-dir        Path to the MongoDB specifications repo (overrides auto-detection)
   --apply-patches    Apply all .evergreen/spec-patch files after syncing
   --dry-run          Print the command that would be run without executing it

dpy spec list
~~~~~~~~~~~~~

Lists available spec directories from the local ``specifications`` repository.

.. code-block:: bash

   # List all available specs
   dpy spec list

   # List specs from a custom path
   dpy spec list --specs-dir ~/my-specs

**Example output:**

.. code-block:: text

   Specs in ~/Developer/mongodb/specifications:

   ├── auth
   ├── change-streams
   ├── client-side-encryption
   ├── connection-monitoring-and-pooling
   ├── crud
   ├── gridfs
   ├── load-balancers
   ├── max-staleness
   ├── read-write-concern
   ├── retryable-reads
   ├── retryable-writes
   ├── server-discovery-and-monitoring
   ├── sessions
   ├── transactions
   └── ...

Use the spec names from this output as arguments to ``dpy spec sync``.

dpy spec status
~~~~~~~~~~~~~~~

Compares JSON spec files in the driver repo against the local ``specifications`` repository and reports which specs are out of date, then suggests the exact ``dpy spec sync`` commands to run.  Also checks whether the current branch looks like a spec-resync branch and whether a recent resync commit exists.

.. code-block:: bash

   # Check status for the default driver repo (mongo-python-driver)
   dpy spec status

   # Check a different driver repo
   dpy spec status -r django-mongodb-backend

   # Use a custom path for the specifications repo
   dpy spec status --specs-dir ~/my-specs

**Example output:**

.. code-block:: text

   📊 Spec Status — mongo-python-driver

     🌿 Branch: spec-resync-05-18-2026 ✓
     🕐 Last resync commit: 36dffed resyncing specs 05-18-2026 (3 days ago)

     Checking 35 spec(s) against ~/Developer/mongodb/specifications/source...

     ❌ Stale (3) — suggest syncing:

     ├── dpy spec sync crud
     ├── dpy spec sync sessions
     └── dpy spec sync transactions

     ✅ Up to date (32): auth, bson-binary-vector, bson-corpus, ...

   📋 2 active patch(es) in mongo-python-driver:
     • PYTHON-1234 (3 file(s))
     • PYTHON-5678 (1 file(s))

     Run 'dpy spec patch apply' to apply them.

     💡 To sync all stale specs at once:
        dpy spec sync crud sessions transactions

**Notes:**

- Only ``.json`` files are compared (YAML files are excluded by ``resync-specs.sh`` by default).
- Run ``make`` in ``specifications/source`` first if you want to ensure the JSON files are freshly generated from YAML.
- A ``⚠`` next to the branch name means the branch does not contain "resync" or "spec" in its name.
- If no resync commit is found on the branch, a warning is shown — this may indicate you're on the wrong branch.

**Options:**

.. code-block:: text

   -r, --repo       Driver repository to inspect [default: mongo-python-driver]
   --specs-dir      Path to the MongoDB specifications repo (overrides auto-detection)

dpy spec patch list
~~~~~~~~~~~~~~~~~~~

Lists all active patch files and the test files each one affects. Add ``-v`` to see the individual filenames.

.. code-block:: bash

   dpy spec patch list
   dpy spec patch list -r django-mongodb-backend
   dpy -v spec patch list      # shows individual affected files

**Example output:**

.. code-block:: text

   Active patches in mongo-python-driver (3):

   ├── PYTHON-2673  (2 file(s))
   ├── PYTHON-4261  (1 file(s))
   └── PYTHON-5759  (4 file(s))

dpy spec patch create
~~~~~~~~~~~~~~~~~~~~~

Captures the current ``git diff`` into a new ``.evergreen/spec-patch/<ticket>.patch`` file. Run this after a spec sync brings in tests you don't want yet, then revert or edit those files so the diff captures only the unwanted changes.

.. code-block:: bash

   # Capture all unstaged changes
   dpy spec patch create PYTHON-1234

   # Capture changes to specific files only
   dpy spec patch create PYTHON-1234 test/crud/foo.json test/crud/bar.json

   # Preview the diff that would be saved without writing the file
   dpy spec patch create PYTHON-1234 --dry-run

dpy spec patch remove
~~~~~~~~~~~~~~~~~~~~~

Deletes a patch file once the corresponding ticket has been implemented and the tests should be re-enabled.

.. code-block:: bash

   dpy spec patch remove PYTHON-1234
   dpy spec patch remove PYTHON-1234 -r django-mongodb-backend

dpy spec patch apply
~~~~~~~~~~~~~~~~~~~~

Runs ``git apply -R --allow-empty --whitespace=fix`` on all ``.evergreen/spec-patch/*.patch`` files, matching what ``resync-all-specs.py`` does in CI.

.. code-block:: bash

   dpy spec patch apply
   dpy spec patch apply -r django-mongodb-backend
   dpy spec patch apply --dry-run    # list what would be applied

dpy spec patch verify
~~~~~~~~~~~~~~~~~~~~~

Checks each ``.evergreen/spec-patch/*.patch`` file to confirm it still applies cleanly against the current working tree. Runs ``git apply --check -R`` on every patch and reports whether each one is clean or stale. Exits non-zero if any patch is stale.

.. code-block:: bash

   dpy spec patch verify
   dpy spec patch verify -r django-mongodb-backend

**Example output:**

.. code-block:: text

   Verifying patches in mongo-python-driver:
     ✅ PYTHON-2673
     ✅ PYTHON-4261
     ❌ PYTHON-4918  [stale — does not apply cleanly]

   1 stale patch(es) found.

A patch becomes stale when the spec file it covers has been changed since the patch was created — for example, because a previous resync PR already incorporated part of those changes, or because the upstream file was renamed or removed. Stale patches should be removed (``dpy spec patch remove``) or recreated (``dpy spec patch remove`` + sync + ``dpy spec patch create``).

Reviewing Automated Spec Sync PRs
----------------------------------

The ``mongodb-drivers-pr-bot`` opens a weekly pull request (e.g. *[Spec Resync] 04-13-2026*) that runs ``resync-all-specs.py`` against the latest ``specifications`` repo and submits the result.

**Key point:** a spec resync is a pure file copy — ``resync-specs.sh`` copies JSON test files from ``specifications`` into ``test/`` with no logic or decisions. The diff in the PR is fully reproducible: check out ``main`` and run ``dpy spec sync`` to get identical output. Any CI failures on a resync PR are content-driven (the new spec tests exercise behaviour the driver hasn't implemented yet) and must be resolved before merging.

When tests fail on a resync PR, the options are:

* **Implement the feature** — fix the driver code so the new tests pass.
* **Add a patch** — create a ``.evergreen/spec-patch/PYTHON-XXXX.patch`` that reverse-applies the new tests until a ticket is resolved. The patch must be named after a *pre-existing* JIRA ticket.

The PR body summarises three things you need to triage:

* **Changed specs** — spec test files that were updated upstream and need review
* **Patch errors** — existing ``.evergreen/spec-patch/`` files that no longer apply cleanly
* **New directories** — spec folders that exist upstream but have no corresponding test directory yet

**Example PR body:**

.. code-block:: text

   The following specs were changed:
    -change_streams

   The following spec syncs encountered errors:
    -applying patches
   error: patch failed: test/uri_options/client-backpressure-options.json:1
   error: test/uri_options/client-backpressure-options.json: patch does not apply
   ...

   The following directories are in the specification repository and not in our test directory:
    -client_backpressure
    -open_telemetry

Triaging each section with ``dpy spec``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**1. Reproduce the sync locally**

Check out the PR branch and replay the sync for the specs listed as changed:

.. code-block:: bash

   git fetch origin && git checkout <pr-branch>

   # Re-sync the changed spec(s) from the PR description
   dpy spec sync change-streams

**2. Investigate patch errors**

Patch errors mean a patch file references test content that no longer matches what the spec repo contains — the upstream file may have been renamed, removed, or changed in a way that makes the old diff inapplicable.

.. code-block:: bash

   # See which patches exist and what files they cover
   dpy spec patch list

   # Verbose mode shows the individual filenames — useful for spotting
   # stale paths that no longer exist after a rename/removal upstream
   dpy -v spec patch list

   # Check each patch individually — reports ✅ clean or ❌ stale
   dpy spec patch verify

   # Try applying patches to see which ones fail
   dpy spec patch apply

Once you know which patch is stale, the fix is one of:

* **File was deleted upstream** — the test the patch was protecting is gone; remove the patch:

  .. code-block:: bash

     dpy spec patch remove PYTHON-XXXX

* **File was renamed/modified** — re-sync, make the manual edits again, and recreate the patch:

  .. code-block:: bash

     dpy spec patch remove PYTHON-XXXX
     dpy spec sync <spec-name>
     # manually revert the unwanted lines
     dpy spec patch create PYTHON-XXXX

**3. Evaluate new spec directories**

New directories in the spec repo (``client_backpressure``, ``open_telemetry`` in the example above) mean the upstream team has added a new spec that pymongo doesn't implement yet. For each one, decide:

* **Not yet implemented** — create a JIRA ticket (``PYTHON-XXXX``), sync the spec, and immediately patch out the tests:

  .. code-block:: bash

     # Pull in the new spec tests
     dpy spec sync client-backpressure

     # Patch them all out until the feature is implemented
     dpy spec patch create PYTHON-XXXX

* **Already implemented** — sync the spec and verify the tests pass without a patch:

  .. code-block:: bash

     dpy spec sync client-backpressure

**4. Full local repro in one shot**

Once you have the right patches in place, confirm the complete sync applies cleanly:

.. code-block:: bash

   dpy spec sync --apply-patches

A clean run with no patch errors means the PR is safe to merge.

Typical Workflows
-----------------

**Full sync with patches in one command**

.. code-block:: bash

   dpy sync specifications            # pull latest from upstream
   dpy spec sync crud --apply-patches # sync and apply patches

**Sync, then handle new unimplemented tests**

.. code-block:: bash

   # 1. Sync the spec you're working on
   dpy spec sync crud

   # 2. Active patches are shown automatically — apply them
   dpy spec patch apply

   # 3. If new unimplemented tests appeared, revert/edit them and create a patch
   dpy spec patch create PYTHON-1234

**Implementing a ticket (removing a patch)**

.. code-block:: bash

   # The feature is now implemented — remove its patch file
   dpy spec patch remove PYTHON-1234

   # Re-sync to verify the tests now pass without the patch
   dpy spec sync crud

**See what's excluded before syncing**

.. code-block:: bash

   dpy spec patch list          # quick overview
   dpy -v spec patch list       # with individual filenames

Configuration
-------------

No extra configuration is required beyond having ``specifications`` in your repo groups. The spec command finds it automatically:

.. code-block:: toml

   [repo.groups.pymongo]
   repos = [
       "git@github.com:mongodb/specifications.git",
       "git@github.com:mongodb/mongo-python-driver.git",
       # ...
   ]

If you keep the specifications repo at a non-standard location, pass ``--specs-dir`` each time or symlink it into your ``base_dir``.
