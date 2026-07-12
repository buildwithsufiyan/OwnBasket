from django.core.cache import cache

from products.models import Product
from products.pricing import attach_pricing_to_products

from .models import ProductCarouselSource

CATALOG_VERSION_KEY = "site_sections:carousel_catalog_version"


def invalidate_carousel_catalog(**kwargs):
    try:
        cache.incr(CATALOG_VERSION_KEY)
    except ValueError:
        cache.set(CATALOG_VERSION_KEY, 1, None)


def _catalog_version():
    return cache.get_or_set(CATALOG_VERSION_KEY, 1, None)


def get_carousel_products(section):
    """Resolve a section once, with relations and pricing loaded in batches."""
    key = f"site_sections:carousel:{section.pk}:v{_catalog_version()}"
    product_ids = cache.get(key)
    if product_ids is None:
        queryset = Product.objects.filter(is_active=True, brand__is_active=True, category__is_active=True)
        source = section.source_type
        if source == ProductCarouselSource.MANUAL:
            queryset = queryset.filter(pk__in=section.manual_products.values("pk")).order_by("name", "id")
        elif source == ProductCarouselSource.FEATURED:
            queryset = queryset.filter(featured_product=True)
        elif source == ProductCarouselSource.FLASH_SALE:
            queryset = queryset.filter(flash_sale_product=True)
        elif source == ProductCarouselSource.DEAL_OF_THE_DAY:
            queryset = queryset.filter(deal_of_the_day=True)
        elif source == ProductCarouselSource.RECOMMENDED:
            queryset = queryset.filter(recommended_product=True)
        elif source == ProductCarouselSource.CATEGORY:
            queryset = queryset.filter(category=section.category)
        elif source == ProductCarouselSource.BRAND:
            queryset = queryset.filter(brand=section.brand)
        elif source in {ProductCarouselSource.BEST_SELLING, ProductCarouselSource.TRENDING}:
            # These automatic rankings are intentionally not enabled yet.
            return []
        if source == ProductCarouselSource.LATEST:
            queryset = queryset.order_by("-created_at", "-id")
        elif source != ProductCarouselSource.MANUAL:
            queryset = queryset.order_by("-featured_product", "-created_at", "-id")
        product_ids = list(queryset.values_list("pk", flat=True)[:section.products_limit])
        cache.set(key, product_ids, 300)
    products = Product.objects.select_related("brand", "category", "subcategory").filter(pk__in=product_ids)
    indexed = {product.pk: product for product in products}
    return attach_pricing_to_products([indexed[pk] for pk in product_ids if pk in indexed])
