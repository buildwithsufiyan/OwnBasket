from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from cart.models import Cart, CartItem
from orders.models import Order, OrderItem
from products.models import Brand, Category, Product, ProductReview

from .models import SellerNotification, SellerProfile


User = get_user_model()
TINY_GIF = (
    b'GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00'
    b'\xff\xff\xff!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00'
    b'\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;'
)


class MarketplaceTestBase(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name='Marketplace category', slug='marketplace-category')
        self.brand = Brand.objects.create(name='Marketplace brand')
        self.seller_user = User.objects.create_user('seller-one', password='seller-pass-123')
        self.seller = SellerProfile.objects.create(
            user=self.seller_user,
            store_name='Seller One Store',
            slug='seller-one-store',
            legal_name='Seller One LLC',
            business_email='seller@example.com',
            business_phone='03001234567',
            verification_status=SellerProfile.VerificationStatus.APPROVED,
            commission_rate=Decimal('10.00'),
        )
        self.product = Product.objects.create(
            seller=self.seller,
            name='Seller product',
            category=self.category,
            brand=self.brand,
            price=Decimal('100.00'),
            stock=10,
            description='Seller owned product',
            image=SimpleUploadedFile('seller.gif', TINY_GIF, content_type='image/gif'),
        )


class SellerRegistrationAndLoginTests(TestCase):
    def test_seller_registration_creates_pending_profile(self):
        response = self.client.post(reverse('marketplace:register'), {
            'username': 'new-seller',
            'email': 'new-seller@example.com',
            'store_name': 'New Seller Store',
            'legal_name': 'New Seller Ltd',
            'business_phone': '03001112222',
            'password1': 'Strong-seller-pass-123!',
            'password2': 'Strong-seller-pass-123!',
        })
        seller = SellerProfile.objects.get(user__username='new-seller')
        self.assertRedirects(response, reverse('marketplace:dashboard'))
        self.assertEqual(seller.verification_status, SellerProfile.VerificationStatus.PENDING)
        self.assertEqual(str(self.client.session['_auth_user_id']), str(seller.user_id))

    def test_seller_login_redirects_to_dashboard(self):
        user = User.objects.create_user('login-seller', password='seller-pass-123')
        SellerProfile.objects.create(
            user=user, store_name='Login Store', slug='login-store', legal_name='Login LLC',
            business_email='login@example.com', business_phone='03000000000',
        )
        response = self.client.post(reverse('marketplace:login'), {
            'username': 'login-seller', 'password': 'seller-pass-123',
        })
        self.assertRedirects(response, reverse('marketplace:dashboard'))


class SellerPanelAndPermissionTests(MarketplaceTestBase):
    def test_approved_seller_dashboard_and_products_render(self):
        self.client.force_login(self.seller_user)
        dashboard = self.client.get(reverse('marketplace:dashboard'))
        products = self.client.get(reverse('marketplace:products'))
        self.assertEqual(dashboard.status_code, 200)
        self.assertContains(dashboard, 'Seller dashboard')
        self.assertContains(products, self.product.name)

    def test_seller_created_product_is_forcibly_owned_by_current_seller(self):
        self.client.force_login(self.seller_user)
        response = self.client.post(reverse('marketplace:product_create'), {
            'name': 'Panel created product',
            'category': self.category.pk,
            'brand': self.brand.pk,
            'short_description': 'Created in seller panel',
            'description': 'Seller panel product description',
            'price': '250.00',
            'cost_price': '150.00',
            'stock': '7',
            'low_stock_alert': '2',
            'tax_percentage': '0.00',
            'image': SimpleUploadedFile('panel.gif', TINY_GIF, content_type='image/gif'),
        })
        created = Product.objects.get(name='Panel created product')
        self.assertRedirects(response, reverse('marketplace:products'))
        self.assertEqual(created.seller, self.seller)

    def test_pending_seller_cannot_access_product_management(self):
        self.seller.verification_status = SellerProfile.VerificationStatus.PENDING
        self.seller.save(update_fields=('verification_status',))
        self.client.force_login(self.seller_user)
        self.assertRedirects(
            self.client.get(reverse('marketplace:products')),
            reverse('marketplace:dashboard'),
        )

    def test_seller_cannot_edit_or_archive_another_sellers_product(self):
        other_user = User.objects.create_user('seller-two', password='seller-pass-123')
        SellerProfile.objects.create(
            user=other_user, store_name='Seller Two', slug='seller-two', legal_name='Seller Two LLC',
            business_email='two@example.com', business_phone='03009999999',
            verification_status=SellerProfile.VerificationStatus.APPROVED,
        )
        self.client.force_login(other_user)
        self.assertEqual(self.client.get(reverse('marketplace:product_update', args=(self.product.pk,))).status_code, 404)
        self.assertEqual(self.client.post(reverse('marketplace:product_archive', args=(self.product.pk,))).status_code, 404)
        self.product.refresh_from_db()
        self.assertTrue(self.product.is_active)

    def test_seller_orders_are_scoped_to_owned_lines(self):
        buyer = User.objects.create_user('buyer', password='buyer-pass-123')
        order = Order.objects.create(
            user=buyer, full_name='Buyer', email='buyer@example.com', address='Test address',
            total_price=Decimal('100.00'),
        )
        OrderItem.objects.create(
            order=order, product=self.product, seller=self.seller, seller_name=self.seller.store_name,
            quantity=1, price=Decimal('100.00'), marketplace_commission=Decimal('10.00'),
            seller_earning=Decimal('90.00'),
        )
        other_user = User.objects.create_user('isolated-seller', password='seller-pass-123')
        SellerProfile.objects.create(
            user=other_user, store_name='Isolated Store', slug='isolated-store', legal_name='Isolated LLC',
            business_email='isolated@example.com', business_phone='03008888888',
            verification_status=SellerProfile.VerificationStatus.APPROVED,
        )
        self.client.force_login(other_user)
        self.assertNotContains(self.client.get(reverse('marketplace:orders')), self.product.name)


class CheckoutMarketplaceCompatibilityTests(MarketplaceTestBase):
    def test_existing_checkout_snapshots_seller_earnings_and_notifies_seller(self):
        buyer = User.objects.create_user('checkout-buyer', password='buyer-pass-123', email='buyer@example.com')
        cart, _ = Cart.objects.get_or_create(id=buyer.id)
        CartItem.objects.create(cart=cart, product=self.product, quantity=2)
        self.client.force_login(buyer)
        response = self.client.post(reverse('checkout'), {
            'full_name': 'Checkout Buyer', 'email': 'buyer@example.com',
            'address': '1 Marketplace Road', 'payment_method': 'COD',
        })
        item = OrderItem.objects.get(order__user=buyer)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(item.seller, self.seller)
        self.assertEqual(item.seller_name, self.seller.store_name)
        self.assertEqual(item.marketplace_commission, Decimal('20.00'))
        self.assertEqual(item.seller_earning, Decimal('180.00'))
        self.assertTrue(SellerNotification.objects.filter(seller=self.seller, title__contains='New order').exists())

    def test_suspended_seller_product_is_hidden_but_legacy_product_remains_visible(self):
        legacy = Product.objects.create(
            name='Legacy OwnBasket product', category=self.category, brand=self.brand,
            price=Decimal('50.00'), stock=3, description='Legacy product',
            image=SimpleUploadedFile('legacy.gif', TINY_GIF, content_type='image/gif'),
        )
        self.seller.verification_status = SellerProfile.VerificationStatus.SUSPENDED
        self.seller.save(update_fields=('verification_status',))
        response = self.client.get(reverse('products:product_list'))
        self.assertNotContains(response, self.product.name)
        self.assertContains(response, legacy.name)
        self.assertEqual(self.client.get(self.product.get_absolute_url()).status_code, 404)


class SellerRatingAndAdminTests(MarketplaceTestBase):
    def test_public_store_rating_uses_only_approved_real_reviews(self):
        approved_user = User.objects.create_user('reviewer-one', password='reviewer-pass-123')
        pending_user = User.objects.create_user('reviewer-two', password='reviewer-pass-123')
        ProductReview.objects.create(
            product=self.product, user=approved_user, rating=5, body='Excellent',
            moderation_status=ProductReview.ModerationStatus.APPROVED,
        )
        ProductReview.objects.create(
            product=self.product, user=pending_user, rating=1, body='Pending',
            moderation_status=ProductReview.ModerationStatus.PENDING,
        )
        response = self.client.get(self.seller.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '5.0/5 from 1 verified reviews')

    def test_admin_can_approve_seller(self):
        admin_user = User.objects.create_superuser('market-admin', 'admin@example.com', 'admin-pass-123')
        self.seller.verification_status = SellerProfile.VerificationStatus.PENDING
        self.seller.save(update_fields=('verification_status',))
        self.client.force_login(admin_user)
        response = self.client.post(reverse('admin:marketplace_sellerprofile_changelist'), {
            'action': 'approve_sellers', '_selected_action': [self.seller.pk],
        })
        self.seller.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.seller.verification_status, SellerProfile.VerificationStatus.APPROVED)
        self.assertEqual(self.seller.approved_by, admin_user)
