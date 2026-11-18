Infrastructure Requirements
===========================

``dbx infra`` inventories and verifies the infrastructure a repo's tests
need: tools, secret vault access, env vars, and host constraints. It answers
two questions: *what does this suite need* and *can I run it right now*.

.. code-block:: bash

   dbx infra list mongo-python-driver
   dbx infra list mongo-python-driver auth_oidc
   dbx infra check mongo-python-driver
   dbx infra check mongo-python-driver load_balancer

Public-safe by design
---------------------

This repository is public, and its docs publish to Read the Docs, so
``dbx infra`` stores and prints public-safe facts only:

- tool names (``haproxy``, ``docker``), secret vault names
  (``drivers/atlas_connect``), env var names, host constraints
- internal wiki pages are linked by title and URL, never copied

Never stored or printed: secret values, cluster hostnames, personal
identifiers. Check output reports presence and shape (``set (28 chars)``),
never values, so it is safe to paste into tickets. This matches the
precedent in pymongo's ``CONTRIBUTING.md``, which links the same wiki pages.

Where the data comes from
-------------------------

Suites are not hand-listed. ``dbx infra list`` parses the repo's own
``.evergreen/scripts/utils.py`` (``TEST_SUITE_MAP``, ``EXTRA_TESTS``,
``NO_RUN_ORCHESTRATION``) with ``ast``, so the suite list is always current
and never drifts from the repo.

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
``evergreen_only``, ``notes``, ``links``. ``dbx config validate`` checks
them. The overlay extends beyond test suites: a release pipeline step can
be described with the same keys.

Checks
------

``dbx infra check`` verifies live state:

- required tools on PATH
- ``DRIVERS_TOOLS`` present (from ``test_env``, else the repo submodule)
  and not stale (fails past 180 days)
- ``secrets-export.sh`` present under ``DRIVERS_TOOLS`` and its age, when
  the suite needs vaults
- AWS credentials resolve via ``aws sts get-caller-identity`` (reports
  account and role name only, both public)
- required env vars set, reported as set with length, never the value
- Evergreen-only suites flagged when not on an Evergreen host

Exit code is 1 when any check fails, so ``dbx infra check`` works as a
pre-flight gate or audit step.

Extending to other repos
------------------------

The pymongo-family adapter reads ``.evergreen/scripts/utils.py``. Repos
without that file fall back to overlay-only listing. Planned adapters:
ABX-style repos (parse ``.github/workflows`` for
``mongodb-labs/abx-release-tools`` actions and their required secrets and
permissions) and a ``dbx infra run`` orchestrator that chains
``run-server``, ``setup-tests``, ``run-tests``, ``teardown-tests``.

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
