from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator, MaxValueValidator, MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone


class MarketplaceSettings(models.Model):
    class Mode(models.TextChoices):
        SINGLE_VENDOR = 'single', 'Single vendor'
        MULTI_VENDOR = 'multi', 'Multi vendor'

    enabled = models.BooleanField(default=True)
    mode = models.CharField(max_length=12, choices=Mode.choices, default=Mode.MULTI_VENDOR)
    seller_registration_enabled = models.BooleanField(default=True)
    global_commission_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('10.00'),
        validators=(MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('100'))),
        help_text='Default structure for future commission evaluation. Checkout behavior is unchanged.',
    )
    low_stock_notification_enabled = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Marketplace settings'
        verbose_name_plural = 'Marketplace settings'

    def clean(self):
        super().clean()
        if MarketplaceSettings.objects.exclude(pk=self.pk).exists():
            raise ValidationError('Only one marketplace settings record is allowed.')
        if self.mode == self.Mode.SINGLE_VENDOR:
            self.seller_registration_enabled = False

    @classmethod
    def get_solo(cls):
        return cls.objects.order_by('pk').first() or cls()

    @property
    def accepts_sellers(self):
        return self.enabled and self.mode == self.Mode.MULTI_VENDOR and self.seller_registration_enabled

    def __str__(self):
        return 'Marketplace settings'


class SellerProfile(models.Model):
    class VerificationStatus(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        PENDING = 'pending', 'Pending review'
        APPROVED = 'approved', 'Approved'
        REJECTED = 'rejected', 'Rejected'
        SUSPENDED = 'suspended', 'Suspended'

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='seller_profile',
    )
    store_name = models.CharField(max_length=160, unique=True)
    slug = models.SlugField(max_length=180, unique=True)
    legal_name = models.CharField(max_length=180)
    contact_person = models.CharField(max_length=160, blank=True)
    business_email = models.EmailField()
    business_phone = models.CharField(max_length=32)
    description = models.TextField(blank=True)
    logo = models.ImageField(upload_to='marketplace/store-logos/', blank=True, null=True)
    banner = models.ImageField(upload_to='marketplace/store-banners/', blank=True, null=True)
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    identity_reference = models.CharField(
        max_length=100, blank=True,
        help_text='Masked or administrative identity reference; do not store raw credentials.',
    )
    tax_identifier = models.CharField(max_length=80, blank=True)
    tax_registration_type = models.CharField(max_length=60, blank=True)
    shipping_policy = models.TextField(blank=True)
    return_policy = models.TextField(blank=True)
    privacy_policy = models.TextField(blank=True)
    verification_status = models.CharField(
        max_length=16,
        choices=VerificationStatus.choices,
        default=VerificationStatus.PENDING,
        db_index=True,
    )
    verification_notes = models.TextField(blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='approved_sellers',
    )
    approved_at = models.DateTimeField(blank=True, null=True)
    commission_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('10.00'),
        validators=(MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('100'))),
    )
    order_notifications = models.BooleanField(default=True)
    inventory_notifications = models.BooleanField(default=True)
    marketing_notifications = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('store_name', 'id')
        permissions = (
            ('review_seller', 'Can review seller applications'),
            ('suspend_seller', 'Can suspend sellers'),
            ('view_seller_metrics', 'Can view seller metrics'),
        )

    def __str__(self):
        return self.store_name

    def get_absolute_url(self):
        return reverse('marketplace:store_detail', args=(self.slug,))

    @property
    def is_approved(self):
        return self.verification_status == self.VerificationStatus.APPROVED

    def approve(self, user):
        self.verification_status = self.VerificationStatus.APPROVED
        self.approved_by = user
        self.approved_at = timezone.now()
        self.verification_notes = ''
        self.save(update_fields=('verification_status', 'approved_by', 'approved_at', 'verification_notes', 'updated_at'))


class SellerDocument(models.Model):
    class DocumentType(models.TextChoices):
        IDENTITY = 'identity', 'Identity document'
        BUSINESS = 'business', 'Business registration'
        TAX = 'tax', 'Tax document'
        BANK = 'bank', 'Bank verification'
        OTHER = 'other', 'Other'

    class ReviewStatus(models.TextChoices):
        PENDING = 'pending', 'Pending'
        VERIFIED = 'verified', 'Verified'
        REJECTED = 'rejected', 'Rejected'

    seller = models.ForeignKey(SellerProfile, on_delete=models.CASCADE, related_name='documents')
    document_type = models.CharField(max_length=20, choices=DocumentType.choices)
    file = models.FileField(
        upload_to='marketplace/seller-documents/',
        validators=(FileExtensionValidator(('pdf', 'jpg', 'jpeg', 'png')),),
    )
    status = models.CharField(max_length=12, choices=ReviewStatus.choices, default=ReviewStatus.PENDING)
    review_notes = models.TextField(blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ('-uploaded_at', '-id')

    def __str__(self):
        return f'{self.seller} - {self.get_document_type_display()}'


class SellerPayoutAccount(models.Model):
    seller = models.OneToOneField(SellerProfile, on_delete=models.CASCADE, related_name='payout_account')
    method = models.CharField(max_length=40, blank=True)
    account_title = models.CharField(max_length=120, blank=True)
    account_reference = models.CharField(
        max_length=80,
        blank=True,
        help_text='Store only a masked account number or provider reference.',
    )
    is_verified = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.seller} payout account'


class SellerPayout(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        APPROVED = 'approved', 'Approved'
        PROCESSING = 'processing', 'Processing'
        PAID = 'paid', 'Paid'
        FAILED = 'failed', 'Failed'

    seller = models.ForeignKey(SellerProfile, on_delete=models.PROTECT, related_name='payouts')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    period_start = models.DateField()
    period_end = models.DateField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING, db_index=True)
    provider_reference = models.CharField(max_length=120, blank=True)
    notes = models.TextField(blank=True)
    requested_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ('-requested_at', '-id')

    def __str__(self):
        return f'{self.seller} - {self.amount} ({self.status})'


class SellerNotification(models.Model):
    class EventType(models.TextChoices):
        SELLER_APPROVED = 'seller_approved', 'Seller approved'
        SELLER_REJECTED = 'seller_rejected', 'Seller rejected'
        NEW_ORDER = 'new_order', 'New order'
        LOW_STOCK = 'low_stock', 'Low stock'
        REVIEW_RECEIVED = 'review_received', 'Review received'
        GENERAL = 'general', 'General'

    class EmailStatus(models.TextChoices):
        NOT_REQUESTED = 'not_requested', 'Not requested'
        QUEUED = 'queued', 'Queued'
        SENT = 'sent', 'Sent'
        FAILED = 'failed', 'Failed'

    seller = models.ForeignKey(SellerProfile, on_delete=models.CASCADE, related_name='notifications')
    event_type = models.CharField(max_length=24, choices=EventType.choices, default=EventType.GENERAL, db_index=True)
    title = models.CharField(max_length=160)
    message = models.TextField()
    link = models.CharField(max_length=255, blank=True)
    email_status = models.CharField(max_length=16, choices=EmailStatus.choices, default=EmailStatus.NOT_REQUESTED)
    is_read = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at', '-id')

    def __str__(self):
        return self.title


class CommissionRule(models.Model):
    """Extensible commission configuration; Phase 18 intentionally does not execute these rules."""

    name = models.CharField(max_length=120)
    seller = models.ForeignKey(
        SellerProfile, on_delete=models.CASCADE, blank=True, null=True, related_name='commission_rules',
    )
    category = models.ForeignKey(
        'products.Category', on_delete=models.CASCADE, blank=True, null=True, related_name='commission_rules',
    )
    rate = models.DecimalField(
        max_digits=5, decimal_places=2,
        validators=(MinValueValidator(Decimal('0')), MaxValueValidator(Decimal('100'))),
    )
    priority = models.PositiveSmallIntegerField(default=100)
    is_active = models.BooleanField(default=True, db_index=True)
    starts_at = models.DateTimeField(blank=True, null=True)
    ends_at = models.DateTimeField(blank=True, null=True)
    conditions = models.JSONField(default=dict, blank=True, help_text='Reserved for future rule conditions.')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('priority', 'id')
        indexes = (models.Index(fields=('is_active', 'priority'), name='commission_active_priority_idx'),)

    def clean(self):
        super().clean()
        if self.starts_at and self.ends_at and self.starts_at >= self.ends_at:
            raise ValidationError({'ends_at': 'End time must be later than start time.'})

    @property
    def scope(self):
        if self.seller_id and self.category_id:
            return 'seller_category'
        if self.seller_id:
            return 'seller'
        if self.category_id:
            return 'category'
        return 'global'

    def __str__(self):
        return f'{self.name} ({self.rate}%)'


class SellerInventory(models.Model):
    seller = models.ForeignKey(SellerProfile, on_delete=models.CASCADE, related_name='inventory_records')
    product = models.OneToOneField('products.Product', on_delete=models.CASCADE, related_name='seller_inventory')
    reserved_stock = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('product__name', 'id')
        permissions = (('adjust_seller_inventory', 'Can adjust seller inventory'),)

    def clean(self):
        super().clean()
        if self.product_id and self.seller_id and self.product.seller_id != self.seller_id:
            raise ValidationError({'product': 'Inventory product must belong to this seller.'})
        if self.product_id and self.reserved_stock > self.product.stock:
            raise ValidationError({'reserved_stock': 'Reserved stock cannot exceed current stock.'})

    @property
    def available_stock(self):
        return max(self.product.stock - self.reserved_stock, 0)

    def __str__(self):
        return f'{self.seller}: {self.product}'


class InventoryHistory(models.Model):
    class Reason(models.TextChoices):
        MANUAL = 'manual', 'Manual adjustment'
        ORDER_RESERVED = 'order_reserved', 'Order reserved'
        ORDER_RELEASED = 'order_released', 'Order released'
        ORDER_FULFILLED = 'order_fulfilled', 'Order fulfilled'
        IMPORT = 'import', 'Import'
        CORRECTION = 'correction', 'Correction'

    inventory = models.ForeignKey(SellerInventory, on_delete=models.CASCADE, related_name='history')
    stock_change = models.IntegerField(default=0)
    reserved_change = models.IntegerField(default=0)
    stock_after = models.PositiveIntegerField()
    reserved_after = models.PositiveIntegerField()
    reason = models.CharField(max_length=24, choices=Reason.choices, default=Reason.MANUAL)
    reference = models.CharField(max_length=120, blank=True)
    note = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at', '-id')
        indexes = (models.Index(fields=('inventory', 'created_at'), name='inventory_history_time_idx'),)

    def __str__(self):
        return f'{self.inventory} at {self.created_at:%Y-%m-%d %H:%M}'


class SellerOrderFulfillment(models.Model):
    class Status(models.TextChoices):
        RECEIVED = 'received', 'Received'
        PACKING = 'packing', 'Packing'
        READY_TO_SHIP = 'ready_to_ship', 'Ready to ship'
        SHIPPED = 'shipped', 'Shipped'
        DELIVERED = 'delivered', 'Delivered'
        CANCELLED = 'cancelled', 'Cancelled'

    seller = models.ForeignKey(SellerProfile, on_delete=models.PROTECT, related_name='fulfillments')
    order = models.ForeignKey('orders.Order', on_delete=models.CASCADE, related_name='seller_fulfillments')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.RECEIVED, db_index=True)
    seller_note = models.TextField(blank=True)
    ready_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-order__created_at', '-id')
        constraints = (
            models.UniqueConstraint(fields=('seller', 'order'), name='unique_seller_order_fulfillment'),
        )
        indexes = (models.Index(fields=('seller', 'status'), name='seller_fulfillment_status_idx'),)

    def clean(self):
        super().clean()
        if self.order_id and self.seller_id and not self.order.items.filter(seller_id=self.seller_id).exists():
            raise ValidationError({'order': 'This order has no items owned by the seller.'})

    def __str__(self):
        return f'Order #{self.order_id} - {self.seller}'


class SellerOrderStatusHistory(models.Model):
    fulfillment = models.ForeignKey(SellerOrderFulfillment, on_delete=models.CASCADE, related_name='history')
    status = models.CharField(max_length=20, choices=SellerOrderFulfillment.Status.choices)
    note = models.CharField(max_length=255, blank=True)
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('created_at', 'id')

    def __str__(self):
        return f'{self.fulfillment}: {self.get_status_display()}'
