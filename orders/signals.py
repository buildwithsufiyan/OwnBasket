from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from marketing.models import EngagementDelivery, NotificationPreference
from marketing.services.email_service import send_branded_email

from .models import Order


@receiver(pre_save, sender=Order)
def remember_order_status(sender, instance, **kwargs):
    instance._previous_status = None
    if instance.pk:
        instance._previous_status = sender.objects.filter(pk=instance.pk).values_list('status', flat=True).first()


@receiver(post_save, sender=Order)
def send_order_status_email(sender, instance, created, **kwargs):
    if created or instance.status == getattr(instance, '_previous_status', None):
        return
    preference = NotificationPreference.objects.filter(user=instance.user).first()
    if instance.status == 'Shipped' and preference and not preference.order_updates:
        return
    if instance.status == 'Delivered' and preference and not preference.delivery_updates:
        return
    template = {'Shipped': 'shipping_update', 'Delivered': 'delivery_confirmation'}.get(instance.status)
    if not template:
        return
    send_branded_email(
        subject=f'OwnBasket order #{instance.pk}: {instance.status}', recipient=instance.email,
        template_name=template, context={'order': instance},
        kind=EngagementDelivery.Kind.TRANSACTIONAL, reference=instance.pk, user=instance.user,
    )
