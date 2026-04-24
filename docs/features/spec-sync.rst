Spec Sync
=========

The ``dbx spec`` command streamlines syncing spec tests from the `MongoDB specifications repository <https://github.com/mongodb/specifications>`_ into a driver repo, and managing the patch files that exclude tests for not-yet-implemented features.

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

``dbx spec`` eliminates the manual steps by auto-detecting both repos from your existing dbx config and running the script for you, and ``dbx spec patch`` gives you full lifecycle management over the patch files.

How It Improves on the Manual Workflow
---------------------------------------

+--------------------------------+-----------------------------------------------+------------------------------------------+
| Task                           | Manual                                        | With ``dbx spec``                        |
+================================+===============================================+==========================================+
| Locate the specs repo          | Remember/export ``MDB_SPECS`` path            | Auto-detected from config                |
+--------------------------------+-----------------------------------------------+------------------------------------------+
| Navigate to the script         | ``cd ~/mongo-python-driver/.evergreen``       | Not required                             |
+--------------------------------+-----------------------------------------------+------------------------------------------+
| Sync all specs                 | ``./resync-specs.sh``                         | ``dbx spec sync``                        |
+--------------------------------+-----------------------------------------------+------------------------------------------+
| Sync specific specs            | ``./resync-specs.sh crud sessions``           | ``dbx spec sync crud sessions``          |
+--------------------------------+-----------------------------------------------+------------------------------------------+
| Block files by pattern         | ``./resync-specs.sh -b "unified" crud``       | ``dbx spec sync crud -b "unified"``      |
+--------------------------------+-----------------------------------------------+------------------------------------------+
| Sync and apply patches         | Run script, then ``git apply -R ...``         | ``dbx spec sync --apply-patches``        |
+--------------------------------+-----------------------------------------------+------------------------------------------+
| Target a different driver repo | Repeat the ``cd``/``export`` dance            | ``dbx spec sync -r django-mongodb-backend`` |
+--------------------------------+-----------------------------------------------+------------------------------------------+
| Preview without running        | No built-in option                            | ``dbx spec sync --dry-run``              |
+--------------------------------+-----------------------------------------------+------------------------------------------+
| Discover available specs       | Browse the ``specifications`` repo on disk    | ``dbx spec list``                        |
+--------------------------------+-----------------------------------------------+------------------------------------------+
| See active patches             | ``ls .evergreen/spec-patch/``                 | ``dbx spec patch list``                  |
+--------------------------------+-----------------------------------------------+------------------------------------------+
| Create a patch file            | Manually write/save a git diff                | ``dbx spec patch create PYTHON-XXXX``    |
+--------------------------------+-----------------------------------------------+------------------------------------------+
| Remove a resolved patch        | ``rm .evergreen/spec-patch/PYTHON-XXXX.patch``| ``dbx spec patch remove PYTHON-XXXX``   |
+--------------------------------+-----------------------------------------------+------------------------------------------+
| Apply all patches              | ``git apply -R --allow-empty ...``            | ``dbx spec patch apply``                 |
+--------------------------------+-----------------------------------------------+------------------------------------------+

Prerequisites
-------------

Both repos must be cloned locally. If you use the default config, the ``specifications`` repo is part of the ``pymongo`` group:

.. code-block:: bash

   # Clone the pymongo group (includes specifications)
   dbx clone -g pymongo

Commands
--------

dbx spec sync
~~~~~~~~~~~~~

Runs ``.evergreen/resync-specs.sh`` in the driver repo with ``MDB_SPECS`` pointing at the specifications repo. After syncing, active patches are listed automatically so you know what will be excluded.

.. code-block:: bash

   # Sync all specs
   dbx spec sync

   # Sync specific specs by name
   dbx spec sync crud sessions change-streams

   # Exclude files matching a regex (passed as -b to resync-specs.sh)
   dbx spec sync crud -b "unified"

   # Sync and immediately apply all patches in one shot
   dbx spec sync crud --apply-patches

   # Target a different driver repo
   dbx spec sync -r django-mongodb-backend

   # Preview the exact command without running it
   dbx spec sync crud --dry-run

   # Use a custom path for the specifications repo
   dbx spec sync --specs-dir ~/my-specs crud

**Options:**

.. code-block:: text

   SPECS              Spec names to sync (e.g. crud transactions). Syncs all if omitted.
   -r, --repo         Driver repository to target [default: mongo-python-driver]
   -b, --block        Regex pattern passed to resync-specs.sh -b to exclude matching files
   --specs-dir        Path to the MongoDB specifications repo (overrides auto-detection)
   --apply-patches    Apply all .evergreen/spec-patch files after syncing
   --dry-run          Print the command that would be run without executing it

dbx spec list
~~~~~~~~~~~~~

Lists available spec directories from the local ``specifications`` repository.

.. code-block:: bash

   # List all available specs
   dbx spec list

   # List specs from a custom path
   dbx spec list --specs-dir ~/my-specs

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

Use the spec names from this output as arguments to ``dbx spec sync``.

dbx spec patch list
~~~~~~~~~~~~~~~~~~~

Lists all active patch files and the test files each one affects. Add ``-v`` to see the individual filenames.

.. code-block:: bash

   dbx spec patch list
   dbx spec patch list -r django-mongodb-backend
   dbx -v spec patch list      # shows individual affected files

**Example output:**

.. code-block:: text

   Active patches in mongo-python-driver (3):

   ├── PYTHON-2673  (2 file(s))
   ├── PYTHON-4261  (1 file(s))
   └── PYTHON-5759  (4 file(s))

dbx spec patch create
~~~~~~~~~~~~~~~~~~~~~

Captures the current ``git diff`` into a new ``.evergreen/spec-patch/<ticket>.patch`` file. Run this after a spec sync brings in tests you don't want yet, then revert or edit those files so the diff captures only the unwanted changes.

.. code-block:: bash

   # Capture all unstaged changes
   dbx spec patch create PYTHON-1234

   # Capture changes to specific files only
   dbx spec patch create PYTHON-1234 test/crud/foo.json test/crud/bar.json

   # Preview the diff that would be saved without writing the file
   dbx spec patch create PYTHON-1234 --dry-run

dbx spec patch remove
~~~~~~~~~~~~~~~~~~~~~

Deletes a patch file once the corresponding ticket has been implemented and the tests should be re-enabled.

.. code-block:: bash

   dbx spec patch remove PYTHON-1234
   dbx spec patch remove PYTHON-1234 -r django-mongodb-backend

dbx spec patch apply
~~~~~~~~~~~~~~~~~~~~

Runs ``git apply -R --allow-empty --whitespace=fix`` on all ``.evergreen/spec-patch/*.patch`` files, matching what ``resync-all-specs.py`` does in CI.

.. code-block:: bash

   dbx spec patch apply
   dbx spec patch apply -r django-mongodb-backend
   dbx spec patch apply --dry-run    # list what would be applied

Reviewing Automated Spec Sync PRs
----------------------------------

The ``mongodb-drivers-pr-bot`` opens a weekly pull request (e.g. *[Spec Resync] 04-13-2026*) that runs ``resync-all-specs.py`` against the latest ``specifications`` repo and submits the result. The PR body summarises three things you need to triage:

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

Triaging each section with ``dbx spec``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**1. Reproduce the sync locally**

Check out the PR branch and replay the sync for the specs listed as changed:

.. code-block:: bash

   git fetch origin && git checkout <pr-branch>

   # Re-sync the changed spec(s) from the PR description
   dbx spec sync change-streams

**2. Investigate patch errors**

Patch errors mean a patch file references test content that no longer matches what the spec repo contains — the upstream file may have been renamed, removed, or changed in a way that makes the old diff inapplicable.

.. code-block:: bash

   # See which patches exist and what files they cover
   dbx spec patch list

   # Verbose mode shows the individual filenames — useful for spotting
   # stale paths that no longer exist after a rename/removal upstream
   dbx -v spec patch list

   # Try applying patches to see which ones fail
   dbx spec patch apply

Once you know which patch is stale, the fix is one of:

* **File was deleted upstream** — the test the patch was protecting is gone; remove the patch:

  .. code-block:: bash

     dbx spec patch remove PYTHON-XXXX

* **File was renamed/modified** — re-sync, make the manual edits again, and recreate the patch:

  .. code-block:: bash

     dbx spec patch remove PYTHON-XXXX
     dbx spec sync <spec-name>
     # manually revert the unwanted lines
     dbx spec patch create PYTHON-XXXX

**3. Evaluate new spec directories**

New directories in the spec repo (``client_backpressure``, ``open_telemetry`` in the example above) mean the upstream team has added a new spec that pymongo doesn't implement yet. For each one, decide:

* **Not yet implemented** — create a JIRA ticket (``PYTHON-XXXX``), sync the spec, and immediately patch out the tests:

  .. code-block:: bash

     # Pull in the new spec tests
     dbx spec sync client-backpressure

     # Patch them all out until the feature is implemented
     dbx spec patch create PYTHON-XXXX

* **Already implemented** — sync the spec and verify the tests pass without a patch:

  .. code-block:: bash

     dbx spec sync client-backpressure

**4. Full local repro in one shot**

Once you have the right patches in place, confirm the complete sync applies cleanly:

.. code-block:: bash

   dbx spec sync --apply-patches

A clean run with no patch errors means the PR is safe to merge.

Typical Workflows
-----------------

**Full sync with patches in one command**

.. code-block:: bash

   dbx sync specifications            # pull latest from upstream
   dbx spec sync crud --apply-patches # sync and apply patches

**Sync, then handle new unimplemented tests**

.. code-block:: bash

   # 1. Sync the spec you're working on
   dbx spec sync crud

   # 2. Active patches are shown automatically — apply them
   dbx spec patch apply

   # 3. If new unimplemented tests appeared, revert/edit them and create a patch
   dbx spec patch create PYTHON-1234

**Implementing a ticket (removing a patch)**

.. code-block:: bash

   # The feature is now implemented — remove its patch file
   dbx spec patch remove PYTHON-1234

   # Re-sync to verify the tests now pass without the patch
   dbx spec sync crud

**See what's excluded before syncing**

.. code-block:: bash

   dbx spec patch list          # quick overview
   dbx -v spec patch list       # with individual filenames

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
