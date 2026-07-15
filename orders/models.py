from django.db import models
from django.contrib.auth.models import User


class Order(models.Model):

    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Processing', 'Processing'),
        ('Shipped', 'Shipped'),
        ('Delivered', 'Delivered'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)

    full_name = models.CharField(max_length=200)
    email = models.EmailField()
    address = models.TextField()

    subtotal = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
    )

    discount_total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
    )

    shipping_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
    )

    coupon_code = models.CharField(
        max_length=50,
        blank=True,
        null=True,
    )

    total_price = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='Pending'
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.full_name


class OrderItem(models.Model):

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='items'
    )

    product = models.ForeignKey(
        'products.Product',
        on_delete=models.CASCADE
    )

    seller = models.ForeignKey(
        'marketplace.SellerProfile',
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name='order_items',
    )

    seller_name = models.CharField(max_length=160, blank=True)

    marketplace_commission = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
    )

    seller_earning = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
    )

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

    price = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    original_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
    )

    discount_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
    )

    applied_offer_name = models.CharField(
        max_length=120,
        blank=True,
        null=True,
    )

    def __str__(self):
        return f"{self.product.name} x {self.quantity}"
