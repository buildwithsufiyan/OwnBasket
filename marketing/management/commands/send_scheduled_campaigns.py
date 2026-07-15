from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from marketing.models import Campaign
from marketing.services.campaigns import send_campaign
from marketing.services.segments import recipient_count


class Command(BaseCommand):
    help = 'Send due scheduled campaigns in bounded batches; safe for cron execution.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--limit', type=int, default=500, help='Maximum recipients per campaign.')

    def handle(self, *args, **options):
        limit = max(1, min(options['limit'], 5000))
        campaigns = Campaign.objects.filter(
            status__in=(Campaign.Status.SCHEDULED, Campaign.Status.PROCESSING),
            scheduled_at__lte=timezone.now(),
        ).select_related('coupon').order_by('scheduled_at', 'pk')[:10]
        if options['dry_run']:
            for campaign in campaigns:
                self.stdout.write(f'DRY RUN: campaign #{campaign.pk} recipients={recipient_count(campaign.target_segment)}')
            return
        total_sent = total_failed = 0
        for campaign in campaigns:
            result = send_campaign(campaign, base_url=settings.CANONICAL_BASE_URL, limit=limit)
            total_sent += result['sent']
            total_failed += result['failed']
        self.stdout.write(self.style.SUCCESS(f'Campaigns processed={len(campaigns)} sent={total_sent} failed={total_failed}'))
