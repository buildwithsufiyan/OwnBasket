from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from cart.models import CartItem
from products.models import Brand, Category, Product

from .models import Wishlist, WishlistCollection


class AdvancedWishlistTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('wish-user', password='test-pass-123')
        self.other = get_user_model().objects.create_user('wish-other', password='test-pass-123')
        category = Category.objects.create(name='Wishlist Category', slug='wishlist-category')
        brand = Brand.objects.create(name='Wishlist Brand')
        self.product = Product.objects.create(
            name='Saved Product', category=category, brand=brand, description='Saved item',
            price=Decimal('50.00'), stock=5,
            image=SimpleUploadedFile('saved.jpg', b'image', content_type='image/jpeg'),
        )
        self.client.force_login(self.user)

    def test_default_and_multiple_collections_with_price_snapshot(self):
        self.client.post(reverse('wishlist:add_to_wishlist', args=(self.product.pk,)))
        item = Wishlist.objects.get(user=self.user, product=self.product)
        self.assertEqual(item.collection.name, 'Favorites')
        self.assertEqual(item.price_at_add, Decimal('50.00'))
        self.client.post(reverse('wishlist:create_collection'), {'name': 'Gifts'})
        collection = WishlistCollection.objects.get(user=self.user, name='Gifts')
        self.client.post(reverse('wishlist:move_item', args=(item.pk,)), {'collection': collection.pk})
        item.refresh_from_db()
        self.assertEqual(item.collection, collection)

    def test_move_to_cart_bulk_remove_and_public_share_permissions(self):
        collection = WishlistCollection.objects.create(user=self.user, name='Public ideas', is_public=True)
        first = Wishlist.objects.create(user=self.user, collection=collection, product=self.product)
        shared = self.client.get(reverse('wishlist:shared', args=(collection.share_token,)))
        self.assertContains(shared, self.product.name)
        self.client.post(reverse('wishlist:move_to_cart', args=(first.pk,)))
        self.assertTrue(CartItem.objects.filter(cart__user=self.user, product=self.product).exists())
        self.assertFalse(Wishlist.objects.filter(pk=first.pk).exists())
        private = WishlistCollection.objects.create(user=self.other, name='Private', is_public=False)
        self.assertEqual(self.client.get(reverse('wishlist:shared', args=(private.share_token,))).status_code, 404)

    def test_collection_actions_are_owner_scoped_and_post_only(self):
        foreign = WishlistCollection.objects.create(user=self.other, name='Foreign')
        self.assertEqual(self.client.get(reverse('wishlist:delete_collection', args=(foreign.pk,))).status_code, 405)
        self.assertEqual(self.client.post(reverse('wishlist:delete_collection', args=(foreign.pk,))).status_code, 404)
