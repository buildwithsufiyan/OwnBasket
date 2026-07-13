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
    products = Product.objects.select_related("brand", "category", "subcategory").filter(
        is_active=True, brand__is_active=True, category__is_active=True
    )
    query = params.get("q", "").strip()
    if query:
        products = products.filter(Q(name__icontains=query) | Q(short_description__icontains=query) | Q(brand__name__icontains=query) | Q(category__name__icontains=query))
    if params.get("category", "").strip():
        products = products.filter(category__slug=params["category"].strip())
    brand_ids = [value for value in params.getlist("brand") if value.isdigit()]
    if brand_ids:
        products = products.filter(brand_id__in=brand_ids)
    for parameter, lookup in (("min_price", "price__gte"), ("max_price", "price__lte")):
        if params.get(parameter, "").strip():
            products = products.filter(**{lookup: params[parameter].strip()})
    if params.get("rating", "").isdigit():
        products = products.filter(rating__gte=int(params["rating"]))
    if params.get("availability") == "in_stock": products = products.filter(stock__gt=0)
    if params.get("discount") == "yes": products = products.filter(Q(discount_price__isnull=False) | Q(old_price__gt=F("price")))
    for parameter, field in (("featured", "featured_product"), ("flash_sale", "flash_sale_product"), ("recommended", "recommended_product")):
        if params.get(parameter) == "yes": products = products.filter(**{field: True})
    sort = params.get("sort", default_sort)
    sort = sort if sort in SORT_OPTIONS else "default"
    params = params.copy(); params.pop("page", None)
    return products.order_by(*SORT_OPTIONS[sort]), query, sort, urlencode(params, doseq=True)
