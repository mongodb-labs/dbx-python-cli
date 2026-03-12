Global Options
==============

Verbose Mode
------------

Use the ``-v`` / ``--verbose`` flag to see more detailed output from any command:

.. code-block:: bash

   # Show verbose output when installing dependencies
   dbx -v install mongo-python-driver -e test

   # Show verbose output when running tests
   dbx -v test mongo-python-driver

   # Show verbose output when cloning repositories
   dbx -v clone -g pymongo

   # Show verbose output when running just commands
   dbx -v just mongo-python-driver lint

**What verbose mode shows:**

- Configuration details (base directory, config values)
- Full command being executed
- Working directory for subprocess commands
- Additional diagnostic information

**Note:** The verbose flag must come **before** the subcommand (e.g., ``dbx -v test``, not ``dbx test -v``).

Pager Mode
----------

Use the ``-p`` / ``--pager`` flag to view command output through a pager (``less``):

.. code-block:: bash

   # View git branches with a pager
   dbx -p branch -g pymongo

   # View git logs with a pager
   dbx -p log mongo-python-driver

   # View configuration with a pager
   dbx -p config show

   # Combine with verbose mode
   dbx -v -p branch -a

**When to use pager mode:**

- When viewing output that doesn't fit on one screen
- When you want to scroll through git logs or branch listings
- When reviewing configuration details

**How it works:**

- Uses ``less -R`` to display output with color support
- Only activates when stdout is a terminal (not when piping to files)
- Pagination is opt-in: you must use the ``-p`` flag to enable it
- Works with all commands that produce output

**Note:** The pager flag must come **before** the subcommand (e.g., ``dbx -p branch``, not ``dbx branch -p``).
