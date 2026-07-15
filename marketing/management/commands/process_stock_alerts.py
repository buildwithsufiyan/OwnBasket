from django.conf import settings
from django.core.management.base import BaseCommand

from marketing.services.reminders import send_stock_alert, stock_alert_candidates


class Command(BaseCommand):
    help = 'Process active back-in-stock alerts in a bounded, failure-isolated batch.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--limit', type=int, default=100)

    def handle(self, *args, **options):
        limit = max(1, min(options['limit'], 1000))
        alerts = list(stock_alert_candidates()[:limit])
        if options['dry_run']:
            self.stdout.write(f'DRY RUN: {len(alerts)} stock alert(s) eligible; no email sent.')
            return
        sent = failed = 0
        for alert in alerts:
            try:
                success = send_stock_alert(alert, settings.CANONICAL_BASE_URL)
            except Exception as exc:
                self.stderr.write(f'Alert #{alert.pk}: {type(exc).__name__}')
                success = False
            sent += int(success)
            failed += int(not success)
        self.stdout.write(self.style.SUCCESS(f'Stock alerts processed={len(alerts)} sent={sent} failed={failed}'))
