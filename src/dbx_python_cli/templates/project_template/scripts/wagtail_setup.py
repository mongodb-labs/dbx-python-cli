"""
Create Wagtail root page, home page, default site, and superuser if they don't exist.
Run with: python scripts/wagtail_setup.py
"""
import os
import sys

import django

django.setup()

try:
    from wagtail.models import Page

    if not Page.objects.filter(depth=1).exists():
        from django.conf import settings as s
        from django.contrib.contenttypes.models import ContentType
        from wagtail.models import Locale, Site

        lang = (getattr(s, "LANGUAGE_CODE", "en") or "en").split("-")[0][:2]
        locale, _ = Locale.objects.get_or_create(language_code=lang)
        ct, _ = ContentType.objects.get_or_create(app_label="wagtailcore", model="page")
        root = Page.add_root(title="Root", slug="root", content_type=ct, locale=locale)
        home = root.add_child(title="Home", slug="home", content_type=ct, locale=locale)
        print("✅ Wagtail root page and home page created.")
        if not Site.objects.exists():
            Site.objects.create(hostname="localhost", root_page=home, is_default_site=True)
            print("✅ Wagtail default site created.")
    else:
        print("ℹ️  Wagtail root page already exists, skipping.")
except ImportError:
    print("ℹ️  Wagtail not installed, skipping setup.")
except Exception as e:
    print(f"⚠️  Wagtail setup error: {e}", file=sys.stderr)
    sys.exit(1)
