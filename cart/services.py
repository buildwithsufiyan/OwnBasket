from .models import Cart


def get_user_cart(user):
    cart, _ = Cart.objects.get_or_create(id=user.id, defaults={'user': user})
    if cart.user_id != user.id:
        cart.user = user
        cart.save(update_fields=('user', 'updated_at'))
    return cart


def touch_cart(cart):
    cart.is_active = True
    cart.save(update_fields=('is_active', 'updated_at'))
