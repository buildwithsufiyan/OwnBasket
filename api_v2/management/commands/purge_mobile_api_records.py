from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from api_v2.models import IdempotencyRecord, MobileSession, SyncOperation, UsedRefreshToken


class Command(BaseCommand):
    help = 'Purge expired mobile credentials and bounded API replay/sync records.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--sync-days', type=int, default=30)

    def handle(self, *args, **options):
        now = timezone.now()
        sync_days = max(7, min(options['sync_days'], 365))
        querysets = {
            'used refresh token': UsedRefreshToken.objects.filter(expires_at__lt=now),
            'expired/revoked mobile session': MobileSession.objects.filter(
                Q(refresh_expires_at__lt=now - timedelta(days=7)) | Q(absolute_expires_at__lt=now - timedelta(days=7))
            ),
            'idempotency record': IdempotencyRecord.objects.filter(expires_at__lt=now),
            'sync operation': SyncOperation.objects.filter(updated_at__lt=now - timedelta(days=sync_days)),
        }
        counts = {label: queryset.count() for label, queryset in querysets.items()}
        if not options['dry_run']:
            for queryset in querysets.values():
                queryset.delete()
        prefix = 'DRY RUN: ' if options['dry_run'] else ''
        self.stdout.write(prefix + ', '.join(f'{count} {label}(s)' for label, count in counts.items()))
