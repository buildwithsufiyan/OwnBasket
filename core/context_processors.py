from django.conf import settings
from django.core.cache import cache
from django.db.models import Sum

from products.models import Category, Brand
from cart.models import Cart, CartItem


def ecommerce_context(request):
    categories = cache.get_or_set(
        "navigation:categories:v1",
        lambda: list(Category.objects.filter(is_active=True).order_by("sort_order", "name")),
        300,
    )
    brands = cache.get_or_set(
        "navigation:brands:v1",
        lambda: list(Brand.objects.filter(is_active=True).order_by("display_order", "name")),
        300,
    )

    if request.user.is_authenticated:
        cart, _ = Cart.objects.get_or_create(id=request.user.id)
        cart_count = CartItem.objects.filter(cart=cart).aggregate(total=Sum("quantity"))["total"] or 0
    else:
        cart_count = 0

    return {
        'all_categories': categories,
        'all_brands': brands,
        'cart_count': cart_count,
    }


def seo_context(request):
    canonical_url = f"{settings.CANONICAL_BASE_URL}{request.path}"
    return {
        "site_name": settings.SITE_NAME,
        "default_meta_description": settings.DEFAULT_META_DESCRIPTION,
        "canonical_url": canonical_url,
        "default_social_image": request.build_absolute_uri("/static/images/logo.png"),
    }
