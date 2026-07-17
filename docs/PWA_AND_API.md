# OwnBasket Mobile API v2 and PWA

Phase 15 adds a same-origin, session-authenticated mobile API and an installable progressive web app while preserving all existing website URLs and workflows. The API and offline layer are foundations for future native clients; they do not claim JWT authentication, production push delivery, or unattended background mutation delivery.

## API v2 architecture

The versioned API is mounted at `/api/v2/`. Existing Django page routes and any earlier API routes remain unchanged. `api_v2/urls.py` is the route index, domain modules contain endpoint logic, `serializers.py` defines intentionally small response payloads, and `http.py` provides JSON parsing, pagination, validation helpers, cache policy, and a consistent error envelope.

Successful API responses include `API-Version: 2.0`. Errors use this shape:

```json
{
  "error": {
    "code": "validation_error",
    "message": "Submitted data is invalid.",
    "fields": {"fieldName": ["Explanation"]}
  }
}
```

CSRF, authentication, authorization, not-found, unsupported-method, invalid JSON, validation, and pagination failures have stable machine-readable codes. Unsafe requests use Django's CSRF protection. A client obtains a token from `GET /api/v2/auth/session/` and sends it in `X-CSRFToken`. Session cookies are same-origin credentials. JWT is explicitly reported as unavailable so clients do not infer support that does not exist.

### Endpoint groups

| Area | Routes | Notes |
| --- | --- | --- |
| Discovery | `/api/v2/` | Version, authentication capabilities, and endpoint links |
| Catalog | `/products/`, `/products/<id>/`, `/categories/`, `/brands/` | Pagination, search and catalog filters; public short-lived HTTP caching |
| Reviews | `/products/<id>/reviews/` | Approved reviews are public; submissions require login and a purchase |
| Cart | `/cart/`, `/cart/items/`, `/cart/items/<id>/` | Owner-scoped, validated mutations; responses are `no-store` |
| Checkout | `/checkout/` | Reuses the transactional web checkout service; COD only at this stage |
| Orders | `/orders/`, `/orders/<id>/` | Paginated and owner-scoped; no cross-account IDs are exposed |
| Wishlist | `/wishlist/`, `/wishlist/<product-id>/` | Idempotent add/remove operations suitable for queued retry |
| Account | `/profile/`, `/seller/dashboard/` | Allowlisted profile fields and authenticated seller ownership |
| Push foundation | `/push/devices/`, `/push/devices/<id>/` | Stores only a SHA-256 device identifier; no delivery provider is connected |
| Sync foundation | `/sync/capabilities/` | Declares supported and explicitly excluded queued operations |

List endpoints accept `page` and bounded `page_size`. Products also accept `q`, `category`, and `brand`. Catalog queries use `select_related`, prepared pricing, and narrow serializers to avoid N+1 work and prevent internal values such as cost price from entering mobile payloads. Authenticated responses and all mutation responses use `Cache-Control: no-store`.

## Web app manifest and installation

`/manifest.json` declares a stable app identity, standalone display mode, theme/background colors, orientation, shopping category, 192 and 512 pixel icons, a maskable icon, and shortcuts for shop, cart, and orders. `base.html` links the manifest, Apple touch icon, theme metadata, PWA stylesheet, and deferred PWA script.

`static/js/pwa.js` registers `/service-worker.js` only in a secure context, captures the browser install event, displays an accessible install control, reports offline state, and exposes notification-permission and mutation-queue foundations through `window.OwnBasketPWA`. Browsers decide whether and when the install event is available.

## Service worker and offline strategy

The service worker is served from the origin root so its scope can cover the site. It pre-caches the offline document, manifest, PWA shell CSS/JS, and app icons. Static assets and explicitly public product/catalog/banner/store media use cache-first delivery with bounded caches. Public navigations use network-first delivery and fall back to a previously cached response or `/offline/`.

HTML is cached only when Django marks an anonymous response with `X-PWA-Cacheable: public`. Signed-in HTML receives `Cache-Control: private, no-store`. This opt-in prevents personalized navbar, cart, or account state from entering the offline page cache. The worker never caches `/api/`, checkout, payment-adjacent order pages, cart, wishlist, account, admin, security, seller dashboards, or seller verification documents. Generic `/media/` caching is intentionally forbidden; only known public media prefixes are allowed.

The homepage is available offline after an anonymous successful visit. It is deliberately not pre-rendered during service-worker installation because doing so could mix locale, theme, cookie, or account state. A first-ever offline visit receives the static offline page.

Cache names are versioned. Activation removes older OwnBasket PWA caches, while cache trimming bounds public pages and assets. Increase the version when shell or strategy changes require immediate invalidation.

## Background sync foundation

Only cart add/update/remove and wishlist add/remove may be queued in IndexedDB. Checkout, payment, profile changes, and review submission are excluded. Queued requests are validated against an operation allowlist, replayed with same-origin credentials and CSRF, removed after success or terminal client errors, and retained after server/rate-limit failures.

The current service-worker sync event asks an open controlled window to flush the queue. It does not pretend to support unattended authenticated replay: CSRF and the HttpOnly session remain browser-controlled, and `/sync/capabilities/` reports the open-client requirement. A future implementation can move replay into the worker only after designing secure token rotation, conflict handling, deduplication/idempotency keys, expiry, user switching, and observable retry state.

## Push notification foundation

The browser helper can request notification permission only in response to a user action. Authenticated users can register an opaque device identifier; the server stores its SHA-256 digest, platform, future provider enum, enabled state, and last-seen timestamp. Records are owner-scoped and auditable. `deliveryConfigured` remains false, and registrations default to disabled/provider `none`.

The service worker contains defensive push and notification-click handlers for a future trusted sender. Production delivery still requires VAPID/Web Push or Firebase credentials, encrypted subscription material, explicit opt-in UI, verified endpoint lifecycle, preference enforcement, rate limits, payload allowlisting, revocation, monitoring, and privacy documentation.

## Responsive and performance baseline

The existing responsive foundation was retained: the navbar collapses below tablet width; product grids scale from desktop to compact two-column mobile layouts; checkout becomes one column; seller/dashboard navigation collapses; admin and analytics tables scroll or stack. Relevant styles cover the requested 320, 375, 768, 1024, and 1440 pixel ranges. The install and network controls respect mobile safe areas and maintain a 44 pixel touch target.

Product card and review images use native lazy loading where they are below the fold, image containers reserve dimensions/aspect ratios, and scripts are deferred. API serializers avoid unnecessary fields and catalog queries prepare related data and pricing in batches. Uploaded public images may be cached by the PWA, but private media and API responses may not.

## Verification

Run from the repository root:

```text
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
git diff --check
```

The Phase 15 test suite covers version/error contracts, pagination and filtering foundations, ownership/IDOR protection, cart/wishlist/checkout behavior, CSRF, seller and push-device permissions, manifest fields, icon dimensions, service-worker exclusions, anonymous page cache opt-in, authenticated page cache denial, offline page access, and install registration markup.

## Future mobile roadmap

1. Publish and freeze an OpenAPI schema, then add compatibility/contract tests for independent clients.
2. Add a separately reviewed token adapter with rotation, revocation, device binding, and scoped permissions; keep session auth supported for the PWA.
3. Add idempotency keys and conflict/version semantics before enabling unattended offline mutations.
4. Integrate Web Push or Firebase only after consent, preference, subscription encryption, and operational controls are complete.
5. Add mobile observability for API latency, payload size, cache hit rate, sync failures, install conversion, and crash-free sessions without collecting sensitive request bodies.
6. Build native Android/iOS clients against the same v2 contract, then introduce `/api/v3/` for breaking changes rather than changing v2 behavior.
