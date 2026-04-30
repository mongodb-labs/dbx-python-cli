"""Tests for the project command."""

import re
from unittest.mock import patch, MagicMock

import typer
import pytest
from typer.testing import CliRunner

from dbx_python_cli.cli import app
from dbx_python_cli.commands.mongodb import ensure_mongodb

runner = CliRunner()


def strip_ansi(text):
    """Remove ANSI escape sequences from text."""
    ansi_escape = re.compile(r"\x1b\[[0-9;]*m")
    return ansi_escape.sub("", text)


def test_project_help():
    """Test that the project help command works."""
    result = runner.invoke(app, ["project", "--help"])
    assert result.exit_code == 0
    output = strip_ansi(result.stdout)
    assert "Project management commands" in output


def test_project_add_help():
    """Test that the project add help command works."""
    result = runner.invoke(app, ["project", "add", "--help"])
    assert result.exit_code == 0
    output = strip_ansi(result.stdout)
    assert "Create a new Django project using bundled templates" in output
    assert "--add-frontend" in output
    assert "--base-dir" in output


def test_project_remove_help():
    """Test that the project remove help command works."""
    result = runner.invoke(app, ["project", "remove", "--help"])
    assert result.exit_code == 0
    output = strip_ansi(result.stdout)
    assert "Delete a Django project by name" in output


def test_project_add_help_shows_wagtail():
    """Test that the project add help shows the --wagtail flag."""
    result = runner.invoke(app, ["project", "add", "--help"])
    assert result.exit_code == 0
    output = strip_ansi(result.stdout)
    assert "--wagtail" in output


def test_project_add_no_name_no_random():
    """Test that project add generates a random name when no name is provided."""
    # When no name is provided, a random name is automatically generated
    # This test just verifies the help text mentions this behavior
    result = runner.invoke(app, ["project", "add", "--help"])
    assert result.exit_code == 0
    output = strip_ansi(result.stdout)
    # Check that the help text mentions random name generation
    assert "random name" in output.lower()


def test_project_edit_help():
    """Test that the project edit help command works."""
    result = runner.invoke(app, ["project", "edit", "--help"])
    assert result.exit_code == 0
    output = strip_ansi(result.stdout)
    assert "Edit project settings file with your default editor" in output
    assert "--settings" in output
    assert "--directory" in output


# Tests for ensure_mongodb function


class TestEnsureMongodb:
    """Tests for the ensure_mongodb helper function."""

    def test_mongodb_uri_from_env_dict(self):
        """Test that MONGODB_URI from env dict is used when present."""
        env = {"MONGODB_URI": "mongodb://myhost:27017"}
        result = ensure_mongodb(env)
        assert result["MONGODB_URI"] == "mongodb://myhost:27017"

    def test_mongodb_uri_empty_string_is_used(self):
        """Test that empty MONGODB_URI in env dict is still used (key exists)."""
        env = {"MONGODB_URI": ""}
        result = ensure_mongodb(env)
        # The function uses the value as-is if the key exists
        assert result["MONGODB_URI"] == ""

    def test_mongodb_uri_from_config(self):
        """Test that MONGODB_URI from config is used when env not set."""
        env = {}
        with patch.dict("os.environ", {}, clear=True):
            with patch("dbx_python_cli.commands.mongodb.get_config") as mock_config:
                mock_config.return_value = {
                    "project": {
                        "default_env": {"MONGODB_URI": "mongodb://confighost:27017"}
                    }
                }
                result = ensure_mongodb(env)
                assert result["MONGODB_URI"] == "mongodb://confighost:27017"

    def test_mongodb_runner_reuses_existing_instance(self):
        """Test that existing mongodb-runner instance is reused."""
        env = {}
        with patch.dict("os.environ", {}, clear=True):
            with patch("dbx_python_cli.commands.mongodb.get_config") as mock_config:
                mock_config.return_value = {"project": {"default_env": {}}}

                with patch(
                    "dbx_python_cli.commands.mongodb.shutil.which",
                    return_value="/usr/bin/mongodb-runner",
                ):
                    with patch(
                        "dbx_python_cli.commands.mongodb.subprocess.run"
                    ) as mock_run:
                        # mongodb-runner ls (returns existing instance)
                        mock_run.return_value = MagicMock(
                            returncode=0,
                            stdout="abc123: mongodb://127.0.0.1:52065/\n",
                            stderr="",
                        )

                        result = ensure_mongodb(env)
                        assert result["MONGODB_URI"] == "mongodb://127.0.0.1:52065/"
                        assert mock_run.call_count == 1

    def test_mongodb_runner_started_on_success(self):
        """Test that mongodb-runner is started when no instance is running."""
        env = {}
        with patch.dict("os.environ", {}, clear=True):
            with patch("dbx_python_cli.commands.mongodb.get_config") as mock_config:
                mock_config.return_value = {"project": {"default_env": {}}}

                with patch(
                    "dbx_python_cli.commands.mongodb.shutil.which",
                    return_value="/usr/bin/mongodb-runner",
                ):
                    with patch(
                        "dbx_python_cli.commands.mongodb.subprocess.run"
                    ) as mock_run:
                        # First call: mongodb-runner ls (no instances)
                        # Second call: mongodb-runner start (success)
                        # Third call: mongodb-runner ls (returns the started instance)
                        mock_run.side_effect = [
                            MagicMock(
                                returncode=0, stdout="", stderr=""
                            ),  # mongodb-runner ls (empty)
                            MagicMock(
                                returncode=0, stdout="Started\n", stderr=""
                            ),  # mongodb-runner start
                            MagicMock(
                                returncode=0,
                                stdout="abc123: mongodb://127.0.0.1:52065/\n",
                                stderr="",
                            ),  # mongodb-runner ls
                        ]

                        result = ensure_mongodb(env)
                        assert result["MONGODB_URI"] == "mongodb://127.0.0.1:52065/"
                        assert mock_run.call_count == 3

    def test_mongodb_runner_failure_exits(self):
        """Test that mongodb-runner failure exits with 'no db running'."""
        env = {}
        with patch.dict("os.environ", {}, clear=True):
            with patch("dbx_python_cli.commands.mongodb.get_config") as mock_config:
                mock_config.return_value = {"project": {"default_env": {}}}

                with patch(
                    "dbx_python_cli.commands.mongodb.subprocess.run"
                ) as mock_run:
                    # First call: mongodb-runner ls (no instances)
                    # Second call: mongodb-runner start (failure)
                    mock_run.side_effect = [
                        MagicMock(
                            returncode=0, stdout="", stderr=""
                        ),  # mongodb-runner ls
                        MagicMock(
                            returncode=1, stdout="", stderr="MongoDB failed to start"
                        ),
                    ]

                    with pytest.raises(typer.Exit) as exc_info:
                        ensure_mongodb(env)
                    assert exc_info.value.exit_code == 1

    def test_mongodb_runner_timeout_exits(self):
        """Test that mongodb-runner timeout exits with 'no db running'."""
        import subprocess

        env = {}
        with patch.dict("os.environ", {}, clear=True):
            with patch("dbx_python_cli.commands.mongodb.get_config") as mock_config:
                mock_config.return_value = {"project": {"default_env": {}}}

                with patch(
                    "dbx_python_cli.commands.mongodb.subprocess.run"
                ) as mock_run:
                    # First call: mongodb-runner ls (no instances)
                    # Second call: timeout on start
                    mock_run.side_effect = [
                        MagicMock(
                            returncode=0, stdout="", stderr=""
                        ),  # mongodb-runner ls
                        subprocess.TimeoutExpired(cmd="npx", timeout=120),
                    ]

                    with pytest.raises(typer.Exit) as exc_info:
                        ensure_mongodb(env)
                    assert exc_info.value.exit_code == 1

    def test_npx_file_not_found_exits(self):
        """Test that FileNotFoundError exits with 'no db running'."""
        env = {}
        with patch.dict("os.environ", {}, clear=True):
            with patch("dbx_python_cli.commands.mongodb.get_config") as mock_config:
                mock_config.return_value = {"project": {"default_env": {}}}

                with patch(
                    "dbx_python_cli.commands.mongodb.subprocess.run"
                ) as mock_run:
                    mock_run.side_effect = FileNotFoundError("npx not found")

                    with pytest.raises(typer.Exit) as exc_info:
                        ensure_mongodb(env)
                    assert exc_info.value.exit_code == 1


def test_enable_wagtail_activates_settings(tmp_path):
    """Test that _enable_wagtail uncomments the Wagtail settings block."""
    from dbx_python_cli.commands.project import _enable_wagtail

    settings_dir = tmp_path / "myproject" / "settings"
    settings_dir.mkdir(parents=True)
    settings_file = settings_dir / "myproject.py"
    settings_file.write_text(
        "# Wagtail CMS Configuration\n"
        "# Uncomment the four lines below to enable Wagtail settings.\n"
        "# from .wagtail import *  # noqa\n"
        "# INSTALLED_APPS += WAGTAIL_INSTALLED_APPS  # noqa: F405\n"
        "# MIDDLEWARE += WAGTAIL_MIDDLEWARE  # noqa: F405\n"
        "# MIGRATION_MODULES.update(WAGTAIL_MIGRATION_MODULES)  # noqa: F405\n"
    )
    (tmp_path / "myproject" / "urls.py").write_text(
        "from django.urls import path\nurlpatterns = []\n"
    )

    _enable_wagtail(tmp_path, "myproject")

    content = settings_file.read_text()
    assert "# from .wagtail import *" not in content
    assert "from .wagtail import *  # noqa" in content
    assert "INSTALLED_APPS += WAGTAIL_INSTALLED_APPS  # noqa: F405" in content
    assert "MIDDLEWARE += WAGTAIL_MIDDLEWARE  # noqa: F405" in content
    assert (
        "MIGRATION_MODULES.update(WAGTAIL_MIGRATION_MODULES)  # noqa: F405" in content
    )


def test_enable_wagtail_adds_url_patterns(tmp_path):
    """Test that _enable_wagtail appends Wagtail URL patterns to urls.py."""
    from dbx_python_cli.commands.project import _enable_wagtail

    settings_dir = tmp_path / "myproject" / "settings"
    settings_dir.mkdir(parents=True)
    (settings_dir / "myproject.py").write_text("# settings\n")

    urls_file = tmp_path / "myproject" / "urls.py"
    urls_file.write_text("from django.urls import path\nurlpatterns = []\n")

    _enable_wagtail(tmp_path, "myproject")

    content = urls_file.read_text()
    assert "wagtailadmin_urls" in content
    assert 'path("cms/"' in content
    assert 'path("documents/"' in content
    assert "wagtail_urls" in content
    assert "MEDIA_URL" in content


def test_create_pyproject_toml_includes_wagtail_dep(tmp_path):
    """Test that _create_pyproject_toml adds wagtail to dependencies when wagtail=True."""
    from dbx_python_cli.commands.project import _create_pyproject_toml

    _create_pyproject_toml(tmp_path, "myproject", wagtail=True)

    content = (tmp_path / "pyproject.toml").read_text()
    deps_section = content[
        content.index("dependencies") : content.index("[project.optional-dependencies]")
    ]
    assert '"wagtail"' in deps_section


def test_create_pyproject_toml_excludes_wagtail_dep_by_default(tmp_path):
    """Test that _create_pyproject_toml does not add wagtail to dependencies by default."""
    from dbx_python_cli.commands.project import _create_pyproject_toml

    _create_pyproject_toml(tmp_path, "myproject")

    content = (tmp_path / "pyproject.toml").read_text()
    deps_section = content[
        content.index("dependencies") : content.index("[project.optional-dependencies]")
    ]
    assert '"wagtail"' not in deps_section


def test_fix_broken_editable_installs_reinstalls_missing_source(tmp_path):
    """Broken editable installs for declared deps (dist-info with missing source) get reinstalled."""
    import json
    from dbx_python_cli.commands.project import _fix_broken_editable_installs

    # Fake project with wagtail as a declared dependency
    project_path = tmp_path / "myproject"
    project_path.mkdir()
    (project_path / "pyproject.toml").write_text(
        '[project]\nname = "myproject"\ndependencies = ["wagtail"]\n'
    )

    site_packages = tmp_path / "lib" / "python3.x" / "site-packages"
    site_packages.mkdir(parents=True)

    dist_info = site_packages / "wagtail-7.4a0.dist-info"
    dist_info.mkdir()
    (dist_info / "direct_url.json").write_text(
        json.dumps(
            {"dir_info": {"editable": True}, "url": "file:///nonexistent/wagtail"}
        )
    )
    (dist_info / "top_level.txt").write_text("wagtail\n")

    python_path = "/fake/python"

    with patch("dbx_python_cli.commands.project.subprocess.run") as mock_run:
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=str(site_packages), stderr=""),
            MagicMock(returncode=1, stdout="", stderr="ModuleNotFoundError"),
            MagicMock(returncode=0, stdout="", stderr=""),
        ]

        _fix_broken_editable_installs(python_path, project_path)

    reinstall_call = mock_run.call_args_list[2]
    cmd = reinstall_call[0][0]
    assert "--reinstall" in cmd
    assert "wagtail" in cmd


def test_fix_broken_editable_installs_skips_undeclared_packages(tmp_path):
    """Broken editable installs for packages NOT in pyproject.toml are ignored."""
    import json
    from dbx_python_cli.commands.project import _fix_broken_editable_installs

    # Project declares only "requests", NOT "old-project"
    project_path = tmp_path / "myproject"
    project_path.mkdir()
    (project_path / "pyproject.toml").write_text(
        '[project]\nname = "myproject"\ndependencies = ["requests"]\n'
    )

    site_packages = tmp_path / "lib" / "python3.x" / "site-packages"
    site_packages.mkdir(parents=True)

    dist_info = site_packages / "old_project-1.0.dist-info"
    dist_info.mkdir()
    (dist_info / "direct_url.json").write_text(
        json.dumps(
            {"dir_info": {"editable": True}, "url": "file:///nonexistent/old-project"}
        )
    )
    (dist_info / "top_level.txt").write_text("old_project\n")

    python_path = "/fake/python"

    with patch("dbx_python_cli.commands.project.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0, stdout=str(site_packages), stderr=""
        )
        _fix_broken_editable_installs(python_path, project_path)

    # Only the site.getsitepackages() call — no import check, no reinstall
    assert mock_run.call_count == 1


def test_fix_broken_editable_installs_skips_valid_source(tmp_path):
    """Editable installs with an existing, valid source directory are left alone."""
    import json
    from dbx_python_cli.commands.project import _fix_broken_editable_installs

    project_path = tmp_path / "myproject"
    project_path.mkdir()
    (project_path / "pyproject.toml").write_text(
        '[project]\nname = "myproject"\ndependencies = ["mypackage"]\n'
    )

    site_packages = tmp_path / "lib" / "python3.x" / "site-packages"
    site_packages.mkdir(parents=True)

    source_dir = tmp_path / "mypackage"
    source_dir.mkdir()
    (source_dir / "pyproject.toml").write_text("[project]\nname='mypackage'\n")

    dist_info = site_packages / "mypackage-1.0.dist-info"
    dist_info.mkdir()
    (dist_info / "direct_url.json").write_text(
        json.dumps({"dir_info": {"editable": True}, "url": f"file://{source_dir}"})
    )
    (dist_info / "top_level.txt").write_text("mypackage\n")

    python_path = "/fake/python"

    with patch("dbx_python_cli.commands.project.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0, stdout=str(site_packages), stderr=""
        )
        _fix_broken_editable_installs(python_path, project_path)

    # Only the site.getsitepackages() call — source is valid, no reinstall
    assert mock_run.call_count == 1


def test_project_run_uses_django_group_venv(tmp_path):
    """Test that project run uses django group venv when no other venv is found."""
    import platform

    config_dir = tmp_path / ".config" / "dbx-python-cli"
    config_dir.mkdir(parents=True)
    config_path = config_dir / "config.toml"

    base_dir = tmp_path / "repos"
    base_dir.mkdir()

    # Create projects directory with a project
    projects_dir = base_dir / "projects"
    projects_dir.mkdir()
    project_dir = projects_dir / "testproject"
    project_dir.mkdir()
    (project_dir / "manage.py").write_text("# manage.py")

    # Create django group with venv
    django_dir = base_dir / "django"
    django_dir.mkdir()
    if platform.system() == "Windows":
        django_venv = django_dir / ".venv" / "Scripts"
        django_venv.mkdir(parents=True)
        (django_venv / "python.exe").write_text("#!/usr/bin/env python3\n")
    else:
        django_venv = django_dir / ".venv" / "bin"
        django_venv.mkdir(parents=True)
        (django_venv / "python").write_text("#!/usr/bin/env python3\n")

    base_dir_str = str(base_dir).replace("\\", "/")
    config_content = f"""[repo]
base_dir = "{base_dir_str}"
"""
    config_path.write_text(config_content)

    with patch("dbx_python_cli.utils.repo.get_config_path") as mock_get_path:
        with patch("dbx_python_cli.commands.project.subprocess.run") as mock_run:
            with patch("dbx_python_cli.utils.venv._is_venv", return_value=False):
                with patch(
                    "dbx_python_cli.utils.venv._get_python_path",
                    return_value="/usr/bin/python",
                ):
                    mock_get_path.return_value = config_path
                    mock_run.return_value = MagicMock(returncode=0)

                    runner.invoke(app, ["project", "run", "testproject"])

                    # Verify the python path used in subprocess.run
                    # Find the call that runs manage.py runserver
                    for call in mock_run.call_args_list:
                        call_args = call[0][0]
                        if len(call_args) > 1 and "manage.py" in str(call_args):
                            assert "django/.venv" in call_args[0]


def test_project_add_help_shows_qe():
    """Test that the project add help shows the --qe flag."""
    result = runner.invoke(app, ["project", "add", "--help"])
    assert result.exit_code == 0
    output = strip_ansi(result.stdout)
    assert "--qe" in output


def test_enable_qe_activates_settings(tmp_path):
    """Test that _enable_qe uncomments the QE settings block."""
    from dbx_python_cli.commands.project import _enable_qe

    settings_dir = tmp_path / "myproject" / "settings"
    settings_dir.mkdir(parents=True)
    settings_file = settings_dir / "myproject.py"
    settings_file.write_text(
        "# Queryable Encryption (QE) Configuration\n"
        "# Uncomment the two lines below to enable Queryable Encryption settings.\n"
        "# from .qe import *  # noqa\n"
        "# INSTALLED_APPS += QE_INSTALLED_APPS  # noqa: F405\n"
    )
    (settings_dir / "qe.py").write_text('QE_INSTALLED_APPS = ["medical_records"]\n')

    _enable_qe(tmp_path, "myproject")

    content = settings_file.read_text()
    assert "# from .qe import *" not in content
    assert "from .qe import *  # noqa" in content
    assert "INSTALLED_APPS += QE_INSTALLED_APPS  # noqa: F405" in content


def test_create_pyproject_toml_includes_pymongocrypt_when_qe(tmp_path):
    """Test that _create_pyproject_toml adds pymongocrypt to dependencies when qe=True."""
    from dbx_python_cli.commands.project import _create_pyproject_toml

    _create_pyproject_toml(tmp_path, "myproject", qe=True)

    content = (tmp_path / "pyproject.toml").read_text()
    deps_section = content[
        content.index("dependencies") : content.index("[project.optional-dependencies]")
    ]
    assert '"pymongocrypt"' in deps_section


def test_create_pyproject_toml_excludes_pymongocrypt_by_default(tmp_path):
    """Test that _create_pyproject_toml does not add pymongocrypt by default."""
    from dbx_python_cli.commands.project import _create_pyproject_toml

    _create_pyproject_toml(tmp_path, "myproject")

    content = (tmp_path / "pyproject.toml").read_text()
    deps_section = content[
        content.index("dependencies") : content.index("[project.optional-dependencies]")
    ]
    assert '"pymongocrypt"' not in deps_section


def test_clone_repo_from_config_not_in_config(tmp_path):
    """Returns None when repo name is not in any config group."""
    from dbx_python_cli.commands.project import _clone_repo_from_config

    config = {
        "repo": {
            "groups": {"mygroup": {"repos": ["https://github.com/org/other-repo.git"]}}
        }
    }
    result = _clone_repo_from_config("medical-records", tmp_path, config, flat=False)
    assert result is None


def test_clone_repo_from_config_clones_when_in_config(tmp_path):
    """Clones the repo and returns its path when it appears in a config group."""
    from dbx_python_cli.commands.project import _clone_repo_from_config

    config = {
        "repo": {
            "groups": {
                "mygroup": {"repos": ["https://github.com/mongodb/medical-records.git"]}
            }
        }
    }
    repo_path = tmp_path / "mygroup" / "medical-records"

    with patch("dbx_python_cli.commands.project.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        result = _clone_repo_from_config(
            "medical-records", tmp_path, config, flat=False
        )

    assert result == repo_path
    mock_run.assert_called_once_with(
        [
            "git",
            "clone",
            "https://github.com/mongodb/medical-records.git",
            str(repo_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )


def test_clone_repo_from_config_clone_failure_returns_none(tmp_path):
    """Returns None when git clone fails."""
    import subprocess
    from dbx_python_cli.commands.project import _clone_repo_from_config

    config = {
        "repo": {
            "groups": {
                "mygroup": {"repos": ["https://github.com/mongodb/medical-records.git"]}
            }
        }
    }

    with patch("dbx_python_cli.commands.project.subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.CalledProcessError(1, "git clone")
        result = _clone_repo_from_config(
            "medical-records", tmp_path, config, flat=False
        )

    assert result is None


def test_install_with_repos_auto_clones_from_config(tmp_path):
    """When a repo is not cloned locally but is in config, it gets cloned then installed."""
    from dbx_python_cli.commands.project import _install_with_repos

    config = {
        "repo": {
            "base_dir": str(tmp_path),
            "flat": False,
            "groups": {
                "mygroup": {"repos": ["https://github.com/mongodb/medical-records.git"]}
            },
        }
    }
    clone_path = tmp_path / "mygroup" / "medical-records"

    with (
        patch("dbx_python_cli.commands.project.get_config", return_value=config),
        patch("dbx_python_cli.commands.project.get_base_dir", return_value=tmp_path),
        patch("dbx_python_cli.utils.repo.find_all_repos", return_value=[]),
        patch(
            "dbx_python_cli.commands.project._clone_repo_from_config",
            return_value=clone_path,
        ) as mock_clone,
        patch(
            "dbx_python_cli.commands.project.install_package", return_value="success"
        ) as mock_install,
    ):
        _install_with_repos(["medical-records"], "/usr/bin/python")

    mock_clone.assert_called_once()
    mock_install.assert_called_once_with(
        clone_path,
        "/usr/bin/python",
        install_dir=None,
        extras=None,
        groups=None,
        verbose=False,
    )


def test_install_with_repos_skips_when_not_in_config(tmp_path):
    """Emits a warning and skips when repo is not local and not in config."""
    from dbx_python_cli.commands.project import _install_with_repos

    config = {"repo": {"base_dir": str(tmp_path), "flat": False, "groups": {}}}

    with (
        patch("dbx_python_cli.commands.project.get_config", return_value=config),
        patch("dbx_python_cli.commands.project.get_base_dir", return_value=tmp_path),
        patch("dbx_python_cli.utils.repo.find_all_repos", return_value=[]),
        patch(
            "dbx_python_cli.commands.project._clone_repo_from_config", return_value=None
        ),
        patch("dbx_python_cli.commands.project.install_package") as mock_install,
    ):
        _install_with_repos(["medical-records"], "/usr/bin/python")

    mock_install.assert_not_called()


def test_qe_with_medical_records_adds_app_to_installed_apps(tmp_path):
    """When --qe and --with medical-records are both used, medical_records must be in INSTALLED_APPS.

    _enable_qe uncomments the QE import block in the project settings, which adds
    QE_INSTALLED_APPS (containing medical_records) to INSTALLED_APPS.
    """
    from dbx_python_cli.commands.project import _enable_qe

    settings_dir = tmp_path / "myproject" / "settings"
    settings_dir.mkdir(parents=True)
    settings_file = settings_dir / "myproject.py"
    settings_file.write_text(
        "# from .qe import *  # noqa\n"
        "# INSTALLED_APPS += QE_INSTALLED_APPS  # noqa: F405\n"
    )
    qe_file = settings_dir / "qe.py"
    qe_file.write_text('QE_INSTALLED_APPS = ["medical_records"]\n')

    _enable_qe(tmp_path, "myproject")

    settings_content = settings_file.read_text()
    assert "from .qe import *  # noqa" in settings_content
    assert "INSTALLED_APPS += QE_INSTALLED_APPS  # noqa: F405" in settings_content
    assert '"medical_records"' in qe_file.read_text()
