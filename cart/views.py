from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import models
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .models import Cart, CartItem
from products.models import Product
from products.pricing import build_cart_summary, get_coupon_by_code, validate_coupon


def _get_user_cart(user):
    cart, _ = Cart.objects.get_or_create(id=user.id, defaults={'user': user})
    if cart.user_id != user.id:
        cart.user = user
        cart.save(update_fields=('user', 'updated_at'))
    return cart


def _touch_cart(cart):
    cart.is_active = True
    cart.save(update_fields=('is_active', 'updated_at'))


def _get_coupon_session_key():
    return 'active_coupon_code'


def _set_coupon_code(request, code):
    request.session[_get_coupon_session_key()] = (code or '').upper().strip()


def _clear_coupon_code(request):
    request.session.pop(_get_coupon_session_key(), None)


def _get_coupon_code(request):
    return request.session.get(_get_coupon_session_key(), '')


def _coupon_return_url(request):
    return_to = request.POST.get('return_to') or request.GET.get('return_to')
    if return_to and url_has_allowed_host_and_scheme(
        return_to,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return return_to
    return reverse('cart_detail')


@login_required(login_url='login')
def add_to_cart(request, product_id):
    product = get_object_or_404(Product.objects.marketplace_visible(), id=product_id, is_active=True)

    size = request.POST.get('size')
    color = request.POST.get('color')

    cart = _get_user_cart(request.user)

    cart_item, item_created = CartItem.objects.get_or_create(
        cart=cart,
        product=product,
        size=size,
        color=color,
    )

    if not item_created:
        cart_item.quantity += 1
        cart_item.save()
    _touch_cart(cart)

    return redirect('cart_detail')


@login_required(login_url='login')
def cart_detail(request):
    cart = _get_user_cart(request.user)
    items = CartItem.objects.filter(cart=cart, product__is_active=True).filter(
        models.Q(product__seller__isnull=True) |
        models.Q(product__seller__verification_status='approved')
    ).select_related('product', 'product__seller', 'product__brand', 'product__category')
    coupon_code = _get_coupon_code(request)
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
    item = get_object_or_404(CartItem, id=item_id)

    if item.cart.id != request.user.id:
        return redirect('cart_detail')

    item.quantity += 1
    item.save()
    _touch_cart(item.cart)

    return redirect('cart_detail')


@login_required(login_url='login')
def decrease_quantity(request, item_id):
    item = get_object_or_404(CartItem, id=item_id)

    if item.cart.id != request.user.id:
        return redirect('cart_detail')

    if item.quantity > 1:
        item.quantity -= 1
        item.save()
        _touch_cart(item.cart)

    return redirect('cart_detail')


@login_required(login_url='login')
def remove_from_cart(request, item_id):
    item = get_object_or_404(CartItem, id=item_id)

    if item.cart.id != request.user.id:
        return redirect('cart_detail')

    cart = item.cart
    item.delete()
    _touch_cart(cart)

    return redirect('cart_detail')


@login_required(login_url='login')
@require_POST
def apply_coupon(request):
    code = (request.POST.get('code') or '').upper().strip()
    cart = _get_user_cart(request.user)
    items = CartItem.objects.filter(cart=cart).select_related('product', 'product__brand', 'product__category')

    if not code:
        _clear_coupon_code(request)
        messages.error(request, 'Please enter a coupon code.')
        return redirect(_coupon_return_url(request))

    summary = build_cart_summary(items, user=request.user, coupon_code=code)
    if summary.applied_coupon:
        _set_coupon_code(request, code)
        messages.success(request, summary.coupon_message)
    else:
        _clear_coupon_code(request)
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
    _clear_coupon_code(request)
    messages.success(request, 'Coupon removed successfully.')
    return redirect(_coupon_return_url(request))
