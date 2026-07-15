from datetime import timedelta

from django import template
from django.utils import timezone

from cart.models import Cart
from marketing.models import Campaign, NewsletterSubscription, Referral, StockAlert


register = template.Library()


@register.simple_tag
def marketing_dashboard_stats():
    cutoff = timezone.now() - timedelta(hours=24)
    return {
        'active_subscribers': NewsletterSubscription.objects.filter(status=NewsletterSubscription.Status.ACTIVE).count(),
        'unsubscribed': NewsletterSubscription.objects.filter(status=NewsletterSubscription.Status.UNSUBSCRIBED).count(),
        'draft_campaigns': Campaign.objects.filter(status=Campaign.Status.DRAFT).count(),
        'scheduled_campaigns': Campaign.objects.filter(status=Campaign.Status.SCHEDULED).count(),
        'sent_campaigns': Campaign.objects.filter(status=Campaign.Status.SENT).count(),
        'abandoned_candidates': Cart.objects.filter(is_active=True, user__isnull=False, updated_at__lte=cutoff, cartitem__isnull=False).distinct().count(),
        'active_stock_alerts': StockAlert.objects.filter(is_active=True).count(),
        'referral_signups': Referral.objects.count(),
    }
