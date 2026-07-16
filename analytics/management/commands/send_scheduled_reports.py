from datetime import timedelta

from django.core.mail import EmailMessage
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from analytics.forms import validated_period
from analytics.models import ScheduledReport
from analytics.services.exports import csv_response, excel_response
from analytics.views import _export_definition


class Command(BaseCommand):
    help = 'Send due scheduled analytics reports in a bounded, duplicate-safe batch.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--limit', type=int, default=25)

    def handle(self, *args, **options):
        limit = options['limit']
        if limit < 1 or limit > 500:
            raise CommandError('--limit must be between 1 and 500.')
        due_ids = list(ScheduledReport.objects.filter(active=True, next_run__lte=timezone.now()).values_list('id', flat=True)[:limit])
        if options['dry_run']:
            self.stdout.write(f'DRY RUN: {len(due_ids)} scheduled report(s) due; nothing sent or updated.')
            return
        sent = 0
        for report_id in due_ids:
            with transaction.atomic():
                report = ScheduledReport.objects.select_for_update().get(pk=report_id)
                if not report.active or report.next_run > timezone.now():
                    continue
                form, period = validated_period(report.filters or {'preset': 'last_30_days'})
                if period is None:
                    self.stderr.write(f'Skipping report {report.pk}: invalid filters: {form.errors.as_text()}')
                    continue
                try:
                    title, headers, rows = _export_definition(report.report_type, *period)
                except Exception as exc:
                    self.stderr.write(f'Skipping report {report.pk}: {exc}')
                    continue
                filename = f'ownbasket-{report.report_type}-{timezone.localdate()}'
                response = csv_response(filename, headers, rows) if report.format == ScheduledReport.Format.CSV else excel_response(filename, title, headers, rows)
                content = b''.join(chunk.encode('utf-8') if isinstance(chunk, str) else chunk for chunk in response.streaming_content) if getattr(response, 'streaming', False) else response.content
                if response.status_code != 200:
                    self.stderr.write(f'Skipping report {report.pk}: export dependency unavailable.')
                    continue
                extension = report.format
                message = EmailMessage(subject=f'OwnBasket scheduled report: {title}', body='Attached is the requested OwnBasket report. Verify financial and tax figures before external use.', to=[report.recipient])
                message.attach(f'{filename}.{extension}', content, response.get('Content-Type'))
                message.send(fail_silently=False)
                now = timezone.now()
                increments = {'daily': timedelta(days=1), 'weekly': timedelta(days=7), 'monthly': timedelta(days=30)}
                report.last_sent = now
                report.next_run = max(report.next_run, now) + increments[report.frequency]
                report.save(update_fields=('last_sent', 'next_run'))
                sent += 1
        self.stdout.write(self.style.SUCCESS(f'Sent {sent} scheduled report(s).'))
