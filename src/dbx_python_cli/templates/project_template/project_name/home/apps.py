from django.apps import AppConfig
from django.conf import settings


class HomeConfig(AppConfig):
    name = "{{ project_name }}.home"
    verbose_name = "Home"

    @property
    def default_auto_field(self):
        return getattr(settings, "DEFAULT_AUTO_FIELD", "django.db.models.BigAutoField")
