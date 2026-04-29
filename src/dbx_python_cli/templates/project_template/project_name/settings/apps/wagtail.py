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

        # Patch Wagtail API v2 page-ID filters to accept 24-char ObjectId hex
        # strings in addition to integers.  All four filters call int(value)
        # and raise BadRequestError on ValueError, rejecting ObjectId strings.
        try:
            from bson import ObjectId
            from wagtail.api.v2 import filters as _api_filters
            from wagtail.api.v2.utils import BadRequestError as _BadReq
            from wagtail.models import Page as _Page

            def _parse_page_id(value):
                try:
                    n = int(value)
                    if n < 0:
                        raise ValueError()
                    return n
                except ValueError:
                    return ObjectId(value)

            def _child_of_filter(self, request, queryset, view):
                if "child_of" not in request.GET:
                    return queryset
                value = request.GET["child_of"]
                if value == "root":
                    parent_page = view.get_root_page()
                else:
                    try:
                        parent_page = view.get_base_queryset().get(
                            id=_parse_page_id(value)
                        )
                    except _Page.DoesNotExist as e:
                        raise _BadReq("parent page doesn't exist") from e
                    except Exception as e:
                        raise _BadReq("child_of must be a positive integer") from e
                queryset = queryset.child_of(parent_page)
                queryset._filtered_by_child_of = parent_page
                return queryset

            def _ancestor_of_filter(self, request, queryset, view):
                if "ancestor_of" not in request.GET:
                    return queryset
                value = request.GET["ancestor_of"]
                try:
                    descendant_page = view.get_base_queryset().get(
                        id=_parse_page_id(value)
                    )
                except _Page.DoesNotExist as e:
                    raise _BadReq("descendant page doesn't exist") from e
                except Exception as e:
                    raise _BadReq("ancestor_of must be a positive integer") from e
                return queryset.ancestor_of(descendant_page)

            def _descendant_of_filter(self, request, queryset, view):
                if "descendant_of" not in request.GET:
                    return queryset
                if hasattr(queryset, "_filtered_by_child_of"):
                    raise _BadReq(
                        "filtering by descendant_of with child_of is not supported"
                    )
                value = request.GET["descendant_of"]
                if value == "root":
                    parent_page = view.get_root_page()
                else:
                    try:
                        parent_page = view.get_base_queryset().get(
                            id=_parse_page_id(value)
                        )
                    except _Page.DoesNotExist as e:
                        raise _BadReq("ancestor page doesn't exist") from e
                    except Exception as e:
                        raise _BadReq("descendant_of must be a positive integer") from e
                return queryset.descendant_of(parent_page)

            def _translation_of_filter(self, request, queryset, view):
                if "translation_of" not in request.GET:
                    return queryset
                value = request.GET["translation_of"]
                if value == "root":
                    page = view.get_root_page()
                else:
                    try:
                        page = view.get_base_queryset().get(id=_parse_page_id(value))
                    except _Page.DoesNotExist as e:
                        raise _BadReq("translation_of page doesn't exist") from e
                    except Exception as e:
                        raise _BadReq(
                            "translation_of must be a positive integer"
                        ) from e
                saved = getattr(queryset, "_filtered_by_child_of", None)
                queryset = queryset.translation_of(page)
                if saved:
                    queryset._filtered_by_child_of = saved
                return queryset

            _api_filters.ChildOfFilter.filter_queryset = _child_of_filter
            _api_filters.AncestorOfFilter.filter_queryset = _ancestor_of_filter
            _api_filters.DescendantOfFilter.filter_queryset = _descendant_of_filter
            _api_filters.TranslationOfFilter.filter_queryset = _translation_of_filter
        except ImportError:
            pass

        # Patch Wagtail API serializer_field_mapping so ObjectIdAutoField PKs
        # are serialized as strings (hex) rather than integers.
        # ObjectIdAutoField inherits AutoField → DRF maps it to IntegerField,
        # which raises TypeError when trying int(ObjectId(...)).
        try:
            from django_mongodb_backend.fields import ObjectIdAutoField
            from rest_framework.fields import CharField
            from wagtail.api.v2.serializers import BaseSerializer

            BaseSerializer.serializer_field_mapping[ObjectIdAutoField] = CharField
        except ImportError:
            pass

        # Patch BaseAPIViewSet.get_urlpatterns to use a regex that accepts
        # both 24-char ObjectId hex strings and plain integers for <pk>, and
        # patch get_object_detail_urlpath to str()-convert pk before reverse()
        # so ObjectId values produce valid URLs.
        try:
            from django.urls import path as _dj_path
            from django.urls import re_path as _dj_re_path
            from django.urls import reverse as _dj_reverse
            from wagtail.api.v2.views import BaseAPIViewSet

            @classmethod
            def _api_get_urlpatterns(cls):
                return [
                    _dj_path("", cls.as_view({"get": "listing_view"}), name="listing"),
                    _dj_re_path(
                        r"^(?P<pk>[0-9a-fA-F]{24}|\d+)/$",
                        cls.as_view({"get": "detail_view"}),
                        name="detail",
                    ),
                    _dj_path("find/", cls.as_view({"get": "find_view"}), name="find"),
                ]

            @classmethod
            def _api_get_object_detail_urlpath(cls, model, pk, namespace=""):
                url_name = (namespace + ":detail") if namespace else "detail"
                return _dj_reverse(url_name, args=(str(pk),))

            BaseAPIViewSet.get_urlpatterns = _api_get_urlpatterns
            BaseAPIViewSet.get_object_detail_urlpath = _api_get_object_detail_urlpath
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
