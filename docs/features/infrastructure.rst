Infrastructure Requirements
===========================

``dpy infra`` inventories and verifies the infrastructure a repo's tests
need: tools, secret vault access, env vars, and host constraints. It answers
two questions: *what does this suite need* and *can I run it right now*.

.. code-block:: bash

   dpy infra list mongo-python-driver
   dpy infra list mongo-python-driver auth_oidc
   dpy infra check mongo-python-driver
   dpy infra check mongo-python-driver load_balancer

Human output
------------

``dpy infra list`` prints one Rich panel per system, the same style as
``dpy ci``. Evergreen suites and GitHub Actions release workflows stay
separate. Each suite line shows its constraint markers:

.. code-block:: text

   ╭───────────── Evergreen test suites for mongo-python-driver (8) ─────────────╮
   │ Run: just setup-tests <suite>                                               │
   │                                                                             │
   │ atlas_connect  [no-server | vaults: drivers/atlas_connect]                  │
   │ load_balancer  [tools: haproxy]                                             │
   ╰─────────────────────────────────────────────────────────────────────────────╯

``dpy infra list <suite>`` prints a single suite panel with its marker, notes,
and links. ``--verbose`` adds overlay notes and links to the suite list.

Public-safe by design
---------------------

This repository is public, and its docs publish to Read the Docs, so
``dpy infra`` stores and prints public-safe facts only:

- tool names (``haproxy``, ``docker``), secret vault names
  (``drivers/atlas_connect``), env var names, host constraints
- internal wiki pages are linked by title and URL, never copied

Never stored or printed: secret values, cluster hostnames, personal
identifiers. Check output reports presence and shape (``set (28 chars)``),
never values, so it is safe to paste into tickets. This matches the
precedent in pymongo's ``CONTRIBUTING.md``, which links the same wiki pages.

Where the data comes from
-------------------------

The listing has two independent sources:

- **Evergreen test suites.** These come from the suite registry. Suites are
  not hand-listed: ``dpy infra list`` parses the repo's own
  ``.evergreen/scripts/utils.py`` (``TEST_SUITE_MAP``, ``EXTRA_TESTS``,
  ``NO_RUN_ORCHESTRATION``) with ``ast``, so the list is always current and
  never drifts from the repo.
- **GitHub Actions release workflows.** These come from
  ``.github/workflows/*.yml``. See `Extending to other repos`_.

A repo can have either source, both, or neither. Evergreen and GitHub
Actions are separate systems, and the command keeps their output separate.

The overlay
-----------

Facts the registry cannot express live in an ``[infra.<repo>.<suite>]``
overlay in ``config.toml``:

.. code-block:: toml

   [infra.mongo-python-driver.load_balancer]
   requires_tools = ["haproxy"]

   [infra.mongo-python-driver.enterprise_auth]
   evergreen_only = true

   [infra.mongo-python-driver.atlas_connect]
   vaults = ["drivers/atlas_connect"]

   [infra.mongo-python-driver.auth_oidc]
   notes = "Types: default, azure, gcp, eks, aks, gke. eks needs drivers-test-secrets-role access."
   links = { aws-secrets = "https://wiki.corp.mongodb.com/spaces/DRIVERS/pages/239737385/..." }

Allowed keys: ``requires_tools``, ``vaults``, ``env_names``,
``evergreen_only``, ``notes``, ``links``. ``dpy config validate`` checks
them. The overlay extends beyond test suites: a release pipeline step can
be described with the same keys.

Checks
------

``dpy infra check`` verifies live state:

- required tools on PATH
- ``DRIVERS_TOOLS`` present (from ``test_env``, else the repo submodule)
  and not stale (fails past 180 days)
- ``secrets-export.sh`` present under ``DRIVERS_TOOLS`` and its age, when
  the suite needs vaults
- AWS credentials resolve via ``aws sts get-caller-identity`` (reports
  account and role name only, both public)
- required env vars set, reported as set with length, never the value
- Evergreen-only suites flagged when not on an Evergreen host

Exit code is 1 when any check fails, so ``dpy infra check`` works as a
pre-flight gate or audit step.

Extending to other repos
------------------------

Two adapters exist. The pymongo-family adapter reads the Evergreen suite
registry, ``.evergreen/scripts/utils.py``. The release adapter reads the
GitHub Actions workflow files, ``.github/workflows/*.yml``, and covers the
three release styles seen across the repos:

- abx-release-tools composite actions (``strands-mongodb``)
- repo-local composite actions under ``.github/actions``
  (``claude-agent-sdk-mongodb-session-store``)
- plain workflows using PyPI trusted publishing
  (``ms-agent-framework-mongodb``)

A workflow counts as a release workflow when its filename contains
``release`` or ``publish``. ``dpy infra list`` shows each file, its ABX and
local actions, SHA pin status, and the repo vars and secrets the workflow
references. It also prints an ``Action docs:`` line for each external action
source: a known tool links to its documentation site, every other action
links to its GitHub repo. Standard ``actions/*`` steps are omitted. Add
repo-specific links in the ``[infra.<repo>.release]`` overlay.

``dpy infra check`` flags unpinned ABX actions and a workflow that publishes
without ``id-token: write``. Release runs in CI, so local checks cover
workflow hygiene only. Repos with neither adapter fall back to overlay-only
listing.

Planned: a ``dpy infra run`` orchestrator that chains ``run-server``,
``setup-tests``, ``run-tests``, ``teardown-tests``.

Reference links
---------------

- `pymongo CONTRIBUTING.md, "Running tests that require secrets, services,
  or other configuration"
  <https://github.com/mongodb/mongo-python-driver/blob/master/CONTRIBUTING.md>`_
  (public; the per-suite runbook)
- `drivers-evergreen-tools secrets handling
  <https://github.com/mongodb-labs/drivers-evergreen-tools/tree/master/.evergreen/secrets_handling>`_
  (public)
- `Using AWS Secrets Manager to Store Testing Secrets
  <https://wiki.corp.mongodb.com/spaces/DRIVERS/pages/239737385/Using+AWS+Secrets+Manager+to+Store+Testing+Secrets>`_
  (internal)
- `Drivers Cloud Services
  <https://wiki.corp.mongodb.com/spaces/DRIVERS/pages/473895023/Drivers+Cloud+Services>`_
  (internal)
- `Atlas QA Admin
  <https://wiki.corp.mongodb.com/spaces/DRIVERS/pages/473895025/Atlas+QA+Admin>`_
  (internal)
- `abx-release-tools docs <https://abx-release-tools.readthedocs.io/en/latest/>`_
  (public; release pipeline)
