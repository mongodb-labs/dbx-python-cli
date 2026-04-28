"""Spec command for managing spec syncs with the MongoDB specifications repository."""

import os
import subprocess
from pathlib import Path

import typer

from dbx_python_cli.utils.repo import (
    find_repo_by_name,
    get_base_dir,
    get_config,
)

app = typer.Typer(
    help="Manage spec syncs with the MongoDB specifications repository",
    no_args_is_help=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)

patch_app = typer.Typer(
    help="Manage .evergreen/spec-patch files for unimplemented spec tests",
    no_args_is_help=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)
app.add_typer(patch_app, name="patch")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _find_specs_dir(config, base_dir) -> Path | None:
    """Find the specifications repo directory via the repo config."""
    repo = find_repo_by_name("specifications", base_dir, config)
    if repo:
        return repo["path"]
    return None


def _get_driver_repo(repo_name: str, base_dir, config):
    """Return the driver repo dict or exit with an error."""
    repo = find_repo_by_name(repo_name, base_dir, config)
    if not repo:
        typer.echo(f"❌ Error: Repository '{repo_name}' not found", err=True)
        typer.echo("\nUse 'dbx list' to see available repositories")
        raise typer.Exit(1)
    return repo


def _get_patch_dir(driver_repo) -> Path:
    return driver_repo["path"] / ".evergreen" / "spec-patch"


def _parse_patch_files(patch_path: Path) -> list[str]:
    """Return the list of file paths mentioned in a patch diff header."""
    files = []
    for line in patch_path.read_text().splitlines():
        if line.startswith("diff --git "):
            # "diff --git a/test/foo.json b/test/foo.json" -> "test/foo.json"
            parts = line.split(" ")
            if len(parts) >= 4:
                files.append(parts[2].removeprefix("a/"))
    return files


def _list_patches(patch_dir: Path) -> list[Path]:
    """Return sorted list of patch files in patch_dir."""
    if not patch_dir.exists():
        return []
    return sorted(patch_dir.glob("*.patch"))


def _show_patch_summary(driver_repo, verbose: bool = False) -> int:
    """Print a summary of active patches. Returns the patch count."""
    patch_dir = _get_patch_dir(driver_repo)
    patches = _list_patches(patch_dir)
    if not patches:
        return 0
    typer.echo(f"\n📋 {len(patches)} active patch(es) in {driver_repo['name']}:")
    for p in patches:
        ticket = p.stem
        files = _parse_patch_files(p)
        if verbose:
            typer.echo(f"  • {ticket} ({len(files)} file(s)):")
            for f in files:
                typer.echo(f"      {f}")
        else:
            typer.echo(f"  • {ticket} ({len(files)} file(s))")
    typer.echo("\n  Run 'dbx spec patch apply' to apply them.")
    return len(patches)


def _apply_patches(driver_repo, verbose: bool = False) -> bool:
    """Run git apply -R on all patch files. Returns True on success."""
    patch_dir = _get_patch_dir(driver_repo)
    patches = _list_patches(patch_dir)
    if not patches:
        typer.echo("  No patches to apply.")
        return True

    cmd = [
        "git",
        "apply",
        "-R",
        "--allow-empty",
        "--whitespace=fix",
        *[str(p) for p in patches],
    ]
    if verbose:
        typer.echo(f"[verbose] Running: {' '.join(cmd)}")

    result = subprocess.run(
        cmd, cwd=str(driver_repo["path"]), check=False, capture_output=True, text=True
    )
    if result.returncode != 0:
        typer.echo(f"❌ Failed to apply patches: {result.stderr.strip()}", err=True)
        return False
    return True


# ---------------------------------------------------------------------------
# dbx spec sync
# ---------------------------------------------------------------------------


@app.command("sync")
def spec_sync(
    ctx: typer.Context,
    specs: list[str] = typer.Argument(
        None,
        help="Spec names to sync (e.g., crud transactions). Syncs all if omitted.",
    ),
    repo_name: str = typer.Option(
        "mongo-python-driver",
        "--repo",
        "-r",
        help="Driver repository whose .evergreen/resync-specs.sh will be run",
    ),
    block: str = typer.Option(
        None,
        "--block",
        "-b",
        help="Regex pattern passed to resync-specs.sh -b to exclude matching files",
    ),
    specs_dir: str = typer.Option(
        None,
        "--specs-dir",
        help="Path to the MongoDB specifications repo (overrides auto-detection)",
    ),
    apply_patches: bool = typer.Option(
        False,
        "--apply-patches",
        help="Apply all .evergreen/spec-patch files after syncing",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Print the command that would be run without executing it",
    ),
):
    """Sync spec tests from the MongoDB specifications repository.

    Runs .evergreen/resync-specs.sh inside the driver repo with MDB_SPECS set
    to the path of the specifications repository. Active patch files are shown
    after syncing; use --apply-patches to apply them in one shot.

    Usage::

        dbx spec sync                              # Sync all specs
        dbx spec sync crud transactions            # Sync specific specs
        dbx spec sync crud -b "unified"            # Block files matching regex
        dbx spec sync -r django-mongodb-backend    # Target a different driver repo
        dbx spec sync crud --apply-patches         # Sync and apply patches
        dbx spec sync crud --dry-run               # Preview without running

    Examples::

        dbx spec sync
        dbx spec sync crud sessions change-streams
        dbx spec sync crud -b "unified"
        dbx spec sync --specs-dir ~/my-specs crud
        dbx spec sync crud --apply-patches
    """
    verbose = ctx.obj.get("verbose", False) if ctx.obj else False
    config = get_config()
    base_dir = get_base_dir(config)

    driver_repo = _get_driver_repo(repo_name, base_dir, config)

    if specs_dir:
        mdb_specs = Path(specs_dir).expanduser().resolve()
    else:
        mdb_specs = _find_specs_dir(config, base_dir)
        if not mdb_specs:
            typer.echo(
                "❌ Error: Could not find the 'specifications' repository", err=True
            )
            typer.echo("\nClone it with: dbx clone specifications")
            typer.echo("Or specify the path with: --specs-dir <path>")
            raise typer.Exit(1)

    if not mdb_specs.exists():
        typer.echo(
            f"❌ Error: Specifications directory not found: {mdb_specs}", err=True
        )
        raise typer.Exit(1)

    script = driver_repo["path"] / ".evergreen" / "resync-specs.sh"
    if not script.exists():
        typer.echo(f"❌ Error: resync-specs.sh not found at {script}", err=True)
        typer.echo(
            "\nIs this a driver repository with a .evergreen/resync-specs.sh script?",
            err=True,
        )
        raise typer.Exit(1)

    cmd = [str(script)]
    if block:
        cmd.extend(["-b", block])
    if specs:
        cmd.extend(specs)

    cwd = driver_repo["path"] / ".evergreen"
    env = {**os.environ, "MDB_SPECS": str(mdb_specs)}

    if verbose:
        typer.echo(f"[verbose] MDB_SPECS={mdb_specs}")
        typer.echo(f"[verbose] Command: {' '.join(cmd)}")
        typer.echo(f"[verbose] Working directory: {cwd}\n")

    if dry_run:
        typer.echo(f"🔍 Would run: MDB_SPECS={mdb_specs} {' '.join(cmd)}")
        typer.echo(f"   Working directory: {cwd}")
        patch_count = len(_list_patches(_get_patch_dir(driver_repo)))
        if patch_count:
            typer.echo(
                f"\n📋 {patch_count} patch(es) would be applied with --apply-patches"
            )
        return

    spec_label = ", ".join(specs) if specs else "all"
    typer.echo(f"🔄 Syncing specs ({spec_label}) for {repo_name}...")

    result = subprocess.run(cmd, cwd=str(cwd), env=env, check=False)
    if result.returncode != 0:
        raise typer.Exit(result.returncode)

    typer.echo("\n✅ Spec sync complete!")

    if apply_patches:
        typer.echo("\n🩹 Applying patches...")
        if not _apply_patches(driver_repo, verbose):
            raise typer.Exit(1)
        typer.echo("✅ Patches applied.")
    else:
        _show_patch_summary(driver_repo, verbose)


# ---------------------------------------------------------------------------
# dbx spec list
# ---------------------------------------------------------------------------


@app.command("list")
def spec_list(
    ctx: typer.Context,
    specs_dir: str = typer.Option(
        None,
        "--specs-dir",
        help="Path to the MongoDB specifications repo (overrides auto-detection)",
    ),
):
    """List available specs in the MongoDB specifications repository.

    Usage::

        dbx spec list
        dbx spec list --specs-dir ~/my-specs
    """
    verbose = ctx.obj.get("verbose", False) if ctx.obj else False
    config = get_config()
    base_dir = get_base_dir(config)

    if specs_dir:
        mdb_specs = Path(specs_dir).expanduser().resolve()
    else:
        mdb_specs = _find_specs_dir(config, base_dir)
        if not mdb_specs:
            typer.echo(
                "❌ Error: Could not find the 'specifications' repository", err=True
            )
            typer.echo("\nClone it with: dbx clone specifications")
            typer.echo("Or specify the path with: --specs-dir <path>")
            raise typer.Exit(1)

    if not mdb_specs.exists():
        typer.echo(
            f"❌ Error: Specifications directory not found: {mdb_specs}", err=True
        )
        raise typer.Exit(1)

    source_dir = mdb_specs / "source"
    search_dir = source_dir if source_dir.exists() else mdb_specs

    if verbose:
        typer.echo(f"[verbose] Listing specs in: {search_dir}\n")

    spec_dirs = sorted(
        d.name
        for d in search_dir.iterdir()
        if d.is_dir() and not d.name.startswith(".")
    )

    if not spec_dirs:
        typer.echo(f"No spec directories found in {search_dir}", err=True)
        raise typer.Exit(1)

    typer.echo(f"Specs in {mdb_specs}:\n")
    for i, name in enumerate(spec_dirs):
        is_last = i == len(spec_dirs) - 1
        prefix = "└──" if is_last else "├──"
        typer.echo(f"{prefix} {name}")


# ---------------------------------------------------------------------------
# dbx spec patch list
# ---------------------------------------------------------------------------


@patch_app.command("list")
def patch_list(
    ctx: typer.Context,
    repo_name: str = typer.Option(
        "mongo-python-driver",
        "--repo",
        "-r",
        help="Driver repository to inspect",
    ),
):
    """List active spec patch files and the test files each one affects.

    Usage::

        dbx spec patch list
        dbx spec patch list -r django-mongodb-backend
    """
    verbose = ctx.obj.get("verbose", False) if ctx.obj else False
    config = get_config()
    base_dir = get_base_dir(config)

    driver_repo = _get_driver_repo(repo_name, base_dir, config)
    patch_dir = _get_patch_dir(driver_repo)
    patches = _list_patches(patch_dir)

    if not patches:
        typer.echo(f"No patch files found in {patch_dir}")
        return

    typer.echo(f"Active patches in {driver_repo['name']} ({len(patches)}):\n")
    for i, p in enumerate(patches):
        is_last = i == len(patches) - 1
        prefix = "└──" if is_last else "├──"
        files = _parse_patch_files(p)
        typer.echo(f"{prefix} {p.stem}  ({len(files)} file(s))")
        if verbose:
            continuation = "    " if is_last else "│   "
            for f in files:
                typer.echo(f"{continuation}  {f}")


# ---------------------------------------------------------------------------
# dbx spec patch create
# ---------------------------------------------------------------------------


@patch_app.command("create")
def patch_create(
    ctx: typer.Context,
    ticket: str = typer.Argument(
        ...,
        help="JIRA ticket ID (e.g. PYTHON-1234)",
    ),
    files: list[str] = typer.Argument(
        None,
        help="Files to include in the patch. Uses all unstaged changes if omitted.",
    ),
    repo_name: str = typer.Option(
        "mongo-python-driver",
        "--repo",
        "-r",
        help="Driver repository to create the patch in",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show the diff that would be saved without writing the file",
    ),
):
    """Create a spec patch file from the current git diff.

    Captures unstaged changes (or specific files) into
    .evergreen/spec-patch/<ticket>.patch so they can be reversed after each
    spec sync via 'dbx spec patch apply'.

    Usage::

        dbx spec patch create PYTHON-1234
        dbx spec patch create PYTHON-1234 test/crud/foo.json
        dbx spec patch create PYTHON-1234 --dry-run

    Typical workflow::

        dbx spec sync crud                      # sync brings in new tests
        # edit/revert the tests you don't want  # or let git diff show them
        dbx spec patch create PYTHON-1234       # capture the diff as a patch
        dbx spec patch apply                    # apply immediately
    """
    verbose = ctx.obj.get("verbose", False) if ctx.obj else False
    config = get_config()
    base_dir = get_base_dir(config)

    driver_repo = _get_driver_repo(repo_name, base_dir, config)
    patch_dir = _get_patch_dir(driver_repo)
    patch_path = patch_dir / f"{ticket}.patch"

    if patch_path.exists() and not dry_run:
        typer.echo(f"⚠️  Patch file already exists: {patch_path}", err=True)
        typer.echo("Remove it first with: dbx spec patch remove " + ticket, err=True)
        raise typer.Exit(1)

    diff_cmd = ["git", "diff", "--", *(files or [])]
    if verbose:
        typer.echo(f"[verbose] Running: {' '.join(diff_cmd)}")

    result = subprocess.run(
        diff_cmd,
        cwd=str(driver_repo["path"]),
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        typer.echo(f"❌ git diff failed: {result.stderr.strip()}", err=True)
        raise typer.Exit(1)

    diff = result.stdout
    if not diff.strip():
        typer.echo("❌ No changes to capture (git diff is empty)", err=True)
        typer.echo(
            "\nMake sure you have unstaged changes in the driver repo after syncing."
        )
        raise typer.Exit(1)

    if dry_run:
        typer.echo(f"🔍 Would write to: {patch_path}\n")
        typer.echo(diff)
        return

    patch_dir.mkdir(parents=True, exist_ok=True)
    patch_path.write_text(diff)
    files_affected = _parse_patch_files(patch_path)
    typer.echo(f"✅ Created {patch_path.name} ({len(files_affected)} file(s))")
    if verbose:
        for f in files_affected:
            typer.echo(f"   {f}")
    typer.echo("\n  Run 'dbx spec patch apply' to apply it now.")


# ---------------------------------------------------------------------------
# dbx spec patch remove
# ---------------------------------------------------------------------------


@patch_app.command("remove")
def patch_remove(
    ctx: typer.Context,
    ticket: str = typer.Argument(
        ...,
        help="JIRA ticket ID to remove (e.g. PYTHON-1234)",
    ),
    repo_name: str = typer.Option(
        "mongo-python-driver",
        "--repo",
        "-r",
        help="Driver repository to remove the patch from",
    ),
):
    """Remove a spec patch file once the corresponding ticket is implemented.

    Usage::

        dbx spec patch remove PYTHON-1234
        dbx spec patch remove PYTHON-1234 -r django-mongodb-backend
    """
    config = get_config()
    base_dir = get_base_dir(config)

    driver_repo = _get_driver_repo(repo_name, base_dir, config)
    patch_path = _get_patch_dir(driver_repo) / f"{ticket}.patch"

    if not patch_path.exists():
        typer.echo(f"❌ Patch file not found: {patch_path}", err=True)
        typer.echo("\nRun 'dbx spec patch list' to see active patches.")
        raise typer.Exit(1)

    files_affected = _parse_patch_files(patch_path)
    patch_path.unlink()
    typer.echo(f"✅ Removed {ticket}.patch ({len(files_affected)} file(s) affected)")


# ---------------------------------------------------------------------------
# dbx spec patch apply
# ---------------------------------------------------------------------------


@patch_app.command("apply")
def patch_apply(
    ctx: typer.Context,
    repo_name: str = typer.Option(
        "mongo-python-driver",
        "--repo",
        "-r",
        help="Driver repository to apply patches in",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show which patches would be applied without running git apply",
    ),
):
    """Apply all spec patch files with git apply -R.

    Reverses the diff in each .evergreen/spec-patch/*.patch file to exclude
    tests for unimplemented features, matching what resync-all-specs.py does
    automatically in CI.

    Usage::

        dbx spec patch apply
        dbx spec patch apply -r django-mongodb-backend
        dbx spec patch apply --dry-run
    """
    verbose = ctx.obj.get("verbose", False) if ctx.obj else False
    config = get_config()
    base_dir = get_base_dir(config)

    driver_repo = _get_driver_repo(repo_name, base_dir, config)
    patch_dir = _get_patch_dir(driver_repo)
    patches = _list_patches(patch_dir)

    if not patches:
        typer.echo(f"No patch files found in {patch_dir}")
        return

    typer.echo(
        f"🩹 {'Would apply' if dry_run else 'Applying'} {len(patches)} patch(es) to {repo_name}:"
    )
    for p in patches:
        files = _parse_patch_files(p)
        typer.echo(f"  • {p.stem} ({len(files)} file(s))")

    if dry_run:
        return

    typer.echo("")
    if not _apply_patches(driver_repo, verbose):
        raise typer.Exit(1)
    typer.echo("✅ All patches applied.")
