from django import template
from django.urls import reverse

from core.admin_visual_editor import get_google_fonts_url
from banners.models import BannerCarousel
from fonts.services import get_active_google_font_families


register = template.Library()


@register.simple_tag
def ownbasket_google_fonts_url():
    banner_font_names = set()
    for slide in BannerCarousel.objects.filter(is_active=True).only(
        'badge_font_family',
        'heading_font_family',
        'description_font_family',
        'button_font_family',
    ):
        for value in (
            slide.badge_font_family,
            slide.heading_font_family,
            slide.description_font_family,
            slide.button_font_family,
        ):
            if value:
                banner_font_names.add(value)

    font_families = get_active_google_font_families(font_names=sorted(banner_font_names))
    if not font_families:
        font_families = ['Inter', 'Plus Jakarta Sans']
    return get_google_fonts_url(font_families)


@register.simple_tag
def ownbasket_managed_fonts_stylesheet_url():
    return reverse('fonts:stylesheet')
