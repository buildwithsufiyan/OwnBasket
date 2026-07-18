import hashlib
import hmac
import secrets
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import MobileSession, UsedRefreshToken


def token_hash(value):
    return hmac.new(settings.SECRET_KEY.encode(), value.encode(), hashlib.sha256).hexdigest()


def device_hash(value):
    return hashlib.sha256(value.encode()).hexdigest()


def _new_token():
    return secrets.token_urlsafe(48)


@transaction.atomic
def issue_mobile_session(user, *, device_id, device_name='', platform='unknown'):
    now = timezone.now()
    digest = device_hash(device_id)
    MobileSession.objects.filter(user=user, device_id_hash=digest, revoked_at__isnull=True).update(
        revoked_at=now, revoke_reason='device_replaced',
    )
    access_token, refresh_token = _new_token(), _new_token()
    session = MobileSession.objects.create(
        user=user,
        device_id_hash=digest,
        device_name=device_name[:120],
        platform=platform[:12],
        access_token_hash=token_hash(access_token),
        refresh_token_hash=token_hash(refresh_token),
        access_expires_at=now + timedelta(minutes=settings.MOBILE_ACCESS_TOKEN_MINUTES),
        refresh_expires_at=now + timedelta(days=settings.MOBILE_REFRESH_TOKEN_DAYS),
        absolute_expires_at=now + timedelta(days=settings.MOBILE_SESSION_MAX_DAYS),
        last_used_at=now,
    )
    return session, access_token, refresh_token


def token_payload(session, access_token, refresh_token):
    return {
        'tokenType': 'Bearer',
        'accessToken': access_token,
        'accessExpiresAt': session.access_expires_at.isoformat(),
        'refreshToken': refresh_token,
        'refreshExpiresAt': session.refresh_expires_at.isoformat(),
        'sessionExpiresAt': session.absolute_expires_at.isoformat(),
        'sessionId': session.pk,
    }


def authenticate_access_token(raw_token):
    now = timezone.now()
    try:
        session = MobileSession.objects.select_related('user').get(access_token_hash=token_hash(raw_token))
    except MobileSession.DoesNotExist:
        return None, 'invalid_token'
    if session.revoked_at is not None:
        return None, 'revoked_token'
    if session.access_expires_at <= now:
        return None, 'expired_token'
    if not session.user.is_active:
        session.revoke('user_inactive')
        return None, 'invalid_token'
    if session.last_used_at < now - timedelta(minutes=5):
        MobileSession.objects.filter(pk=session.pk).update(last_used_at=now)
        session.last_used_at = now
    return session, None


@transaction.atomic
def rotate_refresh_token(raw_token):
    digest = token_hash(raw_token)
    now = timezone.now()
    session = MobileSession.objects.select_for_update().select_related('user').filter(
        refresh_token_hash=digest,
    ).first()
    if session is None:
        replay = UsedRefreshToken.objects.select_related('session').filter(token_hash=digest).first()
        if replay:
            replay.session.revoke('refresh_reuse')
            return None, None, None, 'refresh_token_reused'
        return None, None, None, 'invalid_refresh_token'
    if session.revoked_at is not None:
        return None, None, None, 'revoked_refresh_token'
    if session.refresh_expires_at <= now or session.absolute_expires_at <= now or not session.user.is_active:
        session.revoke('refresh_expired')
        return None, None, None, 'expired_refresh_token'

    UsedRefreshToken.objects.create(
        session=session, token_hash=session.refresh_token_hash, expires_at=session.refresh_expires_at,
    )
    access_token, refresh_token = _new_token(), _new_token()
    session.access_token_hash = token_hash(access_token)
    session.refresh_token_hash = token_hash(refresh_token)
    session.access_expires_at = now + timedelta(minutes=settings.MOBILE_ACCESS_TOKEN_MINUTES)
    session.refresh_expires_at = min(
        now + timedelta(days=settings.MOBILE_REFRESH_TOKEN_DAYS), session.absolute_expires_at,
    )
    session.last_used_at = now
    session.save(update_fields=(
        'access_token_hash', 'refresh_token_hash', 'access_expires_at',
        'refresh_expires_at', 'last_used_at',
    ))
    return session, access_token, refresh_token, None
