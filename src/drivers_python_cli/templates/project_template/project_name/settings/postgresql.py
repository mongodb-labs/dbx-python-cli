"""
PostgreSQL-specific Django settings.

This file contains all PostgreSQL-specific configuration.
Import this in {{ project_name }}.py to use PostgreSQL as your database.

Requirements:
- pip install -e ".[postgres]"
"""

from .base import *  # noqa

import dj_database_url

# PostgreSQL-specific default auto field
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# PostgreSQL database configuration
DATABASES = {
    "default": dj_database_url.config(
        default="postgres://postgres:postgres@localhost:5432/{{ project_name }}",
        conn_max_age=600,
        conn_health_checks=True,
    )
}

# Add SQL Panel to debug toolbar
DEBUG_TOOLBAR_PANELS.insert(  # noqa: F405
    DEBUG_TOOLBAR_PANELS.index("debug_toolbar.panels.staticfiles.StaticFilesPanel"),  # noqa: F405
    "debug_toolbar.panels.sql.SQLPanel",
)

# Use default Django migrations for PostgreSQL (not custom directories)
# This allows switching between databases without migration conflicts
MIGRATION_MODULES = {}
