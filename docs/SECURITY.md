# OwnBasket security and compliance foundation

This document describes the controls implemented in Phase 14. It is an engineering baseline, not a certification or a claim of legal compliance. Production deployment requires an independent security review, privacy/legal review, infrastructure hardening, and an incident-response owner.

## Architecture

OwnBasket uses Django authentication, password hashing, CSRF middleware, server-side sessions, clickjacking protection, CSP, secure-cookie production defaults, request IDs, conservative endpoint rate limits, and application-level authorization. `SecurityMonitoringMiddleware` attaches request context for audit attribution, refreshes a hashed session inventory, adds browser security headers, and prevents caching on sensitive pages.

Production must terminate HTTPS correctly, set `DJANGO_ENV=production`, configure trusted hosts/origins, keep `SECRET_KEY` outside source control, use a shared cache for rate limiting, and serve `MEDIA_ROOT` as non-executable content from a dedicated origin or hardened media server.

## Audit logging

`AuditEvent` records actor, category, action, result, timestamp, IP address, user agent, request ID, target type/ID, and allowlisted metadata. Authentication, account changes, tracked commerce/admin objects, rate-limit events, upload rejections, session revocation, privacy requests, and Django admin log entries generate events. Bulk order-status and seller-review actions save objects individually so their security signals are not bypassed.

Audit metadata excludes keys associated with passwords, OTPs, tokens, sessions, cookies, authorization headers, cards, CVVs, secrets, and admin object representations. Customer/order representations are not copied into audit targets. Passwords, raw payment payloads, personal documents, secret keys, and session keys must never be added to audit metadata. Audit records are read-only and non-deletable in Django admin; database administrators still have database-level access, so append-only external log export is recommended for stronger tamper evidence.

## Login, password, and session controls

- Successful and failed logins and logout are audited. Repeated failures temporarily lock the account; both customer and seller login forms enforce that state.
- Passwords require Django similarity, 12-character minimum, common-password, and numeric-only validation. Six recent encoded passwords are retained for reuse prevention; plaintext passwords are never stored.
- Password changes retain the current authenticated session and are audited. Password-reset requests and successful reset completion are audited without logging the submitted email or reset token.
- Session IDs are stored in the security inventory only as SHA-256 hashes. Users see only their own device/login history, can revoke an owned non-current session, and can log out all other sessions. The current session is protected from accidental device-list revocation.
- Django rotates the session key at login. Browser-close expiry is the default; “keep me signed in” uses the configured maximum session age. Cookie security settings are enabled for production.

## Two-factor authentication foundation

The security center records an authenticated user’s opt-in preference for future email OTP enrollment. It deliberately does **not** claim that 2FA is enabled and does not enforce a second factor. Authenticator/TOTP is represented only as a future method. No raw OTP or recovery code is generated or stored.

Before enforcement, implement a cryptographically random challenge, one-way challenge digest, short expiry, attempt counter, single-use/replay protection, per-user and per-IP rate limits, verified delivery, recovery workflow, support controls, and end-to-end tests. Do not set `verified_at` until that complete flow succeeds.

## Rate limiting

`RateLimitMiddleware` protects login, customer/seller registration, password reset, search suggestions, checkout, coupon application, privacy requests, 2FA preference endpoints, and newsletter subscription. Authenticated endpoints key by user; credential endpoints combine IP with a digest of the submitted identity to reduce shared-network collateral blocking. Search remains IP-limited. Limits are cache-backed, emit real audit/alert records, return HTTP 429 and `Retry-After`, and can be enabled explicitly in tests.

Deploy a shared Redis cache across all application instances. Cache rate limiting is a safety control, not a substitute for upstream WAF/bot protection. Review/contact/OTP endpoints must be added to the limit table when those endpoints become operational.

## Upload validation

Product, seller, banner, brand/category, homepage-section, theme-preview, font, and related admin uploads use shared validators. Images are checked for allowed extension, declared MIME, decoded format, content/extension agreement, corruption, size, and maximum dimensions. Documents allow PDF or safe raster formats and validate PDF/image signatures. Video and font headers are checked against their extensions.

Theme archives enforce compressed and uncompressed size limits, member-count limits, allowed extensions, traversal/absolute-path rejection, and destination containment before extraction. SVG and executable upload formats are not allowed. Storage-generated filenames must remain untrusted. Production media must not be interpreted by a web server, and malware scanning should be added for seller documents and imported archives.

## Permissions and API security

Authorization is enforced in backend queries and views:

| Role | Intended sensitive access |
| --- | --- |
| Super admin | Full administration and security configuration |
| Store manager | Explicitly assigned store permissions; no implicit security access |
| Product manager | Product/catalog permissions only |
| Order manager | Order workflow permissions; financial reporting only when separately granted |
| Marketing manager | Marketing permissions created by the marketing app; no payment/security permissions |
| Finance manager | Explicit financial report/export permissions; no security or theme configuration by default |
| Seller | Own seller profile, products, documents, order lines, payouts, and notifications only |
| Support staff | Explicit support/view permissions; no password, token, OTP, payout secret, or security-setting access |
| Customer | Own profile, orders, invoice, sessions, audit history, and privacy requests only |

Security dashboard access requires `security.view_security_dashboard`. Privacy processing requires `security.process_privacy_requests`. Seller review and suspension actions require their dedicated marketplace permissions. Theme reads and state changes require the appropriate theme model permission; activation, preview changes, deletion, scans, restores, and suggestion application are POST/CSRF protected where they mutate state.

The current JSON endpoints expose only public catalog/font data, cap search results, and accept GET only. Order/detail/invoice endpoints scope queries to `request.user`; seller endpoints scope product and order queries to `request.seller`. No session key, password hash, token, payment credential, or private seller document is serialized. Any future API framework must add object-level permissions, serializer allowlists, pagination, throttling, and non-enumerating errors.

## Security dashboard and alerts

Authorized staff see real 24-hour successful/failed login counts, currently locked accounts, recently active sessions, open alerts, upload failures, recent audit events, and open alert details. Counts are database-backed; there are no fake incidents. Querysets use indexes and `select_related` where user data is displayed.

## Privacy and policy workflows

Customers can submit export, correction, or deletion requests and view only their own request history. Requests start pending and never delete or export data automatically. Authorized administrators review status and notes; completing a request timestamps and audits the transition. Deletion handling must preserve orders, invoices, payment/refund records, fraud evidence, tax records, and other legally required retention data, using anonymization where approved.

`PolicyVersion` stores version and approved-content hash. `PolicyAcceptance` stores the user, exact version, timestamp, and IP and is read-only in admin. Privacy and terms must be separate versioned policy records. Product/legal owners must supply approved text, lawful basis, jurisdiction-specific retention schedules, consent wording, withdrawal rules, age requirements, and verified fulfillment procedures before relying on these foundations.

## Incident response basics

1. Preserve audit, proxy, database, email, payment-provider, and infrastructure logs with access controls.
2. Triage affected accounts, time range, data classes, sessions, and administrative actions; do not alter evidence.
3. Revoke affected sessions and credentials, contain vulnerable endpoints, rotate exposed secrets, and document every action.
4. Notify the assigned security/privacy/legal owners. They determine contractual and regulatory notification duties and deadlines.
5. Remediate, validate with tests and independent review, monitor recurrence, and record a blameless post-incident report.

## Known limitations and required follow-up

- 2FA is preference-only and is not an authentication factor yet.
- Cache limits are not a distributed WAF and require shared production cache configuration.
- Audit rows are application-read-only, not cryptographically chained or externally immutable.
- File inspection is format/signature validation, not antivirus, sandboxing, or content-disarm/reconstruction.
- Policy acceptance capture is a data model/admin foundation; approved registration/checkout acceptance UX still requires legal sign-off.
- Privacy exports, identity verification, anonymization, retention execution, and deletion fulfillment remain reviewed operational workflows.
- User-agent device labels are best-effort summaries, not device identity.
- A penetration test, dependency/SBOM review, secrets scan, infrastructure review, accessibility review, and jurisdiction-specific legal assessment remain required before production assurance claims.
