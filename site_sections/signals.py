from django.db.models.signals import m2m_changed, post_delete, post_save
from django.dispatch import receiver

from products.models import Product
from .models import ProductCarouselSection
from .services import invalidate_carousel_catalog


@receiver([post_save, post_delete], sender=Product)
@receiver([post_save, post_delete], sender=ProductCarouselSection)
def invalidate_product_carousels(**kwargs):
    invalidate_carousel_catalog()


@receiver(m2m_changed, sender=ProductCarouselSection.manual_products.through)
def invalidate_manual_product_carousels(**kwargs):
    if kwargs["action"] in {"post_add", "post_remove", "post_clear"}:
        invalidate_carousel_catalog()
