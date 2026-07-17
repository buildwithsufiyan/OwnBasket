from django.urls import path

from . import account, catalog, commerce, views


app_name = 'api-v2'

urlpatterns = [
    path('', views.index, name='index'),
    path('auth/session/', account.session, name='session'),
    path('products/', catalog.products, name='products'),
    path('products/<int:product_id>/', catalog.product_detail, name='product-detail'),
    path('products/<int:product_id>/reviews/', catalog.product_reviews, name='product-reviews'),
    path('categories/', catalog.categories, name='categories'),
    path('brands/', catalog.brands, name='brands'),
    path('cart/', commerce.cart, name='cart'),
    path('cart/items/', commerce.cart_items, name='cart-items'),
    path('cart/items/<int:item_id>/', commerce.cart_item_detail, name='cart-item-detail'),
    path('checkout/', commerce.checkout, name='checkout'),
    path('orders/', commerce.orders, name='orders'),
    path('orders/<int:order_id>/', commerce.order_detail, name='order-detail'),
    path('wishlist/', commerce.wishlist, name='wishlist'),
    path('wishlist/<int:product_id>/', commerce.wishlist_detail, name='wishlist-detail'),
    path('profile/', account.profile, name='profile'),
    path('seller/dashboard/', account.seller_dashboard, name='seller-dashboard'),
    path('push/devices/', account.push_devices, name='push-devices'),
    path('push/devices/<int:device_id>/', account.push_device_detail, name='push-device-detail'),
    path('sync/capabilities/', views.sync_capabilities, name='sync-capabilities'),
]
