from django.conf import settings
from django.db import models


class BehaviorEvent(models.Model):
    class EventType(models.TextChoices):
        PRODUCT_VIEW = 'product_view', 'Product view'
        CATEGORY_VIEW = 'category_view', 'Category view'
        BRAND_VIEW = 'brand_view', 'Brand view'
        SEARCH = 'search', 'Search'
        WISHLIST_ADD = 'wishlist_add', 'Wishlist add'
        WISHLIST_REMOVE = 'wishlist_remove', 'Wishlist remove'
        CART_ADD = 'cart_add', 'Cart add/update'
        CART_REMOVE = 'cart_remove', 'Cart remove'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, blank=True, null=True,
        related_name='behavior_events',
    )
    session_hash = models.CharField(max_length=64, blank=True, db_index=True)
    event_type = models.CharField(max_length=24, choices=EventType.choices, db_index=True)
    product = models.ForeignKey(
        'products.Product', on_delete=models.CASCADE, blank=True, null=True,
        related_name='behavior_events',
    )
    category = models.ForeignKey(
        'products.Category', on_delete=models.CASCADE, blank=True, null=True,
        related_name='behavior_events',
    )
    brand = models.ForeignKey(
        'products.Brand', on_delete=models.CASCADE, blank=True, null=True,
        related_name='behavior_events',
    )
    search_term = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ('-created_at', '-id')
        indexes = (
            models.Index(fields=('event_type', 'created_at'), name='behavior_type_created_idx'),
            models.Index(fields=('user', 'event_type', 'created_at'), name='behavior_user_type_idx'),
            models.Index(fields=('product', 'event_type', 'created_at'), name='behavior_product_type_idx'),
        )

    def __str__(self):
        return f'{self.event_type} at {self.created_at:%Y-%m-%d %H:%M}'


class SearchSynonym(models.Model):
    canonical_term = models.CharField(max_length=80, unique=True)
    alternatives = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('canonical_term', 'id')

    def __str__(self):
        return self.canonical_term
