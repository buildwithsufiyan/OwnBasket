from django.shortcuts import get_object_or_404

from personalization.models import BehaviorEvent
from personalization.search import intelligent_search, popular_searches
from personalization.services import (
    RecommendationService, frequently_bought_together, record_behavior,
    similar_products, trending_products, visible_products,
)

from .http import ApiError, api_endpoint, paginated, positive_int
from .serializers import product_data


@api_endpoint()
def recommendations(request):
    service = RecommendationService(request)
    has_signals = service.has_signals()
    products = service.recommended(limit=24)
    return {
        'results': [product_data(request, product) for product in products],
        'personalized': has_signals,
        'fallback': not has_signals,
    }


@api_endpoint(public_cache_seconds=60)
def trending(request):
    hours = positive_int(request.GET.get('hours'), name='hours', default=168)
    if hours not in (24, 168, 720):
        raise ApiError('validation_error', 'hours must be 24, 168, or 720.', fields={'hours': ['Unsupported window.']})
    products = trending_products(hours=hours, limit=24)
    return {'results': [product_data(request, product) for product in products], 'windowHours': hours}


@api_endpoint()
def similar(request, product_id):
    product = get_object_or_404(visible_products().prefetch_related('features'), pk=product_id)
    products = similar_products(product, limit=12)
    return {'results': [product_data(request, item) for item in products]}


@api_endpoint()
def bought_together(request, product_id):
    product = get_object_or_404(visible_products(), pk=product_id)
    products = frequently_bought_together(product, limit=8)
    return {
        'results': [product_data(request, item) for item in products],
        'minimumSupportingOrders': 2,
    }


@api_endpoint()
def search(request):
    query = (request.GET.get('q') or '').strip()
    result = intelligent_search(query)
    if query:
        record_behavior(request, BehaviorEvent.EventType.SEARCH, search_term=query)
    payload = paginated(
        request, result.products, lambda product: product_data(request, product),
        default_size=20, maximum_size=50,
    ) if result.products else {
        'results': [],
        'pagination': {'page': 1, 'pageSize': 20, 'totalPages': 0, 'totalItems': 0, 'hasNext': False, 'hasPrevious': False},
    }
    payload.update({
        'query': query,
        'correctedQuery': result.corrected_query or None,
        'popularSearches': popular_searches(8) if not query else [],
    })
    return payload
