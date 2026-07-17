import hashlib
import ipaddress
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from .context import get_current_request
from .models import AuditEvent, SecurityAlert, UserSession


def client_ip(request):
    value = request.META.get('REMOTE_ADDR', '')
    if settings.TRUST_PROXY_HEADERS:
        value = request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip() or value
    try:
        return str(ipaddress.ip_address(value))
    except ValueError:
        return None


def session_hash(session_key):
    return hashlib.sha256((session_key or '').encode('utf-8')).hexdigest()


def describe_user_agent(value):
    ua = (value or '')[:512]
    browser = next((name for token, name in (('Edg/', 'Microsoft Edge'), ('Chrome/', 'Chrome'), ('Firefox/', 'Firefox'), ('Safari/', 'Safari')) if token in ua), 'Unknown browser')
    device = 'Mobile device' if any(token in ua for token in ('Mobile', 'Android', 'iPhone')) else 'Desktop or laptop'
    return device, browser


def audit(action, *, category=AuditEvent.Category.SECURITY, user=None, success=True, obj=None, metadata=None, request=None):
    request = request or get_current_request()
    if user is None and request is not None and getattr(request, 'user', None) and request.user.is_authenticated:
        user = request.user
    safe_metadata = {}
    sensitive_fragments = ('password', 'token', 'secret', 'authorization', 'cookie', 'session', 'otp', 'card', 'cvv', 'object_repr')
    for key, value in (metadata or {}).items():
        normalized_key = str(key).lower()
        if not any(fragment in normalized_key for fragment in sensitive_fragments):
            safe_metadata[str(key)[:80]] = str(value)[:500]
    return AuditEvent.objects.create(
        user=user, action=action[:80], category=category, success=success,
        ip_address=client_ip(request) if request else None,
        user_agent=(request.META.get('HTTP_USER_AGENT', '')[:512] if request else ''),
        request_id=(getattr(request, 'security_request_id', '') if request else ''),
        object_app=(obj._meta.app_label if obj is not None else ''),
        object_model=(obj._meta.model_name if obj is not None else ''),
        object_id=(str(obj.pk)[:100] if obj is not None and obj.pk is not None else ''),
        object_repr=_safe_object_repr(obj), metadata=safe_metadata,
    )


def _safe_object_repr(obj):
    if obj is None:
        return ''
    allowed = {
        ('products', 'product'), ('products', 'coupon'),
        ('marketplace', 'sellerprofile'), ('themes', 'theme'),
        ('banners', 'homepagesettings'),
    }
    return str(obj)[:200] if (obj._meta.app_label, obj._meta.model_name) in allowed else ''


def touch_session(request, force=False, user=None):
    user = user or getattr(request, 'user', None)
    if user is None or not user.is_authenticated:
        return None
    if not request.session.session_key:
        request.session.save()
    key_hash = session_hash(request.session.session_key)
    device, browser = describe_user_agent(request.META.get('HTTP_USER_AGENT', ''))
    session, created = UserSession.objects.get_or_create(
        session_key_hash=key_hash,
        defaults={'user': user, 'ip_address': client_ip(request), 'user_agent': request.META.get('HTTP_USER_AGENT', '')[:512], 'device': device, 'browser': browser},
    )
    if not created and session.user_id == user.id:
        threshold = timezone.now() - timedelta(minutes=5)
        if force or session.last_active < threshold or session.ended_at is not None:
            UserSession.objects.filter(pk=session.pk).update(last_active=timezone.now(), ended_at=None, ip_address=client_ip(request))
    return session


def create_alert(alert_type, message, *, user=None, severity=SecurityAlert.Severity.WARNING):
    return SecurityAlert.objects.create(alert_type=alert_type[:60], message=message[:255], user=user, severity=severity)
