"""List commits on a development branch that are candidates for backporting."""

import re
import subprocess

import typer

from dbx_python_cli.utils import repo
from dbx_python_cli.utils.release import git_out, is_release_chore, latest_release_tag

app = typer.Typer(
    help="List backport candidates for a release branch",
    no_args_is_help=True,
    invoke_without_command=True,
    context_settings={
        "allow_interspersed_args": True,
        "help_option_names": ["-h", "--help"],
    },
)

# Release branches are named for the series they carry, e.g. "5.2.x".
_SERIES_BRANCH_RE = re.compile(r"^(\d+\.\d+)\.x$")


def _release_branches(path, remote):
    """Return ``(branch, series)`` for each ``X.Y.x`` branch on ``remote``, newest first."""
    refs = git_out(
        path, ["for-each-ref", "--format=%(refname:short)", f"refs/remotes/{remote}"]
    )
    found = []
    for ref in refs.split():
        branch = ref[len(remote) + 1 :]
        match = _SERIES_BRANCH_RE.match(branch)
        if match:
            found.append((branch, match.group(1)))
    found.sort(key=lambda b: [int(n) for n in b[1].split(".")], reverse=True)
    return found


def _resolve_since(path, since):
    """Return an ISO date for ``since``, resolving it as a git ref when possible.

    ``--since`` accepts "a git ref or date". Git's own ``--since=`` only takes a
    date and quietly misreads a tag as one, so a ref is resolved to the commit
    date of what it points at; anything that is not a ref is passed through
    untouched for git's approxidate parser to handle.
    """
    try:
        git_out(path, ["rev-parse", "--verify", "-q", f"{since}^{{commit}}"])
        return git_out(path, ["log", "-1", "--format=%cI", since]) or since
    except subprocess.CalledProcessError:
        return since


def _candidates(path, remote, source, target, since_iso):
    """Return ``(sha, date, subject)`` for source commits missing from target.

    ``--cherry-mark`` drops commits whose patch-id already exists on the target,
    which catches individually cherry-picked backports. It does *not* catch
    backports that were squashed into a single commit, which is why the caller
    bounds the window by the last release rather than the branch point.
    """
    log = git_out(
        path,
        [
            "log",
            "--cherry-mark",
            "--left-right",
            "--format=%m\x01%h\x01%cd\x01%s",
            "--date=short",
            *([f"--since={since_iso}"] if since_iso else []),
            f"{remote}/{target}...{remote}/{source}",
        ],
    )
    commits = []
    for line in log.splitlines():
        parts = line.split("\x01", 3)
        # ">" is only-on-source; "=" means an equivalent commit is already there.
        if len(parts) == 4 and parts[0] == ">":
            commits.append(tuple(p.strip() for p in parts[1:]))
    return commits


@app.callback()
def backports(
    ctx: typer.Context,
    repo_name: str = typer.Argument(..., help="Repository to inspect"),
    group: str = typer.Option(None, "--group", "-g", help="Group the repo lives in"),
    source: str = typer.Option(
        "main", "--from", help="Branch the candidates are taken from"
    ),
    target: list[str] = typer.Option(
        None,
        "--to",
        help="Release branch to backport into (repeatable; defaults to every X.Y.x branch)",
    ),
    since: str = typer.Option(
        None,
        "--since",
        help="Widen the window: a git ref or date to list commits from, instead of the branch's last release tag",
    ),
    all_commits: bool = typer.Option(
        False,
        "--all",
        help="Go back to the branch point and include release chores (implies no --since bound)",
    ),
    remote: str = typer.Option(
        "upstream", "--remote", help="Remote to read branches from"
    ),
    no_fetch: bool = typer.Option(
        False, "--no-fetch", help="Skip fetching the remote first"
    ),
):
    """List commits on ``--from`` that have not reached a release branch.

    Candidates are bounded by the release branch's own latest tag: everything
    older was already triaged when that release was assembled, so re-listing it
    is noise. Pass ``--since`` or ``--all`` when hunting for a fix that was
    missed rather than deliberately skipped.

    Usage::

        dbx backports django-mongodb-backend                    # every release branch
        dbx backports django-mongodb-backend --to 5.2.x         # just the 5.2 LTS branch
        dbx backports django-mongodb-backend --to 5.2.x --all   # back to the branch point
        dbx backports django-mongodb-backend --since 5.2.3      # widen to an older release
    """
    verbose = ctx.obj.get("verbose", False) if ctx.obj else False

    config = repo.get_config()
    base_dir = repo.get_base_dir(config)

    if group:
        path = repo.get_repo_dir(base_dir, group, repo_name, repo.is_flat_mode(config))
        if not path.exists():
            typer.echo(
                f"❌ Repository '{repo_name}' not found in group '{group}'", err=True
            )
            raise typer.Exit(1)
    else:
        repo_info = repo.find_repo_by_name(repo_name, base_dir, config)
        if not repo_info:
            typer.echo(f"❌ Repository '{repo_name}' not found", err=True)
            raise typer.Exit(1)
        path = repo_info["path"]

    if not no_fetch:
        # A stale clone under-reports candidates, which is the dangerous
        # direction here: a fix that landed today would simply not appear.
        try:
            git_out(path, ["fetch", "--tags", "--quiet", remote])
        except subprocess.CalledProcessError as e:
            typer.echo(
                f"⚠️  Could not fetch {remote}: {(e.stderr or '').strip()} "
                f"(results may be stale)",
                err=True,
            )

    try:
        branches = _release_branches(path, remote)
    except subprocess.CalledProcessError as e:
        typer.echo(f"❌ Could not list branches: {(e.stderr or '').strip()}", err=True)
        raise typer.Exit(1) from e

    if not branches:
        typer.echo(f"No X.Y.x release branches found on {remote}")
        return

    if target:
        wanted = set(target)
        known = {b[0] for b in branches}
        for branch in sorted(wanted - known):
            typer.echo(
                f"⚠️  No {remote}/{branch} branch found "
                f"(known: {', '.join(sorted(known))})"
            )
        branches = [b for b in branches if b[0] in wanted]
        if not branches:
            raise typer.Exit(1)

    typer.echo(f"\n📋 Backport candidates from {remote}/{source}:\n")

    for branch, series in branches:
        typer.echo(f"🌿 {branch}")

        since_iso = None
        if all_commits:
            typer.echo("   since the branch point")
        elif since:
            # --since is documented as "a git ref or date", but git log --since
            # only understands dates and silently *misparses* a tag rather than
            # rejecting it ("5.2.3" reads as a 2003 date, leaving the window
            # effectively unbounded). Resolve refs to their commit date first so
            # a tag bounds the window the way the user expects.
            since_iso = _resolve_since(path, since)
            if since_iso != since:
                typer.echo(f"   since {since} ({since_iso[:10]})")
            else:
                typer.echo(f"   since {since}")
        else:
            release = latest_release_tag(path, series)
            if not release:
                # Without a tag the window would fall back to the branch point,
                # which on a long-dead branch means hundreds of lines that were
                # never candidates. Say so and move on.
                typer.echo(
                    f"   ⚠️  No {series}.* release tag — skipping "
                    f"(pass --since or --all to list anyway)"
                )
                continue
            tag, since_iso = release
            typer.echo(f"   since {tag} ({since_iso[:10]})")

        try:
            commits = _candidates(path, remote, source, branch, since_iso)
        except subprocess.CalledProcessError as e:
            typer.echo(
                f"   ⚠️  Could not compare against {remote}/{source}: "
                f"{(e.stderr or '').strip()}",
                err=True,
            )
            continue

        chores = 0
        shown = []
        for sha, date, subject in commits:
            if not all_commits and is_release_chore(subject):
                chores += 1
                continue
            shown.append((sha, date, subject))

        if not shown:
            note = f" ({chores} release chore(s) skipped)" if chores else ""
            typer.echo(f"   ✅ nothing to backport{note}")
            continue

        typer.echo(f"   {len(shown)} candidate(s):")
        for sha, date, subject in shown:
            typer.echo(f"     {sha} {date} {subject}")
        if chores:
            typer.echo(f"   ({chores} release chore(s) hidden — pass --all)")

        if verbose:
            typer.echo(
                f"   [verbose] git log --cherry-mark --left-right "
                f"{remote}/{branch}...{remote}/{source}"
            )

    typer.echo(
        "\nNot every candidate belongs on a release branch — check the project's "
        "supported-versions policy before cherry-picking."
    )
