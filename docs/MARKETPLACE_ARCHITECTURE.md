# Marketplace and Seller Platform

Phase 18 extends OwnBasket's earlier marketplace foundation into a configurable seller platform. It introduces no payment gateway, shipping/logistics integration, wallet, loyalty system, external AI service, ERP/CRM integration, or new mobile API.

## Operating modes

`MarketplaceSettings` is a singleton managed in Django admin.

- **Enabled + multi vendor** exposes approved seller products, seller registration, seller tools, the seller directory, and public stores.
- **Enabled + single vendor** exposes only legacy products whose `seller` is null. Seller registration, seller tools, and public seller pages return 404.
- **Disabled** behaves like single-vendor mode for catalog visibility and blocks marketplace surfaces.

When no settings row exists, in-memory defaults keep the established multi-vendor behavior. This makes the migration backward compatible and avoids a database write on ordinary reads.

## Domain model

- `SellerProfile` owns the store identity, business/contact details, masked identity reference, tax structure, policies, approval state, and legacy seller commission rate.
- `SellerDocument` stores validated identity, business, tax, bank-verification, or other evidence for admin review.
- `SellerInventory` records reserved stock beside the existing `Product.stock`; `InventoryHistory` provides immutable adjustment snapshots and actor attribution.
- `SellerOrderFulfillment` creates one seller-specific fulfillment record per order and seller. `SellerOrderStatusHistory` records received, packing, and ready-to-ship transitions. Shipping remains structural only.
- `CommissionRule` represents global, category, seller, or seller/category rules with priority, activation windows, and future JSON conditions. Phase 18 does not apply these rules to payment calculations.
- `SellerNotification` classifies approval, rejection, new order, low stock, review, and general events and records future email delivery state.

## Seller workflows

Seller registration creates a pending profile. Admin reviewers can approve or reject it, and authorized administrators can suspend approved sellers. Pending sellers retain access to documents and store settings; approved sellers gain owner-scoped products, inventory, orders, analytics, and public store pages.

The seller product form supports the existing catalog fields plus additional images, variants, and specifications. Inventory adjustments update current and reserved stock in a transaction and append an audit event. Seller order detail is built only from order lines owned by the authenticated seller, then maintains a separate packing timeline without changing another seller's fulfillment state or the global order state.

## Security boundaries

- Django authentication and CSRF middleware protect seller mutations.
- Product, inventory, and order lookups begin from `request.seller` relationships; cross-seller identifiers return 404.
- Approval and suspension actions use custom Django permissions, with superuser override.
- Uploaded documents and product images use the existing secure upload forms.
- Identity references must be masked or short administrative references; payout references follow the same masking pattern.
- Django template auto-escaping remains enabled for seller descriptions, policies, notes, and reviews.

## Query and pagination strategy

Dashboard totals use conditional aggregates. Orders use `select_related`; review lists load product/user relationships; stores compute product/review metrics in one annotated query; storefront products load brand/category relationships; inventory loads product/category/brand relationships. Seller products, stores, orders, inventory, notifications, and reviews use pagination or bounded recent slices.

## Administration and operations

The Marketplace admin contains settings, seller applications and metrics, verification documents, commission rules, inventory/history, fulfillment/timelines, notification delivery state, and existing payout structure.

Apply and verify Phase 18 with:

```powershell
python manage.py migrate
python manage.py check
python manage.py makemigrations --check
python manage.py test marketplace
python manage.py test
```

The migration is `marketplace/migrations/0002_marketplacesettings_sellernotification_email_status_and_more.py`.
