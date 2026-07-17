from django.conf import settings
from django.db import models


class PushDevice(models.Model):
    class Platform(models.TextChoices):
        WEB = 'web', 'Web/PWA'
        ANDROID = 'android', 'Android (future)'
        IOS = 'ios', 'iOS (future)'

    class Provider(models.TextChoices):
        NONE = 'none', 'Not connected'
        WEB_PUSH = 'web_push', 'Web Push (future)'
        FCM = 'fcm', 'Firebase Cloud Messaging (future)'

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='push_devices')
    device_id_hash = models.CharField(max_length=64)
    platform = models.CharField(max_length=12, choices=Platform.choices, default=Platform.WEB)
    provider = models.CharField(max_length=12, choices=Provider.choices, default=Provider.NONE)
    notifications_enabled = models.BooleanField(default=False)
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
