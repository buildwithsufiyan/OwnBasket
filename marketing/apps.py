from django.apps import AppConfig


class MarketingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'marketing'
    verbose_name = 'Marketing & Engagement'

    def ready(self):
        from . import signals  # noqa: F401
