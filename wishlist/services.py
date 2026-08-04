from django.db.models import F

from api_v2.sync import bump_sync_state
from marketplace.visibility import visible_seller_q
from personalization.models import BehaviorEvent
from personalization.services import record_behavior
from products.models import Product

from .models import Wishlist, WishlistCollection

WISHLIST_ITEM_RELATED = ('product', 'product__seller', 'product__brand', 'product__category')
DEFAULT_COLLECTION_NAME = 'Favorites'


def default_collection(user):
    """Return the user's default collection, adopting any collection-less items."""
    collection, _ = WishlistCollection.objects.get_or_create(user=user, name=DEFAULT_COLLECTION_NAME)
    Wishlist.objects.filter(user=user, collection__isnull=True).update(collection=collection)
    return collection


def visible_wishlist_items(queryset):
    return queryset.filter(visible_seller_q('product__seller')).select_related(*WISHLIST_ITEM_RELATED)


def add_product_to_wishlist(request, product, collection):
    """Save a product to a collection and return whether a new entry was created."""
    current_price = product.discount_price if product.has_active_offer() else product.selling_price or product.price
    _, created = Wishlist.objects.get_or_create(
        user=request.user, product=product, collection=collection,
        defaults={'price_at_add': current_price},
    )
    if created:
        Product.objects.filter(pk=product.pk).update(wishlist_count=F('wishlist_count') + 1)
        bump_sync_state(request.user)
        record_behavior(request, BehaviorEvent.EventType.WISHLIST_ADD, product=product, category=product.category, brand=product.brand)
    return created
