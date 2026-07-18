from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .crypto import decrypt_provider_token
from .models import PushDelivery


PROVIDER_ADAPTERS = {}
MAX_ATTEMPTS = 5


def register_provider(name, sender):
    """Register a Firebase/APNs/Web Push adapter at process startup."""
    PROVIDER_ADAPTERS[name] = sender


def queue_push(device, *, event_key, title, body, target_path='/home/', data=None):
    if not device.notifications_enabled or not device.provider_token_encrypted:
        return None, False
    return PushDelivery.objects.get_or_create(
        device=device, event_key=event_key[:120],
        defaults={
            'title': title[:80], 'body': body[:240], 'target_path': target_path[:255],
            'data': data or {},
        },
    )


@transaction.atomic
def deliver_push(delivery_id):
    delivery = PushDelivery.objects.select_for_update().select_related('device').get(pk=delivery_id)
    if delivery.status in {PushDelivery.Status.DELIVERED, PushDelivery.Status.FAILED, PushDelivery.Status.CANCELLED}:
        return delivery
    device = delivery.device
    if not device.notifications_enabled or device.disabled_at:
        delivery.status = PushDelivery.Status.CANCELLED
        delivery.last_error_code = 'device_disabled'
        delivery.save(update_fields=('status', 'last_error_code', 'updated_at'))
        return delivery
    adapter = PROVIDER_ADAPTERS.get(device.provider)
    delivery.status = PushDelivery.Status.SENDING
    delivery.attempt_count += 1
    delivery.save(update_fields=('status', 'attempt_count', 'updated_at'))
    try:
        if adapter is None:
            raise RuntimeError('provider_not_configured')
        provider_message_id = adapter(
            token=decrypt_provider_token(device.provider_token_encrypted),
            title=delivery.title, body=delivery.body, target_path=delivery.target_path, data=delivery.data,
        )
    except Exception as exc:
        code = str(exc).split(':', 1)[0][:80] or 'delivery_failed'
        delivery.last_error_code = code
        if delivery.attempt_count >= MAX_ATTEMPTS:
            delivery.status = PushDelivery.Status.FAILED
            device.failure_count += 1
            if device.failure_count >= 3:
                device.notifications_enabled = False
                device.disabled_at = timezone.now()
            device.save(update_fields=('failure_count', 'notifications_enabled', 'disabled_at'))
        else:
            delivery.status = PushDelivery.Status.RETRY
            delivery.next_attempt_at = timezone.now() + timedelta(minutes=min(2 ** delivery.attempt_count, 60))
        delivery.save(update_fields=('status', 'last_error_code', 'next_attempt_at', 'updated_at'))
        return delivery
    delivery.status = PushDelivery.Status.DELIVERED
    delivery.provider_message_id = str(provider_message_id or '')[:160]
    delivery.delivered_at = timezone.now()
    delivery.last_error_code = ''
    delivery.save(update_fields=('status', 'provider_message_id', 'delivered_at', 'last_error_code', 'updated_at'))
    if device.failure_count:
        device.failure_count = 0
        device.save(update_fields=('failure_count',))
    return delivery


def process_due_deliveries(limit=100):
    ids = list(PushDelivery.objects.filter(
        status__in=(PushDelivery.Status.QUEUED, PushDelivery.Status.RETRY),
        next_attempt_at__lte=timezone.now(),
    ).order_by('next_attempt_at').values_list('pk', flat=True)[:limit])
    return [deliver_push(delivery_id) for delivery_id in ids]
