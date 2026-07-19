from django.urls import path

from . import account, catalog, commerce, discovery, openapi, sync, views


app_name = 'api-v2'

urlpatterns = [
    path('', views.index, name='index'),
    path('openapi.json', openapi.schema, name='openapi'),
    path('docs/', openapi.swagger_ui, name='swagger'),
    path('redoc/', openapi.redoc_ui, name='redoc'),
    path('health/', views.health, name='health'),
    path('metrics/', views.metrics, name='metrics'),
    path('auth/session/', account.session, name='session'),
    path('auth/token/', account.token_login, name='token-login'),
    path('auth/token/refresh/', account.token_refresh, name='token-refresh'),
    path('auth/token/sessions/', account.token_sessions, name='token-sessions'),
    path('auth/token/sessions/<int:session_id>/', account.token_session_detail, name='token-session-detail'),
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
    path('push/deliveries/', account.push_deliveries, name='push-deliveries'),
    path('sync/capabilities/', views.sync_capabilities, name='sync-capabilities'),
    path('sync/batches/', sync.sync_batch, name='sync-batch'),
    path('recommendations/', discovery.recommendations, name='recommendations'),
    path('trending/', discovery.trending, name='trending'),
    path('search/', discovery.search, name='intelligent-search'),
    path('products/<int:product_id>/similar/', discovery.similar, name='similar-products'),
    path('products/<int:product_id>/bought-together/', discovery.bought_together, name='bought-together'),
]
