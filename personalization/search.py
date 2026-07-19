from dataclasses import dataclass
from difflib import get_close_matches
from functools import reduce
from operator import or_

from django.core.cache import cache
from django.db.models import Count, Q
from django.utils import timezone
from datetime import timedelta

from products.models import Brand, Category, Product

from .models import BehaviorEvent, SearchSynonym
from .services import sanitize_search_term, visible_products


@dataclass
class SearchResults:
    query: str
    products: list
    categories: list
    brands: list
    corrected_query: str = ''


def _synonym_terms(query):
    rows = cache.get('personalization:search-synonyms')
    if rows is None:
        rows = list(SearchSynonym.objects.filter(is_active=True).values_list('canonical_term', 'alternatives'))
        cache.set('personalization:search-synonyms', rows, 600)
    terms = [query]
    lowered = query.lower()
    for canonical, alternatives in rows:
        group = [sanitize_search_term(canonical)] + [sanitize_search_term(item) for item in alternatives if isinstance(item, str)]
        group = [item for item in group if item]
        if lowered in group:
            terms.extend(group)
    return list(dict.fromkeys(terms))[:12]


def _vocabulary():
    vocabulary = cache.get('personalization:search-vocabulary')
    if vocabulary is None:
        vocabulary = list(Product.objects.filter(is_active=True).values_list('name', flat=True)[:4000])
        vocabulary += list(Category.objects.filter(is_active=True).values_list('name', flat=True)[:500])
        vocabulary += list(Brand.objects.filter(is_active=True).values_list('name', flat=True)[:500])
        vocabulary = list(dict.fromkeys(item.strip().lower() for item in vocabulary if item.strip()))
        cache.set('personalization:search-vocabulary', vocabulary, 600)
    return vocabulary


def _correction(query):
    matches = get_close_matches(query.lower(), _vocabulary(), n=1, cutoff=.72)
    if matches and matches[0] != query.lower():
        return matches[0]
    return ''


def _product_score(product, terms):
    name, brand, category = product.name.lower(), product.brand.name.lower(), product.category.name.lower()
    subcategory = product.subcategory.name.lower() if product.subcategory_id else ''
    score = 0
    for term in terms:
        term = term.lower()
        if name == term:
            score = max(score, 100)
        elif name.startswith(term):
            score = max(score, 85)
        elif term in name:
            score = max(score, 70)
        elif brand.startswith(term):
            score = max(score, 55)
        elif category.startswith(term) or subcategory.startswith(term):
            score = max(score, 50)
        elif term in product.short_description.lower():
            score = max(score, 35)
        else:
            score = max(score, 20)
    return score + min(product.total_sold, 1000) * .02 + min(product.total_views, 10000) * .001 + float(product.rating or 0)


def intelligent_search(query, *, product_limit=100):
    query = sanitize_search_term(query)
    if not query:
        return SearchResults(query='', products=[], categories=[], brands=[])
    terms = _synonym_terms(query)

    def product_filter(term):
        return (
            Q(name__icontains=term) | Q(sku__icontains=term) | Q(barcode__icontains=term)
            | Q(short_description__icontains=term) | Q(description__icontains=term)
            | Q(brand__name__icontains=term) | Q(category__name__icontains=term)
            | Q(subcategory__name__icontains=term)
        )

    product_query = reduce(or_, (product_filter(term) for term in terms))
    products = list(visible_products().filter(product_query).distinct()[:product_limit])
    corrected_query = ''
    if not products:
        corrected_query = _correction(query)
        if corrected_query:
            terms = _synonym_terms(corrected_query)
            product_query = reduce(or_, (product_filter(term) for term in terms))
            products = list(visible_products().filter(product_query).distinct()[:product_limit])
    products.sort(key=lambda product: (_product_score(product, terms), -product.pk), reverse=True)

    category_query = reduce(or_, (Q(name__icontains=term) for term in terms))
    brand_query = reduce(or_, (Q(name__icontains=term) for term in terms))
    categories = list(Category.objects.filter(is_active=True).filter(category_query).order_by('sort_order', 'name')[:20])
    brands = list(Brand.objects.filter(is_active=True).filter(brand_query).order_by('display_order', 'name')[:20])
    return SearchResults(
        query=query, products=products, categories=categories, brands=brands,
        corrected_query=corrected_query,
    )


def popular_searches(limit=8):
    cache_key = f'personalization:popular-searches:{limit}'
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    since = timezone.now() - timedelta(days=30)
    rows = list(
        BehaviorEvent.objects.filter(
            event_type=BehaviorEvent.EventType.SEARCH, created_at__gte=since,
        ).exclude(search_term='').values('search_term').annotate(total=Count('id')).order_by('-total', 'search_term')[:limit]
    )
    results = [row['search_term'] for row in rows]
    cache.set(cache_key, results, 300)
    return results
