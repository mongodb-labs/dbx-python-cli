Documentation Commands
======================

Manage and view documentation for repositories.

Listing Repositories with Documentation
---------------------------------------

List all cloned repositories that have documentation:

.. code-block:: bash

   dbx docs list

This will show repositories that have a ``docs/`` or ``doc/`` directory with
Sphinx configuration (``conf.py``).

Example Output
~~~~~~~~~~~~~~

.. code-block:: bash

   $ dbx docs list
   Repositories with documentation:

     pymongo:
       • mongo-python-driver
       • specifications

   2 repositories with documentation

   Run 'dbx docs build <repo_name>' to build docs locally
   Run 'dbx docs open <repo_name>' to open built docs

Building Documentation
----------------------

Build Sphinx documentation for a repository:

.. code-block:: bash

   dbx docs build mongo-python-driver

This runs Sphinx to build HTML documentation. The output will be in
``<repo>/docs/_build/html/``.

Example Output
~~~~~~~~~~~~~~

.. code-block:: bash

   $ dbx docs build mongo-python-driver
   📖 Building documentation for mongo-python-driver...
      Docs directory: ~/Developer/dbx-repos/pymongo/mongo-python-driver/docs

   Running Sphinx v8.0.2
   ...

   ✅ Documentation built successfully!
      Output: ~/Developer/dbx-repos/pymongo/mongo-python-driver/docs/_build/html

   Run 'dbx docs open mongo-python-driver' to view the docs

Opening Documentation
---------------------

Open documentation in a web browser:

.. code-block:: bash

   # Open dbx documentation on Read the Docs
   dbx docs open

   # Open locally built documentation for a repository
   dbx docs open mongo-python-driver

For local documentation, you must build the docs first with ``dbx docs build``.

Example Output
~~~~~~~~~~~~~~

.. code-block:: bash

   $ dbx docs open
   📖 Opening dbx docs: https://dbx-python-cli.readthedocs.io/

   $ dbx docs open mongo-python-driver
   📖 Opening docs for mongo-python-driver: file:///.../_build/html/index.html

Requirements
------------

- For ``dbx docs list`` and ``dbx docs build``: Repositories must have a ``docs/``
  or ``doc/`` directory with a ``conf.py`` (Sphinx configuration)
- For ``dbx docs build``: Sphinx must be installed (typically in the repository's
  virtual environment)
- For ``dbx docs open <repo>``: Documentation must be built first

Typical Workflow
----------------

.. code-block:: bash

   # See which repos have documentation
   dbx docs list

   # Build docs for a repository
   dbx docs build mongo-python-driver

   # View the built documentation
   dbx docs open mongo-python-driver
