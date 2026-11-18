About
=====

What is drivers-python-cli?
---------------------------

**drivers-python-cli** is a command line tool designed for Drivers Python development tasks. It provides a unified interface for managing repositories, virtual environments, dependencies, and testing workflows.

The tool is built with an **AI-first** philosophy, making it easy to work with AI assistants and modern development workflows. It emphasizes automation, consistency, and developer productivity.

What is Drivers Python?
-----------------------

**Drivers Python** is the MongoDB Database Experience Team for the MongoDB Python driver. The team works on:

- `PyMongo <https://github.com/mongodb/mongo-python-driver>`_ - The official MongoDB driver for Python
- MongoDB integrations with Python frameworks and tools
- Developer experience improvements for Python developers using MongoDB

.. note::
   This is not `Databricks for Python developers <https://docs.databricks.com/aws/en/languages/python>`__.

.. raw:: html

   <script>
   document.addEventListener('DOMContentLoaded', function() {
       var links = document.querySelectorAll('a[href="https://docs.databricks.com/aws/en/languages/python"]');
       links.forEach(function(link) {
           link.setAttribute('target', '_blank');
           link.setAttribute('rel', 'noopener noreferrer');
       });
   });
   </script>

Why drivers-python-cli?
-----------------------

The tool was created to solve common pain points in managing multiple related repositories:

**De-siloing Development**
   Work across multiple repositories seamlessly without context switching between different tools and workflows.

**Consistency**
   Ensure consistent development environments, dependency management, and testing across all repositories.

**Automation**
   Automate repetitive tasks like cloning repositories, setting up virtual environments, and running tests.

**AI-First Design**
   Built with AI-assisted development in mind, making it easy to describe what you want to accomplish and let the tool handle the details.

Inspiration
-----------

drivers-python-cli is inspired by `django-mongodb-cli <https://github.com/mongodb-labs/django-mongodb-cli>`_, which provides similar functionality for Django and MongoDB development.

Key Principles
--------------

**Standalone Tool**
   Installed globally via ``pipx install``, not tied to any specific repository or workspace.

**Modern Tooling**
   Uses the latest Python development tools:

   - `uv <https://github.com/astral-sh/uv>`_ for fast package management
   - `just <https://github.com/casey/just>`_ for task automation
   - `prek <https://github.com/aclark4life/prek>`_ for pre-commit hook management
   - `ruff <https://github.com/astral-sh/ruff>`_ for linting and formatting
   - `pytest <https://pytest.org/>`_ for testing

**Group-Based Organization**
   Organize repositories into logical groups with shared virtual environments and configurations.

**Developer Experience**
   Focus on making common tasks simple and intuitive, with helpful error messages and clear documentation.

License
-------

drivers-python-cli is open source software. See the `GitHub repository <https://github.com/aclark4life/drivers-python-cli>`_ for license information.
