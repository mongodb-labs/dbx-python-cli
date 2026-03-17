"""
Wagtail CMS configuration for {{ project_name }}.

Import this in {{ project_name }}.py to enable Wagtail:
  from .wagtail import *  # noqa
"""

INSTALLED_APPS += [  # noqa: F405, F821
    "{{ project_name }}.apps.CustomWagtailConfig",
    "{{ project_name }}.apps.CustomWagtailAdminConfig",
    "{{ project_name }}.apps.CustomWagtailDocsConfig",
    "{{ project_name }}.apps.CustomWagtailImagesConfig",
    "{{ project_name }}.apps.CustomWagtailSearchConfig",
    "{{ project_name }}.apps.CustomWagtailSnippetsConfig",
    "{{ project_name }}.apps.CustomWagtailFormsConfig",
    "{{ project_name }}.apps.CustomWagtailRedirectsConfig",
    "wagtail.embeds",
    "modelcluster",
    "taggit",
]

MIDDLEWARE += [  # noqa: F405, F821
    "wagtail.contrib.redirects.middleware.RedirectMiddleware",
]

WAGTAIL_SITE_NAME = "{{ project_name }}"

WAGTAILADMIN_BASE_URL = "http://localhost:8000"

MEDIA_ROOT = base_dir / "media"  # noqa: F405, F821
MEDIA_URL = "/media/"
