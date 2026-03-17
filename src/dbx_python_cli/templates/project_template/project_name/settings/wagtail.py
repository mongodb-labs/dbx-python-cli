"""
Wagtail CMS configuration for {{ project_name }}.

To enable Wagtail, uncomment the three lines in {{ project_name }}.py:
  from .wagtail import *
  INSTALLED_APPS += WAGTAIL_INSTALLED_APPS
  MIDDLEWARE += WAGTAIL_MIDDLEWARE
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
