# OwnBasket production checklist

## Configuration and security

- [ ] `DJANGO_ENV=production` and `DJANGO_DEBUG=false`
- [ ] Unique secret key stored outside Git
- [ ] Exact allowed hosts and HTTPS trusted origins
- [ ] Valid TLS certificate, HTTPS redirect, secure cookies, HSTS reviewed
- [ ] Reverse-proxy SSL header trusted only from the proxy
- [ ] CSP reports reviewed before enforcement
- [ ] Rate limiting and provider webhook validation tested
- [ ] `python manage.py check --deploy` reviewed with production variables

## Data and services

- [ ] Production PostgreSQL configured; connection and least-privilege user tested
- [ ] Migration plan reviewed and migrations applied
- [ ] Redis/cache configured or local-cache limitations accepted
- [ ] SMTP delivery and sender authentication tested
- [ ] Payment sandbox flow, keys, callbacks, and error handling tested
- [ ] Persistent media storage and upload limits tested
- [ ] Database, media, and secrets backups verified off-server
- [ ] Restore rehearsal and rollback owner/date recorded

## Release and storefront

- [ ] Dependencies installed from `requirements.txt`
- [ ] `collectstatic` succeeds and hashed assets load
- [ ] Gunicorn/service manager and reverse proxy configured
- [ ] Homepage, PLP, PDP, search/filter, cart, checkout, account, and admin smoke-tested
- [ ] Sitemap and robots use the production canonical domain
- [ ] Titles, descriptions, canonicals, Open Graph, and structured data validated
- [ ] 400/403/404/500 pages render without debug details
- [ ] Health checks, logging, alerts, and log retention configured
- [ ] Keyboard navigation, focus, labels, alt text, and reduced motion checked
- [ ] Mobile layouts and real uploaded-image dimensions checked
- [ ] Production Lighthouse/Core Web Vitals baseline recorded
- [ ] Full test suite and migration check pass
- [ ] Superuser access secured with a strong unique password
- [ ] Release commit and rollback target recorded
