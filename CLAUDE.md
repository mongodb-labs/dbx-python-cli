# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install (editable) + hooks
uv pip install -e .
prek install

# Run all tests
python -m pytest

# Run a single test file / single test
python -m pytest tests/test_install_command.py -v
python -m pytest tests/test_install_command.py::test_install_basic_success -v

# Lint / format (also run automatically on git commit via prek)
uvx ruff check .
uvx ruff format .

# Build docs
cd docs && python -m sphinx -b html . _build/html
```

Pre-commit hooks (ruff lint + format, toml/yaml checks) run on every `git commit` via `prek`. If a hook modifies files, re-stage them and commit again.

## Architecture

### Entry point and command registration

`src/dbx_python_cli/cli.py` creates the root Typer app and mounts every command module as a sub-app. Global flags (`--verbose`, `--pager`, `--backend`, `--edition`) are defined on `@app.callback()` and forwarded to subcommands via `ctx.obj`. The CLI is registered as `dbx = "dbx_python_cli.cli:app"` in `pyproject.toml`.

### Command modules

Each file in `src/dbx_python_cli/commands/` follows the same pattern:

```python
app = typer.Typer(invoke_without_command=True, context_settings={"help_option_names": ["-h", "--help"]})

@app.callback()
def my_command(ctx: typer.Context, ...):
    verbose = ctx.obj.get("verbose", False) if ctx.obj else False
    config = repo.get_config()
    base_dir = repo.get_base_dir(config)
    ...
```

Commands with subcommands (e.g. `config`, `env`, `project`, `spec`) use `@app.command()` for each subcommand instead of a single `@app.callback()`.

### Configuration

`utils/repo.py:get_config()` loads `~/.config/dbx-python-cli/config.toml`, falling back to the bundled `src/dbx_python_cli/config.toml`. Config is plain TOML read with `tomllib`.

Key config sections:
- `[repo]` — `base_dir`, `flat`, `fork_user`, `global_groups`, `group_priority`, `python_version`, `editor`
- `[repo.groups.<name>]` — per-group: `repos`, `python_version`, `preferred_branch`, `no_fork`, `upstream`, `upstream_branch`, `install_extras`, `install_groups`, `install_dirs`, `build_commands`, `test_runner`, `test_runner_args`, `test_env`, `skip_install`, `sys_path`
- `[project.*]` — Django project defaults and MongoDB backend config
- `[evergreen.<repo>]` — Evergreen CI project name mappings

### Directory layout

Two modes controlled by `repo.flat`:
- **Grouped** (default): `base_dir/<group>/<repo>`
- **Flat**: `base_dir/<repo>` (group membership from config, not filesystem)

All path resolution goes through helpers in `utils/repo.py`: `get_group_dir()`, `get_repo_dir()`, `is_flat_mode()`.

### Fork workflow

`dbx clone` supports cloning from a personal fork (`--fork` / `--fork-user`). The global `fork_user` in `[repo]` is the default. Per-repo overrides:
- `no_fork = ["repo-name"]` — skip fork substitution for specific repos even when `--fork` is active (used for org forks like `mongodb-forks/django`)
- `upstream = {repo = "url"}` — add an `upstream` remote automatically on clone
- `upstream_branch = {repo = "branch"}` — override the rebase target in `dbx sync` when the local branch name differs from the upstream branch

### Utilities

- `utils/repo.py` — config loading, path helpers, all per-group config accessors (`get_upstream_url`, `get_upstream_branch`, `get_no_fork_repos`, `get_preferred_branch`, `get_install_dirs`, etc.)
- `utils/venv.py` — venv detection chain: repo-level → group-level → base-level → activated venv → PATH
- `utils/project.py` — Django project helpers (settings discovery, env var injection)
- `utils/output.py` — pager support (`paginate_output`, `should_use_pager`)

### Testing

Tests use `typer.testing.CliRunner`. Mock `get_config` at the command module level (e.g. `dbx_python_cli.commands.install.get_config`), not at the utils level. Shared fixtures are in `tests/conftest.py`.
