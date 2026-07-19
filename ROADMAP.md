# OwnBasket Version 1.0 Roadmap

OwnBasket Version 1.0 is completed at Phase 20. Each phase must preserve existing behavior, use production-ready Django architecture, pass migration validation and the complete test suite, and be merged through normal non-destructive Git workflows.

## Completed

### Phase 18 — Marketplace and Seller Platform

- Configurable single-vendor and multi-vendor operation with marketplace enable/disable controls
- Seller applications, approval/rejection/suspension, business and verification structure, public stores, and ratings
- Seller dashboards, product media/variants/attributes, inventory reservations/history, fulfillment timelines, analytics, and notifications
- Global/category/seller commission-rule structure, enterprise admin controls, seller isolation, pagination, and query optimization

### Phase 17 — Customer Experience and Personalization

- Enterprise reviews and advanced wishlist collections
- Recently viewed, related products, and frequently bought together
- Product comparison, advanced catalog filters, labels, and stock indicators
- Product gallery, sticky purchase controls, responsive UX, accessibility, security, and query improvements

## Planned for Version 1.0

### Phase 19 — Enterprise CMS and Marketing Suite

- Landing-page builder, dynamic sections, blog, and SEO/meta management
- Popup, banner, and announcement builders
- Newsletter, email-template, contact-form, and marketing-automation management
- Analytics dashboard improvements

### Phase 20 — OwnBasket Enterprise Edition

No major new features. Phase 20 is limited to production polish: bug fixes, refactoring, security and accessibility audits, database and performance optimization, responsive and image improvements, static cleanup, Django best practices, complete documentation, full testing, migration validation, production configuration, and repository cleanup.

Phase 20 concludes with release tag `v1.0.0` and release title **OwnBasket Enterprise Edition**.

## Reserved for Version 2.x

- Payment gateways, UPI, wallets, loyalty points, and subscription products
- Shipping and logistics integrations
- AI chat, voice search, and external AI recommendation services
- ERP and CRM integrations
- Native mobile applications and expanded mobile/push capabilities
- Live chat, advanced warehouse/inventory intelligence, and enterprise reporting
- Internationalization, multiple currencies, and multiple languages

Existing Phase 15 mobile/PWA and push foundations, Phase 16 deterministic recommendations, and existing warehouse functionality remain supported. The Version 2.x restriction applies to major expansions and external integrations; existing features will not be removed.

## Delivery rules

For each remaining phase:

1. Fetch all remotes and verify a clean working tree.
2. Preserve a `backup-before-phaseXX` branch and work on `phase-XX-feature-name`.
3. Use Conventional Commits and never use force push, hard reset, or destructive clean commands.
4. Run `python manage.py check`, migration validation, relevant tests, and the full test suite.
5. Merge non-interactively and push normally to both GitHub repositories only after verification succeeds.
