Contributing
============

Thank you for your interest in contributing to drivers-python-cli!

Getting Started
---------------

1. Fork the repository on GitHub
2. Clone your fork locally
3. Set up your development environment (see :doc:`setup`)
4. Create a new branch for your changes
5. Make your changes
6. Run tests and ensure they pass
7. Submit a pull request

Development Workflow
--------------------

Create a Branch
~~~~~~~~~~~~~~~

.. code-block:: bash

   # Create a new branch for your feature/fix
   git checkout -b feature/my-new-feature

   # Or for a bug fix
   git checkout -b fix/issue-123

Make Changes
~~~~~~~~~~~~

1. Write your code
2. Add tests for your changes
3. Update documentation if needed
4. Run pre-commit hooks to check formatting

.. code-block:: bash

   # Run pre-commit hooks manually
   just hooks-run

   # Or they'll run automatically on commit
   git commit -m "Add new feature"

Run Tests
~~~~~~~~~

.. code-block:: bash

   # Run all tests
   just test

   # Run specific tests
   pytest tests/test_install_command.py -v

   # Check coverage
   just test-cov

Update Documentation
~~~~~~~~~~~~~~~~~~~~

If your changes affect user-facing functionality:

1. Update relevant documentation in ``docs/``
2. Add code examples if applicable
3. Build docs locally to verify

.. code-block:: bash

   # Build documentation
   just docs

   # Serve locally to preview
   just docs-serve

Submit Pull Request
~~~~~~~~~~~~~~~~~~~

1. Push your branch to your fork
2. Open a pull request on GitHub
3. Describe your changes clearly
4. Link any related issues
5. Wait for review

Code Style
----------

This project uses `ruff <https://github.com/astral-sh/ruff>`_ for linting and formatting:

.. code-block:: bash

   # Format code
   just format

   # Run linter
   just lint

   # Both are run automatically by pre-commit hooks

Follow these guidelines:

- Use type hints where appropriate
- Write docstrings for public functions/classes
- Keep functions focused and small
- Use descriptive variable names
- Follow PEP 8 style guide (enforced by ruff)

Commit Messages
---------------

Write clear, descriptive commit messages:

.. code-block:: text

   Add support for -g flag in install command

   - When installing a single repo with -g, now looks for repo in specified group
   - Useful when same repo exists in multiple groups
   - Added tests to verify behavior
   - All tests pass (56/56)

Format:

1. **First line:** Brief summary (50 chars or less)
2. **Blank line**
3. **Body:** Detailed description with bullet points
   - What changed
   - Why it changed
   - Any breaking changes
   - Test results

Testing Requirements
--------------------

All contributions must include tests:

1. **New features:** Add tests for new functionality
2. **Bug fixes:** Add tests that would have caught the bug
3. **Refactoring:** Ensure existing tests still pass
4. **Coverage:** Aim to maintain or improve coverage

See :doc:`testing` for detailed testing guidelines.

Documentation Requirements
--------------------------

Update documentation for:

- New features or commands
- Changed behavior or APIs
- New configuration options
- Breaking changes

See :doc:`documentation` for documentation guidelines.

Review Process
--------------

Pull requests are reviewed by maintainers:

1. **Automated checks:** Tests, linting, coverage must pass
2. **Code review:** Maintainer reviews code quality and design
3. **Documentation review:** Ensure docs are clear and complete
4. **Testing review:** Verify tests are comprehensive
5. **Approval:** Once approved, PR will be merged

Questions?
----------

If you have questions:

- Open an issue on GitHub
- Ask in the pull request
- Check existing documentation

We're here to help! 🎉
