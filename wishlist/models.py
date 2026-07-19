from decimal import Decimal
from uuid import uuid4

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from products.models import Product


class WishlistCollection(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='wishlist_collections')
    name = models.CharField(max_length=80)
    share_token = models.UUIDField(default=uuid4, unique=True, editable=False)
    is_public = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('created_at', 'id')
        constraints = (
            models.UniqueConstraint(fields=('user', 'name'), name='unique_wishlist_collection_name'),
        )

    def __str__(self):
        return f'{self.user} - {self.name}'


class WishlistSettings(models.Model):
    max_collections_per_user = models.PositiveSmallIntegerField(default=10)
    max_items_per_collection = models.PositiveSmallIntegerField(default=100)
    allow_public_sharing = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Wishlist settings'
        verbose_name_plural = 'Wishlist settings'

    def clean(self):
        super().clean()
        if not 1 <= self.max_collections_per_user <= 50:
            raise ValidationError({'max_collections_per_user': 'Use a value from 1 to 50.'})
        if not 10 <= self.max_items_per_collection <= 500:
            raise ValidationError({'max_items_per_collection': 'Use a value from 10 to 500.'})
        if WishlistSettings.objects.exclude(pk=self.pk).exists():
            raise ValidationError('Only one wishlist settings record is allowed.')

    @classmethod
    def get_solo(cls):
        return cls.objects.order_by('pk').first() or cls()

class Wishlist(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    collection = models.ForeignKey(
        WishlistCollection, on_delete=models.CASCADE, related_name='items',
    )
    price_at_add = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    saved_for_later = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at', '-id')
        constraints = (
            models.UniqueConstraint(fields=('collection', 'product'), name='unique_product_per_wishlist_collection'),
        )

    def __str__(self):
        return f"{self.user.username} - {self.product.name}"

    def save(self, *args, **kwargs):
        if not self.collection_id and self.user_id:
            self.collection, _ = WishlistCollection.objects.get_or_create(user_id=self.user_id, name='Favorites')
        if self.price_at_add is None and self.product_id:
            product = self.product
            self.price_at_add = product.discount_price if product.has_active_offer() else product.selling_price or product.price
        super().save(*args, **kwargs)

    @property
    def price_changed(self):
        if self.price_at_add is None:
            return False
        current = self.product.discount_price if self.product.has_active_offer() else self.product.selling_price or self.product.price
        return current != self.price_at_add

    @property
    def price_change_amount(self):
        if self.price_at_add is None:
            return Decimal('0.00')
        current = self.product.discount_price if self.product.has_active_offer() else self.product.selling_price or self.product.price
        return current - self.price_at_add
