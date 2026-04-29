Virtual Environment Strategy
============================

**Decision: Fine-grained virtual environments at base, group, or repo level**

dbx-python-cli Installation
----------------------------

``dbx-python-cli`` is expected to be installed via pipx:

.. code-block:: bash

   pipx install git+https://github.com/aclark4life/dbx-python-cli.git

This keeps the ``dbx`` command available globally, isolated from project dependencies.

Repository and Virtual Environment Structure
---------------------------------------------

Users configure a base directory and clone repository groups. Virtual environments can be created at any level of the hierarchy:

.. code-block:: bash

   # Create a base venv shared across all groups (recommended)
   dbx env init

   # Create a group-level venv
   dbx env init -g pymongo

   # Create a repo-level venv
   dbx env init mongo-python-driver

This supports a structure like:

.. code-block:: text

   ~/Developer/mongodb/
   ├── .venv/                          # Base venv (shared across all groups)
   ├── projects/
   │   ├── .venv/                      # Shared venv for all Django projects
   │   ├── myproject/
   │   └── another_project/
   ├── pymongo/
   │   ├── .venv/                      # Group-level venv (optional)
   │   ├── mongo-python-driver/
   │   │   └── .venv/                  # Repo-level venv (optional)
   │   ├── specifications/
   │   └── drivers-evergreen-tools/
   ├── langchain/
   │   ├── .venv/                      # Separate group venv
   │   └── langchain-mongodb/

Rationale
---------

- **Flexibility** - Choose the right isolation level for each use case: a shared base venv for simplicity, a group venv for per-group dependency sets, or a per-repo venv for full isolation
- **Most specific wins** - Commands always prefer the most fine-grained venv available (repo > group > base), so adding a repo-level venv is always safe
- **Disk efficient** - A shared base or group venv avoids duplicating common dependencies across repos

Command Behavior
----------------

dbx env init
~~~~~~~~~~~~

Create a virtual environment at any level:

.. code-block:: bash

   # Create base venv (shared across all groups)
   dbx env init

   # Create venv for pymongo group
   dbx env init -g pymongo

   # Create repo-level venv
   dbx env init mongo-python-driver

   # Create with specific Python version
   dbx env init -g pymongo --python 3.11

dbx install
~~~~~~~~~~~

Install dependencies using the most specific venv found:

.. code-block:: bash

   # Uses repo, group, or base venv — whichever is most specific
   dbx install mongo-python-driver -e test

dbx test
~~~~~~~~

Run tests using the most specific venv found:

.. code-block:: bash

   # Uses repo, group, or base venv — whichever is most specific
   dbx test mongo-python-driver

dbx project add
~~~~~~~~~~~~~~~

Django project creation uses a project-specific lookup order:

1. ``projects/.venv`` — shared venv for all projects (group level)
2. ``base_dir/django/.venv`` — django group venv, if it exists
3. ``base_dir/.venv`` — base venv
4. Activated venv

If no venv is found and ``--install`` is active (the default), one is created automatically at ``projects/.venv`` and Django is bootstrapped into it. See :doc:`wagtail-support` for how this interacts with Wagtail projects.

Venv Detection
--------------

Commands detect and use venvs in this priority order (most specific first):

1. **Repo-level venv** - ``<repo_path>/.venv``
2. **Group-level venv** - ``<group_path>/.venv``
3. **Base directory venv** - ``<base_path>/.venv``
4. **Activated venv** - The current ``sys.executable`` or shell-activated Python if it is inside a venv
5. **Auto-detected venv** - If exactly one venv exists in the base directory, it is used automatically
6. **Auto-created venv** (``dbx project add`` only) - If no venv is found, one is created automatically at the ``projects/`` group level and Django is bootstrapped into it
7. **Error** - Installation to system Python is not allowed (all other commands)

You'll see clear messages indicating which venv is being used:

- ``Using repo venv: <repo_path>/.venv`` - Repo-level venv found
- ``Using group venv: <group_path>/.venv`` - Group-level venv found
- ``Using base venv: <base_path>/.venv`` - Base venv found
- ``Using venv: /path/to/venv/bin/python`` - Activated or auto-detected venv

Technical Implementation
------------------------

Running Commands in Venvs
~~~~~~~~~~~~~~~~~~~~~~~~~~

When ``dbx`` (installed via pipx into an isolated environment) needs to execute commands in a venv, it cannot use ``source`` or activation scripts in subprocesses. Instead, it must directly invoke the venv's Python executable:

.. code-block:: python

   # ❌ WRONG - Activation doesn't work in subprocess
   subprocess.run("source .venv/bin/activate && pytest", shell=True)

   # ✅ CORRECT - Directly invoke venv's Python
   subprocess.run([".venv/bin/python", "-m", "pytest"], cwd=repo_path)

This is because:

1. Activation scripts modify the current shell's environment
2. Subprocess environments don't persist across commands
3. The venv's Python executable knows where its packages are without activation

Venv Detection Example
~~~~~~~~~~~~~~~~~~~~~~

The actual ``get_venv_info`` signature includes an optional ``fallback_paths`` list for intermediate group lookups (used by ``dbx project`` commands to check the ``django`` group before falling back to base):

.. code-block:: python

   def get_venv_info(repo_path, group_path=None, base_path=None, fallback_paths=None):
       """
       Get information about which venv will be used.

       Checks in priority order (most specific to least specific):
       1. repo_path/.venv
       2. group_path/.venv
       3. Each path in fallback_paths (e.g. django group)
       4. base_path/.venv
       5. sys.executable — if already inside a venv
       6. PATH python — if a different venv is activated in the shell
       7. Auto-detected — if exactly one venv exists under base_path
       8. Error — system Python, installation refused

       Returns:
           tuple: (python_path, venv_type)
           venv_type is one of: "repo", "group", "base", "venv"

       Raises:
           typer.Exit: If no virtual environment is found
       """
       # 1. Repo-level venv
       # 2. Group-level venv
       # 3. Fallback group venvs (e.g. django group for projects)
       # 4. Base directory venv
       # 5-6. Activated venv (sys.executable or shell PATH)
       # 7. Auto-detect: if exactly one .venv exists, use it unambiguously
       # 8. Error with suggestions (dbx env init / source .venv/bin/activate)
