Repository Management
=====================

The ``dbx clone``, ``dbx sync``, ``dbx branch``, ``dbx switch``, ``dbx log``, and ``dbx open`` commands provide repository management functionality for cloning and managing groups of related repositories.

Initialize Configuration
------------------------

Before using the repo commands, initialize your configuration file:

.. code-block:: bash

   # Create user configuration file at ~/.config/dbx-python-cli/config.toml
   dbx config init

This creates a configuration file with default repository groups that you can customize.

Clone Repositories by Group
----------------------------

Clone repositories from predefined groups:

.. code-block:: bash

   # Clone pymongo repositories
   dbx clone -g pymongo

   # Clone langchain repositories
   dbx clone -g langchain

   # Clone django repositories
   dbx clone -g django

   # Clone all groups from configuration
   dbx clone -a
   # or
   dbx clone --all

Fork-Based Workflow
~~~~~~~~~~~~~~~~~~~

For contributing to upstream repositories, you can clone from your personal fork and automatically set up the upstream remote:

.. code-block:: bash

   # Clone from your GitHub fork instead of the upstream org
   dbx clone -g pymongo --fork-user aclark4life

This will:

1. Clone from ``git@github.com:aclark4life/mongo-python-driver.git`` (your fork)
2. Add an ``upstream`` remote pointing to ``git@github.com:mongodb/mongo-python-driver.git`` (original repo)
3. Set up your local repository ready for the fork-based contribution workflow

Because ``mongo-python-driver`` is a global repo it is cloned into the target group
directory (e.g. ``pymongo/mongo-python-driver`` when you clone the ``pymongo`` group).

**Example workflow:**

.. code-block:: bash

   # Clone your forks with upstream remotes configured
   # mongo-python-driver (global) is also cloned into pymongo/
   dbx clone -g pymongo --fork-user aclark4life

   # Now you can work with the standard fork workflow
   cd ~/Developer/mongodb/pymongo/mongo-python-driver
   git remote -v
   # origin    git@github.com:aclark4life/mongo-python-driver.git (fetch)
   # origin    git@github.com:aclark4life/mongo-python-driver.git (push)
   # upstream  git@github.com:mongodb/mongo-python-driver.git (fetch)
   # upstream  git@github.com:mongodb/mongo-python-driver.git (push)

   # Fetch latest changes from upstream
   git fetch upstream
   git merge upstream/main

**Configuration:**

You can optionally set a default fork username in your configuration file to avoid typing it every time:

.. code-block:: toml

   [repo]
   base_dir = "~/Developer/mongodb"
   # fork_user = "your-github-username"  # Optional: specify your GitHub username for fork operations

   [repo.groups.pymongo]
   repos = [
       "git@github.com:mongodb/mongo-python-driver.git",
   ]

With this configuration, you can simply run:

.. code-block:: bash

   # Uses fork_user from config
   dbx clone -g pymongo --fork

   # Or specify a different username
   dbx clone -g pymongo --fork-user different-user

Clone All Groups
~~~~~~~~~~~~~~~~

You can clone all groups defined in your configuration at once using the ``-a`` or ``--all`` flag:

.. code-block:: bash

   # Clone all groups from configuration
   dbx clone -a

   # Clone all groups with fork workflow
   dbx clone -a --fork-user aclark4life

   # Clone all groups without automatic installation
   dbx clone -a --no-install

This will:

1. Clone all repositories from every non-global group defined in your configuration
2. Create separate directories for each non-global group under your ``base_dir``
3. Automatically include global group repositories in each non-global group
4. Optionally install dependencies if ``--no-install`` is not specified

**Example:**

If your configuration has groups ``global``, ``pymongo``, ``django``, and ``langchain``, running ``dbx clone -a`` will:

- Clone ``pymongo`` group repos (plus global repos) into ``~/Developer/mongodb/pymongo/``
- Clone ``django`` group repos (plus global repos) into ``~/Developer/mongodb/django/``
- Clone ``langchain`` group repos (plus global repos) into ``~/Developer/mongodb/langchain/``

Note that the ``global`` group itself does not get its own directory - its repositories are only cloned into the other group directories.

This is useful when setting up a new development environment or when you want to work with all configured repositories.

Sync Fork with Upstream
~~~~~~~~~~~~~~~~~~~~~~~~

After cloning with the fork workflow, you can easily sync your local repository with upstream changes:

.. code-block:: bash

   # Sync a specific repository
   dbx sync mongo-python-driver

   # Sync all repositories in a group
   dbx sync -g pymongo

   # Sync all repositories across all groups
   dbx sync -a

   # Preview what would be synced without making changes
   dbx sync mongo-python-driver --dry-run

   # Force push after rebasing (use if previous sync failed to push)
   dbx sync mongo-python-driver --force

   # List available repositories
   dbx sync -l

This command will:

1. Fetch the latest changes from the ``upstream`` remote
2. Rebase your current branch on top of ``upstream/<current-branch>``
3. Push the rebased branch to ``origin`` (your fork)
4. If ``--force`` is used, force push with ``--force-with-lease`` for safety
5. If ``--dry-run`` is used, compare commits between upstream and origin without making changes

**Example workflow:**

.. code-block:: bash

   # Clone your fork with upstream configured
   dbx clone -g pymongo --fork-user aclark4life

   # Make some changes in your fork
   cd ~/Developer/mongodb/pymongo/mongo-python-driver
   git checkout -b my-feature
   # ... make changes ...
   git commit -am "Add new feature"

   # Preview what would be synced (dry run)
   dbx sync mongo-python-driver --dry-run
   # Shows commits that would be applied from upstream and commits that would be rebased

   # Sync with upstream to get latest changes and push
   dbx sync mongo-python-driver
   # Fetches from upstream, rebases your branch, and pushes to origin

   # Your changes are now in your fork, ready for a pull request!

**Notes:**

- The ``sync`` command requires an ``upstream`` remote to be configured
- If you cloned with ``--fork``, the upstream remote is automatically set up
- The command will rebase your current branch on ``upstream/<current-branch>``
- After rebasing, it automatically pushes to ``origin/<current-branch>``
- If the push fails (e.g., you've already pushed and rebased), use ``--force`` flag
- The ``--force`` flag uses ``--force-with-lease`` for safety (won't overwrite others' changes)
- If there are rebase conflicts, you'll need to resolve them manually
- Works with any repository that has an ``upstream`` remote, not just forks

**Available Groups (Default):**

- ``global`` - Repos cloned into every group automatically (e.g. ``mongo-python-driver``)
- ``pymongo`` - MongoDB Python driver support repositories (Specifications, drivers-evergreen-tools)
- ``langchain`` - LangChain framework repositories
- ``django`` - Django web framework repositories (Django, django-mongodb-backend)

Global Groups
~~~~~~~~~~~~~

A *global group* is a special group whose repositories are automatically cloned into
**every other group** when you run ``dbx clone -g <group>``.  This is useful for repos
that every group needs — for example, the MongoDB Python driver is a shared dependency
for all driver-related groups.

.. code-block:: bash

   # Clones django repos AND mongo-python-driver into ~/Developer/mongodb/django/
   dbx clone -g django

   # Clones pymongo repos AND mongo-python-driver into ~/Developer/mongodb/pymongo/
   dbx clone -g pymongo

Global groups are declared with ``global_groups`` under ``[repo]``:

.. code-block:: toml

   [repo]
   base_dir = "~/Developer/mongodb"
   global_groups = ["global"]  # these repos are injected into every group clone

   [repo.groups.global]
   repos = [
       "git@github.com:mongodb/mongo-python-driver.git",
   ]

   [repo.groups.pymongo]
   repos = [
       "git@github.com:mongodb/specifications.git",
       "git@github.com:mongodb-labs/drivers-evergreen-tools.git",
   ]

Because ``mongo-python-driver`` ends up physically inside each group directory
(e.g. ``pymongo/mongo-python-driver``), ``dbx install -g pymongo`` and
``dbx test mongo-python-driver`` all work without any extra flags.

**Configuration:**

Repository groups are defined in ``~/.config/dbx-python-cli/config.toml``. The default base directory for cloning is ``~/Developer/dbx-repos``, which can be customized.

Repositories are cloned into subdirectories named after their group. For example, the ``pymongo`` group will be cloned to ``~/Developer/dbx-repos/pymongo/``.

.. code-block:: toml

   [repo]
   base_dir = "~/Developer/dbx-repos"
   global_groups = ["global"]

   [repo.groups.global]
   repos = [
       "https://github.com/mongodb/mongo-python-driver.git",
   ]

   [repo.groups.pymongo]
   repos = [
       "https://github.com/mongodb/specifications.git",
   ]

   [repo.groups.django]
   repos = [
       "https://github.com/django/django.git",
       "https://github.com/mongodb-labs/django-mongodb-backend.git",
   ]

   [repo.groups.custom]
   repos = [
       "https://github.com/your-org/your-repo.git",
   ]

You can add your own custom groups by editing the configuration file.

**Features:**

- User-specific configuration file (works with pip-installed package)
- Clones all repositories in a group to the configured base directory
- Skips repositories that already exist locally
- Fork-based workflow support with automatic upstream remote configuration
- Sync command to fetch from upstream and rebase current branch
- Provides clear progress feedback with emoji indicators
- Handles errors gracefully and continues with remaining repositories
- Easy to add custom repository groups

View Git Branches
-----------------

The ``dbx branch`` command allows you to run ``git branch`` in one or more repositories:

.. code-block:: bash

   # Show branches in a single repository
   dbx branch mongo-python-driver

   # Show all branches (including remote branches)
   dbx branch mongo-python-driver -a

   # Show branches with verbose information
   dbx branch mongo-python-driver -v

   # Show branches in all repositories in a group
   dbx branch -g pymongo

   # Show branches in all repositories in a group with arguments
   dbx branch -g pymongo -a

   # Show branches in a project
   dbx branch -p myproject

This command will:

1. Find the repository, group, or project by name
2. Run ``git branch`` with any provided arguments
3. Display the output for each repository

**Examples:**

.. code-block:: bash

   # View local branches in a single repo
   $ dbx branch mongo-python-driver
   🌿 mongo-python-driver:
   * main
     feature-branch

   # View all branches (local and remote)
   $ dbx branch mongo-python-driver -a
   🌿 mongo-python-driver: git branch -a
   * main
     feature-branch
     remotes/origin/HEAD -> origin/main
     remotes/origin/main
     remotes/origin/feature-branch

   # View branches across all repos in a group
   $ dbx branch -g pymongo
   Running git branch in 2 repository(ies) in group 'pymongo':

   🌿 mongo-python-driver:
   * main
   🌿 specifications:
   * master

   # View all branches (local and remote) across all repos in a group
   $ dbx branch -g pymongo -a
   Running git branch in 2 repository(ies) in group 'pymongo':

   🌿 mongo-python-driver: git branch -a
   * main
     feature-branch
     remotes/origin/HEAD -> origin/main
     remotes/origin/main
     remotes/origin/feature-branch
   🌿 specifications: git branch -a
   * master
     remotes/origin/HEAD -> origin/master
     remotes/origin/master

**Notes:**

- The command works with any repository that has been cloned using ``dbx clone``
- You can pass any valid ``git branch`` arguments (e.g., ``-a``, ``-r``, ``-v``, ``--merged``)
- The ``-a`` or ``--all`` flag shows all branches (local and remote) for all repositories
- When using with a group, the command runs in all repositories in that group
- Projects without a ``.git`` directory will be skipped with a warning
- Run ``dbx list`` to see all available repositories

Switch Git Branches
-------------------

The ``dbx switch`` command allows you to switch git branches in one or more repositories:

.. code-block:: bash

   # Switch to a branch in a single repository
   dbx switch mongo-python-driver PYTHON-5683

   # Switch branches in all repositories in a group
   dbx switch -g pymongo main

   # Switch branches in a project
   dbx switch -p myproject feature-branch

   # Create and switch to a new branch
   dbx switch mongo-python-driver new-feature --create

   # List available repositories
   dbx switch --list

This command will:

1. Find the repository, group, or project by name
2. Run ``git switch <branch>`` to switch to the specified branch
3. Optionally create the branch if ``--create`` flag is used
4. Display the output for each repository

**Examples:**

.. code-block:: bash

   # Switch to an existing branch
   $ dbx switch mongo-python-driver PYTHON-5683
   🔀 mongo-python-driver: Switched to branch 'PYTHON-5683'

   # Create and switch to a new branch
   $ dbx switch mongo-python-driver new-feature --create
   🔀 mongo-python-driver: Switched to a new branch 'new-feature'

   # Switch all repos in a group to main branch
   $ dbx switch -g pymongo main
   Switching to branch 'main' in 2 repository(ies) in group 'pymongo':

   🔀 mongo-python-driver: Switched to branch 'main'
   🔀 specifications: Switched to branch 'main'

**Notes:**

- The command works with any repository that has been cloned using ``dbx clone``
- When using with a group, the command runs in all repositories in that group
- The ``--create`` flag creates a new branch if it doesn't exist
- Projects without a ``.git`` directory will be skipped with a warning
- Run ``dbx list`` to see all available repositories

View Git Commit Logs
---------------------

The ``dbx log`` command allows you to view git commit logs from one or more repositories:

.. code-block:: bash

   # Show last 10 commits from a repository
   dbx log mongo-python-driver

   # Show last 20 commits
   dbx log -n 20 mongo-python-driver

   # Show logs in oneline format
   dbx log --oneline mongo-python-driver

   # Show logs from all repositories in a group
   dbx log -g pymongo

   # Show last 5 commits from all repos in a group
   dbx log -n 5 -g pymongo

   # Show logs from a project
   dbx log -p myproject

This command will:

1. Find the repository, group, or project by name
2. Run ``git log`` with the specified options
3. Display the commit logs for each repository

**Examples:**

.. code-block:: bash

   # View last 10 commits (default)
   $ dbx log mongo-python-driver
   📜 mongo-python-driver: Last 10 commits
   commit abc123...
   Author: John Doe <john@example.com>
   Date:   Mon Jan 1 12:00:00 2024 -0500

       Add new feature

   # View last 5 commits in oneline format
   $ dbx log -n 5 --oneline mongo-python-driver
   📜 mongo-python-driver: Last 5 commits (oneline)
   abc123 Add new feature
   def456 Fix bug
   ghi789 Update docs

   # View logs from all repos in a group
   $ dbx log -g pymongo
   📜 mongo-python-driver: Last 10 commits
   ...
   📜 specifications: Last 10 commits
   ...

**Notes:**

- The command works with any repository that has been cloned using ``dbx clone``
- Default number of commits shown is 10
- Use ``-n`` or ``--number`` to specify a custom number of commits
- Use ``--oneline`` for a compact one-line-per-commit format
- When using with a group, the command runs in all repositories in that group
- Projects without a ``.git`` directory will be skipped with a warning
- Run ``dbx list`` to see all available repositories

Open Repositories in Browser
-----------------------------

The ``dbx open`` command allows you to open repositories in your web browser:

.. code-block:: bash

   # Open a single repository in browser
   dbx open mongo-python-driver

   # Open all repositories in a group
   dbx open -g pymongo

This command will:

1. Find the repository or group by name
2. Get the git remote URL from the repository
3. Convert the git URL to a browser-friendly URL
4. Open the URL in your default web browser

**Examples:**

.. code-block:: bash

   # Open a single repository
   $ dbx open mongo-python-driver
   🌐 Opening mongo-python-driver in browser...
   # Opens https://github.com/mongodb/mongo-python-driver

   # Open all repos in a group
   $ dbx open -g pymongo
   Opening 2 repository(ies) in group 'pymongo' in browser:

   🌐 Opening mongo-python-driver in browser...
   🌐 Opening specifications in browser...

**Notes:**

- The command works with any repository that has been cloned using ``dbx clone``
- Automatically converts SSH URLs (``git@github.com:org/repo.git``) to HTTPS URLs (``https://github.com/org/repo``)
- Also works with HTTPS git URLs
- When using with a group, opens all repositories in that group
- Requires the repository to have an ``origin`` remote configured
- Run ``dbx list`` to see all available repositories
