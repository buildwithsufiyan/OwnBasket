import hashlib

from django.contrib.auth import authenticate, login, logout
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.core.validators import validate_email
from django.db.models import Count, Sum
from django.middleware.csrf import get_token
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from marketplace.models import SellerProfile
from orders.models import OrderItem
from security.models import AuditEvent
from security.services import audit

from .auth import issue_mobile_session, rotate_refresh_token, token_payload
from .crypto import encrypt_provider_token
from .http import ApiError, api_endpoint, json_body
from .models import MobileSession, PushDelivery, PushDevice
from .push import PROVIDER_ADAPTERS


@api_endpoint(('GET', 'POST', 'DELETE'))
def session(request):
    if request.method == 'GET':
        return {
            'authenticated': request.user.is_authenticated,
            'csrfToken': get_token(request),
            'user': ({
                'id': request.user.pk, 'username': request.user.get_username(),
                'firstName': request.user.first_name, 'lastName': request.user.last_name,
                'email': request.user.email,
            } if request.user.is_authenticated else None),
            'authentication': {'session': True, 'bearer': True, 'jwt': False},
        }
    if request.method == 'DELETE':
        if request.user.is_authenticated:
            logout(request)
        return {'authenticated': False}

    payload = json_body(request)
    username = str(payload.get('username') or '').strip()
    password = str(payload.get('password') or '')
    user = authenticate(request, username=username, password=password)
    if user is None:
        raise ApiError('invalid_credentials', 'Unable to sign in with these credentials.', 400)
    try:
        state = user.security_state
    except ObjectDoesNotExist:
        state = None
    if state and state.locked_until and state.locked_until > timezone.now():
        raise ApiError('account_temporarily_locked', 'Unable to sign in. Try again later.', 423)
    login(request, user)
    return {'authenticated': True, 'user': {'id': user.pk, 'username': user.get_username()}}


def _mobile_identity(payload):
    device_id = str(payload.get('deviceId') or '').strip()
    if len(device_id) < 16 or len(device_id) > 512:
        raise ApiError(
            'validation_error', 'deviceId must be an opaque value from 16 to 512 characters.',
            fields={'deviceId': ['Invalid device identifier.']},
        )
    platform = str(payload.get('platform') or 'unknown').strip().lower()
    if platform not in {'web', 'android', 'ios', 'unknown'}:
        raise ApiError('validation_error', 'Platform is not supported.', fields={'platform': ['Unsupported platform.']})
    return device_id, str(payload.get('deviceName') or '').strip(), platform


@csrf_exempt
@api_endpoint(
    ('POST',), summary='Issue mobile tokens', tags=('Authentication',),
    request_example={'username': 'buyer', 'password': 'secret', 'deviceId': 'opaque-installation-id', 'platform': 'android'},
    response_example={'tokenType': 'Bearer', 'accessToken': '<opaque>', 'refreshToken': '<opaque>', 'sessionId': 1},
)
def token_login(request):
    payload = json_body(request)
    username = str(payload.get('username') or '').strip()
    password = str(payload.get('password') or '')
    device_id, device_name, platform = _mobile_identity(payload)
    user = authenticate(request, username=username, password=password)
    if user is None:
        raise ApiError('invalid_credentials', 'Unable to sign in with these credentials.', 400)
    state = getattr(user, 'security_state', None)
    if state and state.locked_until and state.locked_until > timezone.now():
        raise ApiError('account_temporarily_locked', 'Unable to sign in. Try again later.', 423)
    session, access_token, refresh_token = issue_mobile_session(
        user, device_id=device_id, device_name=device_name, platform=platform,
    )
    audit('mobile_token_issued', category=AuditEvent.Category.ACCOUNT, user=user, request=request,
          metadata={'mobile_session_id': session.pk, 'platform': platform})
    return {**token_payload(session, access_token, refresh_token), 'user': {'id': user.pk, 'username': user.get_username()}}


@csrf_exempt
@api_endpoint(
    ('POST',), summary='Rotate refresh token', tags=('Authentication',),
    request_example={'refreshToken': '<opaque-refresh-token>'},
    response_example={'tokenType': 'Bearer', 'accessToken': '<new-opaque>', 'refreshToken': '<new-opaque>'},
)
def token_refresh(request):
    payload = json_body(request)
    raw_token = str(payload.get('refreshToken') or '').strip()
    if len(raw_token) < 32 or len(raw_token) > 512:
        raise ApiError('invalid_refresh_token', 'Refresh token is invalid.', 401)
    session, access_token, refresh_token, error = rotate_refresh_token(raw_token)
    if error:
        status = 409 if error == 'refresh_token_reused' else 401
        raise ApiError(error, 'Refresh token is invalid, expired, revoked, or already used.', status)
    audit('mobile_token_rotated', category=AuditEvent.Category.ACCOUNT, user=session.user, request=request,
          metadata={'mobile_session_id': session.pk})
    return token_payload(session, access_token, refresh_token)


@api_endpoint(('GET', 'DELETE'), auth=True, summary='List or revoke mobile sessions', tags=('Authentication',))
def token_sessions(request):
    if request.method == 'DELETE':
        current = getattr(request, 'mobile_session', None)
        if current is None:
            raise ApiError('bearer_authentication_required', 'Use the Bearer token for the device being logged out.', 400)
        current.revoke('device_logout')
        audit('mobile_device_logged_out', category=AuditEvent.Category.ACCOUNT, user=request.user, request=request,
              metadata={'mobile_session_id': current.pk})
        return {'revoked': True, 'sessionId': current.pk}
    return {'results': [{
        'id': item.pk, 'deviceName': item.device_name, 'platform': item.platform,
        'createdAt': item.created_at.isoformat(), 'lastUsedAt': item.last_used_at.isoformat(),
        'accessExpiresAt': item.access_expires_at.isoformat(),
        'refreshExpiresAt': item.refresh_expires_at.isoformat(),
        'absoluteExpiresAt': item.absolute_expires_at.isoformat(),
        'current': item.pk == getattr(getattr(request, 'mobile_session', None), 'pk', None),
    } for item in request.user.mobile_sessions.filter(revoked_at__isnull=True)[:25]]}


@api_endpoint(('DELETE',), auth=True, summary='Revoke a mobile device session', tags=('Authentication',))
def token_session_detail(request, session_id):
    session = MobileSession.objects.filter(user=request.user, pk=session_id, revoked_at__isnull=True).first()
    if not session:
        raise ApiError('not_found', 'Mobile session was not found.', 404)
    session.revoke('device_logout')
    audit('mobile_device_logged_out', category=AuditEvent.Category.ACCOUNT, user=request.user, request=request,
          metadata={'mobile_session_id': session.pk})
    return {'revoked': True, 'sessionId': session.pk}


@api_endpoint(('GET', 'PATCH'), auth=True)
def profile(request):
    user = request.user
    if request.method == 'GET':
        return {'profile': {
            'id': user.pk, 'username': user.get_username(), 'email': user.email,
            'firstName': user.first_name, 'lastName': user.last_name,
            'dateJoined': user.date_joined.isoformat(),
        }}
    payload = json_body(request)
    allowed = {'firstName': 'first_name', 'lastName': 'last_name', 'email': 'email'}
    update_fields = []
    for source, target in allowed.items():
        if source in payload:
            value = str(payload[source] or '').strip()
            if target == 'email':
                try:
                    validate_email(value)
                except ValidationError:
                    raise ApiError('validation_error', 'Email is invalid.', fields={'email': ['Enter a valid email address.']})
            max_length = 150 if target != 'email' else 254
            if len(value) > max_length:
                raise ApiError('validation_error', f'{source} is too long.', fields={source: [f'Use no more than {max_length} characters.']})
            setattr(user, target, value)
            update_fields.append(target)
    if update_fields:
        user.save(update_fields=update_fields)
        audit('profile_updated_via_api', category=AuditEvent.Category.ACCOUNT, user=user, request=request)
    return {'profile': {'id': user.pk, 'email': user.email, 'firstName': user.first_name, 'lastName': user.last_name}}


@api_endpoint(auth=True)
def seller_dashboard(request):
    try:
        seller = request.user.seller_profile
    except SellerProfile.DoesNotExist:
        raise ApiError('seller_account_required', 'This account does not have a seller profile.', 403)
    lines = OrderItem.objects.filter(seller=seller)
    totals = lines.aggregate(earnings=Sum('seller_earning'), orders=Count('order_id', distinct=True))
    return {'seller': {
        'id': seller.pk, 'storeName': seller.store_name,
        'verificationStatus': seller.verification_status,
        'productCount': seller.products.count(),
        'activeProductCount': seller.products.filter(is_active=True).count(),
        'orderCount': totals['orders'] or 0,
        'earnings': f"{totals['earnings'] or 0:.2f}",
    }}


@api_endpoint(('GET', 'POST'), auth=True, summary='List or register push devices', tags=('Push',))
def push_devices(request):
    if request.method == 'GET':
        return {'results': [{
            'id': device.pk, 'platform': device.platform, 'provider': device.provider,
            'notificationsEnabled': device.notifications_enabled, 'appVersion': device.app_version,
            'lastSeenAt': device.last_seen_at.isoformat(),
        } for device in request.user.push_devices.all()[:25]],
        'deliveryLifecycleAvailable': True, 'configuredProviders': sorted(PROVIDER_ADAPTERS),
    }
    payload = json_body(request)
    raw_device_id = str(payload.get('deviceId') or '')
    if len(raw_device_id) < 16 or len(raw_device_id) > 512:
        raise ApiError('validation_error', 'deviceId must be an opaque value from 16 to 512 characters.', fields={'deviceId': ['Invalid device identifier.']})
    platform = str(payload.get('platform') or PushDevice.Platform.WEB)
    if platform not in PushDevice.Platform.values:
        raise ApiError('validation_error', 'Platform is not supported.', fields={'platform': ['Unsupported platform.']})
    digest = hashlib.sha256(raw_device_id.encode()).hexdigest()
    provider = str(payload.get('provider') or PushDevice.Provider.NONE)
    if provider not in PushDevice.Provider.values:
        raise ApiError('validation_error', 'Push provider is not supported.', fields={'provider': ['Unsupported provider.']})
    provider_token = str(payload.get('pushToken') or '').strip()
    if provider != PushDevice.Provider.NONE and not 16 <= len(provider_token) <= 4096:
        raise ApiError('validation_error', 'pushToken is invalid.', fields={'pushToken': ['Use 16 to 4096 characters.']})
    defaults = {
        'platform': platform, 'provider': provider,
        'notifications_enabled': provider != PushDevice.Provider.NONE,
        'locale': str(payload.get('locale') or '')[:12],
        'app_version': str(payload.get('appVersion') or '')[:32],
        'disabled_at': None,
    }
    if provider_token:
        defaults.update({
            'provider_token_hash': hashlib.sha256(provider_token.encode()).hexdigest(),
            'provider_token_encrypted': encrypt_provider_token(provider_token),
            'token_updated_at': timezone.now(), 'failure_count': 0,
        })
    device, created = PushDevice.objects.update_or_create(
        user=request.user, device_id_hash=digest,
        defaults=defaults,
    )
    audit('push_device_registered', category=AuditEvent.Category.ACCOUNT, user=request.user, request=request,
          metadata={'platform': platform, 'device_record_id': device.pk})
    return {'device': {
        'id': device.pk, 'platform': device.platform, 'provider': device.provider,
        'notificationsEnabled': device.notifications_enabled,
    }, 'created': created, 'deliveryLifecycleAvailable': True, 'providerConfigured': provider in PROVIDER_ADAPTERS}


@api_endpoint(('GET', 'PATCH', 'DELETE'), auth=True, summary='Manage a push device', tags=('Push',))
def push_device_detail(request, device_id):
    device = PushDevice.objects.filter(user=request.user, pk=device_id).first()
    if not device:
        raise ApiError('not_found', 'Device registration was not found.', 404)
    if request.method == 'GET':
        return {'device': {
            'id': device.pk, 'platform': device.platform, 'provider': device.provider,
            'notificationsEnabled': device.notifications_enabled, 'failureCount': device.failure_count,
            'tokenUpdatedAt': device.token_updated_at.isoformat() if device.token_updated_at else None,
        }}
    if request.method == 'PATCH':
        payload = json_body(request)
        provider_token = str(payload.get('pushToken') or '').strip()
        if provider_token:
            if len(provider_token) > 4096 or len(provider_token) < 16:
                raise ApiError('validation_error', 'pushToken is invalid.', fields={'pushToken': ['Use 16 to 4096 characters.']})
            device.provider_token_hash = hashlib.sha256(provider_token.encode()).hexdigest()
            device.provider_token_encrypted = encrypt_provider_token(provider_token)
            device.token_updated_at = timezone.now()
            device.failure_count = 0
        if 'notificationsEnabled' in payload:
            if payload['notificationsEnabled'] is True and not (provider_token or device.provider_token_encrypted):
                raise ApiError('push_token_required', 'A provider token is required before notifications can be enabled.', 400)
            device.notifications_enabled = payload['notificationsEnabled'] is True
            device.disabled_at = None if device.notifications_enabled else timezone.now()
        device.app_version = str(payload.get('appVersion', device.app_version) or '')[:32]
        device.locale = str(payload.get('locale', device.locale) or '')[:12]
        device.save()
        return {'device': {'id': device.pk, 'notificationsEnabled': device.notifications_enabled, 'tokenUpdatedAt': device.token_updated_at.isoformat() if device.token_updated_at else None}}
    device.delete()
    audit('push_device_removed', category=AuditEvent.Category.ACCOUNT, user=request.user, request=request,
          metadata={'device_record_id': device_id})
    return {'deleted': True}


@api_endpoint(auth=True, summary='List push delivery statuses', tags=('Push',))
def push_deliveries(request):
    deliveries = PushDelivery.objects.filter(device__user=request.user).select_related('device')[:50]
    return {'results': [{
        'id': str(item.pk), 'deviceId': item.device_id, 'eventKey': item.event_key,
        'status': item.status, 'attemptCount': item.attempt_count,
        'nextAttemptAt': item.next_attempt_at.isoformat(), 'deliveredAt': item.delivered_at.isoformat() if item.delivered_at else None,
        'errorCode': item.last_error_code,
    } for item in deliveries]}
