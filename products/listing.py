from urllib.parse import urlencode

from django.db.models import F, Q

from .models import Product

SORT_OPTIONS = {
    "default": ("-featured_product", "-created_at", "-id"), "newest": ("-created_at", "-id"),
    "price_low": ("price", "id"), "price_high": ("-price", "-id"),
    "rating": ("-rating", "-reviews_count", "-id"), "popular": ("-total_views", "-id"),
    "discount": ("-discount_percentage", "-id"), "name": ("name", "id"),
}


def build_product_listing(request, default_sort="default"):
    """Build a single relation-optimized queryset from all public PLP filters."""
    params = request.GET
    products = Product.objects.marketplace_visible().select_related("seller", "brand", "category", "subcategory").prefetch_related('custom_badges').filter(
        is_active=True, brand__is_active=True, category__is_active=True
    )
    query = params.get("q", "").strip()
    if query:
        products = products.filter(Q(name__icontains=query) | Q(short_description__icontains=query) | Q(brand__name__icontains=query) | Q(category__name__icontains=query))
    if params.get("category", "").strip():
        products = products.filter(category__slug=params["category"].strip())
    if params.get("subcategory", "").strip():
        products = products.filter(subcategory__slug=params["subcategory"].strip())
    brand_ids = [value for value in params.getlist("brand") if value.isdigit()]
    if brand_ids:
        products = products.filter(brand_id__in=brand_ids)
    for parameter, lookup in (("min_price", "price__gte"), ("max_price", "price__lte")):
        if params.get(parameter, "").strip():
            products = products.filter(**{lookup: params[parameter].strip()})
    if params.get("rating", "").isdigit():
        products = products.filter(rating__gte=int(params["rating"]))
    availability = params.get("availability")
    if availability == "in_stock": products = products.filter(Q(stock__gt=0) | Q(availability_mode='pre_order'))
    elif availability == "low_stock": products = products.filter(stock__gt=0, stock__lte=F('low_stock_alert'))
    elif availability == "out_of_stock": products = products.filter(stock=0).exclude(availability_mode='pre_order')
    elif availability == "pre_order": products = products.filter(availability_mode='pre_order')
    discount = params.get("discount")
    if discount == "yes": products = products.filter(Q(discount_price__isnull=False) | Q(old_price__gt=F("price")))
    elif discount and discount.isdigit(): products = products.filter(discount_percentage__gte=int(discount))
    for parameter, variant_name in (("color", "color"), ("size", "size")):
        values = [value.strip()[:100] for value in params.getlist(parameter) if value.strip()]
        if values:
            products = products.filter(variants__variant_name__iexact=variant_name, variants__variant_value__in=values)
    tags = [value.strip()[:100] for value in params.getlist('tag') if value.strip()]
    if tags:
        products = products.filter(features__feature__in=tags)
    for parameter, field in (("featured", "featured_product"), ("flash_sale", "flash_sale_product"), ("recommended", "recommended_product")):
        if params.get(parameter) == "yes": products = products.filter(**{field: True})
    sort = params.get("sort", default_sort)
    sort = sort if sort in SORT_OPTIONS else "default"
    params = params.copy(); params.pop("page", None)
    return products.order_by(*SORT_OPTIONS[sort]).distinct(), query, sort, urlencode(params, doseq=True)
