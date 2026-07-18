from django.core.management.base import BaseCommand

from api_v2.models import PushDelivery
from api_v2.push import process_due_deliveries


class Command(BaseCommand):
    help = 'Process a bounded batch of queued/retry push deliveries.'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=100)
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        limit = max(1, min(options['limit'], 1000))
        if options['dry_run']:
            count = PushDelivery.objects.filter(status__in=('queued', 'retry')).count()
            self.stdout.write(f'DRY RUN: {min(count, limit)} push delivery record(s) eligible.')
            return
        deliveries = process_due_deliveries(limit=limit)
        delivered = sum(item.status == PushDelivery.Status.DELIVERED for item in deliveries)
        retrying = sum(item.status == PushDelivery.Status.RETRY for item in deliveries)
        failed = sum(item.status == PushDelivery.Status.FAILED for item in deliveries)
        self.stdout.write(f'Push processed={len(deliveries)} delivered={delivered} retrying={retrying} failed={failed}')
