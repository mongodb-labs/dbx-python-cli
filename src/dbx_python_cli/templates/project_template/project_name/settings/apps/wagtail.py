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

    def ready(self):
        super().ready()
        # Register a telepath adapter so MongoDB ObjectId values are serialized
        # as their hex string when Wagtail's sidebar builds its JS props.
        # Must register with wagtail.admin.telepath.registry (not the global
        # telepath registry) — Wagtail's JSContext uses its own registry instance.
        try:
            from bson import ObjectId
            from telepath import BaseAdapter
            from wagtail.admin.telepath import register as wagtail_register

            class _ObjectIdAdapter(BaseAdapter):
                def build_node(self, obj, context):
                    return context.build_node(str(obj))

            wagtail_register(_ObjectIdAdapter(), ObjectId)
        except ImportError:
            pass

        # Patch DjangoJSONEncoder to serialize MongoDB ObjectId as a hex string.
        # JsonResponse (used by render_modal_workflow and others) uses this encoder.
        try:
            from bson import ObjectId
            from django.core.serializers.json import DjangoJSONEncoder

            def _patched_json_default(self, o, _orig=DjangoJSONEncoder.default):
                if isinstance(o, ObjectId):
                    return str(o)
                return _orig(self, o)

            DjangoJSONEncoder.default = _patched_json_default
            del _patched_json_default
        except ImportError:
            pass

        # Patch ModelViewSet.pk_path_converter so viewsets whose model uses
        # ObjectIdAutoField get "object_id" URL converter instead of "int".
        # ObjectIdAutoField inherits AutoField → IntegerField, so Wagtail's
        # isinstance(pk, IntegerField) check incorrectly picks "int".
        try:
            from django.db import models
            from django_mongodb_backend.fields import ObjectIdAutoField
            from wagtail.admin.viewsets.model import ModelViewSet

            @property
            def _pk_path_converter(self):
                if isinstance(self.model_opts.pk, ObjectIdAutoField):
                    return "object_id"
                if isinstance(self.model_opts.pk, models.UUIDField):
                    return "uuid"
                if isinstance(self.model_opts.pk, models.IntegerField):
                    return "int"
                return "str"

            ModelViewSet.pk_path_converter = _pk_path_converter
            del _pk_path_converter
        except ImportError:
            pass


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
