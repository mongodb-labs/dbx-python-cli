# Default recipe to display help information
default:
    @just --list

# Install the package in editable mode and pre-commit hooks
install:
    uv pip install -e .
    prek install

# Alias for install
alias i := install

# Install development dependencies
install-dev:
    uv pip install -e ".[dev]"

# Install documentation dependencies
install-docs:
    uv pip install -e ".[docs]"

# Install test dependencies
install-test:
    uv pip install -e ".[test]"

# Build the package
build:
    python -m build

# Alias for build
alias b := build

# Clean build artifacts
clean:
    rm -rf build/
    rm -rf dist/
    rm -rf *.egg-info
    rm -rf src/*.egg-info
    find . -type d -name __pycache__ -exec rm -rf {} +
    find . -type f -name "*.pyc" -delete

# Alias for clean
alias c := clean

# Run the CLI with --help
run:
    dpy --help

# Alias for run
alias r := run

# Run the CLI with --version
version:
    dpy --version

# Alias for version
alias v := version

# Uninstall the package
uninstall:
    uv pip uninstall drivers-python-cli

# Alias for uninstall
alias u := uninstall

# Reinstall the package (clean install)
reinstall: uninstall install

# Format code (placeholder for future formatter)
format:
    @echo "No formatter configured yet"

# Alias for format
alias f := format

# Lint code (placeholder for future linter)
lint:
    @echo "No linter configured yet"

# Alias for lint
alias l := lint

# Run tests with pytest
test:
    python -m pytest

# Alias for test
alias t := test

# Run tests with coverage report
test-cov:
    python -m pytest --cov=drivers_python_cli --cov-report=term-missing --cov-report=html

# Run tests in watch mode (requires pytest-watch)
test-watch:
    python -m pytest_watch

# Run tests with verbose output
test-verbose:
    python -m pytest -vv

# Install pre-commit hooks with prek
install-hooks:
    prek install

# Run pre-commit hooks on all files
hooks-run:
    prek run --all-files

# Alias for hooks-run
alias h := hooks-run

# Build Sphinx documentation
docs:
    cd docs && python -m sphinx -b html . _build/html

# Alias for docs
alias d := docs

# Clean documentation build
docs-clean:
    rm -rf docs/_build

# Serve documentation locally
docs-serve:
    python -m http.server --directory docs/_build/html 8000
