"""Infrastructure requirement discovery and checks.

Public-safe facts only: tool names, secret vault names, env var names,
host constraints, and links. Never secret values. Check output reports
presence and shape, never values, so it is safe to paste into tickets.
"""

import ast
import os
import shutil
import subprocess
import time
from pathlib import Path

# Keys allowed in [infra.<repo>.<suite>] overlay tables.
KNOWN_INFRA_SUITE_KEYS = {
    "requires_tools",
    "vaults",
    "env_names",
    "evergreen_only",
    "notes",
    "links",
}

# Fixed locations setup_secrets.sh writes to, checked in order.
SECRETS_EXPORT_CANDIDATES = (
    "secrets-export.sh",
    ".evergreen/secrets-export.sh",
    ".evergreen/auth_aws/secrets-export.sh",
)


def parse_suite_registry(repo_path):
    """Parse TEST_SUITE_MAP, EXTRA_TESTS and NO_RUN_ORCHESTRATION from a repo.

    Reads the repo's own ``.evergreen/scripts/utils.py`` with ast, so the
    suite list is always current. No import of the target module happens.

    Returns a dict with ``suites`` (name -> pytest marker), ``extra`` (list),
    and ``no_orchestration`` (list), or None when the repo has no registry.
    """
    utils_py = Path(repo_path) / ".evergreen" / "scripts" / "utils.py"
    if not utils_py.exists():
        return None

    try:
        tree = ast.parse(utils_py.read_text())
    except (SyntaxError, OSError):
        return None

    found = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if not (
                isinstance(target, ast.Name)
                and target.id
                in (
                    "TEST_SUITE_MAP",
                    "EXTRA_TESTS",
                    "NO_RUN_ORCHESTRATION",
                )
            ):
                continue
            try:
                found[target.id] = ast.literal_eval(node.value)
            except ValueError:
                continue

    if "TEST_SUITE_MAP" not in found:
        return None

    return {
        "suites": found.get("TEST_SUITE_MAP", {}),
        "extra": list(found.get("EXTRA_TESTS", [])),
        "no_orchestration": list(found.get("NO_RUN_ORCHESTRATION", [])),
    }


def get_infra_overlay(config, repo_name):
    """Get the [infra.<repo>] overlay table from config."""
    overlay = config.get("infra", {})
    if not isinstance(overlay, dict):
        return {}
    entry = overlay.get(repo_name, {})
    return entry if isinstance(entry, dict) else {}


def resolve_drivers_tools(config, group_name, repo_name, base_dir, repo_path):
    """Resolve the DRIVERS_TOOLS checkout for a repo.

    Priority: test_env DRIVERS_TOOLS, then the drivers-evergreen-tools
    submodule inside the repo (what ``just install`` initializes).
    """
    from dbx_python_cli.utils.repo import get_test_env_vars

    env_vars = get_test_env_vars(config, group_name, repo_name, base_dir)
    value = env_vars.get("DRIVERS_TOOLS")
    if value:
        return Path(value).expanduser()
    return Path(repo_path) / "drivers-evergreen-tools"


def _last_commit_age_days(path):
    """Days since the last commit in *path*, or None when not a git repo."""
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%ct"],
            cwd=str(path),
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        return max(0.0, (time.time() - float(result.stdout.strip())) / 86400)
    except (
        subprocess.CalledProcessError,
        subprocess.TimeoutExpired,
        ValueError,
        FileNotFoundError,
    ):
        return None


def check_tool(name):
    """Check that *name* is on PATH."""
    path = shutil.which(name)
    if path:
        return True, path
    return False, f"{name} not found on PATH"


def check_drivers_tools(path):
    """Check DRIVERS_TOOLS presence and freshness."""
    path = Path(path)
    if not path.is_dir():
        return False, f"DRIVERS_TOOLS not found: {path}"
    age = _last_commit_age_days(path)
    if age is None:
        return True, f"{path} (not a git checkout)"
    if age > 180:
        return False, f"{path} (last commit {int(age)} days ago, likely stale)"
    return True, f"{path} (last commit {int(age)} days ago)"


def check_secrets_export(drivers_tools):
    """Check for a secrets-export.sh file and its age. Never its contents."""
    if not drivers_tools:
        return False, "DRIVERS_TOOLS not resolved"
    for candidate in SECRETS_EXPORT_CANDIDATES:
        path = Path(drivers_tools) / candidate
        if path.exists():
            age_days = max(0, int((time.time() - path.stat().st_mtime) / 86400))
            return True, f"{candidate} (written {age_days} day(s) ago)"
    return False, "no secrets-export.sh under DRIVERS_TOOLS"


def check_aws_credentials(env=None):
    """Check AWS credentials resolve via STS. Prints account and role only.

    The account id and role name are public (committed to
    drivers-evergreen-tools), so reporting them is safe. Credential values
    are never printed.
    """
    if not shutil.which("aws"):
        return False, "aws CLI not found on PATH"
    try:
        result = subprocess.run(
            ["aws", "sts", "get-caller-identity"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
            env=env or os.environ.copy(),
        )
    except subprocess.TimeoutExpired:
        return False, "aws sts get-caller-identity timed out"
    if result.returncode != 0:
        return False, "credentials expired or not configured (run: aws sso login)"
    try:
        import json

        data = json.loads(result.stdout)
        account = data.get("Account", "unknown")
        arn_parts = data.get("Arn", "").split("/")
        role = arn_parts[-1] if len(arn_parts) > 1 else "unknown"
        return True, f"authenticated (account {account}, role {role})"
    except ValueError:
        # SSO can return non-JSON with certain output configurations.
        return True, "authenticated"


def check_env_var(name):
    """Check that env var *name* is set. Never print its value."""
    if name in os.environ:
        return True, _redact(os.environ[name])
    return False, "unset"


def _redact(value):
    """Describe a value without revealing it."""
    if not value:
        return "set (empty)"
    return f"set ({len(value)} chars)"


def is_evergreen_host():
    """Heuristic: True when running on an Evergreen EC2 host."""
    return bool(os.environ.get("EVG_HOME")) or Path("/etc/evergreen").exists()
