import secrets
from uuid import uuid4
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Sum
from django.utils import timezone


class NewsletterSubscription(models.Model):
    token_id = models.UUIDField(default=uuid4, unique=True, editable=False)
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending confirmation'
        ACTIVE = 'active', 'Active'
        UNSUBSCRIBED = 'unsubscribed', 'Unsubscribed'

    email = models.EmailField(unique=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True,
        related_name='newsletter_subscriptions',
    )
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING, db_index=True)
    source = models.CharField(max_length=40, default='footer')
    consent_recorded_at = models.DateTimeField(default=timezone.now)
    subscribed_at = models.DateTimeField(blank=True, null=True)
    unsubscribed_at = models.DateTimeField(blank=True, null=True)
    confirmation_sent_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-created_at', '-id')
        indexes = (models.Index(fields=('status', 'created_at'), name='newsletter_status_created_idx'),)
        permissions = (('export_newslettersubscription', 'Can export newsletter subscribers'),)

    def save(self, *args, **kwargs):
        self.email = self.email.strip().lower()
        super().save(*args, **kwargs)

    def activate(self):
        self.status = self.Status.ACTIVE
        self.subscribed_at = timezone.now()
        self.unsubscribed_at = None
        self.save(update_fields=('status', 'subscribed_at', 'unsubscribed_at', 'updated_at'))

    def unsubscribe(self):
        self.status = self.Status.UNSUBSCRIBED
        self.unsubscribed_at = timezone.now()
        self.save(update_fields=('status', 'unsubscribed_at', 'updated_at'))

    def __str__(self):
        return f'Subscription #{self.pk} ({self.status})'


class NotificationPreference(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notification_preferences')
    order_updates = models.BooleanField(default=True)
    delivery_updates = models.BooleanField(default=True)
    promotional_emails = models.BooleanField(default=False)
    newsletter = models.BooleanField(default=False)
    abandoned_cart_reminders = models.BooleanField(default=False)
    wishlist_reminders = models.BooleanField(default=False)
    back_in_stock_alerts = models.BooleanField(default=False)
    marketing_consent = models.BooleanField(default=False, db_index=True)
    consent_recorded_at = models.DateTimeField(blank=True, null=True)
    consent_source = models.CharField(max_length=40, blank=True)
    consent_withdrawn_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    def record_consent(self, granted, source):
        now = timezone.now()
        self.marketing_consent = granted
        self.consent_source = source
        if granted:
            self.consent_recorded_at = now
            self.consent_withdrawn_at = None
        else:
            self.consent_withdrawn_at = now
            self.promotional_emails = False
            self.abandoned_cart_reminders = False
            self.wishlist_reminders = False
        self.save()

    def __str__(self):
        return f'Notification preferences for user #{self.user_id}'


class EngagementDelivery(models.Model):
    class Kind(models.TextChoices):
        ABANDONED_CART = 'abandoned_cart', 'Abandoned cart reminder'
        WISHLIST = 'wishlist', 'Wishlist reminder'
        STOCK = 'stock', 'Back-in-stock alert'
        CAMPAIGN = 'campaign', 'Campaign'
        TRANSACTIONAL = 'transactional', 'Transactional'

    class Status(models.TextChoices):
        SENT = 'sent', 'Sent'
        FAILED = 'failed', 'Failed'
        SKIPPED = 'skipped', 'Skipped'

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True)
    kind = models.CharField(max_length=24, choices=Kind.choices, db_index=True)
    reference = models.CharField(max_length=100, blank=True, db_index=True)
    recipient_hash = models.CharField(max_length=64, db_index=True)
    status = models.CharField(max_length=12, choices=Status.choices, db_index=True)
    error_code = models.CharField(max_length=40, blank=True)
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-sent_at', '-id')
        indexes = (models.Index(fields=('kind', 'reference', 'sent_at'), name='engage_kind_ref_sent_idx'),)


class StockAlert(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='stock_alerts')
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE, related_name='stock_alerts')
    email = models.EmailField()
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    notified_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ('-created_at', '-id')
        constraints = (models.UniqueConstraint(fields=('user', 'product'), name='unique_user_product_stock_alert'),)
        indexes = (models.Index(fields=('is_active', 'created_at'), name='stock_alert_active_created_idx'),)

    def save(self, *args, **kwargs):
        self.email = self.email.strip().lower()
        super().save(*args, **kwargs)


class Campaign(models.Model):
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        SCHEDULED = 'scheduled', 'Scheduled'
        PROCESSING = 'processing', 'Processing'
        SENT = 'sent', 'Sent'
        CANCELLED = 'cancelled', 'Cancelled'
        FAILED = 'failed', 'Failed'

    class Segment(models.TextChoices):
        OPTED_IN = 'opted_in', 'All opted-in customers'
        NEW_CUSTOMERS = 'new_customers', 'New customers (30 days)'
        RETURNING = 'returning', 'Returning customers'
        COMPLETED_ORDERS = 'completed_orders', 'Customers with delivered orders'
        NO_ORDERS = 'no_orders', 'Customers with no orders'
        HIGH_VALUE = 'high_value', 'High-value customers'
        INACTIVE = 'inactive', 'Inactive customers (90 days)'
        NEWSLETTER = 'newsletter', 'Active newsletter subscribers'
        WISHLIST = 'wishlist', 'Customers with wishlist items'

    name = models.CharField(max_length=160)
    subject = models.CharField(max_length=200)
    preview_text = models.CharField(max_length=240, blank=True)
    content = models.TextField(help_text='Plain text content. It is safely escaped in the branded HTML email.')
    target_segment = models.CharField(max_length=24, choices=Segment.choices, default=Segment.OPTED_IN)
    coupon = models.ForeignKey('products.Coupon', on_delete=models.SET_NULL, blank=True, null=True, related_name='marketing_campaigns')
    starts_at = models.DateTimeField(blank=True, null=True)
    scheduled_at = models.DateTimeField(blank=True, null=True, db_index=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT, db_index=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='created_campaigns')
    sent_count = models.PositiveIntegerField(default=0)
    failed_count = models.PositiveIntegerField(default=0)
    unsubscribed_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ('-created_at', '-id')
        indexes = (models.Index(fields=('status', 'scheduled_at'), name='campaign_status_schedule_idx'),)
        permissions = (
            ('send_test_campaign', 'Can send campaign test emails'),
            ('schedule_campaign', 'Can schedule campaigns'),
            ('view_campaign_results', 'Can view campaign results'),
        )

    def clean(self):
        super().clean()
        if self.status == self.Status.SCHEDULED and not self.scheduled_at:
            raise ValidationError({'scheduled_at': 'Scheduled campaigns require a scheduled date.'})

    def __str__(self):
        return self.name


class CampaignDelivery(models.Model):
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name='deliveries')
    recipient_hash = models.CharField(max_length=64)
    status = models.CharField(max_length=12, choices=EngagementDelivery.Status.choices)
    error_code = models.CharField(max_length=40, blank=True)
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = (models.UniqueConstraint(fields=('campaign', 'recipient_hash'), name='unique_campaign_recipient_hash'),)
        indexes = (models.Index(fields=('campaign', 'status'), name='campaign_delivery_status_idx'),)


class ReferralCode(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='referral_code')
    code = models.CharField(max_length=24, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @classmethod
    def create_for_user(cls, user):
        while True:
            code = secrets.token_urlsafe(9).replace('-', '').replace('_', '')[:12].upper()
            if not cls.objects.filter(code=code).exists():
                return cls.objects.create(user=user, code=code)

    def __str__(self):
        return self.code


class Referral(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending qualification'
        QUALIFIED = 'qualified', 'Qualified'
        REJECTED = 'rejected', 'Rejected'

    referral_code = models.ForeignKey(ReferralCode, on_delete=models.PROTECT, related_name='referrals')
    referred_user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='referral_entry')
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    qualified_at = models.DateTimeField(blank=True, null=True)

    def clean(self):
        if self.referral_code_id and self.referred_user_id == self.referral_code.user_id:
            raise ValidationError('Self-referrals are not allowed.')

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class LoyaltyAccount(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='loyalty_account')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def balance(self):
        return self.transactions.aggregate(total=Sum('points'))['total'] or 0

    def __str__(self):
        return f'Loyalty account #{self.pk}'


class LoyaltyTransaction(models.Model):
    class Type(models.TextChoices):
        EARN = 'earn', 'Earn'
        REDEEM = 'redeem', 'Redeem'
        ADJUSTMENT = 'adjustment', 'Adjustment'
        EXPIRED = 'expired', 'Expired'
        REVERSED = 'reversed', 'Reversed'

    account = models.ForeignKey(LoyaltyAccount, on_delete=models.PROTECT, related_name='transactions')
    transaction_type = models.CharField(max_length=16, choices=Type.choices)
    points = models.IntegerField(help_text='Signed ledger entry; debits are negative.')
    reference = models.CharField(max_length=100, blank=True)
    notes = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name='loyalty_adjustments')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at', '-id')
        indexes = (models.Index(fields=('account', 'created_at'), name='loyalty_account_created_idx'),)

    def clean(self):
        if self.points == 0:
            raise ValidationError({'points': 'A loyalty ledger entry cannot be zero.'})
        current = self.account.balance if self.account_id else 0
        if self.pk:
            current -= type(self).objects.get(pk=self.pk).points
        if current + self.points < 0:
            raise ValidationError({'points': 'This transaction would create a negative balance.'})

    def save(self, *args, **kwargs):
        with transaction.atomic():
            if self.account_id:
                LoyaltyAccount.objects.select_for_update().get(pk=self.account_id)
            self.full_clean()
            super().save(*args, **kwargs)
