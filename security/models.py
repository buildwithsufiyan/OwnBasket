from django.conf import settings
from django.db import models


class AuditEvent(models.Model):
    class Category(models.TextChoices):
        AUTH = 'auth', 'Authentication'
        ACCOUNT = 'account', 'Account'
        ADMIN = 'admin', 'Administration'
        COMMERCE = 'commerce', 'Commerce'
        SECURITY = 'security', 'Security'
        COMPLIANCE = 'compliance', 'Compliance'

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True, related_name='audit_events')
    category = models.CharField(max_length=16, choices=Category.choices, db_index=True)
    action = models.CharField(max_length=80, db_index=True)
    success = models.BooleanField(default=True, db_index=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.CharField(max_length=512, blank=True)
    request_id = models.CharField(max_length=36, blank=True, db_index=True)
    object_app = models.CharField(max_length=50, blank=True)
    object_model = models.CharField(max_length=80, blank=True)
    object_id = models.CharField(max_length=100, blank=True)
    object_repr = models.CharField(max_length=200, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ('-timestamp', '-id')
        indexes = (
            models.Index(fields=('category', 'action', 'timestamp'), name='audit_category_action_idx'),
            models.Index(fields=('user', 'timestamp'), name='audit_user_time_idx'),
        )
        permissions = (('view_security_dashboard', 'Can view security dashboard'),)

    def __str__(self):
        return f'{self.action} at {self.timestamp:%Y-%m-%d %H:%M:%S}'


class UserSession(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='security_sessions')
    session_key_hash = models.CharField(max_length=64, unique=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.CharField(max_length=512, blank=True)
    device = models.CharField(max_length=120, blank=True)
    browser = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_active = models.DateTimeField(auto_now=True, db_index=True)
    ended_at = models.DateTimeField(blank=True, null=True, db_index=True)

    class Meta:
        ordering = ('-last_active', '-id')
        indexes = (models.Index(fields=('user', 'ended_at', 'last_active'), name='user_session_active_idx'),)

    def __str__(self):
        return f'{self.user} - {self.device or "Unknown device"}'


class TwoFactorProfile(models.Model):
    class Method(models.TextChoices):
        EMAIL = 'email', 'Email OTP'
        AUTHENTICATOR = 'authenticator', 'Authenticator app (future)'

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='two_factor_profile')
    opted_in = models.BooleanField(default=False)
    method = models.CharField(max_length=20, choices=Method.choices, default=Method.EMAIL)
    verified_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.user} - {self.get_method_display()}'


class AccountSecurityState(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='security_state')
    failed_login_count = models.PositiveIntegerField(default=0)
    locked_until = models.DateTimeField(blank=True, null=True, db_index=True)
    last_failed_login = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f'{self.user} security state'


class PasswordHistory(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='password_history')
    encoded_password = models.CharField(max_length=256)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at', '-id')
        indexes = (models.Index(fields=('user', 'created_at'), name='password_history_user_idx'),)


class SecurityAlert(models.Model):
    class Severity(models.TextChoices):
        INFO = 'info', 'Information'
        WARNING = 'warning', 'Warning'
        CRITICAL = 'critical', 'Critical'

    severity = models.CharField(max_length=10, choices=Severity.choices, default=Severity.WARNING, db_index=True)
    alert_type = models.CharField(max_length=60, db_index=True)
    message = models.CharField(max_length=255)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, blank=True, null=True)
    resolved = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    resolved_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ('-created_at', '-id')


class PrivacyRequest(models.Model):
    class RequestType(models.TextChoices):
        EXPORT = 'export', 'Data export'
        DELETION = 'deletion', 'Data deletion'
        CORRECTION = 'correction', 'Data correction'

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending review'
        IN_PROGRESS = 'in_progress', 'In progress'
        COMPLETED = 'completed', 'Completed'
        REJECTED = 'rejected', 'Rejected'

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='privacy_requests')
    request_type = models.CharField(max_length=16, choices=RequestType.choices)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING, db_index=True)
    notes = models.TextField(blank=True)
    requested_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ('-requested_at', '-id')
        permissions = (('process_privacy_requests', 'Can process privacy requests'),)


class PolicyVersion(models.Model):
    policy_type = models.CharField(max_length=40)
    version = models.CharField(max_length=30)
    published_at = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    content_hash = models.CharField(max_length=64, help_text='SHA-256 of the approved policy document.')

    class Meta:
        ordering = ('-published_at', '-id')
        constraints = (models.UniqueConstraint(fields=('policy_type', 'version'), name='unique_policy_version'),)


class PolicyAcceptance(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='policy_acceptances')
    policy = models.ForeignKey(PolicyVersion, on_delete=models.PROTECT, related_name='acceptances')
    accepted_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)

    class Meta:
        constraints = (models.UniqueConstraint(fields=('user', 'policy'), name='unique_user_policy_acceptance'),)
