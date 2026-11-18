Command Structure
=================

This document explains the design decisions behind how commands are organised in the CLI.

Decision
--------

We prefer **top-level commands** (``dpy clone``, ``dpy sync``) over **nested command groups** (``dpy repo clone``, ``dpy repo sync``), but command groups and even two-level nesting are used when the domain is rich enough to warrant it.

Rationale
---------

Simplicity and Discoverability
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Top-level commands are more discoverable and easier to use:

- **Shorter commands**: ``dpy clone -g pymongo`` vs ``dpy repo clone -g pymongo``
- **Fewer concepts**: Users don't need to understand command groups
- **Better help output**: Commands appear directly in ``dpy --help``

Common Usage Patterns
~~~~~~~~~~~~~~~~~~~~~

The most frequently used commands should be at the top level:

- ``dpy clone`` — Clone repositories from a group
- ``dpy sync`` — Sync repositories with upstream
- ``dpy backports`` — List commits on main that have not reached a release branch
- ``dpy install`` — Install packages
- ``dpy test`` — Run tests
- ``dpy list`` — List cloned repositories

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

   dpy branch      Git branch operations across repositories
   dpy clone       Clone a repository group
   dpy edit        Open a repository in an editor
   dpy install     Install package dependencies
   dpy just        Run just commands in a repository
   dpy list        List cloned repositories
   dpy log         Git log across repositories
   dpy open        Open a repository in the browser
   dpy patch       Create Evergreen CI patches
   dpy remove      Remove a cloned repository
   dpy status      Git status across repositories
   dpy switch      Switch git branches across repositories
   dpy sync        Sync repositories with upstream
   dpy backports   List backport candidates for a release branch
   dpy test        Run tests in a repository

Command Groups (One Level)
~~~~~~~~~~~~~~~~~~~~~~~~~~

Related subcommands that share a common domain:

.. code-block:: bash

   # Configuration management
   dpy config init
   dpy config show
   dpy config edit
   dpy config validate

   # Documentation operations
   dpy docs build
   dpy docs list
   dpy docs open

   # Virtual environment management
   dpy env init
   dpy env list
   dpy env remove
   dpy env status

   # Infrastructure requirements per repo
   dpy infra list mongo-python-driver
   dpy infra check mongo-python-driver auth_oidc

   # Django project management
   dpy project add myproject
   dpy project edit
   dpy project install
   dpy project migrate
   dpy project run
   dpy project su
   dpy project list
   dpy project remove

   # Git worktree management
   dpy worktree add django --upstream
   dpy worktree list django
   dpy worktree remove django

Command Groups (Two Levels)
~~~~~~~~~~~~~~~~~~~~~~~~~~~

When a domain has enough distinct sub-domains, two levels of nesting are acceptable. The only current example is ``dpy spec``, where spec-level operations (``sync``, ``list``, ``status``) are clearly separate from patch lifecycle operations:

.. code-block:: bash

   # Spec-level operations
   dpy spec sync crud sessions
   dpy spec list
   dpy spec status

   # Patch lifecycle (sub-group)
   dpy spec patch apply
   dpy spec patch create PYTHON-1234
   dpy spec patch list
   dpy spec patch remove PYTHON-1234
   dpy spec patch verify

Two-level nesting should remain rare. The bar for adding a third level is very high — if you find yourself wanting ``dpy foo bar baz``, consider whether ``foo`` and ``bar`` should be merged or whether ``baz`` belongs at a higher level.

When to Use Command Groups
~~~~~~~~~~~~~~~~~~~~~~~~~~

Command groups are appropriate when:

- **Multiple related subcommands** share a common domain (e.g., environment management, spec sync)
- **Namespacing prevents collisions** — ``dpy spec list`` and ``dpy list`` do different things
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

   dpy repo clone -g pymongo
   dpy repo sync mongo-python-driver
   dpy repo -l

**After:**

.. code-block:: bash

   dpy clone -g pymongo
   dpy sync mongo-python-driver
   dpy list

The ``repo.py`` module was converted from a command module to a utility functions module containing helpers like ``get_config()``, ``get_base_dir()``, and ``get_repo_groups()``.

Smart Defaults for Convenience
-------------------------------

To further improve usability, commands should provide smart defaults when possible.

Project Commands Default to Newest
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Most ``dpy project`` commands default to the newest project when no project name is specified:

.. code-block:: bash

   dpy project run              # Run newest project
   dpy project manage shell     # Open shell on newest project
   dpy project su               # Create superuser on newest project
   dpy project migrate          # Run migrations on newest project
   dpy project remove           # Remove newest project

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
