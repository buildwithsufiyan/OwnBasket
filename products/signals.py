from django.core.cache import cache
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import Brand, Category


@receiver([post_save, post_delete], sender=Category)
def clear_category_navigation_cache(**kwargs):
    cache.delete("navigation:categories:v1")


@receiver([post_save, post_delete], sender=Brand)
def clear_brand_navigation_cache(**kwargs):
    cache.delete("navigation:brands:v1")
