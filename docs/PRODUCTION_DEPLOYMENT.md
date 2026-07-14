# OwnBasket production deployment

This guide is host-neutral and works for a VPS, Hostinger Python/VPS plan, Render, Railway, or a similar WSGI host. Shared hosting must support Python 3.12+, a persistent application process, environment variables, and a writable persistent media directory.

## 1. Provision and configure

1. Create a non-root service account, Python virtual environment, PostgreSQL database, and optionally Redis.
2. Install with `python -m pip install -r requirements.txt`.
3. Configure environment variables from `.env.example` in the host control panel or service manager. Never upload the real `.env`, database password, payment secrets, or Django secret to Git.
4. Set `DJANGO_ENV=production`, `DJANGO_DEBUG=false`, a unique `DJANGO_SECRET_KEY`, exact `DJANGO_ALLOWED_HOSTS`, HTTPS `DJANGO_CSRF_TRUSTED_ORIGINS`, and the public `CANONICAL_BASE_URL`.
5. Use `DATABASE_URL` for PostgreSQL. SQLite is a local-development fallback, not the recommended production database.

## 2. Release commands

Take a verified database and media backup first, then run:

```text
python manage.py check
python manage.py check --deploy
python manage.py migrate --plan
python manage.py migrate --noinput
python manage.py collectstatic --noinput
python manage.py createsuperuser
```

Create the superuser only on the first deployment. `collectstatic` writes hashed, compressed assets for WhiteNoise. Uploaded media must live on a persistent volume or supported object storage; WhiteNoise does not serve user uploads.

Start with the `Procfile` command or `gunicorn config.wsgi:application --config gunicorn.conf.py`. On a VPS, supervise Gunicorn with systemd and proxy through Nginx. Nginx should terminate HTTPS, forward `Host` and `X-Forwarded-Proto`, limit request sizes consistently with Django, and serve `/media/` only from the intended persistent directory. Do not expose the development server.

## 3. HTTPS, email, payments, and media

- Issue and auto-renew a TLS certificate before enabling redirects. Keep `TRUST_PROXY_SSL_HEADER=true` only when the trusted proxy overwrites that header.
- Validate SMTP with a real order/status email before launch. Console email is development-only.
- Configure only the payment provider in use. Make a sandbox transaction and verify webhook signatures without logging payload secrets or customer payment data.
- Back media with versioning or snapshots. Validate extensions/content in application workflows and keep the 5 MB in-memory threshold; the proxy should enforce an appropriate total upload limit.
- Keep CSP in report-only mode while reviewing violations from admin, payment, font, and visual-editor flows. Remove required inline dependencies or add nonces/hashes before setting `CSP_REPORT_ONLY=false`.

## 4. Operations and observability

Use `/health/` for a fast liveness check and `/health/?database=1` for a readiness probe. Send console output to the platform log collector. `DJANGO_LOG_FILE` is optional and requires a persistent writable log directory with OS rotation/retention. Never log passwords, tokens, card data, full request bodies, or secret settings.

Monitor 5xx/429 rates, response latency, database connections, Redis availability, disk/media usage, email failures, order failures, and certificate expiry. Run a real mobile/desktop Lighthouse audit against the deployed site; no synthetic score is claimed by this repository change.

## 5. Backup, recovery, and rollback

- Database: encrypted daily backups plus point-in-time recovery where available; retain daily/weekly/monthly copies according to business policy.
- Media: daily incremental/versioned off-server backup. Database and media restore points should be time-aligned.
- Secrets: store encrypted in a password manager or secrets service, separately from application backups.
- Before every release: database snapshot, media snapshot, release commit recorded, and restore test status confirmed.
- Quarterly: restore database and media into an isolated environment, run checks, sample orders/products/images, and record recovery time.
- Rollback: stop traffic-changing jobs, deploy the previous known-good commit, restore dependencies/static assets, and reverse a migration only when its migration is explicitly reversible. For destructive schema/data changes, restore the pre-release backup instead of improvising.

Post-deployment verify `/`, `/home/`, `/shop/`, product/category/brand pages, login, cart, checkout sandbox flow, dashboard/admin permissions, `/sitemap.xml`, `/robots.txt`, `/health/`, static/media assets, branded errors, email, CSP reports, and logs.

## Known repository hygiene prerequisite

The project history already tracks a development SQLite database, uploaded media, and old log files. They were deliberately not deleted during Phase 10. Before a public deployment, inventory and back them up, remove sensitive/runtime files from Git tracking in a dedicated reviewed change (without deleting the required production copies), rotate any exposed credentials, and assess whether Git-history remediation is necessary.
