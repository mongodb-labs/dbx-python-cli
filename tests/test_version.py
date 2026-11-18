"""Tests for package version."""

import drivers_python_cli


def test_version_exists():
    """Test that the package has a version attribute."""
    assert hasattr(drivers_python_cli, "__version__")


def test_version_format():
    """Test that the version is in the expected format."""
    assert drivers_python_cli.__version__ == "0.1.0"
