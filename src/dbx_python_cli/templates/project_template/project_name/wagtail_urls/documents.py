# Copied from wagtail/documents/urls.py (Wagtail 7.3.1)
# <int: path converters replaced with <object_id: and \d+ regex replaced with
# [0-9a-fA-F]{24} for Django MongoDB Backend compatibility.
# Re-diff against upstream on Wagtail upgrades.
from django.urls import path, re_path

from wagtail.documents.views import serve

urlpatterns = [
    re_path(r"^([0-9a-fA-F]{24})/(.*)$", serve.serve, name="wagtaildocs_serve"),
    path(
        "authenticate_with_password/<object_id:restriction_id>/",
        serve.authenticate_with_password,
        name="wagtaildocs_authenticate_with_password",
    ),
]
