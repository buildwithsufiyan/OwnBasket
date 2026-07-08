from decimal import Decimal

from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from cart.models import Cart, CartItem
from orders.models import Order
from products.pricing import build_cart_summary, resolve_product_pricing

from .admin import BrandHeroBannerAdmin
from .forms import BrandHeroBannerAdminForm
from .models import (
    Brand,
    BrandHeroBanner,
    BuyXGetYOffer,
    Category,
    CategoryDiscount,
    Coupon,
    Product,
    ProductDiscount,
)


class DiscountPricingTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='discount-user',
            password='secret123',
        )
        self.category = Category.objects.create(name='Phones', slug='phones')
        self.brand = Brand.objects.create(name='Samsung')
        self.product = Product.objects.create(
            name='Galaxy S25',
            slug='galaxy-s25',
            category=self.category,
            brand=self.brand,
            description='Flagship phone',
            price=Decimal('900.00'),
            old_price=Decimal('1000.00'),
            stock=10,
            image=SimpleUploadedFile('phone.jpg', b'fake-image', content_type='image/jpeg'),
        )

    def test_product_discount_beats_category_discount(self):
        CategoryDiscount.objects.create(
            category=self.category,
            name='Category Offer',
            discount_type='percentage',
            value=Decimal('10'),
            priority=200,
        )
        ProductDiscount.objects.create(
            product=self.product,
            name='Product Offer',
            discount_type='percentage',
            value=Decimal('20'),
            priority=300,
        )

        pricing = resolve_product_pricing(self.product)

        self.assertEqual(pricing.final_price, Decimal('800.00'))
        self.assertEqual(pricing.source_type, 'product')
        self.assertEqual(pricing.discount_amount, Decimal('200.00'))

    def test_coupon_does_not_stack_on_discounted_product(self):
        ProductDiscount.objects.create(
            product=self.product,
            name='Product Offer',
            discount_type='percentage',
            value=Decimal('20'),
            priority=300,
        )
        Coupon.objects.create(
            code='SAVE10',
            title='Save 10',
            discount_type='percentage',
            value=Decimal('10'),
            is_active=True,
        )

        cart = Cart.objects.create(id=self.user.id)
        CartItem.objects.create(cart=cart, product=self.product, quantity=1)

        summary = build_cart_summary(cart.cartitem_set.select_related('product', 'product__brand', 'product__category'), user=self.user, coupon_code='SAVE10')

        self.assertIsNone(summary.applied_coupon)
        self.assertEqual(summary.coupon_discount, Decimal('0.00'))
        self.assertEqual(summary.grand_total, Decimal('879.00'))

    def test_buy_x_get_y_applies_free_units(self):
        accessory = Product.objects.create(
            name='Galaxy Case',
            slug='galaxy-case',
            category=self.category,
            brand=self.brand,
            description='Protective case',
            price=Decimal('100.00'),
            stock=10,
            image=SimpleUploadedFile('case.jpg', b'fake-image-2', content_type='image/jpeg'),
        )
        BuyXGetYOffer.objects.create(
            name='Buy 2 Get 1 Case',
            buy_product=self.product,
            buy_quantity=2,
            get_product=accessory,
            get_quantity=1,
            is_active=True,
        )

        cart = Cart.objects.create(id=self.user.id)
        CartItem.objects.create(cart=cart, product=self.product, quantity=2)
        CartItem.objects.create(cart=cart, product=accessory, quantity=1)

        summary = build_cart_summary(cart.cartitem_set.select_related('product', 'product__brand', 'product__category'), user=self.user)

        self.assertEqual(summary.buy_x_get_y_discount, Decimal('100.00'))
        self.assertIn('Buy 2 Get 1 Case', summary.buy_x_get_y_messages[0])


class ProductManagementTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='product-user',
            password='secret123',
        )
        self.category = Category.objects.create(name='Accessories', slug='accessories')
        self.brand = Brand.objects.create(name='Apple')

    def test_product_auto_generates_slug_and_sku_and_syncs_pricing_fields(self):
        product = Product.objects.create(
            name='AirPods Pro 2',
            slug='',
            category=self.category,
            brand=self.brand,
            description='Wireless earbuds',
            price=Decimal('249.00'),
            selling_price=Decimal('249.00'),
            mrp=Decimal('299.00'),
            cost_price=Decimal('180.00'),
            stock=12,
            image=SimpleUploadedFile('airpods.jpg', b'fake-image-3', content_type='image/jpeg'),
        )

        self.assertTrue(product.slug.startswith('airpods-pro-2'))
        self.assertTrue(product.sku)
        self.assertEqual(product.old_price, Decimal('299.00'))
        self.assertEqual(product.discount_percentage, Decimal('16.72'))
        self.assertEqual(product.profit_margin, Decimal('27.71'))

    def test_first_order_coupon_rejects_existing_customer(self):
        Coupon.objects.create(
            code='FIRST10',
            title='First Order',
            discount_type='percentage',
            value=Decimal('10'),
            first_order_only=True,
            is_active=True,
        )
        Order.objects.create(
            user=self.user,
            full_name='Test User',
            email='test@example.com',
            address='Address',
            total_price=Decimal('100.00'),
        )

        product = Product.objects.create(
            name='Magic Mouse',
            slug='magic-mouse',
            category=self.category,
            brand=self.brand,
            description='Mouse',
            price=Decimal('99.00'),
            stock=2,
            image=SimpleUploadedFile('mouse.jpg', b'fake-image-4', content_type='image/jpeg'),
        )
        cart = Cart.objects.create(id=self.user.id)
        CartItem.objects.create(cart=cart, product=product, quantity=1)

        summary = build_cart_summary(cart.cartitem_set.select_related('product', 'product__brand', 'product__category'), user=self.user, coupon_code='FIRST10')

        self.assertIsNone(summary.applied_coupon)
        self.assertEqual(summary.coupon_discount, Decimal('0.00'))

    def test_product_detail_increments_views_and_tracks_recently_viewed(self):
        product = Product.objects.create(
            name='Apple Watch',
            slug='apple-watch',
            category=self.category,
            brand=self.brand,
            description='Smart watch',
            price=Decimal('399.00'),
            stock=4,
            image=SimpleUploadedFile('watch.jpg', b'fake-image-5', content_type='image/jpeg'),
        )

        response = self.client.get(reverse('products:product_detail', args=[product.slug]))
        product.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(product.total_views, 1)
        self.assertEqual(self.client.session['recently_viewed_product_ids'][0], product.id)

    def test_active_badges_do_not_include_disabled_automatic_classification_labels(self):
        product = Product.objects.create(
            name='MacBook Air',
            slug='macbook-air',
            category=self.category,
            brand=self.brand,
            description='Laptop',
            price=Decimal('1099.00'),
            stock=5,
            featured_product=True,
            flash_sale_product=True,
            recommended_product=True,
            deal_of_the_day=True,
            image=SimpleUploadedFile('macbook.jpg', b'fake-image-7', content_type='image/jpeg'),
        )

        self.assertIn('Featured', product.active_badges)
        self.assertIn('Flash Sale', product.active_badges)
        self.assertIn('Recommended', product.active_badges)
        self.assertIn('Deal of the Day', product.active_badges)
        self.assertNotIn('Best Seller', product.active_badges)
        self.assertNotIn('Trending', product.active_badges)
        self.assertNotIn('New Arrival', product.active_badges)


class ProductAdminRegressionTests(TestCase):
    def setUp(self):
        self.admin_user = get_user_model().objects.create_superuser(
            username='admin-user',
            email='admin@example.com',
            password='secret123',
        )
        self.category = Category.objects.create(name='Admin Category', slug='admin-category')
        self.brand = Brand.objects.create(name='Admin Brand')
        self.product = Product.objects.create(
            name='Admin Product',
            category=self.category,
            brand=self.brand,
            description='Admin page product',
            price=Decimal('199.00'),
            stock=7,
            image=SimpleUploadedFile('admin-product.jpg', b'fake-image-6', content_type='image/jpeg'),
        )

    def test_admin_product_change_page_opens_without_slug_keyerror(self):
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse('admin:products_product_change', args=[self.product.pk]))

        self.assertEqual(response.status_code, 200)


class BrandDetailPageTests(TestCase):
    def setUp(self):
        self.admin_user = get_user_model().objects.create_superuser(
            username='brand-admin',
            email='brand-admin@example.com',
            password='secret123',
        )
        self.category = Category.objects.create(name='Laptops', slug='laptops')
        self.brand = Brand.objects.create(
            name='Acer',
            logo=SimpleUploadedFile('acer-logo.png', b'acer-logo', content_type='image/png'),
        )
        for index in range(13):
            Product.objects.create(
                name=f'Acer Product {index + 1}',
                category=self.category,
                brand=self.brand,
                description='Brand detail page product',
                price=Decimal('1500.00'),
                stock=5,
                featured_product=index % 2 == 0,
                image=SimpleUploadedFile(
                    f'acer-product-{index + 1}.jpg',
                    b'acer-product-image',
                    content_type='image/jpeg',
                ),
            )

    def test_brand_detail_uses_only_active_banners_in_display_order(self):
        BrandHeroBanner.objects.create(
            brand=self.brand,
            banner_title='Third Banner',
            display_order=3,
            is_active=True,
            cover_image=SimpleUploadedFile('banner-3.jpg', b'banner-3', content_type='image/jpeg'),
        )
        BrandHeroBanner.objects.create(
            brand=self.brand,
            banner_title='Hidden Banner',
            display_order=1,
            is_active=False,
            cover_image=SimpleUploadedFile('banner-hidden.jpg', b'banner-hidden', content_type='image/jpeg'),
        )
        BrandHeroBanner.objects.create(
            brand=self.brand,
            banner_title='First Banner',
            display_order=1,
            is_active=True,
            cover_image=SimpleUploadedFile('banner-1.jpg', b'banner-1', content_type='image/jpeg'),
        )

        response = self.client.get(reverse('products:brand_detail', args=[self.brand.pk]))

        self.assertEqual(response.status_code, 200)
        banners = response.context['brand_hero_banners']
        self.assertEqual([banner.banner_title for banner in banners], ['First Banner', 'Third Banner'])
        self.assertContains(response, 'brand-hero-swiper')
        self.assertContains(response, 'First Banner')
        self.assertNotContains(response, 'Hidden Banner')
        self.assertTrue(response.context['page_obj'].has_next())

    def test_brand_detail_shows_default_hero_when_no_banner_exists(self):
        response = self.client.get(reverse('products:brand_detail', args=[self.brand.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['brand_hero_banners'], [])
        self.assertContains(response, f'Explore the latest collection from {self.brand.name}')

    def test_brand_detail_hides_empty_optional_banner_fields(self):
        BrandHeroBanner.objects.create(
            brand=self.brand,
            banner_title='',
            banner_subtitle='',
            button_text='',
            button_url='',
            display_order=1,
            is_active=True,
            cover_image=SimpleUploadedFile('banner-empty-copy.jpg', b'banner-empty-copy', content_type='image/jpeg'),
        )

        response = self.client.get(reverse('products:brand_detail', args=[self.brand.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['brand_hero_banners'][0].has_content)
        self.assertNotContains(response, '<div class="brand-hero-content">', html=False)
        self.assertNotContains(response, '<a href="#" class="btn btn-owncart brand-hero-button">', html=False)

    def test_brand_hero_banner_admin_form_marks_copy_fields_optional(self):
        form = BrandHeroBannerAdminForm()

        self.assertFalse(form.fields['banner_title'].required)
        self.assertFalse(form.fields['banner_subtitle'].required)
        self.assertFalse(form.fields['button_text'].required)
        self.assertFalse(form.fields['button_url'].required)
        self.assertIn('Optional', form.fields['banner_title'].help_text)
        self.assertIn('Optional', form.fields['button_text'].widget.attrs.get('placeholder', ''))

    def test_brand_hero_banner_admin_uses_visual_editor_template(self):
        admin_instance = BrandHeroBannerAdmin(BrandHeroBanner, AdminSite())

        self.assertEqual(admin_instance.change_form_template, 'admin/visual_editor_change_form.html')

    def test_brand_hero_banner_admin_add_page_renders_live_preview_panel(self):
        self.client.force_login(self.admin_user)

        response = self.client.get('/admin/products/brandherobanner/add/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 've-live-preview')
        self.assertContains(response, '<details open><summary>', html=False)
