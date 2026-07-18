# OwnBasket Mobile API v2 and PWA

Phase 15 adds a versioned mobile API and installable progressive web app while preserving all existing website URLs and workflows. The finalized production contract includes backward-compatible session authentication, rotating/revocable opaque mobile Bearer tokens, request idempotency, encrypted push-device lifecycle records, provider adapters, server-side offline synchronization, OpenAPI documentation, and observability. See `docs/MOBILE_API.md` for the current operational contract.

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

CSRF, authentication, authorization, not-found, unsupported-method, invalid JSON, validation, conflict, idempotency and pagination failures have stable machine-readable codes. Same-origin session clients obtain a CSRF token from `GET /api/v2/auth/session/`; native clients use short-lived opaque Bearer credentials with rotating refresh tokens. JWT is explicitly unavailable because server-revocable opaque credentials are the selected contract.

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
| Push lifecycle | `/push/devices/`, `/push/devices/<id>/`, `/push/deliveries/` | Encrypted provider tokens, refresh/unregister, delivery status and retry adapter |
| Synchronization | `/sync/capabilities/`, `/sync/batches/` | Allowlisted operations, deduplication, version conflicts and retry-safe results |

List endpoints accept `page` and bounded `page_size`. Products also accept `q`, `category`, and `brand`. Catalog queries use `select_related`, prepared pricing, and narrow serializers to avoid N+1 work and prevent internal values such as cost price from entering mobile payloads. Authenticated responses and all mutation responses use `Cache-Control: no-store`.

## Web app manifest and installation

`/manifest.json` declares a stable app identity, standalone display mode, theme/background colors, orientation, shopping category, 192 and 512 pixel icons, a maskable icon, and shortcuts for shop, cart, and orders. `base.html` links the manifest, Apple touch icon, theme metadata, PWA stylesheet, and deferred PWA script.

`static/js/pwa.js` registers `/service-worker.js` only in a secure context, captures the browser install event, displays an accessible install control, reports offline state, and exposes notification-permission and mutation-queue foundations through `window.OwnBasketPWA`. Browsers decide whether and when the install event is available.

## Service worker and offline strategy

The service worker is served from the origin root so its scope can cover the site. It pre-caches the offline document, manifest, PWA shell CSS/JS, and app icons. Static assets and explicitly public product/catalog/banner/store media use cache-first delivery with bounded caches. Public navigations use network-first delivery and fall back to a previously cached response or `/offline/`.

HTML is cached only when Django marks an anonymous response with `X-PWA-Cacheable: public`. Signed-in HTML receives `Cache-Control: private, no-store`. This opt-in prevents personalized navbar, cart, or account state from entering the offline page cache. The worker never caches `/api/`, checkout, payment-adjacent order pages, cart, wishlist, account, admin, security, seller dashboards, or seller verification documents. Generic `/media/` caching is intentionally forbidden; only known public media prefixes are allowed.

The homepage is available offline after an anonymous successful visit. It is deliberately not pre-rendered during service-worker installation because doing so could mix locale, theme, cookie, or account state. A first-ever offline visit receives the static offline page.

Cache names are versioned. Activation removes older OwnBasket PWA caches, while cache trimming bounds public pages and assets. Increase the version when shell or strategy changes require immediate invalidation.

## Background synchronization

Only cart add/update/remove and wishlist add/remove may be queued in IndexedDB. Checkout, payment, profile changes, and review submission are excluded. Queued requests are validated against an operation allowlist, replayed with same-origin credentials and CSRF, removed after success or terminal client errors, and retained after server/rate-limit failures.

The service worker can flush while no window is open. It obtains a fresh CSRF token from the same-origin session endpoint into worker memory, then batches actions through `/sync/batches/`; it never persists the CSRF token or session credential. Stable action IDs, payload digests, server versions and idempotency keys provide deduplication and conflict handling. Bounded retries cover rate-limit/server failures, and non-sensitive conflict results are surfaced on the next app open. Native clients use the same contract with Bearer credentials without storing credentials inside sync payloads.

## Push notification lifecycle

The browser helper requests notification permission only in response to a user action. Authenticated users register an opaque device ID and optional Web Push/FCM/APNs provider token. Device IDs are hashed; provider tokens are Fernet-encrypted and hashed, never returned. Records support token refresh, preference disablement and unregister. Delivery rows expose queued/sending/delivered/retry/failed/cancelled states and bounded exponential retry.

The service worker contains defensive push and notification-click handlers. Deployment-specific sender code registers through the provider adapter boundary; VAPID/FCM/APNs credentials remain external secrets. A production environment must configure and sandbox-test the selected adapter before enabling devices.

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

1. Build native Android/iOS clients against the published v2 OpenAPI contract.
2. Configure and sandbox-test the selected Web Push/FCM/APNs adapter with deployment secrets.
3. Export structured logs and metrics to the production observability platform.
4. Add compatibility tests in each independent client and use `/api/v3/` for breaking changes.
