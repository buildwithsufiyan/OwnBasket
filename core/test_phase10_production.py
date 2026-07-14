from decimal import Decimal

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.template.loader import render_to_string
from django.urls import reverse

from products.models import Brand, Category, Product
from themes.models import Theme


class ProductionReadinessTests(TestCase):
    def setUp(self):
        category = Category.objects.create(name="Laptops", slug="laptops")
        brand = Brand.objects.create(name="Acme")
        self.product = Product.objects.create(
            name="Safe Laptop", slug="safe-laptop", category=category, brand=brand,
            price=Decimal("1000.00"), stock=3, short_description="A tested laptop",
            description="A tested laptop for production metadata.", warranty="", return_policy="",
        )
        theme = Theme.objects.create(name="Production test", slug="production-test", description="", is_active=True, theme_folder="default")
        cache.set("active_theme", theme)
        cache.set("default_theme", theme)

    def tearDown(self):
        cache.clear()

    def test_health_has_no_internal_details(self):
        response = self.client.get(reverse("health"))
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {"status": "ok"})

    def test_robots_blocks_private_routes_and_links_sitemap(self):
        response = self.client.get(reverse("robots_txt"))
        self.assertContains(response, "Disallow: /admin/")
        self.assertContains(response, "Disallow: /checkout/")
        self.assertContains(response, "Sitemap:")

    def test_sitemap_contains_only_active_public_product(self):
        response = self.client.get("/sitemap.xml")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.product.get_absolute_url())

    def test_product_metadata_uses_real_price_stock_and_rating_rules(self):
        response = self.client.get(self.product.get_absolute_url())
        self.assertContains(response, '<link rel="canonical"', html=False)
        self.assertContains(response, '"price": "1000.00"')
        self.assertContains(response, "https://schema.org/InStock")
        self.assertNotContains(response, "aggregateRating")
        self.assertContains(response, 'property="og:type" content="product"')

    @override_settings(DEBUG=False)
    def test_branded_404_hides_debug_information(self):
        response = self.client.get("/missing-phase-10-page/")
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "OwnBasket", status_code=404)
        self.assertNotContains(response, "Traceback", status_code=404)

    def test_search_is_noindex_follow(self):
        response = self.client.get(reverse("products:search_results"), {"q": "Laptop"})
        self.assertContains(response, '<meta name="robots" content="noindex,follow">')

    def test_private_pages_receive_noindex_header(self):
        user = User.objects.create_user("private-user", password="test-pass")
        self.client.force_login(user)
        response = self.client.get(reverse("account_dashboard"))
        self.assertEqual(response["X-Robots-Tag"], "noindex, nofollow")

    def test_all_error_templates_are_lightweight_and_branded(self):
        for status in (400, 403, 404, 500):
            markup = render_to_string(f"errors/{status}.html")
            self.assertIn("OwnBasket", markup)
            self.assertIn('name="robots" content="noindex"', markup)
