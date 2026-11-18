"""
MongoDB-specific Django settings.

This file contains all MongoDB-specific configuration.
Import this in {{ project_name }}.py to use MongoDB as your database.
"""

from .base import *  # noqa

import os

# MongoDB-specific default auto field
DEFAULT_AUTO_FIELD = "django_mongodb_backend.fields.ObjectIdAutoField"

# Add MongoDB extensions to installed apps
INSTALLED_APPS += [  # noqa: F405
    "django_mongodb_extensions",  # MQL Panel for Debug Toolbar
]

# MongoDB database configuration
DATABASES = {
    "default": {
        "ENGINE": "django_mongodb_backend",
        "HOST": os.getenv("MONGODB_URI"),  # noqa: F405
        "NAME": "{{ project_name }}",
    },
}

# Add MQL Panel to debug toolbar
DEBUG_TOOLBAR_PANELS.insert(  # noqa: F405
    DEBUG_TOOLBAR_PANELS.index("debug_toolbar.panels.staticfiles.StaticFilesPanel"),  # noqa: F405
    "django_mongodb_extensions.mql_panel.MQLPanel",
)

# Custom migration directories for MongoDB
MIGRATION_MODULES = {
    "admin": "{{ project_name }}.migrations.admin",
    "auth": "{{ project_name }}.migrations.auth",
    "contenttypes": "{{ project_name }}.migrations.contenttypes",
}
