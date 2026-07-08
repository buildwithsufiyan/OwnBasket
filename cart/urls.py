from django.urls import path
from .views import (
    add_to_cart,
    apply_coupon,
    cart_detail,
    increase_quantity,
    decrease_quantity,
    remove_coupon,
    remove_from_cart
)

urlpatterns = [
    path(
        'add-to-cart/<int:product_id>/',
        add_to_cart,
        name='add_to_cart'
    ),

    path(
        'cart/',
        cart_detail,
        name='cart_detail'
    ),

    path(
        'increase/<int:item_id>/',
        increase_quantity,
        name='increase_quantity'
    ),

    path(
        'decrease/<int:item_id>/',
        decrease_quantity,
        name='decrease_quantity'
    ),

    path(
        'remove/<int:item_id>/',
        remove_from_cart,
        name='remove_from_cart'
    ),

    path(
        'cart/apply-coupon/',
        apply_coupon,
        name='apply_coupon'
    ),

    path(
        'cart/remove-coupon/',
        remove_coupon,
        name='remove_coupon'
    ),
    
]
