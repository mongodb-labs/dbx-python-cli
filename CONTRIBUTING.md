# Contributing to drivers-python-cli

Thank you for your interest in contributing to drivers-python-cli! This project requires that **all contributions are made exclusively through AI coding assistants**. Direct, hand-written code changes are not accepted. Please read this document carefully before contributing.

## Table of Contents

- [Getting Started](#getting-started)
- [Development Workflow](#development-workflow)
- [AI-Only Contributions](#ai-only-contributions)
- [Code Style and Quality](#code-style-and-quality)
- [Testing](#testing)
- [Documentation](#documentation)
- [Submitting Changes](#submitting-changes)

## Getting Started

### Prerequisites

- Python 3.11 or higher
- [uv](https://github.com/astral-sh/uv) for package management
- Git for version control

### Setting Up Your Development Environment

1. **Fork and clone the repository:**

```bash
git clone https://github.com/YOUR_USERNAME/drivers-python-cli.git
cd drivers-python-cli
```

2. **Install development dependencies:**

```bash
uv pip install -e ".[dev]"
```

3. **Install pre-commit hooks:**

```bash
uvx prek install
```

## Development Workflow

### Running Tests

```bash
# Run all tests
just test

# Run tests with coverage
just test-cov

# Run specific test file
python -m pytest tests/test_open_command.py -v
```

### Code Formatting and Linting

```bash
# Format code with ruff
uvx ruff format .

# Check formatting
uvx ruff format --check .

# Run linter
uvx ruff check .

# Fix auto-fixable linting issues
uvx ruff check --fix .
```

### Building Documentation

```bash
# Build documentation
just docs

# Serve documentation locally
just docs-serve
```

## AI-Only Contributions

**This project is AI-first and AI-only.** All code, tests, and documentation changes must be authored by an AI coding assistant. Human contributors participate by directing, reviewing, and iterating on AI output — not by writing code directly.

### Why AI-Only?

- Ensures consistent code style and quality enforced through AI guidelines
- Encourages contributors to think at a higher level (intent and requirements) rather than implementation details
- Makes the contribution process accessible regardless of coding experience

### Recommended AI Tools

- **[Augment Agent](https://www.augmentcode.com/)** *(recommended)* — deeply context-aware, understands the full codebase
- GitHub Copilot, Cursor, Windsurf, or similar agentic coding assistants

### How to Contribute

1. **Open an issue** describing the feature, bug, or improvement you want
2. **Start an AI session** with your preferred AI coding assistant
3. **Point the AI at this file** at the start of your session:
   ```
   Please read CONTRIBUTING.md for project guidelines and instructions.
   ```
4. **Describe your goal** to the AI and let it plan and implement the changes
5. **Review the AI's output** — read diffs, run tests, and iterate with the AI until the result is correct
6. **Open a Pull Request** with the AI-generated changes

> ⚠️ Pull requests containing code that was clearly hand-written without AI assistance will not be accepted.

### Instructions for AI Assistants

When contributing to this project, please follow these guidelines:

#### Code Changes

1. **Always search before editing**: Use `codebase-retrieval` to understand existing patterns and implementations before making changes
2. **Use package managers**: Always use `uv pip install/uninstall` instead of manually editing `pyproject.toml`
3. **Follow existing patterns**: Match the coding style and patterns used in similar commands/features
4. **Be conservative**: Respect the existing codebase structure and don't make unnecessary changes

#### Testing Requirements

1. **Write tests first**: For new features, write tests before or alongside implementation
2. **Update existing tests**: When modifying functionality, update affected tests
3. **Run full test suite**: Always run `python -m pytest` before committing
4. **Maintain coverage**: Aim to maintain or improve test coverage

#### Code Quality

1. **Format code**: Run `uvx ruff format .` before committing
2. **Fix linting errors**: Run `uvx ruff check --fix .` and address any remaining issues
3. **No f-strings without placeholders**: Use regular strings if there are no f-string placeholders
4. **Type hints**: Add type hints to function signatures where appropriate

#### Commit Guidelines

1. **Descriptive messages**: Write clear, descriptive commit messages
2. **Atomic commits**: Make focused commits that address one concern
3. **Test before commit**: Ensure all tests pass before committing
4. **Format before commit**: Ensure code is formatted before committing

#### Documentation

1. **Update docstrings**: Keep docstrings up-to-date with code changes
2. **Update docs**: Update Sphinx documentation for user-facing changes
3. **Add examples**: Include usage examples in docstrings and documentation

#### Project-Specific Instructions

<!--
Add project-specific instructions below this comment.
These instructions will be read by AI assistants in future sessions.

Examples:
- Specific architectural decisions or patterns to follow
- Known issues or workarounds
- Preferred libraries or approaches for certain tasks
- Domain-specific knowledge about MongoDB, PyMongo, etc.
- Common pitfalls to avoid
-->

**Current Project-Specific Instructions:**

1. **Fork workflow**: When repos are cloned with `--fork`, the `origin` remote points to the fork and `upstream` points to the original repo
2. **Group-based operations**: Many commands support `-g/--group` flag to operate on all repos in a group
3. **Verbose logging**: Use the `verbose` flag from context for detailed logging: `verbose = ctx.obj.get("verbose", False) if ctx.obj else False`
4. **Git operations**: Always use subprocess to run git commands, check return codes, and handle errors gracefully
5. **Config structure**: Configuration is in TOML format with `[repo.groups.GROUP_NAME]` sections containing repo lists

<!-- Add new instructions above this line -->

### Tips for Directing Your AI Assistant

When prompting an AI assistant to contribute, give it enough context to do the job well:

- **Reference similar features**: "There's an existing `clone` command in `commands/clone.py` — use it as a pattern"
- **Describe expected behavior and edge cases**: Be specific about what should happen and what shouldn't
- **State testing requirements**: "Write tests alongside the implementation and make sure they pass"
- **Iterate**: If the first attempt isn't right, describe what's wrong and ask the AI to fix it — don't patch it by hand

## Code Style and Quality

### Python Style

- Follow PEP 8 guidelines
- Use [ruff](https://github.com/astral-sh/ruff) for formatting and linting
- Maximum line length: 88 characters (Black-compatible)
- Use type hints where appropriate

### Project Conventions

- Commands are organized in `src/drivers_python_cli/commands/`
- Each command has its own module (e.g., `open.py`, `clone.py`)
- Shared utilities go in `repo_utils.py` or similar utility modules
- Tests mirror the source structure in `tests/`
- Use Typer for CLI interface
- Use subprocess for git operations

## Testing

### Test Organization

- Unit tests in `tests/test_*.py`
- Integration tests in `tests/integration/`
- Use pytest fixtures for common setup
- Mock external dependencies (git, subprocess, etc.)

### Writing Tests

```python
def test_feature_name(tmp_path, mock_config):
    """Test description of what is being tested."""
    # Arrange
    # ... setup

    # Act
    result = runner.invoke(app, ["command", "args"])

    # Assert
    assert result.exit_code == 0
    assert "expected output" in result.stdout
```

## Documentation

- Main documentation in `docs/` using Sphinx
- API documentation auto-generated from docstrings
- Feature documentation in `docs/features/`
- Keep README.md up-to-date with major changes

## Submitting Changes

1. **Create a feature branch**: `git checkout -b feature/your-feature-name`
2. **Make your changes**: Follow the guidelines above
3. **Run tests**: Ensure all tests pass
4. **Format code**: Run ruff format and check
5. **Commit changes**: Use clear, descriptive commit messages
6. **Push to your fork**: `git push origin feature/your-feature-name`
7. **Open a Pull Request**: Describe your changes and link any related issues

### Pull Request Guidelines

- Provide a clear description of the changes
- Reference any related issues
- Ensure CI checks pass
- Be responsive to feedback and review comments

## Questions?

If you have questions or need help, please:
- Open an issue on GitHub
- Check existing documentation
- Ask in pull request comments

Thank you for contributing to drivers-python-cli! 🎉
