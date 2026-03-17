"""
Custom app configurations for {{ project_name }}.

These custom configs set the default_auto_field based on which database settings
are imported in {{ project_name }}.py (mongodb.py or postgresql.py).

To switch between MongoDB and PostgreSQL:
1. Edit {{ project_name }}.py
2. Change the import from .mongodb import * to .postgresql import * (or vice versa)
3. Run migrations: dbx project migrate {{ project_name }}

The default_auto_field will automatically use:
- ObjectIdAutoField for MongoDB
- BigAutoField for PostgreSQL
"""

from django.conf import settings
from django.contrib.admin.apps import AdminConfig
from django.contrib.auth.apps import AuthConfig
from django.contrib.contenttypes.apps import ContentTypesConfig
from django.contrib.flatpages.apps import FlatPagesConfig
from django.contrib.redirects.apps import RedirectsConfig
from django.contrib.sites.apps import SitesConfig
from wagtail.admin.apps import WagtailAdminAppConfig
from wagtail.apps import WagtailAppConfig
from wagtail.contrib.forms.apps import WagtailFormsAppConfig
from wagtail.contrib.redirects.apps import WagtailRedirectsAppConfig
from wagtail.documents.apps import WagtailDocsAppConfig
from wagtail.images.apps import WagtailImagesAppConfig
from wagtail.search.apps import WagtailSearchAppConfig
from wagtail.snippets.apps import WagtailSnippetsAppConfig


class CustomAdminConfig(AdminConfig):
    """Custom admin app config that uses the project's DEFAULT_AUTO_FIELD setting."""

    @property
    def default_auto_field(self):
        return getattr(settings, "DEFAULT_AUTO_FIELD", "django.db.models.BigAutoField")


class CustomAuthConfig(AuthConfig):
    """Custom auth app config that uses the project's DEFAULT_AUTO_FIELD setting."""

    @property
    def default_auto_field(self):
        return getattr(settings, "DEFAULT_AUTO_FIELD", "django.db.models.BigAutoField")


class CustomContentTypesConfig(ContentTypesConfig):
    """Custom contenttypes app config that uses the project's DEFAULT_AUTO_FIELD setting."""

    @property
    def default_auto_field(self):
        return getattr(settings, "DEFAULT_AUTO_FIELD", "django.db.models.BigAutoField")


class CustomFlatPagesConfig(FlatPagesConfig):
    """Custom flatpages app config that uses the project's DEFAULT_AUTO_FIELD setting."""

    @property
    def default_auto_field(self):
        return getattr(settings, "DEFAULT_AUTO_FIELD", "django.db.models.BigAutoField")


class CustomRedirectsConfig(RedirectsConfig):
    """Custom redirects app config that uses the project's DEFAULT_AUTO_FIELD setting."""

    @property
    def default_auto_field(self):
        return getattr(settings, "DEFAULT_AUTO_FIELD", "django.db.models.BigAutoField")


class CustomSitesConfig(SitesConfig):
    """Custom sites app config that uses the project's DEFAULT_AUTO_FIELD setting."""

    @property
    def default_auto_field(self):
        return getattr(settings, "DEFAULT_AUTO_FIELD", "django.db.models.BigAutoField")


# Wagtail app configs


class CustomWagtailConfig(WagtailAppConfig):
    """Custom wagtail app config that uses the project's DEFAULT_AUTO_FIELD setting."""

    @property
    def default_auto_field(self):
        return getattr(settings, "DEFAULT_AUTO_FIELD", "django.db.models.BigAutoField")


class CustomWagtailAdminConfig(WagtailAdminAppConfig):
    """Custom wagtail.admin app config that uses the project's DEFAULT_AUTO_FIELD setting."""

    @property
    def default_auto_field(self):
        return getattr(settings, "DEFAULT_AUTO_FIELD", "django.db.models.BigAutoField")


class CustomWagtailDocsConfig(WagtailDocsAppConfig):
    """Custom wagtail.documents app config that uses the project's DEFAULT_AUTO_FIELD setting."""

    @property
    def default_auto_field(self):
        return getattr(settings, "DEFAULT_AUTO_FIELD", "django.db.models.BigAutoField")


class CustomWagtailImagesConfig(WagtailImagesAppConfig):
    """Custom wagtail.images app config that uses the project's DEFAULT_AUTO_FIELD setting."""

    @property
    def default_auto_field(self):
        return getattr(settings, "DEFAULT_AUTO_FIELD", "django.db.models.BigAutoField")


class CustomWagtailSearchConfig(WagtailSearchAppConfig):
    """Custom wagtail.search app config that uses the project's DEFAULT_AUTO_FIELD setting."""

    @property
    def default_auto_field(self):
        return getattr(settings, "DEFAULT_AUTO_FIELD", "django.db.models.BigAutoField")


class CustomWagtailSnippetsConfig(WagtailSnippetsAppConfig):
    """Custom wagtail.snippets app config that uses the project's DEFAULT_AUTO_FIELD setting."""

    @property
    def default_auto_field(self):
        return getattr(settings, "DEFAULT_AUTO_FIELD", "django.db.models.BigAutoField")


class CustomWagtailFormsConfig(WagtailFormsAppConfig):
    """Custom wagtail.contrib.forms app config that uses the project's DEFAULT_AUTO_FIELD setting."""

    @property
    def default_auto_field(self):
        return getattr(settings, "DEFAULT_AUTO_FIELD", "django.db.models.BigAutoField")


class CustomWagtailRedirectsConfig(WagtailRedirectsAppConfig):
    """Custom wagtail.contrib.redirects app config that uses the project's DEFAULT_AUTO_FIELD setting."""

    @property
    def default_auto_field(self):
        return getattr(settings, "DEFAULT_AUTO_FIELD", "django.db.models.BigAutoField")
