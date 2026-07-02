Testing
=======

Run Tests in Repositories
--------------------------

Run tests in any cloned repository using pytest (default) or a custom test runner:

.. code-block:: bash

   # Run tests in a specific repository
   dbx test mongo-python-driver

   # Run tests matching a keyword expression (pytest only)
   dbx test mongo-python-driver --keyword "test_connection"

   # Pass additional arguments to the test runner
   dbx test mongo-python-driver -x --tb=short

   # Short forms
   dbx test mongo-python-driver -k "test_auth"  # filter tests

The ``test`` command will:

1. Find the repository by name across all cloned groups
2. Run the configured test runner (pytest by default, or custom runner if configured)
3. Pass any additional arguments to the test runner
4. Display the test results

Example Output
--------------

.. code-block:: bash

   $ dbx test mongo-python-driver
   Running pytest in ~/Developer/dbx-repos/pymongo/mongo-python-driver...

   ============================= test session starts ==============================
   ...
   ✅ Tests passed in mongo-python-driver

Filter Tests by Keyword
-----------------------

The ``-k`` / ``--keyword`` flag passes a keyword expression to pytest's ``-k`` option to filter which tests to run. This is useful for:

- Running only tests matching a specific pattern (e.g., ``-k "test_connection"``)
- Running tests from a specific class (e.g., ``-k "TestAuth"``)
- Using boolean expressions (e.g., ``-k "test_auth and not test_slow"``)

The keyword expression is passed directly to pytest, so all pytest ``-k`` syntax is supported.

**Note:** The ``-k`` / ``--keyword`` flag only works with pytest. For custom test runners, pass filtering arguments directly as additional arguments.

Pass Additional Arguments
-------------------------

You can pass additional arguments to the test runner by adding them after the repository name:

.. code-block:: bash

   # Pass pytest arguments
   dbx test mongo-python-driver -x --tb=short --maxfail=1

   # Pass arguments to custom test runner
   dbx test django --verbose --parallel

Arguments are passed directly to the test runner, so you can use any arguments supported by pytest or your custom test runner.

Custom Test Runners
-------------------

By default, ``dbx test`` uses pytest. However, some projects use custom test runners (e.g., Django's ``tests/runtests.py``). You can configure a custom test runner in your config file:

.. code-block:: toml

   [repo.groups.django]
   repos = [
       "git@github.com:django/django.git",
   ]

   # Specify custom test runner (path relative to repo root)
   [repo.groups.django.test_runner]
   django = "tests/runtests.py"

When a custom test runner is configured:

- The test command runs the custom script instead of pytest
- Additional arguments are passed directly to the custom runner
- The ``-k`` / ``--keyword`` flag is not supported (use additional arguments instead)

Example with custom test runner:

.. code-block:: bash

   # Run Django's custom test runner with arguments
   dbx test django --verbose --parallel

   # This executes: python tests/runtests.py --verbose --parallel

Environment Variables
---------------------

You can configure environment variables to be set when running tests or just commands. This is useful for setting paths to tools, test configuration, or other environment-specific settings.

Configure environment variables in your config file:

.. code-block:: toml

   [repo.groups.pymongo]
   repos = [
       "git@github.com:mongodb/mongo-python-driver.git",
       "git@github.com:mongodb-labs/drivers-evergreen-tools.git",
   ]

   # Environment variables for test runs
   [repo.groups.pymongo.test_env]
   mongo-python-driver = { DRIVERS_TOOLS = "{base_dir}/{group}/drivers-evergreen-tools" }

Supported placeholders in environment variable values:

- ``{base_dir}`` - Expands to the base directory path (e.g., ``~/Developer/mongodb``)
- ``{group}`` - Expands to the group name (e.g., ``pymongo``)
- ``~`` - Expands to the user's home directory

You can set multiple environment variables for a repository:

.. code-block:: toml

   [repo.groups.pymongo.test_env]
   mongo-python-driver = { DRIVERS_TOOLS = "{base_dir}/{group}/drivers-evergreen-tools", TEST_MODE = "integration", CUSTOM_PATH = "~/my/custom/path" }

When you run tests or just commands, these environment variables will be automatically set:

.. code-block:: bash

   # Run tests with configured environment variables
   dbx test mongo-python-driver

   # Run just commands with configured environment variables
   dbx just mongo-python-driver setup-tests

   # View environment variables in verbose mode
   dbx --verbose test mongo-python-driver
   dbx --verbose just mongo-python-driver setup-tests

The environment variables are merged with your current environment, so existing environment variables are preserved unless explicitly overridden by the configuration.

.. note::
   Environment variables configured under ``test_env`` are used by both the ``test`` and ``just`` commands.

Requirements
------------

- The repository must be cloned first using ``dbx clone``
- For pytest (default): pytest must be installed in the repository's virtual environment
- For custom test runners: the test runner script must exist at the configured path
