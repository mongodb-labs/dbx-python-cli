"""Test command for running pytest in repositories."""

import json
import os
import subprocess
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import typer

from dbx_python_cli.utils.repo import (
    find_repo_by_name,
    find_all_repos_by_name,
    get_base_dir,
    get_config,
    get_test_env_vars,
    get_test_runner,
    get_test_runner_args,
)
from dbx_python_cli.utils.venv import get_venv_info
from dbx_python_cli.commands.project import add_project
from dbx_python_cli.commands.mongodb import ensure_mongodb

app = typer.Typer(
    help="💚 Test commands",
    context_settings={
        "help_option_names": ["-h", "--help"],
        "ignore_unknown_options": False,
    },
    no_args_is_help=True,
)


@app.callback(
    invoke_without_command=True, context_settings={"allow_interspersed_args": False}
)
def test_callback(
    ctx: typer.Context,
    repo_name: str = typer.Argument(None, help="Repository name to test"),
    test_args: list[str] = typer.Argument(
        None,
        help="Additional arguments to pass to the test runner (e.g., '--verbose', '-k test_name'). For pytest, these are passed directly. For custom test runners, all args are forwarded.",
    ),
    keyword: str = typer.Option(
        None,
        "--keyword",
        "-k",
        help="Only run tests matching the given keyword expression (passed to pytest -k). Note: Use test_args for custom test runners.",
    ),
    group: Optional[str] = typer.Option(
        None,
        "--group",
        "-g",
        help="Group name - tests will run in the repo within this group using its venv (e.g., 'pymongo')",
    ),
    list_repos: bool = typer.Option(
        False,
        "--list",
        "-l",
        help="Show repository status (cloned vs available)",
    ),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Skip confirmation prompts",
    ),
):
    """Run tests in a cloned repository.

    Usage::

        dbx test <repo_name> [test_args...]
        dbx test <repo_name> -k <keyword>
        dbx test <repo_name> -g <group>

    Examples::

        dbx test mongo-python-driver                    # Run pytest
        dbx test mongo-python-driver -v                 # Run pytest with verbose
        dbx test mongo-python-driver -k test_insert     # Run specific test
        dbx test django --verbose                       # Run custom test runner with args
    """
    # If a subcommand was invoked, don't run this logic
    if ctx.invoked_subcommand is not None:
        return

    # Get verbose flag from parent context
    verbose = ctx.obj.get("verbose", False) if ctx.obj else False

    # test_args will be None if not provided, or a list of strings if provided
    if test_args is None:
        test_args = []

    try:
        config = get_config()
        base_dir = get_base_dir(config)
        if verbose:
            typer.echo(f"[verbose] Using base directory: {base_dir}")
            typer.echo(f"[verbose] Config:\n{json.dumps(config, indent=4)}\n")
    except Exception as e:
        typer.echo(f"❌ Error: {e}", err=True)
        raise typer.Exit(1)

    # MongoDB URI handling is done later via ensure_mongodb

    # Handle --list flag
    if list_repos:
        from dbx_python_cli.utils.repo import list_repos as list_repos_func

        output = list_repos_func(base_dir, config=config)
        if output:
            typer.echo(f"Base directory: {base_dir}\n")
            typer.echo("Repository status:\n")
            typer.echo(output)
            typer.echo(
                "\nLegend: ✓ = cloned, ○ = available to clone, ? = cloned but not in config"
            )
        else:
            typer.echo(f"Base directory: {base_dir}\n")
            typer.echo("No repositories found.")
            typer.echo("\nClone repositories using: dbx clone -g <group>")
        return

    try:
        # Require repo_name
        if not repo_name:
            typer.echo("❌ Error: Repository name is required", err=True)
            typer.echo("\nUsage: dbx test <repo_name> [OPTIONS]")
            raise typer.Exit(1)

        # Find the repository
        if group:
            # When group is specified, find the repo in that specific group
            group_path = Path(base_dir) / group
            if not group_path.exists():
                typer.echo(
                    f"❌ Error: Group '{group}' not found in {base_dir}", err=True
                )
                raise typer.Exit(1)

            # Look for the repo in the specified group
            repo_path = group_path / repo_name
            if not repo_path.exists() or not (repo_path / ".git").exists():
                typer.echo(
                    f"❌ Error: Repository '{repo_name}' not found in group '{group}'",
                    err=True,
                )
                typer.echo(f"Expected path: {repo_path}", err=True)
                raise typer.Exit(1)

            repo = {
                "name": repo_name,
                "path": repo_path,
                "group": group,
            }
        else:
            # Default behavior: find repo by name across all groups
            repo = find_repo_by_name(repo_name, base_dir)
            if not repo:
                typer.echo(f"Error: Repository '{repo_name}' not found.", err=True)
                typer.echo("Run 'dbx list' to see available repositories.", err=True)
                raise typer.Exit(1)

            # Check if repo exists in multiple groups
            all_matches = find_all_repos_by_name(repo_name, base_dir)
            if len(all_matches) > 1:
                groups = [r["group"] for r in all_matches]
                typer.echo(
                    f"ℹ️  Note: '{repo_name}' exists in multiple groups: {', '.join(groups)}"
                )
                typer.echo(
                    f"   Using: {repo['group']} group (specify with -g to use a different one)\n"
                )

            repo_path = repo["path"]
            # Use repo's own group
            group_path = repo_path.parent

        # Detect venv
        python_path, venv_type = get_venv_info(
            repo["path"], group_path, base_path=base_dir
        )

        if verbose:
            typer.echo(f"[verbose] Venv type: {venv_type}")
            typer.echo(f"[verbose] Python: {python_path}\n")

        # Get test runner configuration
        test_runner = get_test_runner(config, repo["group"], repo_name)
        runner_default_args = get_test_runner_args(config, repo["group"], repo_name)

        # For the django repo with a custom test runner: inject default settings
        if test_runner and repo_name == "django":
            # Also handle keyword if set via the typer option (e.g. -k before repo name)
            if keyword:
                test_args = list(test_args) + ["-k", keyword]

            # Warn when no test module (non-flag positional arg) is specified.
            # -k is a keyword filter, not a module — skip its value when scanning.
            def _has_test_module(args):
                i = 0
                while i < len(args):
                    if args[i] in ("-k", "--keyword") and i + 1 < len(args):
                        i += 2  # skip flag and its value
                    elif args[i].startswith(("-k=", "--keyword=")):
                        i += 1
                    elif not args[i].startswith("-"):
                        return True
                    else:
                        i += 1
                return False

            if not _has_test_module(test_args):
                typer.echo(
                    "⚠️  No test module specified — this will run the entire Django test suite.",
                    err=True,
                )
                typer.echo(
                    "    Tip: specify a module to narrow the run, e.g. dbx test django encryption_",
                    err=True,
                )
                if not yes:
                    confirm = typer.confirm("Continue?", default=False)
                    if not confirm:
                        typer.echo("Aborted.")
                        raise typer.Exit(0)

            has_settings = "--settings" in test_args or any(
                a.startswith("--settings=") for a in test_args
            )
            if not has_settings:
                test_args = ["--settings", "django_test.settings.django_test"] + list(
                    test_args
                )

        # Build test command
        if test_runner:
            # Use custom test runner (relative path from repo root)
            test_script = repo["path"] / test_runner
            if not test_script.exists():
                typer.echo(f"❌ Error: Test runner not found: {test_script}", err=True)
                raise typer.Exit(1)

            test_cmd = [python_path, str(test_script)]

            # Add default args from config, then user-supplied args
            all_runner_args = list(runner_default_args) + list(test_args)
            if all_runner_args:
                test_cmd.extend(all_runner_args)
                typer.echo(
                    f"Running {test_runner} {' '.join(all_runner_args)} in {repo['path']}..."
                )
            else:
                typer.echo(f"Running {test_runner} in {repo['path']}...")

            # Warn if -k/--keyword option is used with custom test runner
            if keyword:
                typer.echo(
                    "⚠️  Warning: -k/--keyword option not supported with custom test runner. Use test_args instead.",
                    err=True,
                )
        else:
            # Use default pytest
            test_cmd = [python_path, "-m", "pytest"]

            # Add test_args if provided
            if test_args:
                test_cmd.extend(test_args)

            # Add verbose flag if set
            if verbose and "-v" not in test_args and "--verbose" not in test_args:
                test_cmd.append("-v")

            # Add keyword filter if set
            if keyword:
                test_cmd.extend(["-k", keyword])
                typer.echo(f"Running pytest -k '{keyword}' in {repo['path']}...")
            elif test_args:
                typer.echo(f"Running pytest {' '.join(test_args)} in {repo['path']}...")
            else:
                typer.echo(f"Running pytest in {repo['path']}...")

        if venv_type == "group":
            typer.echo(f"Using group venv: {group_path}/.venv\n")
        elif venv_type == "venv":
            typer.echo(f"Using venv: {python_path}\n")

        # Get environment variables for test run
        test_env = os.environ.copy()
        env_vars = get_test_env_vars(config, repo["group"], repo_name, base_dir)

        if env_vars:
            test_env.update(env_vars)
            if verbose:
                typer.echo("[verbose] Environment variables:")
                for key, value in env_vars.items():
                    typer.echo(f"[verbose]   {key}={value}")
                typer.echo()

        # Check for default environment variables from project config
        default_env = config.get("project", {}).get("default_env", {})

        # Get CLI overrides from context
        backend_override = ctx.obj.get("mongodb_backend") if ctx.obj else None
        edition_override = ctx.obj.get("mongodb_edition") if ctx.obj else None

        # Ensure MongoDB is available (uses env, config, or starts mongodb-runner)
        test_env = ensure_mongodb(test_env, backend_override, edition_override)

        # For pymongo tests: parse MONGODB_URI and set DB_IP and DB_PORT
        # The pymongo test suite uses DB_IP and DB_PORT instead of MONGODB_URI
        if "MONGODB_URI" in test_env and "DB_IP" not in test_env:
            try:
                parsed = urlparse(test_env["MONGODB_URI"])
                if parsed.hostname:
                    test_env["DB_IP"] = parsed.hostname
                    if parsed.port:
                        test_env["DB_PORT"] = str(parsed.port)
                    else:
                        test_env["DB_PORT"] = "27017"  # Default MongoDB port
                    if verbose:
                        typer.echo(
                            f"[verbose] Set DB_IP={test_env['DB_IP']} and DB_PORT={test_env['DB_PORT']} from MONGODB_URI"
                        )
            except Exception as e:
                if verbose:
                    typer.echo(f"[verbose] Could not parse MONGODB_URI: {e}")

        # Check for libmongocrypt environment variables from project config
        for var in [
            "PYMONGOCRYPT_LIB",
            "DYLD_LIBRARY_PATH",
            "DYLD_FALLBACK_LIBRARY_PATH",
            "LD_LIBRARY_PATH",
            "CRYPT_SHARED_LIB_PATH",
        ]:
            if var not in test_env and var in default_env:
                value = os.path.expanduser(default_env[var])
                # For library file paths, check if the file exists
                if var in ["PYMONGOCRYPT_LIB", "CRYPT_SHARED_LIB_PATH"]:
                    if Path(value).exists():
                        test_env[var] = value
                        typer.echo(f"🔧 Using {var} from config: {value}")
                    # Skip warning - user may not need QE
                else:
                    # For library directory paths, set them even if directory doesn't exist yet
                    test_env[var] = value
                    typer.echo(f"🔧 Using {var} from config: {value}")

        if verbose:
            typer.echo(f"[verbose] Running command: {' '.join(test_cmd)}")
            typer.echo(f"[verbose] Working directory: {repo['path']}\n")

        # For the django repo: ensure django_test project exists and is importable
        if test_runner and repo_name == "django":
            django_test_path = base_dir / "projects" / "django_test"
            if not (django_test_path / "manage.py").exists():
                typer.echo("📦 django_test project not found, creating it...")
                try:
                    # Use auto_install=False so add_project can fall back to sys.executable
                    # (the dbx CLI's Python) for scaffolding. The test repo's venv doesn't
                    # have Django installed as a module - it IS the Django source.
                    add_project(
                        "django_test",
                        directory=None,
                        base_dir=None,
                        add_frontend=True,
                        auto_install=False,
                    )
                except typer.Exit as e:
                    if getattr(e, "exit_code", getattr(e, "code", 1)) != 0:
                        typer.echo("❌ Failed to create django_test project", err=True)
                        raise typer.Exit(1)
            # Add the project root to PYTHONPATH so Django can import the settings module
            existing = test_env.get("PYTHONPATH", "")
            test_env["PYTHONPATH"] = (
                f"{django_test_path}{os.pathsep}{existing}"
                if existing
                else str(django_test_path)
            )

        # Run test command in the repository
        result = subprocess.run(
            test_cmd,
            cwd=str(repo["path"]),
            env=test_env,
            check=False,
        )

        if result.returncode == 0:
            typer.echo(f"\n✅ Tests passed in {repo_name}")
        else:
            typer.echo(f"\n❌ Tests failed in {repo_name}", err=True)
            raise typer.Exit(result.returncode)

    except typer.Exit:
        # Re-raise typer.Exit to preserve the exit code
        raise
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)
