Wagtail CMS Support
===================

This document explains the design decisions behind ``dbx project add --wagtail``, which scaffolds a Django project with Wagtail CMS pre-configured for the MongoDB backend.

Overview
--------

Wagtail is a Django-based CMS with its own migration history, admin URL patterns, and serialization assumptions. Several of those assumptions are incompatible with MongoDB out of the box. The template ships with a set of targeted patches and conventions that make Wagtail work with ``django-mongodb-backend`` without forking Wagtail itself.

Migration Modules
------------------

**Decision: configure ``MIGRATION_MODULES`` in settings and generate migrations with ``makemigrations``**

Wagtail ships with its own migration files that include SQL-style assumptions incompatible with MongoDB. The project's ``settings/wagtail.py`` uses ``MIGRATION_MODULES`` to redirect each Wagtail app to an in-project package:

.. code-block:: python

   MIGRATION_MODULES = {
       "wagtailcore": "myproject.migrations.wagtailcore",
       "wagtailadmin": "myproject.migrations.wagtailadmin",
       # ... one entry per Wagtail app
   }

``dbx project run`` automatically runs ``manage.py makemigrations`` before ``migrate`` whenever Wagtail is installed. On first run this populates the empty in-project packages with MongoDB-compatible migration files; on subsequent runs it is a no-op.

Home App
---------

**Decision: ship a ``home`` app with a ``HomePage(Page)`` model**

The template includes a ``home`` app (mirroring what ``wagtail start`` generates) so the site has a concrete starting point for building out page types:

.. code-block:: python

   # home/models.py
   class HomePage(Page):
       body = RichTextField(blank=True)
       content_panels = Page.content_panels + [FieldPanel("body")]

``dbx project run`` creates the Wagtail root page and a ``HomePage`` instance programmatically (not via a data migration), then points the default ``Site`` at that home page. The Wagtail admin is immediately usable on first run.

To add more page types, subclass ``Page`` in a new app or in ``home/models.py`` and run ``manage.py makemigrations``.

Custom App Configurations
--------------------------

**Decision: subclass every Wagtail AppConfig to inject ``default_auto_field``**

Django MongoDB Backend requires models to use ``ObjectIdAutoField`` as their primary key type, while standard Django and PostgreSQL use ``BigAutoField``. Wagtail's own ``AppConfig`` subclasses hard-code no ``default_auto_field``, so they inherit the project-level default.

The template defines thin wrappers in ``settings/apps/wagtail.py``:

.. code-block:: python

   class CustomWagtailConfig(WagtailAppConfig):
       @property
       def default_auto_field(self):
           return getattr(settings, "DEFAULT_AUTO_FIELD", "django.db.models.BigAutoField")

``WAGTAIL_INSTALLED_APPS`` uses these wrappers instead of the originals, so the correct field type is applied for whichever backend is active.

ObjectId Serialization Patches
--------------------------------

**Decision: monkey-patch JSON encoders and Wagtail internals at startup**

Wagtail's admin makes extensive use of JSON serialization — chooser widgets, telepath adapters, API endpoints. None of these are aware of MongoDB's ``ObjectId`` type. Rather than fork Wagtail, ``CustomWagtailAdminConfig.ready()`` applies a series of targeted patches:

1. **Telepath registry** — registers an ``_ObjectIdAdapter`` that serializes ``ObjectId`` as its hex string for Wagtail's sidebar.
2. **DjangoJSONEncoder** — patches ``default()`` so ``JsonResponse`` can serialize ``ObjectId`` values.
3. **Base ``json.JSONEncoder``** — patches the stdlib encoder for direct ``json.dumps()`` calls inside Wagtail widgets.
4. **API v2 filters** — patches ``ChildOfFilter``, ``AncestorOfFilter``, ``DescendantOfFilter``, and ``TranslationOfFilter`` to accept 24-character hex ObjectId strings in addition to integers.
5. **``BaseSerializer`` field mapping** — maps ``ObjectIdAutoField`` to DRF's ``CharField`` so page PKs are serialised as strings in API responses.
6. **``BaseAPIViewSet`` URL patterns** — replaces the ``<int:pk>`` converter with a regex accepting both ObjectId hex strings and plain integers.
7. **``ModelViewSet.pk_path_converter``** — detects ``ObjectIdAutoField`` and returns ``"object_id"`` instead of ``"int"``.

All patches are wrapped in ``try/except ImportError`` so the app config is safe even without Wagtail or Django MongoDB Backend installed.

Custom Admin URL Patterns
--------------------------

**Decision: copy and patch Wagtail's admin URLs into the project**

Wagtail's admin URL conf uses ``<int:parent_page_id>`` path converters throughout, which reject MongoDB ObjectId values. The template ships its own copy of ``wagtail/admin/urls/__init__.py`` at ``project_name/wagtail_urls/admin/__init__.py`` with every ``<int:`` converter replaced by ``<object_id:``.

Sub-module imports (``pages``, ``collections``, ``editing_sessions``, ``workflows``) are loaded dynamically from the project package rather than hard-coded, so the patched copy tracks the Wagtail version installed without requiring a full fork.

A ``viewsets.populate()`` idempotency guard is also included: both the local copy and Wagtail's own URL module call ``register_admin_urls`` hooks, which would double-populate the viewsets list and produce Django W005 warnings without the guard.

**Maintenance note:** this file must be re-diffed against the upstream ``wagtail/admin/urls/__init__.py`` on each Wagtail upgrade.


Flag-Based Enablement
---------------------

**Decision: Wagtail config is commented out by default, activated by ``--wagtail``**

The project template always includes the Wagtail settings file and URL infrastructure, but the settings are commented out in ``<project_name>/settings/<project_name>.py``. Running ``dbx project add --wagtail`` calls ``_enable_wagtail()`` which uncomments the five relevant lines and appends Wagtail URL patterns to ``urls.py``.

This approach means:

- Non-Wagtail projects pay no runtime cost for the Wagtail infrastructure sitting in the template.
- The same project can be inspected or upgraded to Wagtail by editing a few lines, without re-scaffolding.
- ``--qe`` can be stacked with ``--wagtail`` to produce a Wagtail site with Queryable Encryption in a single command.
