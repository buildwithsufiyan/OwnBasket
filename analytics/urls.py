from django.urls import path

from . import views

app_name = 'analytics'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('sales/', views.sales, name='sales'),
    path('products/', views.products, name='products'),
    path('customers/', views.customers, name='customers'),
    path('sellers/', views.sellers, name='sellers'),
    path('refunds/', views.refunds, name='refunds'),
    path('tax/', views.tax, name='tax'),
    path('export/<str:report>/<str:file_format>/', views.export_report, name='export'),
]
