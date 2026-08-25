"""Manage git worktrees so one clone can serve fork and upstream development."""

import typer

from dbx_python_cli.utils.repo import (
    find_repo_by_name,
    get_base_dir,
    get_config,
    is_flat_mode,
)
from dbx_python_cli.utils.worktree import (
    UPSTREAM_LABEL,
    add_worktree,
    branch_to_label,
    get_remote_head_branch,
    get_worktree_dir,
    has_remote,
    list_worktrees,
    remove_worktree,
)

app = typer.Typer(
    help="Manage git worktrees for a repository",
    context_settings={"help_option_names": ["-h", "--help"]},
)


def _resolve_repo(repo_name, config, verbose):
    """Locate a cloned repo by name, reporting and exiting when it is missing."""
    base_dir = get_base_dir(config)
    repo = find_repo_by_name(repo_name, base_dir, config)
    if not repo:
        typer.echo(f"❌ Repository '{repo_name}' not found in {base_dir}", err=True)
        raise typer.Exit(1)
    if repo.get("worktree"):
        typer.echo(
            f"❌ '{repo_name}' is itself a worktree. Run this against the primary clone.",
            err=True,
        )
        raise typer.Exit(1)
    if verbose:
        typer.echo(f"  [verbose] Repo path: {repo['path']}")
    return repo, base_dir


def create_upstream_worktree(repo_path, repo_name, group, config, verbose=False):
    """Create the ``<repo>-upstream`` worktree for a freshly cloned fork.

    Shared with ``dbx clone`` so the ``upstream_worktree`` config key and the
    ``dbx worktree add --upstream`` flag behave identically.

    The worktree checks out a local branch named ``upstream-<default branch>``
    rather than the bare default branch name, so it cannot collide with a
    same-named branch already tracking ``origin`` in the fork.

    Args:
        repo_path: Path to the primary clone
        repo_name: Repository name
        group: Group the repo belongs to
        config: Configuration dictionary
        verbose: Print git invocations

    Returns:
        tuple: ``(ok, message)`` — *message* explains the failure when not ok.
    """
    if not has_remote(repo_path, "upstream"):
        return False, "no 'upstream' remote configured"

    upstream_branch = get_remote_head_branch(repo_path, "upstream", verbose=verbose)
    if not upstream_branch:
        return False, "could not determine the upstream default branch"

    base_dir = get_base_dir(config)
    flat = is_flat_mode(config)
    worktree_path = get_worktree_dir(
        base_dir, group, repo_name, label=UPSTREAM_LABEL, flat=flat
    )
    if worktree_path.exists():
        return False, f"{worktree_path} already exists"

    local_branch = f"{UPSTREAM_LABEL}-{branch_to_label(upstream_branch)}"
    ok, message = add_worktree(
        repo_path,
        worktree_path,
        local_branch,
        start_point=f"upstream/{upstream_branch}",
        verbose=verbose,
    )
    if not ok:
        return False, message
    return True, f"{worktree_path} on {local_branch} (upstream/{upstream_branch})"


@app.command("add")
def worktree_add(
    ctx: typer.Context,
    repo_name: str = typer.Argument(..., help="Repository to add a worktree to"),
    branch: str = typer.Argument(
        None,
        help="Branch to check out. Omit with --upstream to use the upstream default branch.",
    ),
    upstream: bool = typer.Option(
        False,
        "--upstream",
        "-u",
        help="Create a worktree tracking the upstream remote's default branch",
    ),
    label: str = typer.Option(
        None,
        "--label",
        "-l",
        help="Directory suffix for the worktree (defaults to the branch name)",
    ),
):
    """Add a worktree so another branch is checked out alongside the main clone."""
    verbose = ctx.obj.get("verbose", False) if ctx.obj else False
    config = get_config()

    if not upstream and not branch:
        typer.echo("❌ Provide a branch, or pass --upstream.", err=True)
        raise typer.Exit(1)

    repo, base_dir = _resolve_repo(repo_name, config, verbose)

    if upstream and not branch:
        ok, message = create_upstream_worktree(
            repo["path"], repo["name"], repo["group"], config, verbose
        )
        if not ok:
            typer.echo(f"❌ {repo_name}: {message}", err=True)
            raise typer.Exit(1)
        typer.echo(f"✅ {repo_name}: worktree added at {message}")
        return

    # Explicit branch: create it from upstream when --upstream is combined with
    # a branch name, otherwise check out the existing local/remote branch.
    start_point = None
    if upstream:
        if not has_remote(repo["path"], "upstream"):
            typer.echo(f"❌ {repo_name}: no 'upstream' remote configured", err=True)
            raise typer.Exit(1)
        start_point = f"upstream/{branch}"

    worktree_path = get_worktree_dir(
        base_dir,
        repo["group"],
        repo["name"],
        label=label or branch_to_label(branch),
        flat=is_flat_mode(config),
    )
    if worktree_path.exists():
        typer.echo(f"❌ {repo_name}: {worktree_path} already exists", err=True)
        raise typer.Exit(1)

    ok, message = add_worktree(
        repo["path"], worktree_path, branch, start_point=start_point, verbose=verbose
    )
    if not ok:
        typer.echo(f"❌ {repo_name}: {message}", err=True)
        raise typer.Exit(1)
    typer.echo(f"✅ {repo_name}: worktree added at {worktree_path} on {branch}")


@app.command("list")
def worktree_list(
    ctx: typer.Context,
    repo_name: str = typer.Argument(..., help="Repository to list worktrees for"),
):
    """List the worktrees attached to a repository."""
    verbose = ctx.obj.get("verbose", False) if ctx.obj else False
    config = get_config()
    repo, _ = _resolve_repo(repo_name, config, verbose)

    worktrees = list_worktrees(repo["path"], verbose=verbose)
    if not worktrees:
        typer.echo(f"No worktrees found for {repo_name}")
        return

    typer.echo(f"Worktrees for {repo_name}:")
    for entry in worktrees:
        marker = "  " if entry["path"] != repo["path"] else "* "
        branch = entry["branch"] or f"detached at {(entry['head'] or '')[:8]}"
        typer.echo(f"{marker}{entry['path']}  [{branch}]")


@app.command("remove")
def worktree_remove(
    ctx: typer.Context,
    repo_name: str = typer.Argument(..., help="Repository the worktree belongs to"),
    label: str = typer.Argument(
        UPSTREAM_LABEL,
        help="Directory suffix of the worktree to remove (default: upstream)",
    ),
    force: bool = typer.Option(
        False, "--force", "-f", help="Remove even with uncommitted changes"
    ),
):
    """Remove a worktree and its registration in the primary clone."""
    verbose = ctx.obj.get("verbose", False) if ctx.obj else False
    config = get_config()
    repo, base_dir = _resolve_repo(repo_name, config, verbose)

    worktree_path = get_worktree_dir(
        base_dir, repo["group"], repo["name"], label=label, flat=is_flat_mode(config)
    )
    if not worktree_path.exists():
        typer.echo(f"❌ {repo_name}: no worktree at {worktree_path}", err=True)
        raise typer.Exit(1)

    ok, message = remove_worktree(
        repo["path"], worktree_path, force=force, verbose=verbose
    )
    if not ok:
        typer.echo(f"❌ {repo_name}: {message}", err=True)
        raise typer.Exit(1)
    typer.echo(f"✅ {repo_name}: removed worktree {worktree_path}")
