"""Tests for the repo module utilities."""

from pathlib import Path

import pytest

from dbx_python_cli.utils.repo import (
    _expand_env_var_value,
    find_all_repos,
    find_repo_by_name,
    get_group_priority,
    get_preferred_branch,
    get_global_groups,
    get_test_env_vars,
    list_repos,
)


@pytest.fixture
def temp_repos_dir(tmp_path):
    """Create a temporary repos directory with test repos."""
    repos_dir = tmp_path / "repos"
    repos_dir.mkdir()

    # Create group directories with repos
    django_group = repos_dir / "django"
    django_group.mkdir()
    (django_group / "django").mkdir()
    (django_group / "django" / ".git").mkdir()
    (django_group / "django-mongodb-backend").mkdir()
    (django_group / "django-mongodb-backend" / ".git").mkdir()

    pymongo_group = repos_dir / "pymongo"
    pymongo_group.mkdir()
    (pymongo_group / "mongo-python-driver").mkdir()
    (pymongo_group / "mongo-python-driver" / ".git").mkdir()

    # Create a directory without .git (should be ignored)
    (pymongo_group / "not-a-repo").mkdir()

    # Create a file (should be ignored)
    (django_group / "README.md").write_text("test")

    return repos_dir


def test_find_all_repos_empty_dir(tmp_path):
    """Test find_all_repos with an empty directory."""
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()

    repos = find_all_repos(empty_dir)
    assert repos == []


def test_find_all_repos_nonexistent_dir(tmp_path):
    """Test find_all_repos with a nonexistent directory."""
    nonexistent = tmp_path / "nonexistent"

    repos = find_all_repos(nonexistent)
    assert repos == []


def test_find_all_repos_with_repos(temp_repos_dir):
    """Test find_all_repos with actual repos."""
    repos = find_all_repos(temp_repos_dir)

    assert len(repos) == 3
    repo_names = [r["name"] for r in repos]
    assert "django" in repo_names
    assert "django-mongodb-backend" in repo_names
    assert "mongo-python-driver" in repo_names
    assert "not-a-repo" not in repo_names  # No .git directory


def test_find_all_repos_structure(temp_repos_dir):
    """Test that find_all_repos returns correct structure."""
    repos = find_all_repos(temp_repos_dir)

    for repo in repos:
        assert "name" in repo
        assert "path" in repo
        assert "group" in repo
        assert isinstance(repo["path"], Path)


def test_find_all_repos_groups(temp_repos_dir):
    """Test that find_all_repos correctly identifies groups."""
    repos = find_all_repos(temp_repos_dir)

    django_repos = [r for r in repos if r["group"] == "django"]
    pymongo_repos = [r for r in repos if r["group"] == "pymongo"]

    assert len(django_repos) == 2
    assert len(pymongo_repos) == 1


def test_find_repo_by_name_found(temp_repos_dir):
    """Test find_repo_by_name when repo exists."""
    repo = find_repo_by_name("django", temp_repos_dir)

    assert repo is not None
    assert repo["name"] == "django"
    assert repo["group"] == "django"
    assert repo["path"] == temp_repos_dir / "django" / "django"


def test_find_repo_by_name_not_found(temp_repos_dir):
    """Test find_repo_by_name when repo doesn't exist."""
    repo = find_repo_by_name("nonexistent-repo", temp_repos_dir)

    assert repo is None


def test_find_repo_by_name_empty_dir(tmp_path):
    """Test find_repo_by_name with empty directory."""
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()

    repo = find_repo_by_name("any-repo", empty_dir)
    assert repo is None


def test_list_repos_empty(tmp_path):
    """Test list_repos with no repos."""
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()

    result = list_repos(empty_dir)
    assert result is None


def test_list_repos_default_format(temp_repos_dir):
    """Test list_repos with default format (tree structure)."""
    result = list_repos(temp_repos_dir, format_style="default")

    assert result is not None
    # Tree format should show groups as directories
    assert "django/" in result
    assert "pymongo/" in result
    # And repos under their groups
    assert "django" in result
    assert "django-mongodb-backend" in result
    assert "mongo-python-driver" in result
    # Should have tree characters
    assert "├──" in result or "└──" in result


def test_list_repos_grouped_format(temp_repos_dir):
    """Test list_repos with grouped format."""
    result = list_repos(temp_repos_dir, format_style="grouped")

    assert result is not None
    assert "[django]" in result
    assert "[pymongo]" in result
    assert "• django" in result
    assert "• django-mongodb-backend" in result
    assert "• mongo-python-driver" in result


def test_list_repos_simple_format(temp_repos_dir):
    """Test list_repos with simple format."""
    result = list_repos(temp_repos_dir, format_style="simple")

    assert result is not None
    assert "• django (django)" in result
    assert "• django-mongodb-backend (django)" in result
    assert "• mongo-python-driver (pymongo)" in result


def test_get_test_env_vars_no_config(tmp_path):
    """Test get_test_env_vars with no environment variables configured."""
    config = {
        "repo": {
            "base_dir": str(tmp_path),
            "groups": {
                "pymongo": {"repos": ["git@github.com:mongodb/mongo-python-driver.git"]}
            },
        }
    }

    env_vars = get_test_env_vars(config, "pymongo", "mongo-python-driver", tmp_path)
    assert env_vars == {}


def test_get_test_env_vars_with_repo_specific_vars(tmp_path):
    """Test get_test_env_vars with repo-specific environment variables."""
    config = {
        "repo": {
            "base_dir": str(tmp_path),
            "groups": {
                "pymongo": {
                    "repos": ["git@github.com:mongodb/mongo-python-driver.git"],
                    "test_env": {
                        "mongo-python-driver": {
                            "DRIVERS_TOOLS": "{base_dir}/{group}/drivers-evergreen-tools",
                            "TEST_VAR": "test_value",
                        }
                    },
                }
            },
        }
    }

    env_vars = get_test_env_vars(config, "pymongo", "mongo-python-driver", tmp_path)
    assert "DRIVERS_TOOLS" in env_vars
    assert "TEST_VAR" in env_vars
    assert env_vars["TEST_VAR"] == "test_value"
    expected_path = str(Path(tmp_path) / "pymongo" / "drivers-evergreen-tools")
    assert env_vars["DRIVERS_TOOLS"] == expected_path


def test_get_test_env_vars_nonexistent_group(tmp_path):
    """Test get_test_env_vars with a group that doesn't exist."""
    config = {
        "repo": {
            "base_dir": str(tmp_path),
            "groups": {
                "pymongo": {"repos": ["git@github.com:mongodb/mongo-python-driver.git"]}
            },
        }
    }

    env_vars = get_test_env_vars(config, "nonexistent", "some-repo", tmp_path)
    assert env_vars == {}


def test_expand_env_var_value_with_placeholders(tmp_path):
    """Test _expand_env_var_value with placeholders."""
    value = "{base_dir}/{group}/drivers-evergreen-tools"
    expanded = _expand_env_var_value(value, tmp_path, "pymongo")
    expected = str(Path(tmp_path) / "pymongo" / "drivers-evergreen-tools")
    assert expanded == expected


def test_expand_env_var_value_with_tilde(tmp_path):
    """Test _expand_env_var_value with tilde expansion."""
    value = "~/some/path"
    expanded = _expand_env_var_value(value, tmp_path, "pymongo")
    # Should expand to user's home directory
    assert expanded.startswith(str(Path.home()))
    expected_suffix = str(Path("some") / "path")
    assert expected_suffix in expanded


def test_expand_env_var_value_plain_string(tmp_path):
    """Test _expand_env_var_value with a plain string."""
    value = "plain_value"
    expanded = _expand_env_var_value(value, tmp_path, "pymongo")
    assert expanded == "plain_value"


def test_expand_env_var_value_non_string(tmp_path):
    """Test _expand_env_var_value with non-string value."""
    value = 123
    expanded = _expand_env_var_value(value, tmp_path, "pymongo")
    assert expanded == "123"


# ---------------------------------------------------------------------------
# get_global_groups tests
# ---------------------------------------------------------------------------


def test_get_global_groups_returns_list(tmp_path):
    """Test get_global_groups returns the configured list."""
    config = {
        "repo": {
            "base_dir": str(tmp_path),
            "global_groups": ["global"],
            "groups": {},
        }
    }
    assert get_global_groups(config) == ["global"]


def test_get_global_groups_multiple(tmp_path):
    """Test get_global_groups with multiple global groups."""
    config = {
        "repo": {
            "global_groups": ["global", "shared"],
            "groups": {},
        }
    }
    assert get_global_groups(config) == ["global", "shared"]


def test_get_global_groups_not_configured(tmp_path):
    """Test get_global_groups returns empty list when not configured."""
    config = {"repo": {"base_dir": str(tmp_path), "groups": {}}}
    assert get_global_groups(config) == []


def test_get_global_groups_empty_config():
    """Test get_global_groups with an empty config."""
    assert get_global_groups({}) == []


# ---------------------------------------------------------------------------
# get_test_env_vars global fallback tests
# ---------------------------------------------------------------------------


def test_get_test_env_vars_global_fallback(tmp_path):
    """Test that get_test_env_vars falls back to global groups when the
    repo's own group has no test_env entry for the repo."""
    config = {
        "repo": {
            "base_dir": str(tmp_path),
            "global_groups": ["global"],
            "groups": {
                "global": {
                    "repos": ["git@github.com:mongodb/mongo-python-driver.git"],
                    "test_env": {
                        "mongo-python-driver": {
                            "DRIVERS_TOOLS": "{base_dir}/pymongo/drivers-evergreen-tools",
                            "USE_ACTIVE_VENV": "1",
                        }
                    },
                },
                "django": {
                    "repos": ["git@github.com:mongodb-labs/django-mongodb-backend.git"],
                },
            },
        }
    }

    # mongo-python-driver was cloned into 'django' group but its test_env
    # is defined in 'global' — the fallback should find it.
    env_vars = get_test_env_vars(config, "django", "mongo-python-driver", tmp_path)
    assert "DRIVERS_TOOLS" in env_vars
    assert "USE_ACTIVE_VENV" in env_vars
    expected_path = str(tmp_path / "pymongo" / "drivers-evergreen-tools")
    assert env_vars["DRIVERS_TOOLS"] == expected_path


def test_get_test_env_vars_own_group_takes_priority(tmp_path):
    """Test that a repo's own group test_env takes priority over global fallback."""
    config = {
        "repo": {
            "global_groups": ["global"],
            "groups": {
                "global": {
                    "test_env": {"mongo-python-driver": {"MY_VAR": "from_global"}}
                },
                "pymongo": {
                    "test_env": {"mongo-python-driver": {"MY_VAR": "from_pymongo"}}
                },
            },
        }
    }

    env_vars = get_test_env_vars(config, "pymongo", "mongo-python-driver", tmp_path)
    assert env_vars["MY_VAR"] == "from_pymongo"


def test_get_test_env_vars_no_global_groups(tmp_path):
    """Test get_test_env_vars with no global_groups configured returns empty dict
    when the group has no test_env."""
    config = {
        "repo": {
            "groups": {
                "django": {
                    "repos": ["git@github.com:mongodb-labs/django-mongodb-backend.git"],
                },
            },
        }
    }

    env_vars = get_test_env_vars(config, "django", "mongo-python-driver", tmp_path)
    assert env_vars == {}


# ---------------------------------------------------------------------------
# get_preferred_branch tests
# ---------------------------------------------------------------------------


def test_get_preferred_branch_returns_configured_branch():
    """get_preferred_branch returns the branch name when configured."""
    config = {
        "repo": {
            "groups": {
                "django": {
                    "repos": ["git@github.com:mongodb-forks/django.git"],
                    "preferred_branch": {"django": "mongodb-6.0.x"},
                },
            },
        }
    }
    assert get_preferred_branch(config, "django", "django") == "mongodb-6.0.x"


def test_get_preferred_branch_returns_none_when_not_configured():
    """get_preferred_branch returns None when no preferred_branch entry exists."""
    config = {
        "repo": {
            "groups": {
                "django": {
                    "repos": ["git@github.com:mongodb-forks/django.git"],
                },
            },
        }
    }
    assert get_preferred_branch(config, "django", "django") is None


def test_get_preferred_branch_returns_none_for_unconfigured_repo():
    """get_preferred_branch returns None when the repo is not in preferred_branch."""
    config = {
        "repo": {
            "groups": {
                "django": {
                    "repos": ["git@github.com:mongodb-forks/django.git"],
                    "preferred_branch": {"django": "mongodb-6.0.x"},
                },
            },
        }
    }
    assert get_preferred_branch(config, "django", "django-mongodb-backend") is None


def test_get_preferred_branch_returns_none_for_unknown_group():
    """get_preferred_branch returns None when the group is not in config."""
    config = {"repo": {"groups": {}}}
    assert get_preferred_branch(config, "nonexistent", "django") is None


# ---------------------------------------------------------------------------
# get_group_priority tests
# ---------------------------------------------------------------------------


def test_get_group_priority():
    """Test get_group_priority returns the priority list."""
    config = {
        "repo": {
            "group_priority": ["pymongo", "django", "langchain"],
            "groups": {},
        }
    }
    assert get_group_priority(config) == ["pymongo", "django", "langchain"]


def test_get_group_priority_not_configured():
    """Test get_group_priority returns empty list when not configured."""
    config = {"repo": {"groups": {}}}
    assert get_group_priority(config) == []


def test_get_group_priority_empty_config():
    """Test get_group_priority with an empty config."""
    assert get_group_priority({}) == []


# ---------------------------------------------------------------------------
# find_repo_by_name with priority tests
# ---------------------------------------------------------------------------


def test_find_repo_by_name_with_priority(tmp_path):
    """Test find_repo_by_name uses priority when multiple repos exist."""
    # Create two groups with the same repo
    pymongo_dir = tmp_path / "pymongo"
    pymongo_dir.mkdir()
    pymongo_repo = pymongo_dir / "mongo-python-driver"
    pymongo_repo.mkdir()
    (pymongo_repo / ".git").mkdir()

    django_dir = tmp_path / "django"
    django_dir.mkdir()
    django_repo = django_dir / "mongo-python-driver"
    django_repo.mkdir()
    (django_repo / ".git").mkdir()

    config = {
        "repo": {
            "group_priority": ["pymongo", "django"],
            "groups": {},
        }
    }

    # Should return pymongo version (higher priority)
    repo = find_repo_by_name("mongo-python-driver", tmp_path, config)
    assert repo is not None
    assert repo["group"] == "pymongo"
    assert repo["path"] == pymongo_repo


def test_find_repo_by_name_with_priority_reverse(tmp_path):
    """Test find_repo_by_name respects priority order."""
    # Create two groups with the same repo
    pymongo_dir = tmp_path / "pymongo"
    pymongo_dir.mkdir()
    pymongo_repo = pymongo_dir / "mongo-python-driver"
    pymongo_repo.mkdir()
    (pymongo_repo / ".git").mkdir()

    django_dir = tmp_path / "django"
    django_dir.mkdir()
    django_repo = django_dir / "mongo-python-driver"
    django_repo.mkdir()
    (django_repo / ".git").mkdir()

    config = {
        "repo": {
            "group_priority": ["django", "pymongo"],  # Django has higher priority
            "groups": {},
        }
    }

    # Should return django version (higher priority)
    repo = find_repo_by_name("mongo-python-driver", tmp_path, config)
    assert repo is not None
    assert repo["group"] == "django"
    assert repo["path"] == django_repo


def test_find_repo_by_name_no_priority_config(tmp_path):
    """Test find_repo_by_name without priority config returns first match."""
    # Create two groups with the same repo
    pymongo_dir = tmp_path / "pymongo"
    pymongo_dir.mkdir()
    pymongo_repo = pymongo_dir / "mongo-python-driver"
    pymongo_repo.mkdir()
    (pymongo_repo / ".git").mkdir()

    django_dir = tmp_path / "django"
    django_dir.mkdir()
    django_repo = django_dir / "mongo-python-driver"
    django_repo.mkdir()
    (django_repo / ".git").mkdir()

    # No config provided
    repo = find_repo_by_name("mongo-python-driver", tmp_path, None)
    assert repo is not None
    # Should return one of them (order not guaranteed without priority)
    assert repo["name"] == "mongo-python-driver"
