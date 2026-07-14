from decimal import Decimal

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from products.models import Brand, Category, Product
from themes.models import Theme
from cart.models import Cart, CartItem
from .models import Order


class CheckoutTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('checkout-user', password='test-pass', email='buyer@example.com')
        category = Category.objects.create(name='Checkout category', slug='checkout-category')
        brand = Brand.objects.create(name='Checkout brand')
        self.product = Product.objects.create(name='Checkout product', slug='checkout-product', category=category, brand=brand, price=Decimal('100.00'), short_description='', description='', warranty='', return_policy='')
        theme = Theme.objects.create(name='Test theme', slug='test-theme', description='', is_active=True, theme_folder='default')
        cache.set('active_theme', theme)
        cache.set('default_theme', theme)

    def tearDown(self):
        cache.clear()

    def add_cart_item(self):
        cart, _ = Cart.objects.get_or_create(id=self.user.id)
        CartItem.objects.create(cart=cart, product=self.product, quantity=1)

    def test_checkout_requires_login(self):
        response = self.client.get(reverse('checkout'))
        self.assertRedirects(response, f"{reverse('login')}?next={reverse('checkout')}")

    def test_checkout_shows_only_supported_payment_method(self):
        self.client.force_login(self.user)
        self.add_cart_item()
        response = self.client.get(reverse('checkout'))
        self.assertContains(response, 'Cash on Delivery')
        self.assertNotContains(response, 'UPI / QR Code')

    def test_order_redirects_to_owned_success_page_and_clears_cart(self):
        self.client.force_login(self.user)
        self.add_cart_item()
        response = self.client.post(reverse('checkout'), {'full_name':'Checkout Buyer','email':'buyer@example.com','address':'1 Main Street, Test City 123456','payment_method':'COD'})
        order = Order.objects.get(user=self.user)
        self.assertRedirects(response, reverse('order_success', args=[order.id]))
        self.assertFalse(CartItem.objects.filter(cart_id=self.user.id).exists())

    def test_success_page_cannot_show_another_users_order(self):
        other = User.objects.create_user('other-user', password='test-pass')
        order = Order.objects.create(user=other, full_name='Other', email='other@example.com', address='Elsewhere', total_price=Decimal('10.00'))
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse('order_success', args=[order.id])).status_code, 404)

    def test_order_detail_and_invoice_cannot_show_another_users_order(self):
        other = User.objects.create_user('invoice-owner', password='test-pass')
        order = Order.objects.create(user=other, full_name='Other', email='other@example.com', address='Elsewhere', total_price=Decimal('10.00'))
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse('order_detail', args=[order.id])).status_code, 404)
        self.assertEqual(self.client.get(reverse('invoice_pdf', args=[order.id])).status_code, 404)
