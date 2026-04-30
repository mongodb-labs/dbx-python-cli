Project Management
==================

The ``dbx project`` command provides tools for creating and managing Django projects with MongoDB backend support.

Overview
--------

Projects are Django applications created from bundled templates that include:

- Django project structure with MongoDB backend configuration
- Optional frontend application with webpack setup
- Pre-configured settings with commented Queryable Encryption (QE) support
- Justfile for common development tasks
- Pre-generated migrations for Django's built-in apps

Projects are created in ``base_dir/projects/`` by default, where ``base_dir`` is configured in your ``~/.config/dbx-python-cli/config.toml`` file.

Newest Project Default
~~~~~~~~~~~~~~~~~~~~~~

**Most project commands default to the newest project when no project name is specified.** This makes it easier to work with your most recent project without having to type the project name repeatedly.

The "newest" project is determined by the most recently modified project directory (based on filesystem modification time). When a command defaults to the newest project, you'll see an informative message:

.. code-block:: text

   ℹ️  No project specified, using newest: 'myproject'

Commands that support this behavior:

- ``dbx project run`` - Run the Django development server
- ``dbx project remove`` - Remove a project
- ``dbx project manage`` - Run Django management commands
- ``dbx project migrate`` - Run Django migrations
- ``dbx project su`` - Create a superuser

This feature is particularly useful during active development when you're frequently working with the same project.

Creating Projects
-----------------

Create a new Django project with the ``add`` command:

.. code-block:: bash

   # Create a project with explicit name (includes frontend by default)
   dbx project add myproject

   # Create without frontend
   dbx project add myproject --no-frontend

   # Generate a random project name (omit the name argument)
   dbx project add

   # Create in a custom directory
   dbx project add myproject -d ~/custom/path

   # Enable Wagtail CMS
   dbx project add myproject --wagtail

   # Enable Queryable Encryption
   dbx project add myproject --qe

   # Stack flags: Wagtail + QE
   dbx project add myproject --wagtail --qe

   # Install local clones into the project venv after creation
   dbx project add myproject --with medical-records
   dbx project add myproject --with django --with django-mongodb-extensions

Omitting the project name generates a random name from adjectives and nouns (e.g., ``swift_seal``, ``brave_eagle``).

If no virtual environment exists when ``dbx project add`` runs, one is created automatically at the ``projects/`` group level and Django is installed into it before scaffolding begins.

Project Structure
-----------------

A generated project includes:

.. code-block:: text

   myproject/
   ├── manage.py
   ├── pyproject.toml
   ├── justfile
   ├── myproject/
   │   ├── __init__.py
   │   ├── apps.py  (custom app configs with auto-field detection)
   │   ├── settings/
   │   │   ├── __init__.py
   │   │   ├── base.py  (common settings)
   │   │   ├── mongodb.py  (MongoDB-specific settings)
   │   │   ├── postgresql.py  (PostgreSQL-specific settings)
   │   │   └── myproject.py  (main settings, imports from mongodb.py or postgresql.py)
   │   ├── urls.py
   │   ├── wsgi.py
   │   └── migrations/
   │       ├── admin/  (MongoDB-compatible migrations)
   │       ├── auth/  (MongoDB-compatible migrations)
   │       └── contenttypes/  (MongoDB-compatible migrations)
   └── frontend/  (if --add-frontend)
       ├── package.json
       ├── webpack/
       └── src/

Installing Projects
-------------------

Projects can be installed using the standard ``dbx install`` command:

.. code-block:: bash

   # Install a project (automatically finds it in base_dir/projects/)
   dbx install myproject

This will:

1. Install the project's Python dependencies using pip
2. Automatically detect and install frontend npm dependencies if a ``frontend/`` directory with ``package.json`` exists

The ``dbx install`` command now supports frontend installation for both projects and regular repositories. If a ``frontend/`` directory is detected with a ``package.json`` file, npm dependencies will be installed automatically after the Python package installation completes.

Switching Between MongoDB and PostgreSQL
-----------------------------------------

Projects are designed to support both MongoDB and PostgreSQL databases with minimal configuration changes. The database backend is controlled by a single import statement in your project's settings file.

Database-Specific Settings
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Each project includes three settings files in the ``settings/`` directory:

- ``base.py`` - Common Django settings shared by all databases
- ``mongodb.py`` - MongoDB-specific configuration (uses ``ObjectIdAutoField``)
- ``postgresql.py`` - PostgreSQL-specific configuration (uses ``BigAutoField``)
- ``<project_name>.py`` - Main settings file that imports from either ``mongodb.py`` or ``postgresql.py``

Switching Databases
~~~~~~~~~~~~~~~~~~~

To switch between databases, edit ``<project_name>/settings/<project_name>.py``:

**For MongoDB (default):**

.. code-block:: python

   # Database Configuration
   # ----------------------
   # To use MongoDB (default):
   from .mongodb import *  # noqa

   # To use PostgreSQL (uncomment the line below and comment out the MongoDB import above):
   # from .postgresql import *  # noqa

**For PostgreSQL:**

.. code-block:: python

   # Database Configuration
   # ----------------------
   # To use MongoDB (default):
   # from .mongodb import *  # noqa

   # To use PostgreSQL (uncomment the line below and comment out the MongoDB import above):
   from .postgresql import *  # noqa

After switching the import:

1. **Install PostgreSQL dependencies** (if switching to PostgreSQL):

   .. code-block:: bash

      pip install -e ".[postgres]"

2. **Run migrations**:

   .. code-block:: bash

      dbx project migrate <project_name>

The custom app configurations in ``apps.py`` automatically detect which database backend is configured and use the appropriate ``default_auto_field``:

- **MongoDB**: Uses ``django_mongodb_backend.fields.ObjectIdAutoField``
- **PostgreSQL**: Uses ``django.db.models.BigAutoField``

This allows you to switch between databases without modifying any model code or app configurations.

Just Recipes
------------

Each project includes a ``justfile`` with convenient recipes for common development tasks:

.. code-block:: bash

   # Django recipes
   just django-open      # Open http://localhost:8000 in browser (alias: o)
   just django-serve     # Run Django development server
   just django-migrate   # Run Django migrations (alias: m)
   just django-drop      # Drop the project database (alias: d)

   # Python recipes
   just pip-install      # Install project dependencies (alias: i)

   # NPM recipes (if frontend exists)
   just npm-install      # Install frontend dependencies
   just npm-serve        # Run frontend development server

   # Combined recipe
   just serve            # Install and run both frontend and Django servers (alias: s)

The ``django-drop`` recipe uses ``mongosh`` to drop the MongoDB database with the same name as your project. This is useful for resetting your database during development.

Running Projects
----------------

Run a Django project's development server with the ``run`` command:

.. code-block:: bash

   # Run the newest project (no name required)
   dbx project run

   # Run a specific project
   dbx project run myproject

   # Run with custom host and port
   dbx project run myproject --host 0.0.0.0 --port 8080

   # Run with custom MongoDB URI
   dbx project run myproject --mongodb-uri mongodb://localhost:27017

This will:

1. Run ``manage.py migrate`` against the default database
2. Run ``manage.py migrate --database encrypted`` if an ``encrypted`` database is configured (e.g. QE projects)
3. Create a Django superuser (``admin`` / ``admin``) if one does not already exist
4. Start the Django development server using ``manage.py runserver``
5. Automatically start the frontend development server if a ``frontend/`` directory exists
6. Handle graceful shutdown of both servers on CTRL-C

Managing Projects
-----------------

Run Django management commands with the ``manage`` command:

.. code-block:: bash

   # Run shell on the newest project (no name required)
   dbx project manage shell

   # Run migrations on a specific project
   dbx project manage myproject migrate

   # Create migrations
   dbx project manage myproject makemigrations

   # Run with MongoDB URI
   dbx project manage myproject --mongodb-uri mongodb://localhost:27017 shell

Editing Settings
----------------

Open the project's settings files in your default editor with the ``edit`` command:

.. code-block:: bash

   # Open all settings files for the newest project
   dbx project edit

   # Open all settings files for a specific project
   dbx project edit myproject

   # Open a single settings file by name
   dbx project edit myproject --settings base
   dbx project edit myproject -s qe

By default all ``.py`` files in the project's ``settings/`` directory (excluding ``__init__.py``) are opened together in one editor invocation. Pass ``--settings <name>`` to open only that file.

The editor is determined by the ``EDITOR`` environment variable. If ``EDITOR`` is not set, the command falls back to ``vim``, ``nano``, ``vi``, or ``open`` (macOS).

.. code-block:: bash

   # Use VS Code
   EDITOR=code dbx project edit myproject

   # Use a specific settings file
   EDITOR=nano dbx project edit myproject -s qe

Creating Superusers
-------------------

Create a Django superuser with the ``su`` command:

.. code-block:: bash

   # Create superuser on the newest project (no name required)
   dbx project su

   # Create superuser on a specific project
   dbx project su myproject

   # Create with custom credentials
   dbx project su myproject -u admin -p secretpass -e admin@example.com

   # Create with custom MongoDB URI
   dbx project su myproject --mongodb-uri mongodb://localhost:27017

The default username and password are both ``admin``. The email defaults to the ``PROJECT_EMAIL`` environment variable or ``admin@example.com`` if not set.

Running Migrations
------------------

Run Django migrations with the ``migrate`` command:

.. code-block:: bash

   # Run migrations on the newest project (no name required)
   dbx project migrate

   # Run migrations on a specific project
   dbx project migrate myproject

   # Run migrations with custom settings
   dbx project migrate myproject --settings base

   # Run migrations on a specific database
   dbx project migrate myproject --database encrypted

   # Run migrations with custom MongoDB URI
   dbx project migrate myproject --mongodb-uri mongodb://localhost:27017

This is a convenience command that wraps ``django-admin migrate`` with the same environment setup as other project commands.

Removing Projects
-----------------

Remove a project with the ``remove`` command:

.. code-block:: bash

   # Remove the newest project (no name required)
   dbx project remove

   # Remove a specific project
   dbx project remove myproject

   # Remove from custom directory
   dbx project remove myproject -d ~/custom/path

This will:

1. Drop all MongoDB databases associated with the project (reads ``settings.DATABASES`` and drops every database backed by ``django_mongodb_backend``, including the encrypted database for QE projects)
2. Attempt to uninstall the project package from the current Python environment
3. Remove the project directory from the filesystem

Database deletion is non-fatal — if the database cannot be reached the warning is printed and filesystem cleanup proceeds normally.

.. note::

   When using the ``--directory`` flag, you must specify the project name explicitly.

Installing Local Clones
-----------------------

The ``--with`` flag installs one or more local clones (managed by ``dbx clone``) as editable packages into the project venv immediately after project creation:

.. code-block:: bash

   # Install a single local clone
   dbx project add myproject --with medical-records

   # Install multiple local clones
   dbx project add myproject --with django --with django-mongodb-extensions

   # Combine with other flags
   dbx project add myproject --wagtail --with medical-records

Each ``--with`` value is looked up by name using the same discovery logic as ``dbx install`` (respecting group priority from your config). If the clone is not found locally but the repo name appears in your config groups, it is cloned automatically before installation. If it cannot be found or cloned, a warning is printed and that repo is skipped — the project is still created successfully.

This is useful when you want to develop against a local fork or in-progress version of a library rather than the PyPI release. For a dependency already in ``pyproject.toml`` (e.g. ``django-mongodb-extensions``), specifying ``--with`` reinstalls it from the local clone, overriding the PyPI version.

Virtual Environments
--------------------

Projects use a shared virtual environment in the ``projects/`` directory:

.. code-block:: bash

   # Create a virtual environment for all projects
   dbx env init -g projects

   # List all virtual environments
   dbx env list

**Auto-creation**: If no virtual environment is found when ``dbx project add`` runs, one is created automatically at the ``projects/`` group level (``base_dir/projects/.venv``) and Django is bootstrapped into it before project scaffolding begins. You do not need to run ``dbx env init`` manually before your first ``dbx project add``.

**Python version**: The venv is always created using the Python version specified by ``python_version`` in your config (e.g. ``3.13``). If an existing group venv is found but its Python version does not match the configured version, a fresh project-specific venv is created with the correct version instead.

.. note::

   All projects in the ``projects/`` directory share the same virtual environment. If you need full isolation, use the ``--directory`` flag to create projects in separate locations and manage their virtual environments independently.

Configuration
-------------

Projects are created in the directory specified by ``base_dir`` in your configuration file:

.. code-block:: toml

   [repo]
   base_dir = "~/Developer/mongodb"

With this configuration, projects will be created in ``~/Developer/mongodb/projects/``.

Environment Variables
---------------------

Project commands automatically set environment variables from your ``~/.config/dbx-python-cli/config.toml`` file. The default configuration includes:

.. code-block:: toml

   [project.default_env]
   MONGODB_URI = "mongodb://localhost:27017"
   # Set the path to your libmongocrypt build for Queryable Encryption support
   PYMONGOCRYPT_LIB = "~/Developer/mongodb/django/libmongocrypt/cmake-build/libmongocrypt.dylib"  # macOS
   # PYMONGOCRYPT_LIB = "~/Developer/mongodb/django/libmongocrypt/cmake-build/libmongocrypt.so"     # Linux
   # DYLD_LIBRARY_PATH = "~/Developer/mongodb/django/libmongocrypt/cmake-build"  # macOS (alternative)
   # LD_LIBRARY_PATH = "~/Developer/mongodb/django/libmongocrypt/cmake-build"    # Linux (alternative)
   CRYPT_SHARED_LIB_PATH = "~/Downloads/mongo_crypt_shared_v1-macos-arm64-enterprise-8.2.2/lib/mongo_crypt_v1.dylib"  # macOS
   # CRYPT_SHARED_LIB_PATH = "~/Downloads/mongo_crypt_shared_v1-linux-x86_64-enterprise-8.2.2/lib/mongo_crypt_v1.so"     # Linux

These environment variables are automatically used by the ``run``, ``manage``, ``migrate``, and ``su`` commands. You can override them using command-line flags:

.. code-block:: bash

   # Override MongoDB URI
   dbx project run myproject --mongodb-uri mongodb://custom-host:27017

   # Environment variables from config are used if not overridden
   dbx project migrate myproject

Automatic MongoDB Startup
-------------------------

If ``MONGODB_URI`` is not set in your environment or config, the CLI will automatically attempt to start MongoDB using `mongodb-runner <https://www.npmjs.com/package/mongodb-runner>`_.

**How it works:**

1. The CLI first checks for ``MONGODB_URI`` in your environment variables
2. If not found, it checks the ``[project.default_env]`` section in your config file
3. If still not found, it attempts to start MongoDB using ``npx mongodb-runner start``
4. If mongodb-runner succeeds, it uses ``mongodb://localhost:27017`` as the connection URI
5. If mongodb-runner fails (or npx is not available), the command exits with ``no db running``

**Requirements:**

- Node.js and npm must be installed (for ``npx`` command)
- mongodb-runner will automatically download and install the latest stable MongoDB version for your OS/architecture (stored in ``~/.mongodb/``)

**Example output:**

.. code-block:: text

   ⚠️  MONGODB_URI is not set. Attempting to start MongoDB with mongodb-runner...
   🚀 Starting MongoDB with mongodb-runner...
   ✅ MongoDB started successfully with mongodb-runner
   🔗 Using MongoDB URI: mongodb://localhost:27017

**When mongodb-runner fails:**

.. code-block:: text

   ⚠️  MONGODB_URI is not set. Attempting to start MongoDB with mongodb-runner...
   🚀 Starting MongoDB with mongodb-runner...
   ❌ mongodb-runner failed to start: <error message>
   no db running

This feature makes it easy to get started with Django + MongoDB projects without manually configuring a database. Simply run ``dbx project run`` and the CLI will handle the rest.

.. note::

   **Recommended setup:** For production or regular development, set ``MONGODB_URI`` in your config file or environment to avoid the startup delay of mongodb-runner:

   .. code-block:: toml

      [project.default_env]
      MONGODB_URI = "mongodb://localhost:27017"

Settings Configurations
-----------------------

Projects include multiple settings files:

- ``base.py``: Shared base settings
- ``<project_name>.py``: Project-specific settings (default) with commented Queryable Encryption configuration

The default ``DJANGO_SETTINGS_MODULE`` in the generated ``pyproject.toml`` uses the project-specific settings module (``<project_name>.settings.<project_name>``).

Queryable Encryption Support
-----------------------------

Projects include commented configuration for MongoDB Queryable Encryption (QE) in the main settings file. To enable QE:

1. **Uncomment the QE database configuration** in ``<project_name>/settings/<project_name>.py``:

   .. code-block:: python

      DATABASES = {
          "default": {
              "ENGINE": "django_mongodb_backend",
              "NAME": "<project_name>",
              "CLIENT": {
                  "host": os.getenv("MONGODB_URI", "mongodb://localhost:27017"),
                  "auto_encryption_opts": AutoEncryptionOpts(
                      key_vault_namespace="<project_name>_encrypted.__keyVault",
                      kms_providers={
                          "local": {
                              "key": b"..."  # 96-byte key included in template
                          },
                      },
                      crypt_shared_lib_path=os.getenv("CRYPT_SHARED_LIB_PATH"),
                      crypt_shared_lib_required=True,
                  )
              },
          },
          # Optional: separate database for encrypted data
          "encrypted": {
              "ENGINE": "django_mongodb_backend",
              "NAME": "<project_name>_encrypted",
              "CLIENT": {
                  "host": os.getenv("MONGODB_URI", "mongodb://localhost:27017"),
              },
          },
      }

2. **Uncomment the medical_records app** (if using the QE demo):

   .. code-block:: python

      INSTALLED_APPS = (
          INSTALLED_APPS
          + [
              "medical_records",  # Uncomment for QE demo
          ]
      )

3. **Ensure environment variables are set** in your ``~/.config/dbx-python-cli/config.toml``:

   - ``PYMONGOCRYPT_LIB``: Path to the libmongocrypt shared library
   - ``CRYPT_SHARED_LIB_PATH``: Path to the MongoDB Automatic Encryption Shared Library
   - ``MONGODB_URI``: MongoDB connection string (defaults to ``mongodb://localhost:27017``)

4. **Build libmongocrypt** (if not already built):

   .. code-block:: bash

      # Install libmongocrypt (includes cmake build step)
      dbx install libmongocrypt

The ``dbx install`` command will automatically run the cmake build commands configured in ``config.toml`` to build the libmongocrypt C library.

.. note::

   **Queryable Encryption Requirements:**

   - MongoDB 7.0+ (replica set or sharded cluster)
   - libmongocrypt C library (built via ``dbx install libmongocrypt``)
   - MongoDB Automatic Encryption Shared Library (download from MongoDB)
   - pymongocrypt Python package (installed automatically with django-mongodb-backend)
