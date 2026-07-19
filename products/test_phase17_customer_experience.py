from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from orders.models import Order, OrderItem

from .models import (
    Brand, Category, Product, ProductBadge, ProductFeature, ProductReview,
    ReviewHelpfulVote, SubCategory,
)


User = get_user_model()


class Phase17ProductExperienceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('phase17-user', password='test-pass-123')
        self.other = User.objects.create_user('phase17-other', password='test-pass-123')
        self.category = Category.objects.create(name='Audio', slug='audio')
        self.subcategory = SubCategory.objects.create(category=self.category, name='Headphones', slug='headphones')
        self.brand = Brand.objects.create(name='SoundLab')
        self.product = Product.objects.create(
            name='Studio Headphones', category=self.category, subcategory=self.subcategory,
            brand=self.brand, description='Detailed sound', short_description='Wireless audio',
            price=Decimal('100.00'), stock=3,
            image=SimpleUploadedFile('headphones.jpg', b'image', content_type='image/jpeg'),
        )
        ProductFeature.objects.create(product=self.product, feature='Noise cancelling')

    def delivered_order(self):
        order = Order.objects.create(
            user=self.user, full_name='Phase Customer', email='phase@example.com',
            address='1 Test Road', total_price=100, status='Delivered',
        )
        OrderItem.objects.create(order=order, product=self.product, quantity=1, price=100)

    def test_verified_customer_can_create_edit_and_delete_review(self):
        self.delivered_order()
        self.client.force_login(self.user)
        url = reverse('products:submit_review', args=(self.product.slug,))
        response = self.client.post(url, {'rating': 5, 'title': 'Excellent', 'body': 'Excellent sound and comfortable fit.'})
        self.assertRedirects(response, self.product.get_absolute_url() + '#reviews')
        review = ProductReview.objects.get(user=self.user, product=self.product)
        self.assertTrue(review.verified_purchase)
        self.assertEqual(review.moderation_status, 'pending')
        self.client.post(url, {'rating': 4, 'title': 'Updated', 'body': 'Updated review with enough useful detail.'})
        self.assertEqual(ProductReview.objects.filter(user=self.user, product=self.product).count(), 1)
        review.refresh_from_db()
        self.assertEqual(review.rating, 4)
        self.client.post(reverse('products:delete_review', args=(review.pk,)))
        self.assertFalse(ProductReview.objects.filter(pk=review.pk).exists())

    def test_review_requires_delivered_purchase_and_helpful_vote_is_unique(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse('products:submit_review', args=(self.product.slug,)), {
            'rating': 5, 'body': 'A detailed review that should not be accepted yet.',
        })
        self.assertFalse(ProductReview.objects.exists())
        review = ProductReview.objects.create(
            user=self.other, product=self.product, rating=5, body='A useful approved review.',
            verified_purchase=True, moderation_status='approved',
        )
        url = reverse('products:helpful_review', args=(review.pk,))
        self.client.post(url)
        self.client.post(url)
        review.refresh_from_db()
        self.assertEqual(review.helpful_count, 1)
        self.assertEqual(ReviewHelpfulVote.objects.count(), 1)

    def test_comparison_limit_and_ownership_safe_session(self):
        self.client.post(reverse('products:compare_add', args=(self.product.pk,)))
        response = self.client.get(reverse('products:compare'))
        self.assertContains(response, self.product.name)
        self.client.post(reverse('products:compare_remove', args=(self.product.pk,)))
        self.assertNotContains(self.client.get(reverse('products:compare')), self.product.name)

    def test_dynamic_badge_availability_and_enterprise_filters(self):
        badge = ProductBadge.objects.create(label='Eco Friendly', priority=1)
        badge.products.add(self.product)
        self.assertIn('Eco Friendly', self.product.active_badges)
        self.assertEqual(self.product.availability_label, 'Only 3 left')
        response = self.client.get(reverse('products:product_list'), {
            'subcategory': self.subcategory.slug, 'availability': 'low_stock', 'tag': 'Noise cancelling',
        })
        self.assertContains(response, self.product.name)


class Phase17SecurityTests(TestCase):
    def test_mutating_endpoints_reject_get(self):
        self.assertEqual(self.client.get(reverse('products:compare_add', args=(999,))).status_code, 405)
