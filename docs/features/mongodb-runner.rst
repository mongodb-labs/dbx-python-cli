MongoDB Runner Integration
==========================

dbx-python-cli integrates with `mongodb-runner <https://www.npmjs.com/package/mongodb-runner>`_ to automatically start MongoDB when needed. This makes it easy to get started with MongoDB projects without manually installing or configuring MongoDB.

How It Works
------------

When you run commands that require MongoDB (``project run``, ``project manage``, ``project migrate``, ``project su``), the CLI checks for a MongoDB connection in this order:

1. **Environment variable**: Uses ``MONGODB_URI`` if set in your shell environment
2. **Config file**: Uses ``MONGODB_URI`` from ``~/.config/dbx-python-cli/config.toml``
3. **mongodb-runner**: Automatically starts MongoDB using ``npx mongodb-runner start``
4. **Exit**: If all above fail, exits with ``no db running``

Requirements
------------

To use the automatic MongoDB startup feature:

- **Node.js and npm** must be installed (for the ``npx`` command)
- mongodb-runner will automatically download the latest stable MongoDB version for your OS/architecture
- Downloaded MongoDB binaries are cached in ``~/.mongodb/``

Usage
-----

Simply run your project without setting ``MONGODB_URI``:

.. code-block:: bash

   # MongoDB will be started automatically
   dbx project run myproject

Example output when mongodb-runner starts:

.. code-block:: text

   ⚠️  MONGODB_URI is not set. Attempting to start MongoDB with mongodb-runner...
   🚀 Starting MongoDB with mongodb-runner...
   ✅ MongoDB started successfully with mongodb-runner
   🔗 Using MongoDB URI: mongodb://127.0.0.1:52065

.. note::

   mongodb-runner uses a **random port** each time it starts. The CLI automatically parses the actual URI from the output and uses it for your Django application.

When mongodb-runner Fails
-------------------------

If mongodb-runner fails to start (e.g., npx not installed, download fails, or MongoDB can't start), the CLI exits with an error:

.. code-block:: text

   ⚠️  MONGODB_URI is not set. Attempting to start MongoDB with mongodb-runner...
   🚀 Starting MongoDB with mongodb-runner...
   ❌ mongodb-runner failed to start: <error message>
   no db running

Configuring a Persistent MongoDB
--------------------------------

For regular development, you may want to run MongoDB permanently instead of using mongodb-runner each time. You have several options:

**Option 1: Set MONGODB_URI in config**

Add to ``~/.config/dbx-python-cli/config.toml``:

.. code-block:: toml

   [project.default_env]
   MONGODB_URI = "mongodb://localhost:27017"

**Option 2: Set environment variable**

.. code-block:: bash

   export MONGODB_URI="mongodb://localhost:27017"

**Option 3: Use the --mongodb-uri flag**

.. code-block:: bash

   dbx project run myproject --mongodb-uri mongodb://localhost:27017

Installing MongoDB Permanently
------------------------------

If you prefer to install MongoDB permanently:

- **macOS**: ``brew install mongodb-community``
- **Ubuntu/Debian**: Follow the `MongoDB installation guide <https://www.mongodb.com/docs/manual/administration/install-on-linux/>`_
- **Docker**: ``docker run -d -p 27017:27017 mongo``

Then set ``MONGODB_URI`` in your config file to use your permanent installation.

Stopping mongodb-runner
-----------------------

mongodb-runner instances started by dbx are managed separately. To stop all mongodb-runner instances:

.. code-block:: bash

   npx mongodb-runner stop --all

Or stop a specific instance using the ID shown in the output:

.. code-block:: bash

   npx mongodb-runner stop --id=<instance-id>

Specifying MongoDB Version
--------------------------

mongodb-runner uses the latest stable MongoDB version by default. To use a specific version, set the ``MONGODB_VERSION`` environment variable before running:

.. code-block:: bash

   MONGODB_VERSION=7.0.0 dbx project run myproject
   MONGODB_VERSION=^6.0.0 dbx project run myproject  # Latest 6.x
