"""
Bootstrap the Wagtail page tree and default site for a fresh MongoDB install.

Wagtail's data migrations (root page, default site) live in wagtail's own
migration package and are not replicated when MIGRATION_MODULES redirects to
empty stub packages, so this command creates them programmatically.

Usage:
    python manage.py bootstrap
"""

import importlib

from django.apps import apps
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand
from wagtail.models import Locale, Page, Site


def _get_home_page_class():
    """Return (HomePage class, kwargs) for the appropriate home page model."""
    if apps.is_installed("bakerydemo.base"):
        module = importlib.import_module("bakerydemo.base.models")
        return module.HomePage, {
            "title": "Bakery Demo",
            "slug": "home",
            "hero_text": "Welcome to the Bakery Demo",
            "hero_cta": "Our Breads",
        }
    module = importlib.import_module("{{ project_name }}.home.models")
    return module.HomePage, {"title": "Home", "slug": "home"}


class Command(BaseCommand):
    help = "Bootstrap Wagtail root page, home page, and default site."

    def handle(self, **options):
        from django.conf import settings

        lang = (getattr(settings, "LANGUAGE_CODE", "en") or "en").split("-")[0][:2]
        locale, _ = Locale.objects.get_or_create(language_code=lang)

        root_page = Page.objects.filter(depth=1).first()
        if root_page is None:
            page_ct, _ = ContentType.objects.get_or_create(
                app_label="wagtailcore", model="page"
            )
            root_page = Page.add_root(
                title="Root",
                slug="root",
                content_type=page_ct,
                locale=locale,
                url_path="/",
                live=True,
            )
            self.stdout.write("Created Wagtail root page")

        home_cls, home_kwargs = _get_home_page_class()
        if home_cls.objects.exists():
            home = home_cls.objects.first()
            self.stdout.write(f"Using existing home page: '{home.title}'")
        else:
            home = home_cls(locale=locale, **home_kwargs)
            root_page.add_child(instance=home)
            self.stdout.write(f"Created home page '{home.title}'")

        site = Site.objects.filter(is_default_site=True).first()
        if site:
            site.root_page = home
            site.site_name = home.title
            site.save()
            self.stdout.write(f"Updated default site ({site.hostname}:{site.port})")
        else:
            Site.objects.create(
                hostname="localhost",
                port=8000,
                root_page=home,
                site_name=home.title,
                is_default_site=True,
            )
            self.stdout.write("Created default site at localhost:8000")

        self.stdout.write(self.style.SUCCESS("Bootstrap complete"))
