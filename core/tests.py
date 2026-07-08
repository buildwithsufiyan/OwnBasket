from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from products.models import Brand, Category, Product


class HomePageSectionTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name='Mobiles', slug='mobiles')
        self.brand = Brand.objects.create(name='Demo Brand')
        Product.objects.create(
            name='Featured Product',
            category=self.category,
            brand=self.brand,
            description='Homepage featured item',
            price=Decimal('999.00'),
            stock=10,
            featured_product=True,
            image=SimpleUploadedFile('featured.jpg', b'featured-image', content_type='image/jpeg'),
        )

    def test_homepage_hides_automatic_classification_sections(self):
        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<h2 class="homepage-section-title">Featured Products</h2>', html=False)
        self.assertNotContains(response, '<h2 class="homepage-section-title">Best Sellers</h2>', html=False)
        self.assertNotContains(response, '<h2 class="homepage-section-title">Trending Products</h2>', html=False)
        self.assertNotContains(response, '<h2 class="homepage-section-title">New Arrivals</h2>', html=False)
        self.assertNotContains(response, '<h2 class="homepage-section-title">Recommended For You</h2>', html=False)
        self.assertNotContains(response, '<h2 class="homepage-section-title">Deal of the Day</h2>', html=False)
        self.assertNotContains(response, '<h2 class="homepage-section-title">Recently Viewed</h2>', html=False)
