# OwnBasket Marketing Automation

Phase 12 adds permission-based customer engagement without enabling unsolicited bulk mail, tracking pixels, fake rewards, or fake analytics.

## Email backend

Development defaults to Django's console email backend. Production should set:

```text
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.example.com
EMAIL_PORT=587
EMAIL_HOST_USER=provider-user
EMAIL_HOST_PASSWORD=provider-secret
EMAIL_USE_TLS=true
DEFAULT_FROM_EMAIL=OwnBasket <noreply@example.com>
CANONICAL_BASE_URL=https://shop.example.com
```

Never commit real credentials. The centralized service in `marketing/services/email_service.py` sends plain-text and HTML alternatives, rejects header injection, logs only hashed recipients, and isolates backend failures.

## Newsletter and consent

The footer form requires explicit consent and uses CSRF protection plus a honeypot. Submissions always receive a generic response to avoid email enumeration. A subscription remains pending until the signed, opaque confirmation link is used. Duplicate email rows are prevented at the database level.

Unsubscribe links use timestamped Django signatures around a random UUID. GET renders a confirmation screen; only POST withdraws the subscription. Re-subscribing creates a fresh pending-confirmation flow. Newsletter withdrawal never blocks transactional order, password, or security messages.

Registration and checkout consent are optional and unchecked by default. Consent source, grant time, and withdrawal time are stored in `NotificationPreference`.

## Customer preferences

Authenticated customers can manage supported email preferences at `/marketing/preferences/` and inspect newsletter status, referrals, loyalty ledger entries, and stock alerts at `/marketing/engagement/`. SMS, WhatsApp, push, and unimplemented price-drop claims are intentionally absent.

## Campaign workflow

The post-migrate hook creates a least-privilege `Marketing Manager` group containing only subscriber/campaign/result permissions; it does not grant user-password, payment, seller-finance, or security-setting access. Authorized staff can create draft campaigns, preview safely escaped content, inspect a dynamic recipient count, send a test only to their own staff email, and schedule a campaign. Campaigns reuse the existing coupon engine and refuse to send an unavailable coupon. Recipient addresses are not stored in campaign delivery analytics; SHA-256 hashes provide deduplication.

Bulk campaigns are never sent from a web request. The scheduled command processes bounded recipient batches. Supported dynamic segments use real users, orders, wishlist entries, newsletter subscriptions, consent, and preferences.

## Batch commands

Every command supports `--dry-run` and a bounded `--limit`:

```bash
python manage.py process_abandoned_carts --dry-run --limit 100
python manage.py process_wishlist_reminders --dry-run --limit 100
python manage.py process_stock_alerts --dry-run --limit 100
python manage.py send_scheduled_campaigns --dry-run --limit 500
```

Example cron entries (adjust the virtual environment and project paths):

```cron
15 * * * * cd /srv/ownbasket && /srv/ownbasket/venv/bin/python manage.py process_abandoned_carts --limit 100
30 8 * * * cd /srv/ownbasket && /srv/ownbasket/venv/bin/python manage.py process_wishlist_reminders --limit 100
*/20 * * * * cd /srv/ownbasket && /srv/ownbasket/venv/bin/python manage.py process_stock_alerts --limit 100
*/10 * * * * cd /srv/ownbasket && /srv/ownbasket/venv/bin/python manage.py send_scheduled_campaigns --limit 500
```

Use a single scheduler instance or a deployment lock when horizontally scaled. Celery is not currently installed; these commands are the production scheduling boundary.

## Eligibility and frequency

- Abandoned carts require a linked logged-in user, non-empty active cart, configured inactivity, explicit marketing consent, specific reminder preference, and remaining reminder allowance.
- Checkout marks its cart inactive, excluding completed carts.
- Wishlist reminders include only current active, in-stock products and enforce a configurable send frequency.
- Stock alerts require an authenticated user preference, are unique per user/product, and deactivate only after successful delivery.

Environment tuning:

```text
MARKETING_HIGH_VALUE_THRESHOLD=50000
ABANDONED_CART_MIN_HOURS=24
ABANDONED_CART_MAX_REMINDERS=2
WISHLIST_REMINDER_DAYS=14
WISHLIST_REMINDER_FREQUENCY_DAYS=30
```

## Referral and loyalty foundations

Each customer receives an opaque referral code. A referred customer can have only one referral record, and model validation rejects self-referral. No reward is issued because qualification and reward rules are intentionally undefined.

Loyalty points use signed immutable ledger entries. Balance is derived from the ledger, zero entries and negative resulting balances are rejected, and admin adjustments record the acting staff user. Automatic earning, redemption, expiry, and cancellation rewards remain disabled until approved business rules exist.

## Privacy and analytics

Available analytics are sent, failed, unsubscribed subscription status, current candidate counts, and reliable coupon redemption data in the existing coupon engine. Open and click rates are not shown because no tracking pixel or redirect tracking was introduced. Customer email addresses are never placed in campaign delivery logs or public views.

## Verification

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
```
