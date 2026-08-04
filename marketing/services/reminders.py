from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Prefetch
from django.urls import reverse
from django.utils import timezone
from django.db.models import Q

from cart.models import Cart, CartItem
from marketing.models import EngagementDelivery, StockAlert
from marketing.services.email_service import send_branded_email
from marketplace.visibility import visible_seller_q
from wishlist.models import Wishlist


def abandoned_cart_candidates():
    cutoff = timezone.now() - timedelta(hours=getattr(settings, 'ABANDONED_CART_MIN_HOURS', 24))
    max_reminders = getattr(settings, 'ABANDONED_CART_MAX_REMINDERS', 2)
    return Cart.objects.filter(
        user__isnull=False,
        user__is_active=True,
        user__email__gt='',
        is_active=True,
        updated_at__lte=cutoff,
        reminder_count__lt=max_reminders,
        user__notification_preferences__marketing_consent=True,
        user__notification_preferences__abandoned_cart_reminders=True,
        cartitem__product__is_active=True,
    ).filter(
        Q(last_reminder_at__isnull=True) | Q(last_reminder_at__lte=cutoff),
    ).filter(
        visible_seller_q('cartitem__product__seller')
    ).select_related('user', 'user__notification_preferences').prefetch_related(
        Prefetch('cartitem_set', queryset=CartItem.objects.select_related('product').filter(
            visible_seller_q('product__seller'), product__is_active=True,
        ))
    ).distinct().order_by('updated_at', 'pk')


def send_abandoned_cart_reminder(cart, base_url):
    items = list(cart.cartitem_set.all())
    if not items:
        return False
    success = send_branded_email(
        subject='You left items in your OwnBasket cart', recipient=cart.user.email,
        template_name='abandoned_cart', context={'user': cart.user, 'items': items, 'cart_url': f'{base_url}/cart/'},
        kind=EngagementDelivery.Kind.ABANDONED_CART, reference=cart.pk, user=cart.user,
    )
    if success:
        cart.reminder_count += 1
        cart.last_reminder_at = timezone.now()
        cart.save(update_fields=('reminder_count', 'last_reminder_at'))
    return success


def wishlist_candidates():
    cutoff = timezone.now() - timedelta(days=getattr(settings, 'WISHLIST_REMINDER_DAYS', 14))
    users = get_user_model().objects.filter(
        is_active=True, email__gt='',
        notification_preferences__marketing_consent=True,
        notification_preferences__wishlist_reminders=True,
        wishlist__created_at__lte=cutoff,
        wishlist__product__is_active=True,
        wishlist__product__stock__gt=0,
    ).filter(
        visible_seller_q('wishlist__product__seller')
    ).distinct().order_by('pk')
    return users.prefetch_related(Prefetch(
        'wishlist_set', queryset=Wishlist.objects.select_related('product').filter(
            visible_seller_q('product__seller'),
            product__is_active=True, product__stock__gt=0, created_at__lte=cutoff,
        )
    ))


def send_wishlist_reminder(user, base_url):
    frequency_cutoff = timezone.now() - timedelta(days=getattr(settings, 'WISHLIST_REMINDER_FREQUENCY_DAYS', 30))
    if EngagementDelivery.objects.filter(
        user=user, kind=EngagementDelivery.Kind.WISHLIST,
        status=EngagementDelivery.Status.SENT, sent_at__gte=frequency_cutoff,
    ).exists():
        return False
    items = list(user.wishlist_set.all())[:12]
    if not items:
        return False
    return send_branded_email(
        subject='Items saved in your OwnBasket wishlist', recipient=user.email,
        template_name='wishlist_reminder', context={'user': user, 'items': items, 'base_url': base_url, 'wishlist_url': f'{base_url}/wishlist/'},
        kind=EngagementDelivery.Kind.WISHLIST, reference=user.pk, user=user,
    )


def stock_alert_candidates():
    return StockAlert.objects.filter(
        is_active=True, product__is_active=True, product__stock__gt=0,
        user__is_active=True, user__notification_preferences__back_in_stock_alerts=True,
    ).filter(
        visible_seller_q('product__seller')
    ).select_related('user', 'product').order_by('created_at', 'pk')


def send_stock_alert(alert, base_url):
    success = send_branded_email(
        subject=f'{alert.product.name} is back in stock', recipient=alert.email,
        template_name='stock_alert', context={'user': alert.user, 'product': alert.product, 'product_url': f'{base_url}{alert.product.get_absolute_url()}'},
        kind=EngagementDelivery.Kind.STOCK, reference=alert.pk, user=alert.user,
    )
    if success:
        alert.is_active = False
        alert.notified_at = timezone.now()
        alert.save(update_fields=('is_active', 'notified_at'))
    return success
