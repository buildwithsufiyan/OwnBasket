from decimal import Decimal

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from orders.models import Order
from themes.models import Theme
from wishlist.models import Wishlist


class AccountDashboardTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('member', password='old-password-123', email='old@example.com')
        theme = Theme.objects.create(name='Account test', slug='account-test', description='', is_active=True, theme_folder='default')
        cache.set('active_theme', theme)
        cache.set('default_theme', theme)

    def tearDown(self):
        cache.clear()

    def test_dashboard_requires_login(self):
        response = self.client.get(reverse('account_dashboard'))
        self.assertRedirects(response, f"{reverse('login')}?next={reverse('account_dashboard')}")

    def test_dashboard_uses_real_order_count(self):
        Order.objects.create(user=self.user, full_name='Member', email='old@example.com', address='Test address', total_price=Decimal('25.00'))
        self.client.force_login(self.user)
        response = self.client.get(reverse('account_dashboard'))
        self.assertEqual(response.context['order_count'], 1)
        self.assertEqual(response.context['wishlist_count'], Wishlist.objects.filter(user=self.user).count())

    def test_profile_update_changes_existing_user(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse('account_profile'), {'first_name':'Own','last_name':'Basket','email':'new@example.com'})
        self.assertRedirects(response, reverse('account_profile'))
        self.user.refresh_from_db()
        self.assertEqual(self.user.get_full_name(), 'Own Basket')
        self.assertEqual(self.user.email, 'new@example.com')

    def test_password_change_preserves_session(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse('account_change_password'), {'old_password':'old-password-123','new_password1':'New-password-456!','new_password2':'New-password-456!'})
        self.assertRedirects(response, reverse('account_settings'))
        self.assertIn('_auth_user_id', self.client.session)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('New-password-456!'))

# Create your tests here.
