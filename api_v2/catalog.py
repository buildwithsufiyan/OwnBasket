from django.db.models import F, Q
from django.shortcuts import get_object_or_404

from products.models import (
    Brand, Category, CustomerExperienceSettings, Product, ProductReview, ReviewHelpfulVote,
)
from products.pricing import attach_pricing_to_products

from .http import ApiError, api_endpoint, json_body, paginated, positive_int
from .serializers import brand_data, category_data, product_data, review_data
from personalization.models import BehaviorEvent
from personalization.services import record_behavior


def visible_products():
    return Product.objects.marketplace_visible().filter(
        is_active=True, category__is_active=True, brand__is_active=True,
    ).select_related('category', 'brand', 'seller')


@api_endpoint(public_cache_seconds=60)
def products(request):
    queryset = visible_products().order_by('-featured_product', '-created_at', '-id')
    query = (request.GET.get('q') or '').strip()[:100]
    if query:
        queryset = queryset.filter(Q(name__icontains=query) | Q(short_description__icontains=query))
        record_behavior(request, BehaviorEvent.EventType.SEARCH, search_term=query)
    if request.GET.get('category'):
        queryset = queryset.filter(category__slug=request.GET['category'][:100])
    if request.GET.get('brand'):
        queryset = queryset.filter(brand_id=positive_int(request.GET['brand'], name='brand'))
    return paginated(request, queryset, lambda item: product_data(request, item), prepare=attach_pricing_to_products)


@api_endpoint(public_cache_seconds=60)
def product_detail(request, product_id):
    product = get_object_or_404(visible_products(), pk=product_id)
    record_behavior(request, BehaviorEvent.EventType.PRODUCT_VIEW, product=product, category=product.category, brand=product.brand)
    payload = product_data(request, product)
    payload.update({
        'description': product.description,
        'warranty': product.warranty,
        'returnPolicy': product.return_policy,
    })
    return {'product': payload}


@api_endpoint(public_cache_seconds=300)
def categories(request):
    queryset = Category.objects.filter(is_active=True).order_by('sort_order', 'name', 'id')
    return paginated(request, queryset, lambda item: category_data(request, item), default_size=30)


@api_endpoint(public_cache_seconds=300)
def brands(request):
    queryset = Brand.objects.filter(is_active=True).order_by('display_order', 'name', 'id')
    return paginated(request, queryset, lambda item: brand_data(request, item), default_size=30)


@api_endpoint(('GET', 'POST', 'PATCH', 'DELETE'))
def product_reviews(request, product_id):
    product = get_object_or_404(visible_products(), pk=product_id)
    if request.method == 'GET':
        queryset = ProductReview.objects.filter(
            product=product, moderation_status=ProductReview.ModerationStatus.APPROVED,
        ).select_related('user')
        return paginated(request, queryset, review_data)

    if not request.user.is_authenticated:
        raise ApiError('authentication_required', 'Sign in is required to submit a review.', 401)
    from orders.models import OrderItem
    if request.method == 'DELETE':
        review = ProductReview.objects.filter(user=request.user, product=product).first()
        if not review:
            raise ApiError('not_found', 'Your review was not found.', 404)
        review.delete()
        return {'deleted': True}
    if not OrderItem.objects.filter(order__user=request.user, product=product).exists():
        raise ApiError('purchase_required', 'Only customers who purchased this product can review it.', 403)
    payload = json_body(request)
    rating = positive_int(payload.get('rating'), name='rating', maximum=5)
    title = str(payload.get('title') or '').strip()
    body = str(payload.get('body') or '').strip()
    if not body or len(body) > 4000 or len(title) > 160 or body.count('http://') + body.count('https://') > 2:
        raise ApiError('validation_error', 'Review content is invalid.', fields={
            'body': ['Use between 1 and 4000 characters with no more than two links.'], 'title': ['Use no more than 160 characters.'],
        })
    review, created = ProductReview.objects.update_or_create(
        user=request.user, product=product,
        defaults={
            'rating': rating, 'title': title, 'body': body,
            'verified_purchase': True, 'is_spam': False,
            'moderation_status': ProductReview.ModerationStatus.PENDING,
            'moderation_notes': '', 'moderated_by': None, 'moderated_at': None,
        },
    )
    return {'review': {'id': review.pk, 'status': review.moderation_status}, 'created': created}


@api_endpoint(('POST',), auth=True)
def review_helpful(request, review_id):
    review = get_object_or_404(
        ProductReview, pk=review_id, moderation_status=ProductReview.ModerationStatus.APPROVED,
    )
    if review.user_id == request.user.id:
        raise ApiError('invalid_vote', 'You cannot vote on your own review.', 409)
    _, created = ReviewHelpfulVote.objects.get_or_create(review=review, user=request.user)
    if created:
        ProductReview.objects.filter(pk=review.pk).update(helpful_count=F('helpful_count') + 1)
    return {'reviewId': review.pk, 'created': created}
