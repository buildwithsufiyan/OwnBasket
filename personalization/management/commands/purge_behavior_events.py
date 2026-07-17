from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from personalization.models import BehaviorEvent


class Command(BaseCommand):
    help = 'Delete privacy-friendly personalization events older than the retention window.'

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=180)
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        days = options['days']
        if days < 30:
            raise CommandError('Retention must be at least 30 days.')
        queryset = BehaviorEvent.objects.filter(created_at__lt=timezone.now() - timedelta(days=days))
        count = queryset.count()
        if not options['dry_run']:
            queryset.delete()
        prefix = 'DRY RUN: ' if options['dry_run'] else ''
        self.stdout.write(f'{prefix}{count} behavior event(s) older than {days} days.')
