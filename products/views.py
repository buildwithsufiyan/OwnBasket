import re
from decimal import Decimal
from urllib.parse import urlencode

from django.core.paginator import Paginator
from django.db.models import Case, F, IntegerField, Q, Value, When
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.utils.html import conditional_escape
from django.utils.safestring import mark_safe

from .models import Brand, BrandHeroBanner, Category, Product, SubCategory
from .pricing import attach_pricing_to_products


# 📌 Product Detail Page
def product_detail(request, slug):
    product = get_object_or_404(Product, slug=slug)
    Product.objects.filter(pk=product.pk).update(total_views=F('total_views') + 1, last_viewed_at=timezone.now())
    product.refresh_from_db()
    attach_pricing_to_products([product])

    recent_ids = request.session.get('recently_viewed_product_ids', [])
    recent_ids = [product_id for product_id in recent_ids if product_id != product.id]
    recent_ids.insert(0, product.id)
    request.session['recently_viewed_product_ids'] = recent_ids[:12]

    related_products = Product.objects.filter(
        category=product.category
    ).exclude(
        id=product.id
    )[:4]
    related_products = attach_pricing_to_products(related_products)

    return render(
        request,
        'products/product_detail.html',
        {
            'product': product,
            'related_products': related_products,
        }
    )


def _format_price(value):
    if value is None:
        return ""

    if isinstance(value, Decimal) and value == value.to_integral():
        return f"Rs. {int(value):,}"

    return f"Rs. {value:,.2f}"


def _get_search_query(request):
    return request.GET.get('q', '').strip()


def _highlight_text(text, query):
    if not text or not query:
        return text

    pattern = re.compile(re.escape(str(query)), re.IGNORECASE)
    source = str(text)
    result = []
    last_index = 0

    for match in pattern.finditer(source):
        result.append(conditional_escape(source[last_index:match.start()]))
        result.append(
            f"<mark class=\"search-highlight\">{conditional_escape(match.group(0))}</mark>"
        )
        last_index = match.end()

    result.append(conditional_escape(source[last_index:]))
    return mark_safe(''.join(result))


def _get_search_results(query):
    if not query:
        return (
            Product.objects.none(),
            Category.objects.none(),
            Brand.objects.none(),
        )

    product_filters = (
        Q(name__icontains=query) |
        Q(sku__icontains=query) |
        Q(barcode__icontains=query) |
        Q(short_description__icontains=query) |
        Q(description__icontains=query) |
        Q(brand__name__icontains=query) |
        Q(category__name__icontains=query) |
        Q(subcategory__name__icontains=query)
    )
    startswith_name = When(name__istartswith=query, then=Value(0))
    contains_name = When(name__icontains=query, then=Value(1))
    startswith_brand = When(brand__name__istartswith=query, then=Value(2))
    startswith_category = When(category__name__istartswith=query, then=Value(3))
    startswith_subcategory = When(subcategory__name__istartswith=query, then=Value(4))

    products = Product.objects.select_related('brand', 'category', 'subcategory').filter(
        product_filters,
        brand__is_active=True,
        category__is_active=True,
        is_active=True,
    ).annotate(
        search_rank=Case(
            startswith_name,
            contains_name,
            startswith_brand,
            startswith_category,
            startswith_subcategory,
            default=Value(5),
            output_field=IntegerField(),
        )
    ).order_by('search_rank', 'name', 'id').distinct()

    categories = Category.objects.filter(
        is_active=True,
        name__icontains=query,
    ).annotate(
        search_rank=Case(
            When(name__istartswith=query, then=Value(0)),
            default=Value(1),
            output_field=IntegerField(),
        )
    ).order_by('search_rank', 'sort_order', 'name', 'id')

    brands = Brand.objects.filter(
        is_active=True,
        name__icontains=query,
    ).annotate(
        search_rank=Case(
            When(name__istartswith=query, then=Value(0)),
            default=Value(1),
            output_field=IntegerField(),
        )
    ).order_by('search_rank', 'display_order', 'name', 'id')

    return products, categories, brands


def search_results(request):
    query = _get_search_query(request)
    products, categories, brands = _get_search_results(query)
    products = attach_pricing_to_products(products)
    categories = list(categories)
    brands = list(brands)

    for product in products:
        product.highlighted_name = _highlight_text(product.name, query)
        product.highlighted_category_name = _highlight_text(product.category.name, query)
        product.highlighted_brand_name = _highlight_text(product.brand.name, query)

    for category in categories:
        category.highlighted_name = _highlight_text(category.name, query)

    for brand in brands:
        brand.highlighted_name = _highlight_text(brand.name, query)

    context = {
        'query': query,
        'products': products,
        'categories': categories,
        'brands': brands,
        'has_results': bool(products or categories or brands),
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


def category_detail(request, slug):
    category = get_object_or_404(Category, slug=slug, is_active=True)
    subcategory_slug = request.GET.get('subcategory')
    products = Product.objects.select_related('brand', 'category', 'subcategory').filter(category=category, is_active=True)
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
    search_query = request.GET.get('q', '').strip()
    category_slug = request.GET.get('category', '').strip()
    subcategory_slug = request.GET.get('subcategory', '').strip()
    sort_by = request.GET.get('sort', 'featured').strip() or 'featured'

    products_queryset = Product.objects.select_related('brand', 'category', 'subcategory').filter(
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
        }
    )


def _build_live_search_payload(query):
    products, categories, brands = _get_search_results(query)
    products = attach_pricing_to_products(products)

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
    }


def live_search(request):
    query = _get_search_query(request)
    return JsonResponse(_build_live_search_payload(query))


def search_suggestions_api(request):
    query = _get_search_query(request)
    return JsonResponse(_build_live_search_payload(query))
