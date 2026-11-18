from debug_toolbar.toolbar import debug_toolbar_urls
from django.contrib import admin
from django.urls import path

from .views import HomeView


urlpatterns = [
    path("admin/", admin.site.urls),
    path("", HomeView.as_view(), name="default_urlconf"),
] + debug_toolbar_urls()
