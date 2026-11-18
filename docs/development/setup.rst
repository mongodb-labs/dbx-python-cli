Setup
=====

This guide covers setting up your development environment for drivers-python-cli.

Prerequisites
-------------

- Python 3.10 or higher
- `uv <https://github.com/astral-sh/uv>`_ - Ultra-fast Python package installer
- `just <https://github.com/casey/just>`_ - Command runner (optional but recommended)
- Git

Installing uv
~~~~~~~~~~~~~

.. code-block:: bash

   # macOS/Linux
   curl -LsSf https://astral.sh/uv/install.sh | sh

   # Windows
   powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

Installing just
~~~~~~~~~~~~~~~

.. code-block:: bash

   # macOS
   brew install just

   # Linux
   cargo install just

   # Or download from https://github.com/casey/just/releases

Clone the Repository
--------------------

.. code-block:: bash

   git clone https://github.com/aclark4life/drivers-python-cli.git
   cd drivers-python-cli

Install the Package
-------------------

Using just (Recommended)
~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   # Install the package in editable mode
   just install

   # Install with development dependencies
   just install-dev

   # Install documentation dependencies
   just install-docs

   # Install testing dependencies
   just install-test

Using uv Directly
~~~~~~~~~~~~~~~~~

.. code-block:: bash

   # Install the package in editable mode
   uv pip install -e .

   # Install with development dependencies
   uv pip install -e ".[dev]"

   # Install with specific dependency groups
   uv pip install -e ".[docs]"  # Documentation dependencies
   uv pip install -e ".[test]"  # Testing dependencies

Install Pre-commit Hooks
------------------------

.. code-block:: bash

   # Using just
   just install-hooks

   # Or manually
   pre-commit install

The pre-commit hooks will run automatically on every commit and check:

- Trailing whitespace
- End of files
- YAML/TOML syntax
- Large files
- Merge conflicts
- Line endings
- Code formatting (ruff)

Verify Installation
-------------------

.. code-block:: bash

   # Check that dpy is installed
   dpy --version

   # Run tests to verify everything works
   just test

   # Build documentation
   just docs
