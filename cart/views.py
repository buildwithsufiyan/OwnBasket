from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .models import CartItem
from .services import (
    clear_coupon_code,
    get_coupon_code,
    get_user_cart,
    set_coupon_code,
    touch_cart,
    visible_cart_items,
)
from core.http import safe_redirect_target
from products.models import Product
from products.pricing import build_cart_summary, get_coupon_by_code, validate_coupon
from api_v2.sync import bump_sync_state
from personalization.models import BehaviorEvent
from personalization.services import record_behavior


def _coupon_return_url(request):
    return_to = request.POST.get('return_to') or request.GET.get('return_to')
    return safe_redirect_target(request, return_to, reverse('cart_detail'))


@login_required(login_url='login')
def add_to_cart(request, product_id):
    product = get_object_or_404(Product.objects.marketplace_visible(), id=product_id, is_active=True)
    if not product.can_purchase:
        messages.error(request, 'This product is currently unavailable.')
        return redirect(product.get_absolute_url())

    size = request.POST.get('size')
    color = request.POST.get('color')

    cart = get_user_cart(request.user)

    cart_item, item_created = CartItem.objects.get_or_create(
        cart=cart,
        product=product,
        size=size,
        color=color,
    )

    if not item_created:
        cart_item.quantity += 1
        cart_item.save()
    touch_cart(cart)
    bump_sync_state(request.user)
    record_behavior(request, BehaviorEvent.EventType.CART_ADD, product=product, category=product.category, brand=product.brand)

    return redirect('cart_detail')


@login_required(login_url='login')
def cart_detail(request):
    cart = get_user_cart(request.user)
    items = visible_cart_items(cart)
    coupon_code = get_coupon_code(request)
    summary = build_cart_summary(items, user=request.user, coupon_code=coupon_code)

    return render(
        request,
        'cart/cart_detail.html',
        {
            'items': summary.items,
            'summary': summary,
            'total': summary.grand_total,
            'cart_count': summary.item_count,
            'coupon_code': coupon_code,
        },
    )


@login_required(login_url='login')
def increase_quantity(request, item_id):
    item = get_object_or_404(CartItem, id=item_id, cart__user=request.user)

    item.quantity += 1
    item.save()
    touch_cart(item.cart)
    bump_sync_state(request.user)
    record_behavior(request, BehaviorEvent.EventType.CART_ADD, product=item.product, category=item.product.category, brand=item.product.brand)

    return redirect('cart_detail')


@login_required(login_url='login')
def decrease_quantity(request, item_id):
    item = get_object_or_404(CartItem, id=item_id, cart__user=request.user)

    if item.quantity > 1:
        item.quantity -= 1
        item.save()
        touch_cart(item.cart)
        bump_sync_state(request.user)
        record_behavior(request, BehaviorEvent.EventType.CART_REMOVE, product=item.product, category=item.product.category, brand=item.product.brand)

    return redirect('cart_detail')


@login_required(login_url='login')
def remove_from_cart(request, item_id):
    item = get_object_or_404(CartItem, id=item_id, cart__user=request.user)

    cart = item.cart
    product = item.product
    item.delete()
    touch_cart(cart)
    bump_sync_state(request.user)
    record_behavior(request, BehaviorEvent.EventType.CART_REMOVE, product=product, category=product.category, brand=product.brand)

    return redirect('cart_detail')


@login_required(login_url='login')
@require_POST
def apply_coupon(request):
    code = (request.POST.get('code') or '').upper().strip()
    cart = get_user_cart(request.user)
    items = CartItem.objects.filter(cart=cart).select_related('product', 'product__brand', 'product__category')

    if not code:
        clear_coupon_code(request)
        messages.error(request, 'Please enter a coupon code.')
        return redirect(_coupon_return_url(request))

    summary = build_cart_summary(items, user=request.user, coupon_code=code)
    if summary.applied_coupon:
        set_coupon_code(request, code)
        messages.success(request, summary.coupon_message)
    else:
        clear_coupon_code(request)
        coupon = get_coupon_by_code(code)
        _, message = validate_coupon(
            coupon,
            user=request.user,
            subtotal=summary.subtotal_after_item_discounts,
            eligible_subtotal=sum(
                (
                    line.line_final_total
                    for line in summary.line_items
                    if not line.has_item_discount
                ),
                0,
            ),
        )
        messages.error(request, message)
    return redirect(_coupon_return_url(request))


@login_required(login_url='login')
@require_POST
def remove_coupon(request):
    clear_coupon_code(request)
    messages.success(request, 'Coupon removed successfully.')
    return redirect(_coupon_return_url(request))
