# Changelog

All notable OwnBasket changes are documented here. The project follows Conventional Commits; the first stable semantic-versioned release will be `v1.0.0` after Phase 20.

## Unreleased

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
