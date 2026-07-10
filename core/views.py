from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.db.models import F, Q, Prefetch
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from products.models import Brand, Category, Product
from products.pricing import attach_pricing_to_products
from banners.models import (
    BannerCarousel,
    HomepageCarousel,
    HomepageSettings,
    HomepageFeature,
)
from site_sections.models import (
    HeroSection,
    HomepageSection,
    ProductCarouselSection,
)

DEFAULT_HOME_FEATURES = [
    {
        "icon": "bi-truck",
        "title": "Free Delivery",
        "description": "On all orders",
    },
    {
        "icon": "bi-shield-check",
        "title": "Secure Payment",
        "description": "100% protected",
    },
    {
        "icon": "bi-arrow-repeat",
        "title": "Easy Returns",
        "description": "Hassle free",
    },
    {
        "icon": "bi-headset",
        "title": "24/7 Support",
        "description": "Always here for you",
    },
]


def _get_recently_viewed_products(request):
    recent_ids = request.session.get("recently_viewed_product_ids", [])[:8]
    if not recent_ids:
        return []
    products = list(
        Product.objects.select_related("brand", "category", "subcategory").filter(
            id__in=recent_ids, is_active=True
        )
    )
    products_by_id = {
        product.id: product for product in attach_pricing_to_products(products)
    }
    return [
        products_by_id[product_id]
        for product_id in recent_ids
        if product_id in products_by_id
    ]


def _home_section_queryset():
    return Product.objects.select_related("brand", "category", "subcategory").filter(
        is_active=True
    )


def _priced_products(queryset, limit=12):
    return attach_pricing_to_products(queryset[:limit])


def home(request):
    category_slug = request.GET.get("category")
    brand_id = request.GET.get("brand")
    subcategory_slug = request.GET.get("subcategory")
    query = request.GET.get("q")

    products = Product.objects.select_related("brand", "category").all()
    products = Product.objects.select_related(
        "brand", "category", "subcategory"
    ).filter(is_active=True)

    if category_slug:
        products = products.filter(category__slug=category_slug)
        selected_category = Category.objects.filter(slug=category_slug).first()
    else:
        selected_category = None

    if subcategory_slug:
        products = products.filter(subcategory__slug=subcategory_slug)
        selected_subcategory = (
            products.first().subcategory if products.exists() else None
        )
    else:
        selected_subcategory = None

    if brand_id:
        products = products.filter(brand_id=brand_id)
        selected_brand = Brand.objects.filter(pk=brand_id).first()
    else:
        selected_brand = None

    if query:
        products = products.filter(
            Q(name__icontains=query)
            | Q(sku__icontains=query)
            | Q(barcode__icontains=query)
            | Q(brand__name__icontains=query)
            | Q(category__name__icontains=query)
            | Q(subcategory__name__icontains=query)
            | Q(description__icontains=query)
        )

    homepage_settings = HomepageSettings.get_solo()
    homepage_carousels = list(
        HomepageCarousel.objects.filter(is_active=True).order_by(
            "display_order", "created_at", "id"
        )
    )
    banner_carousels = list(
        BannerCarousel.objects.filter(is_active=True).order_by(
            "display_order", "created_at", "id"
        )
    )
    homepage_features = list(
        HomepageFeature.objects.filter(is_active=True).order_by("display_order", "id")
    )
    homepage_categories = list(
        Category.objects.filter(is_active=True).order_by("sort_order", "name", "id")[:4]
    )

    hero_section = (
        HeroSection.objects.filter(is_active=True)
        .order_by("display_order", "created_at", "id")
        .first()
    )
    top_brands = list(
        Brand.objects.filter(is_active=True).order_by("display_order", "name", "id")[:4]
    )
    products = attach_pricing_to_products(products)
    section_products = _home_section_queryset()
    popular_products = _priced_products(
        section_products.order_by("-total_views", "-wishlist_count", "-id")
    )
    best_rated_products = _priced_products(
        section_products.order_by("-rating", "-reviews_count", "-id")
    )
    featured_products = _priced_products(
        section_products.filter(featured_product=True).order_by("-created_at", "-id")
    )
    latest_products = _priced_products(section_products.order_by("-created_at", "-id"))
    top_deal_products = _priced_products(
        section_products.filter(
            Q(flash_sale_product=True)
            | Q(deal_of_the_day=True)
            | Q(discount_price__isnull=False)
            | Q(old_price__isnull=False)
            | Q(mrp__isnull=False)
        )
        .distinct()
        .order_by("-flash_sale_product", "-deal_of_the_day", "-created_at", "-id")
    )
    product_carousel_sections = [
        {
            "id": "popular",
            "title": "Popular",
            "subtitle": "Most viewed picks shoppers keep coming back to.",
            "products": popular_products,
        },
        {
            "id": "best-rated",
            "title": "Best Rated",
            "subtitle": "Highly rated products with strong customer feedback.",
            "products": best_rated_products,
        },
        {
            "id": "featured-products",
            "title": "Featured Products",
            "subtitle": "Curated highlights from the catalog.",
            "products": featured_products,
        },
        {
            "id": "latest-products",
            "title": "Latest Products",
            "subtitle": "Fresh arrivals added most recently.",
            "products": latest_products,
        },
        {
            "id": "top-deals",
            "title": "Top Deals",
            "subtitle": "Sale, flash-sale, and deal products in one place.",
            "products": top_deal_products,
            "accent": True,
        },
    ]

    # Fetching dynamic homepage sections
    product_carousel_prefetch = Prefetch(
        "productcarouselsection",
        queryset=ProductCarouselSection.objects.prefetch_related(
            "manual_products", "category", "brand"
        ),
    )
    homepage_dynamic_sections = (
        HomepageSection.objects.filter(is_active=True)
        .select_related("herosection")
        .prefetch_related(product_carousel_prefetch)
        .order_by("display_order")
    )

    # Attach products to each product carousel section
    now = timezone.now()
    for section in homepage_dynamic_sections:
        instance = section.get_section_instance()
        if isinstance(instance, ProductCarouselSection):
            limit = instance.products_limit
            source_type = instance.source_type
            qs = Product.objects.none()

            if source_type == ProductCarouselSection.SourceType.MANUAL:
                # Products are already prefetched via manual_products
                product_list = list(instance.manual_products.filter(is_active=True))
                instance.products = attach_pricing_to_products(product_list[:limit])
                continue

            base_qs = Product.objects.select_related(
                "brand", "category", "subcategory"
            ).filter(is_active=True)

            if source_type == ProductCarouselSection.SourceType.FEATURED:
                qs = base_qs.filter(featured_product=True).order_by(
                    "-created_at", "-id"
                )
            elif source_type == ProductCarouselSection.SourceType.FLASH_SALE:
                qs = (
                    base_qs.filter(
                        Q(flash_sale_product=True)
                        | Q(discount_price__isnull=False, offer_end_at__gte=now)
                    )
                    .distinct()
                    .order_by("-offer_end_at", "-created_at", "-id")
                )
            elif source_type == ProductCarouselSection.SourceType.LATEST:
                qs = base_qs.order_by("-created_at", "-id")
            elif source_type == ProductCarouselSection.SourceType.BEST_SELLING:
                qs = base_qs.order_by("-total_sold", "-id")
            elif source_type == ProductCarouselSection.SourceType.TRENDING:
                qs = base_qs.order_by("-total_views", "-id")
            elif (
                source_type == ProductCarouselSection.SourceType.CATEGORY
                and instance.category
            ):
                qs = base_qs.filter(category=instance.category).order_by(
                    "-created_at", "-id"
                )
            elif (
                source_type == ProductCarouselSection.SourceType.BRAND
                and instance.brand
            ):
                qs = base_qs.filter(brand=instance.brand).order_by("-created_at", "-id")

            # Attach prices and set it on the instance
            instance.products = attach_pricing_to_products(qs[:limit])

    # This is for backward compatibility with templates that might still use the old hero_section
    if not any(s.section_type == "hero" for s in homepage_dynamic_sections):
        hero_section = None

    context = {
        "products": products,
        "selected_category": selected_category,
        "selected_subcategory": selected_subcategory,
        "selected_brand": selected_brand,
        "search_query": query,
        "homepage_settings": homepage_settings,
        "homepage_carousels": homepage_carousels,
        "banner_carousels": banner_carousels,
        "homepage_features": homepage_features or DEFAULT_HOME_FEATURES,
        "homepage_categories": homepage_categories,
        "top_brands": top_brands,
        "home_page_url": reverse("home"),
        "homepage_dynamic_sections": homepage_dynamic_sections,
        "hero_section": hero_section,
        "popular_products": popular_products,
        "best_rated_products": best_rated_products,
        "featured_products": featured_products,
        "latest_products": latest_products,
        "top_deal_products": top_deal_products,
        "product_carousel_sections": product_carousel_sections,
    }
    return render(request, "core/home.html", context)


def landing(request):
    return render(request, "landing.html")


@require_GET
def track_banner_click(request, banner_id):
    banner = get_object_or_404(BannerCarousel, pk=banner_id)
    BannerCarousel.objects.filter(pk=banner.pk).update(
        clicks_count=F("clicks_count") + 1
    )
    target_url = request.GET.get("next") or banner.button_url or "/home/"
    return redirect(target_url)


@csrf_exempt
@require_POST
def track_banner_view(request, banner_id):
    updated = BannerCarousel.objects.filter(pk=banner_id, is_active=True).update(
        views_count=F("views_count") + 1
    )
    return JsonResponse({"tracked": bool(updated)})
