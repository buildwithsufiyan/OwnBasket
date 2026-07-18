import hashlib
import json

from django.db import transaction
from django.db.models import F
from django.http import Http404
from django.shortcuts import get_object_or_404

from cart.models import CartItem
from cart.services import get_user_cart, touch_cart
from products.models import Product
from wishlist.models import Wishlist

from .catalog import visible_products
from .http import ApiError, api_endpoint, json_body, positive_int
from .models import SyncOperation, SyncState


SUPPORTED_OPERATIONS = {'cart:add', 'cart:update', 'cart:remove', 'wishlist:add', 'wishlist:remove'}


def bump_sync_state(user):
    state, _ = SyncState.objects.get_or_create(user=user)
    SyncState.objects.filter(pk=state.pk).update(version=F('version') + 1)
    state.refresh_from_db(fields=('version', 'updated_at'))
    return state


def _device_hash(request):
    if getattr(request, 'mobile_session', None):
        return request.mobile_session.device_id_hash
    session_key = request.session.session_key or 'session-not-persisted'
    return hashlib.sha256(session_key.encode()).hexdigest()


def _payload_hash(operation, payload):
    canonical = json.dumps({'operation': operation, 'payload': payload}, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(canonical.encode()).hexdigest()


def _validate_action(action):
    if not isinstance(action, dict):
        raise ApiError('validation_error', 'Each sync action must be an object.')
    action_id = str(action.get('clientActionId') or '').strip()
    if not 8 <= len(action_id) <= 64 or not all(char.isalnum() or char in '-_.' for char in action_id):
        raise ApiError('validation_error', 'clientActionId is invalid.', fields={'clientActionId': ['Use 8 to 64 safe characters.']})
    operation = str(action.get('operation') or '')
    if operation not in SUPPORTED_OPERATIONS:
        raise ApiError('unsupported_sync_operation', 'This operation cannot be synchronized.', 400)
    payload = action.get('payload') or {}
    if not isinstance(payload, dict):
        raise ApiError('validation_error', 'Sync payload must be an object.')
    allowed = {
        'cart:add': {'productId', 'quantity', 'size', 'color'},
        'cart:update': {'itemId', 'quantity'}, 'cart:remove': {'itemId'},
        'wishlist:add': {'productId'}, 'wishlist:remove': {'productId'},
    }[operation]
    if set(payload) - allowed:
        raise ApiError('unsafe_sync_payload', 'Sync payload contains unsupported fields.', 400)
    return action_id, operation, payload


def _apply(user, operation, payload):
    if operation == 'cart:add':
        product = get_object_or_404(visible_products(), pk=positive_int(payload.get('productId'), name='productId'))
        quantity = positive_int(payload.get('quantity'), name='quantity', default=1, maximum=99)
        cart = get_user_cart(user)
        item, created = CartItem.objects.get_or_create(
            cart=cart, product=product, size=(str(payload.get('size') or '')[:50] or None),
            color=(str(payload.get('color') or '')[:50] or None), defaults={'quantity': quantity},
        )
        if not created:
            item.quantity = min(99, item.quantity + quantity)
            item.save(update_fields=('quantity',))
        touch_cart(cart)
        return {'itemId': item.pk, 'quantity': item.quantity, 'created': created}
    if operation in {'cart:update', 'cart:remove'}:
        item = get_object_or_404(CartItem.objects.select_related('cart'), pk=positive_int(payload.get('itemId'), name='itemId'), cart__user=user)
        item_id = item.pk
        if operation == 'cart:remove':
            cart = item.cart
            item.delete()
            touch_cart(cart)
            return {'itemId': item_id, 'deleted': True}
        item.quantity = positive_int(payload.get('quantity'), name='quantity', maximum=99)
        item.save(update_fields=('quantity',))
        touch_cart(item.cart)
        return {'itemId': item.pk, 'quantity': item.quantity}
    product_id = positive_int(payload.get('productId'), name='productId')
    if operation == 'wishlist:add':
        product = get_object_or_404(visible_products(), pk=product_id)
        _, created = Wishlist.objects.get_or_create(user=user, product=product)
        if created:
            Product.objects.filter(pk=product_id).update(wishlist_count=F('wishlist_count') + 1)
        return {'productId': product_id, 'created': created}
    deleted, _ = Wishlist.objects.filter(user=user, product_id=product_id).delete()
    if deleted:
        Product.objects.filter(pk=product_id, wishlist_count__gt=0).update(wishlist_count=F('wishlist_count') - 1)
    return {'productId': product_id, 'deleted': bool(deleted)}


@api_endpoint(
    ('POST',), auth=True, idempotent=True, summary='Apply an offline action batch', tags=('Synchronization',),
    request_example={'baseVersion': 3, 'actions': [{'clientActionId': 'action-0001', 'operation': 'wishlist:add', 'payload': {'productId': 42}}]},
    response_example={'serverVersion': 4, 'results': [{'clientActionId': 'action-0001', 'status': 'applied'}]},
)
def sync_batch(request):
    body = json_body(request)
    actions = body.get('actions')
    if not isinstance(actions, list) or not 1 <= len(actions) <= 50:
        raise ApiError('validation_error', 'actions must contain 1 to 50 operations.', fields={'actions': ['Invalid batch size.']})
    base_version = body.get('baseVersion')
    if base_version is not None and (not isinstance(base_version, int) or base_version < 0):
        raise ApiError('validation_error', 'baseVersion must be a non-negative integer.')
    device = _device_hash(request)
    state, _ = SyncState.objects.get_or_create(user=request.user)
    results = []
    for action in actions:
        action_id, operation, payload = _validate_action(action)
        digest = _payload_hash(operation, payload)
        existing = SyncOperation.objects.filter(
            user=request.user, device_id_hash=device, client_action_id=action_id,
        ).first()
        if existing:
            if existing.payload_hash != digest:
                raise ApiError('sync_action_conflict', 'clientActionId was reused with different content.', 409)
            results.append({**existing.result, 'duplicate': True})
            continue
        if base_version is not None and state.version != base_version:
            result = {
                'clientActionId': action_id, 'operation': operation, 'status': 'conflict',
                'code': 'stale_base_version', 'serverVersion': state.version,
            }
            SyncOperation.objects.create(
                user=request.user, device_id_hash=device, client_action_id=action_id,
                operation=operation, payload_hash=digest, status=SyncOperation.Status.CONFLICT, result=result,
            )
            results.append(result)
            continue
        try:
            with transaction.atomic():
                outcome = _apply(request.user, operation, payload)
                state = bump_sync_state(request.user)
        except (ApiError, Http404) as exc:
            code = exc.code if isinstance(exc, ApiError) else 'not_found'
            result = {
                'clientActionId': action_id, 'operation': operation, 'status': 'failed',
                'code': code, 'serverVersion': state.version,
            }
            SyncOperation.objects.create(
                user=request.user, device_id_hash=device, client_action_id=action_id,
                operation=operation, payload_hash=digest, status=SyncOperation.Status.FAILED, result=result,
            )
            results.append(result)
            continue
        result = {
            'clientActionId': action_id, 'operation': operation, 'status': 'applied',
            'serverVersion': state.version, 'data': outcome,
        }
        SyncOperation.objects.create(
            user=request.user, device_id_hash=device, client_action_id=action_id,
            operation=operation, payload_hash=digest, status=SyncOperation.Status.APPLIED, result=result,
        )
        results.append(result)
        if base_version is not None:
            base_version = state.version
    return {'serverVersion': state.version, 'results': results, 'retryable': False}
