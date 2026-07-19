from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase
from django.urls import reverse

from orders.models import Order, OrderItem
from products.models import Brand, Category, Product, ProductFeature
from wishlist.models import Wishlist

from .models import BehaviorEvent, SearchSynonym
from .search import intelligent_search
from .services import (
    RecommendationService, frequently_bought_together, record_behavior,
    sanitize_search_term, similar_products, trending_products,
)


User = get_user_model()
TINY_GIF = (
    b'GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00'
    b'\xff\xff\xff!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00'
    b'\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;'
)


class PersonalizationBase(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user('ai-user', password='Strong-AI-Pass-123!')
        self.category = Category.objects.create(name='Audio', slug='audio', is_active=True)
        self.other_category = Category.objects.create(name='Kitchen', slug='kitchen', is_active=True)
        self.brand = Brand.objects.create(name='SoundLab', is_active=True)
        self.other_brand = Brand.objects.create(name='HomeLab', is_active=True)
        self.signal = self.product('Wireless Headphones', self.category, self.brand, 100, total_sold=2)
        self.match = self.product('Wireless Earbuds', self.category, self.brand, 110, total_sold=8)
        self.unrelated = self.product('Steel Pan', self.other_category, self.other_brand, 110, total_sold=1)

    def product(self, name, category, brand, price, **extra):
        return Product.objects.create(
            name=name, category=category, brand=brand, price=Decimal(str(price)),
            cost_price=Decimal('10.00'), stock=10, description=f'{name} description',
            short_description=f'{name} compact',
            image=SimpleUploadedFile(f'{name}.gif', TINY_GIF, content_type='image/gif'),
            **extra,
        )


class BehaviorTests(PersonalizationBase):
    def test_events_are_minimal_hashed_and_deduplicated(self):
        request = RequestFactory().get(self.signal.get_absolute_url())
        request.user = AnonymousUser()
        from django.contrib.sessions.middleware import SessionMiddleware
        SessionMiddleware(lambda value: value).process_request(request)
        request.session.save()
        first = record_behavior(request, BehaviorEvent.EventType.PRODUCT_VIEW, product=self.signal)
        second = record_behavior(request, BehaviorEvent.EventType.PRODUCT_VIEW, product=self.signal)
        self.assertIsNotNone(first)
        self.assertIsNone(second)
        self.assertEqual(len(first.session_hash), 64)
        self.assertFalse(hasattr(first, 'ip_address'))

    def test_sensitive_looking_search_terms_are_not_stored(self):
        self.assertEqual(sanitize_search_term('person@example.com'), '')
        self.assertEqual(sanitize_search_term('030012345678'), '')
        self.client.get(reverse('products:search_results'), {'q': 'person@example.com'})
        self.assertFalse(BehaviorEvent.objects.filter(event_type='search').exists())


class RecommendationTests(PersonalizationBase):
    def test_personalized_ranking_uses_real_wishlist_affinity(self):
        Wishlist.objects.create(user=self.user, product=self.signal)
        self.client.force_login(self.user)
        request = self.client.get('/home/').wsgi_request
        recommendations = RecommendationService(request).recommended()
        self.assertEqual(recommendations[0], self.match)
        self.assertNotIn(self.signal, recommendations)

    def test_similarity_uses_category_brand_price_and_features(self):
        ProductFeature.objects.create(product=self.signal, feature='Noise cancelling')
        ProductFeature.objects.create(product=self.match, feature='Noise cancelling')
        results = similar_products(self.signal)
        self.assertEqual(results[0], self.match)
        self.assertNotIn(self.unrelated, results)

    def test_frequently_bought_together_requires_two_real_orders(self):
        for index in range(2):
            order = Order.objects.create(
                user=self.user, full_name='Buyer', email='buyer@example.com',
                address=f'{index} Road', total_price=210,
            )
            OrderItem.objects.create(order=order, product=self.signal, quantity=1, price=100)
            OrderItem.objects.create(order=order, product=self.match, quantity=1, price=110)
        results = frequently_bought_together(self.signal)
        self.assertEqual([item.pk for item in results], [self.match.pk])
        self.assertEqual(frequently_bought_together(self.unrelated), [])

    def test_trending_uses_windowed_events_instead_of_fake_products(self):
        BehaviorEvent.objects.create(event_type='product_view', product=self.match)
        BehaviorEvent.objects.create(event_type='product_view', product=self.match)
        BehaviorEvent.objects.create(event_type='product_view', product=self.signal)
        results = trending_products(hours=24)
        self.assertEqual(results[0], self.match)


class IntelligentSearchTests(PersonalizationBase):
    def test_typo_tolerance_corrects_catalog_term(self):
        result = intelligent_search('wireles headphones')
        self.assertEqual(result.corrected_query, 'wireless headphones')
        self.assertEqual(result.products[0], self.signal)

    def test_configurable_synonym_expands_without_seeded_fake_terms(self):
        SearchSynonym.objects.create(canonical_term='headphones', alternatives=['cans'])
        cache.clear()
        result = intelligent_search('cans')
        self.assertIn(self.signal, result.products)

    def test_search_view_records_term_and_exposes_correction(self):
        response = self.client.get(reverse('products:search_results'), {'q': 'wireles headphones'})
        self.assertContains(response, 'Showing results for')
        self.assertTrue(BehaviorEvent.objects.filter(event_type='search', search_term='wireles headphones').exists())

    def test_mobile_search_contract_exposes_correction_and_pagination(self):
        response = self.client.get(reverse('api-v2:intelligent-search'), {'q': 'wireles headphones'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['correctedQuery'], 'wireless headphones')
        self.assertEqual(response.json()['pagination']['totalItems'], 1)


class PersonalizationIntegrationTests(PersonalizationBase):
    def test_home_switches_between_guest_and_authenticated_sections(self):
        guest = self.client.get('/home/')
        self.assertContains(guest, 'Trending This Week')
        Wishlist.objects.create(user=self.user, product=self.signal)
        self.client.force_login(self.user)
        member = self.client.get('/home/')
        self.assertContains(member, 'Recommended For You')
        self.assertContains(member, 'Your Favourite Aisles')

    def test_product_page_tracks_view_and_uses_similarity_label(self):
        response = self.client.get(self.signal.get_absolute_url())
        self.assertContains(response, 'Similar products')
        self.assertTrue(BehaviorEvent.objects.filter(event_type='product_view', product=self.signal).exists())

    def test_mobile_trending_rejects_unsupported_window(self):
        response = self.client.get(reverse('api-v2:trending'), {'hours': 48})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['error']['code'], 'validation_error')
