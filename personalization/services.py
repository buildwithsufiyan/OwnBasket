import math
import re
from collections import Counter, defaultdict
from datetime import timedelta
from decimal import Decimal

from django.core.cache import cache
from django.core.signing import salted_hmac
from django.db.models import Count, Sum
from django.utils import timezone

from cart.models import CartItem
from orders.models import OrderItem
from products.models import Brand, Category, Product
from products.pricing import attach_pricing_to_products
from wishlist.models import Wishlist

from .models import BehaviorEvent


VISIBLE_RELATED = ('seller', 'brand', 'category', 'subcategory')
TRENDING_WINDOWS = {24: timedelta(hours=24), 168: timedelta(days=7), 720: timedelta(days=30)}


def visible_products():
    return Product.objects.marketplace_visible().filter(
        is_active=True, category__is_active=True, brand__is_active=True,
    ).select_related(*VISIBLE_RELATED)


def sanitize_search_term(value):
    value = re.sub(r'\s+', ' ', str(value or '')).strip().lower()[:100]
    if len(value) < 2 or '@' in value or re.search(r'\d{8,}', value):
        return ''
    return value


def _session_hash(request):
    if request.user.is_authenticated:
        return ''
    if not request.session.session_key:
        request.session.create()
    return salted_hmac(
        'ownbasket.behavior-session', request.session.session_key, algorithm='sha256',
    ).hexdigest()


def record_behavior(request, event_type, *, product=None, category=None, brand=None, search_term=''):
    """Record a minimal, deduplicated event without IP, user agent, or raw session ID."""
    term = sanitize_search_term(search_term)
    if event_type == BehaviorEvent.EventType.SEARCH and not term:
        return None
    user = request.user if request.user.is_authenticated else None
    session_hash = _session_hash(request)
    identity = {'user': user} if user else {'session_hash': session_hash}
    duplicate_since = timezone.now() - timedelta(minutes=10)
    duplicate = BehaviorEvent.objects.filter(
        **identity, event_type=event_type, product=product, category=category, brand=brand,
        search_term=term, created_at__gte=duplicate_since,
    ).exists()
    if duplicate:
        return None
    event = BehaviorEvent.objects.create(
        user=user, session_hash=session_hash, event_type=event_type,
        product=product, category=category, brand=brand, search_term=term,
    )
    if product_id := getattr(product, 'pk', None):
        for hours in TRENDING_WINDOWS:
            cache.delete(f'personalization:trending:{hours}')
    return event


def _score_products(products, scores, limit):
    ranked = sorted(
        products,
        key=lambda product: (
            scores.get(product.pk, 0), product.rating or 0,
            product.total_sold, product.total_views, -product.pk,
        ),
        reverse=True,
    )[:limit]
    return attach_pricing_to_products(ranked)


def trending_products(*, hours=168, limit=12):
    if hours not in TRENDING_WINDOWS:
        raise ValueError('Trending window must be 24, 168, or 720 hours.')
    cache_key = f'personalization:trending:{hours}'
    cached_ids = cache.get(cache_key)
    if cached_ids is not None:
        by_id = {item.pk: item for item in visible_products().filter(pk__in=cached_ids)}
        return attach_pricing_to_products([by_id[pk] for pk in cached_ids if pk in by_id][:limit])

    since = timezone.now() - TRENDING_WINDOWS[hours]
    views = dict(
        BehaviorEvent.objects.filter(
            event_type=BehaviorEvent.EventType.PRODUCT_VIEW, product__isnull=False, created_at__gte=since,
        ).values_list('product_id').annotate(total=Count('id'))
    )
    orders = dict(
        OrderItem.objects.filter(order__created_at__gte=since).values_list('product_id').annotate(total=Sum('quantity'))
    )
    wishes = dict(
        Wishlist.objects.filter(created_at__gte=since).values_list('product_id').annotate(total=Count('id'))
    )
    candidate_ids = set(views) | set(orders) | set(wishes)
    candidates = list(visible_products().filter(pk__in=candidate_ids)) if candidate_ids else list(
        visible_products().order_by('-total_sold', '-total_views', '-wishlist_count', '-rating')[:60]
    )
    scores = {
        product.pk: (
            views.get(product.pk, 0) * 1.0 + orders.get(product.pk, 0) * 5.0
            + wishes.get(product.pk, 0) * 2.5 + float(product.rating or 0) * 0.4
            + math.log1p(product.total_sold) * 0.25
        )
        for product in candidates
    }
    ranked = _score_products(candidates, scores, 50)
    ranked_ids = [product.pk for product in ranked]
    cache.set(cache_key, ranked_ids, 300)
    return ranked[:limit]


def frequently_bought_together(product, *, limit=4, minimum_orders=2):
    order_ids = OrderItem.objects.filter(product=product).values('order_id')
    rows = list(
        OrderItem.objects.filter(order_id__in=order_ids)
        .exclude(product=product)
        .values('product_id')
        .annotate(order_count=Count('order_id', distinct=True), units=Sum('quantity'))
        .filter(order_count__gte=minimum_orders)
        .order_by('-order_count', '-units', 'product_id')[:limit]
    )
    ids = [row['product_id'] for row in rows]
    by_id = {item.pk: item for item in visible_products().filter(pk__in=ids)}
    return attach_pricing_to_products([by_id[pk] for pk in ids if pk in by_id])


def similar_products(product, *, limit=8):
    price = product.selling_price or product.price or Decimal('0')
    lower, upper = price * Decimal('0.60'), price * Decimal('1.40')
    candidates = list(
        visible_products().filter(
            category=product.category,
        ).exclude(pk=product.pk).filter(price__gte=lower, price__lte=upper).prefetch_related('features')[:80]
    )
    if len(candidates) < limit:
        existing = [item.pk for item in candidates] + [product.pk]
        candidates.extend(list(
            visible_products().filter(brand=product.brand).exclude(pk__in=existing).prefetch_related('features')[:40]
        ))
    source_tags = {feature.feature.strip().lower() for feature in product.features.all() if feature.feature.strip()}
    scores = {}
    for item in candidates:
        score = 8 if item.category_id == product.category_id else 0
        score += 5 if item.brand_id == product.brand_id else 0
        score += 4 if product.subcategory_id and item.subcategory_id == product.subcategory_id else 0
        item_price = item.selling_price or item.price or Decimal('0')
        if price > 0:
            score += max(0, 4 - float(abs(item_price - price) / price) * 4)
        item_tags = {feature.feature.strip().lower() for feature in item.features.all() if feature.feature.strip()}
        score += min(4, len(source_tags & item_tags) * 2)
        score += float(item.rating or 0) * .2 + math.log1p(item.total_sold) * .2
        scores[item.pk] = score
    return _score_products(candidates, scores, limit)


class RecommendationService:
    def __init__(self, request):
        self.request = request
        self.user = request.user
        self._signals = None

    def recently_viewed(self, limit=12):
        ids = list(self.request.session.get('recently_viewed_product_ids', []))
        if self.user.is_authenticated:
            event_ids = BehaviorEvent.objects.filter(
                user=self.user, event_type=BehaviorEvent.EventType.PRODUCT_VIEW,
            ).exclude(product__isnull=True).values_list('product_id', flat=True)[:30]
            ids.extend(event_ids)
        ordered_ids = list(dict.fromkeys(ids))[:limit]
        by_id = {item.pk: item for item in visible_products().filter(pk__in=ordered_ids)}
        return attach_pricing_to_products([by_id[pk] for pk in ordered_ids if pk in by_id])

    def _build_signals(self):
        if self._signals is not None:
            return self._signals
        product_weights, categories, brands = defaultdict(float), Counter(), Counter()

        def add(product_id, category_id, brand_id, weight):
            product_weights[product_id] += weight
            categories[category_id] += weight
            brands[brand_id] += weight

        recent_ids = list(self.request.session.get('recently_viewed_product_ids', []))[:30]
        for row in Product.objects.filter(pk__in=recent_ids).values_list('id', 'category_id', 'brand_id'):
            add(*row, 3)
        event_identity = None
        if self.user.is_authenticated:
            event_identity = {'user': self.user}
        elif self.request.session.session_key:
            event_identity = {'session_hash': salted_hmac(
                'ownbasket.behavior-session', self.request.session.session_key, algorithm='sha256',
            ).hexdigest()}
        if event_identity:
            events = BehaviorEvent.objects.filter(
                **event_identity, created_at__gte=timezone.now() - timedelta(days=90),
                event_type__in=(
                    BehaviorEvent.EventType.PRODUCT_VIEW,
                    BehaviorEvent.EventType.CATEGORY_VIEW,
                    BehaviorEvent.EventType.BRAND_VIEW,
                ),
            ).values_list('event_type', 'product_id', 'category_id', 'brand_id')[:150]
            for event_type, product_id, category_id, brand_id in events:
                if event_type == BehaviorEvent.EventType.PRODUCT_VIEW and product_id:
                    add(product_id, category_id, brand_id, 2)
                elif event_type == BehaviorEvent.EventType.CATEGORY_VIEW and category_id:
                    categories[category_id] += 2
                elif event_type == BehaviorEvent.EventType.BRAND_VIEW and brand_id:
                    brands[brand_id] += 2
        if self.user.is_authenticated:
            for row in Wishlist.objects.filter(user=self.user).values_list('product_id', 'product__category_id', 'product__brand_id')[:50]:
                add(*row, 5)
            for row in CartItem.objects.filter(cart__user=self.user).values_list('product_id', 'product__category_id', 'product__brand_id')[:50]:
                add(*row, 7)
            for row in OrderItem.objects.filter(order__user=self.user).values_list('product_id', 'product__category_id', 'product__brand_id')[:100]:
                add(*row, 4)
        self._signals = product_weights, categories, brands
        return self._signals

    def recommended(self, limit=12):
        product_weights, categories, brands = self._build_signals()
        if not categories and not brands:
            return trending_products(limit=limit)
        exclude_ids = set(product_weights)
        candidates = list(
            visible_products().filter(category_id__in=categories.keys()).exclude(pk__in=exclude_ids)[:100]
        )
        if len(candidates) < limit:
            existing = exclude_ids | {item.pk for item in candidates}
            candidates.extend(list(
                visible_products().filter(brand_id__in=brands.keys()).exclude(pk__in=existing)[:60]
            ))
        signal_prices = list(Product.objects.filter(pk__in=exclude_ids).values_list('price', flat=True)[:50])
        average_price = sum(signal_prices, Decimal('0')) / len(signal_prices) if signal_prices else None
        scores = {}
        for item in candidates:
            score = categories[item.category_id] * 1.4 + brands[item.brand_id]
            if average_price and average_price > 0:
                score += max(0, 3 - float(abs(item.price - average_price) / average_price) * 3)
            score += float(item.rating or 0) * .3 + math.log1p(item.total_sold) * .25
            scores[item.pk] = score
        return _score_products(candidates, scores, limit)

    def has_signals(self):
        product_weights, categories, brands = self._build_signals()
        return bool(product_weights or categories or brands)

    def has_signals(self):
        product_weights, categories, brands = self._build_signals()
        return bool(product_weights or categories or brands)

    def favorite_brands(self, limit=4):
        _, _, brands = self._build_signals()
        ids = [pk for pk, _ in brands.most_common(limit)]
        by_id = {item.pk: item for item in Brand.objects.filter(pk__in=ids, is_active=True)}
        return [by_id[pk] for pk in ids if pk in by_id]

    def suggested_categories(self, limit=4):
        _, categories, _ = self._build_signals()
        ids = [pk for pk, _ in categories.most_common(limit)]
        by_id = {item.pk: item for item in Category.objects.filter(pk__in=ids, is_active=True)}
        return [by_id[pk] for pk in ids if pk in by_id]

    def personalized_offers(self, limit=8):
        return [item for item in self.recommended(limit=24) if item.display_compare_price][:limit]
