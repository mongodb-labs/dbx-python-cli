Standalone Installation
=======================

**Decision: Install dbx-python-cli as a standalone tool, not requiring a clone of the CLI repository**

Background
----------

The predecessor to ``dbx-python-cli`` was `django-mongodb-cli <https://github.com/mongodb-labs/django-mongodb-cli>`_, which required users to:

1. Clone the ``django-mongodb-cli`` repository
2. Work within that repository's directory structure
3. Configure ``base_dir`` to point to a subdirectory within the cloned repo (e.g., ``django-mongodb-cli/repos/``)

This approach had several limitations:

- Users had to manage the CLI tool's repository alongside their actual work repositories
- The CLI repository became a "workspace" that mixed tool code with user data
- Updates to the CLI required pulling changes in a repository that also contained user's cloned repos
- The tool was tightly coupled to its own repository structure
- Users couldn't easily install and use the tool from anywhere

New Approach
------------

``dbx-python-cli`` is designed as a **standalone tool** that can be installed globally and used from anywhere:

.. code-block:: bash

   # Install globally using pipx
   pipx install git+https://github.com/mongodb-labs/dbx-python-cli.git

   # Use from anywhere
   cd ~/Developer/mongodb/
   dbx clone -g pymongo

Key Differences
---------------

**django-mongodb-cli (old approach):**

.. code-block:: text

   ~/Developer/
   └── django-mongodb-cli/          # CLI repository (required)
       ├── src/                      # CLI source code
       ├── repos/                    # User's cloned repositories
       │   ├── django/
       │   └── django-mongodb-backend/
       └── config.toml               # Configuration

**dbx-python-cli (new approach):**

.. code-block:: text

   # CLI installed globally via pipx
   # No CLI repository needed in workspace

   ~/Developer/mongodb/              # User's workspace (configurable)
   ├── pymongo/
   │   ├── .venv/
   │   ├── mongo-python-driver/
   │   └── specifications/
   └── django/
       ├── .venv/
       ├── django/
       └── django-mongodb-backend/

   ~/.config/dbx-python-cli/         # Configuration (separate)
   └── config.toml

Benefits
--------

**Separation of Concerns**
   The CLI tool is completely separate from the user's workspace. Tool updates don't affect user data.

**Flexibility**
   Users can configure ``base_dir`` to point anywhere on their system, not just within the CLI repository.

**Cleaner Workspace**
   The user's workspace contains only their actual work repositories, not the CLI tool's code.

**Standard Installation**
   Uses standard Python packaging tools (``pipx install``) instead of requiring a git clone.

**Global Availability**
   The ``dbx`` command is available from anywhere in the terminal, not just within a specific directory.

**Easier Updates**
   Update the tool with ``pipx upgrade dbx-python-cli`` without affecting user repositories.

**Multiple Workspaces**
   Users can easily work with multiple base directories by updating the config, without needing multiple CLI clones.

Implementation Details
----------------------

**Configuration Location**

Configuration is stored in the standard user config directory:

- **macOS/Linux**: ``~/.config/dbx-python-cli/config.toml``
- **Windows**: ``%APPDATA%\dbx-python-cli\config.toml``

**Base Directory**

The ``base_dir`` setting in the config points to where repositories should be cloned:

.. code-block:: toml

   [repo]
   base_dir = "~/Developer/mongodb/"

This can be any directory on the user's system.

**Initialization**

The ``dbx config init`` command creates the initial configuration:

.. code-block:: bash

   $ dbx config init
   Configuration file created at: ~/.config/dbx-python-cli/config.toml

   Default base directory: ~/Developer/mongodb/

   Edit the configuration file to customize repository groups and settings.

**No Repository Required**

Users never need to clone or interact with the ``dbx-python-cli`` repository itself. The tool is installed as a package and used as a command-line utility.

Comparison with Other Tools
----------------------------

This approach aligns with how most modern CLI tools work:

- **git**: Installed globally, works in any directory
- **docker**: Installed globally, manages containers anywhere
- **kubectl**: Installed globally, manages clusters from anywhere
- **aws-cli**: Installed globally, works with any AWS resources

The old approach (requiring a clone) was more like:

- **Makefiles**: Must be in the repository to use
- **Scripts in repos**: Tied to specific repository structure

Migration from django-mongodb-cli
----------------------------------

Users migrating from ``django-mongodb-cli`` should:

1. Install ``dbx-python-cli`` globally:

   .. code-block:: bash

      pipx install git+https://github.com/mongodb-labs/dbx-python-cli.git

2. Initialize configuration:

   .. code-block:: bash

      dbx config init

3. Update ``base_dir`` in ``~/.config/dbx-python-cli/config.toml`` to point to their existing repositories (or a new location)

4. The ``django-mongodb-cli`` repository can be safely removed - it's no longer needed

Rationale
---------

This design decision reflects modern best practices for CLI tools:

- **User-centric**: The tool serves the user's workflow, not the other way around
- **Portable**: Works from anywhere, not tied to a specific directory
- **Maintainable**: Tool updates are independent of user data
- **Standard**: Follows Python packaging conventions
- **Flexible**: Users control their workspace organization

The standalone installation model makes ``dbx-python-cli`` a true utility tool rather than a workspace that users must work within.
