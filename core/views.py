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
from site_sections.models import HeroSection, HomepageSection
from site_sections.services import get_carousel_products

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

    # Fetching dynamic homepage sections
    homepage_dynamic_sections = (
        HomepageSection.objects.filter(is_active=True)
        .select_related("herosection")
        .order_by("display_order")
    )
    homepage_dynamic_sections = list(homepage_dynamic_sections)
    for section in homepage_dynamic_sections:
        if section.section_type == "product_carousel":
            carousel = section.get_section_instance()
            if carousel:
                carousel.products = get_carousel_products(carousel)

    # ==========================================
    # Product Carousel Data
    # ==========================================

    # Featured Products
    featured_products = _priced_products(
        _home_section_queryset().filter(featured_product=True)
    )

    # Popular Products (Most Viewed)
    popular_products = _priced_products(
        _home_section_queryset().order_by("-total_views")
    )

    # Latest Products
    latest_products = _priced_products(_home_section_queryset().order_by("-created_at"))

    # Best Rated Products
    best_rated_products = _priced_products(_home_section_queryset().order_by("-rating"))

    # This is for backward compatibility with templates
    # that might still use the old hero_section
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
        # Product Carousel
        "featured_products": featured_products,
        "popular_products": popular_products,
        "latest_products": latest_products,
        "best_rated_products": best_rated_products,
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
