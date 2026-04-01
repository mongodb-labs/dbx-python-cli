"""
Base Django settings for {{ project_name }}.

Database Configuration:
-----------------------
This template supports MongoDB, PostgreSQL, or both simultaneously.
- mongodb.py: MongoDB-specific settings
- postgresql.py: PostgreSQL-specific settings
- multi.py: Both MongoDB and PostgreSQL simultaneously
- {{ project_name }}.py: Project settings (imports from mongodb.py by default)

To switch databases, edit {{ project_name }}.py to import from the desired settings file.
"""

from pathlib import Path


base_dir = Path(__file__).resolve().parent.parent
frontend_dir = Path(__file__).resolve().parent.parent.parent

ALLOWED_HOSTS = []
DEBUG = True
SECRET_KEY = "your-secret-key"

INSTALLED_APPS = [
    "{{ project_name }}.settings.apps.django.CustomAdminConfig",
    "{{ project_name }}.settings.apps.django.CustomAuthConfig",
    "{{ project_name }}.settings.apps.django.CustomContentTypesConfig",
    "debug_toolbar",
    "django.contrib.messages",
    "django.contrib.sessions",
    "django.contrib.staticfiles",
    "webpack_boilerplate",
]

MIDDLEWARE = [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "debug_toolbar.middleware.DebugToolbarMiddleware",
]

ROOT_URLCONF = "{{ project_name }}.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [base_dir / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "django.template.context_processors.request",
            ],
        },
    },
]

WSGI_APPLICATION = "{{ project_name }}.wsgi.application"

# Database configuration is in mongodb.py or postgresql.py
# Import the appropriate settings file in {{ project_name }}.py

STATIC_URL = "static/"

# Debug toolbar
INTERNAL_IPS = [
    "127.0.0.1",
]

DEBUG_TOOLBAR_PANELS = [
    "debug_toolbar.panels.history.HistoryPanel",
    "debug_toolbar.panels.versions.VersionsPanel",
    "debug_toolbar.panels.timer.TimerPanel",
    "debug_toolbar.panels.settings.SettingsPanel",
    "debug_toolbar.panels.headers.HeadersPanel",
    "debug_toolbar.panels.request.RequestPanel",
    # Database-specific panel added in mongodb.py or postgresql.py
    "debug_toolbar.panels.staticfiles.StaticFilesPanel",
    "debug_toolbar.panels.templates.TemplatesPanel",
    "debug_toolbar.panels.alerts.AlertsPanel",
    "debug_toolbar.panels.cache.CachePanel",
    "debug_toolbar.panels.signals.SignalsPanel",
    "debug_toolbar.panels.redirects.RedirectsPanel",
    "debug_toolbar.panels.profiling.ProfilingPanel",
]

# Webpack
STATICFILES_DIRS = [
    frontend_dir / "frontend/build",
]

WEBPACK_LOADER = {
    "MANIFEST_FILE": frontend_dir / "frontend/build/manifest.json",
}

# Custom migration directories
# Overridden in database-specific settings (mongodb.py or postgresql.py)
