from marketing.services.reminders import abandoned_cart_candidates, send_abandoned_cart_reminder

from ._batch import BatchReminderCommand


class Command(BatchReminderCommand):
    help = 'Process consented, identifiable abandoned carts in a bounded batch.'
    candidate_label = 'abandoned cart'
    result_label = 'Abandoned carts'

    def get_candidates(self):
        return abandoned_cart_candidates()

    def send(self, candidate, base_url):
        return send_abandoned_cart_reminder(candidate, base_url)
