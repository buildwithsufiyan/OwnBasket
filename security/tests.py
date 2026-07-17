from io import BytesIO

from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth.models import Permission
from django.contrib.sessions.models import Session
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.utils import timezone
from PIL import Image
from marketplace.models import SellerProfile
from orders.models import Order
from themes.models import Theme

from .models import AuditEvent, PolicyAcceptance, PolicyVersion, PrivacyRequest, UserSession
from .services import audit, session_hash
from .uploads import validate_document_upload, validate_image_upload


User = get_user_model()
OLD_PASSWORD = 'Original-Strong-Pass-123!'
NEW_PASSWORD = 'Different-Strong-Pass-456!'


def image_upload(name='safe.png', content_type='image/png'):
    stream = BytesIO()
    Image.new('RGB', (2, 2), 'white').save(stream, format='PNG')
    return SimpleUploadedFile(name, stream.getvalue(), content_type=content_type)


class AuthenticationAuditTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('security-user', 'security@example.com', OLD_PASSWORD)

    def test_login_success_is_audited_and_session_tracked(self):
        response = self.client.post(reverse('login'), {'username': self.user.username, 'password': OLD_PASSWORD})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(AuditEvent.objects.filter(user=self.user, action='login', success=True).exists())
        self.assertEqual(UserSession.objects.filter(user=self.user, ended_at__isnull=True).count(), 1)

    def test_login_failure_is_audited_without_plain_username(self):
        self.client.post(reverse('login'), {'username': self.user.username, 'password': 'wrong-password'})
        event = AuditEvent.objects.get(action='login_failed')
        self.assertEqual(event.user, self.user)
        self.assertNotIn(self.user.username, str(event.metadata))

    def test_logout_is_post_only_and_audited(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse('logout')).status_code, 405)
        self.client.post(reverse('logout'))
        self.assertTrue(AuditEvent.objects.filter(user=self.user, action='logout').exists())

    def test_password_change_is_audited_and_keeps_current_session(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse('account_change_password'), {
            'old_password': OLD_PASSWORD, 'new_password1': NEW_PASSWORD, 'new_password2': NEW_PASSWORD,
        })
        self.assertRedirects(response, reverse('account_settings'))
        self.assertIn('_auth_user_id', self.client.session)
        self.assertTrue(AuditEvent.objects.filter(user=self.user, action='password_changed').exists())

    def test_recent_password_reuse_is_rejected(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse('account_change_password'), {
            'old_password': OLD_PASSWORD, 'new_password1': OLD_PASSWORD, 'new_password2': OLD_PASSWORD,
        })
        self.assertContains(response, 'not used recently')

    def test_audit_metadata_redacts_sensitive_key_variants(self):
        event = audit('redaction_test', metadata={
            'access_token': 'hidden', 'otp_code': '123456', 'card_number': '4111', 'safe': 'visible',
        })
        self.assertEqual(event.metadata, {'safe': 'visible'})

    def test_password_reset_completion_is_audited(self):
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = default_token_generator.make_token(self.user)
        response = self.client.get(reverse('password_reset_confirm', args=(uid, token)))
        response = self.client.post(response.url, {
            'new_password1': NEW_PASSWORD, 'new_password2': NEW_PASSWORD,
        })
        self.assertRedirects(response, reverse('password_reset_complete'))
        self.assertTrue(AuditEvent.objects.filter(user=self.user, action='password_reset_completed').exists())

    def test_order_audit_target_does_not_store_customer_name(self):
        order = Order.objects.create(
            user=self.user, full_name='Sensitive Customer Name', email=self.user.email,
            address='Private address', total_price='10.00',
        )
        event = AuditEvent.objects.filter(object_model='order', object_id=str(order.pk)).latest('id')
        self.assertEqual(event.object_repr, '')


class SessionSecurityTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('session-user', password=OLD_PASSWORD)
        self.other = User.objects.create_user('other-user', password=OLD_PASSWORD)

    def test_security_center_only_shows_own_history(self):
        own = AuditEvent.objects.create(user=self.user, category=AuditEvent.Category.AUTH, action='own_login')
        other = AuditEvent.objects.create(user=self.other, category=AuditEvent.Category.AUTH, action='other_login')
        self.client.force_login(self.user)
        response = self.client.get(reverse('security:center'))
        self.assertContains(response, own.action)
        self.assertNotContains(response, other.action)

    def test_session_keys_are_not_rendered(self):
        self.client.force_login(self.user)
        raw_key = self.client.session.session_key
        response = self.client.get(reverse('security:center'))
        self.assertNotContains(response, raw_key)

    def test_logout_other_sessions_preserves_current_and_revokes_other(self):
        current = Client(); other = Client()
        self.assertTrue(current.login(username=self.user.username, password=OLD_PASSWORD))
        self.assertTrue(other.login(username=self.user.username, password=OLD_PASSWORD))
        current_key = current.session.session_key
        other_key = other.session.session_key
        current.post(reverse('security:logout_other_sessions'))
        self.assertTrue(Session.objects.filter(session_key=current_key).exists())
        self.assertFalse(Session.objects.filter(session_key=other_key).exists())

    def test_individual_session_revocation_is_owner_scoped(self):
        self.client.force_login(self.user)
        foreign = UserSession.objects.create(user=self.other, session_key_hash='f' * 64)
        response = self.client.post(reverse('security:revoke_session', args=(foreign.pk,)))
        self.assertEqual(response.status_code, 404)
        self.assertIsNone(UserSession.objects.get(pk=foreign.pk).ended_at)

    def test_current_session_cannot_be_revoked_by_device_action(self):
        self.client.force_login(self.user)
        raw_key = self.client.session.session_key
        tracked = UserSession.objects.get(user=self.user, session_key_hash=session_hash(raw_key))
        self.client.post(reverse('security:revoke_session', args=(tracked.pk,)))
        self.assertTrue(Session.objects.filter(session_key=raw_key).exists())
        tracked.refresh_from_db()
        self.assertIsNone(tracked.ended_at)


class UploadSecurityTests(TestCase):
    def test_disallowed_image_extension_is_rejected(self):
        with self.assertRaises(ValidationError):
            validate_image_upload(image_upload('payload.exe'))

    def test_declared_image_mime_mismatch_is_rejected(self):
        with self.assertRaises(ValidationError):
            validate_image_upload(image_upload(content_type='application/javascript'))

    def test_actual_image_format_must_match_extension_and_mime(self):
        with self.assertRaises(ValidationError):
            validate_image_upload(image_upload(name='renamed.jpg', content_type='image/jpeg'))

    def test_fake_image_content_is_rejected(self):
        upload = SimpleUploadedFile('fake.png', b'not an image', content_type='image/png')
        with self.assertRaises(ValidationError):
            validate_image_upload(upload)

    def test_oversized_upload_is_rejected(self):
        upload = SimpleUploadedFile('large.png', b'x' * (5 * 1024 * 1024 + 1), content_type='image/png')
        with self.assertRaises(ValidationError):
            validate_image_upload(upload)

    def test_fake_pdf_signature_is_rejected(self):
        upload = SimpleUploadedFile('document.pdf', b'not-pdf', content_type='application/pdf')
        with self.assertRaises(ValidationError):
            validate_document_upload(upload)


class ComplianceAndPermissionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('privacy-user', password=OLD_PASSWORD)

    def test_data_export_request_is_created_pending(self):
        self.client.force_login(self.user)
        self.client.post(reverse('security:privacy_requests'), {'request_type': 'export', 'notes': ''})
        self.assertTrue(PrivacyRequest.objects.filter(user=self.user, request_type='export', status='pending').exists())

    def test_data_deletion_request_is_non_destructive(self):
        self.client.force_login(self.user)
        self.client.post(reverse('security:privacy_requests'), {'request_type': 'deletion', 'notes': ''})
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())
        self.assertTrue(PrivacyRequest.objects.filter(user=self.user, request_type='deletion', status='pending').exists())

    def test_privacy_request_page_is_user_isolated(self):
        other = User.objects.create_user('privacy-other', password=OLD_PASSWORD)
        PrivacyRequest.objects.create(user=other, request_type='correction', notes='private marker')
        self.client.force_login(self.user)
        self.assertNotContains(self.client.get(reverse('security:privacy_requests')), 'private marker')

    def test_policy_acceptance_records_version_and_user(self):
        policy = PolicyVersion.objects.create(
            policy_type='privacy', version='2026-01', published_at=timezone.now(), content_hash='a' * 64,
        )
        acceptance = PolicyAcceptance.objects.create(user=self.user, policy=policy, ip_address='127.0.0.1')
        self.assertEqual(acceptance.policy.version, '2026-01')

    def test_security_dashboard_denies_staff_without_permission(self):
        self.user.is_staff = True; self.user.save(update_fields=('is_staff',))
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse('security-dashboard')).status_code, 403)

    def test_security_dashboard_allows_explicit_permission(self):
        self.user.is_staff = True; self.user.save(update_fields=('is_staff',))
        self.user.user_permissions.add(Permission.objects.get(codename='view_security_dashboard'))
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse('security-dashboard')).status_code, 200)

    def test_privacy_workflow_requires_dedicated_processing_permission(self):
        privacy_request = PrivacyRequest.objects.create(user=self.user, request_type='export')
        self.user.is_staff = True; self.user.save(update_fields=('is_staff',))
        self.user.user_permissions.add(
            Permission.objects.get(codename='view_privacyrequest'),
            Permission.objects.get(codename='change_privacyrequest'),
        )
        self.client.force_login(self.user)
        url = reverse('admin:security_privacyrequest_change', args=(privacy_request.pk,))
        self.assertEqual(self.client.post(url, {'status': 'completed', 'notes': ''}).status_code, 403)
        privacy_request.refresh_from_db()
        self.assertEqual(privacy_request.status, PrivacyRequest.Status.PENDING)
        self.user.user_permissions.add(Permission.objects.get(codename='process_privacy_requests'))
        self.assertEqual(self.client.post(url, {'status': 'completed', 'notes': ''}).status_code, 302)
        privacy_request.refresh_from_db()
        self.assertEqual(privacy_request.status, PrivacyRequest.Status.COMPLETED)
        self.assertIsNotNone(privacy_request.completed_at)

    def test_theme_state_changes_are_post_only_and_permission_gated(self):
        theme = Theme.objects.create(name='Security theme', slug='security-theme', theme_folder='default')
        self.user.is_staff = True; self.user.save(update_fields=('is_staff',))
        self.client.force_login(self.user)
        url = reverse('themes:apply_theme', args=(theme.pk,))
        self.assertEqual(self.client.post(url).status_code, 403)
        self.user.user_permissions.add(Permission.objects.get(codename='change_theme'))
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertEqual(self.client.post(url).status_code, 302)

    def test_seller_login_honors_account_lock_state(self):
        SellerProfile.objects.create(
            user=self.user, store_name='Locked seller', slug='locked-seller', legal_name='Locked LLC',
            business_email='locked@example.com', business_phone='03000000000',
        )
        for _ in range(5):
            self.client.post(reverse('login'), {'username': self.user.username, 'password': 'wrong'})
        response = self.client.post(reverse('marketplace:login'), {
            'username': self.user.username, 'password': OLD_PASSWORD,
        })
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_audit_log_cannot_be_changed_in_admin(self):
        self.user.is_staff = True; self.user.save(update_fields=('is_staff',))
        self.user.user_permissions.add(Permission.objects.get(codename='view_auditevent'))
        event = AuditEvent.objects.create(category=AuditEvent.Category.SECURITY, action='immutable')
        self.client.force_login(self.user)
        url = reverse('admin:security_auditevent_change', args=(event.pk,))
        self.assertEqual(self.client.get(url).status_code, 200)
        response = self.client.post(url, {'action': 'tampered'})
        self.assertIn(response.status_code, (302, 403))
        event.refresh_from_db()
        self.assertEqual(event.action, 'immutable')

    def test_two_factor_preference_does_not_mark_2fa_verified(self):
        self.user.email = 'privacy@example.com'; self.user.save(update_fields=('email',))
        self.client.force_login(self.user)
        self.client.post(reverse('security:two_factor_opt_in'), {'password': OLD_PASSWORD})
        self.user.two_factor_profile.refresh_from_db()
        self.assertTrue(self.user.two_factor_profile.opted_in)
        self.assertIsNone(self.user.two_factor_profile.verified_at)


class RateLimitTests(TestCase):
    @override_settings(RATE_LIMIT_ENABLED=True)
    def test_login_rate_limit_returns_429(self):
        cache.clear()
        for _ in range(10):
            self.client.post(reverse('login'), {'username': 'unknown', 'password': 'wrong'})
        response = self.client.post(reverse('login'), {'username': 'unknown', 'password': 'wrong'})
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response['Retry-After'], '300')

    def test_search_api_rejects_non_get_methods(self):
        self.assertEqual(self.client.post(reverse('products:search_suggestions_api')).status_code, 405)
