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
    "{{ project_name }}.settings.apps.wagtail.CustomWagtailEmbedsConfig",
    "{{ project_name }}.settings.apps.wagtail.CustomWagtailImagesConfig",
    "{{ project_name }}.settings.apps.wagtail.CustomWagtailSearchConfig",
    "{{ project_name }}.settings.apps.wagtail.CustomWagtailSnippetsConfig",
    "{{ project_name }}.settings.apps.wagtail.CustomWagtailFormsConfig",
    "{{ project_name }}.settings.apps.wagtail.CustomWagtailRedirectsConfig",
    "{{ project_name }}.settings.apps.wagtail.CustomWagtailUsersConfig",
    "wagtail.sites",
    "modelcluster",
    "{{ project_name }}.settings.apps.wagtail.CustomTaggitConfig",
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
    "wagtailembeds": "{{ project_name }}.migrations.wagtailembeds",
    "wagtailimages": "{{ project_name }}.migrations.wagtailimages",
    "wagtailredirects": "{{ project_name }}.migrations.wagtailredirects",
    "wagtailsearch": "{{ project_name }}.migrations.wagtailsearch",
    "wagtailsites": "{{ project_name }}.migrations.wagtailsites",
    "wagtailsnippets": "{{ project_name }}.migrations.wagtailsnippets",
    "wagtailforms": "{{ project_name }}.migrations.wagtailforms",
    "wagtailusers": "{{ project_name }}.migrations.wagtailusers",
    "taggit": "{{ project_name }}.migrations.taggit",
}
