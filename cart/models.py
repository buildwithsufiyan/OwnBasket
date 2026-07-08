from django.db import models
from products.models import Product


class Cart(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Cart {self.id}"


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)

    # ✅ Variant fields (user selection)
    size = models.CharField(
        max_length=50,
        blank=True,
        null=True
    )

    color = models.CharField(
        max_length=50,
        blank=True,
        null=True
    )

    quantity = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f"{self.product.name} ({self.size}, {self.color}) x {self.quantity}"