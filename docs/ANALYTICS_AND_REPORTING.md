# OwnBasket analytics and reporting

## Financial definitions

Revenue reports use persisted order, item, payment and refund snapshots. An order is eligible when it is explicitly `paid` or has reached the existing operational completion status `Delivered`; a failed payment is always excluded. The system does not invent cancellation/return states that are absent from `Order.STATUS_CHOICES`.

- Gross sales: sum of the order `subtotal` snapshot (item pre-discount selling amounts captured by checkout).
- Discounts: persisted `discount_total`, including product/offer/coupon effects already calculated by the pricing engine.
- Tax: persisted `tax_amount`; it is zero until checkout or an accounting integration records tax.
- Shipping: persisted `shipping_amount`.
- Refunds: sum of real `Refund.amount` records created in the reporting period. Multiple rows per order support partial refunds.
- Net revenue: gross sales - discounts + tax + shipping - refunds.
- Average order value: net revenue divided by eligible order count. Zero orders produce zero, not a fabricated ratio.

Refund timing follows the refund transaction date, while gross sales follow the order date. This makes period cash adjustments explicit. Revenue is bookkeeping-oriented and must be reconciled with the payment provider and general ledger.

## Data coverage and limitations

Legacy orders have no historical payment/tax/cost snapshot. Delivered legacy orders are treated as completed; pending COD orders are not revenue. Checkout now snapshots the submitted payment method and product cost on each new order line. It does not mark COD paid before delivery and does not calculate tax that the checkout pricing engine did not charge.

Product view and wishlist counters exist, but views are cumulative and not session/order attributed. Therefore conversion rate is intentionally not calculated. Customer reports export internal IDs and aggregates by default, not email, phone, address, password or authentication data.

## Tax and GST foundation

Order and item tax snapshots plus customer state provide a future integration point. Existing product tax percentages are catalog metadata, not evidence that tax was charged. HSN/SAC, supply state and CGST/SGST/IGST components are currently unavailable, so reports show a clear unavailable state instead of deriving or fabricating GST. This is not a legal-compliance report; an accountant must verify classifications, place-of-supply rules, invoice treatment and filings.

## Profit and margin foundation

Products contain cost price and new order lines snapshot it. Profit may only be calculated for lines with a known cost snapshot. The intended formula is net merchandise revenue - cost of goods - refund impact - seller commission - explicitly configured operational charges. Legacy lines with `NULL` cost remain unknown; zero must not be interpreted as a verified zero cost. No operational-charge model currently exists, so a net-profit claim is disabled.

## Reports

The staff analytics area is mounted at `/admin/analytics/` and includes dashboard, sales/order/payment, product/category/brand/inventory, customer/coupon, seller, refund and tax views. Date presets and custom ranges use the active Django timezone, inclusive calendar dates implemented as a half-open `[start midnight, day-after-end midnight)` query. Future dates, reversed dates and ranges over ten years are rejected. Comparison mode uses an immediately preceding equal-length period and returns `None` when a percentage denominator is zero.

Seller-facing analytics remain in the marketplace dashboard and are scoped through `request.seller`. The admin seller report is staff-only and cross-seller.

## Permissions and privacy

All analytics URLs require an authenticated staff user plus `orders.view_financial_reports` (superusers bypass normal permission checks). Exports additionally require `orders.export_financial_reports`. `analytics.manage_scheduled_reports` controls scheduled-report administration. Role groups can be assigned these permissions without exposing order administration or customer security fields.

Exports omit addresses, passwords, tokens, payment card details, provider secrets and seller bank information. Payment provider references are not exported. Spreadsheet-formula prefixes are apostrophe escaped to prevent CSV injection. Responses use `no-store`; CSV is streamed in UTF-8 with a BOM. Excel export requires `openpyxl`, freezes the header and constrains column widths. Extremely large recurring exports should move to a background object-storage workflow before production scale.

## Scheduling

`ScheduledReport` stores report type, frequency, recipient, format, JSON filters, active state, and last/next run. No web request sends reports automatically. Run a bounded batch from a trusted scheduler:

```text
python manage.py send_scheduled_reports --dry-run --limit 25
python manage.py send_scheduled_reports --limit 25
```

Rows are locked and rechecked before sending to prevent two workers from sending the same due record concurrently. The configured Django email backend is used. Production requires a reliable scheduler, email provider, monitoring, retention policy and failure retry policy.

## Performance and caching

Reports use database aggregation, filtered annotations, correlated subqueries for product/dimension sales, `select_related`, bounded UI result sets, iterator-based exports and date/status indexes. Dashboard summary cards are cached for five minutes with a version key invalidated by order/payment/refund changes. Export and seller-user data are not cached. For high volume, add asynchronous export jobs, database-specific query plans, materialized summaries and lifecycle-based cache invalidation.

## Deployment checklist

Apply migrations, install locked requirements, assign permissions, configure email and timezone, then reconcile sample orders against payment/refund records. Run `python manage.py check`, `python manage.py makemigrations --check --dry-run`, and the full test suite. Finance/accounting owners must approve revenue, refund and tax definitions before relying on reports operationally.
