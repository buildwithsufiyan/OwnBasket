from django import template
from django.template.loader import select_template

register = template.Library()


@register.simple_tag(takes_context=True)
def render_product_carousel(context, section):
    """Allow an active theme to override the shared carousel component."""
    active_theme = context.get("active_theme")
    folder = (
        active_theme.get("theme_folder")
        if isinstance(active_theme, dict)
        else getattr(active_theme, "theme_folder", "")
    )
    candidates = ["components/product_carousel.html"]
    if folder:
        candidates.insert(0, f"themes/{folder}/components/product_carousel.html")
    template_obj = select_template(candidates)
    context_data = context.flatten()
    context_data["section"] = section
    return template_obj.render(context_data, request=getattr(context, "request", None))
