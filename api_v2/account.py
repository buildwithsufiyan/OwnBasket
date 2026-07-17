import hashlib

from django.contrib.auth import authenticate, login, logout
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db.models import Count, Sum
from django.middleware.csrf import get_token

from marketplace.models import SellerProfile
from orders.models import OrderItem
from security.models import AuditEvent
from security.services import audit

from .http import ApiError, api_endpoint, json_body
from .models import PushDevice


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
            'authentication': {'session': True, 'jwt': False},
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
    except Exception:
        state = None
    from django.utils import timezone
    if state and state.locked_until and state.locked_until > timezone.now():
        raise ApiError('account_temporarily_locked', 'Unable to sign in. Try again later.', 423)
    login(request, user)
    return {'authenticated': True, 'user': {'id': user.pk, 'username': user.get_username()}}


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


@api_endpoint(('GET', 'POST'), auth=True)
def push_devices(request):
    if request.method == 'GET':
        return {'results': [{
            'id': device.pk, 'platform': device.platform, 'provider': device.provider,
            'notificationsEnabled': device.notifications_enabled,
            'lastSeenAt': device.last_seen_at.isoformat(),
        } for device in request.user.push_devices.all()[:25]], 'deliveryConfigured': False}
    payload = json_body(request)
    raw_device_id = str(payload.get('deviceId') or '')
    if len(raw_device_id) < 16 or len(raw_device_id) > 512:
        raise ApiError('validation_error', 'deviceId must be an opaque value from 16 to 512 characters.', fields={'deviceId': ['Invalid device identifier.']})
    platform = str(payload.get('platform') or PushDevice.Platform.WEB)
    if platform not in PushDevice.Platform.values:
        raise ApiError('validation_error', 'Platform is not supported.', fields={'platform': ['Unsupported platform.']})
    digest = hashlib.sha256(raw_device_id.encode()).hexdigest()
    device, created = PushDevice.objects.update_or_create(
        user=request.user, device_id_hash=digest,
        defaults={'platform': platform, 'provider': PushDevice.Provider.NONE, 'notifications_enabled': False},
    )
    audit('push_device_registered', category=AuditEvent.Category.ACCOUNT, user=request.user, request=request,
          metadata={'platform': platform, 'device_record_id': device.pk})
    return {'device': {'id': device.pk, 'platform': device.platform, 'notificationsEnabled': False}, 'created': created, 'deliveryConfigured': False}


@api_endpoint(('DELETE',), auth=True)
def push_device_detail(request, device_id):
    deleted, _ = PushDevice.objects.filter(user=request.user, pk=device_id).delete()
    if not deleted:
        raise ApiError('not_found', 'Device registration was not found.', 404)
    audit('push_device_removed', category=AuditEvent.Category.ACCOUNT, user=request.user, request=request,
          metadata={'device_record_id': device_id})
    return {'deleted': True}
