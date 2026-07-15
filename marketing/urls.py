from django.urls import path

from . import views


app_name = 'marketing'

urlpatterns = [
    path('newsletter/subscribe/', views.newsletter_subscribe, name='newsletter_subscribe'),
    path('newsletter/confirm/<str:token>/', views.newsletter_confirm, name='newsletter_confirm'),
    path('newsletter/unsubscribe/<str:token>/', views.newsletter_unsubscribe, name='newsletter_unsubscribe'),
    path('engagement/', views.engagement_dashboard, name='engagement_dashboard'),
    path('preferences/', views.notification_preferences, name='preferences'),
    path('stock-alert/<int:product_id>/', views.stock_alert_subscribe, name='stock_alert_subscribe'),
    path('stock-alert/remove/<int:alert_id>/', views.stock_alert_remove, name='stock_alert_remove'),
]
