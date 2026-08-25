"""Git worktree helpers.

A worktree lets a single clone have more than one branch checked out at once,
each in its own directory but sharing one object store.  This is what makes it
possible to develop against both a fork and its upstream from one ``dbx clone``:
the primary checkout stays on the fork branch (``origin``) while a sibling
worktree tracks the upstream default branch, with no second fetch and no
duplicated history.

Layout mirrors the repo layout from :mod:`dbx_python_cli.utils.repo`, with the
worktree as a sibling of its primary checkout:

- Grouped: ``base_dir/<group>/<repo>-<label>``
- Flat:    ``base_dir/<repo>-<label>``
"""

import subprocess
from pathlib import Path

import typer

from dbx_python_cli.utils.repo import get_repo_dir, is_worktree

#: Directory-name suffix used when a worktree is created for the upstream remote.
UPSTREAM_LABEL = "upstream"

#: Re-exported so callers only need one import for worktree handling.
__all__ = [
    "UPSTREAM_LABEL",
    "add_worktree",
    "branch_to_label",
    "get_remote_head_branch",
    "get_worktree_dir",
    "has_remote",
    "is_worktree",
    "list_worktrees",
    "local_branch_exists",
    "prune_worktrees",
    "remove_worktree",
]


def get_worktree_dir(base_dir, group, repo_name, label=UPSTREAM_LABEL, flat=False):
    """Return the directory a worktree for *repo_name* should live in.

    Args:
        base_dir: Base directory for clones
        group: Group name (ignored in flat mode)
        repo_name: Name of the primary repo (e.g. ``django``)
        label: Suffix distinguishing the worktree (e.g. ``upstream``)
        flat: True when repos live directly under base_dir

    Returns:
        Path: e.g. ``base_dir/django/django-upstream``
    """
    return get_repo_dir(base_dir, group, f"{repo_name}-{label}", flat=flat)


def branch_to_label(branch):
    """Turn a branch name into a filesystem-safe directory suffix.

    Branch names may contain ``/`` (``stable/6.1.x``), which would otherwise
    create nested directories.

    Args:
        branch: Branch name

    Returns:
        str: Suffix safe to append to a directory name
    """
    return branch.replace("/", "-")


def list_worktrees(repo_path, verbose=False):
    """List the worktrees attached to the clone at *repo_path*.

    The primary checkout is included; it is the entry whose path equals
    *repo_path* and for which :func:`is_worktree` is False.

    Args:
        repo_path: Path to any checkout of the repository
        verbose: Print the underlying git invocation

    Returns:
        list: Dicts with ``path`` (Path), ``branch`` (str or None, detached
        HEAD yields None), ``head`` (str or None) and ``bare`` (bool) keys.
        Empty if *repo_path* is not a git repository.
    """
    if verbose:
        typer.echo(f"  [verbose] git -C {repo_path} worktree list --porcelain")

    result = subprocess.run(
        ["git", "-C", str(repo_path), "worktree", "list", "--porcelain"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return []

    worktrees = []
    current = None
    for line in result.stdout.splitlines():
        if line.startswith("worktree "):
            if current is not None:
                worktrees.append(current)
            current = {
                "path": Path(line[len("worktree ") :]),
                "branch": None,
                "head": None,
                "bare": False,
            }
        elif current is None:
            continue
        elif line.startswith("HEAD "):
            current["head"] = line[len("HEAD ") :]
        elif line.startswith("branch "):
            # Porcelain reports the full ref: refs/heads/<branch>
            ref = line[len("branch ") :]
            current["branch"] = (
                ref[len("refs/heads/") :] if ref.startswith("refs/heads/") else ref
            )
        elif line == "bare":
            current["bare"] = True

    if current is not None:
        worktrees.append(current)
    return worktrees


def get_remote_head_branch(repo_path, remote="upstream", verbose=False):
    """Return the default branch of *remote*, or None if it cannot be determined.

    Reads the cached ``refs/remotes/<remote>/HEAD`` symbolic ref first (set by
    ``git clone`` / ``git remote add`` + ``fetch``) and falls back to asking the
    remote directly, which also repairs the local ref for later calls.
    """
    result = subprocess.run(
        ["git", "-C", str(repo_path), "symbolic-ref", f"refs/remotes/{remote}/HEAD"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0 and result.stdout.strip():
        # refs/remotes/upstream/main -> main
        return result.stdout.strip().split(f"refs/remotes/{remote}/", 1)[-1]

    if verbose:
        typer.echo(f"  [verbose] {remote}/HEAD not set, querying remote")

    # set-head asks the remote and writes the ref; then re-read it.
    subprocess.run(
        ["git", "-C", str(repo_path), "remote", "set-head", remote, "--auto"],
        capture_output=True,
        text=True,
    )
    result = subprocess.run(
        ["git", "-C", str(repo_path), "symbolic-ref", f"refs/remotes/{remote}/HEAD"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip().split(f"refs/remotes/{remote}/", 1)[-1]
    return None


def has_remote(repo_path, remote):
    """Return True if *repo_path* has a remote named *remote*."""
    result = subprocess.run(
        ["git", "-C", str(repo_path), "remote"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return False
    return remote in result.stdout.split()


def local_branch_exists(repo_path, branch):
    """Return True if *branch* exists as a local branch in *repo_path*."""
    result = subprocess.run(
        [
            "git",
            "-C",
            str(repo_path),
            "show-ref",
            "--verify",
            "--quiet",
            f"refs/heads/{branch}",
        ],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def add_worktree(repo_path, worktree_path, branch, start_point=None, verbose=False):
    """Create a worktree for *branch* at *worktree_path*.

    When *start_point* is given and *branch* does not exist locally, the branch
    is created from *start_point* (e.g. ``upstream/main``) with ``-b``.  When the
    branch already exists it is simply checked out into the new worktree; git
    refuses if it is already checked out elsewhere, which is reported as a
    failure rather than worked around.

    Args:
        repo_path: Path to an existing checkout of the repository
        worktree_path: Directory to create
        branch: Local branch name to check out in the worktree
        start_point: Ref to create *branch* from when it does not exist yet
        verbose: Stream git output instead of capturing it

    Returns:
        tuple: ``(ok, message)`` where *ok* is a bool and *message* is git's
        error output when *ok* is False, otherwise an empty string.
    """
    cmd = ["git", "-C", str(repo_path), "worktree", "add"]
    if start_point and not local_branch_exists(repo_path, branch):
        cmd += ["-b", branch, str(worktree_path), start_point]
    else:
        cmd += [str(worktree_path), branch]

    if verbose:
        typer.echo(f"  [verbose] {' '.join(cmd)}")

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return False, (result.stderr or result.stdout).strip()
    return True, ""


def remove_worktree(repo_path, worktree_path, force=False, verbose=False):
    """Remove the worktree at *worktree_path*.

    Uses ``git worktree remove`` so the registration in ``.git/worktrees`` is
    cleaned up too; deleting the directory outright would leave a stale entry
    that blocks re-creating the worktree later.

    Args:
        repo_path: Path to another checkout of the same repository
        worktree_path: Worktree directory to remove
        force: Remove even when the worktree has uncommitted changes
        verbose: Stream git output instead of capturing it

    Returns:
        tuple: ``(ok, message)`` as in :func:`add_worktree`.
    """
    cmd = ["git", "-C", str(repo_path), "worktree", "remove"]
    if force:
        cmd.append("--force")
    cmd.append(str(worktree_path))

    if verbose:
        typer.echo(f"  [verbose] {' '.join(cmd)}")

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return False, (result.stderr or result.stdout).strip()
    return True, ""


def prune_worktrees(repo_path, verbose=False):
    """Drop registrations for worktree directories that no longer exist."""
    if verbose:
        typer.echo(f"  [verbose] git -C {repo_path} worktree prune")
    subprocess.run(
        ["git", "-C", str(repo_path), "worktree", "prune"],
        capture_output=True,
        text=True,
    )
