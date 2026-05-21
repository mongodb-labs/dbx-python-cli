# Copilot Instructions

## Commands

```bash
# Install
uv pip install -e ".[dev]"      # dev extras
uv pip install -e ".[test]"     # test extras

# Test
python -m pytest                                                    # full suite
python -m pytest tests/test_install_command.py -v                  # single file
python -m pytest tests/test_install_command.py::test_install_basic_success -v  # single test
python -m pytest --cov=dbx --cov-report=term-missing               # with coverage

# Build
python -m build
```

Pre-commit hooks (ruff lint + format, toml/yaml checks) run on `git commit`. To apply ruff formatting manually: `ruff format src/`.

## Architecture

`dbx` is a Typer CLI tool for managing a local workspace of multiple git repositories, grouped by project area. The entry point is `src/dbx_python_cli/cli.py`, which mounts each command module as a sub-`typer.Typer` app.

### Config system

Config is loaded from `~/.config/dbx-python-cli/config.toml` (user) with fallback to the bundled `src/dbx_python_cli/config.toml`. The config drives almost all behavior — commands rarely have hardcoded paths or group names.

Key config sections:
- `[repo]` — `base_dir`, `flat`, `global_groups`, `group_priority`, `fork_user`, `python_version`, `editor`
- `[repo.groups.<name>]` — per-group settings: `repos`, `python_version`, `test_env`, `install_extras`, `install_dirs`, `build_commands`, `install_groups`, `test_runner`, `test_runner_args`, `preferred_branch`, `sys_path`, `skip_install`
- `[project.*]` — Django project defaults (MongoDB backend, edition, runner config)
- `[evergreen.<repo>]` — Evergreen CI project name mappings

### Flat mode vs grouped mode

`flat = true` in `[repo]` means repos live directly under `base_dir`. Grouped mode (default) uses `base_dir/<group>/<repo>`. All path helpers in `utils/repo.py` (`get_group_dir`, `get_repo_dir`, `get_projects_dir`) accept a `flat` flag — always derive it from `is_flat_mode(config)`.

### Global groups

Groups listed in `repo.global_groups` are not cloned into their own subdirectory. Their repos are installed into every other group's venv. Functions like `get_test_env_vars()` and install helpers fall back to global groups when a repo's own group has no config for it.

### Command pattern

Every command module follows this shape:

```python
app = typer.Typer(
    help="...",
    invoke_without_command=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)

@app.callback()
def my_command(ctx: typer.Context, ...):
    verbose = ctx.obj.get("verbose", False) if ctx.obj else False
    config = get_config()
    base_dir = get_base_dir(config)
    ...
```

`ctx.obj` carries top-level flags: `verbose`, `pager`, `mongodb_backend`, `mongodb_edition`. Commands are registered in `cli.py` with `app.add_typer(module.app, name="command-name")`.

### Key utilities (`utils/repo.py`)

All config lookups go through helpers — never access `config["repo"]["groups"]` directly:
- `get_repo_groups(config)` — all groups dict
- `get_global_groups(config)` — list of global group names
- `get_group_priority(config)` — ordered list for conflict resolution
- `is_flat_mode(config)` — bool
- `find_all_repos(base_dir, config)` — discovers cloned repos respecting flat/grouped layout
- `find_repo_by_name(name, base_dir, config)` — finds a repo with group priority applied
- `get_test_env_vars(config, group_name, repo_name)` — resolves env vars with global group fallback

## Testing conventions

- Tests use `pytest` with `typer.testing.CliRunner` to invoke commands end-to-end.
- Common patches: `dbx_python_cli.commands.<module>.get_config`, `subprocess.run`, `subprocess.check_call`.
- `tests/conftest.py` provides shared fixtures (`cli_runner`, temp directory helpers).
- Integration tests live in `tests/integration/` and may require real filesystem state.
- Mock the config dict directly rather than the TOML file:
  ```python
  with patch("dbx_python_cli.commands.list.get_config", return_value={
      "repo": {"base_dir": str(tmp_path), "flat": True, "groups": {...}}
  }):
  ```
