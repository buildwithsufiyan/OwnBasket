from django.conf import settings
from django.db import models
from django.utils import timezone
import uuid


class MobileSession(models.Model):
    """Revocable, per-device opaque credentials for native/mobile clients."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='mobile_sessions')
    device_id_hash = models.CharField(max_length=64)
    device_name = models.CharField(max_length=120, blank=True)
    platform = models.CharField(max_length=12, default='unknown')
    access_token_hash = models.CharField(max_length=64, unique=True)
    refresh_token_hash = models.CharField(max_length=64, unique=True)
    access_expires_at = models.DateTimeField(db_index=True)
    refresh_expires_at = models.DateTimeField(db_index=True)
    absolute_expires_at = models.DateTimeField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(default=timezone.now)
    revoked_at = models.DateTimeField(blank=True, null=True, db_index=True)
    revoke_reason = models.CharField(max_length=40, blank=True)

    class Meta:
        ordering = ('-last_used_at', '-id')
        indexes = (
            models.Index(fields=('user', 'device_id_hash', 'revoked_at'), name='mobile_session_device_idx'),
        )

    @property
    def is_active(self):
        now = timezone.now()
        return self.revoked_at is None and self.refresh_expires_at > now and self.absolute_expires_at > now and self.user.is_active

    def revoke(self, reason='logout'):
        if self.revoked_at is None:
            self.revoked_at = timezone.now()
            self.revoke_reason = reason[:40]
            self.save(update_fields=('revoked_at', 'revoke_reason'))


class UsedRefreshToken(models.Model):
    """Refresh-token tombstones detect replay after rotation."""

    session = models.ForeignKey(MobileSession, on_delete=models.CASCADE, related_name='used_refresh_tokens')
    token_hash = models.CharField(max_length=64, unique=True)
    rotated_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(db_index=True)

    class Meta:
        ordering = ('-rotated_at',)


class IdempotencyRecord(models.Model):
    class Status(models.TextChoices):
        PROCESSING = 'processing', 'Processing'
        COMPLETED = 'completed', 'Completed'

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='api_idempotency_records')
    key_hash = models.CharField(max_length=64)
    method = models.CharField(max_length=8)
    path = models.CharField(max_length=255)
    request_hash = models.CharField(max_length=64)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PROCESSING)
    response_status = models.PositiveSmallIntegerField(blank=True, null=True)
    response_body = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    expires_at = models.DateTimeField(db_index=True)

    class Meta:
        constraints = (
            models.UniqueConstraint(fields=('user', 'key_hash'), name='unique_user_idempotency_key'),
        )
        indexes = (models.Index(fields=('expires_at', 'status'), name='idempotency_expiry_idx'),)


class PushDevice(models.Model):
    class Platform(models.TextChoices):
        WEB = 'web', 'Web/PWA'
        ANDROID = 'android', 'Android (future)'
        IOS = 'ios', 'iOS (future)'

    class Provider(models.TextChoices):
        NONE = 'none', 'Not connected'
        WEB_PUSH = 'web_push', 'Web Push'
        FCM = 'fcm', 'Firebase Cloud Messaging'
        APNS = 'apns', 'Apple Push Notification service'

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='push_devices')
    device_id_hash = models.CharField(max_length=64)
    platform = models.CharField(max_length=12, choices=Platform.choices, default=Platform.WEB)
    provider = models.CharField(max_length=12, choices=Provider.choices, default=Provider.NONE)
    provider_token_hash = models.CharField(max_length=64, blank=True, db_index=True)
    provider_token_encrypted = models.TextField(blank=True)
    notifications_enabled = models.BooleanField(default=False)
    locale = models.CharField(max_length=12, blank=True)
    app_version = models.CharField(max_length=32, blank=True)
    token_updated_at = models.DateTimeField(blank=True, null=True)
    disabled_at = models.DateTimeField(blank=True, null=True)
    failure_count = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now=True, db_index=True)

    class Meta:
        ordering = ('-last_seen_at', '-id')
        constraints = (
            models.UniqueConstraint(fields=('user', 'device_id_hash'), name='unique_user_push_device'),
        )
        indexes = (models.Index(fields=('user', 'last_seen_at'), name='push_device_user_seen_idx'),)

    def __str__(self):
        return f'{self.user} - {self.get_platform_display()}'


class PushDelivery(models.Model):
    class Status(models.TextChoices):
        QUEUED = 'queued', 'Queued'
        SENDING = 'sending', 'Sending'
        DELIVERED = 'delivered', 'Delivered'
        RETRY = 'retry', 'Retry scheduled'
        FAILED = 'failed', 'Permanently failed'
        CANCELLED = 'cancelled', 'Cancelled'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    device = models.ForeignKey(PushDevice, on_delete=models.CASCADE, related_name='deliveries')
    event_key = models.CharField(max_length=120)
    title = models.CharField(max_length=80)
    body = models.CharField(max_length=240)
    target_path = models.CharField(max_length=255, default='/home/')
    data = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.QUEUED, db_index=True)
    attempt_count = models.PositiveSmallIntegerField(default=0)
    next_attempt_at = models.DateTimeField(default=timezone.now, db_index=True)
    provider_message_id = models.CharField(max_length=160, blank=True)
    last_error_code = models.CharField(max_length=80, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    delivered_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ('-created_at',)
        constraints = (
            models.UniqueConstraint(fields=('device', 'event_key'), name='unique_push_event_per_device'),
        )
        indexes = (models.Index(fields=('status', 'next_attempt_at'), name='push_retry_queue_idx'),)


class SyncState(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='mobile_sync_state')
    version = models.PositiveBigIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)


class SyncOperation(models.Model):
    class Status(models.TextChoices):
        APPLIED = 'applied', 'Applied'
        CONFLICT = 'conflict', 'Conflict'
        FAILED = 'failed', 'Failed'

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='mobile_sync_operations')
    device_id_hash = models.CharField(max_length=64)
    client_action_id = models.CharField(max_length=64)
    operation = models.CharField(max_length=32)
    payload_hash = models.CharField(max_length=64)
    status = models.CharField(max_length=12, choices=Status.choices)
    result = models.JSONField(default=dict)
    attempt_count = models.PositiveSmallIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = (
            models.UniqueConstraint(
                fields=('user', 'device_id_hash', 'client_action_id'), name='unique_mobile_sync_action'
            ),
        )
        indexes = (models.Index(fields=('user', 'updated_at'), name='sync_operation_user_idx'),)
