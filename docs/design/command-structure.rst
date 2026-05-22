Command Structure
=================

This document explains the design decisions behind how commands are organised in the CLI.

Decision
--------

We prefer **top-level commands** (``dbx clone``, ``dbx sync``) over **nested command groups** (``dbx repo clone``, ``dbx repo sync``), but command groups and even two-level nesting are used when the domain is rich enough to warrant it.

Rationale
---------

Simplicity and Discoverability
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Top-level commands are more discoverable and easier to use:

- **Shorter commands**: ``dbx clone -g pymongo`` vs ``dbx repo clone -g pymongo``
- **Fewer concepts**: Users don't need to understand command groups
- **Better help output**: Commands appear directly in ``dbx --help``

Common Usage Patterns
~~~~~~~~~~~~~~~~~~~~~

The most frequently used commands should be at the top level:

- ``dbx clone`` — Clone repositories from a group
- ``dbx sync`` — Sync repositories with upstream
- ``dbx install`` — Install packages
- ``dbx test`` — Run tests
- ``dbx list`` — List cloned repositories

These are the primary workflows, so they should be as accessible as possible.

Consistency with Git
~~~~~~~~~~~~~~~~~~~~

Git uses top-level commands (``git clone``, ``git pull``, ``git push``) rather than nested groups (``git repo clone``). This pattern is familiar to developers.

Current Command Inventory
-------------------------

Top-Level Commands
~~~~~~~~~~~~~~~~~~

Single-action commands that are frequently used or domain-agnostic:

.. code-block:: text

   dbx branch      Git branch operations across repositories
   dbx clone       Clone a repository group
   dbx edit        Open a repository in an editor
   dbx install     Install package dependencies
   dbx just        Run just commands in a repository
   dbx list        List cloned repositories
   dbx log         Git log across repositories
   dbx open        Open a repository in the browser
   dbx patch       Create Evergreen CI patches
   dbx remove      Remove a cloned repository
   dbx status      Git status across repositories
   dbx swap        Swap between repository versions
   dbx switch      Switch git branches across repositories
   dbx sync        Sync repositories with upstream
   dbx test        Run tests in a repository

Command Groups (One Level)
~~~~~~~~~~~~~~~~~~~~~~~~~~

Related subcommands that share a common domain:

.. code-block:: bash

   # Configuration management
   dbx config init
   dbx config show
   dbx config edit

   # Documentation operations
   dbx docs build
   dbx docs list
   dbx docs open

   # Virtual environment management
   dbx env init
   dbx env list
   dbx env remove

   # Django project management
   dbx project add myproject
   dbx project install
   dbx project migrate
   dbx project run
   dbx project su
   dbx project list
   dbx project remove

Command Groups (Two Levels)
~~~~~~~~~~~~~~~~~~~~~~~~~~~

When a domain has enough distinct sub-domains, two levels of nesting are acceptable. The only current example is ``dbx spec``, where spec-level operations (``sync``, ``list``, ``status``) are clearly separate from patch lifecycle operations:

.. code-block:: bash

   # Spec-level operations
   dbx spec sync crud sessions
   dbx spec list
   dbx spec status

   # Patch lifecycle (sub-group)
   dbx spec patch apply
   dbx spec patch create PYTHON-1234
   dbx spec patch list
   dbx spec patch remove PYTHON-1234
   dbx spec patch verify

Two-level nesting should remain rare. The bar for adding a third level is very high — if you find yourself wanting ``dbx foo bar baz``, consider whether ``foo`` and ``bar`` should be merged or whether ``baz`` belongs at a higher level.

When to Use Command Groups
~~~~~~~~~~~~~~~~~~~~~~~~~~

Command groups are appropriate when:

- **Multiple related subcommands** share a common domain (e.g., environment management, spec sync)
- **Namespacing prevents collisions** — ``dbx spec list`` and ``dbx list`` do different things
- **The group has 3+ subcommands** — a group with only one subcommand adds friction without benefit

Top-level placement is preferred when:

- The command is used frequently in isolation
- It has no natural siblings that share state or configuration
- Adding it to a group would make it harder to discover

Migration Notes
---------------

This design was established when ``clone`` and ``sync`` were promoted from the ``repo`` command group to the top level.

**Before:**

.. code-block:: bash

   dbx repo clone -g pymongo
   dbx repo sync mongo-python-driver
   dbx repo -l

**After:**

.. code-block:: bash

   dbx clone -g pymongo
   dbx sync mongo-python-driver
   dbx list

The ``repo.py`` module was converted from a command module to a utility functions module containing helpers like ``get_config()``, ``get_base_dir()``, and ``get_repo_groups()``.

Smart Defaults for Convenience
-------------------------------

To further improve usability, commands should provide smart defaults when possible.

Project Commands Default to Newest
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Most ``dbx project`` commands default to the newest project when no project name is specified:

.. code-block:: bash

   dbx project run              # Run newest project
   dbx project manage shell     # Open shell on newest project
   dbx project su               # Create superuser on newest project
   dbx project migrate          # Run migrations on newest project
   dbx project remove           # Remove newest project

The "newest" project is determined by filesystem modification time. When a command defaults to the newest project, it displays an informative message:

.. code-block:: text

   ℹ️  No project specified, using newest: 'myproject'

This follows the principle of **optimizing for the common case**: developers typically work on one project at a time, so requiring the project name for every command adds unnecessary friction.

Future Considerations
---------------------

As the CLI grows, continue to evaluate whether commands belong at the top level or in a group:

- **Top level**: Frequently used, standalone operations
- **Command groups**: Related operations that share context or configuration
- **Two-level groups**: Only when a domain is large enough to have distinct sub-domains

When adding smart defaults:

- **Sensible defaults**: Commands should work with minimal arguments for common use cases
- **Clear feedback**: When defaults are applied, inform the user what was chosen
- **Easy override**: Defaults should be easy to override when needed
