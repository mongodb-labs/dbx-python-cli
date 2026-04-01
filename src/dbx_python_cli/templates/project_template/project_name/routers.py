"""
Database routers for {{ project_name }}.

This module contains database routers that control database operations.
"""

from django_mongodb_backend.utils import model_has_encrypted_fields


class PostgreSQLRouter:
    """
    Routes Django built-in apps to the PostgreSQL database.

    When running MongoDB and PostgreSQL simultaneously (see settings/multi.py),
    this router directs auth, admin, contenttypes, and sessions to PostgreSQL
    while application models use MongoDB via MongoRouter.

    Configure DATABASE_ROUTERS in settings/multi.py as:
        DATABASE_ROUTERS = [
            "{{ project_name }}.routers.PostgreSQLRouter",
            "django_mongodb_backend.routers.MongoRouter",
        ]
    """

    POSTGRESQL_APPS: set = set()  # Add app labels here to route them to PostgreSQL

    def db_for_read(self, model, **hints):
        if model._meta.app_label in self.POSTGRESQL_APPS:
            return "postgresql"
        return None

    def db_for_write(self, model, **hints):
        if model._meta.app_label in self.POSTGRESQL_APPS:
            return "postgresql"
        return None

    def allow_relation(self, obj1, obj2, **hints):
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if app_label in self.POSTGRESQL_APPS:
            return db == "postgresql"
        return None


class EncryptedRouter:
    """
    Router for Queryable Encryption (QE) support.

    This router automatically routes models with encrypted fields to the "encrypted"
    database and all other models to the "default" database.

    To enable this router, uncomment the DATABASE_ROUTERS setting in your settings
    file and ensure you have configured the "encrypted" database with AutoEncryptionOpts.

    See: https://django-mongodb-backend.readthedocs.io/en/latest/howto/queryable-encryption/
    """

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if hints.get("model"):
            if model_has_encrypted_fields(hints["model"]):
                return db == "encrypted"
            else:
                return db == "default"
        return None

    def db_for_read(self, model, **hints):
        if model_has_encrypted_fields(model):
            return "encrypted"
        return "default"

    def kms_provider(self, model):
        if model_has_encrypted_fields(model):
            return "local"
        return None

    db_for_write = db_for_read
