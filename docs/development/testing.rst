Testing
=======

This guide covers testing workflows for drivers-python-cli.

Running Tests
-------------

Using just (Recommended)
~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   # Run all tests with coverage
   just test

   # Run tests with verbose output
   just test-verbose

   # Generate coverage report
   just test-cov

   # Run specific test file
   pytest tests/test_install_command.py -v

   # Run specific test
   pytest tests/test_install_command.py::test_install_basic_success -v

Using pytest Directly
~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   # Run all tests
   python -m pytest tests/ -v

   # Run with coverage
   python -m pytest tests/ --cov=src/drivers_python_cli --cov-report=html

   # Run specific test file
   python -m pytest tests/test_install_command.py -v

   # Run with verbose output and show print statements
   python -m pytest tests/ -v -s

Test Structure
--------------

The test suite is organized by command:

.. code-block:: text

   tests/
   ├── test_cli.py              # Main CLI tests
   ├── test_install_command.py  # Install command tests
   ├── test_just_command.py     # Just command tests
   ├── test_repo.py             # Repo command tests
   ├── test_test_command.py     # Test command tests
   └── test_version.py          # Version tests

Writing Tests
-------------

Test Naming Convention
~~~~~~~~~~~~~~~~~~~~~~

- Test files: ``test_<module>.py``
- Test functions: ``test_<feature>_<scenario>``

Example:

.. code-block:: python

   def test_install_basic_success(tmp_path):
       """Test basic installation of a repository."""
       # Test implementation

Using Fixtures
~~~~~~~~~~~~~~

Common fixtures are available in ``conftest.py``:

.. code-block:: python

   def test_with_temp_dir(tmp_path):
       """Use pytest's tmp_path fixture for temporary directories."""
       repo_dir = tmp_path / "test-repo"
       repo_dir.mkdir()
       # Test implementation

Mocking
~~~~~~~

Use ``unittest.mock`` for mocking external dependencies:

.. code-block:: python

   from unittest.mock import patch, MagicMock

   def test_with_mocked_subprocess():
       with patch("subprocess.run") as mock_run:
           mock_run.return_value = MagicMock(returncode=0)
           # Test implementation

Coverage
--------

The project aims for high test coverage. Current coverage is displayed in the test output:

.. code-block:: bash

   # Generate HTML coverage report
   just test-cov

   # Open coverage report in browser
   open htmlcov/index.html

Coverage reports show:

- Overall coverage percentage
- Line-by-line coverage for each file
- Missing lines that need tests

Continuous Integration
----------------------

Tests run automatically on every push via GitHub Actions. The CI pipeline:

1. Runs tests on multiple Python versions (3.10, 3.11, 3.12, 3.13, 3.14)
2. Checks code formatting with ruff
3. Generates coverage reports
4. Fails if tests don't pass or coverage drops

Best Practices
--------------

1. **Write tests first** - Test-driven development helps catch issues early
2. **Test edge cases** - Don't just test the happy path
3. **Use descriptive names** - Test names should describe what they test
4. **Keep tests isolated** - Each test should be independent
5. **Mock external dependencies** - Don't rely on external services
6. **Check coverage** - Aim for high coverage but focus on meaningful tests
