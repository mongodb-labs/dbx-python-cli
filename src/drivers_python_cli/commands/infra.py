"""Infra command: inventory and verify infrastructure requirements per repo."""

from pathlib import Path

import typer
from rich.console import Console, Group
from rich.markup import escape
from rich.padding import Padding
from rich.panel import Panel
from rich.text import Text

from drivers_python_cli.utils.infra import action_docs_url
from drivers_python_cli.utils.repo import (
    find_repo_by_name,
    find_repo_by_path,
    get_base_dir,
    get_config,
    is_flat_mode,
    is_path_like,
)

app = typer.Typer(
    invoke_without_command=True,
    context_settings={"help_option_names": ["-h", "--help"]},
    no_args_is_help=True,
    help="List and check infrastructure requirements (tools, secrets access, env) per repo.",
)

console = Console(highlight=False)


def _resolve_repo(ctx, repo):
    """Resolve a repo argument to {name, path, group}, defaulting to cwd."""
    config = get_config()
    base_dir = get_base_dir(config)
    flat = is_flat_mode(config)

    if repo:
        if is_path_like(repo):
            repo_info = find_repo_by_path(Path(repo), base_dir, config)
        else:
            repo_info = find_repo_by_name(repo, base_dir, config)
    else:
        repo_info = find_repo_by_path(Path.cwd(), base_dir, config)

    return config, base_dir, flat, repo_info


@app.command("list")
def list_suites(
    ctx: typer.Context,
    repo: str = typer.Argument(
        None, help="Repository name or path (defaults to current directory)."
    ),
    suite: str = typer.Argument(None, help="Show a single suite in detail."),
):
    """List test suites and their infrastructure requirements.

    Suites are parsed from the repo's own .evergreen/scripts/utils.py, so the
    list is always current. Extra facts (required tools, vaults, host
    constraints) come from the [infra.<repo>] overlay in config.
    """
    from drivers_python_cli.utils.infra import (
        get_infra_overlay,
        parse_release_workflows,
        parse_suite_registry,
    )

    verbose = ctx.obj.get("verbose", False) if ctx.obj else False
    config, _base_dir, _flat, repo_info = _resolve_repo(ctx, repo)

    if not repo_info:
        typer.echo(f"Error: repo not found: {repo or Path.cwd()}", err=True)
        raise typer.Exit(1)

    name = repo_info["name"]
    registry = parse_suite_registry(repo_info["path"])
    release = parse_release_workflows(repo_info["path"])
    overlay = get_infra_overlay(config, name)

    if not registry and not overlay and not release:
        typer.echo(
            f"No Evergreen suite registry, GitHub Actions release workflow, "
            f"or [infra.{name}] overlay found."
        )
        typer.echo(
            "Suites are discovered from .evergreen/scripts/utils.py (pymongo-family repos)."
        )
        raise typer.Exit(1)

    if suite:
        _print_suite_detail(suite, registry, overlay)
        raise typer.Exit(
            0
            if (not registry or suite in _all_suites(registry) or suite in overlay)
            else 1
        )

    suites = _all_suites(registry) if registry else []
    console.print()
    console.print(_evergreen_panel(name, suites, overlay, registry, verbose))
    if release:
        console.print(_release_panel(name, release, overlay))


def _all_suites(registry):
    return sorted(list(registry["suites"]) + registry["extra"])


def _suite_markers(suite_name, facts, registry):
    """Return the short constraint markers for one suite."""
    markers = []
    if (
        registry
        and registry["no_orchestration"]
        and suite_name in registry["no_orchestration"]
    ):
        markers.append("no-server")
    if facts.get("evergreen_only"):
        markers.append("evergreen-only")
    if facts.get("requires_tools"):
        markers.append("tools: " + ", ".join(facts["requires_tools"]))
    if facts.get("vaults"):
        markers.append("vaults: " + ", ".join(facts["vaults"]))
    if facts.get("env_names"):
        markers.append("env: " + ", ".join(facts["env_names"]))
    return markers


def _suite_line(suite_name, facts, registry):
    markers = _suite_markers(suite_name, facts, registry)
    suffix = f"  [{' | '.join(markers)}]" if markers else ""
    return Text.assemble((suite_name, "bold cyan"), (suffix, "dim"))


def _evergreen_panel(name, suites, overlay, registry, verbose):
    """Build the Evergreen suites panel."""
    # Overlay entries with no registry counterpart (e.g. mod_wsgi).
    # "release" holds links for the release workflows section, not a domain.
    entries = [(suite_name, overlay.get(suite_name, {})) for suite_name in suites]
    for domain, facts in overlay.items():
        if domain != "release" and domain not in suites:
            entries.append((domain, facts))

    lines = []
    if registry:
        title = f"Evergreen test suites for {name} ({len(suites)})"
        lines.append(Text("Run: just setup-tests <suite>", style="dim"))
        border = "cyan"
    elif entries:
        title = f"Overlay domains for {name}"
        lines.append(Text("Overlay domains only", style="dim"))
        border = "cyan"
    else:
        title = f"Evergreen: {name}"
        lines.append(
            Text(
                f"No Evergreen suite registry in {name}: .evergreen/scripts/utils.py "
                "is missing or has no TEST_SUITE_MAP.",
                style="yellow",
            )
        )
        border = "yellow"

    if entries:
        lines.append(Text(""))
        for suite_name, facts in entries:
            lines.append(_suite_line(suite_name, facts, registry))
            if verbose:
                if facts.get("notes"):
                    lines.append(
                        Padding(Text(facts["notes"], style="dim"), (0, 0, 0, 2))
                    )
                for label, url in (facts.get("links") or {}).items():
                    lines.append(
                        Padding(
                            Text.assemble(
                                (f"{label}: ", "dim"), (url, "blue underline")
                            ),
                            (0, 0, 0, 2),
                        )
                    )

    return Panel(
        Group(*lines),
        title=f"[bold cyan]{escape(title)}[/]",
        border_style=border,
        padding=(0, 1),
    )


def _release_panel(name, release, overlay):
    """Build the GitHub Actions release workflows panel."""
    title = (
        f"GitHub Actions release workflows for {name} ({len(release['files'])} file(s))"
    )
    lines = []
    if release["sources"]:
        lines.append(Text("Action docs:", style="bold"))
        for source in release["sources"]:
            lines.append(
                Text.assemble(
                    (f"{source}: ", "dim"),
                    (action_docs_url(source), "blue underline"),
                )
            )
        lines.append(Text(""))
    for info in release["files"]:
        lines.append(Text(info["file"], style="bold cyan"))
        if info["abx_actions"]:
            parts = []
            for action_name, action in sorted(info["abx_actions"].items()):
                pin = "pinned" if action["pinned"] else "UNPINNED"
                parts.append(f"{action_name} [{pin}]")
            lines.append(
                Padding(
                    Text.assemble(
                        ("abx actions: ", "dim"),
                        (", ".join(parts), ""),
                    ),
                    (0, 0, 0, 2),
                )
            )
        if info["local_actions"]:
            lines.append(
                Padding(
                    Text.assemble(
                        ("local actions: ", "dim"),
                        (", ".join(info["local_actions"]), ""),
                    ),
                    (0, 0, 0, 2),
                )
            )
        if info["id_token_write"]:
            lines.append(Padding(Text("id-token: write"), (0, 0, 0, 2)))
        else:
            lines.append(
                Padding(Text("no id-token permission", style="dim"), (0, 0, 0, 2))
            )
        if info["publishes"] and not info["id_token_write"]:
            lines.append(
                Padding(
                    Text("⚠️  publishes but no id-token: write", style="yellow"),
                    (0, 0, 0, 2),
                )
            )
    if release["vars"]:
        lines.append(
            Text.assemble(("repo vars: ", "dim"), (", ".join(release["vars"]), ""))
        )
    if release["secrets"]:
        lines.append(
            Text.assemble(
                ("repo secrets: ", "dim"), (", ".join(release["secrets"]), "")
            )
        )
    for label, url in ((overlay.get("release") or {}).get("links") or {}).items():
        lines.append(Text.assemble((f"{label}: ", "dim"), (url, "blue underline")))

    return Panel(
        Group(*lines),
        title=f"[bold cyan]{escape(title)}[/]",
        border_style="blue",
        padding=(0, 1),
    )


def _print_suite_detail(suite_name, registry, overlay):
    facts = overlay.get(suite_name, {})
    lines = []
    if registry:
        if suite_name in registry["suites"]:
            marker = registry["suites"][suite_name] or "(default)"
            lines.append(Text.assemble(("pytest marker: ", "dim"), (marker, "")))
        elif suite_name in registry["extra"]:
            lines.append(Text("extra test (not in TEST_SUITE_MAP)", style="dim"))
        else:
            lines.append(Text("not found in repo registry", style="red"))
            if not facts:
                raise typer.Exit(1)
    if registry and suite_name in registry["no_orchestration"]:
        lines.append(Text("no run-server step (setup-tests starts the server)"))
    if facts.get("evergreen_only"):
        lines.append(Text("evergreen-only: can only run on an Evergreen host"))
    if facts.get("requires_tools"):
        lines.append(
            Text.assemble(
                ("required tools: ", "dim"),
                (", ".join(facts["requires_tools"]), ""),
            )
        )
    if facts.get("vaults"):
        lines.append(
            Text.assemble(("secret vaults: ", "dim"), (", ".join(facts["vaults"]), ""))
        )
    if facts.get("env_names"):
        lines.append(
            Text.assemble(("env vars: ", "dim"), (", ".join(facts["env_names"]), ""))
        )
    if facts.get("notes"):
        lines.append(Text.assemble(("notes: ", "dim"), (facts["notes"], "")))
    for label, url in (facts.get("links") or {}).items():
        lines.append(Text.assemble((f"{label}: ", "dim"), (url, "blue underline")))

    console.print(
        Panel(
            Group(*lines),
            title=f"[bold cyan]{escape(f'Suite: {suite_name}')}[/]",
            border_style="cyan",
            padding=(0, 1),
        )
    )


@app.command()
def check(
    ctx: typer.Context,
    repo: str = typer.Argument(
        None, help="Repository name or path (defaults to current directory)."
    ),
    suite: str = typer.Argument(
        None, help="Check only this suite's requirements. Default: common checks."
    ),
):
    """Verify tools, secrets access, and env for a repo or suite.

    Reports presence and shape only. Never prints secret values, so the
    output is safe to paste into tickets.
    """
    from drivers_python_cli.utils.infra import (
        check_aws_credentials,
        check_drivers_tools,
        check_env_var,
        check_secrets_export,
        check_tool,
        get_infra_overlay,
        is_evergreen_host,
        parse_release_workflows,
        parse_suite_registry,
        resolve_drivers_tools,
    )

    config, base_dir, _flat, repo_info = _resolve_repo(ctx, repo)

    if not repo_info:
        typer.echo(f"Error: repo not found: {repo or Path.cwd()}", err=True)
        raise typer.Exit(1)

    name = repo_info["name"]
    group = repo_info["group"]
    overlay = get_infra_overlay(config, name)
    registry = parse_suite_registry(repo_info["path"])
    facts = overlay.get(suite, {}) if suite else {}

    if suite and registry and suite not in _all_suites(registry) and not facts:
        typer.echo(f"Error: unknown suite: {suite}", err=True)
        raise typer.Exit(1)

    typer.echo(
        f"Infrastructure check: {name}" + (f" (suite: {suite})" if suite else "")
    )
    typer.echo()
    failures = []

    def _record(ok, label, detail):
        typer.echo(f"{'✅' if ok else '❌'} {label}: {detail}")
        if not ok:
            failures.append(label)

    # Common checks.
    ok, detail = check_tool("just")
    _record(ok, "just", detail)
    drivers_tools = None
    if registry:
        drivers_tools = resolve_drivers_tools(
            config, group, name, base_dir, repo_info["path"]
        )
        ok, detail = check_drivers_tools(drivers_tools)
        _record(ok, "DRIVERS_TOOLS", detail)
        ok, detail = check_secrets_export(
            drivers_tools if facts.get("vaults") else None
        )
        if facts.get("vaults"):
            _record(ok, "secrets export", detail)
    needs_aws = (
        bool(facts.get("vaults"))
        or (facts.get("notes") or "").find("drivers-test-secrets-role") >= 0
    )
    if registry and (needs_aws or not suite):
        ok, detail = check_aws_credentials()
        _record(ok, "AWS credentials", detail)

    # Suite-specific checks.
    for tool in facts.get("requires_tools", []):
        ok, detail = check_tool(tool)
        _record(ok, f"tool {tool}", detail)
    for var in facts.get("env_names", []):
        ok, detail = check_env_var(var)
        _record(ok, f"env {var}", detail)
    if facts.get("evergreen_only") and not is_evergreen_host():
        _record(False, "host", "evergreen-only suite, not on an Evergreen host")

    # Release workflow checks (repos without a suite registry).
    if not registry:
        release = parse_release_workflows(repo_info["path"])
        if release:
            for action_name in release["unpinned"]:
                ref = release["actions"][action_name]["ref"]
                _record(
                    False,
                    f"action {action_name}",
                    f"not pinned to a commit SHA (ref: {ref})",
                )
            for info in release["files"]:
                if info["publishes"] and not info["id_token_write"]:
                    _record(
                        False,
                        f"id-token permission ({info['file']})",
                        "publishes but has no id-token: write",
                    )
            if release["vars"]:
                typer.echo(f"ℹ️  repo vars referenced: {', '.join(release['vars'])}")
            if release["secrets"]:
                typer.echo(
                    f"ℹ️  repo secrets referenced: {', '.join(release['secrets'])}"
                )

    typer.echo()
    if failures:
        typer.echo(f"❌ {len(failures)} check(s) failed: {', '.join(failures)}")
        raise typer.Exit(1)
    typer.echo("✅ All checks passed")
