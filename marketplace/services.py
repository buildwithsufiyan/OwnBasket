from django.db import transaction
from django.utils import timezone

from .models import (
    InventoryHistory,
    MarketplaceSettings,
    SellerInventory,
    SellerNotification,
    SellerOrderFulfillment,
    SellerOrderStatusHistory,
)


def marketplace_settings():
    """Return saved settings or safe backward-compatible defaults without writing."""
    return MarketplaceSettings.get_solo()


def create_seller_notification(*, seller, event_type, title, message, link='', queue_email=False):
    return SellerNotification.objects.create(
        seller=seller,
        event_type=event_type,
        title=title,
        message=message,
        link=link,
        email_status=(
            SellerNotification.EmailStatus.QUEUED
            if queue_email else SellerNotification.EmailStatus.NOT_REQUESTED
        ),
    )


@transaction.atomic
def update_inventory(*, inventory, current_stock, reserved_stock, user, note=''):
    inventory = SellerInventory.objects.select_for_update().select_related('product').get(pk=inventory.pk)
    old_stock = inventory.product.stock
    old_reserved = inventory.reserved_stock
    inventory.product.stock = current_stock
    inventory.product.save(update_fields=('stock',))
    inventory.reserved_stock = reserved_stock
    inventory.full_clean()
    inventory.save(update_fields=('reserved_stock', 'updated_at'))
    InventoryHistory.objects.create(
        inventory=inventory,
        stock_change=current_stock - old_stock,
        reserved_change=reserved_stock - old_reserved,
        stock_after=current_stock,
        reserved_after=reserved_stock,
        reason=InventoryHistory.Reason.MANUAL,
        note=note[:255],
        created_by=user,
    )
    return inventory


@transaction.atomic
def update_fulfillment(*, fulfillment, status, note, user):
    fulfillment = SellerOrderFulfillment.objects.select_for_update().get(pk=fulfillment.pk)
    if status == SellerOrderFulfillment.Status.READY_TO_SHIP and not fulfillment.ready_at:
        fulfillment.ready_at = timezone.now()
    fulfillment.status = status
    fulfillment.seller_note = note
    fulfillment.full_clean()
    fulfillment.save(update_fields=('status', 'seller_note', 'ready_at', 'updated_at'))
    SellerOrderStatusHistory.objects.create(
        fulfillment=fulfillment,
        status=status,
        note=note[:255],
        changed_by=user,
    )
    return fulfillment
