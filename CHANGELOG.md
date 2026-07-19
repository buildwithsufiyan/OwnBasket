# Changelog

All notable OwnBasket changes are documented here. The project follows Conventional Commits; the first stable semantic-versioned release will be `v1.0.0` after Phase 20.

## Unreleased

### Phase 18 — Marketplace and Seller Platform

#### Added

- Singleton marketplace settings for enable/disable, single-vendor and multi-vendor modes, seller registration, global commission defaults, and low-stock notifications.
- Seller business, contact, masked identity-reference, tax-structure, approval, rejection, suspension, document, and queued email-notification workflows.
- Seller dashboard revenue, orders, products, inventory health, reservations, approved ratings/reviews, recent orders, and performance analytics.
- Searchable public seller directory and storefronts with banners, logos, descriptions, contact details, policies, products, and verified ratings.
- Seller-owned product galleries, variants, attributes, pricing, visibility, stock, and inventory audit history.
- Seller order detail, packing and ready-to-ship states, fulfillment timelines, and seller-specific order history.
- Extensible global, category, seller, and seller/category commission-rule configuration without executing new payment calculations.
- Marketplace admin settings, seller review actions, suspension, stores, commission rules, inventory, fulfillment, notifications, and seller analytics.
- Typed seller notifications for approval, rejection, new orders, low stock, and reviews, with delivery-state structure for future email workers.
- Focused mode, ownership, inventory, fulfillment, commission, notification, integration, and backward-compatibility tests.

#### Security and performance

- Seller product, inventory, and order mutations are owner-scoped; unauthorized objects return 404 and admin override remains permission controlled.
- Identity references accept only masked values or short administrative codes; uploaded seller/product media continues through secure upload validation.
- Seller dashboards, store pages, orders, reviews, and inventory use aggregate queries, related-object loading, pagination, and bounded recent lists.

#### Database

- Added `marketplace.0002_marketplacesettings_sellernotification_email_status_and_more`.

### Phase 17 — Customer Experience and Personalization

#### Added

- Verified-purchase reviews with ratings, titles, descriptions, optional images, helpful votes, owner editing/deletion, moderation, rating distribution, and pagination.
- Multiple wishlist collections with sharing, move-to-cart, save-for-later, bulk removal, price-change indicators, stock visibility, and collection limits.
- Guest and authenticated recently viewed products on product and homepage surfaces, with configurable limits and retention.
- Deterministic related-product and frequently-bought-together recommendations using catalog and order data without external AI services.
- Session-backed product comparison with configurable limits and a responsive comparison table.
- Catalog filtering for category, subcategory, brand, price, rating, discount, availability, color, size, tags, sorting, and persistent query parameters.
- Admin-managed product badges, availability labels, review moderation, wishlist limits, comparison limits, and recommendation settings.
- Customer-experience documentation and focused integration coverage.

#### Changed

- Product gallery, sticky purchase controls, loading states, lazy loading, responsive layouts, empty states, keyboard navigation, and focus indicators were improved.
- Catalog and recommendation queries now use bounded candidate sets, pagination, and related-object loading where appropriate.
- Cart, wishlist, review, comparison, and mobile API flows now consistently enforce product availability and ownership rules.

#### Security

- Review mutations require authenticated ownership, purchase eligibility, CSRF protection, unique customer/product reviews, spam checks, and validated image type, size, and count.
- Wishlist and comparison mutations validate ownership, request method, item limits, and marketplace visibility.

#### Database

- Added `products.0016_customerexperiencesettings_and_more`.
- Added `wishlist.0002_wishlistsettings_alter_wishlist_options_and_more`, including migration of existing wishlist rows into per-user Favorites collections.

## Earlier phases

Phases 9–16 established advanced administration, production foundations, marketplace groundwork, marketing, analytics, security, PWA/mobile APIs, intelligent search, and deterministic personalization. Their detailed operational documentation remains under [`docs/`](docs/).
