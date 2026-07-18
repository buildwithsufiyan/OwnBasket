import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse
from PIL import Image

from cart.models import CartItem
from cart.services import get_user_cart
from marketplace.models import SellerProfile
from orders.models import Order, OrderItem
from products.models import Brand, Category, Product, ProductReview
from wishlist.models import Wishlist

from .crypto import decrypt_provider_token
from .models import IdempotencyRecord, MobileSession, PushDelivery, PushDevice, SyncOperation, SyncState
from .push import PROVIDER_ADAPTERS, deliver_push, queue_push


User = get_user_model()
PASSWORD = 'Mobile-API-Strong-Pass-123!'
TINY_GIF = (
    b'GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00'
    b'\xff\xff\xff!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00'
    b'\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;'
)


def api_post(client, url, payload):
    return client.post(url, data=json.dumps(payload), content_type='application/json')


class ApiV2Base(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('mobile-user', 'mobile@example.com', PASSWORD)
        self.other = User.objects.create_user('mobile-other', 'other@example.com', PASSWORD)
        self.category = Category.objects.create(name='Mobile', slug='mobile', is_active=True)
        self.brand = Brand.objects.create(name='Own Brand', is_active=True)
        self.product = Product.objects.create(
            name='Mobile product', category=self.category, brand=self.brand,
            price=Decimal('100.00'), cost_price=Decimal('45.00'), stock=5,
            description='Mobile API product', short_description='Compact payload',
            image=SimpleUploadedFile('mobile.gif', TINY_GIF, content_type='image/gif'),
        )


class ApiV2CatalogTests(ApiV2Base):
    def test_api_index_is_versioned_and_honest_about_authentication(self):
        response = self.client.get(reverse('api-v2:index'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['version'], '2.0')
        self.assertFalse(response.json()['authentication']['jwt']['available'])
        self.assertEqual(response['API-Version'], '2.0')

    def test_products_are_paginated_and_exclude_sensitive_cost_data(self):
        response = self.client.get(reverse('api-v2:products'), {'page_size': 1})
        payload = response.json()
        self.assertEqual(payload['pagination']['totalItems'], 1)
        product = payload['results'][0]
        self.assertEqual(product['name'], self.product.name)
        self.assertNotIn('cost_price', product)
        self.assertNotIn('costPrice', product)

    def test_invalid_page_and_method_use_consistent_json_errors(self):
        response = self.client.get(reverse('api-v2:products'), {'page': 999})
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()['error']['code'], 'page_out_of_range')
        response = self.client.post(reverse('api-v2:products'))
        self.assertEqual(response.status_code, 405)
        self.assertEqual(response.json()['error']['code'], 'method_not_allowed')

    def test_review_submission_requires_purchase_and_starts_pending(self):
        self.client.force_login(self.user)
        url = reverse('api-v2:product-reviews', args=(self.product.pk,))
        self.assertEqual(api_post(self.client, url, {'rating': 5, 'body': 'Great'}).status_code, 403)
        order = Order.objects.create(user=self.user, full_name='Buyer', email=self.user.email, address='Address', total_price=100)
        OrderItem.objects.create(order=order, product=self.product, quantity=1, price=100)
        response = api_post(self.client, url, {'rating': 5, 'title': 'Good', 'body': 'Great'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(ProductReview.objects.get(user=self.user, product=self.product).moderation_status, 'pending')


class ApiV2CommerceTests(ApiV2Base):
    def test_private_endpoints_return_json_401(self):
        response = self.client.get(reverse('api-v2:cart'))
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()['error']['code'], 'authentication_required')

    def test_cart_mutations_are_owner_scoped(self):
        own_cart = get_user_cart(self.user)
        foreign_item = CartItem.objects.create(cart=get_user_cart(self.other), product=self.product, quantity=1)
        self.client.force_login(self.user)
        response = self.client.patch(
            reverse('api-v2:cart-item-detail', args=(foreign_item.pk,)),
            data=json.dumps({'quantity': 3}), content_type='application/json',
        )
        self.assertEqual(response.status_code, 404)
        foreign_item.refresh_from_db()
        self.assertEqual(foreign_item.quantity, 1)
        response = api_post(self.client, reverse('api-v2:cart-items'), {'productId': self.product.pk, 'quantity': 2})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(CartItem.objects.get(cart=own_cart).quantity, 2)

    def test_checkout_reuses_order_service_and_rejects_duplicate_submission(self):
        CartItem.objects.create(cart=get_user_cart(self.user), product=self.product, quantity=1)
        self.client.force_login(self.user)
        payload = {'fullName': 'Mobile Buyer', 'email': self.user.email, 'address': '1 Mobile Road', 'paymentMethod': 'COD'}
        first = api_post(self.client, reverse('api-v2:checkout'), payload)
        second = api_post(self.client, reverse('api-v2:checkout'), payload)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 409)
        self.assertEqual(Order.objects.filter(user=self.user).count(), 1)

    def test_order_detail_prevents_idor(self):
        order = Order.objects.create(user=self.other, full_name='Other', email=self.other.email, address='Private', total_price=100)
        self.client.force_login(self.user)
        response = self.client.get(reverse('api-v2:order-detail', args=(order.pk,)))
        self.assertEqual(response.status_code, 404)
        self.assertNotContains(response, 'Private', status_code=404)

    def test_wishlist_sync_is_idempotent(self):
        self.client.force_login(self.user)
        url = reverse('api-v2:wishlist')
        api_post(self.client, url, {'productId': self.product.pk})
        response = api_post(self.client, url, {'productId': self.product.pk})
        self.assertFalse(response.json()['created'])
        self.assertEqual(Wishlist.objects.filter(user=self.user, product=self.product).count(), 1)


class ApiV2AccountTests(ApiV2Base):
    def test_session_endpoint_issues_csrf_and_unsafe_api_honors_it(self):
        client = Client(enforce_csrf_checks=True)
        session_response = client.get(reverse('api-v2:session'))
        token = session_response.json()['csrfToken']
        denied = api_post(client, reverse('api-v2:session'), {'username': self.user.username, 'password': PASSWORD})
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(denied.json()['error']['code'], 'csrf_failed')
        allowed = client.post(
            reverse('api-v2:session'), data=json.dumps({'username': self.user.username, 'password': PASSWORD}),
            content_type='application/json', HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(allowed.status_code, 200)
        self.assertTrue(allowed.json()['authenticated'])

    def test_profile_allowlist_cannot_escalate_privileges(self):
        self.client.force_login(self.user)
        response = self.client.patch(
            reverse('api-v2:profile'), data=json.dumps({'firstName': 'Mobile', 'is_staff': True}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'Mobile')
        self.assertFalse(self.user.is_staff)

    def test_seller_dashboard_uses_only_authenticated_seller(self):
        SellerProfile.objects.create(
            user=self.user, store_name='Mobile Store', slug='mobile-store', legal_name='Mobile LLC',
            business_email=self.user.email, business_phone='03000000000', verification_status='approved',
        )
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(reverse('api-v2:seller-dashboard')).status_code, 403)
        self.client.force_login(self.user)
        response = self.client.get(reverse('api-v2:seller-dashboard'))
        self.assertEqual(response.json()['seller']['storeName'], 'Mobile Store')

    def test_push_device_identifier_is_hashed_and_owner_scoped(self):
        self.client.force_login(self.user)
        raw_id = 'opaque-device-id-1234567890'
        response = api_post(self.client, reverse('api-v2:push-devices'), {'deviceId': raw_id, 'platform': 'web'})
        device = PushDevice.objects.get(user=self.user)
        self.assertNotEqual(device.device_id_hash, raw_id)
        self.assertFalse(device.notifications_enabled)
        self.client.force_login(self.other)
        self.assertEqual(self.client.delete(reverse('api-v2:push-device-detail', args=(device.pk,))).status_code, 404)
        self.assertTrue(PushDevice.objects.filter(pk=device.pk).exists())


class PwaTests(TestCase):
    def test_manifest_is_installable_and_has_maskable_icon_and_shortcuts(self):
        response = self.client.get(reverse('pwa-manifest'))
        payload = response.json()
        self.assertEqual(response['Content-Type'], 'application/manifest+json')
        self.assertEqual(payload['display'], 'standalone')
        self.assertTrue(any(icon.get('purpose') == 'maskable' for icon in payload['icons']))
        self.assertGreaterEqual(len(payload['shortcuts']), 3)

    def test_service_worker_never_caches_api_or_private_routes(self):
        response = self.client.get(reverse('pwa-service-worker'))
        content = response.content.decode()
        self.assertEqual(response['Service-Worker-Allowed'], '/')
        self.assertIn("'/api/'", content)
        self.assertIn("'/checkout/'", content)
        self.assertIn('networkFirstPage', content)
        self.assertIn('ownbasket-pending-sync', content)
        self.assertIn('flushPendingInWorker', content)
        self.assertIn("fetch('/api/v2/auth/session/'", content)
        self.assertIn("'X-CSRFToken': session.csrfToken", content)
        self.assertIn("response.headers.get('X-PWA-Cacheable') === 'public'", content)
        self.assertNotIn("url.pathname.startsWith('/media/')", content)

    def test_offline_page_is_accessible_and_base_registers_pwa(self):
        offline = self.client.get(reverse('pwa-offline'))
        self.assertContains(offline, 'aria-labelledby="offline-title"')
        home = self.client.get('/home/')
        self.assertContains(home, 'rel="manifest"')
        self.assertContains(home, 'id="pwa-network-status"')
        self.assertContains(home, 'js/pwa.js')
        self.assertEqual(home['X-PWA-Cacheable'], 'public')

    def test_authenticated_home_is_never_opted_into_offline_page_cache(self):
        user = User.objects.create_user('private-pwa-user', password=PASSWORD)
        self.client.force_login(user)
        response = self.client.get('/home/')
        self.assertNotIn('X-PWA-Cacheable', response)
        self.assertIn('no-store', response['Cache-Control'])

    def test_generated_icons_have_declared_dimensions(self):
        expected = {'icon-192.png': (192, 192), 'icon-512.png': (512, 512), 'icon-maskable-512.png': (512, 512), 'apple-touch-icon.png': (180, 180)}
        for name, dimensions in expected.items():
            with Image.open(f'static/images/pwa/{name}') as image:
                self.assertEqual(image.size, dimensions)


class MobileTokenTests(ApiV2Base):
    def token_login(self, device_id='production-device-id-0001'):
        client = Client(enforce_csrf_checks=True)
        response = api_post(client, reverse('api-v2:token-login'), {
            'username': self.user.username, 'password': PASSWORD,
            'deviceId': device_id, 'deviceName': 'Pixel', 'platform': 'android',
        })
        self.assertEqual(response.status_code, 200)
        return client, response.json()

    def test_bearer_login_works_without_csrf_and_access_token_authenticates(self):
        client, tokens = self.token_login()
        self.assertNotIn(tokens['accessToken'], MobileSession.objects.get().access_token_hash)
        response = client.get(reverse('api-v2:profile'), HTTP_AUTHORIZATION=f"Bearer {tokens['accessToken']}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['profile']['id'], self.user.pk)
        self.assertNotIn('sessionid', response.cookies)

    def test_refresh_rotation_detects_replay_and_revokes_device(self):
        client, original = self.token_login()
        rotated = api_post(client, reverse('api-v2:token-refresh'), {'refreshToken': original['refreshToken']})
        self.assertEqual(rotated.status_code, 200)
        second = rotated.json()
        replay = api_post(client, reverse('api-v2:token-refresh'), {'refreshToken': original['refreshToken']})
        self.assertEqual(replay.status_code, 409)
        self.assertEqual(replay.json()['error']['code'], 'refresh_token_reused')
        denied = client.get(reverse('api-v2:profile'), HTTP_AUTHORIZATION=f"Bearer {second['accessToken']}")
        self.assertEqual(denied.status_code, 401)

    def test_multiple_devices_are_independent_and_can_be_remotely_revoked(self):
        client, first = self.token_login('production-device-id-0001')
        _, second = self.token_login('production-device-id-0002')
        self.assertEqual(MobileSession.objects.filter(user=self.user, revoked_at__isnull=True).count(), 2)
        response = client.delete(
            reverse('api-v2:token-session-detail', args=(second['sessionId'],)),
            HTTP_AUTHORIZATION=f"Bearer {first['accessToken']}",
        )
        self.assertEqual(response.status_code, 200)
        denied = client.get(reverse('api-v2:profile'), HTTP_AUTHORIZATION=f"Bearer {second['accessToken']}")
        self.assertEqual(denied.status_code, 401)
        allowed = client.get(reverse('api-v2:profile'), HTTP_AUTHORIZATION=f"Bearer {first['accessToken']}")
        self.assertEqual(allowed.status_code, 200)


class IdempotencyTests(ApiV2Base):
    def setUp(self):
        super().setUp()
        response = api_post(self.client, reverse('api-v2:token-login'), {
            'username': self.user.username, 'password': PASSWORD,
            'deviceId': 'idempotency-device-0001', 'platform': 'android',
        })
        self.access_token = response.json()['accessToken']
        CartItem.objects.create(cart=get_user_cart(self.user), product=self.product, quantity=1)
        self.payload = {'fullName': 'Mobile Buyer', 'email': self.user.email, 'address': '1 Mobile Road', 'paymentMethod': 'COD'}

    def checkout(self, payload=None, key=None):
        headers = {'HTTP_AUTHORIZATION': f'Bearer {self.access_token}'}
        if key:
            headers['HTTP_IDEMPOTENCY_KEY'] = key
        return self.client.post(
            reverse('api-v2:checkout'), data=json.dumps(payload or self.payload),
            content_type='application/json', **headers,
        )

    def test_bearer_checkout_requires_idempotency_key(self):
        response = self.checkout()
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error']['code'], 'idempotency_key_required')
        self.assertFalse(Order.objects.filter(user=self.user).exists())

    def test_completed_checkout_is_replayed_without_duplicate_order(self):
        first = self.checkout(key='checkout-request-0001')
        second = self.checkout(key='checkout-request-0001')
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second['Idempotency-Replayed'], 'true')
        self.assertEqual(first.json()['order']['id'], second.json()['order']['id'])
        self.assertEqual(Order.objects.filter(user=self.user).count(), 1)
        self.assertEqual(IdempotencyRecord.objects.get().status, 'completed')

    def test_reused_key_with_different_request_returns_conflict(self):
        self.assertEqual(self.checkout(key='checkout-request-0002').status_code, 200)
        changed = {**self.payload, 'address': 'A different address'}
        response = self.checkout(changed, key='checkout-request-0002')
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()['error']['code'], 'idempotency_conflict')


class PushLifecycleTests(ApiV2Base):
    def test_provider_token_is_encrypted_refreshable_and_unregisterable(self):
        self.client.force_login(self.user)
        token = 'fcm-provider-token-value-0000001'
        created = api_post(self.client, reverse('api-v2:push-devices'), {
            'deviceId': 'push-device-identifier-0001', 'platform': 'android',
            'provider': 'fcm', 'pushToken': token, 'appVersion': '2.0.0',
        })
        self.assertEqual(created.status_code, 200)
        device = PushDevice.objects.get(user=self.user)
        self.assertNotIn(token, device.provider_token_encrypted)
        self.assertEqual(decrypt_provider_token(device.provider_token_encrypted), token)
        replacement = 'fcm-provider-token-value-0000002'
        updated = self.client.patch(
            reverse('api-v2:push-device-detail', args=(device.pk,)),
            data=json.dumps({'pushToken': replacement}), content_type='application/json',
        )
        self.assertEqual(updated.status_code, 200)
        device.refresh_from_db()
        self.assertEqual(decrypt_provider_token(device.provider_token_encrypted), replacement)
        self.assertEqual(self.client.delete(reverse('api-v2:push-device-detail', args=(device.pk,))).status_code, 200)
        self.assertFalse(PushDevice.objects.filter(pk=device.pk).exists())

    def test_delivery_status_and_provider_adapter_lifecycle(self):
        device = PushDevice.objects.create(
            user=self.user, device_id_hash='a' * 64, platform='android', provider='fcm',
            provider_token_hash='b' * 64, provider_token_encrypted='invalid-placeholder', notifications_enabled=True,
        )
        from .crypto import encrypt_provider_token
        device.provider_token_encrypted = encrypt_provider_token('real-provider-token-0001')
        device.save(update_fields=('provider_token_encrypted',))
        delivery, created = queue_push(device, event_key='order-1-shipped', title='Shipped', body='Your order shipped')
        self.assertTrue(created)
        PROVIDER_ADAPTERS['fcm'] = lambda **kwargs: 'provider-message-1'
        try:
            deliver_push(delivery.pk)
        finally:
            PROVIDER_ADAPTERS.pop('fcm', None)
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, PushDelivery.Status.DELIVERED)
        self.assertEqual(delivery.provider_message_id, 'provider-message-1')


class BackgroundSyncTests(ApiV2Base):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.user)

    def batch(self, action_id, operation='wishlist:add', payload=None, base_version=0):
        return api_post(self.client, reverse('api-v2:sync-batch'), {
            'baseVersion': base_version,
            'actions': [{'clientActionId': action_id, 'operation': operation, 'payload': payload or {'productId': self.product.pk}}],
        })

    def test_sync_applies_once_and_replays_client_action(self):
        first = self.batch('sync-action-0001')
        second = self.batch('sync-action-0001')
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json()['results'][0]['status'], 'applied')
        self.assertTrue(second.json()['results'][0]['duplicate'])
        self.assertEqual(Wishlist.objects.filter(user=self.user, product=self.product).count(), 1)
        self.assertEqual(SyncOperation.objects.count(), 1)

    def test_stale_base_version_returns_action_conflict(self):
        self.assertEqual(self.batch('sync-action-0002').status_code, 200)
        response = self.batch('sync-action-0003', operation='wishlist:remove', base_version=0)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['results'][0]['status'], 'conflict')
        self.assertEqual(response.json()['results'][0]['serverVersion'], 1)

    def test_action_id_reuse_with_changed_payload_is_rejected(self):
        self.assertEqual(self.batch('sync-action-0004').status_code, 200)
        other = Product.objects.create(name='Other', category=self.category, brand=self.brand, price=10, stock=1)
        response = self.batch('sync-action-0004', payload={'productId': other.pk}, base_version=1)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()['error']['code'], 'sync_action_conflict')

    def test_sync_rejects_sensitive_or_unknown_payload_fields(self):
        response = self.batch('sync-action-0005', payload={'productId': self.product.pk, 'accessToken': 'must-not-store'})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error']['code'], 'unsafe_sync_payload')
        self.assertFalse(SyncOperation.objects.exists())

    def test_missing_owned_object_is_a_terminal_action_result_not_a_partial_batch_error(self):
        response = self.batch(
            'sync-action-0006', operation='cart:update', payload={'itemId': 999999, 'quantity': 2},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['results'][0]['status'], 'failed')
        self.assertEqual(response.json()['results'][0]['code'], 'not_found')


class ApiContractAndObservabilityTests(ApiV2Base):
    def test_openapi_is_generated_from_routes_and_documents_security_errors_and_examples(self):
        response = self.client.get(reverse('api-v2:openapi'))
        self.assertEqual(response.status_code, 200)
        spec = response.json()
        self.assertEqual(spec['openapi'], '3.0.3')
        self.assertIn('/api/v2/checkout/', spec['paths'])
        checkout = spec['paths']['/api/v2/checkout/']['post']
        self.assertIn('bearerAuth', spec['components']['securitySchemes'])
        self.assertIn('example', checkout['requestBody']['content']['application/json'])
        self.assertIn('409', checkout['responses'])
        self.assertIn('/api/v2/auth/token/refresh/', spec['paths'])

    def test_swagger_and_redoc_render_the_live_contract(self):
        self.assertContains(self.client.get(reverse('api-v2:swagger')), reverse('api-v2:openapi'))
        self.assertContains(self.client.get(reverse('api-v2:redoc')), reverse('api-v2:openapi'))

    def test_health_request_ids_timing_and_staff_metrics(self):
        correlation_id = '550e8400-e29b-41d4-a716-446655440000'
        health = self.client.get(reverse('api-v2:health'), HTTP_X_REQUEST_ID=correlation_id)
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json()['status'], 'ok')
        self.assertEqual(health['X-Request-ID'], correlation_id)
        self.assertIn('Server-Timing', health)
        self.user.is_staff = True
        self.user.save(update_fields=('is_staff',))
        self.client.force_login(self.user)
        metrics = self.client.get(reverse('api-v2:metrics'))
        self.assertEqual(metrics.status_code, 200)
        self.assertGreaterEqual(metrics.json()['requestsTotal'], 1)
