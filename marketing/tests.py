from datetime import timedelta
from decimal import Decimal
from io import StringIO
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core import mail
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from cart.models import Cart, CartItem
from orders.models import Order
from products.models import Brand, Category, Product
from wishlist.models import Wishlist

from .models import (
    Campaign, CampaignDelivery, EngagementDelivery, LoyaltyAccount, LoyaltyTransaction,
    NewsletterSubscription, NotificationPreference, Referral, ReferralCode, StockAlert,
)
from .services.email_service import recipient_hash
from .services.reminders import abandoned_cart_candidates, send_abandoned_cart_reminder, send_wishlist_reminder
from .services.segments import recipient_count
from .services.tokens import make_subscription_token


User = get_user_model()
TINY_GIF = b'GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;'


class MarketingBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('customer', email='customer@example.com', password='customer-pass-123')
        self.category = Category.objects.create(name='Engagement', slug='engagement')
        self.brand = Brand.objects.create(name='Engagement Brand')
        self.product = Product.objects.create(
            name='Engagement Product', category=self.category, brand=self.brand,
            price=Decimal('100.00'), stock=5, description='Real product',
            image=SimpleUploadedFile('product.gif', TINY_GIF, content_type='image/gif'),
        )


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class NewsletterTests(MarketingBase):
    def subscribe(self, email='guest@example.com'):
        return self.client.post(reverse('marketing:newsletter_subscribe'), {
            'email': email, 'consent': 'on', 'source': 'footer', 'next': reverse('home'), 'website': '',
        })

    def test_valid_subscribe_is_pending_and_sends_confirmation(self):
        response = self.subscribe()
        subscription = NewsletterSubscription.objects.get(email='guest@example.com')
        self.assertRedirects(response, reverse('home'))
        self.assertEqual(subscription.status, NewsletterSubscription.Status.PENDING)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Confirm', mail.outbox[0].subject)

    def test_duplicate_subscription_does_not_create_duplicate_row(self):
        self.subscribe()
        self.subscribe()
        self.assertEqual(NewsletterSubscription.objects.filter(email='guest@example.com').count(), 1)

    def test_duplicate_active_subscription_is_not_downgraded(self):
        subscription = NewsletterSubscription.objects.create(
            email='guest@example.com', status=NewsletterSubscription.Status.ACTIVE,
            subscribed_at=timezone.now(),
        )
        self.subscribe()
        subscription.refresh_from_db()
        self.assertEqual(subscription.status, NewsletterSubscription.Status.ACTIVE)

    def test_invalid_email_or_missing_consent_is_rejected(self):
        self.client.post(reverse('marketing:newsletter_subscribe'), {'email': 'invalid', 'website': ''})
        self.assertFalse(NewsletterSubscription.objects.exists())

    def test_confirm_unsubscribe_and_resubscribe_flow(self):
        self.subscribe()
        subscription = NewsletterSubscription.objects.get()
        token = make_subscription_token(subscription)
        self.client.get(reverse('marketing:newsletter_confirm', args=(token,)))
        subscription.refresh_from_db()
        self.assertEqual(subscription.status, NewsletterSubscription.Status.ACTIVE)
        self.client.get(reverse('marketing:newsletter_unsubscribe', args=(token,)))
        subscription.refresh_from_db()
        self.assertEqual(subscription.status, NewsletterSubscription.Status.ACTIVE)
        self.client.post(reverse('marketing:newsletter_unsubscribe', args=(token,)))
        subscription.refresh_from_db()
        self.assertEqual(subscription.status, NewsletterSubscription.Status.UNSUBSCRIBED)
        self.subscribe()
        subscription.refresh_from_db()
        self.assertEqual(subscription.status, NewsletterSubscription.Status.PENDING)

    def test_invalid_unsubscribe_token_is_not_accepted(self):
        self.assertEqual(self.client.get(reverse('marketing:newsletter_unsubscribe', args=('bad-token',))).status_code, 404)


class ConsentAndDashboardTests(MarketingBase):
    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_registration_consent_is_optional_and_records_source_when_selected(self):
        response = self.client.post(reverse('register'), {
            'username': 'consented-user', 'email': 'consented@example.com',
            'password1': 'Strong-pass-123!', 'password2': 'Strong-pass-123!',
            'marketing_consent': 'on',
        })
        registered = User.objects.get(username='consented-user')
        self.assertRedirects(response, reverse('login'))
        self.assertTrue(registered.notification_preferences.marketing_consent)
        self.assertEqual(registered.notification_preferences.consent_source, 'registration')
        self.assertEqual(len(mail.outbox), 1)

    def test_preferences_record_and_withdraw_marketing_consent(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse('marketing:preferences'), {
            'order_updates': 'on', 'delivery_updates': 'on', 'promotional_emails': 'on',
            'wishlist_reminders': 'on', 'marketing_consent': 'on',
        })
        preference = self.user.notification_preferences
        preference.refresh_from_db()
        self.assertRedirects(response, reverse('marketing:preferences'))
        self.assertTrue(preference.marketing_consent)
        self.assertEqual(preference.consent_source, 'account_settings')
        self.client.post(reverse('marketing:preferences'), {'order_updates': 'on', 'delivery_updates': 'on'})
        preference.refresh_from_db()
        self.assertFalse(preference.marketing_consent)
        self.assertFalse(preference.promotional_emails)
        self.assertIsNotNone(preference.consent_withdrawn_at)

    def test_customer_engagement_dashboard_uses_real_foundations(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('marketing:engagement_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.user.referral_code.code)
        self.assertContains(response, '0 points')


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend', ABANDONED_CART_MIN_HOURS=24)
class ReminderTests(MarketingBase):
    def enable(self):
        preference = self.user.notification_preferences
        preference.marketing_consent = True
        preference.abandoned_cart_reminders = True
        preference.wishlist_reminders = True
        preference.back_in_stock_alerts = True
        preference.save()

    def test_abandoned_cart_eligibility_and_duplicate_frequency_prevention(self):
        self.enable()
        cart = Cart.objects.create(id=self.user.id, user=self.user)
        CartItem.objects.create(cart=cart, product=self.product)
        Cart.objects.filter(pk=cart.pk).update(updated_at=timezone.now() - timedelta(hours=25))
        self.assertEqual(list(abandoned_cart_candidates()), [cart])
        self.assertTrue(send_abandoned_cart_reminder(cart, 'https://shop.example.com'))
        self.assertFalse(abandoned_cart_candidates().filter(pk=cart.pk).exists())

    def test_empty_and_completed_carts_are_excluded(self):
        self.enable()
        empty = Cart.objects.create(user=self.user)
        Cart.objects.filter(pk=empty.pk).update(updated_at=timezone.now() - timedelta(hours=25))
        self.assertFalse(abandoned_cart_candidates().filter(pk=empty.pk).exists())
        CartItem.objects.create(cart=empty, product=self.product)
        empty.is_active = False
        empty.save(update_fields=('is_active',))
        self.assertFalse(abandoned_cart_candidates().filter(pk=empty.pk).exists())

    def test_wishlist_reminder_uses_real_items_and_prevents_fast_duplicate(self):
        self.enable()
        Wishlist.objects.create(user=self.user, product=self.product)
        self.assertTrue(send_wishlist_reminder(self.user, 'https://shop.example.com'))
        self.assertFalse(send_wishlist_reminder(self.user, 'https://shop.example.com'))
        self.assertEqual(EngagementDelivery.objects.filter(kind=EngagementDelivery.Kind.WISHLIST).count(), 1)

    def test_stock_alert_processes_real_inventory_once(self):
        self.enable()
        alert = StockAlert.objects.create(user=self.user, product=self.product, email=self.user.email)
        call_command('process_stock_alerts', limit=10)
        alert.refresh_from_db()
        self.assertFalse(alert.is_active)
        self.assertIsNotNone(alert.notified_at)

    def test_stock_alert_subscription_requires_and_uses_user_preference(self):
        self.product.stock = 0
        self.product.save()
        self.client.force_login(self.user)
        response = self.client.post(reverse('marketing:stock_alert_subscribe', args=(self.product.pk,)))
        self.assertFalse(StockAlert.objects.exists())
        self.enable()
        response = self.client.post(reverse('marketing:stock_alert_subscribe', args=(self.product.pk,)))
        self.assertRedirects(response, self.product.get_absolute_url())
        self.assertTrue(StockAlert.objects.filter(user=self.user, product=self.product, is_active=True).exists())

    def test_failed_stock_alert_batch_exits_with_an_error(self):
        self.enable()
        StockAlert.objects.create(user=self.user, product=self.product, email=self.user.email)
        target = 'marketing.management.commands.process_stock_alerts.send_stock_alert'
        with mock.patch(target, side_effect=RuntimeError('smtp down')):
            with self.assertRaises(CommandError):
                call_command('process_stock_alerts', limit=10, stderr=StringIO())

    def test_dry_run_does_not_mutate_abandoned_cart(self):
        self.enable()
        cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=cart, product=self.product)
        Cart.objects.filter(pk=cart.pk).update(updated_at=timezone.now() - timedelta(hours=25))
        call_command('process_abandoned_carts', dry_run=True, limit=10)
        cart.refresh_from_db()
        self.assertEqual(cart.reminder_count, 0)


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class CampaignAndSegmentationTests(MarketingBase):
    def setUp(self):
        super().setUp()
        preference = self.user.notification_preferences
        preference.marketing_consent = True
        preference.promotional_emails = True
        preference.save()
        self.staff = User.objects.create_user('marketer', email='marketer@example.com', password='staff-pass-123', is_staff=True)
        self.campaign = Campaign.objects.create(
            name='Real campaign', subject='A safe campaign', content='<script>alert(1)</script>',
            target_segment=Campaign.Segment.OPTED_IN, created_by=self.staff,
        )

    def test_dynamic_segment_count_uses_opted_in_users(self):
        self.assertEqual(recipient_count(Campaign.Segment.OPTED_IN), 1)

    def test_marketing_manager_group_is_least_privilege(self):
        group = Group.objects.get(name='Marketing Manager')
        codenames = set(group.permissions.values_list('codename', flat=True))
        self.assertIn('add_campaign', codenames)
        self.assertIn('send_test_campaign', codenames)
        self.assertNotIn('change_user', codenames)
        self.assertNotIn('change_sellerpayout', codenames)

    def test_campaign_admin_requires_permission_for_test_email(self):
        self.client.force_login(self.staff)
        url = reverse('admin:marketing_campaign_test_email', args=(self.campaign.pk,))
        self.assertEqual(self.client.post(url).status_code, 403)
        permission = Permission.objects.get(codename='send_test_campaign')
        self.staff.user_permissions.add(permission)
        self.assertEqual(self.client.post(url).status_code, 302)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.staff.email])

    def test_scheduled_campaign_command_sends_and_deduplicates(self):
        self.campaign.status = Campaign.Status.SCHEDULED
        self.campaign.scheduled_at = timezone.now() - timedelta(minutes=1)
        self.campaign.save()
        call_command('send_scheduled_campaigns', limit=10)
        self.campaign.refresh_from_db()
        self.assertEqual(self.campaign.sent_count, 1)
        self.assertEqual(CampaignDelivery.objects.count(), 1)
        call_command('send_scheduled_campaigns', limit=10)
        self.assertEqual(CampaignDelivery.objects.count(), 1)
        self.assertNotIn('<script>', mail.outbox[0].alternatives[0].content)
        self.assertIn('Unsubscribe from marketing email', mail.outbox[0].alternatives[0].content)


class ReferralAndLoyaltyTests(MarketingBase):
    def test_self_referral_and_duplicate_referred_user_are_blocked(self):
        code = self.user.referral_code
        self_referral = Referral(referral_code=code, referred_user=self.user)
        with self.assertRaises(ValidationError):
            self_referral.full_clean()
        other = User.objects.create_user('other', email='other@example.com')
        Referral.objects.create(referral_code=code, referred_user=other)
        duplicate = Referral(referral_code=code, referred_user=other)
        with self.assertRaises(ValidationError):
            duplicate.full_clean()

    def test_loyalty_balance_is_ledger_derived_and_cannot_go_negative(self):
        account = self.user.loyalty_account
        LoyaltyTransaction.objects.create(account=account, transaction_type='adjustment', points=100)
        LoyaltyTransaction.objects.create(account=account, transaction_type='redeem', points=-40)
        self.assertEqual(account.balance, 60)
        with self.assertRaises(ValidationError):
            LoyaltyTransaction.objects.create(account=account, transaction_type='redeem', points=-61)


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class TransactionalCompatibilityTests(MarketingBase):
    def test_checkout_marks_cart_completed_and_optional_consent_is_not_required(self):
        cart = Cart.objects.create(id=self.user.id, user=self.user)
        CartItem.objects.create(cart=cart, product=self.product, quantity=1)
        self.client.force_login(self.user)
        response = self.client.post(reverse('checkout'), {
            'full_name': 'Customer', 'email': self.user.email, 'address': '1 Test Road',
            'payment_method': 'COD',
        })
        cart.refresh_from_db()
        preference = self.user.notification_preferences
        preference.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertFalse(cart.is_active)
        self.assertFalse(preference.marketing_consent)
        self.assertTrue(EngagementDelivery.objects.filter(kind=EngagementDelivery.Kind.TRANSACTIONAL).exists())

    def test_transactional_order_status_email_ignores_marketing_opt_out(self):
        preference = self.user.notification_preferences
        preference.marketing_consent = False
        preference.order_updates = True
        preference.save()
        order = Order.objects.create(user=self.user, full_name='Customer', email=self.user.email, address='Address', total_price=Decimal('100'))
        order.status = 'Shipped'
        order.save()
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Shipped', mail.outbox[0].subject)

    def test_admin_dashboard_renders_real_marketing_cards(self):
        admin = User.objects.create_superuser('admin', 'admin@example.com', 'admin-pass-123')
        self.client.force_login(admin)
        response = self.client.get(reverse('admin:index'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Active Subscribers')
        self.assertContains(response, 'Unsubscribed')
        self.assertContains(response, 'Referral Signups')
