Quick Start
===========

This guide will help you get started with dbx-python-cli in just a few minutes.

Step 1: Initialize Configuration
---------------------------------

First, initialize the configuration file:

.. code-block:: bash

   dbx config init

This creates a configuration file at ``~/.config/dbx-python-cli/config.toml`` with default settings.

The default configuration includes:

- Base directory: ``~/Developer/mongodb``
- Pre-configured repository groups (django, pymongo, langchain, etc.)

You can edit this file to customize your setup.

Step 2: Clone Repositories
---------------------------

Clone a group of related repositories:

.. code-block:: bash

   # Clone the django group
   dbx clone -g django

This will clone all repositories in the django group to ``~/Developer/mongodb/django/``.

Step 3: Install Dependencies
-----------------------------

.. tip::

   The ``dbx clone`` command automatically runs ``dbx install`` after cloning, but you can also install repositories and repository groups manually.

Install dependencies for a repository:

.. code-block:: bash

   # Install dependencies for django-mongodb-backend
   dbx install django-mongodb-backend

To install with extras:

.. code-block:: bash

   # Install with test extras
   dbx install django-mongodb-backend -e test

   # Install libmongocrypt (includes cmake build step for Queryable Encryption)
   dbx install libmongocrypt

.. tip::

   Extras can also be configured in your ``~/.dbx.toml`` config file so you don't need to specify them on the command line each time.

Step 4: Run Tests
-----------------

Run tests for a repository:

.. code-block:: bash

   # Run all tests
   dbx test django

   # Run a specific test module (note: django-mongodb-backend modules have trailing underscores)
   dbx test django encryption_

   # Run tests matching a keyword
   dbx test django encryption_ -k test_schema

Working with Django Projects
-----------------------------

Create and manage Django projects with MongoDB backend:

.. code-block:: bash

   # Create a new project
   dbx project add myproject

   # Install the project
   dbx install myproject

   # Run migrations (defaults to newest project)
   dbx project migrate

   # Create a superuser (defaults to newest project)
   dbx project su

   # Run the project (defaults to newest project)
   dbx project run

.. note::

   **Convenience Feature**: Most project commands default to the newest project when no name is specified. This makes it faster to work with your current project without typing the name repeatedly.

Common Workflows
----------------

List Everything
~~~~~~~~~~~~~~~

See what's available:

.. code-block:: bash

   # List all cloned repositories
   dbx list

   # List all virtual environments
   dbx env list

Run Just Commands
~~~~~~~~~~~~~~~~~

If a repository has a ``justfile``, you can run just commands:

.. code-block:: bash

   # Show available just commands
   dbx just mongo-python-driver

   # Run a specific just command
   dbx just mongo-python-driver lint

   # Run just command with arguments
   dbx just mongo-python-driver test -v

Sync Repositories
~~~~~~~~~~~~~~~~~

Keep your repositories up to date:

.. code-block:: bash

   # Sync a single repository
   dbx sync django-mongodb-backend

   # Sync all repositories in a group
   dbx sync -g django

View Git Branches
~~~~~~~~~~~~~~~~~

View branches across repositories:

.. code-block:: bash

   # View branches in a single repository
   dbx branch django-mongodb-backend

   # View all branches (including remote)
   dbx branch django-mongodb-backend -a

   # View branches in all repositories in a group
   dbx branch -g django

   # View all branches in all repositories in a group
   dbx branch -g django -a

Working with Multiple Groups
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

You can work with multiple repository groups:

.. code-block:: bash

   # Clone langchain group
   dbx clone -g langchain

   # Create venv for langchain
   dbx env init -g langchain

   # Install dependencies
   dbx install langchain-mongodb -g langchain

Verbose Mode
~~~~~~~~~~~~

Use ``-v`` or ``--verbose`` for detailed output:

.. code-block:: bash

   dbx -v install django-mongodb-backend
   dbx --verbose test django encryption_

Next Steps
----------

Now that you're familiar with the basics, explore:

- :doc:`../features/index` - Detailed feature documentation
- :doc:`overview` - High-level overview of all features
- :doc:`../design/index` - Design decisions and architecture
- :doc:`../development/index` - Contributing to dbx-python-cli
