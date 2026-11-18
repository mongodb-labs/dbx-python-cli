Documentation Commands
======================

Manage and view documentation for repositories.

Listing Repositories with Documentation
---------------------------------------

List all cloned repositories that have documentation:

.. code-block:: bash

   dpy docs list

This will show repositories that have a ``docs/`` or ``doc/`` directory with
Sphinx configuration (``conf.py``).

Example Output
~~~~~~~~~~~~~~

.. code-block:: bash

   $ dpy docs list
   Repositories with documentation:

     pymongo:
       • mongo-python-driver
       • specifications

   2 repositories with documentation

   Run 'dpy docs build <repo_name>' to build docs locally
   Run 'dpy docs open <repo_name>' to open built docs

Building Documentation
----------------------

Build Sphinx documentation for a repository:

.. code-block:: bash

   dpy docs build mongo-python-driver

This runs Sphinx to build HTML documentation. The output will be in
``<repo>/docs/_build/html/``.

Example Output
~~~~~~~~~~~~~~

.. code-block:: bash

   $ dpy docs build mongo-python-driver
   📖 Building documentation for mongo-python-driver...
      Docs directory: ~/Developer/dpy-repos/pymongo/mongo-python-driver/docs

   Running Sphinx v8.0.2
   ...

   ✅ Documentation built successfully!
      Output: ~/Developer/dpy-repos/pymongo/mongo-python-driver/docs/_build/html

   Run 'dpy docs open mongo-python-driver' to view the docs

Opening Documentation
---------------------

Open documentation in a web browser:

.. code-block:: bash

   # Open dpy documentation on Read the Docs
   dpy docs open

   # Open locally built documentation for a repository
   dpy docs open mongo-python-driver

For local documentation, you must build the docs first with ``dpy docs build``.

Example Output
~~~~~~~~~~~~~~

.. code-block:: bash

   $ dpy docs open
   📖 Opening dpy docs: https://drivers-python-cli.readthedocs.io/

   $ dpy docs open mongo-python-driver
   📖 Opening docs for mongo-python-driver: file:///.../_build/html/index.html

Requirements
------------

- For ``dpy docs list`` and ``dpy docs build``: Repositories must have a ``docs/``
  or ``doc/`` directory with a ``conf.py`` (Sphinx configuration)
- For ``dpy docs build``: Sphinx must be installed (typically in the repository's
  virtual environment)
- For ``dpy docs open <repo>``: Documentation must be built first

Typical Workflow
----------------

.. code-block:: bash

   # See which repos have documentation
   dpy docs list

   # Build docs for a repository
   dpy docs build mongo-python-driver

   # View the built documentation
   dpy docs open mongo-python-driver
