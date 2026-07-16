from django.core.cache import cache
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from orders.models import Order, PaymentTransaction, Refund


def bump_analytics_cache_version():
    try:
        cache.incr('analytics-cache-version')
    except ValueError:
        cache.set('analytics-cache-version', 2, None)


@receiver((post_save, post_delete), sender=Order)
@receiver((post_save, post_delete), sender=PaymentTransaction)
@receiver((post_save, post_delete), sender=Refund)
def invalidate_analytics_cache(**kwargs):
    bump_analytics_cache_version()
