drivers-python-cli Documentation
================================

A command line tool for Drivers Python development tasks.

**Get started:** :doc:`introduction/installation` | :doc:`introduction/quick-start` | :doc:`introduction/overview`

What is drivers-python-cli?
---------------------------

drivers-python-cli is a unified command-line interface for managing Python development workflows across multiple related repositories. It provides tools for:

- 📦 **Repository Management** - Clone, sync, and organize related repositories
- 🐍 **Virtual Environments** - Group-level venvs with smart detection
- ⚡ **Fast Installation** - Dependency management powered by uv
- ✅ **Testing** - Run tests across repositories with consistent commands
- 🔧 **Task Automation** - Execute just commands and custom workflows

Feature Highlights
------------------

- 🤖 **AI-First Design** - Built with AI-assisted development workflows in mind
- 🔧 **Modern Tooling** - Uses the latest Python development tools and best practices
- 📦 **Fast Package Management** - Powered by `uv <https://github.com/astral-sh/uv>`_
- ✨ **Quality Focused** - Pre-commit hooks with `prek <https://github.com/aclark4life/prek>`_ and `ruff <https://github.com/astral-sh/ruff>`_
- 📚 **Well Documented** - Sphinx documentation with the beautiful Furo theme
- ✅ **Fully Tested** - Comprehensive test suite with pytest and coverage reporting

Quick Start
-----------

Install drivers-python-cli and get started in minutes:

.. code-block:: bash

   # Install via pipx
   pipx install git+https://github.com/aclark4life/drivers-python-cli.git

   # Initialize configuration
   dpy config init

   # Clone repositories by group (installs automatically)
   dpy clone -g django

   # Run tests
   dpy test django

See :doc:`introduction/quick-start` for a detailed walkthrough.

Documentation Sections
----------------------

.. toctree::
   :maxdepth: 2

   introduction/index
   features/index
   design/index
   api/index
   development/index

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
