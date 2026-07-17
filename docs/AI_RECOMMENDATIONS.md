# OwnBasket AI recommendations and intelligent search

Phase 16 introduces a deterministic, explainable personalization layer built from real OwnBasket activity. “AI” here means intelligent ranking and an ML-ready service boundary; no fabricated events, products, affinities, co-purchase pairs, or model predictions are created.

## Available signals

The engine uses product category, subcategory, brand, price, features, lifetime views, lifetime units sold, wishlist count, approved-review rating, session recently viewed IDs, current cart, timestamped wishlists, timestamped orders/order lines, and the new privacy-friendly behavior events. Seller visibility is enforced on every candidate queryset, so unapproved seller products do not enter recommendations.

Before Phase 16 the project had no timestamped product/category/brand/search event stream. `personalization.BehaviorEvent` fills that gap for future activity; historical totals remain useful but are not backfilled into fake dated events.

## Recommendation architecture

`personalization.services` is the reusable service boundary for website and API clients. `RecommendationService` builds per-request category and brand affinity from these weighted signals:

| Signal | Relative weight |
| --- | ---: |
| Cart product | 7 |
| Wishlist product | 5 |
| Previous purchase | 4 |
| Recently viewed | 3 |

Candidate products inherit weighted category and brand affinity. Similarity to the average observed price, rating, and real sales add bounded tie-breaking scores. Products already used as signals are excluded from “Recommended for you” because they are shown separately through continue-shopping/cart/wishlist experiences. Users without enough signals receive the trending fallback, clearly identified as a fallback rather than personalized output.

The homepage shows logged-in users continue shopping, recommended products, relevant active offers, favourite brands, and suggested categories. Guests see seven-day trending products, lifetime best sellers, and categories represented in current trending results. An “offer for you” is only an already-active catalog price reduction among relevant products; Phase 16 does not invent coupons or claim that an offer is exclusive.

## Similar products

Product similarity is explainable and bounded. Candidates first come from the same category and a 60–140% price window, then same-brand candidates fill any remaining capacity. Ranking weights same category, brand, subcategory, price distance, shared real `ProductFeature` values, rating, and sales. There is no tag inference when product features are absent.

## Frequently bought together

Co-purchases are derived from `OrderItem` rows sharing real orders. A product pair must appear together in at least two distinct orders before it is displayed. Ranking uses supporting-order count, then units. When evidence is insufficient the section is omitted; unrelated fallback combinations are never manufactured.

## Trending engine

`trending_products(hours=...)` supports 24-hour, 7-day (`168` hours), and 30-day (`720` hours) windows. Within the selected window the score combines:

- product-view events × 1;
- ordered units × 5;
- wishlist additions/rows × 2.5;
- approved-review summary rating as a small quality tie-breaker;
- lifetime units sold as a bounded stability tie-breaker.

If no windowed event/order/wishlist evidence exists, the engine falls back to real lifetime sales, views, wishlists, and ratings. Trending IDs are cached for five minutes; new product-view/cart/wishlist events invalidate relevant keys. Cached IDs are resolved again through the current visibility queryset so product or seller state changes cannot expose an ineligible product.

## Intelligent search

`personalization.search` powers full search, autocomplete, and `/api/v2/search/`. Input is normalized and bounded. Product matching covers name, SKU, barcode, descriptions, brand, category, and subcategory. Ranking prioritizes exact name, name prefix, name containment, brand/category matches, description matches, then real popularity and rating.

When direct product matching is empty, typo tolerance compares the term to a cached catalog vocabulary and retries only above a conservative similarity threshold. The UI and API disclose `corrected_query`/`correctedQuery`; the original term is retained for the user. `SearchSynonym` is an admin-configurable foundation containing a canonical term and explicit alternatives. No synonyms are seeded, because domain owners must validate language and merchandising intent.

Popular searches aggregate sanitized search events from the last 30 days and are cached for five minutes. Autocomplete requests do not record every keystroke; a search is recorded only when the result page or mobile search endpoint is requested.

## Behavior tracking and privacy

Tracked event types are product view, category view, brand view, completed search, wishlist add/remove, and cart add/update/remove. Events contain only applicable object IDs, a normalized search term, timestamp, and either an authenticated user ID or an HMAC-SHA256 session digest.

The table does not store IP addresses, user agents, referrers, raw session keys, full URLs, request bodies, email addresses, or device fingerprints. Search terms containing an email marker or a long digit sequence are rejected. Repeated identical events for the same actor and target are deduplicated within ten minutes. This is data minimization, not a complete privacy program: production still needs consent/legal review, user-facing disclosure, access/deletion workflows, and retention ownership.

Run retention cleanup on a schedule:

```text
python manage.py purge_behavior_events --days 180 --dry-run
python manage.py purge_behavior_events --days 180
```

Retention below 30 days is rejected by the command to prevent an accidental broad operational change; organizations may implement a separately reviewed shorter policy in code.

## Mobile API

Phase 16 extends API v2 without changing existing routes:

| Endpoint | Purpose |
| --- | --- |
| `GET /api/v2/recommendations/` | Personalized results or an explicit guest fallback |
| `GET /api/v2/trending/?hours=24|168|720` | Time-window trending products |
| `GET /api/v2/search/?q=...` | Paginated ranked search with correction metadata |
| `GET /api/v2/products/<id>/similar/` | Explainable similar-product results |
| `GET /api/v2/products/<id>/bought-together/` | Evidence-gated co-purchases |

Personalized/search responses are `no-store`. Public trending responses may use short HTTP caching for anonymous requests. Existing API v2 authentication, CSRF, error envelope, owner scoping, pagination, and version headers remain intact.

## Performance and operations

- Candidate pools and per-signal reads are capped.
- Product queries consistently load seller, brand, category, and subcategory in one query.
- Trending and search vocabularies/synonyms/popular terms use short bounded caches.
- Pricing is attached in batches after ranking.
- Co-purchase aggregation runs in SQL and enforces an evidence threshold.
- Event indexes cover type/time, user/type/time, and product/type/time access paths.
- Personalized responses themselves are not shared-cache entries.

At higher traffic, move event ingestion to a durable queue, precompute user/item features and co-purchase matrices in background jobs, use Redis for shared caches, and measure cache hit rate, recommendation latency, candidate coverage, click-through, conversion, diversity, novelty, and out-of-stock exposure.

## Future ML integration

The deterministic services are stable fallbacks and provide training/evaluation signals. A future model adapter should return product IDs plus model/version/reason metadata, after which the same visibility and pricing layers must resolve results. Before launch, add offline evaluation, holdouts/A-B testing, drift and bias checks, cold-start behavior, feature freshness SLAs, reproducible model/version registries, deletion propagation, explainability, and a kill switch. Model output must never bypass seller approval, inventory, permissions, privacy preferences, or pricing truth.

## Verification

```text
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test personalization api_v2 products core cart orders wishlist marketplace analytics
python manage.py test
git diff --check
```
