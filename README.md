# dbx-python-cli

> A command line tool for DBX Python development tasks. AI first. De-siloing happens here. Inspired by [django-mongodb-cli](https://github.com/mongodb-labs/django-mongodb-cli).

[![CI](https://github.com/aclark4life/dbx-python-cli/actions/workflows/ci.yml/badge.svg)](https://github.com/aclark4life/dbx-python-cli/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/aclark4life/dbx-python-cli/branch/main/graph/badge.svg)](https://codecov.io/gh/aclark4life/dbx-python-cli)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-Apache%202.0-green.svg)](LICENSE)
[![Documentation Status](https://readthedocs.org/projects/dbx-python-cli/badge/?version=latest)](https://dbx-python-cli.readthedocs.io/en/latest/?badge=latest)

## About

DBX Python is the MongoDB Database Experience Team for the MongoDB Python driver.

> **Note:** This is not [Databricks for Python developers](https://docs.databricks.com/aws/en/languages/python).

## Feature Highlights

- 🤖 **AI-First Design** - Built with AI-assisted development workflows in mind
- 🔧 **Modern Tooling** - Uses the latest Python development tools and best practices
- 📦 **Fast Package Management** - Powered by [uv](https://github.com/astral-sh/uv)
- ✨ **Quality Focused** - Pre-commit hooks with [prek](https://github.com/aclark4life/prek) and [ruff](https://github.com/astral-sh/ruff)
- 📚 **Well Documented** - Sphinx documentation with the beautiful Furo theme
- ✅ **Fully Tested** - Comprehensive test suite with pytest and coverage reporting

See the [full documentation](https://dbx-python-cli.readthedocs.io/) for detailed feature documentation.

## Installation

### Via pipx (Recommended)

```bash
# Install directly from GitHub
pipx install git+https://github.com/aclark4life/dbx-python-cli.git
```

This will install `dbx-python-cli` globally and make the `dbx` command available in your terminal.

## Quick Start

### Step 1: Initialize Configuration

First, initialize the configuration file:

```bash
dbx config init
```

This creates a configuration file at `~/.config/dbx-python-cli/config.toml` with default settings.

The default configuration includes:
- Base directory: `~/Developer/mongodb`
- Pre-configured repository groups (django, pymongo, langchain, etc.)

You can edit this file to customize your setup.

### Step 2: Clone Repositories

Clone a group of related repositories:

```bash
# Clone the django group
dbx clone -g django
```

This will clone all repositories in the django group to `~/Developer/mongodb/django/`.

### Step 3: Install Dependencies

> **Note:** The `dbx clone` command automatically runs `dbx install` after cloning, but you can also install repositories and repository groups manually.

Install dependencies for a repository:

```bash
# Install dependencies for django-mongodb-backend
dbx install django-mongodb-backend

# Install with test extras
dbx install django-mongodb-backend -e test

# Install libmongocrypt (includes cmake build step for Queryable Encryption)
dbx install libmongocrypt
```

> **Tip:** Extras and dependency groups can be configured in your `config.toml` file so you don't need to specify them on the command line each time.

### Step 4: Run Tests

Run tests for a repository:

```bash
# Run all tests
dbx test django

# Run a specific test module (note: django-mongodb-backend modules have trailing underscores)
dbx test django encryption_

# Run tests matching a keyword
dbx test django encryption_ -k test_schema
```

### Working with Django Projects

Create and manage Django projects with MongoDB backend:

```bash
# Create a new project
dbx project add myproject

# Install the project (defaults to newest project)
dbx project install

# Run migrations (defaults to newest project)
dbx project migrate

# Create a superuser (defaults to newest project)
dbx project su

# Run the project (defaults to newest project)
dbx project run
```

> **Convenience Feature:** Most project commands default to the newest project when no name is specified. This makes it faster to work with your current project without typing the name repeatedly.

### Common Workflows

**List Everything:**

```bash
# List all cloned repositories
dbx list

# List all virtual environments
dbx env list
```

**Run Just Commands:**

If a repository has a `justfile`, you can run just commands:

```bash
# Show available just commands
dbx just mongo-python-driver

# Run a specific just command
dbx just mongo-python-driver lint

# Run just command with arguments
dbx just mongo-python-driver test -v
```

**Sync Repositories:**

Keep your repositories up to date:

```bash
# Sync a single repository
dbx sync django-mongodb-backend

# Sync all repositories in a group
dbx sync -g django
```

**View Git Branches:**

View branches across repositories:

```bash
# View branches in a single repository
dbx branch django-mongodb-backend

# View all branches (including remote) with verbose output
dbx -v branch django-mongodb-backend

# View branches in all repositories in a group
dbx branch -g django

# View all branches in all repositories in a group
dbx -v branch -g django
```

**Working with Multiple Groups:**

You can work with multiple repository groups:

```bash
# Clone langchain group
dbx clone -g langchain

# Create venv for langchain
dbx env init -g langchain

# Install dependencies
dbx install langchain-mongodb -g langchain
```

**Verbose Mode:**

Use `-v` or `--verbose` for detailed output:

```bash
dbx -v install django-mongodb-backend
dbx --verbose test django encryption_
```

For more details, see the [full documentation](https://dbx-python-cli.readthedocs.io/).

## Development

### Getting Started

```bash
# Clone the repository
git clone https://github.com/aclark4life/dbx-python-cli.git
cd dbx-python-cli

# Install the package (uses uv pip install -e .)
just install

# Install pre-commit hooks
just install-hooks
```

The `just install` command uses [uv](https://github.com/astral-sh/uv) under the hood to install the package in editable mode. If you need development dependencies, you can install them with just:

```bash
just install-docs  # Documentation dependencies
just install-test  # Testing dependencies
```

Or use uv directly:

```bash
uv pip install -e ".[docs]"  # Documentation dependencies
uv pip install -e ".[test]"  # Testing dependencies
uv pip install -e ".[dev]"   # All development dependencies (docs + test)
```

### Command Runner

This project uses [just](https://github.com/casey/just) as a command runner. All commands have single-character aliases for convenience.

### Common Commands

```bash
# Install the package
just install      # or: just i

# Run tests
just test         # or: just t

# Build documentation
just docs         # or: just d

# Format code
just format       # or: just f

# Run linter
just lint         # or: just l

# Run pre-commit hooks
just hooks-run    # or: just h

# Build the package
just build        # or: just b

# Clean build artifacts
just clean        # or: just c
```

### Running Tests

```bash
# Run all tests with coverage
just test

# Run tests with verbose output
just test-verbose

# Generate coverage report
just test-cov
```

### Building Documentation

```bash
# Build HTML documentation
just docs

# Serve documentation locally
just docs-serve

# Clean documentation build
just docs-clean
```

## Technology Stack

- **CLI Framework:** [Typer](https://typer.tiangolo.com/) - Modern, intuitive CLI framework
- **Package Manager:** [uv](https://github.com/astral-sh/uv) - Ultra-fast Python package installer
- **Task Runner:** [just](https://github.com/casey/just) - Command runner with simple syntax
- **Pre-commit:** [prek](https://github.com/aclark4life/prek) - Pre-commit hook manager
- **Linter/Formatter:** [ruff](https://github.com/astral-sh/ruff) - Extremely fast Python linter
- **Documentation:** [Sphinx](https://www.sphinx-doc.org/) with [Furo](https://github.com/pradyunsg/furo) theme
- **Testing:** [pytest](https://pytest.org/) with [pytest-cov](https://pytest-cov.readthedocs.io/)

## Project Structure

### Repository Structure

```
dbx-python-cli/
├── src/dbx_python_cli/       # Source code
│   ├── __init__.py           # Package initialization
│   ├── cli.py                # Main CLI entry point
│   ├── config.toml           # Default configuration template
│   ├── commands/             # Command implementations
│   │   ├── branch.py         # Git branch commands
│   │   ├── clone.py          # Repository cloning
│   │   ├── config.py         # Configuration management
│   │   ├── docs.py           # Documentation commands
│   │   ├── edit.py           # Editor integration
│   │   ├── env.py            # Virtual environment management
│   │   ├── install.py        # Dependency installation
│   │   ├── just.py           # Just command runner
│   │   ├── list.py           # Repository listing
│   │   ├── log.py            # Git log commands
│   │   ├── mongodb.py        # MongoDB runner integration
│   │   ├── open.py           # Browser integration
│   │   ├── project.py        # Django project management
│   │   ├── project_utils.py  # Project utilities
│   │   ├── remove.py         # Repository removal
│   │   ├── repo_utils.py     # Repository utilities
│   │   ├── status.py         # Git status commands
│   │   ├── switch.py         # Git branch switching
│   │   ├── sync.py           # Fork synchronization
│   │   ├── test.py           # Test runner
│   │   └── venv_utils.py     # Virtual environment utilities
│   └── templates/            # Django project templates
│       ├── app_template/     # Django app template
│       ├── frontend_template/ # Frontend template
│       └── project_template/ # Django project template
├── tests/                    # Test suite
│   ├── conftest.py           # Pytest configuration
│   ├── test_*.py             # Command tests
│   └── integration/          # Integration tests
├── docs/                     # Sphinx documentation
│   ├── conf.py               # Sphinx configuration
│   ├── index.rst             # Documentation index
│   ├── introduction/         # Introduction docs
│   ├── features/             # Feature documentation
│   ├── design/               # Design documentation
│   ├── api/                  # API documentation
│   └── development/          # Development docs
├── pyproject.toml            # Project configuration
├── justfile                  # Task runner commands
├── uv.lock                   # Dependency lock file
└── README.md                 # This file
```

### User Directory Structure

After running `dbx config init` and `dbx clone -g django`, your directory structure will look like:

```
~/Developer/mongodb/              # base_dir (configurable)
├── django/                       # Group directory
│   ├── .venv/                    # Group-level virtual environment
│   ├── mongo-python-driver/     # Cloned from global group
│   ├── django/                   # Django fork
│   ├── django-mongodb-backend/  # MongoDB backend for Django
│   ├── django-mongodb-extensions/ # MongoDB extensions
│   ├── libmongocrypt/           # Queryable Encryption library
│   └── medical-records/         # Example project
├── pymongo/                      # Another group
│   ├── .venv/                    # Separate venv for this group
│   ├── mongo-python-driver/     # Cloned from global group
│   ├── specifications/          # MongoDB specifications
│   └── drivers-evergreen-tools/ # Testing tools
└── langchain/                    # Another group
    ├── .venv/                    # Separate venv for this group
    ├── mongo-python-driver/     # Cloned from global group
    └── langchain-mongodb/       # LangChain MongoDB integration
```

**Key Points:**

- **Group-Level Virtual Environments:** Each group has its own `.venv` directory for isolated dependencies
- **Global Repositories:** Repositories in `global_groups` (like `mongo-python-driver`) are automatically cloned into every group
- **Configurable Base Directory:** The base directory can be customized in `~/.config/dbx-python-cli/config.toml`
- **Organized by Purpose:** Groups organize related repositories (e.g., django, pymongo, langchain)

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Install pre-commit hooks (`just install-hooks`)
4. Make your changes
5. Run tests (`just test`)
6. Commit your changes (`git commit -m 'Add amazing feature'`)
7. Push to the branch (`git push origin feature/amazing-feature`)
8. Open a Pull Request

## License

This project is licensed under the Apache 2.0 License - see the LICENSE file for details.

## Links

- **Documentation:** [Read the Docs](https://dbx-python-cli.readthedocs.io/)
- **Source Code:** [GitHub](https://github.com/aclark4life/dbx-python-cli)
- **Issue Tracker:** [GitHub Issues](https://github.com/aclark4life/dbx-python-cli/issues)

---

Made with ❤️ by MongoDB DBX Python
