# Copied from wagtail/admin/urls/collections.py (Wagtail 7.3.1)
# <int: path converters replaced with <object_id: for Django MongoDB Backend compatibility.
# Re-diff against upstream on Wagtail upgrades.
from django.urls import path

from wagtail.admin.views import collection_privacy, collections

app_name = "wagtailadmin_collections"
urlpatterns = [
    path("", collections.Index.as_view(), name="index"),
    path("add/", collections.Create.as_view(), name="add"),
    path("<object_id:pk>/", collections.Edit.as_view(), name="edit"),
    path("<object_id:pk>/delete/", collections.Delete.as_view(), name="delete"),
    path(
        "<object_id:collection_id>/privacy/",
        collection_privacy.set_privacy,
        name="set_privacy",
    ),
]
