# Copied from wagtail/admin/urls/__init__.py (Wagtail 7.3.1)
# <int: path converters replaced with <object_id: for Django MongoDB Backend compatibility.
# Sub-module imports use dynamic importlib calls to avoid hard-coding the project name.
# Re-diff against upstream on Wagtail upgrades.
import functools
import importlib as _importlib

from django.conf import settings
from django.http import Http404
from django.urls import include, path, re_path
from django.views.decorators.cache import never_cache
from django.views.defaults import page_not_found
from django.views.generic import TemplateView

from wagtail import hooks
from wagtail.admin.api import urls as api_urls
from wagtail.admin.auth import require_admin_access
from wagtail.admin.urls import password_reset as wagtailadmin_password_reset_urls
from wagtail.admin.urls import reports as wagtailadmin_reports_urls
from wagtail.admin.views import account, chooser, dismissibles, home, tags
from wagtail.admin.views.bulk_action import index as bulk_actions
from wagtail.admin.views.generic.preview import StreamFieldBlockPreview
from wagtail.admin.views.i18n import localized_js_catalog
from wagtail.admin.views.pages import listing
from wagtail.admin.viewsets import viewsets as _viewsets
from wagtail.utils.urlpatterns import decorate_urlpatterns

# Use our local patched sub-modules instead of the originals.
# Dynamic import derives the project name from __name__ at runtime.
_pkg = __name__.rsplit(".", 2)[0]  # "proj.wagtail_urls.admin" -> "proj"
wagtailadmin_collections_urls = _importlib.import_module(
    f"{_pkg}.wagtail_urls.admin.collections"
)
wagtailadmin_editing_sessions_urls = _importlib.import_module(
    f"{_pkg}.wagtail_urls.admin.editing_sessions"
)
wagtailadmin_pages_urls = _importlib.import_module(f"{_pkg}.wagtail_urls.admin.pages")
wagtailadmin_workflows_urls = _importlib.import_module(
    f"{_pkg}.wagtail_urls.admin.workflows"
)
del _importlib, _pkg

# Patch viewsets.populate() to be idempotent. Both this module and
# wagtail/admin/urls/__init__.py call register_admin_urls hooks, which invoke
# viewsets.populate(). Without this guard the viewsets list doubles, causing
# Django W005 "URL namespace not unique" warnings.
_orig_populate = _viewsets.populate


def _populate_once():
    if not _viewsets.viewsets:
        _orig_populate()


_viewsets.populate = _populate_once
del _populate_once

urlpatterns = [
    path("", home.HomeView.as_view(), name="wagtailadmin_home"),
    path("test404/", TemplateView.as_view(template_name="wagtailadmin/404.html")),
    path("api/", include(api_urls)),
    path("failwhale/", home.error_test, name="wagtailadmin_error_test"),
    # TODO: Move into wagtailadmin_pages namespace
    path(
        "pages/",
        listing.ExplorableIndexView.as_view(),
        name="wagtailadmin_explore_root",
    ),
    path(
        "pages/<object_id:parent_page_id>/",
        listing.ExplorableIndexView.as_view(),
        name="wagtailadmin_explore",
    ),
    path(
        "pages/<object_id:parent_page_id>/results/",
        listing.ExplorableIndexView.as_view(results_only=True),
        name="wagtailadmin_explore_results",
    ),
    # bulk actions
    path(
        "bulk/<slug:app_label>/<slug:model_name>/<slug:action>/",
        bulk_actions,
        name="wagtail_bulk_action",
    ),
    path("pages/", include(wagtailadmin_pages_urls, namespace="wagtailadmin_pages")),
    # TODO: Move into wagtailadmin_pages namespace
    path("choose-page/", chooser.BrowseView.as_view(), name="wagtailadmin_choose_page"),
    path(
        "choose-page/<object_id:parent_page_id>/",
        chooser.BrowseView.as_view(),
        name="wagtailadmin_choose_page_child",
    ),
    path(
        "choose-page/search/",
        chooser.SearchView.as_view(),
        name="wagtailadmin_choose_page_search",
    ),
    path(
        "choose-page/chosen-multiple/",
        chooser.ChosenMultipleView.as_view(),
        name="wagtailadmin_choose_page_chosen_multiple",
    ),
    path(
        "choose-external-link/",
        chooser.ExternalLinkView.as_view(),
        name="wagtailadmin_choose_page_external_link",
    ),
    path(
        "choose-email-link/",
        chooser.EmailLinkView.as_view(),
        name="wagtailadmin_choose_page_email_link",
    ),
    path(
        "choose-phone-link/",
        chooser.PhoneLinkView.as_view(),
        name="wagtailadmin_choose_page_phone_link",
    ),
    path(
        "choose-anchor-link/",
        chooser.AnchorLinkView.as_view(),
        name="wagtailadmin_choose_page_anchor_link",
    ),
    path("tag-autocomplete/", tags.autocomplete, name="wagtailadmin_tag_autocomplete"),
    path(
        "tag-autocomplete/<slug:app_name>/<slug:model_name>/",
        tags.autocomplete,
        name="wagtailadmin_tag_model_autocomplete",
    ),
    path(
        "collections/",
        include(wagtailadmin_collections_urls, namespace="wagtailadmin_collections"),
    ),
    path(
        "workflows/",
        include(wagtailadmin_workflows_urls, namespace="wagtailadmin_workflows"),
    ),
    path(
        "reports/", include(wagtailadmin_reports_urls, namespace="wagtailadmin_reports")
    ),
    path("account/", account.AccountView.as_view(), name="wagtailadmin_account"),
    path("logout/", account.LogoutView.as_view(), name="wagtailadmin_logout"),
    path(
        "dismissibles/",
        dismissibles.DismissiblesView.as_view(),
        name="wagtailadmin_dismissibles",
    ),
    path(
        "editing-sessions/",
        include(
            wagtailadmin_editing_sessions_urls,
            namespace="wagtailadmin_editing_sessions",
        ),
    ),
    path(
        "block-preview/",
        StreamFieldBlockPreview.as_view(),
        name="wagtailadmin_block_preview",
    ),
]


# Import additional urlpatterns from any apps that define a register_admin_urls hook
for fn in hooks.get_hooks("register_admin_urls"):
    urls = fn()
    if urls:
        urlpatterns += urls


# Add "wagtailadmin.access_admin" permission check
urlpatterns = decorate_urlpatterns(urlpatterns, require_admin_access)


# These url patterns do not require an authenticated admin user
urlpatterns += [
    path("sprite/", home.sprite, name="wagtailadmin_sprite"),
    path("login/", account.LoginView.as_view(), name="wagtailadmin_login"),
    # Password reset
    path("password_reset/", include(wagtailadmin_password_reset_urls)),
    # JS translation catalog
    path(
        "jsi18n/",
        localized_js_catalog,
        name="wagtailadmin_javascript_catalog",
    ),
]


# Default view (will show 404 page)
# This must be the last URL in this file!

if settings.APPEND_SLASH:
    # Only catch unrecognised patterns with a trailing slash
    # and let CommonMiddleware handle adding a slash to every other pattern
    urlpatterns += [
        re_path(r"^.*/$", home.default),
    ]

else:
    # Catch all unrecognised patterns
    urlpatterns += [
        re_path(r"^", home.default),
    ]


# Hook in our own 404 handler
def display_custom_404(view_func):
    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        try:
            return view_func(request, *args, **kwargs)
        except Http404:
            return page_not_found(request, "", template_name="wagtailadmin/404.html")

    return wrapper


urlpatterns = decorate_urlpatterns(urlpatterns, display_custom_404)


# Decorate all views with cache settings to prevent caching
urlpatterns = decorate_urlpatterns(urlpatterns, never_cache)
