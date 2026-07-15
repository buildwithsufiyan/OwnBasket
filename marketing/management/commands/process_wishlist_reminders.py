from django.conf import settings
from django.core.management.base import BaseCommand

from marketing.services.reminders import send_wishlist_reminder, wishlist_candidates


class Command(BaseCommand):
    help = 'Send bounded wishlist reminders using only current, in-stock wishlist products.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--limit', type=int, default=100)

    def handle(self, *args, **options):
        limit = max(1, min(options['limit'], 1000))
        users = list(wishlist_candidates()[:limit])
        if options['dry_run']:
            self.stdout.write(f'DRY RUN: {len(users)} wishlist recipient(s) eligible; no email sent.')
            return
        sent = skipped = 0
        for user in users:
            success = send_wishlist_reminder(user, settings.CANONICAL_BASE_URL)
            sent += int(success)
            skipped += int(not success)
        self.stdout.write(self.style.SUCCESS(f'Wishlist recipients={len(users)} sent={sent} skipped={skipped}'))
