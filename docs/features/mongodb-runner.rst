MongoDB Integration
===================

dbx-python-cli can automatically start MongoDB when needed, making it easy to get started with MongoDB projects without manually installing or configuring MongoDB.

Three backends are supported:

- **mongodb-runner** (default): Uses `mongodb-runner <https://www.npmjs.com/package/mongodb-runner>`_ to download and run MongoDB (Community or Enterprise)
- **docker**: Uses Docker to run official MongoDB images (Community or Enterprise)
- **atlas-local**: Uses Docker to run `MongoDB Atlas Local <https://hub.docker.com/r/mongodb/mongodb-atlas-local>`_ with Atlas Search and Vector Search support

How It Works
------------

When you run commands that require MongoDB (``project run``, ``project manage``, ``project migrate``, ``project su``), the CLI checks for a MongoDB connection in this order:

1. **Environment variable**: Uses ``MONGODB_URI`` if set in your shell environment
2. **Config file**: Uses ``MONGODB_URI`` from ``~/.config/dbx-python-cli/config.toml``
3. **Configured backend**: Uses mongodb-runner, docker, or atlas-local based on ``[project.mongodb] backend`` setting
4. **Exit**: If all above fail, exits with ``no db running``

This means if you run ``dbx project run`` in one terminal and then ``dbx project migrate`` in another, both will use the same MongoDB instance.

Choosing an Edition
-------------------

For **mongodb-runner** and **docker** backends, you can choose between Community and Enterprise editions:

- **Community Edition** (default): Free, open-source MongoDB
- **Enterprise Edition**: Includes additional enterprise features (requires license)

Set the edition in ``~/.config/dbx-python-cli/config.toml``:

.. code-block:: toml

   [project.mongodb]
   edition = "community"  # or "enterprise"

Or use the ``--edition`` CLI flag to override for a single command:

.. code-block:: bash

   dbx --edition enterprise project run myproject

CLI Flags (Quick Override)
---------------------------

You can override the backend and edition without editing the config file using global CLI flags:

.. code-block:: bash

   # Use Atlas Local for this run only
   dbx --backend atlas-local project run myproject

   # Use Docker with Enterprise edition
   dbx --backend docker --edition enterprise project run myproject

   # Use mongodb-runner with Enterprise edition
   dbx --edition enterprise project run myproject

**Available flags:**

- ``--backend``: Choose ``mongodb-runner``, ``docker``, or ``atlas-local``
- ``--edition``: Choose ``community`` or ``enterprise`` (for mongodb-runner and docker only)

These flags work with all project commands: ``run``, ``manage``, ``migrate``, ``su``

.. note::

   CLI flags take precedence over config file settings, making it easy to test different backends without changing your configuration.

Backend 1: mongodb-runner (Default)
------------------------------------

Requirements
~~~~~~~~~~~~

To use mongodb-runner:

- **Node.js and npm** must be installed (for the ``npx`` command)
- mongodb-runner will automatically download MongoDB for your OS/architecture
- Downloaded MongoDB binaries are cached in ``~/.mongodb/``

Configuration
~~~~~~~~~~~~~

mongodb-runner is the default backend. To explicitly configure it:

.. code-block:: toml

   [project.mongodb]
   backend = "mongodb-runner"
   edition = "community"  # or "enterprise"

   [project.mongodb.mongodb_runner]
   topology = "standalone"  # or "replset" or "sharded"
   # Optional: additional options to pass to mongodb-runner
   # options = []

Usage
~~~~~

Simply run your project without setting ``MONGODB_URI``:

.. code-block:: bash

   # MongoDB Community will be started automatically (default)
   dbx project run myproject

Example output when mongodb-runner starts:

.. code-block:: text

   ⚠️  MONGODB_URI is not set. Checking for mongodb-runner (Community)...
   🚀 Starting MongoDB Community with mongodb-runner...
   ✅ MongoDB started successfully with mongodb-runner
   🔗 Using MongoDB URI: mongodb://127.0.0.1:52065

Enterprise Edition
~~~~~~~~~~~~~~~~~~

To use MongoDB Enterprise with mongodb-runner:

.. code-block:: toml

   [project.mongodb]
   backend = "mongodb-runner"
   edition = "enterprise"

Example output:

.. code-block:: text

   ⚠️  MONGODB_URI is not set. Checking for mongodb-runner (Enterprise)...
   🚀 Starting MongoDB Enterprise with mongodb-runner...
   ✅ MongoDB started successfully with mongodb-runner
   🔗 Using MongoDB URI: mongodb://127.0.0.1:52065

.. note::

   mongodb-runner uses a **random port** each time it starts. The CLI automatically parses the actual URI from the output and uses it for your Django application.

Topology Configuration
~~~~~~~~~~~~~~~~~~~~~~~

mongodb-runner supports three topology types:

- **standalone** (default): Single MongoDB instance
- **replset**: Replica set with configurable number of secondaries and arbiters
- **sharded**: Sharded cluster with configurable number of shards and secondaries

**Replica Set Example:**

.. code-block:: toml

   [project.mongodb.mongodb_runner]
   topology = "replset"
   secondaries = 2  # Number of secondary nodes
   arbiters = 0     # Number of arbiter nodes

**Sharded Cluster Example:**

.. code-block:: toml

   [project.mongodb.mongodb_runner]
   topology = "sharded"
   shards = 2        # Number of shards
   secondaries = 1   # Number of secondaries per replica set

Example output when starting a replica set:

.. code-block:: text

   ⚠️  MONGODB_URI is not set. Checking for mongodb-runner (Community, Replset)...
   🚀 Starting MongoDB Community (Replset) with mongodb-runner...
   ✅ MongoDB started successfully with mongodb-runner
   🔗 Using MongoDB URI: mongodb://127.0.0.1:52065

Stopping mongodb-runner
~~~~~~~~~~~~~~~~~~~~~~~

mongodb-runner instances started by dbx are managed separately. To stop all mongodb-runner instances:

.. code-block:: bash

   npx mongodb-runner stop --all

Or stop a specific instance using the ID shown in the output:

.. code-block:: bash

   npx mongodb-runner stop --id=<instance-id>

Specifying MongoDB Version
~~~~~~~~~~~~~~~~~~~~~~~~~~~

mongodb-runner uses the latest stable MongoDB version by default. To use a specific version, set the ``MONGODB_VERSION`` environment variable before running:

.. code-block:: bash

   MONGODB_VERSION=7.0.0 dbx project run myproject
   MONGODB_VERSION=^6.0.0 dbx project run myproject  # Latest 6.x

Backend 2: Docker
-----------------

Use official MongoDB Docker images for a containerized MongoDB instance.

Requirements
~~~~~~~~~~~~

To use Docker backend:

- **Docker** must be installed and running
- MongoDB Docker images will be pulled automatically

Configuration
~~~~~~~~~~~~~

To enable Docker backend, edit ``~/.config/dbx-python-cli/config.toml``:

.. code-block:: toml

   [project.mongodb]
   backend = "docker"
   edition = "community"  # or "enterprise"

   [project.mongodb.docker]
   # Optional: override default image
   # image = "mongo"  # Use Docker Official Image instead
   tag = "latest"  # or "8.0", "7.0", etc.
   container_name = "dbx-mongodb"
   port = 27017

Available Images
~~~~~~~~~~~~~~~~

**Community Edition** (``edition = "community"``):

- ``mongodb/mongodb-community-server`` (default) - Official MongoDB Community image
- ``mongo`` - Docker Official Image (alternative)

**Enterprise Edition** (``edition = "enterprise"``):

- ``mongodb/mongodb-enterprise-server`` (default) - Official MongoDB Enterprise image

Usage
~~~~~

Once configured, run your project as normal:

.. code-block:: bash

   # MongoDB will be started automatically
   dbx project run myproject

Example output when Docker starts:

.. code-block:: text

   ⚠️  MONGODB_URI is not set. Checking for Docker MongoDB (Community)...
   🚀 Starting new Docker MongoDB container with image: mongodb/mongodb-community-server:latest...
   ⏳ Waiting for MongoDB to start...
   ✅ Docker MongoDB Community started successfully
   🔗 Using MongoDB URI: mongodb://localhost:27017

Enterprise Edition
~~~~~~~~~~~~~~~~~~

To use MongoDB Enterprise with Docker:

.. code-block:: toml

   [project.mongodb]
   backend = "docker"
   edition = "enterprise"

Example output:

.. code-block:: text

   ⚠️  MONGODB_URI is not set. Checking for Docker MongoDB (Enterprise)...
   🚀 Starting new Docker MongoDB container with image: mongodb/mongodb-enterprise-server:latest...
   ⏳ Waiting for MongoDB to start...
   ✅ Docker MongoDB Enterprise started successfully
   🔗 Using MongoDB URI: mongodb://localhost:27017

Replica Set Configuration
~~~~~~~~~~~~~~~~~~~~~~~~~~

To run Docker MongoDB as a replica set instead of standalone:

.. code-block:: toml

   [project.mongodb.docker]
   replset = "rs0"  # Replica set name

When configured as a replica set, the CLI will automatically:

1. Start MongoDB with the ``--replSet`` flag
2. Initialize the replica set with ``rs.initiate()``
3. Include the replica set name in the connection URI

Example output when starting a replica set:

.. code-block:: text

   ⚠️  MONGODB_URI is not set. Checking for Docker MongoDB (Community, Replica Set)...
   🚀 Starting new Docker MongoDB container with image: mongodb/mongodb-community-server:latest...
   ⏳ Waiting for MongoDB to start...
   ⏳ Initializing replica set 'rs0'...
   ✅ Replica set 'rs0' initialized successfully
   ✅ Docker MongoDB Community (Replica Set) started successfully
   🔗 Using MongoDB URI: mongodb://localhost:27017/?replicaSet=rs0

.. note::

   Docker backend only supports single-node replica sets. For multi-node replica sets or sharded clusters, use the mongodb-runner backend.

Stopping Docker MongoDB
~~~~~~~~~~~~~~~~~~~~~~~~

To stop the Docker container:

.. code-block:: bash

   docker stop dbx-mongodb

To remove the container:

.. code-block:: bash

   docker rm dbx-mongodb

Advanced Configuration
~~~~~~~~~~~~~~~~~~~~~~~

You can customize the Docker run options in your config:

.. code-block:: toml

   [project.mongodb.docker]
   image = "mongo"  # Use Docker Official Image
   tag = "8.0"
   container_name = "my-mongodb"
   port = 27017
   docker_options = ["--rm"]  # Auto-remove container on stop

Backend 3: Atlas Local
----------------------

MongoDB Atlas Local provides a full deployment of MongoDB with Atlas Search and Atlas Vector Search support via Docker.

Requirements
~~~~~~~~~~~~

To use Atlas Local:

- **Docker** must be installed and running
- The ``mongodb/mongodb-atlas-local`` Docker image will be pulled automatically

Configuration
~~~~~~~~~~~~~

To enable Atlas Local, edit ``~/.config/dbx-python-cli/config.toml``:

.. code-block:: toml

   [project.mongodb]
   backend = "atlas-local"

   [project.mongodb.atlas_local]
   image = "mongodb/mongodb-atlas-local"
   tag = "latest"  # or "8.0", "7.0", or specific version
   container_name = "dbx-atlas-local"
   port = 27017

Usage
~~~~~

Once configured, run your project as normal:

.. code-block:: bash

   # MongoDB Atlas Local will be started automatically
   dbx project run myproject

Example output when Atlas Local starts:

.. code-block:: text

   ⚠️  MONGODB_URI is not set. Checking for Atlas Local...
   🚀 Starting new Atlas Local container with image: mongodb/mongodb-atlas-local:latest...
   ⏳ Waiting for Atlas Local to become healthy...
   ✅ Atlas Local started successfully
   🔗 Using MongoDB URI: mongodb://localhost:27017/?directConnection=true

Features Available with Atlas Local
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

When using Atlas Local, you get access to:

- **Atlas Search**: Full-text search capabilities
- **Atlas Vector Search**: Vector similarity search for AI/ML applications
- **Single-node replica set**: Supports change streams and transactions
- **Auto-embedding**: Automatic vector embedding (preview tag only)

.. note::

   Atlas Local runs as a single-node replica set with an internal hostname. The CLI automatically adds ``directConnection=true`` to the connection URI to bypass replica set discovery and ensure proper connectivity.

See the `Atlas Local documentation <https://www.mongodb.com/docs/atlas/cli/current/atlas-cli-deploy-docker/>`_ for more details.

Stopping Atlas Local
~~~~~~~~~~~~~~~~~~~~

To stop the Atlas Local container:

.. code-block:: bash

   docker stop dbx-atlas-local

To remove the container:

.. code-block:: bash

   docker rm dbx-atlas-local

Advanced Configuration
~~~~~~~~~~~~~~~~~~~~~~~

You can customize the Docker run options in your config:

.. code-block:: toml

   [project.mongodb.atlas_local]
   image = "mongodb/mongodb-atlas-local"
   tag = "8.0"
   container_name = "my-atlas-local"
   port = 27017
   docker_options = ["--rm"]  # Auto-remove container on stop

Manual MongoDB Configuration
----------------------------

For regular development, you may want to use a manually managed MongoDB instance. You have several options:

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
-------------------------------

If you prefer to install MongoDB permanently:

- **macOS**: ``brew install mongodb-community``
- **Ubuntu/Debian**: Follow the `MongoDB installation guide <https://www.mongodb.com/docs/manual/administration/install-on-linux/>`_
- **Docker**: ``docker run -d -p 27017:27017 mongo``

Then set ``MONGODB_URI`` in your config file to use your permanent installation.
