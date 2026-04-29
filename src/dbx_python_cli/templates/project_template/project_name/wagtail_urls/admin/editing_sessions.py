# Copied from wagtail/admin/urls/editing_sessions.py (Wagtail 7.3.1)
# <int: path converters replaced with <object_id: for Django MongoDB Backend compatibility.
# Re-diff against upstream on Wagtail upgrades.
from django.urls import path

from wagtail.admin.views.editing_sessions import ping, release

app_name = "wagtailadmin_editing_sessions"
urlpatterns = [
    path(
        "ping/<str:app_label>/<str:model_name>/<object_id:object_id>/<object_id:session_id>/",
        ping,
        name="ping",
    ),
    path(
        "release/<object_id:session_id>/",
        release,
        name="release",
    ),
]
