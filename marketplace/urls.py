from django.urls import path

from . import views


app_name = 'marketplace'

urlpatterns = [
    path('sellers/', views.store_list, name='store_list'),
    path('store/<slug:slug>/', views.store_detail, name='store_detail'),
    path('seller/register/', views.seller_register, name='register'),
    path('seller/login/', views.SellerLoginView.as_view(), name='login'),
    path('seller/onboarding/', views.seller_onboarding, name='onboarding'),
    path('seller/', views.dashboard, name='dashboard'),
    path('seller/products/', views.product_list, name='products'),
    path('seller/products/add/', views.product_create, name='product_create'),
    path('seller/products/<int:product_id>/edit/', views.product_update, name='product_update'),
    path('seller/products/<int:product_id>/archive/', views.product_archive, name='product_archive'),
    path('seller/orders/', views.orders, name='orders'),
    path('seller/orders/<int:order_id>/', views.order_detail, name='order_detail'),
    path('seller/inventory/', views.inventory, name='inventory'),
    path('seller/inventory/<int:product_id>/', views.inventory_update, name='inventory_update'),
    path('seller/analytics/', views.analytics, name='analytics'),
    path('seller/payouts/', views.payouts, name='payouts'),
    path('seller/documents/', views.documents, name='documents'),
    path('seller/notifications/', views.notifications, name='notifications'),
    path('seller/settings/', views.settings, name='settings'),
]
