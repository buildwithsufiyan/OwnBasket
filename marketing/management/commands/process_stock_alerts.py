from marketing.services.reminders import send_stock_alert, stock_alert_candidates

from ._batch import BatchReminderCommand


class Command(BatchReminderCommand):
    help = 'Process active back-in-stock alerts in a bounded, failure-isolated batch.'
    candidate_label = 'stock alert'
    result_label = 'Stock alerts'

    def get_candidates(self):
        return stock_alert_candidates()

    def send(self, candidate, base_url):
        return send_stock_alert(candidate, base_url)
