from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, F
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from api_v2.sync import bump_sync_state
from cart.models import CartItem
from cart.services import get_user_cart, touch_cart
from core.http import safe_redirect_target
from personalization.models import BehaviorEvent
from personalization.services import record_behavior
from products.models import Product
from products.pricing import attach_pricing_to_products

from .models import Wishlist, WishlistCollection, WishlistSettings
from .services import add_product_to_wishlist, default_collection, visible_wishlist_items


def _safe_return_url(request, fallback='wishlist:wishlist'):
    return safe_redirect_target(request, request.POST.get('next'), fallback)


@login_required
@require_POST
def add_to_wishlist(request, product_id):
    product = get_object_or_404(Product.objects.marketplace_visible(), id=product_id, is_active=True)
    settings = WishlistSettings.get_solo()
    collection_id = request.POST.get('collection')
    collection = WishlistCollection.objects.filter(user=request.user, pk=collection_id).first() if collection_id else default_collection(request.user)
    if not collection:
        messages.error(request, 'Select a valid wishlist collection.')
        return redirect(product.get_absolute_url())
    if collection.items.count() >= settings.max_items_per_collection:
        messages.error(request, 'This wishlist collection has reached its item limit.')
        return redirect('wishlist:wishlist')
    if add_product_to_wishlist(request, product, collection):
        messages.success(request, f'Added to {collection.name}.')
    return redirect(_safe_return_url(request))


@login_required
@require_POST
def remove_from_wishlist(request, product_id):
    collection_id = request.POST.get('collection')
    items = Wishlist.objects.filter(user=request.user, product_id=product_id)
    if collection_id and collection_id.isdigit():
        items = items.filter(collection_id=collection_id)
    item = items.select_related('product').first()
    if item:
        product = item.product
        item.delete()
        Product.objects.filter(pk=product.pk, wishlist_count__gt=0).update(wishlist_count=F('wishlist_count') - 1)
        bump_sync_state(request.user)
        record_behavior(request, BehaviorEvent.EventType.WISHLIST_REMOVE, product=product, category=product.category, brand=product.brand)
    return redirect('wishlist:wishlist')


@login_required
@require_POST
def create_collection(request):
    settings = WishlistSettings.get_solo()
    name = ' '.join((request.POST.get('name') or '').split())[:80]
    if not name:
        messages.error(request, 'Collection name is required.')
    elif WishlistCollection.objects.filter(user=request.user).count() >= settings.max_collections_per_user:
        messages.error(request, 'You have reached the collection limit.')
    else:
        _, created = WishlistCollection.objects.get_or_create(user=request.user, name=name)
        messages.success(request, 'Collection created.' if created else 'That collection already exists.')
    return redirect('wishlist:wishlist')


@login_required
@require_POST
def delete_collection(request, collection_id):
    collection = get_object_or_404(WishlistCollection, pk=collection_id, user=request.user)
    affected = list(collection.items.values_list('product_id', flat=True))
    with transaction.atomic():
        collection.delete()
        for product_id in affected:
            Product.objects.filter(pk=product_id, wishlist_count__gt=0).update(wishlist_count=F('wishlist_count') - 1)
    messages.success(request, 'Collection deleted.')
    return redirect('wishlist:wishlist')


@login_required
@require_POST
def move_item(request, item_id):
    item = get_object_or_404(Wishlist, pk=item_id, user=request.user)
    target = get_object_or_404(WishlistCollection, pk=request.POST.get('collection'), user=request.user)
    if Wishlist.objects.filter(collection=target, product=item.product).exclude(pk=item.pk).exists():
        item.delete()
        Product.objects.filter(pk=item.product_id, wishlist_count__gt=0).update(wishlist_count=F('wishlist_count') - 1)
    else:
        item.collection = target
        item.save(update_fields=('collection',))
    return redirect(f'{redirect("wishlist:wishlist").url}?collection={target.pk}')


@login_required
@require_POST
def bulk_remove(request):
    ids = [value for value in request.POST.getlist('items') if value.isdigit()][:100]
    items = list(Wishlist.objects.filter(user=request.user, pk__in=ids).values_list('id', 'product_id'))
    Wishlist.objects.filter(user=request.user, pk__in=[item[0] for item in items]).delete()
    for _, product_id in items:
        Product.objects.filter(pk=product_id, wishlist_count__gt=0).update(wishlist_count=F('wishlist_count') - 1)
    messages.success(request, f'{len(items)} wishlist item(s) removed.')
    return redirect('wishlist:wishlist')


@login_required
@require_POST
def move_to_cart(request, item_id):
    item = get_object_or_404(Wishlist.objects.select_related('product'), pk=item_id, user=request.user)
    product = item.product
    if not product.can_purchase:
        messages.error(request, 'This product is currently unavailable.')
        return redirect('wishlist:wishlist')
    cart = get_user_cart(request.user)
    cart_item, created = CartItem.objects.get_or_create(cart=cart, product=product, defaults={'quantity': 1})
    if not created:
        cart_item.quantity = min(cart_item.quantity + 1, 99)
        cart_item.save(update_fields=('quantity',))
    touch_cart(cart)
    item.delete()
    Product.objects.filter(pk=product.pk, wishlist_count__gt=0).update(wishlist_count=F('wishlist_count') - 1)
    bump_sync_state(request.user)
    record_behavior(request, BehaviorEvent.EventType.CART_ADD, product=product, category=product.category, brand=product.brand)
    messages.success(request, 'Product moved to your cart.')
    return redirect('cart_detail')


@login_required
@require_POST
def toggle_saved_for_later(request, item_id):
    item = get_object_or_404(Wishlist, pk=item_id, user=request.user)
    item.saved_for_later = not item.saved_for_later
    item.save(update_fields=('saved_for_later',))
    return redirect('wishlist:wishlist')


@login_required
@require_POST
def toggle_share(request, collection_id):
    collection = get_object_or_404(WishlistCollection, pk=collection_id, user=request.user)
    if not WishlistSettings.get_solo().allow_public_sharing:
        messages.error(request, 'Wishlist sharing is disabled.')
    else:
        collection.is_public = not collection.is_public
        collection.save(update_fields=('is_public',))
    return redirect(f'{redirect("wishlist:wishlist").url}?collection={collection.pk}')


def shared_wishlist(request, token):
    collection = get_object_or_404(WishlistCollection.objects.select_related('user'), share_token=token, is_public=True)
    items = list(visible_wishlist_items(collection.items.filter(product__is_active=True)))
    attach_pricing_to_products([item.product for item in items])
    return render(request, 'wishlist/shared.html', {'collection': collection, 'items': items})


@login_required
def wishlist_view(request):
    default = default_collection(request.user)
    collections = list(WishlistCollection.objects.filter(user=request.user).annotate(item_count=Count('items')))
    selected_id = request.GET.get('collection')
    selected = next((item for item in collections if str(item.pk) == selected_id), default)
    items = list(visible_wishlist_items(Wishlist.objects.filter(user=request.user, collection=selected)))
    attach_pricing_to_products([item.product for item in items])
    return render(request, 'wishlist/wishlist.html', {
        'items': items, 'collections': collections, 'selected_collection': selected,
        'wishlist_settings': WishlistSettings.get_solo(),
    })
