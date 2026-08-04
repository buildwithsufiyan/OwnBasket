import json
from decimal import Decimal
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, F, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from .forms import ProductReviewForm
from .models import (
    Brand, BrandHeroBanner, Category, CustomerExperienceSettings, Product,
    ProductFeature, ProductListingSettings, ProductReview, ProductReviewImage,
    ProductVariant, ReviewHelpfulVote, SubCategory,
)
from .highlighting import highlight_matches
from .listing import SORT_OPTIONS, build_product_listing
from .pricing import attach_pricing_to_products
from personalization.models import BehaviorEvent
from personalization.search import intelligent_search, popular_searches
from personalization.services import RecommendationService, frequently_bought_together, record_behavior, similar_products


# 📌 Product Detail Page
def product_detail(request, slug):
    experience = CustomerExperienceSettings.get_solo()
    approved_reviews = ProductReview.objects.filter(
        moderation_status=ProductReview.ModerationStatus.APPROVED, is_spam=False,
    ).select_related("user").prefetch_related('images')
    product = get_object_or_404(
        Product.objects.marketplace_visible().select_related("seller", "brand", "category", "subcategory").prefetch_related(
            "gallery", "variants", "features", "specifications", "custom_badges",
        ),
        slug=slug,
        is_active=True,
    )
    Product.objects.filter(pk=product.pk).update(total_views=F('total_views') + 1, last_viewed_at=timezone.now())
    product.total_views += 1
    record_behavior(request, BehaviorEvent.EventType.PRODUCT_VIEW, product=product, category=product.category, brand=product.brand)
    attach_pricing_to_products([product])

    recent_ids = request.session.get('recently_viewed_product_ids', [])
    recent_ids = [product_id for product_id in recent_ids if product_id != product.id]
    recent_ids.insert(0, product.id)
    request.session['recently_viewed_product_ids'] = recent_ids[:experience.recently_viewed_limit]

    related_products = similar_products(product, limit=experience.related_products_limit)
    bought_together_products = frequently_bought_together(product, limit=experience.bought_together_limit)
    bought_together_is_fallback = False
    if not bought_together_products and experience.allow_bought_together_fallback:
        bought_together_products = related_products[:experience.bought_together_limit]
        bought_together_is_fallback = bool(bought_together_products)
    recommendations = RecommendationService(request)
    recently_viewed_products = [item for item in recommendations.recently_viewed(experience.recently_viewed_limit + 1) if item.pk != product.pk][:experience.recently_viewed_limit]

    reviews = approved_reviews.filter(product=product)
    reviews_paginator = Paginator(reviews, experience.reviews_per_page)
    reviews_page = reviews_paginator.get_page(request.GET.get('review_page'))
    distribution_rows = {row['rating']: row['total'] for row in reviews.values('rating').annotate(total=Count('id'))}
    approved_total = sum(distribution_rows.values())
    rating_distribution = [
        {'stars': stars, 'count': distribution_rows.get(stars, 0), 'percentage': round(distribution_rows.get(stars, 0) * 100 / approved_total) if approved_total else 0}
        for stars in range(5, 0, -1)
    ]
    can_review = False
    own_review = None
    if request.user.is_authenticated:
        from orders.models import OrderItem
        can_review = OrderItem.objects.filter(
            order__user=request.user, order__status='Delivered', product=product,
        ).exists()
        own_review = ProductReview.objects.filter(product=product, user=request.user).first()

    canonical_url = request.build_absolute_uri(product.get_absolute_url())
    image_url = request.build_absolute_uri(product.image.url) if product.image else ""
    availability = "https://schema.org/InStock" if product.stock > 0 or product.allow_backorder else "https://schema.org/OutOfStock"
    product_schema = {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": product.name,
        "description": product.short_description or product.description,
        "sku": product.sku or "",
        "url": canonical_url,
        "brand": {"@type": "Brand", "name": product.brand.name},
        "offers": {
            "@type": "Offer", "url": canonical_url, "priceCurrency": "PKR",
            "price": str(product.display_price), "availability": availability,
        },
    }
    if image_url:
        product_schema["image"] = [image_url]
    if product.reviews_count and product.rating:
        product_schema["aggregateRating"] = {
            "@type": "AggregateRating", "ratingValue": str(product.rating),
            "reviewCount": product.reviews_count,
        }
    breadcrumb_schema = {
        "@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": request.build_absolute_uri("/")},
            {"@type": "ListItem", "position": 2, "name": product.category.name, "item": request.build_absolute_uri(product.category.target_url)},
            {"@type": "ListItem", "position": 3, "name": product.name, "item": canonical_url},
        ],
    }
    safe_json = lambda data: json.dumps(data, ensure_ascii=False).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    return render(
        request,
        'products/product_detail.html',
        {
            'product': product,
            'related_products': related_products,
            'bought_together_products': bought_together_products,
            'bought_together_is_fallback': bought_together_is_fallback,
            'recently_viewed_products': recently_viewed_products,
            'reviews_page': reviews_page,
            'rating_distribution': rating_distribution,
            'review_form': ProductReviewForm(instance=own_review, minimum_characters=experience.review_minimum_characters),
            'can_review': can_review,
            'own_review': own_review,
            'compare_ids': request.session.get('compare_product_ids', []),
            'canonical_url': canonical_url,
            'social_image': image_url,
            'product_json_ld': safe_json(product_schema),
            'breadcrumb_json_ld': safe_json(breadcrumb_schema),
        }
    )


@login_required
@require_POST
def submit_review(request, slug):
    experience = CustomerExperienceSettings.get_solo()
    product = get_object_or_404(Product.objects.marketplace_visible(), slug=slug, is_active=True)
    from orders.models import OrderItem
    verified = OrderItem.objects.filter(
        order__user=request.user, order__status='Delivered', product=product,
    ).exists()
    if not verified:
        messages.error(request, 'Only customers with a delivered order can review this product.')
        return redirect(product.get_absolute_url() + '#reviews')
    review = ProductReview.objects.filter(product=product, user=request.user).first()
    form = ProductReviewForm(
        request.POST, instance=review, minimum_characters=experience.review_minimum_characters,
    )
    images = request.FILES.getlist('images')
    existing_images = review.images.count() if review else 0
    if existing_images + len(images) > experience.max_review_images:
        form.add_error(None, f'Upload at most {experience.max_review_images} review images.')
    allowed_types = {'image/jpeg', 'image/png', 'image/webp'}
    for image in images:
        if image.size > 5 * 1024 * 1024 or image.content_type not in allowed_types:
            form.add_error(None, 'Review images must be JPG, PNG or WebP and no larger than 5 MB.')
            break
    if not form.is_valid():
        messages.error(request, 'Please correct the review errors and try again.')
        request.session['review_form_errors'] = form.errors.get_json_data()
        return redirect(product.get_absolute_url() + '#review-form')
    with transaction.atomic():
        review = form.save(commit=False)
        review.product = product
        review.user = request.user
        review.verified_purchase = True
        review.is_spam = False
        review.moderation_status = ProductReview.ModerationStatus.PENDING
        review.moderation_notes = ''
        review.moderated_by = None
        review.moderated_at = None
        review.save()
        for image in images:
            ProductReviewImage.objects.create(review=review, image=image, alt_text=f'Review image for {product.name}')
    messages.success(request, 'Your verified-purchase review was submitted for moderation.')
    return redirect(product.get_absolute_url() + '#reviews')


@login_required
@require_POST
def delete_review(request, review_id):
    review = get_object_or_404(ProductReview.objects.select_related('product'), pk=review_id, user=request.user)
    url = review.product.get_absolute_url() + '#reviews'
    review.delete()
    messages.success(request, 'Your review was deleted.')
    return redirect(url)


@login_required
@require_POST
def helpful_review(request, review_id):
    review = get_object_or_404(
        ProductReview, pk=review_id, moderation_status=ProductReview.ModerationStatus.APPROVED,
    )
    if review.user_id == request.user.id:
        messages.info(request, 'You cannot vote on your own review.')
    else:
        _, created = ReviewHelpfulVote.objects.get_or_create(review=review, user=request.user)
        if created:
            ProductReview.objects.filter(pk=review.pk).update(helpful_count=F('helpful_count') + 1)
    return redirect(review.product.get_absolute_url() + '#reviews')


@require_POST
def compare_add(request, product_id):
    product = get_object_or_404(Product.objects.marketplace_visible(), pk=product_id, is_active=True)
    limit = CustomerExperienceSettings.get_solo().compare_limit
    ids = [int(pk) for pk in request.session.get('compare_product_ids', []) if str(pk).isdigit()]
    if product.pk not in ids:
        if len(ids) >= limit:
            messages.error(request, f'You can compare up to {limit} products.')
        else:
            ids.append(product.pk)
            request.session['compare_product_ids'] = ids
            messages.success(request, f'{product.name} added to comparison.')
    return redirect('products:compare')


@require_POST
def compare_remove(request, product_id):
    ids = [int(pk) for pk in request.session.get('compare_product_ids', []) if str(pk).isdigit()]
    request.session['compare_product_ids'] = [pk for pk in ids if pk != product_id]
    return redirect('products:compare')


def compare_products(request):
    limit = CustomerExperienceSettings.get_solo().compare_limit
    ids = [int(pk) for pk in request.session.get('compare_product_ids', []) if str(pk).isdigit()][:limit]
    by_id = {
        product.pk: product for product in Product.objects.marketplace_visible().filter(
            pk__in=ids, is_active=True,
        ).select_related('brand', 'category', 'subcategory').prefetch_related('specifications', 'features')
    }
    products = [by_id[pk] for pk in ids if pk in by_id]
    attach_pricing_to_products(products)
    request.session['compare_product_ids'] = [product.pk for product in products]
    spec_names = sorted({spec.name for product in products for spec in product.specifications.all()})
    for product in products:
        product.comparison_specs = {spec.name: spec.value for spec in product.specifications.all()}
    return render(request, 'products/compare.html', {'products': products, 'spec_names': spec_names, 'compare_limit': limit})


def _format_price(value):
    if value is None:
        return ""

    if isinstance(value, Decimal) and value == value.to_integral():
        return f"Rs. {int(value):,}"

    return f"Rs. {value:,.2f}"


def _get_search_query(request):
    return request.GET.get('q', '').strip()


def search_results(request):
    query = _get_search_query(request)
    result = intelligent_search(query)
    products = attach_pricing_to_products(result.products)
    categories = result.categories
    brands = result.brands
    if query:
        record_behavior(request, BehaviorEvent.EventType.SEARCH, search_term=query)
    highlight_query = result.corrected_query or query

    for product in products:
        product.highlighted_name = highlight_matches(product.name, highlight_query)
        product.highlighted_category_name = highlight_matches(product.category.name, highlight_query)
        product.highlighted_brand_name = highlight_matches(product.brand.name, highlight_query)

    for category in categories:
        category.highlighted_name = highlight_matches(category.name, highlight_query)

    for brand in brands:
        brand.highlighted_name = highlight_matches(brand.name, highlight_query)

    context = {
        'query': query,
        'products': products,
        'categories': categories,
        'brands': brands,
        'corrected_query': result.corrected_query,
        'popular_searches': popular_searches(),
        'has_results': bool(products or categories or brands),
        'canonical_url': request.build_absolute_uri(request.path),
    }
    return render(request, 'products/search_results.html', context)


def category_list(request):
    categories = Category.objects.filter(is_active=True).order_by('sort_order', 'name', 'id')

    return render(
        request,
        'products/category_list.html',
        {
            'categories': categories,
        }
    )


def product_list(request):
    settings = ProductListingSettings.get_solo()
    queryset, query, selected_sort, filter_querystring = build_product_listing(request, settings.default_sort)
    paginator = Paginator(queryset, settings.products_per_page)
    page_obj = paginator.get_page(request.GET.get("page"))
    products = attach_pricing_to_products(list(page_obj.object_list))
    page_obj.object_list = products
    return render(request, "products/product_list.html", {
        "products": products, "page_obj": page_obj, "paginator": paginator,
        "page_range": paginator.get_elided_page_range(page_obj.number), "total_products": paginator.count,
        "categories": Category.objects.filter(is_active=True).order_by("sort_order", "name", "id"),
        "subcategories": SubCategory.objects.filter(is_active=True).select_related('category').order_by('category__name', 'sort_order', 'name'),
        "brands": Brand.objects.filter(is_active=True).order_by("display_order", "name", "id"),
        "colors": ProductVariant.objects.filter(variant_name__iexact='color').values_list('variant_value', flat=True).distinct().order_by('variant_value'),
        "sizes": ProductVariant.objects.filter(variant_name__iexact='size').values_list('variant_value', flat=True).distinct().order_by('variant_value'),
        "tags": ProductFeature.objects.values_list('feature', flat=True).distinct().order_by('feature')[:50],
        "query": query, "selected_sort": selected_sort, "sort_options": SORT_OPTIONS,
        "filter_querystring": filter_querystring, "listing_settings": settings,
        "canonical_url": request.build_absolute_uri(request.path),
        "selected_brand_ids": request.GET.getlist("brand"),
        "selected_colors": request.GET.getlist('color'), "selected_sizes": request.GET.getlist('size'),
        "selected_tags": request.GET.getlist('tag'),
    })


def category_detail(request, slug):
    category = get_object_or_404(Category, slug=slug, is_active=True)
    record_behavior(request, BehaviorEvent.EventType.CATEGORY_VIEW, category=category)
    subcategory_slug = request.GET.get('subcategory')
    products = Product.objects.marketplace_visible().select_related('seller', 'brand', 'category', 'subcategory').filter(category=category, is_active=True)
    selected_subcategory = None
    if subcategory_slug:
        products = products.filter(subcategory__slug=subcategory_slug)
        selected_subcategory = SubCategory.objects.filter(category=category, slug=subcategory_slug, is_active=True).first()
    products = attach_pricing_to_products(products)

    return render(
        request,
        'products/category_detail.html',
        {
            'category': category,
            'selected_subcategory': selected_subcategory,
            'products': products,
            'categories': Category.objects.filter(is_active=True).order_by('sort_order', 'name', 'id'),
            'subcategories': category.subcategories.filter(is_active=True).order_by('sort_order', 'name', 'id'),
            'canonical_url': request.build_absolute_uri(request.path),
        }
    )


def brand_list(request):
    brands = Brand.objects.filter(is_active=True).order_by('display_order', 'name', 'id')

    return render(
        request,
        'products/brand_list.html',
        {
            'brands': brands,
        }
    )


def brand_detail(request, pk):
    brand = get_object_or_404(Brand, pk=pk, is_active=True)
    record_behavior(request, BehaviorEvent.EventType.BRAND_VIEW, brand=brand)
    search_query = request.GET.get('q', '').strip()
    category_slug = request.GET.get('category', '').strip()
    subcategory_slug = request.GET.get('subcategory', '').strip()
    sort_by = request.GET.get('sort', 'featured').strip() or 'featured'

    products_queryset = Product.objects.marketplace_visible().select_related('seller', 'brand', 'category', 'subcategory').filter(
        brand=brand,
        is_active=True,
    )

    if search_query:
        products_queryset = products_queryset.filter(
            Q(name__icontains=search_query) |
            Q(short_description__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(category__name__icontains=search_query) |
            Q(subcategory__name__icontains=search_query)
        )

    selected_category = None
    if category_slug:
        selected_category = Category.objects.filter(
            slug=category_slug,
            product__brand=brand,
            product__is_active=True,
        ).distinct().first()
        if selected_category:
            products_queryset = products_queryset.filter(category=selected_category)

    selected_subcategory = None
    if subcategory_slug:
        selected_subcategory = SubCategory.objects.filter(
            slug=subcategory_slug,
            products__brand=brand,
            products__is_active=True,
        ).distinct().first()
        if selected_subcategory:
            products_queryset = products_queryset.filter(subcategory=selected_subcategory)

    sort_options = {
        'featured': ('-featured_product', '-flash_sale_product', '-created_at', '-id'),
        'latest': ('-created_at', '-id'),
        'price_low': ('price', 'id'),
        'price_high': ('-price', '-id'),
        'name_asc': ('name', 'id'),
        'popular': ('-total_views', '-id'),
    }
    products_queryset = products_queryset.order_by(*sort_options.get(sort_by, sort_options['featured']))

    paginator = Paginator(products_queryset, 12)
    page_obj = paginator.get_page(request.GET.get('page'))
    products = attach_pricing_to_products(list(page_obj.object_list))
    page_obj.object_list = products
    page_range = paginator.get_elided_page_range(page_obj.number)

    brand_hero_banners = list(
        BrandHeroBanner.objects.filter(
            brand=brand,
            is_active=True,
        ).order_by('display_order', 'id')
    )

    available_categories = Category.objects.filter(
        product__brand=brand,
        product__is_active=True,
    ).distinct().order_by('sort_order', 'name', 'id')
    available_subcategories = SubCategory.objects.filter(
        products__brand=brand,
        products__is_active=True,
    ).distinct().order_by('category__name', 'sort_order', 'name', 'id')

    query_params = request.GET.copy()
    query_params.pop('page', None)
    filter_querystring = urlencode([(key, value) for key, values in query_params.lists() for value in values])

    return render(
        request,
        'products/brand_detail.html',
        {
            'brand': brand,
            'products': products,
            'page_obj': page_obj,
            'paginator': paginator,
            'page_range': page_range,
            'total_products': paginator.count,
            'brands': Brand.objects.filter(is_active=True).order_by('display_order', 'name', 'id'),
            'brand_hero_banners': brand_hero_banners,
            'available_categories': available_categories,
            'available_subcategories': available_subcategories,
            'selected_category': selected_category,
            'selected_subcategory': selected_subcategory,
            'selected_sort': sort_by,
            'search_query': search_query,
            'filter_querystring': filter_querystring,
            'canonical_url': request.build_absolute_uri(request.path),
        }
    )


def _build_live_search_payload(query):
    result = intelligent_search(query, product_limit=20)
    products = attach_pricing_to_products(result.products)
    categories = result.categories
    brands = result.brands

    product_results = [
        {
            "name": product.name,
            "category_name": product.category.name,
            "brand_name": product.brand.name,
            "price": _format_price(product.display_price),
            "old_price": _format_price(product.display_compare_price) if product.display_compare_price else "",
            "badge": product.display_badge,
            "image": product.image.url if product.image else "",
            "url": product.get_absolute_url() if hasattr(product, 'get_absolute_url') else f"/product/{product.slug}/",
        }
        for product in products[:5]
    ]
    category_results = [
        {
            "name": category.name,
            "image": category.category_image.url if category.category_image else "",
            "url": category.target_url,
        }
        for category in categories[:3]
    ]
    brand_results = [
        {
            "name": brand.name,
            "image": brand.logo.url if brand.logo else "",
            "url": brand.target_url,
        }
        for brand in brands[:3]
    ]

    return {
        "query": query,
        "products": product_results,
        "categories": category_results,
        "brands": brand_results,
        "has_results": bool(product_results or category_results or brand_results),
        "corrected_query": result.corrected_query,
        "popular_searches": popular_searches(6) if not query else [],
    }


@require_GET
def live_search(request):
    query = _get_search_query(request)
    return JsonResponse(_build_live_search_payload(query))


@require_GET
def search_suggestions_api(request):
    query = _get_search_query(request)
    return JsonResponse(_build_live_search_payload(query))
