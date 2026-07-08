from django.core.cache import cache

from .models import Theme
from .services import LayoutResolver, ensure_default_theme, get_active_theme


def layout_processor(request):
    """
    Injects a layout resolver into the template context.
    It uses a shared service to get the active theme, avoiding direct
    calls to other context processors.
    """
    # Use the centralized service to get the current theme.
    active_theme = get_active_theme(request)

    # The resolver still needs the default_theme for fallbacks.
    cache_key = "default_theme"
    default_theme = cache.get(cache_key)
    if not default_theme:
        default_theme = ensure_default_theme()
        cache.set(cache_key, default_theme, timeout=None)  # Cache indefinitely

    resolver = LayoutResolver(theme=active_theme, default_theme=default_theme)

    return {"layout_resolver": resolver}


# Alias for backward compatibility. Older settings might still reference theme_context.
theme_context = layout_processor
