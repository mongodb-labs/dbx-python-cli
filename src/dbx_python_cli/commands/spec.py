"""Spec command for managing spec syncs with the MongoDB specifications repository."""

import filecmp
import os
import re
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


def _patch_dir_map(patch_dir: Path) -> dict[str, list[str]]:
    """Return {test_subdir: [ticket, ...]} for all active patches.

    Reads each .patch file, extracts the ``test/<subdir>/`` paths from diff
    headers, and builds a reverse map so callers can quickly find which
    patches touch a given spec directory.
    """
    result: dict[str, list[str]] = {}
    for patch_path in _list_patches(patch_dir):
        ticket = patch_path.stem
        for file_path in _parse_patch_files(patch_path):
            parts = file_path.split("/")
            if len(parts) >= 3 and parts[0] == "test":
                subdir = parts[1]
                result.setdefault(subdir, [])
                if ticket not in result[subdir]:
                    result[subdir].append(ticket)
    return result


def _show_patch_summary(driver_repo, verbose: bool = False) -> int:
    """Print a summary of active patches with the spec dirs each covers. Returns patch count."""
    patch_dir = _get_patch_dir(driver_repo)
    patches = _list_patches(patch_dir)
    if not patches:
        return 0
    typer.echo(f"\n📋 {len(patches)} active patch(es) in {driver_repo['name']}:")
    for p in patches:
        ticket = p.stem
        files = _parse_patch_files(p)
        subdirs = sorted(
            {
                parts[1]
                for f in files
                for parts in [f.split("/")]
                if len(parts) >= 3 and parts[0] == "test"
            }
        )
        dirs_str = f"  → {', '.join(subdirs)}" if subdirs else ""
        if verbose:
            typer.echo(f"  • {ticket} ({len(files)} file(s)){dirs_str}:")
            for f in files:
                typer.echo(f"      {f}")
        else:
            typer.echo(f"  • {ticket} ({len(files)} file(s)){dirs_str}")
    typer.echo(
        "\n  ⚠  After syncing any of the above spec dirs, run: dbx spec patch apply"
    )
    return len(patches)


def _apply_patches(driver_repo, verbose: bool = False) -> bool:
    """Run git apply -R on all patch files. Returns True on success.

    Checks applicability first and gives a clear error if patches appear to be
    already applied (i.e. the test files have already been modified).
    """
    patch_dir = _get_patch_dir(driver_repo)
    patches = _list_patches(patch_dir)
    if not patches:
        typer.echo("  No patches to apply.")
        return True

    # Dry-run first so we can give a helpful error instead of a raw git failure
    check_result = subprocess.run(
        ["git", "apply", "-R", "--check", "--allow-empty", *[str(p) for p in patches]],
        cwd=str(driver_repo["path"]),
        check=False,
        capture_output=True,
        text=True,
    )
    if check_result.returncode != 0:
        typer.echo(
            "❌ Patches cannot be applied — they may already be applied.", err=True
        )
        typer.echo(
            "   Run 'dbx spec sync <spec> --apply-patches' to reset and re-apply in one shot.",
            err=True,
        )
        if verbose:
            typer.echo(check_result.stderr.strip(), err=True)
        return False

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
# dbx spec status helpers
# ---------------------------------------------------------------------------


def _join_continuations(text: str) -> list[str]:
    """Merge shell line-continuations into single logical lines."""
    lines: list[str] = []
    buf = ""
    for line in text.splitlines():
        if line.rstrip().endswith("\\"):
            buf += line.rstrip()[:-1] + " "
        else:
            lines.append(buf + line)
            buf = ""
    if buf:
        lines.append(buf)
    return lines


def _parse_resync_script(script_path: Path) -> dict[str, list[tuple[str, str]]]:
    """Parse resync-specs.sh and return {canonical_name: [(specs_src, driver_dst), ...]}.

    The canonical name is the first label in each case branch (before any ``|``).
    Paths have trailing slashes stripped.
    """
    try:
        text = script_path.read_text()
    except OSError:
        return {}

    spec_map: dict[str, list[tuple[str, str]]] = {}
    logical_lines = _join_continuations(text)

    in_for = False
    current_canonical: str | None = None
    current_calls: list[tuple[str, str]] = []

    for line in logical_lines:
        stripped = line.strip()

        # Enter the 'for spec in "$@"' loop
        if 'for spec in "$@"' in line:
            in_for = True
            continue

        if not in_for:
            continue

        # Case label: "  auth)" or "  bson-binary-vector|bson_binary_vector)"
        # Must end with ) but not be 'case ...' or '*)'
        if (
            stripped.endswith(")")
            and not stripped.startswith("case ")
            and not stripped.startswith("*")
            and not stripped.startswith("#")
        ):
            labels_str = stripped.rstrip(")")
            current_canonical = labels_str.split("|")[0]
            current_calls = []
            continue

        # End of case block
        if stripped == ";;":
            if current_canonical and current_calls:
                spec_map[current_canonical] = current_calls
            current_canonical = None
            current_calls = []
            continue

        # cpjson call inside a block
        if current_canonical and stripped.startswith("cpjson "):
            parts = stripped.split()
            if len(parts) >= 3:
                src = parts[1].rstrip("/")
                dst = parts[2].rstrip("/")
                current_calls.append((src, dst))

    return spec_map


def _get_current_branch(repo_path: Path) -> str:
    result = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=repo_path,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() or "HEAD (detached)"


def _find_recent_resync_commits(repo_path: Path, n: int = 5) -> list[str]:
    """Return up to *n* recent commits whose subject mentions 'resync'."""
    result = subprocess.run(
        [
            "git",
            "log",
            "--oneline",
            "--max-count=100",
            "--grep=resync",
            "--regexp-ignore-case",
        ],
        cwd=repo_path,
        capture_output=True,
        text=True,
        check=False,
    )
    lines = [ln.strip() for ln in result.stdout.splitlines() if ln.strip()]
    return lines[:n]


def _commit_relative_date(repo_path: Path, commit_sha: str) -> str:
    """Return a human-readable relative date for a commit (e.g. '3 days ago')."""
    result = subprocess.run(
        ["git", "log", "-1", "--format=%ar", commit_sha],
        cwd=repo_path,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() or "unknown"


def _commit_spec_dirs(repo_path: Path, commit_sha: str) -> list[str]:
    """Return sorted unique top-level test subdirectory names changed in a commit.

    Runs ``git diff-tree`` on the commit and extracts the first path component
    under ``test/``, giving the spec directory names that were actually modified.
    """
    result = subprocess.run(
        ["git", "diff-tree", "--no-commit-id", "-r", "--name-only", commit_sha],
        cwd=repo_path,
        capture_output=True,
        text=True,
        check=False,
    )
    dirs: set[str] = set()
    for line in result.stdout.splitlines():
        parts = line.strip().split("/")
        # Require test/<subdir>/<file> — excludes files sitting directly in test/
        if len(parts) >= 3 and parts[0] == "test":
            dirs.add(parts[1])
    return sorted(dirs)


def _branch_summary(repo_path: Path) -> tuple[list[str], int]:
    """Return (sorted spec dirs touched, commit count) for commits on this branch vs main.

    Tries ``origin/main``, ``upstream/main``, ``main`` in that order as the base.
    Returns ([], 0) if none can be resolved.
    """
    for base in ("origin/main", "upstream/main", "main", "master"):
        result = subprocess.run(
            ["git", "log", "--format=%H", f"{base}..HEAD"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            shas = result.stdout.strip().splitlines()
            all_dirs: set[str] = set()
            for sha in shas:
                all_dirs.update(_commit_spec_dirs(repo_path, sha.strip()))
            return sorted(all_dirs), len(shas)
    return [], 0


def _spec_is_stale(
    specs_source: Path,
    driver_test: Path,
    mappings: list[tuple[str, str]],
) -> tuple[bool, str]:
    """Check staleness for a spec's cpjson mappings.

    Returns ``(is_stale, reason_string)``.  Only JSON files are compared
    (matching what resync-specs.sh copies).
    """
    for spec_dir, driver_dir in mappings:
        src = specs_source / spec_dir
        dst = driver_test / driver_dir

        if not src.exists():
            continue  # specs repo doesn't have this dir; skip

        if not dst.exists():
            return True, f"test dir '{driver_dir}' missing in driver repo"

        src_files = {f.relative_to(src): f for f in src.rglob("*.json")}
        dst_files = {f.relative_to(dst): f for f in dst.rglob("*.json")}

        new_in_src = src_files.keys() - dst_files.keys()
        if new_in_src:
            return True, f"{len(new_in_src)} new file(s) in specs not in driver"

        for rel, src_file in src_files.items():
            if rel in dst_files and not filecmp.cmp(
                str(src_file), str(dst_files[rel]), shallow=False
            ):
                return True, f"content differs: {rel}"

    return False, ""


# ---------------------------------------------------------------------------
# dbx spec status
# ---------------------------------------------------------------------------


@app.command("status")
def spec_status(
    ctx: typer.Context,
    repo_name: str = typer.Option(
        "mongo-python-driver",
        "--repo",
        "-r",
        help="Driver repository to inspect",
    ),
    specs_dir: str = typer.Option(
        None,
        "--specs-dir",
        help="Path to the MongoDB specifications repo (overrides auto-detection)",
    ),
):
    """Show which specs are out of date and suggest sync commands.

    Compares JSON test files in the driver repo against the specifications
    repository and lists any specs whose files differ.  Also checks whether
    the current branch looks like a spec-resync branch and whether a recent
    resync commit exists.

    Usage::

        dbx spec status
        dbx spec status -r django-mongodb-backend
        dbx spec status --specs-dir ~/my-specs
    """
    verbose = ctx.obj.get("verbose", False) if ctx.obj else False
    config = get_config()
    base_dir = get_base_dir(config)

    driver_repo = _get_driver_repo(repo_name, base_dir, config)
    driver_path: Path = driver_repo["path"]
    driver_test = driver_path / "test"

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

    specs_source = mdb_specs / "source"
    if not specs_source.exists():
        specs_source = mdb_specs  # some layouts skip the 'source' subdir

    script = driver_path / ".evergreen" / "resync-specs.sh"
    if not script.exists():
        typer.echo(f"❌ Error: resync-specs.sh not found at {script}", err=True)
        raise typer.Exit(1)

    # --- Header ------------------------------------------------------------ #
    branch = _get_current_branch(driver_path)
    branch_looks_spec = bool(re.search(r"resync|spec", branch, re.IGNORECASE))
    branch_icon = "✓" if branch_looks_spec else "⚠"
    typer.echo(f"\n📊 Spec Status — {repo_name}\n")
    typer.echo(f"  🌿 Branch: {branch} {branch_icon}")
    if not branch_looks_spec:
        typer.echo(
            "     ⚠  Branch name does not look like a spec-resync branch.",
            err=True,
        )

    recent = _find_recent_resync_commits(driver_path)
    if recent:
        sha = recent[0].split()[0]
        age = _commit_relative_date(driver_path, sha)
        typer.echo(f"  🕐 Last resync commit: {recent[0]} ({age})")
        spec_dirs = _commit_spec_dirs(driver_path, sha)
        if spec_dirs:
            typer.echo(f"     Specs touched: {', '.join(spec_dirs)}")
        if verbose and len(recent) > 1:
            for c in recent[1:]:
                c_sha = c.split()[0]
                c_age = _commit_relative_date(driver_path, c_sha)
                c_dirs = _commit_spec_dirs(driver_path, c_sha)
                dirs_str = f" — {', '.join(c_dirs)}" if c_dirs else ""
                typer.echo(f"              also: {c} ({c_age}){dirs_str}")
    else:
        typer.echo("  ⚠  No resync commit found on this branch.", err=True)

    # --- Branch summary (what this PR has done so far) --------------------- #
    branch_dirs, branch_commit_count = _branch_summary(driver_path)
    if branch_commit_count:
        commit_word = "commit" if branch_commit_count == 1 else "commits"
        typer.echo(
            f"\n  📝 PR summary ({branch_commit_count} {commit_word} ahead of main):"
        )
        if branch_dirs:
            typer.echo(f"     Specs synced so far: {', '.join(branch_dirs)}")
        else:
            typer.echo("     No test/ files changed yet on this branch.")

    # --- Parse spec map ---------------------------------------------------- #
    spec_map = _parse_resync_script(script)
    if not spec_map:
        typer.echo("\n⚠  Could not parse resync-specs.sh — no spec mappings found.")
        raise typer.Exit(1)

    typer.echo(f"\n  Checking {len(spec_map)} spec(s) against {specs_source}...\n")

    stale: list[tuple[str, str]] = []  # (spec_name, reason)
    up_to_date: list[str] = []
    skipped: list[str] = []

    for spec_name, mappings in sorted(spec_map.items()):
        # Check that at least one source dir actually exists; skip if not
        any_src_exists = any((specs_source / src).exists() for src, _ in mappings)
        if not any_src_exists:
            skipped.append(spec_name)
            if verbose:
                typer.echo(f"  [skip] {spec_name} — source dir not found in specs repo")
            continue

        is_stale, reason = _spec_is_stale(specs_source, driver_test, mappings)
        if is_stale:
            stale.append((spec_name, reason))
        else:
            up_to_date.append(spec_name)

    # --- Build patch→dir map before output --------------------------------- #
    patch_dir_lookup = _patch_dir_map(_get_patch_dir(driver_repo))
    # reverse: spec_driver_dir → patch tickets that cover it
    dir_to_patches: dict[str, list[str]] = patch_dir_lookup

    # For each spec_name, collect the driver dirs it maps to
    def _patches_for_spec(spec_name: str) -> list[str]:
        tickets: list[str] = []
        for _, driver_dir in spec_map.get(spec_name, []):
            for t in dir_to_patches.get(driver_dir, []):
                if t not in tickets:
                    tickets.append(t)
        return tickets

    # --- Output ------------------------------------------------------------ #
    if stale:
        typer.echo(f"  ❌ Still needs syncing ({len(stale)}):\n")
        for i, (name, reason) in enumerate(stale):
            is_last = i == len(stale) - 1
            prefix = "  └──" if is_last else "  ├──"
            reason_str = f"  [{reason}]" if verbose else ""
            tickets = _patches_for_spec(name)
            patch_str = f"  🩹 {', '.join(tickets)}" if tickets else ""
            typer.echo(f"{prefix} dbx spec sync {name}{reason_str}{patch_str}")
        if any(_patches_for_spec(n) for n, _ in stale):
            typer.echo(
                "\n  🩹 = has an active patch — use --apply-patches to sync + patch in one shot"
            )
    else:
        typer.echo("  ✅ All checked specs are up to date.")

    if up_to_date:
        typer.echo(f"\n  ✅ Up to date ({len(up_to_date)}): " + ", ".join(up_to_date))

    if skipped:
        typer.echo(
            f"\n  ⚠  Skipped ({len(skipped)}, source dir not found): "
            + ", ".join(skipped)
        )

    # --- Patches ----------------------------------------------------------- #
    patch_count = _show_patch_summary(driver_repo, verbose)

    # --- What to do next --------------------------------------------------- #
    typer.echo("\n  🔍 To verify locally:\n")
    step = 1
    if stale:
        spec_names = " ".join(name for name, _ in stale)
        any_patched = any(_patches_for_spec(n) for n, _ in stale)
        if any_patched and patch_count:
            # --apply-patches is idempotent: sync resets files, then patches apply fresh
            typer.echo(
                f"     {step}. Sync and re-apply patches in one shot (recommended):"
            )
            typer.echo(f"        dbx spec sync {spec_names} --apply-patches")
            typer.echo(
                "        # equivalent to sync + 'dbx spec patch apply', but always safe to re-run"
            )
        else:
            typer.echo(f"     {step}. Sync remaining specs:")
            typer.echo(f"        dbx spec sync {spec_names}")
        step += 1
        if patch_count and not any_patched:
            typer.echo(f"     {step}. Re-apply patches (removes unimplemented tests):")
            typer.echo("        dbx spec patch apply")
            typer.echo(
                "        # ⚠  not idempotent — run sync first if patches are already applied"
            )
            step += 1
    elif patch_count:
        typer.echo(f"     {step}. Re-apply patches (removes unimplemented tests):")
        typer.echo("        dbx spec patch apply")
        typer.echo(
            "        # ⚠  not idempotent — run sync first if patches are already applied"
        )
        step += 1
    if branch_dirs:
        test_dirs = " ".join(f"test/{d}/" for d in branch_dirs[:5])
        ellipsis = " ..." if len(branch_dirs) > 5 else ""
        typer.echo(f"     {step}. Run tests for synced specs:")
        typer.echo(f"        python -m pytest {test_dirs}{ellipsis}")
        step += 1
    if not stale and not patch_count:
        typer.echo("     ✅ Nothing outstanding — branch looks complete.\n")
    else:
        typer.echo("")


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
