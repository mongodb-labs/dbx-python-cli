"""
Seed bakerydemo page structure for MongoDB.

Creates the standard bakerydemo index pages (Breads, Blog, Locations, People,
Recipes) as children of the home page and wires them into the homepage's
featured sections.  Safe to re-run — existing pages are left untouched.

Only runs when bakerydemo apps are installed; exits cleanly otherwise.

Usage:
    python manage.py seed
"""

from django.apps import apps
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Seed bakerydemo index pages for a fresh MongoDB install."

    def handle(self, **options):
        if not apps.is_installed("bakerydemo.base"):
            self.stdout.write("bakerydemo is not installed — nothing to do.")
            return

        try:
            import wagtail  # noqa: F401
        except ImportError:
            self.stdout.write("Wagtail is not installed — nothing to do.")
            return

        from bakerydemo.base.models import HomePage
        from bakerydemo.blog.models import BlogIndexPage
        from bakerydemo.breads.models import BreadsIndexPage
        from bakerydemo.locations.models import LocationsIndexPage
        from bakerydemo.people.models import PeopleIndexPage
        from bakerydemo.recipes.models import RecipeIndexPage

        home = HomePage.objects.first()
        if home is None:
            self.stdout.write(
                self.style.ERROR("No HomePage found — run manage.py init first.")
            )
            return

        def get_or_create_child(parent, page_cls, title, slug):
            existing = page_cls.objects.filter(slug=slug).first()
            if existing:
                self.stdout.write(f"  exists: {title}")
                return existing
            page = page_cls(title=title, slug=slug)
            parent.add_child(instance=page)
            self.stdout.write(f"  created: {title}")
            return page

        breads = get_or_create_child(home, BreadsIndexPage, "Breads", "breads")
        blog = get_or_create_child(home, BlogIndexPage, "Blog", "blog")
        get_or_create_child(home, LocationsIndexPage, "Locations", "locations")
        get_or_create_child(home, PeopleIndexPage, "People", "people")
        get_or_create_child(home, RecipeIndexPage, "Recipes", "recipes")

        # Wire up homepage featured sections if they're empty
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

        self.stdout.write(self.style.SUCCESS("Done"))
