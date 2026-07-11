from django.db.models import F
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib.auth.decorators import login_required
from products.models import Product
from products.pricing import attach_pricing_to_products
from .models import Wishlist


@login_required
def add_to_wishlist(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    _, created = Wishlist.objects.get_or_create(user=request.user, product=product)
    if created:
        Product.objects.filter(pk=product.pk).update(
            wishlist_count=F("wishlist_count") + 1
        )
    return redirect("wishlist:wishlist")


@login_required
def remove_from_wishlist(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    deleted, _ = Wishlist.objects.filter(user=request.user, product=product).delete()
    if deleted:
        Product.objects.filter(pk=product.pk, wishlist_count__gt=0).update(
            wishlist_count=F("wishlist_count") - 1
        )
    return redirect("wishlist:wishlist")


@login_required
def wishlist_view(request):
    items = Wishlist.objects.filter(user=request.user)
    attach_pricing_to_products([item.product for item in items])
    return render(request, "wishlist/wishlist.html", {"items": items})
