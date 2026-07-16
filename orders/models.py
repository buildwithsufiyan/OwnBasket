from django.contrib.auth.models import User
from django.db import models


class Order(models.Model):
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Processing', 'Processing'),
        ('Shipped', 'Shipped'),
        ('Delivered', 'Delivered'),
    ]

    class PaymentStatus(models.TextChoices):
        PENDING = 'pending', 'Pending'
        PAID = 'paid', 'Paid'
        FAILED = 'failed', 'Failed'
        REFUNDED = 'refunded', 'Refunded'

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    full_name = models.CharField(max_length=200)
    email = models.EmailField()
    address = models.TextField()
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    shipping_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    coupon_code = models.CharField(max_length=50, blank=True, null=True)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    payment_method = models.CharField(max_length=40, blank=True, default='COD')
    payment_status = models.CharField(
        max_length=12, choices=PaymentStatus.choices,
        default=PaymentStatus.PENDING, db_index=True,
    )
    customer_state = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = (
            models.Index(fields=('created_at', 'status'), name='order_created_status_idx'),
            models.Index(fields=('payment_status', 'created_at'), name='order_payment_created_idx'),
        )
        permissions = (
            ('view_financial_reports', 'Can view financial reports'),
            ('export_financial_reports', 'Can export financial reports'),
        )

    def __str__(self):
        return self.full_name


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE)
    seller = models.ForeignKey(
        'marketplace.SellerProfile', on_delete=models.PROTECT, blank=True, null=True,
        related_name='order_items',
    )
    seller_name = models.CharField(max_length=160, blank=True)
    marketplace_commission = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    seller_earning = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    cost_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    size = models.CharField(max_length=50, blank=True, null=True)
    color = models.CharField(max_length=50, blank=True, null=True)
    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    original_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    applied_offer_name = models.CharField(max_length=120, blank=True, null=True)

    def __str__(self):
        return f'{self.product.name} x {self.quantity}'


class PaymentTransaction(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        SUCCESSFUL = 'successful', 'Successful'
        FAILED = 'failed', 'Failed'
        REFUNDED = 'refunded', 'Refunded'

    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name='payments')
    method = models.CharField(max_length=40)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING, db_index=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    provider_reference = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-created_at', '-id')
        indexes = (models.Index(fields=('method', 'status', 'created_at'), name='payment_method_status_idx'),)

    def __str__(self):
        return f'Order #{self.order_id} - {self.method} - {self.status}'


class Refund(models.Model):
    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name='refunds')
    payment = models.ForeignKey(PaymentTransaction, on_delete=models.SET_NULL, blank=True, null=True, related_name='refunds')
    order_item = models.ForeignKey(OrderItem, on_delete=models.SET_NULL, blank=True, null=True, related_name='refunds')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    quantity = models.PositiveIntegerField(default=0)
    reason = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at', '-id')
        indexes = (models.Index(fields=('created_at', 'order'), name='refund_created_order_idx'),)

    def __str__(self):
        return f'Refund #{self.pk} for order #{self.order_id}'
