"""
Wagtail CMS configuration for {{ project_name }}.

To enable Wagtail, uncomment the five lines in {{ project_name }}.py:
  from .wagtail import *
  INSTALLED_APPS += WAGTAIL_INSTALLED_APPS
  MIDDLEWARE += WAGTAIL_MIDDLEWARE
  MIGRATION_MODULES.update(WAGTAIL_MIGRATION_MODULES)
"""

from pathlib import Path as _Path

WAGTAIL_INSTALLED_APPS = [
    "{{ project_name }}.settings.apps.wagtail.CustomWagtailConfig",
    "{{ project_name }}.settings.apps.wagtail.CustomWagtailAdminConfig",
    "{{ project_name }}.settings.apps.wagtail.CustomWagtailDocsConfig",
    "{{ project_name }}.settings.apps.wagtail.CustomWagtailImagesConfig",
    "{{ project_name }}.settings.apps.wagtail.CustomWagtailSearchConfig",
    "{{ project_name }}.settings.apps.wagtail.CustomWagtailSnippetsConfig",
    "{{ project_name }}.settings.apps.wagtail.CustomWagtailFormsConfig",
    "{{ project_name }}.settings.apps.wagtail.CustomWagtailRedirectsConfig",
    "wagtail.embeds",
    "modelcluster",
    "taggit",
]

WAGTAIL_MIDDLEWARE = [
    "wagtail.contrib.redirects.middleware.RedirectMiddleware",
]

WAGTAIL_SITE_NAME = "{{ project_name }}"

WAGTAILADMIN_BASE_URL = "http://localhost:8000"

MEDIA_ROOT = _Path(__file__).resolve().parent.parent.parent / "media"
MEDIA_URL = "/media/"

WAGTAIL_MIGRATION_MODULES = {
    "wagtailcore": "{{ project_name }}.migrations.wagtailcore",
    "wagtailadmin": "{{ project_name }}.migrations.wagtailadmin",
    "wagtaildocs": "{{ project_name }}.migrations.wagtaildocs",
    "wagtailimages": "{{ project_name }}.migrations.wagtailimages",
    "wagtailsearch": "{{ project_name }}.migrations.wagtailsearch",
    "wagtailsnippets": "{{ project_name }}.migrations.wagtailsnippets",
    "wagtailforms": "{{ project_name }}.migrations.wagtailforms",
    "wagtailredirects": "{{ project_name }}.migrations.wagtailredirects",
    "wagtailembeds": "{{ project_name }}.migrations.wagtailembeds",
    "taggit": "{{ project_name }}.migrations.taggit",
}
