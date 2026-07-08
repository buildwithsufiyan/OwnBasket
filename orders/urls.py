from django.urls import path
from . import views

urlpatterns = [
path(
'checkout/',
views.checkout,
name='checkout'
),


path(
    'my-orders/',
    views.my_orders,
    name='my_orders'
),

path(
    'invoice/<int:order_id>/',
    views.invoice_pdf,
    name='invoice_pdf'
),

]
