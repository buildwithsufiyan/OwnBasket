from django.conf import settings
from django.db import connections
import json
from urllib.parse import urlparse

from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.db.models import F, Q, Prefetch
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from core.http import safe_redirect_target
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
from personalization.services import RecommendationService, trending_products

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
        Product.objects.marketplace_visible().select_related("seller", "brand", "category", "subcategory").filter(
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
    return Product.objects.marketplace_visible().select_related("seller", "brand", "category", "subcategory").filter(
        is_active=True
    )


def _priced_products(queryset, limit=12):
    return attach_pricing_to_products(queryset[:limit])


def home(request):
    category_slug = request.GET.get("category")
    brand_id = request.GET.get("brand")
    subcategory_slug = request.GET.get("subcategory")
    query = request.GET.get("q")

    products = Product.objects.marketplace_visible().select_related(
        "seller", "brand", "category", "subcategory"
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

    recommendations = RecommendationService(request)
    recommendations_personalized = recommendations.has_signals()
    recently_viewed_products = recommendations.recently_viewed(limit=12)
    recommended_products = recommendations.recommended(limit=12)
    personalized_offers = recommendations.personalized_offers(limit=8) if request.user.is_authenticated else []
    favorite_brands = recommendations.favorite_brands(limit=4) if request.user.is_authenticated else []
    suggested_categories = recommendations.suggested_categories(limit=4) if request.user.is_authenticated else []
    guest_trending_products = trending_products(hours=168, limit=12) if not request.user.is_authenticated else []
    guest_best_sellers = _priced_products(_home_section_queryset().order_by('-total_sold', '-total_views'), limit=12) if not request.user.is_authenticated else []
    guest_popular_categories = []
    if guest_trending_products:
        guest_popular_categories = list({item.category_id: item.category for item in guest_trending_products}.values())[:4]

    # This is for backward compatibility with templates
    # that might still use the old hero_section
    if not any(s.section_type == "hero" for s in homepage_dynamic_sections):
        hero_section = None

    base_url = request.build_absolute_uri("/").rstrip("/")
    home_schema = [
        {"@context": "https://schema.org", "@type": "Organization", "name": settings.SITE_NAME, "url": base_url, "logo": request.build_absolute_uri("/static/images/logo.png")},
        {"@context": "https://schema.org", "@type": "WebSite", "name": settings.SITE_NAME, "url": base_url, "potentialAction": {"@type": "SearchAction", "target": f"{base_url}/search/?q={{search_term_string}}", "query-input": "required name=search_term_string"}},
    ]
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
        "recently_viewed_products": recently_viewed_products,
        "recommended_products": recommended_products,
        "recommendations_personalized": recommendations_personalized,
        "personalized_offers": personalized_offers,
        "favorite_brands": favorite_brands,
        "suggested_categories": suggested_categories,
        "guest_trending_products": guest_trending_products,
        "guest_best_sellers": guest_best_sellers,
        "guest_popular_categories": guest_popular_categories,
        "home_json_ld": json.dumps(home_schema).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026"),
    }

    return render(request, "core/home.html", context)


def landing(request):
    return render(request, "landing.html")


@require_GET
def health(request):
    """Fast, non-sensitive readiness response for monitors and load balancers."""
    status = "ok"
    http_status = 200
    if request.GET.get("database") == "1":
        try:
            connections["default"].ensure_connection()
        except Exception:
            status, http_status = "degraded", 503
    return JsonResponse({"status": status}, status=http_status)


@require_GET
def robots_txt(request):
    lines = [
        "User-agent: *",
        "Allow: /",
        "Disallow: /admin/",
        "Disallow: /account/",
        "Disallow: /checkout/",
        "Disallow: /cart/",
        "Disallow: /wishlist/",
        "Disallow: /theme-assets/",
        "Disallow: /api/",
        f"Sitemap: {settings.CANONICAL_BASE_URL}/sitemap.xml",
    ]
    return HttpResponse("\n".join(lines) + "\n", content_type="text/plain; charset=utf-8")


def error_400(request, exception):
    return render(request, "errors/400.html", status=400)


def error_403(request, exception):
    return render(request, "errors/403.html", status=403)


def error_404(request, exception):
    return render(request, "errors/404.html", status=404)


def error_500(request):
    return render(request, "errors/500.html", status=500)


@require_GET
def track_banner_click(request, banner_id):
    banner = get_object_or_404(BannerCarousel, pk=banner_id)
    BannerCarousel.objects.filter(pk=banner.pk).update(
        clicks_count=F("clicks_count") + 1
    )
    target_url = safe_redirect_target(
        request,
        request.GET.get("next", ""),
        banner.button_url or "/home/",
        extra_hosts=(urlparse(banner.button_url or "").hostname,),
    )
    return redirect(target_url)


@csrf_exempt
@require_POST
def track_banner_view(request, banner_id):
    updated = BannerCarousel.objects.filter(pk=banner_id, is_active=True).update(
        views_count=F("views_count") + 1
    )
    return JsonResponse({"tracked": bool(updated)})
