from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from marketing.models import Campaign, CampaignDelivery, EngagementDelivery, NewsletterSubscription
from marketing.services.email_service import recipient_hash, send_branded_email
from marketing.services.segments import recipient_count, recipients_for_segment
from marketing.services.tokens import make_subscription_token


def coupon_is_sendable(coupon):
    return not coupon or coupon.is_available()


def send_campaign(campaign, *, base_url, limit=500):
    if campaign.status not in {Campaign.Status.SCHEDULED, Campaign.Status.PROCESSING}:
        return {'sent': 0, 'failed': 0}
    if not coupon_is_sendable(campaign.coupon):
        campaign.status = Campaign.Status.FAILED
        campaign.save(update_fields=('status', 'updated_at'))
        return {'sent': 0, 'failed': 0}
    campaign.status = Campaign.Status.PROCESSING
    campaign.save(update_fields=('status', 'updated_at'))
    sent = failed = 0
    User = get_user_model()
    for index, recipient in enumerate(recipients_for_segment(campaign.target_segment)):
        if index >= limit:
            break
        hashed = recipient_hash(recipient.email)
        if CampaignDelivery.objects.filter(campaign=campaign, recipient_hash=hashed).exists():
            continue
        user = User.objects.filter(pk=recipient.user_id).first() if recipient.user_id else None
        subscription = NewsletterSubscription.objects.filter(pk=recipient.subscription_id).first() if recipient.subscription_id else None
        if not subscription:
            subscription = NewsletterSubscription.objects.filter(email__iexact=recipient.email).first()
        if not subscription and user:
            preference = getattr(user, 'notification_preferences', None)
            subscription = NewsletterSubscription.objects.create(
                email=recipient.email, user=user, status=NewsletterSubscription.Status.ACTIVE,
                source='account_consent', subscribed_at=getattr(preference, 'consent_recorded_at', None) or timezone.now(),
            )
        unsubscribe_url = ''
        if subscription:
            unsubscribe_url = f'{base_url}/marketing/newsletter/unsubscribe/{make_subscription_token(subscription)}/'
        success = send_branded_email(
            subject=campaign.subject, recipient=recipient.email, template_name='campaign',
            context={'campaign': campaign, 'user': user, 'coupon': campaign.coupon, 'unsubscribe_url': unsubscribe_url, 'preview_text': campaign.preview_text},
            kind=EngagementDelivery.Kind.CAMPAIGN, reference=campaign.pk, user=user,
        )
        CampaignDelivery.objects.create(
            campaign=campaign, recipient_hash=hashed,
            status=EngagementDelivery.Status.SENT if success else EngagementDelivery.Status.FAILED,
            error_code='' if success else 'delivery_failed',
        )
        sent += int(success)
        failed += int(not success)
    with transaction.atomic():
        campaign.sent_count += sent
        campaign.failed_count += failed
        delivered_total = campaign.deliveries.count()
        campaign.status = Campaign.Status.SENT if delivered_total >= recipient_count(campaign.target_segment) else Campaign.Status.PROCESSING
        campaign.completed_at = timezone.now() if campaign.status == Campaign.Status.SENT else None
        campaign.save(update_fields=('sent_count', 'failed_count', 'status', 'completed_at', 'updated_at'))
    return {'sent': sent, 'failed': failed}
