# OwnBasket Mobile API v2 — production operations

This document is the operational contract for `/api/v2/`. The API keeps the existing same-origin Django session flow and adds revocable opaque Bearer credentials for native and mobile clients. Breaking changes require a new major path such as `/api/v3/`; v2 fields may only be added compatibly.

## Live OpenAPI documentation

- OpenAPI 3.0 JSON: `/api/v2/openapi.json`
- Swagger UI: `/api/v2/docs/`
- ReDoc: `/api/v2/redoc/`

The schema is generated at request time from Django's active `api_v2.urlpatterns` and metadata attached by `api_endpoint`. Adding or removing an API route therefore updates the documented path list automatically. Each operation documents authentication, idempotency, standard errors, examples, parameters, and version `2.0.0`.

All API responses include `API-Version: 2.0`. Errors use:

```json
{"error":{"code":"validation_error","message":"Submitted data is invalid.","fields":{"field":["Reason"]}}}
```

## Authentication flows

### Existing PWA/browser session

1. `GET /api/v2/auth/session/` to receive a CSRF token.
2. `POST /api/v2/auth/session/` with username/password and `X-CSRFToken`.
3. Send the same-origin session cookie and CSRF header on unsafe requests.

This remains backward compatible. Session cookies are never exposed to JavaScript by the API.

### Mobile Bearer credentials

1. `POST /api/v2/auth/token/` with username, password, an opaque per-installation `deviceId`, platform, and optional display name.
2. Keep the short-lived access token in platform secure memory/keychain storage. Send it as `Authorization: Bearer <accessToken>`.
3. Store the refresh token only in Android Keystore, iOS Keychain, or an equivalent OS credential vault. Never put it in logs, analytics, URLs, browser local storage, or the PWA IndexedDB sync queue.
4. Before access expiry, `POST /api/v2/auth/token/refresh/`. The response replaces both tokens. Delete the old refresh token immediately.
5. `DELETE /api/v2/auth/token/sessions/` logs out the current Bearer device. An authenticated device can revoke another owned device at `/auth/token/sessions/<sessionId>/`.

Access and refresh tokens are cryptographically random opaque values. Only HMAC-SHA256 digests are stored. Access is checked against the session row on every request, so logout and administrative revocation are immediate. Refresh tokens rotate on every use. Reuse of a rotated token revokes that entire device session as a theft/replay precaution. Defaults are 15-minute access, 30-day sliding refresh expiry, and a non-extendable 90-day device-session lifetime, bounded by deploy checks.

Multiple devices receive independent sessions. Password/account lock and inactive-user controls apply to token issuance and use.

## Idempotency and order safety

Bearer clients must send `Idempotency-Key` on checkout and sync-batch requests. The key must be 8–128 printable non-space ASCII characters and unique to one logical operation. Existing session clients remain compatible without a key, but should send one.

The server binds each key to user, method, path, and exact request bytes for 24 hours:

- an identical completed request replays the saved status/body with `Idempotency-Replayed: true`;
- a different payload/path using the same key returns `409 idempotency_conflict`;
- a concurrent in-progress duplicate returns `409 idempotency_in_progress` and `Retry-After`;
- order creation still uses database row locks and a transaction.

Any future payment-initiation endpoint must use the same `idempotent=True` endpoint contract and provider-side idempotency key.

## Push lifecycle

`POST /push/devices/` registers a per-user/device record. `PATCH /push/devices/<id>/` refreshes a provider token, app version, locale, or notification state. `DELETE` unregisters it. Firebase, APNs, and Web Push provider tokens are encrypted with Fernet and separately hashed; plaintext is never logged or returned.

`PushDelivery` is the provider-independent delivery ledger. It records queued, sending, delivered, retry, failed, and cancelled states, attempt count, next attempt, safe error code, and provider message ID. Event keys deduplicate the same notification per device. `api_v2.push.register_provider()` connects a deployment-specific FCM/APNs/Web Push sender. The bounded worker command is:

```text
python manage.py retry_push_deliveries --dry-run --limit 100
python manage.py retry_push_deliveries --limit 100
```

Failures use exponential retry up to five attempts. Repeated terminal failures disable the device. Customers can inspect their statuses at `GET /api/v2/push/deliveries/`. Provider credentials belong in the deployment secrets manager, never Git.

Provider adapters are callables loaded through `PUSH_WEB_ADAPTER`, `PUSH_FCM_ADAPTER`, or `PUSH_APNS_ADAPTER` dotted import paths. Each receives decrypted `token`, bounded title/body/target path, and allowlisted data, and returns the provider message ID. This keeps provider SDKs and credentials deployment-specific while the lifecycle contract remains stable.

## Secure background synchronization

The PWA IndexedDB queue accepts only cart add/update/remove and wishlist add/remove. It strips every non-allowlisted field and never stores passwords, access/refresh tokens, cookies, profile data, checkout data, or payment data.

The service worker can replay while no application window is open: it requests a fresh CSRF value from the same-origin session endpoint, keeps it only in worker memory, and submits the batch with the browser-managed HttpOnly session cookie. `POST /api/v2/sync/batches/` accepts 1–50 actions. Each action has a stable `clientActionId`, operation, and allowlisted payload. The server stores only a payload digest plus the bounded result ledger:

- replaying the same action ID and payload returns the original result;
- reusing an action ID with changed content returns `409 sync_action_conflict`;
- an optional `baseVersion` detects stale offline state and returns an action-level conflict;
- ownership checks protect cart rows, products, and wishlists;
- the PWA retries 429/5xx responses with bounded exponential backoff and emits browser conflict/rejection events.

Checkout, payment, profile changes, and review creation are deliberately excluded from offline replay.

## Observability and health

Every API response receives `X-Request-ID` and `Server-Timing`. Structured `api_v2` logs include request ID, resolved route, method, status, duration, and authenticated numeric user ID; they exclude request/response bodies, query values, cookies, authorization headers, tokens, email, address, and provider payloads.

- `/api/v2/health/` checks database and cache without exposing connection details.
- `/api/v2/metrics/` exposes cache-backed request/status counters to authenticated staff only.
- HTTP 5xx events emit an `api_error_hook` log suitable for a deployment logging/Sentry/OpenTelemetry adapter.

Use shared Redis in multi-instance production so rate limits and counters are consistent. Monitor latency, 4xx/5xx/429 rate, token refresh failures, refresh replay, idempotency conflicts, sync conflicts, push retry depth, and provider terminal failures.

## Configuration and retention

Required production settings:

```text
MOBILE_TOKEN_ENCRYPTION_KEY=<Fernet key from the deployment secret manager>
MOBILE_ACCESS_TOKEN_MINUTES=15
MOBILE_REFRESH_TOKEN_DAYS=30
MOBILE_SESSION_MAX_DAYS=90
API_IDEMPOTENCY_HOURS=24
```

Generate a Fernet key offline with the command shown in `.env.example`. Rotating the encryption key requires a dual-key migration plan for existing push registrations; never replace it without that plan.

Run bounded retention cleanup from the trusted scheduler:

```text
python manage.py purge_mobile_api_records --dry-run
python manage.py purge_mobile_api_records --sync-days 30
```

Before release, run checks, migration drift detection, all tests, a provider sandbox delivery, device logout/replay tests, sync conflict recovery, and production health/metrics validation.
