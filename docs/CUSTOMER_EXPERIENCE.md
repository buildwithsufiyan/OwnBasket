# Customer Experience and Personalization

Phase 17 extends the existing catalog and Phase 16 recommendation services without introducing an external AI, payment, or shipping dependency.

## Storefront features

- Verified-purchase reviews support ratings, titles, text, optional images, owner edits/deletion, helpful votes, moderation, rating summaries, distribution, and pagination.
- Wishlist collections support moving products, save-for-later, bulk removal, move-to-cart, public share links, stock visibility, and price-change indicators.
- Recently viewed products work for anonymous sessions and authenticated behavior history. Retention and display limits are configurable in Customer Experience Settings.
- Related products use category, brand, tags, configurable price bounds, popularity, and new-arrival fallback. Frequently bought together uses real order co-occurrence before its configured related-product fallback.
- Session-backed comparison has a configurable item limit and a responsive, difference-aware table.
- Catalog filters cover category, subcategory, brand, price, discount, rating, availability, color, size, feature tags, and sorting while retaining query-string state.
- Product badges and availability messages are managed in Django admin.

## Administration

Use **Products > Customer Experience Settings** for singleton limits and recommendation behavior. Use **Products > Product badges** for label assignment and **Products > Product reviews** for moderation. Wishlist limits are managed under **Wishlist > Wishlist settings**.

## Security and data handling

Review and wishlist mutations require POST requests with CSRF protection. Reviews are restricted to purchasers, unique per customer/product, owner-scoped for edits and deletion, honeypot/link checked, and image type/size limited. Helpful votes are unique per user/review. Wishlist collections and compare inputs are ownership and marketplace-visibility checked. User content is rendered through Django templates with automatic escaping.

No secrets, API keys, paid AI APIs, payment gateways, or shipping integrations are required.

## Operations

Apply database changes and validate the application:

```powershell
python manage.py migrate
python manage.py check
python manage.py test
```

Phase 16 behavior history can be pruned on a schedule with the existing `purge_behavior_events` management command. Recently viewed reads also enforce the configured retention window automatically.
