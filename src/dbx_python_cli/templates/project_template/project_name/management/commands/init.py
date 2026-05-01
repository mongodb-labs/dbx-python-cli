"""
Bootstrap the Wagtail page tree and default site for a fresh MongoDB install.

Wagtail's data migrations (root page, default site) live in wagtail's own
migration package and are not replicated when MIGRATION_MODULES redirects to
empty stub packages, so this command creates them programmatically.

Only relevant for Wagtail projects — exits cleanly on non-Wagtail installs.

Usage:
    python manage.py init
"""

import importlib

from django.apps import apps
from django.core.management.base import BaseCommand


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
    help = "Create the Wagtail root page, home page, and default site."

    def handle(self, **options):
        try:
            from django.contrib.contenttypes.models import ContentType
            from wagtail.models import Locale, Page, Site
        except ImportError:
            self.stdout.write("Wagtail is not installed — nothing to do.")
            return

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

        if apps.is_installed("bakerydemo.base"):
            engine = settings.DATABASES.get("default", {}).get("ENGINE", "")
            if "mongodb" in engine:
                self._seed_bakerydemo(home)
            else:
                from django.core.management import call_command

                self.stdout.write("Loading bakerydemo fixture data...")
                call_command("load_initial_data")

        self.stdout.write(self.style.SUCCESS("Done"))

    def _seed_bakerydemo(self, home):
        from bakerydemo.blog.models import BlogIndexPage, BlogPage
        from bakerydemo.breads.models import BreadPage, BreadsIndexPage
        from bakerydemo.locations.models import LocationsIndexPage
        from bakerydemo.people.models import PeopleIndexPage
        from bakerydemo.recipes.models import RecipeIndexPage

        def get_or_create_child(page_cls, title, slug):
            existing = page_cls.objects.filter(slug=slug).first()
            if existing:
                self.stdout.write(f"  exists: {title}")
                return existing
            page = page_cls(title=title, slug=slug)
            home.add_child(instance=page)
            self.stdout.write(f"  created: {title}")
            return page

        def get_or_create_grandchild(parent, page_cls, title, slug, **kwargs):
            existing = page_cls.objects.filter(slug=slug).first()
            if existing:
                self.stdout.write(f"    exists: {title}")
                return existing
            page = page_cls(title=title, slug=slug, **kwargs)
            parent.add_child(instance=page)
            self.stdout.write(f"    created: {title}")
            return page

        breads = get_or_create_child(BreadsIndexPage, "Breads", "breads")
        blog = get_or_create_child(BlogIndexPage, "Blog", "blog")
        get_or_create_child(LocationsIndexPage, "Locations", "locations")
        get_or_create_child(PeopleIndexPage, "People", "people")
        get_or_create_child(RecipeIndexPage, "Recipes", "recipes")

        get_or_create_grandchild(
            breads,
            BreadPage,
            "Sourdough",
            "sourdough",
            introduction="A tangy, chewy loaf with a crisp crust.",
        )
        get_or_create_grandchild(
            breads,
            BreadPage,
            "Baguette",
            "baguette",
            introduction="The classic French stick — light, airy, and golden.",
        )
        get_or_create_grandchild(
            breads,
            BreadPage,
            "Rye Bread",
            "rye-bread",
            introduction="Dense and earthy, made with whole rye flour.",
        )
        get_or_create_grandchild(
            blog,
            BlogPage,
            "Welcome to the Bakery",
            "welcome-to-the-bakery",
            introduction="Our story, our passion, and our bread.",
        )

        home.refresh_from_db()
        changed = False
        if home.featured_section_1 is None:
            home.featured_section_1 = breads
            home.featured_section_1_title = "Breads"
            changed = True
        if home.featured_section_2 is None:
            home.featured_section_2 = blog
            home.featured_section_2_title = "Blog"
            changed = True
        if changed:
            home.save()
            self.stdout.write("Updated homepage featured sections")
