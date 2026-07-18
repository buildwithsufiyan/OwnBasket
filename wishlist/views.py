from django.db.models import F, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib.auth.decorators import login_required
from products.models import Product
from products.pricing import attach_pricing_to_products
from .models import Wishlist
from api_v2.sync import bump_sync_state


@login_required
def add_to_wishlist(request, product_id):
    product = get_object_or_404(Product.objects.marketplace_visible(), id=product_id, is_active=True)
    _, created = Wishlist.objects.get_or_create(user=request.user, product=product)
    if created:
        Product.objects.filter(pk=product.pk).update(
            wishlist_count=F("wishlist_count") + 1
        )
        bump_sync_state(request.user)
    return redirect("wishlist:wishlist")


@login_required
def remove_from_wishlist(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    deleted, _ = Wishlist.objects.filter(user=request.user, product=product).delete()
    if deleted:
        Product.objects.filter(pk=product.pk, wishlist_count__gt=0).update(
            wishlist_count=F("wishlist_count") - 1
        )
        bump_sync_state(request.user)
    return redirect("wishlist:wishlist")


@login_required
def wishlist_view(request):
    items = Wishlist.objects.filter(user=request.user).filter(
        Q(product__seller__isnull=True) | Q(product__seller__verification_status='approved')
    ).select_related('product', 'product__seller', 'product__brand', 'product__category')
    attach_pricing_to_products([item.product for item in items])
    return render(request, "wishlist/wishlist.html", {"items": items})
