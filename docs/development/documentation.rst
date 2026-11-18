Documentation
=============

This guide covers building and contributing to the documentation.

Building Documentation
----------------------

Using just (Recommended)
~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   # Build HTML documentation
   just docs

   # Serve documentation locally
   just docs-serve

   # Clean documentation build
   just docs-clean

Using Sphinx Directly
~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   # Build HTML documentation
   cd docs
   make html

   # Serve documentation locally
   python -m http.server -d _build/html

   # Clean build
   make clean

Documentation Structure
-----------------------

The documentation is organized into several sections:

.. code-block:: text

   docs/
   ├── index.rst              # Main documentation index
   ├── features/              # Feature documentation
   │   ├── index.rst
   │   ├── installation.rst
   │   ├── repo-management.rst
   │   ├── testing.rst
   │   ├── just-commands.rst
   │   └── global-options.rst
   ├── design/                # Design documentation
   │   ├── index.rst
   │   ├── venv-strategy.rst
   │   └── git-operations.rst
   ├── api/                   # API documentation
   │   ├── index.rst
   │   ├── core.rst
   │   └── commands.rst
   └── development/           # Development documentation
       ├── index.rst
       ├── setup.rst
       ├── testing.rst
       ├── documentation.rst
       └── contributing.rst

Writing Documentation
---------------------

reStructuredText Basics
~~~~~~~~~~~~~~~~~~~~~~~~

Documentation is written in reStructuredText (RST) format:

.. code-block:: rst

   Section Title
   =============

   Subsection
   ----------

   **Bold text**
   *Italic text*
   ``Code text``

   - Bullet list
   - Another item

   1. Numbered list
   2. Another item

   .. code-block:: python

      # Python code example
      def hello():
          print("Hello, world!")

   .. note::
      This is a note admonition.

   .. warning::
      This is a warning admonition.

Code Examples
~~~~~~~~~~~~~

Use code blocks with syntax highlighting:

.. code-block:: rst

   .. code-block:: bash

      # Shell commands
      dpy install mongo-python-driver

   .. code-block:: python

      # Python code
      import drivers_python_cli

Cross-References
~~~~~~~~~~~~~~~~

Link to other documentation sections:

.. code-block:: rst

   See :doc:`features/installation` for installation instructions.
   See :ref:`section-label` for a specific section.

API Documentation
~~~~~~~~~~~~~~~~~

API documentation is auto-generated from docstrings using Sphinx autodoc:

.. code-block:: python

   def install_package(repo_path, python_path, install_dir=None):
       """
       Install a package from a directory.

       Args:
           repo_path: Path to the repository root
           python_path: Path to Python executable
           install_dir: Subdirectory to install from (for repos with multiple packages), or None for root

       Returns:
           bool: True if successful, False otherwise
       """

Documentation Style Guide
-------------------------

1. **Use clear, concise language** - Avoid jargon when possible
2. **Include examples** - Show don't just tell
3. **Use admonitions** - Highlight important information with notes/warnings
4. **Keep it up-to-date** - Update docs when code changes
5. **Test code examples** - Make sure examples actually work
6. **Use consistent formatting** - Follow the existing style

Publishing Documentation
------------------------

Documentation is automatically published to Read the Docs on every push to main:

- **URL:** https://drivers-python-cli.readthedocs.io/
- **Builds:** Triggered automatically on push
- **Versions:** Main branch and tagged releases

Local Preview
~~~~~~~~~~~~~

To preview documentation locally before pushing:

.. code-block:: bash

   # Build and serve
   just docs-serve

   # Open in browser
   open http://localhost:8000
