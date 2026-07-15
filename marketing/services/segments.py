from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Count, Q, Sum
from django.utils import timezone

from marketing.models import Campaign, NewsletterSubscription


@dataclass(frozen=True)
class Recipient:
    email: str
    user_id: int | None = None
    subscription_id: int | None = None


def _opted_in_users():
    return get_user_model().objects.filter(
        is_active=True,
        email__gt='',
        notification_preferences__marketing_consent=True,
        notification_preferences__promotional_emails=True,
    )


def recipient_queryset(segment):
    users = _opted_in_users()
    now = timezone.now()
    if segment == Campaign.Segment.NEW_CUSTOMERS:
        return users.filter(date_joined__gte=now - timedelta(days=30))
    if segment == Campaign.Segment.RETURNING:
        return users.annotate(order_count=Count('order')).filter(order_count__gte=2)
    if segment == Campaign.Segment.COMPLETED_ORDERS:
        return users.filter(order__status='Delivered').distinct()
    if segment == Campaign.Segment.NO_ORDERS:
        return users.filter(order__isnull=True)
    if segment == Campaign.Segment.HIGH_VALUE:
        threshold = Decimal(str(getattr(settings, 'MARKETING_HIGH_VALUE_THRESHOLD', '50000')))
        return users.annotate(order_value=Sum('order__total_price', filter=Q(order__status='Delivered'))).filter(order_value__gte=threshold)
    if segment == Campaign.Segment.INACTIVE:
        cutoff = now - timedelta(days=90)
        return users.filter(Q(last_login__lt=cutoff) | Q(last_login__isnull=True, date_joined__lt=cutoff))
    if segment == Campaign.Segment.WISHLIST:
        return users.filter(wishlist__isnull=False).distinct()
    return users


def recipients_for_segment(segment):
    seen = set()
    if segment == Campaign.Segment.NEWSLETTER:
        queryset = NewsletterSubscription.objects.filter(status=NewsletterSubscription.Status.ACTIVE).only('id', 'email', 'user_id')
        for subscription in queryset.iterator(chunk_size=500):
            email = subscription.email.lower()
            if email not in seen:
                seen.add(email)
                yield Recipient(email, subscription.user_id, subscription.pk)
        return
    for user in recipient_queryset(segment).only('id', 'email').iterator(chunk_size=500):
        email = user.email.lower()
        if email not in seen:
            seen.add(email)
            yield Recipient(email, user.pk, None)


def recipient_count(segment):
    if segment == Campaign.Segment.NEWSLETTER:
        return NewsletterSubscription.objects.filter(status=NewsletterSubscription.Status.ACTIVE).values('email').distinct().count()
    return recipient_queryset(segment).values('email').distinct().count()
