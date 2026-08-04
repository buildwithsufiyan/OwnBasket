from django.conf import settings
from django.core.management.base import BaseCommand


class BatchReminderCommand(BaseCommand):
    """Send one reminder per candidate in a bounded, failure-isolated batch."""

    max_limit = 1000
    candidate_label = 'candidate'
    result_label = 'Candidates'
    isolate_failures = True

    def get_candidates(self):
        raise NotImplementedError

    def send(self, candidate, base_url):
        raise NotImplementedError

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--limit', type=int, default=100)

    def handle(self, *args, **options):
        limit = max(1, min(options['limit'], self.max_limit))
        candidates = list(self.get_candidates()[:limit])
        if options['dry_run']:
            self.stdout.write(f'DRY RUN: {len(candidates)} {self.candidate_label}(s) eligible; no email sent.')
            return
        sent = failed = 0
        for candidate in candidates:
            if self.isolate_failures:
                try:
                    success = self.send(candidate, settings.CANONICAL_BASE_URL)
                except Exception as exc:
                    self.stderr.write(f'{self.candidate_label.capitalize()} #{candidate.pk}: {type(exc).__name__}')
                    success = False
            else:
                success = self.send(candidate, settings.CANONICAL_BASE_URL)
            sent += int(success)
            failed += int(not success)
        self.stdout.write(self.style.SUCCESS(
            f'{self.result_label} processed={len(candidates)} sent={sent} failed={failed}'
        ))
