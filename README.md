# OwnBasket

OwnBasket is a production-oriented Django e-commerce platform developed by Md Sufiyan Hussain under QentraX. It combines a responsive storefront with configurable administration, marketplace, marketing, analytics, security, and Phase 15 mobile/PWA capabilities.

## Features

- Responsive homepage, product listings, product detail pages, categories, brands, and product carousels
- Cart, wishlist, checkout, orders, invoices, discounts, coupons, and inventory-aware commerce flows
- Admin-managed homepage sections, banners, products, themes, fonts, and visual storefront controls
- Multi-vendor marketplace foundation
- Marketing automation and customer engagement workflows
- Business analytics and reporting
- Production configuration for PostgreSQL, Redis, SMTP, static files, security headers, rate limiting, and audit logging
- Progressive Web App with install support, offline fallback, and service worker lifecycle
- Versioned mobile API with encrypted token sessions, refresh/revocation, idempotent writes, synchronization, push-device registration, and OpenAPI documentation

## Technology Stack

- Python and Django 6
- HTML5, CSS3, JavaScript, and Bootstrap
- SQLite for local development; PostgreSQL recommended for production
- Redis-compatible caching
- WhiteNoise and Gunicorn for production serving
- Pillow, ReportLab, and OpenPyXL for media, invoices, and reports

## Local Setup

Python 3.12 or newer is recommended.

```powershell
git clone https://github.com/QentraX/OwnBasket.git
cd OwnBasket
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Local development defaults to SQLite. Runtime configuration is read from environment variables; `.env.example` documents the production variables but Django does not automatically load a `.env` file. Set variables in the shell or configure the process manager that launches the application.

Before production deployment, configure at least `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS`, `DATABASE_URL`, `CACHE_URL`, email settings, secure-cookie/HTTPS settings, and `MOBILE_TOKEN_ENCRYPTION_KEY`.

## Verification

```powershell
python manage.py check
python manage.py test
```

For production-specific validation:

```powershell
$env:DJANGO_ENV = "production"
python manage.py check --deploy
```

## Project Structure

```text
accounts/       Customer accounts and authentication
analytics/      Business intelligence and reports
api_v2/         Phase 15 mobile API and push lifecycle
banners/        Homepage banners and presentation controls
cart/           Shopping-cart behavior
core/           Shared storefront functionality and PWA endpoints
marketing/      Engagement and automation workflows
marketplace/    Multi-vendor marketplace foundation
orders/         Checkout, orders, and invoices
products/       Catalog, pricing, brands, and inventory
security/       Audit and application-security controls
site_sections/  Configurable homepage sections
themes/         Theme management and conversion
wishlist/       Saved products
docs/           Deployment, security, analytics, marketing, PWA, and API guides
```

## Documentation

- [Production deployment](docs/PRODUCTION_DEPLOYMENT.md)
- [Production checklist](docs/PRODUCTION_CHECKLIST.md)
- [Security](docs/SECURITY.md)
- [Marketing automation](docs/MARKETING_AUTOMATION.md)
- [Analytics and reporting](docs/ANALYTICS_AND_REPORTING.md)
- [PWA and API](docs/PWA_AND_API.md)
- [Mobile API](docs/MOBILE_API.md)
- [AI recommendations and intelligent search](docs/AI_RECOMMENDATIONS.md)

## Project Status

Phases 9 through 16 are present on `main`. Phase 15 delivers the production mobile API and Progressive Web App platform. Phase 16 adds intelligent search, explainable recommendations, related products, behavior-based personalization, and popularity fallbacks without requiring an external paid AI service.

## Author

**Md Sufiyan Hussain**<br>
Founder, QentraX<br>
Full-Stack Django Developer and Backend Engineer

## License

This project is maintained as a personal and portfolio project. Commercial use, redistribution, or resale requires permission from the author.
