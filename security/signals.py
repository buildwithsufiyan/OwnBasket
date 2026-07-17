from django.contrib.auth import get_user_model
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.db.models.signals import post_save, pre_delete, pre_save
from django.dispatch import receiver
from django.contrib.admin.models import LogEntry
from django.utils import timezone
from datetime import timedelta
import hashlib
from banners.models import HomepageSettings

from marketplace.models import SellerProfile
from orders.models import Order
from products.models import Coupon, Product
from themes.models import Theme

from .models import AccountSecurityState, AuditEvent, PasswordHistory, TwoFactorProfile, UserSession
from .services import audit, create_alert, session_hash, touch_session

User = get_user_model()


@receiver(user_logged_in)
def log_login(sender, request, user, **kwargs):
    AccountSecurityState.objects.filter(user=user).update(failed_login_count=0, locked_until=None)
    touch_session(request, force=True, user=user)
    audit('login', category=AuditEvent.Category.AUTH, user=user, request=request)


@receiver(user_login_failed)
def log_login_failure(sender, credentials, request, **kwargs):
    user = User.objects.filter(username__iexact=(credentials.get('username') or '')).first()
    username_digest = hashlib.sha256((credentials.get('username') or '').strip().lower().encode()).hexdigest()[:16]
    audit('login_failed', category=AuditEvent.Category.AUTH, user=user, success=False, request=request, metadata={'username_hash': username_digest})
    if user:
        state, _ = AccountSecurityState.objects.get_or_create(user=user)
        state.failed_login_count += 1
        state.last_failed_login = timezone.now()
        if state.failed_login_count >= 5:
            state.locked_until = timezone.now() + timedelta(minutes=15)
            create_alert('account_locked', 'Account temporarily locked after repeated failed sign-ins.', user=user)
        state.save(update_fields=('failed_login_count', 'last_failed_login', 'locked_until'))


@receiver(user_logged_out)
def log_logout(sender, request, user, **kwargs):
    key = request.session.session_key if request else None
    if key:
        from django.utils import timezone
        UserSession.objects.filter(session_key_hash=session_hash(key)).update(ended_at=timezone.now())
    audit('logout', category=AuditEvent.Category.AUTH, user=user, request=request)


@receiver(pre_save, sender=User)
def capture_old_password(sender, instance, **kwargs):
    if instance.pk:
        instance._security_old_password = sender.objects.filter(pk=instance.pk).values_list('password', flat=True).first()


@receiver(post_save, sender=User)
def security_user_foundations(sender, instance, created, **kwargs):
    TwoFactorProfile.objects.get_or_create(user=instance)
    AccountSecurityState.objects.get_or_create(user=instance)
    values = [getattr(instance, '_security_old_password', None), instance.password]
    for encoded in values:
        if encoded and not PasswordHistory.objects.filter(user=instance, encoded_password=encoded).exists():
            PasswordHistory.objects.create(user=instance, encoded_password=encoded)
    stale = PasswordHistory.objects.filter(user=instance).order_by('-created_at', '-id').values_list('id', flat=True)[6:]
    PasswordHistory.objects.filter(id__in=list(stale)).delete()


TRACKED = {Product: 'product', Coupon: 'coupon', Order: 'order', SellerProfile: 'seller', Theme: 'theme', HomepageSettings: 'admin_settings'}


def _capture_state(sender, instance, **kwargs):
    if not instance.pk:
        return
    fields = {'status', 'verification_status', 'is_active'}
    instance._security_previous = sender.objects.filter(pk=instance.pk).values(*[field for field in fields if hasattr(instance, field)]).first() or {}


def _audit_tracked(sender, instance, created, **kwargs):
    label = TRACKED[sender]
    previous = getattr(instance, '_security_previous', {})
    changed = {field: f'{old} -> {getattr(instance, field, None)}' for field, old in previous.items() if old != getattr(instance, field, None)}
    action = f'{label}_created' if created else f'{label}_updated'
    if sender is Order and 'status' in changed:
        action = 'order_status_changed'
    elif sender is SellerProfile and 'verification_status' in changed:
        action = 'seller_verification_changed'
    elif sender is Theme and 'is_active' in changed:
        action = 'theme_activation_changed'
    audit(action, category=AuditEvent.Category.COMMERCE if sender is not Theme else AuditEvent.Category.ADMIN, obj=instance, metadata=changed)


for tracked_model in TRACKED:
    pre_save.connect(_capture_state, sender=tracked_model, weak=False, dispatch_uid=f'security_capture_{tracked_model._meta.label_lower}')
    post_save.connect(_audit_tracked, sender=tracked_model, weak=False, dispatch_uid=f'security_audit_{tracked_model._meta.label_lower}')
    pre_delete.connect(lambda sender, instance, **kwargs: audit(f'{TRACKED[sender]}_deleted', category=AuditEvent.Category.ADMIN, obj=instance), sender=tracked_model, weak=False, dispatch_uid=f'security_delete_{tracked_model._meta.label_lower}')


@receiver(post_save, sender=LogEntry)
def mirror_admin_log(sender, instance, created, **kwargs):
    if not created:
        return
    actions = {1: 'admin_created', 2: 'admin_changed', 3: 'admin_deleted'}
    audit(actions.get(instance.action_flag, 'admin_action'), category=AuditEvent.Category.ADMIN, user=instance.user, metadata={'content_type': instance.content_type_id, 'object_id': instance.object_id, 'object_repr': instance.object_repr})
