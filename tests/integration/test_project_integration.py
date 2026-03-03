"""Integration tests for project commands."""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from dbx_python_cli.cli import app

runner = CliRunner()


def test_project_add_with_frontend(tmp_path):
    """Test creating a project with frontend."""
    config_dir = tmp_path / ".config" / "dbx-python-cli"
    config_dir.mkdir(parents=True)
    config_path = config_dir / "config.toml"

    base_dir = tmp_path / "repos"
    base_dir_str = str(base_dir).replace("\\", "/")

    config_content = f"""[repo]
base_dir = "{base_dir_str}"
"""
    config_path.write_text(config_content)

    with patch("dbx_python_cli.commands.repo_utils.get_config_path") as mock_get_path:
        mock_get_path.return_value = config_path

        result = runner.invoke(app, ["project", "add", "--no-install", "testproject"])
        assert result.exit_code == 0
        assert "Creating project: testproject" in result.stdout
        assert "Adding frontend" in result.stdout

        # Verify project structure
        project_path = base_dir / "projects" / "testproject"
        assert project_path.exists()
        assert (project_path / "manage.py").exists()
        assert (project_path / "pyproject.toml").exists()
        assert (project_path / "justfile").exists()
        assert (project_path / "testproject").is_dir()
        assert (project_path / "testproject" / "settings").is_dir()
        assert (project_path / "testproject" / "settings" / "base.py").exists()

        # Verify frontend
        frontend_path = project_path / "frontend"
        assert frontend_path.exists()
        assert (frontend_path / "package.json").exists()
        assert (frontend_path / "webpack").is_dir()


def test_project_add_without_frontend(tmp_path):
    """Test creating a project without frontend."""
    config_dir = tmp_path / ".config" / "dbx-python-cli"
    config_dir.mkdir(parents=True)
    config_path = config_dir / "config.toml"

    base_dir = tmp_path / "repos"
    base_dir_str = str(base_dir).replace("\\", "/")

    config_content = f"""[repo]
base_dir = "{base_dir_str}"
"""
    config_path.write_text(config_content)

    with patch("dbx_python_cli.commands.repo_utils.get_config_path") as mock_get_path:
        mock_get_path.return_value = config_path

        result = runner.invoke(
            app, ["project", "add", "--no-install", "simpleproject", "--no-frontend"]
        )
        assert result.exit_code == 0, (
            f"Exit code was {result.exit_code}, output: {result.output}"
        )
        assert "Creating project: simpleproject" in result.stdout

        # Verify project structure
        project_path = base_dir / "projects" / "simpleproject"
        assert project_path.exists()
        assert (project_path / "manage.py").exists()
        assert (project_path / "pyproject.toml").exists()

        # Verify no frontend
        frontend_path = project_path / "frontend"
        assert not frontend_path.exists()


def test_project_add_with_random_name(tmp_path):
    """Test creating a project with random name."""
    config_dir = tmp_path / ".config" / "dbx-python-cli"
    config_dir.mkdir(parents=True)
    config_path = config_dir / "config.toml"

    base_dir = tmp_path / "repos"
    base_dir_str = str(base_dir).replace("\\", "/")

    config_content = f"""[repo]
base_dir = "{base_dir_str}"
"""
    config_path.write_text(config_content)

    with patch("dbx_python_cli.commands.repo_utils.get_config_path") as mock_get_path:
        mock_get_path.return_value = config_path

        # When no name is provided, a random name is automatically generated
        result = runner.invoke(app, ["project", "add", "--no-install"])
        assert result.exit_code == 0
        assert "Creating project:" in result.stdout
        assert "Generated random project name:" in result.stdout

        # Verify a project was created
        projects_dir = base_dir / "projects"
        assert projects_dir.exists()
        project_dirs = list(projects_dir.iterdir())
        assert len(project_dirs) == 1
        assert project_dirs[0].is_dir()
        assert (project_dirs[0] / "manage.py").exists()


def test_project_add_custom_directory(tmp_path):
    """Test creating a project in a custom directory."""
    custom_dir = tmp_path / "custom_projects"
    custom_dir.mkdir()

    result = runner.invoke(
        app, ["project", "add", "--no-install", "customproject", "-d", str(custom_dir)]
    )
    assert result.exit_code == 0

    # Verify project in custom location
    project_path = custom_dir / "customproject"
    assert project_path.exists()
    assert (project_path / "manage.py").exists()


def test_project_add_with_base_dir_override(tmp_path):
    """Test creating a project with --base-dir override (uses it as project root)."""
    config_dir = tmp_path / ".config" / "dbx-python-cli"
    config_dir.mkdir(parents=True)
    config_path = config_dir / "config.toml"

    # Set up config with a base_dir
    base_dir = tmp_path / "repos"
    base_dir_str = str(base_dir).replace("\\", "/")

    config_content = f"""[repo]
base_dir = "{base_dir_str}"
"""
    config_path.write_text(config_content)

    # Use --base-dir to specify the exact project location
    project_path = tmp_path / "custom_location" / "myproject"

    with patch("dbx_python_cli.commands.repo_utils.get_config_path") as mock_get_path:
        mock_get_path.return_value = config_path

        result = runner.invoke(
            app,
            [
                "project",
                "add",
                "--no-install",
                "myproject",
                "--base-dir",
                str(project_path),
            ],
        )
        assert result.exit_code == 0

        # Verify project is created directly at the specified path
        assert project_path.exists()
        assert (project_path / "manage.py").exists()
        assert (project_path / "pyproject.toml").exists()

        # Verify the inner project module exists (this is normal Django structure)
        inner_module = project_path / "myproject"
        assert inner_module.exists()
        assert (inner_module / "settings").is_dir()

        # Verify it was NOT created with double nesting
        wrong_path = project_path / "myproject" / "myproject"
        assert not wrong_path.exists()


def test_project_add_default_settings(tmp_path):
    """Test creating a project uses project name as default settings module."""
    config_dir = tmp_path / ".config" / "dbx-python-cli"
    config_dir.mkdir(parents=True)
    config_path = config_dir / "config.toml"

    base_dir = tmp_path / "repos"
    base_dir_str = str(base_dir).replace("\\", "/")

    config_content = f"""[repo]
base_dir = "{base_dir_str}"
"""
    config_path.write_text(config_content)

    with patch("dbx_python_cli.commands.repo_utils.get_config_path") as mock_get_path:
        mock_get_path.return_value = config_path

        result = runner.invoke(app, ["project", "add", "--no-install", "myproject"])
        assert result.exit_code == 0

        # Verify pyproject.toml has correct settings (should use project name)
        project_path = base_dir / "projects" / "myproject"
        pyproject_content = (project_path / "pyproject.toml").read_text()
        assert "DJANGO_SETTINGS_MODULE" in pyproject_content
        assert "myproject.settings.myproject" in pyproject_content


def test_project_remove(tmp_path):
    """Test removing a project."""
    config_dir = tmp_path / ".config" / "dbx-python-cli"
    config_dir.mkdir(parents=True)
    config_path = config_dir / "config.toml"

    base_dir = tmp_path / "repos"
    base_dir_str = str(base_dir).replace("\\", "/")

    config_content = f"""[repo]
base_dir = "{base_dir_str}"
"""
    config_path.write_text(config_content)

    with patch("dbx_python_cli.commands.repo_utils.get_config_path") as mock_get_path:
        mock_get_path.return_value = config_path

        # First create a project
        result = runner.invoke(app, ["project", "add", "--no-install", "removetest"])
        assert result.exit_code == 0

        project_path = base_dir / "projects" / "removetest"
        assert project_path.exists()

        # Now remove it
        result = runner.invoke(app, ["project", "remove", "removetest"])
        assert result.exit_code == 0
        assert "Removed project removetest" in result.stdout

        # Verify it's gone
        assert not project_path.exists()


def test_project_remove_nonexistent(tmp_path):
    """Test removing a project that doesn't exist."""
    config_dir = tmp_path / ".config" / "dbx-python-cli"
    config_dir.mkdir(parents=True)
    config_path = config_dir / "config.toml"

    base_dir = tmp_path / "repos"
    base_dir_str = str(base_dir).replace("\\", "/")

    config_content = f"""[repo]
base_dir = "{base_dir_str}"
"""
    config_path.write_text(config_content)

    with patch("dbx_python_cli.commands.repo_utils.get_config_path") as mock_get_path:
        mock_get_path.return_value = config_path

        result = runner.invoke(app, ["project", "remove", "nonexistent"])
        assert result.exit_code == 0
        assert "does not exist" in result.stdout or "does not exist" in result.stderr


def test_project_remove_last_project_removes_projects_dir(tmp_path):
    """Test that removing the last project also removes the projects/ directory."""
    config_dir = tmp_path / ".config" / "dbx-python-cli"
    config_dir.mkdir(parents=True)
    config_path = config_dir / "config.toml"

    base_dir = tmp_path / "repos"
    base_dir_str = str(base_dir).replace("\\", "/")

    config_content = f"""[repo]
base_dir = "{base_dir_str}"
"""
    config_path.write_text(config_content)

    with patch("dbx_python_cli.commands.repo_utils.get_config_path") as mock_get_path:
        mock_get_path.return_value = config_path

        # Create a single project
        result = runner.invoke(app, ["project", "add", "--no-install", "onlyproject"])
        assert result.exit_code == 0

        projects_dir = base_dir / "projects"
        project_path = projects_dir / "onlyproject"
        assert project_path.exists()
        assert projects_dir.exists()

        # Remove the only project
        result = runner.invoke(app, ["project", "remove", "onlyproject"])
        assert result.exit_code == 0
        assert "Removed project onlyproject" in result.stdout
        assert "Removed empty projects directory" in result.stdout

        # Verify both project and projects directory are gone
        assert not project_path.exists()
        assert not projects_dir.exists()


def test_project_remove_one_of_many_keeps_projects_dir(tmp_path):
    """Test that removing one project when multiple exist keeps the projects/ directory."""
    config_dir = tmp_path / ".config" / "dbx-python-cli"
    config_dir.mkdir(parents=True)
    config_path = config_dir / "config.toml"

    base_dir = tmp_path / "repos"
    base_dir_str = str(base_dir).replace("\\", "/")

    config_content = f"""[repo]
base_dir = "{base_dir_str}"
"""
    config_path.write_text(config_content)

    with patch("dbx_python_cli.commands.repo_utils.get_config_path") as mock_get_path:
        mock_get_path.return_value = config_path

        # Create two projects
        result = runner.invoke(app, ["project", "add", "--no-install", "project1"])
        assert result.exit_code == 0
        result = runner.invoke(app, ["project", "add", "--no-install", "project2"])
        assert result.exit_code == 0

        projects_dir = base_dir / "projects"
        project1_path = projects_dir / "project1"
        project2_path = projects_dir / "project2"
        assert project1_path.exists()
        assert project2_path.exists()
        assert projects_dir.exists()

        # Remove one project
        result = runner.invoke(app, ["project", "remove", "project1"])
        assert result.exit_code == 0
        assert "Removed project project1" in result.stdout
        assert "Removed empty projects directory" not in result.stdout

        # Verify only project1 is gone, projects directory still exists
        assert not project1_path.exists()
        assert project2_path.exists()
        assert projects_dir.exists()


def test_project_install_with_dbx_install(tmp_path):
    """Test that projects can be installed with dbx install command."""
    config_dir = tmp_path / ".config" / "dbx-python-cli"
    config_dir.mkdir(parents=True)
    config_path = config_dir / "config.toml"

    base_dir = tmp_path / "repos"
    base_dir_str = str(base_dir).replace("\\", "/")

    config_content = f"""[repo]
base_dir = "{base_dir_str}"
"""
    config_path.write_text(config_content)

    with patch("dbx_python_cli.commands.repo_utils.get_config_path") as mock_get_path_1:
        mock_get_path_1.return_value = config_path

        # Create a project
        result = runner.invoke(
            app, ["project", "add", "--no-install", "installtest", "--no-frontend"]
        )
        assert result.exit_code == 0

    # Now test that it can be found by dbx install
    with patch("dbx_python_cli.commands.repo_utils.get_config_path") as mock_get_path_2:
        mock_get_path_2.return_value = config_path

        # List should show the project
        result = runner.invoke(app, ["install", "--list"])
        assert result.exit_code == 0
        # The project should be listed (it's in projects group)
        assert "installtest" in result.stdout or "projects" in result.stdout


def test_project_with_frontend_structure(tmp_path):
    """Test that frontend has correct structure."""
    config_dir = tmp_path / ".config" / "dbx-python-cli"
    config_dir.mkdir(parents=True)
    config_path = config_dir / "config.toml"

    base_dir = tmp_path / "repos"
    base_dir_str = str(base_dir).replace("\\", "/")

    config_content = f"""[repo]
base_dir = "{base_dir_str}"
"""
    config_path.write_text(config_content)

    with patch("dbx_python_cli.commands.repo_utils.get_config_path") as mock_get_path:
        mock_get_path.return_value = config_path

        result = runner.invoke(app, ["project", "add", "--no-install", "frontendtest"])
        assert result.exit_code == 0

        # Verify detailed frontend structure
        frontend_path = base_dir / "projects" / "frontendtest" / "frontend"
        assert (frontend_path / "package.json").exists()
        assert (frontend_path / "webpack").is_dir()
        assert (frontend_path / "src").is_dir()

        # Check package.json has content
        package_json = (frontend_path / "package.json").read_text()
        assert "name" in package_json
        assert "dependencies" in package_json or "devDependencies" in package_json


def test_project_list(tmp_path):
    """Test listing projects with 'project list' subcommand."""
    config_dir = tmp_path / ".config" / "dbx-python-cli"
    config_dir.mkdir(parents=True)
    config_path = config_dir / "config.toml"

    base_dir = tmp_path / "repos"
    base_dir_str = str(base_dir).replace("\\", "/")

    config_content = f"""[repo]
base_dir = "{base_dir_str}"
"""
    config_path.write_text(config_content)

    with patch("dbx_python_cli.commands.repo_utils.get_config_path") as mock_get_path:
        mock_get_path.return_value = config_path

        # Test with no projects directory
        result = runner.invoke(app, ["project", "list"])
        assert result.exit_code == 0
        assert (
            "No projects" in result.stdout
        )  # Could be "No projects directory found" or "No projects found"

        # Create a project with frontend
        result = runner.invoke(app, ["project", "add", "--no-install", "project1"])
        assert result.exit_code == 0

        # Create a project without frontend
        result = runner.invoke(
            app, ["project", "add", "--no-install", "project2", "--no-frontend"]
        )
        assert result.exit_code == 0

        # List projects
        result = runner.invoke(app, ["project", "list"])
        assert result.exit_code == 0
        assert "Found 2 project(s)" in result.stdout
        assert "project1" in result.stdout
        assert "project2" in result.stdout
        assert "🎨" in result.stdout  # Frontend marker should appear


def test_project_run_settings_module(tmp_path):
    """Test that run command uses correct settings module."""
    config_dir = tmp_path / ".config" / "dbx-python-cli"
    config_dir.mkdir(parents=True)
    config_path = config_dir / "config.toml"

    base_dir = tmp_path / "repos"
    projects_dir = base_dir / "projects"
    projects_dir.mkdir(parents=True)
    base_dir_str = str(base_dir).replace("\\", "/")

    config_content = f"""[repo]
base_dir = "{base_dir_str}"
"""
    config_path.write_text(config_content)

    # Create a minimal project structure
    project_path = projects_dir / "testproject"
    project_path.mkdir()
    (project_path / "manage.py").write_text("# manage.py")

    with patch("dbx_python_cli.commands.repo_utils.get_config_path") as mock_get_path:
        with patch("dbx_python_cli.commands.project.get_venv_info") as mock_venv_info:
            with patch("dbx_python_cli.commands.project.subprocess.run") as mock_run:
                mock_get_path.return_value = config_path
                mock_venv_info.return_value = ("/usr/bin/python", "venv")
                mock_run.return_value = MagicMock(returncode=0)

                # Test default settings (should use project name)
                result = runner.invoke(app, ["project", "run", "testproject"])
                # The command will fail because manage.py doesn't work, but we can check the output
                assert (
                    "DJANGO_SETTINGS_MODULE=testproject.settings.testproject"
                    in result.stdout
                )

                # Test with explicit settings
                result = runner.invoke(
                    app, ["project", "run", "testproject", "--settings", "base"]
                )
                assert (
                    "DJANGO_SETTINGS_MODULE=testproject.settings.base" in result.stdout
                )


def test_project_run_nonexistent(tmp_path):
    """Test running a nonexistent project."""
    config_dir = tmp_path / ".config" / "dbx-python-cli"
    config_dir.mkdir(parents=True)
    config_path = config_dir / "config.toml"

    base_dir = tmp_path / "repos"
    base_dir_str = str(base_dir).replace("\\", "/")

    config_content = f"""[repo]
base_dir = "{base_dir_str}"
"""
    config_path.write_text(config_content)

    with patch("dbx_python_cli.commands.repo_utils.get_config_path") as mock_get_path:
        mock_get_path.return_value = config_path

        # Try to run a nonexistent project
        result = runner.invoke(app, ["project", "run", "nonexistent"])
        assert result.exit_code == 1
        # Error messages go to stdout in typer
        output = result.stdout + (result.stderr or "")
        assert "not found" in output.lower()


def test_project_edit_nonexistent(tmp_path):
    """Test editing a nonexistent project."""
    config_dir = tmp_path / ".config" / "dbx-python-cli"
    config_dir.mkdir(parents=True)
    config_path = config_dir / "config.toml"

    base_dir = tmp_path / "repos"
    base_dir_str = str(base_dir).replace("\\", "/")

    config_content = f"""[repo]
base_dir = "{base_dir_str}"
"""
    config_path.write_text(config_content)

    with patch("dbx_python_cli.commands.repo_utils.get_config_path") as mock_get_path:
        mock_get_path.return_value = config_path

        # Try to edit a nonexistent project
        result = runner.invoke(app, ["project", "edit", "nonexistent"])
        assert result.exit_code == 1
        output = result.stdout + (result.stderr or "")
        assert "not found" in output.lower()


def test_project_edit_with_editor(tmp_path):
    """Test editing a project's settings file."""
    config_dir = tmp_path / ".config" / "dbx-python-cli"
    config_dir.mkdir(parents=True)
    config_path = config_dir / "config.toml"

    base_dir = tmp_path / "repos"
    base_dir_str = str(base_dir).replace("\\", "/")

    config_content = f"""[repo]
base_dir = "{base_dir_str}"
"""
    config_path.write_text(config_content)

    with patch("dbx_python_cli.commands.repo_utils.get_config_path") as mock_get_path:
        mock_get_path.return_value = config_path

        # Create a project
        result = runner.invoke(
            app, ["project", "add", "--no-install", "editproject", "--no-frontend"]
        )
        assert result.exit_code == 0

        # Verify settings file exists
        project_path = base_dir / "projects" / "editproject"
        settings_file = project_path / "editproject" / "settings" / "editproject.py"
        assert settings_file.exists()

        # Mock the editor subprocess
        with patch("subprocess.run") as mock_run:
            from unittest.mock import MagicMock

            mock_run.return_value = MagicMock(returncode=0)

            # Test editing with mocked editor
            with patch.dict("os.environ", {"EDITOR": "nano"}):
                result = runner.invoke(app, ["project", "edit", "editproject"])
                assert result.exit_code == 0
                assert "Opening" in result.stdout
                assert "editproject.py" in result.stdout
                assert "Settings file saved" in result.stdout

                # Verify subprocess was called with correct arguments
                mock_run.assert_called_once()
                args = mock_run.call_args[0][0]
                assert args[0] == "nano"
                assert str(settings_file) in args[1]


def test_project_edit_with_settings_option(tmp_path):
    """Test editing a specific settings file."""
    config_dir = tmp_path / ".config" / "dbx-python-cli"
    config_dir.mkdir(parents=True)
    config_path = config_dir / "config.toml"

    base_dir = tmp_path / "repos"
    base_dir_str = str(base_dir).replace("\\", "/")

    config_content = f"""[repo]
base_dir = "{base_dir_str}"
"""
    config_path.write_text(config_content)

    with patch("dbx_python_cli.commands.repo_utils.get_config_path") as mock_get_path:
        mock_get_path.return_value = config_path

        # Create a project
        result = runner.invoke(
            app, ["project", "add", "--no-install", "settingstest", "--no-frontend"]
        )
        assert result.exit_code == 0

        # Verify base settings file exists
        project_path = base_dir / "projects" / "settingstest"
        base_settings_file = project_path / "settingstest" / "settings" / "base.py"
        assert base_settings_file.exists()

        # Mock the editor subprocess
        with patch("subprocess.run") as mock_run:
            from unittest.mock import MagicMock

            mock_run.return_value = MagicMock(returncode=0)

            # Test editing base settings
            with patch.dict("os.environ", {"EDITOR": "vim"}):
                result = runner.invoke(
                    app, ["project", "edit", "settingstest", "--settings", "base"]
                )
                assert result.exit_code == 0
                assert "base.py" in result.stdout

                # Verify subprocess was called with correct arguments
                mock_run.assert_called_once()
                args = mock_run.call_args[0][0]
                assert args[0] == "vim"
                assert str(base_settings_file) in args[1]


def test_project_edit_newest_project(tmp_path):
    """Test editing the newest project without specifying name."""
    config_dir = tmp_path / ".config" / "dbx-python-cli"
    config_dir.mkdir(parents=True)
    config_path = config_dir / "config.toml"

    base_dir = tmp_path / "repos"
    base_dir_str = str(base_dir).replace("\\", "/")

    config_content = f"""[repo]
base_dir = "{base_dir_str}"
"""
    config_path.write_text(config_content)

    with patch("dbx_python_cli.commands.repo_utils.get_config_path") as mock_get_path:
        mock_get_path.return_value = config_path

        # Create two projects
        result = runner.invoke(
            app, ["project", "add", "--no-install", "oldproject", "--no-frontend"]
        )
        assert result.exit_code == 0

        import time

        time.sleep(0.1)  # Ensure different modification times

        result = runner.invoke(
            app, ["project", "add", "--no-install", "newproject", "--no-frontend"]
        )
        assert result.exit_code == 0

        # Mock the editor subprocess
        with patch("subprocess.run") as mock_run:
            from unittest.mock import MagicMock

            mock_run.return_value = MagicMock(returncode=0)

            # Test editing without specifying project name (should use newest)
            with patch.dict("os.environ", {"EDITOR": "nano"}):
                result = runner.invoke(app, ["project", "edit"])
                assert result.exit_code == 0
                assert (
                    "No project specified, using newest: 'newproject'" in result.stdout
                )
                assert "newproject.py" in result.stdout


def test_project_settings_has_installed_apps(tmp_path):
    """Test that project-specific settings file has INSTALLED_APPS."""
    config_dir = tmp_path / ".config" / "dbx-python-cli"
    config_dir.mkdir(parents=True)
    config_path = config_dir / "config.toml"

    base_dir = tmp_path / "repos"
    base_dir_str = str(base_dir).replace("\\", "/")

    config_content = f"""[repo]
base_dir = "{base_dir_str}"
"""
    config_path.write_text(config_content)

    with patch("dbx_python_cli.commands.repo_utils.get_config_path") as mock_get_path:
        mock_get_path.return_value = config_path

        # Create a project
        result = runner.invoke(
            app, ["project", "add", "--no-install", "appsproject", "--no-frontend"]
        )
        assert result.exit_code == 0, (
            f"Exit code was {result.exit_code}, output: {result.output}"
        )

        # Verify project-specific settings file has INSTALLED_APPS
        project_path = base_dir / "projects" / "appsproject"
        settings_file = project_path / "appsproject" / "settings" / "appsproject.py"
        assert settings_file.exists()

        settings_content = settings_file.read_text()
        assert "INSTALLED_APPS" in settings_content
        assert "INSTALLED_APPS += [  # noqa: F405" in settings_content
        assert "# Add your project-specific apps here" in settings_content
