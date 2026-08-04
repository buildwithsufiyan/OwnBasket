from decimal import Decimal

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from products.models import Brand, Category, Product
from site_sections.models import ProductCarouselSection, ProductCarouselSource
from site_sections.services import (
    CATALOG_VERSION_KEY,
    _catalog_version,
    get_carousel_products,
    invalidate_carousel_catalog,
)


class CarouselCatalogVersionTests(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)

    def test_version_defaults_to_one(self):
        self.assertEqual(_catalog_version(), 1)

    def test_invalidate_seeds_version_when_missing(self):
        invalidate_carousel_catalog()

        self.assertEqual(cache.get(CATALOG_VERSION_KEY), 1)

    def test_invalidate_increments_existing_version(self):
        cache.set(CATALOG_VERSION_KEY, 4, None)

        invalidate_carousel_catalog()

        self.assertEqual(cache.get(CATALOG_VERSION_KEY), 5)


class CarouselProductsTests(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.category = Category.objects.create(name='Phones', slug='phones')
        self.other_category = Category.objects.create(name='Laptops', slug='laptops')
        self.brand = Brand.objects.create(name='Samsung')
        self.other_brand = Brand.objects.create(name='Apple')

    def make_product(self, name, **flags):
        return Product.objects.create(
            name=name,
            slug=name.lower().replace(' ', '-'),
            category=flags.pop('category', self.category),
            brand=flags.pop('brand', self.brand),
            description=name,
            price=Decimal('100.00'),
            stock=5,
            image=SimpleUploadedFile(
                f"{name}.jpg", b'fake-image', content_type='image/jpeg'
            ),
            **flags,
        )

    def make_section(self, source_type, **kwargs):
        return ProductCarouselSection.objects.create(
            name=f'{source_type} carousel',
            source_type=source_type,
            **kwargs,
        )

    def test_manual_source_returns_selected_products_sorted_by_name(self):
        zebra = self.make_product('Zebra Phone')
        alpha = self.make_product('Alpha Phone')
        self.make_product('Unselected Phone')
        section = self.make_section(ProductCarouselSource.MANUAL)
        section.manual_products.set([zebra, alpha])

        self.assertEqual(
            [product.pk for product in get_carousel_products(section)],
            [alpha.pk, zebra.pk],
        )

    def test_featured_source_filters_on_flag(self):
        featured = self.make_product('Featured Phone', featured_product=True)
        self.make_product('Plain Phone')
        section = self.make_section(ProductCarouselSource.FEATURED)

        self.assertEqual(
            [product.pk for product in get_carousel_products(section)], [featured.pk]
        )

    def test_flash_sale_deal_and_recommended_sources(self):
        flash = self.make_product('Flash Phone', flash_sale_product=True)
        deal = self.make_product('Deal Phone', deal_of_the_day=True)
        recommended = self.make_product('Recommended Phone', recommended_product=True)

        for source, expected in (
            (ProductCarouselSource.FLASH_SALE, flash),
            (ProductCarouselSource.DEAL_OF_THE_DAY, deal),
            (ProductCarouselSource.RECOMMENDED, recommended),
        ):
            with self.subTest(source=source):
                cache.clear()
                section = self.make_section(source)
                self.assertEqual(
                    [product.pk for product in get_carousel_products(section)],
                    [expected.pk],
                )

    def test_category_and_brand_sources(self):
        phone = self.make_product('Category Phone')
        laptop = self.make_product(
            'Brand Laptop', category=self.other_category, brand=self.other_brand
        )
        category_section = self.make_section(
            ProductCarouselSource.CATEGORY, category=self.category
        )
        brand_section = self.make_section(
            ProductCarouselSource.BRAND, brand=self.other_brand
        )

        self.assertEqual(
            [product.pk for product in get_carousel_products(category_section)],
            [phone.pk],
        )
        self.assertEqual(
            [product.pk for product in get_carousel_products(brand_section)],
            [laptop.pk],
        )

    def test_latest_source_orders_by_recency(self):
        first = self.make_product('First Phone')
        second = self.make_product('Second Phone')
        section = self.make_section(ProductCarouselSource.LATEST)

        self.assertEqual(
            [product.pk for product in get_carousel_products(section)],
            [second.pk, first.pk],
        )

    def test_legacy_ranking_sources_return_nothing(self):
        self.make_product('Any Phone', featured_product=True)

        for source in (
            ProductCarouselSource.BEST_SELLING,
            ProductCarouselSource.TRENDING,
        ):
            with self.subTest(source=source):
                cache.clear()
                self.assertEqual(get_carousel_products(self.make_section(source)), [])

    def test_inactive_products_categories_and_brands_are_excluded(self):
        self.make_product('Inactive Phone', is_active=False)
        inactive_category = Category.objects.create(
            name='Tablets', slug='tablets', is_active=False
        )
        self.make_product('Tablet', category=inactive_category)
        inactive_brand = Brand.objects.create(name='Nokia', is_active=False)
        self.make_product('Nokia Phone', brand=inactive_brand)
        visible = self.make_product('Visible Phone')
        section = self.make_section(ProductCarouselSource.LATEST)

        self.assertEqual(
            [product.pk for product in get_carousel_products(section)], [visible.pk]
        )

    def test_products_limit_is_respected(self):
        for index in range(4):
            self.make_product(f'Phone {index}')
        section = self.make_section(ProductCarouselSource.LATEST, products_limit=2)

        self.assertEqual(len(get_carousel_products(section)), 2)

    def test_cached_ids_are_reused_until_catalog_is_invalidated(self):
        first = self.make_product('First Phone')
        section = self.make_section(ProductCarouselSource.LATEST)
        get_carousel_products(section)

        cache_key = f'site_sections:carousel:{section.pk}:v{_catalog_version()}'
        self.assertEqual(cache.get(cache_key), [first.pk])
        cache.set(cache_key, [], 300)
        self.assertEqual(get_carousel_products(section), [])

        invalidate_carousel_catalog()
        self.assertEqual(
            [product.pk for product in get_carousel_products(section)], [first.pk]
        )

    def test_saving_a_product_invalidates_the_cached_catalog(self):
        first = self.make_product('First Phone')
        section = self.make_section(ProductCarouselSource.LATEST)
        get_carousel_products(section)

        second = self.make_product('Second Phone')

        self.assertEqual(
            [product.pk for product in get_carousel_products(section)],
            [second.pk, first.pk],
        )

    def test_deleted_products_are_dropped_from_cached_ids(self):
        keep = self.make_product('Keep Phone')
        drop = self.make_product('Drop Phone')
        section = self.make_section(ProductCarouselSource.LATEST)
        get_carousel_products(section)

        drop.delete()

        self.assertEqual(
            [product.pk for product in get_carousel_products(section)], [keep.pk]
        )

    def test_pricing_is_attached_to_returned_products(self):
        self.make_product('Priced Phone')
        section = self.make_section(ProductCarouselSource.LATEST)

        product = get_carousel_products(section)[0]

        self.assertTrue(hasattr(product, 'pricing'))
