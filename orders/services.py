from decimal import Decimal

from django.db import transaction
from django.db.models import F

from cart.models import Cart, CartItem
from marketplace.models import SellerNotification
from marketing.models import NotificationPreference
from products.models import CouponRedemption

from .models import Order, OrderItem


class EmptyCartError(Exception):
    pass


def create_order_from_cart(*, user, cart, items, summary, customer, marketing_consent=False):
    """Create an order from a priced cart while locking against duplicate submissions."""
    item_ids = [item.pk for item in items]
    if not item_ids:
        raise EmptyCartError('Your cart is empty.')

    with transaction.atomic():
        locked_cart = Cart.objects.select_for_update().get(pk=cart.pk, user=user)
        locked_items = list(
            CartItem.objects.select_for_update().filter(
                pk__in=item_ids, cart=locked_cart, product__is_active=True,
            ).select_related('product', 'product__seller')
        )
        if len(locked_items) != len(item_ids):
            raise EmptyCartError('The cart changed while checkout was submitted. Review it and try again.')

        order = Order.objects.create(
            user=user,
            full_name=customer['full_name'],
            email=customer['email'],
            address=customer['address'],
            subtotal=summary.subtotal_original,
            discount_total=summary.total_discount,
            shipping_amount=summary.shipping_amount,
            payment_method=customer.get('payment_method', 'COD')[:40],
            coupon_code=summary.applied_coupon.code if summary.applied_coupon else '',
            total_price=summary.grand_total,
        )

        ordered_sellers = {}
        for line in summary.line_items:
            seller = line.item.product.seller
            line_total = line.unit_final_price * line.quantity
            commission_rate = seller.commission_rate if seller else Decimal('0.00')
            marketplace_commission = (line_total * commission_rate / Decimal('100')).quantize(Decimal('0.01'))
            OrderItem.objects.create(
                order=order,
                product=line.item.product,
                quantity=line.quantity,
                price=line.unit_final_price,
                original_price=line.unit_original_price,
                discount_amount=line.line_discount_total,
                applied_offer_name=line.pricing.source_name or line.pricing.badge_text,
                size=line.item.size,
                color=line.item.color,
                seller=seller,
                seller_name=seller.store_name if seller else '',
                marketplace_commission=marketplace_commission,
                seller_earning=line_total - marketplace_commission,
                cost_price=line.item.product.cost_price,
            )
            if seller:
                ordered_sellers[seller.pk] = seller
            type(line.item.product).objects.filter(pk=line.item.product.pk).update(
                total_sold=F('total_sold') + line.quantity,
            )

        SellerNotification.objects.bulk_create([
            SellerNotification(
                seller=seller,
                title=f'New order #{order.pk}',
                message='A customer placed an order containing one or more of your products.',
                link='/marketplace/seller/orders/',
            )
            for seller in ordered_sellers.values() if seller.order_notifications
        ])

        if summary.applied_coupon:
            CouponRedemption.objects.create(coupon=summary.applied_coupon, user=user, order=order)

        CartItem.objects.filter(pk__in=item_ids, cart=locked_cart).delete()
        locked_cart.is_active = False
        locked_cart.save(update_fields=('is_active', 'updated_at'))

        if marketing_consent:
            preferences, _ = NotificationPreference.objects.get_or_create(user=user)
            preferences.promotional_emails = True
            preferences.record_consent(True, 'checkout')

    return order
