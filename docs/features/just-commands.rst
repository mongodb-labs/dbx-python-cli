Just Commands
=============

Run Just Commands in Repositories
----------------------------------

Run `just <https://github.com/casey/just>`_ commands in any cloned repository:

.. code-block:: bash

   # List repositories that have justfiles
   dbx just list

   # Show available just commands in a repository
   dbx just mongo-python-driver

   # Run a specific just command
   dbx just mongo-python-driver lint

   # Run a just command with arguments
   dbx just mongo-python-driver test -v

The ``just`` command will:

1. Find the repository by name across all cloned groups
2. Check if a ``justfile`` or ``Justfile`` exists in the repository
3. Run the specified just command (or show available commands if none specified)
4. Display the command output

Example Output
--------------

.. code-block:: bash

   $ dbx just list
   Repositories with justfiles:

     pymongo:
       • mongo-python-driver

   1 repository with justfiles

   Run 'dbx just <repo_name>' to see available just commands

   $ dbx just mongo-python-driver
   Running 'just' in ~/Developer/dbx-repos/pymongo/mongo-python-driver...

   Available recipes:
       install
       lint
       test
       docs

   $ dbx just mongo-python-driver lint
   Running 'just lint' in ~/Developer/dbx-repos/pymongo/mongo-python-driver...

   uvx pre-commit run --all-files
   trim trailing whitespace.................................................Passed
   fix end of files.........................................................Passed
   check yaml...............................................................Passed
   ruff.....................................................................Passed
   ruff-format..............................................................Passed

   $ dbx just mongo-python-driver test -v
   Running 'just test -v' in ~/Developer/dbx-repos/pymongo/mongo-python-driver...

   pytest -v
   ============================= test session starts ==============================
   ...

Environment Variables
---------------------

The ``just`` command automatically loads environment variables configured in your ``config.toml`` file,
just like the ``test`` command. This is useful for setting up environment variables needed by your
just recipes.

See :doc:`testing` for details on configuring environment variables.

Example configuration:

.. code-block:: toml

   [repo.groups.pymongo.test_env]
   mongo-python-driver = { DRIVERS_TOOLS = "{base_dir}/{group}/drivers-evergreen-tools", USE_ACTIVE_VENV = "1" }

When you run ``dbx just mongo-python-driver setup-tests``, these environment variables will be
automatically set.

Verbose Mode
------------

Use the ``-v`` / ``--verbose`` flag to see more detailed output:

.. code-block:: bash

   dbx -v just mongo-python-driver lint

This will show:

- Configuration details (base directory, config values)
- Environment variables being set (if any)
- Full command being executed
- Working directory for the just command

Requirements
------------

- The repository must be cloned first using ``dbx clone``
- The repository must have a ``justfile`` or ``Justfile`` in its root directory
- The ``just`` command must be installed on your system

What if there's no justfile?
-----------------------------

If you try to run ``dbx just`` on a repository that doesn't have a justfile, you'll see a warning:

.. code-block:: bash

   $ dbx just specifications
   ⚠️  Warning: No justfile found in ~/Developer/dbx-repos/pymongo/specifications
   This repository may not use just for task automation.
