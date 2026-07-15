from django.conf import settings
from django.core.management.base import BaseCommand

from marketing.services.reminders import abandoned_cart_candidates, send_abandoned_cart_reminder


class Command(BaseCommand):
    help = 'Process consented, identifiable abandoned carts in a bounded batch.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--limit', type=int, default=100)

    def handle(self, *args, **options):
        limit = max(1, min(options['limit'], 1000))
        carts = list(abandoned_cart_candidates()[:limit])
        if options['dry_run']:
            self.stdout.write(f'DRY RUN: {len(carts)} abandoned cart(s) eligible; no email sent.')
            return
        sent = failed = 0
        for cart in carts:
            try:
                success = send_abandoned_cart_reminder(cart, settings.CANONICAL_BASE_URL)
            except Exception as exc:
                self.stderr.write(f'Cart #{cart.pk}: {type(exc).__name__}')
                success = False
            sent += int(success)
            failed += int(not success)
        self.stdout.write(self.style.SUCCESS(f'Abandoned carts processed={len(carts)} sent={sent} failed={failed}'))
