from decimal import Decimal

from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase
from django.urls import reverse

from accounts.admin import CustomerProfileAdmin
from accounts.models import CustomerProfile
from orders.models import Order, OrderItem
from products.admin import ProductReviewAdmin, approve_reviews, reject_reviews
from products.models import Brand, Category, Product, ProductReview
from products.templatetags.product_admin_tags import dashboard_sales_analytics
from themes.models import Theme


class Phase9AdminTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='customer', email='customer@example.com', password='test-password'
        )
        self.admin_user = get_user_model().objects.create_superuser(
            username='phase9-admin', email='admin@example.com', password='test-password'
        )
        Theme.objects.create(
            name='Phase 9 test theme',
            slug='default',
            description='',
            is_active=True,
            theme_folder='default',
        )
        category = Category.objects.create(name='Admin category', slug='admin-category')
        brand = Brand.objects.create(name='Admin brand')
        self.product = Product.objects.create(
            category=category,
            brand=brand,
            name='Admin product',
            description='Admin product description',
            price=Decimal('100.00'),
            image=SimpleUploadedFile('phase9-product.jpg', b'phase9-image', content_type='image/jpeg'),
        )

    def test_review_moderation_keeps_product_summary_real(self):
        review = ProductReview.objects.create(
            product=self.product,
            user=self.user,
            rating=4,
            body='A real customer review.',
        )
        self.product.refresh_from_db()
        self.assertEqual(self.product.reviews_count, 0)
        self.assertEqual(self.product.rating, Decimal('0.0'))

        request = RequestFactory().post('/admin/products/productreview/')
        request.user = self.admin_user
        request._messages = _MessageCollector()
        model_admin = ProductReviewAdmin(ProductReview, AdminSite())
        approve_reviews(model_admin, request, ProductReview.objects.filter(pk=review.pk))

        review.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual(review.moderation_status, ProductReview.ModerationStatus.APPROVED)
        self.assertEqual(review.moderated_by, self.admin_user)
        self.assertEqual(self.product.reviews_count, 1)
        self.assertEqual(self.product.rating, Decimal('4.0'))

        reject_reviews(model_admin, request, ProductReview.objects.filter(pk=review.pk))
        self.product.refresh_from_db()
        self.assertEqual(self.product.reviews_count, 0)
        self.assertEqual(self.product.rating, Decimal('0.0'))

    def test_order_and_customer_admin_use_actual_order_metrics(self):
        order = Order.objects.create(
            user=self.user,
            full_name='Customer One',
            email=self.user.email,
            address='123 Test Street',
            subtotal=Decimal('100.00'),
            shipping_amount=Decimal('10.00'),
            total_price=Decimal('110.00'),
        )
        OrderItem.objects.create(
            order=order,
            product=self.product,
            quantity=2,
            original_price=Decimal('50.00'),
            price=Decimal('50.00'),
        )
        request = RequestFactory().get('/admin/accounts/customerprofile/')
        request.user = self.admin_user
        customer_admin = CustomerProfileAdmin(CustomerProfile, AdminSite())
        profile = customer_admin.get_queryset(request).get(user=self.user)
        self.assertEqual(profile._order_count, 1)
        self.assertEqual(profile._lifetime_value, Decimal('110'))

    def test_dashboard_uses_scaled_real_revenue_and_accessible_markup(self):
        Order.objects.create(
            user=self.user,
            full_name='Customer One',
            email=self.user.email,
            address='123 Test Street',
            total_price=Decimal('250.00'),
        )
        rows = dashboard_sales_analytics(7)
        self.assertEqual(max(row['bar_percent'] for row in rows), 100)

        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('admin:index'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Open Orders')
        self.assertContains(response, 'aria-label="Revenue for the last seven days"')
        self.assertContains(response, 'admin/phase9_admin.css')


class _MessageCollector:
    def add(self, level, message, extra_tags=''):
        pass
