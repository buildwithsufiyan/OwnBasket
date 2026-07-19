from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from orders.models import Order, OrderItem
from products.models import Brand, Category, Product

from .models import (
    CommissionRule,
    InventoryHistory,
    MarketplaceSettings,
    SellerInventory,
    SellerNotification,
    SellerOrderFulfillment,
    SellerProfile,
)


User = get_user_model()
TINY_GIF = (
    b'GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00'
    b'\xff\xff\xff!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00'
    b'\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;'
)


class Phase18MarketplaceBase(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name='Phase 18', slug='phase-18')
        self.brand = Brand.objects.create(name='Marketplace brand')
        self.user = User.objects.create_user('phase18-seller', password='Strong-pass-123!')
        self.seller = SellerProfile.objects.create(
            user=self.user,
            store_name='Phase 18 Store',
            slug='phase-18-store',
            legal_name='Phase 18 LLC',
            business_email='seller@example.com',
            business_phone='03000000000',
            verification_status=SellerProfile.VerificationStatus.APPROVED,
        )
        self.product = Product.objects.create(
            seller=self.seller,
            name='Seller stock item',
            category=self.category,
            brand=self.brand,
            price=Decimal('100.00'),
            stock=12,
            low_stock_alert=3,
            description='Seller-owned stock',
            image=SimpleUploadedFile('phase18.gif', TINY_GIF, content_type='image/gif'),
        )


class MarketplaceModeTests(Phase18MarketplaceBase):
    def test_disabled_marketplace_keeps_legacy_products_and_hides_seller_products(self):
        legacy = Product.objects.create(
            name='OwnBasket legacy product', category=self.category, brand=self.brand,
            price=Decimal('50.00'), stock=5, description='Single-vendor product',
            image=SimpleUploadedFile('legacy.gif', TINY_GIF, content_type='image/gif'),
        )
        MarketplaceSettings.objects.create(enabled=False)
        visible = Product.objects.marketplace_visible()
        self.assertTrue(visible.filter(pk=legacy.pk).exists())
        self.assertFalse(visible.filter(pk=self.product.pk).exists())
        self.assertEqual(self.client.get(reverse('marketplace:store_list')).status_code, 404)
        self.assertEqual(self.client.get(reverse('marketplace:register')).status_code, 404)

    def test_single_vendor_mode_forces_registration_off(self):
        settings = MarketplaceSettings(
            enabled=True,
            mode=MarketplaceSettings.Mode.SINGLE_VENDOR,
            seller_registration_enabled=True,
        )
        settings.full_clean()
        self.assertFalse(settings.seller_registration_enabled)
        self.assertFalse(settings.accepts_sellers)


class SellerInventoryTests(Phase18MarketplaceBase):
    def test_inventory_adjustment_is_owned_and_audited(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse('marketplace:inventory_update', args=(self.product.pk,)),
            {'current_stock': 9, 'reserved_stock': 2},
        )
        self.assertRedirects(response, reverse('marketplace:inventory_update', args=(self.product.pk,)))
        inventory = SellerInventory.objects.get(product=self.product)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 9)
        self.assertEqual(inventory.reserved_stock, 2)
        history = InventoryHistory.objects.get(inventory=inventory)
        self.assertEqual(history.stock_change, -3)
        self.assertEqual(history.reserved_change, 2)

    def test_seller_cannot_adjust_another_sellers_inventory(self):
        other_user = User.objects.create_user('other-seller', password='Strong-pass-123!')
        SellerProfile.objects.create(
            user=other_user, store_name='Other Store', slug='other-store', legal_name='Other LLC',
            business_email='other@example.com', business_phone='03001111111',
            verification_status=SellerProfile.VerificationStatus.APPROVED,
        )
        self.client.force_login(other_user)
        self.assertEqual(
            self.client.post(
                reverse('marketplace:inventory_update', args=(self.product.pk,)),
                {'current_stock': 1, 'reserved_stock': 0},
            ).status_code,
            404,
        )


class SellerFulfillmentTests(Phase18MarketplaceBase):
    def setUp(self):
        super().setUp()
        buyer = User.objects.create_user('phase18-buyer', password='Strong-pass-123!')
        self.order = Order.objects.create(
            user=buyer, full_name='Marketplace Buyer', email='buyer@example.com',
            address='1 Seller Lane', total_price=Decimal('100.00'),
        )
        OrderItem.objects.create(
            order=self.order, product=self.product, seller=self.seller,
            seller_name=self.seller.store_name, quantity=1, price=Decimal('100.00'),
            marketplace_commission=Decimal('10.00'), seller_earning=Decimal('90.00'),
        )

    def test_seller_updates_packing_and_ready_to_ship_timeline(self):
        self.client.force_login(self.user)
        detail_url = reverse('marketplace:order_detail', args=(self.order.pk,))
        self.assertEqual(self.client.get(detail_url).status_code, 200)
        response = self.client.post(detail_url, {'status': 'ready_to_ship', 'seller_note': 'Packed safely'})
        self.assertRedirects(response, detail_url)
        fulfillment = SellerOrderFulfillment.objects.get(seller=self.seller, order=self.order)
        self.assertEqual(fulfillment.status, SellerOrderFulfillment.Status.READY_TO_SHIP)
        self.assertIsNotNone(fulfillment.ready_at)
        self.assertEqual(list(fulfillment.history.values_list('status', flat=True)), ['received', 'ready_to_ship'])

    def test_other_seller_cannot_view_order_detail(self):
        other_user = User.objects.create_user('isolated-fulfiller', password='Strong-pass-123!')
        SellerProfile.objects.create(
            user=other_user, store_name='Isolated Fulfillment', slug='isolated-fulfillment',
            legal_name='Isolated LLC', business_email='isolated@example.com', business_phone='03002222222',
            verification_status=SellerProfile.VerificationStatus.APPROVED,
        )
        self.client.force_login(other_user)
        self.assertEqual(self.client.get(reverse('marketplace:order_detail', args=(self.order.pk,))).status_code, 404)


class CommissionAndNotificationStructureTests(Phase18MarketplaceBase):
    def test_commission_rule_supports_global_category_seller_and_combined_scopes(self):
        global_rule = CommissionRule.objects.create(name='Global', rate=Decimal('8.00'))
        category_rule = CommissionRule.objects.create(name='Category', category=self.category, rate=Decimal('7.00'))
        seller_rule = CommissionRule.objects.create(name='Seller', seller=self.seller, rate=Decimal('6.00'))
        combined = CommissionRule.objects.create(
            name='Seller category', seller=self.seller, category=self.category, rate=Decimal('5.00'),
            conditions={'minimum_quantity': 10},
        )
        self.assertEqual(
            [global_rule.scope, category_rule.scope, seller_rule.scope, combined.scope],
            ['global', 'category', 'seller', 'seller_category'],
        )

    def test_low_stock_and_review_notification_types_are_structured(self):
        self.product.stock = 3
        self.product.save(update_fields=('stock',))
        notification = SellerNotification.objects.get(
            seller=self.seller, event_type=SellerNotification.EventType.LOW_STOCK,
        )
        self.assertEqual(notification.email_status, SellerNotification.EmailStatus.NOT_REQUESTED)
