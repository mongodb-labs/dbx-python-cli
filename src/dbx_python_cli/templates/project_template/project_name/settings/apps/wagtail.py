"""
Wagtail app configurations for {{ project_name }}.

These custom configs set default_auto_field so Wagtail models use the same
field type as the rest of the project (ObjectIdAutoField for MongoDB,
BigAutoField for PostgreSQL).

This module is referenced by settings/wagtail.py via dotted app paths —
it is only loaded when Wagtail is enabled.
"""

from django.conf import settings
from wagtail.admin.apps import WagtailAdminAppConfig
from wagtail.apps import WagtailAppConfig
from wagtail.contrib.forms.apps import WagtailFormsAppConfig
from wagtail.contrib.redirects.apps import WagtailRedirectsAppConfig
from wagtail.documents.apps import WagtailDocsAppConfig
from wagtail.embeds.apps import WagtailEmbedsAppConfig
from wagtail.images.apps import WagtailImagesAppConfig
from wagtail.search.apps import WagtailSearchAppConfig
from wagtail.snippets.apps import WagtailSnippetsAppConfig
from wagtail.users.apps import WagtailUsersAppConfig
from taggit.apps import TaggitAppConfig


def _auto_field():
    return getattr(settings, "DEFAULT_AUTO_FIELD", "django.db.models.BigAutoField")


class CustomWagtailConfig(WagtailAppConfig):
    @property
    def default_auto_field(self):
        return _auto_field()


class CustomWagtailAdminConfig(WagtailAdminAppConfig):
    @property
    def default_auto_field(self):
        return _auto_field()


class CustomWagtailDocsConfig(WagtailDocsAppConfig):
    @property
    def default_auto_field(self):
        return _auto_field()


class CustomWagtailEmbedsConfig(WagtailEmbedsAppConfig):
    @property
    def default_auto_field(self):
        return _auto_field()


class CustomWagtailImagesConfig(WagtailImagesAppConfig):
    @property
    def default_auto_field(self):
        return _auto_field()


class CustomWagtailSearchConfig(WagtailSearchAppConfig):
    @property
    def default_auto_field(self):
        return _auto_field()


class CustomWagtailSnippetsConfig(WagtailSnippetsAppConfig):
    @property
    def default_auto_field(self):
        return _auto_field()


class CustomWagtailFormsConfig(WagtailFormsAppConfig):
    @property
    def default_auto_field(self):
        return _auto_field()


class CustomWagtailRedirectsConfig(WagtailRedirectsAppConfig):
    @property
    def default_auto_field(self):
        return _auto_field()


class CustomWagtailUsersConfig(WagtailUsersAppConfig):
    @property
    def default_auto_field(self):
        return _auto_field()


class CustomTaggitConfig(TaggitAppConfig):
    @property
    def default_auto_field(self):
        return _auto_field()
