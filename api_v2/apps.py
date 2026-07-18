from django.apps import AppConfig


class ApiV2Config(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api_v2'
    verbose_name = 'Mobile API v2'

    def ready(self):
        from . import checks  # noqa: F401
        from django.conf import settings
        from django.utils.module_loading import import_string
        from .push import register_provider
        for provider, import_path in settings.PUSH_PROVIDER_ADAPTERS.items():
            register_provider(provider, import_string(import_path))
