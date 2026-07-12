from django.apps import AppConfig


class SiteSectionsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "site_sections"

    def ready(self):
        from . import signals  # noqa: F401
