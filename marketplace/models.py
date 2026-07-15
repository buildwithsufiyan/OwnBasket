from decimal import Decimal

from django.conf import settings
from django.core.validators import FileExtensionValidator, MaxValueValidator, MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone


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
    business_email = models.EmailField()
    business_phone = models.CharField(max_length=32)
    description = models.TextField(blank=True)
    logo = models.ImageField(upload_to='marketplace/store-logos/', blank=True, null=True)
    banner = models.ImageField(upload_to='marketplace/store-banners/', blank=True, null=True)
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    tax_identifier = models.CharField(max_length=80, blank=True)
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
    seller = models.ForeignKey(SellerProfile, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=160)
    message = models.TextField()
    link = models.CharField(max_length=255, blank=True)
    is_read = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at', '-id')

    def __str__(self):
        return self.title
