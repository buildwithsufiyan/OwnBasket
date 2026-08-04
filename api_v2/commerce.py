from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.db.models import F
from django.shortcuts import get_object_or_404

from cart.models import CartItem
from cart.services import clear_coupon_code, get_coupon_code, get_user_cart, touch_cart, visible_cart_items
from orders.models import Order
from orders.services import EmptyCartError, create_order_from_cart, send_order_confirmation_email
from products.models import Product
from products.pricing import build_cart_summary
from products.pricing import attach_pricing_to_products
from wishlist.models import Wishlist, WishlistSettings
from wishlist.services import add_product_to_wishlist, default_collection, visible_wishlist_items
from personalization.models import BehaviorEvent
from personalization.services import record_behavior

from .catalog import visible_products
from .http import ApiError, api_endpoint, json_body, paginated, positive_int
from .serializers import money, order_data, product_data
from .sync import bump_sync_state


def _cart_state(request):
    cart = get_user_cart(request.user)
    items = visible_cart_items(cart)
    summary = build_cart_summary(items, user=request.user, coupon_code=get_coupon_code(request))
    return cart, list(items), summary


def _cart_payload(request, items, summary):
    return {
        'items': [{
            'id': item.pk, 'quantity': item.quantity, 'size': item.size, 'color': item.color,
            'lineTotal': money(item.line_pricing.line_final_total),
            'product': product_data(request, item.product),
        } for item in items],
        'summary': {
            'itemCount': summary.item_count, 'subtotal': money(summary.subtotal_original),
            'discount': money(summary.total_discount), 'shipping': money(summary.shipping_amount),
            'total': money(summary.grand_total), 'currency': 'INR',
            'couponCode': summary.applied_coupon.code if summary.applied_coupon else '',
        },
    }


@api_endpoint(auth=True)
def cart(request):
    _, items, summary = _cart_state(request)
    return {'cart': _cart_payload(request, items, summary)}


@api_endpoint(('POST',), auth=True)
def cart_items(request):
    payload = json_body(request)
    product_id = positive_int(payload.get('productId'), name='productId')
    quantity = positive_int(payload.get('quantity'), name='quantity', default=1, maximum=99)
    product = get_object_or_404(visible_products(), pk=product_id)
    if not product.can_purchase:
        raise ApiError('product_unavailable', 'This product is currently unavailable.', 409)
    user_cart = get_user_cart(request.user)
    item, created = CartItem.objects.get_or_create(
        cart=user_cart, product=product,
        size=(str(payload.get('size') or '').strip()[:50] or None),
        color=(str(payload.get('color') or '').strip()[:50] or None),
        defaults={'quantity': quantity},
    )
    if not created:
        item.quantity = min(item.quantity + quantity, 99)
        item.save(update_fields=('quantity',))
    touch_cart(user_cart)
    bump_sync_state(request.user)
    record_behavior(request, BehaviorEvent.EventType.CART_ADD, product=product, category=product.category, brand=product.brand)
    _, items, summary = _cart_state(request)
    return {'cart': _cart_payload(request, items, summary), 'created': created}


@api_endpoint(('PATCH', 'DELETE'), auth=True)
def cart_item_detail(request, item_id):
    item = get_object_or_404(CartItem.objects.select_related('cart', 'product__category', 'product__brand'), pk=item_id, cart__user=request.user)
    product = item.product
    if request.method == 'DELETE':
        user_cart = item.cart
        item.delete()
        touch_cart(user_cart)
    else:
        payload = json_body(request)
        item.quantity = positive_int(payload.get('quantity'), name='quantity', maximum=99)
        item.save(update_fields=('quantity',))
        touch_cart(item.cart)
    bump_sync_state(request.user)
    record_behavior(
        request,
        BehaviorEvent.EventType.CART_REMOVE if request.method == 'DELETE' else BehaviorEvent.EventType.CART_ADD,
        product=product, category=product.category, brand=product.brand,
    )
    _, items, summary = _cart_state(request)
    return {'cart': _cart_payload(request, items, summary)}


@api_endpoint(
    ('POST',), auth=True, idempotent=True, summary='Create an order from the active cart', tags=('Commerce',),
    request_example={'fullName': 'Mobile Buyer', 'email': 'buyer@example.com', 'address': '1 Market Road', 'paymentMethod': 'COD'},
    response_example={'order': {'id': 123, 'status': 'Pending', 'paymentMethod': 'COD'}},
)
def checkout(request):
    payload = json_body(request)
    customer = {
        'full_name': str(payload.get('fullName') or '').strip(),
        'email': str(payload.get('email') or '').strip(),
        'address': str(payload.get('address') or '').strip(),
        'payment_method': str(payload.get('paymentMethod') or 'COD').strip().upper(),
    }
    fields = {}
    if not customer['full_name'] or len(customer['full_name']) > 200:
        fields['fullName'] = ['Use between 1 and 200 characters.']
    try:
        validate_email(customer['email'])
    except ValidationError:
        fields['email'] = ['Enter a valid email address.']
    if not customer['address'] or len(customer['address']) > 2000:
        fields['address'] = ['Use between 1 and 2000 characters.']
    if customer['payment_method'] != 'COD':
        fields['paymentMethod'] = ['Only COD is currently supported.']
    if fields:
        raise ApiError('validation_error', 'Checkout details are invalid.', fields=fields)
    user_cart, items, summary = _cart_state(request)
    if not items:
        raise ApiError('empty_cart', 'Your cart is empty.', 409)
    try:
        order = create_order_from_cart(
            user=request.user, cart=user_cart, items=items, summary=summary, customer=customer,
            marketing_consent=payload.get('marketingConsent') is True,
        )
    except EmptyCartError as exc:
        raise ApiError('cart_changed', str(exc), 409)
    clear_coupon_code(request)
    bump_sync_state(request.user)
    send_order_confirmation_email(request, order)
    return {'order': order_data(request, order, detail=True)}


@api_endpoint(auth=True)
def orders(request):
    queryset = Order.objects.filter(user=request.user).order_by('-created_at', '-id')
    return paginated(request, queryset, lambda item: order_data(request, item))


@api_endpoint(auth=True)
def order_detail(request, order_id):
    order = get_object_or_404(
        Order.objects.filter(user=request.user).prefetch_related('items__product'), pk=order_id,
    )
    return {'order': order_data(request, order, detail=True)}


@api_endpoint(('GET', 'POST'), auth=True)
def wishlist(request):
    if request.method == 'POST':
        payload = json_body(request)
        product = get_object_or_404(visible_products(), pk=positive_int(payload.get('productId'), name='productId'))
        collection = default_collection(request.user)
        if collection.items.count() >= WishlistSettings.get_solo().max_items_per_collection:
            raise ApiError('wishlist_limit', 'The default wishlist collection is full.', 409)
        created = add_product_to_wishlist(request, product, collection)
    queryset = list(visible_wishlist_items(Wishlist.objects.filter(user=request.user)))
    attach_pricing_to_products([item.product for item in queryset])
    return {'results': [product_data(request, item.product) for item in queryset], **({'created': created} if request.method == 'POST' else {})}


@api_endpoint(('DELETE',), auth=True)
def wishlist_detail(request, product_id):
    deleted, _ = Wishlist.objects.filter(user=request.user, product_id=product_id).delete()
    if deleted:
        Product.objects.filter(pk=product_id, wishlist_count__gt=0).update(wishlist_count=F('wishlist_count') - 1)
        bump_sync_state(request.user)
        product = Product.objects.select_related('category', 'brand').filter(pk=product_id).first()
        if product:
            record_behavior(request, BehaviorEvent.EventType.WISHLIST_REMOVE, product=product, category=product.category, brand=product.brand)
    return {'deleted': bool(deleted)}
