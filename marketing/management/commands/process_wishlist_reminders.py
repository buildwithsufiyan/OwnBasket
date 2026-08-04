from marketing.services.reminders import send_wishlist_reminder, wishlist_candidates

from ._batch import BatchReminderCommand


class Command(BatchReminderCommand):
    help = 'Send bounded wishlist reminders using only current, in-stock wishlist products.'
    candidate_label = 'wishlist recipient'
    result_label = 'Wishlist recipients'
    isolate_failures = False

    def get_candidates(self):
        return wishlist_candidates()

    def send(self, candidate, base_url):
        return send_wishlist_reminder(candidate, base_url)
