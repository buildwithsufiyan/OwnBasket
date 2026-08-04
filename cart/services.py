from marketplace.visibility import visible_seller_q

from .models import Cart, CartItem

COUPON_SESSION_KEY = 'active_coupon_code'
CART_ITEM_RELATED = ('product', 'product__seller', 'product__brand', 'product__category')


def get_user_cart(user):
    cart, _ = Cart.objects.get_or_create(id=user.id, defaults={'user': user})
    if cart.user_id != user.id:
        cart.user = user
        cart.save(update_fields=('user', 'updated_at'))
    return cart


def touch_cart(cart):
    cart.is_active = True
    cart.save(update_fields=('is_active', 'updated_at'))


def visible_cart_items(cart):
    """Cart items a customer may currently buy: active products from visible sellers."""
    return CartItem.objects.filter(cart=cart, product__is_active=True).filter(
        visible_seller_q('product__seller')
    ).select_related(*CART_ITEM_RELATED)


def get_coupon_code(request):
    return request.session.get(COUPON_SESSION_KEY, '')


def set_coupon_code(request, code):
    request.session[COUPON_SESSION_KEY] = (code or '').upper().strip()


def clear_coupon_code(request):
    request.session.pop(COUPON_SESSION_KEY, None)
