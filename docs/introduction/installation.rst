Installation
============

This guide covers installing drivers-python-cli on your system.

Prerequisites
-------------

Before installing drivers-python-cli, you'll need:

- **Python 3.11 or higher**
- **pipx** - Install Python applications in isolated environments

Installing pipx
~~~~~~~~~~~~~~~

If you don't have pipx installed, install it first:

**macOS:**

.. code-block:: bash

   brew install pipx
   pipx ensurepath

**Linux:**

.. code-block:: bash

   pip install pipx
   pipx ensurepath

**Windows:**

.. code-block:: bash

   pip install pipx
   pipx ensurepath

For more installation options, see the `pipx documentation <https://pipx.pypa.io/>`_.

Installing drivers-python-cli
-----------------------------

Via pipx (Recommended)
~~~~~~~~~~~~~~~~~~~~~~~

The recommended way to install drivers-python-cli is using ``pipx install``:

.. code-block:: bash

   # Install directly from GitHub
   pipx install git+https://github.com/aclark4life/drivers-python-cli.git

This will:

- Install drivers-python-cli in an isolated environment
- Make the ``dpy`` command available globally in your terminal
- Keep the tool separate from your project dependencies

Verify Installation
~~~~~~~~~~~~~~~~~~~

After installation, verify that the ``dpy`` command is available:

.. code-block:: bash

   dpy --help

You should see the help message with available commands.

Updating
--------

To update drivers-python-cli to the latest version:

.. code-block:: bash

   pipx upgrade drivers-python-cli

Or to reinstall a specific version:

.. code-block:: bash

   pipx install --force git+https://github.com/aclark4life/drivers-python-cli.git@<version>

Uninstalling
------------

To uninstall drivers-python-cli:

.. code-block:: bash

   pipx uninstall drivers-python-cli

Next Steps
----------

After installation, proceed to the :doc:`quick-start` guide to set up your first project.
