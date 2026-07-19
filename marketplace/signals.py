from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from products.models import Product, ProductReview

from .models import MarketplaceSettings, SellerNotification
from .services import create_seller_notification


@receiver(pre_save, sender=Product)
def remember_product_stock(sender, instance, **kwargs):
    instance._previous_marketplace_stock = None
    if instance.pk:
        instance._previous_marketplace_stock = sender.objects.filter(pk=instance.pk).values_list('stock', flat=True).first()


@receiver(post_save, sender=Product)
def notify_low_stock(sender, instance, created, **kwargs):
    if not instance.seller_id or not instance.seller.inventory_notifications:
        return
    settings = MarketplaceSettings.get_solo()
    if not settings.low_stock_notification_enabled:
        return
    previous = getattr(instance, '_previous_marketplace_stock', None)
    threshold = instance.low_stock_alert
    crossed_threshold = instance.stock <= threshold and (created or previous is None or previous > threshold)
    if not crossed_threshold:
        return
    create_seller_notification(
        seller=instance.seller,
        event_type=SellerNotification.EventType.LOW_STOCK,
        title=f'Low stock: {instance.name}',
        message=f'{instance.name} has {instance.stock} units remaining.',
        link='/marketplace/seller/inventory/',
    )


@receiver(post_save, sender=ProductReview)
def notify_review_received(sender, instance, created, **kwargs):
    if not created or not instance.product.seller_id:
        return
    create_seller_notification(
        seller=instance.product.seller,
        event_type=SellerNotification.EventType.REVIEW_RECEIVED,
        title=f'Review received: {instance.product.name}',
        message=f'A customer submitted a {instance.rating}/5 review. Moderation status: {instance.get_moderation_status_display()}.',
        link='/marketplace/seller/',
    )
