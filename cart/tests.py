from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from products.models import Brand, Category, Product
from .models import Cart, CartItem


class CartAuthRestrictionTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='tester', password='secret123')
        self.category = Category.objects.create(name='Test Category', slug='test-category')
        self.brand = Brand.objects.create(name='Test Brand')
        self.product = Product.objects.create(
            name='Test Product',
            slug='test-product',
            price=199,
            category=self.category,
            brand=self.brand,
            description='Test description',
            image=SimpleUploadedFile('product.jpg', b'fake-bytes', content_type='image/jpeg'),
        )

    def test_anonymous_user_cannot_access_cart_page(self):
        response = self.client.get(reverse('cart_detail'))
        self.assertRedirects(response, f"{reverse('login')}?next={reverse('cart_detail')}")

    def test_anonymous_user_cannot_add_product_to_cart(self):
        response = self.client.post(reverse('add_to_cart', args=[self.product.id]))
        self.assertRedirects(response, f"{reverse('login')}?next={reverse('add_to_cart', args=[self.product.id])}")

    def test_authenticated_user_can_access_cart_page_and_see_count(self):
        self.client.login(username='tester', password='secret123')
        cart = Cart.objects.create()
        CartItem.objects.create(cart=cart, product=self.product, quantity=2)

        response = self.client.get(reverse('cart_detail'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['cart_count'], 2)

    def test_anonymous_user_sees_zero_cart_count_in_context(self):
        response = self.client.get(reverse('home'))
        self.assertEqual(response.context['cart_count'], 0)
