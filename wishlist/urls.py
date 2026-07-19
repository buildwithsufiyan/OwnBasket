from django.urls import path
from . import views

app_name = 'wishlist'

urlpatterns = [
    path('', views.wishlist_view, name='wishlist'),
    path('add/<int:product_id>/', views.add_to_wishlist, name='add_to_wishlist'),
    path('remove/<int:product_id>/', views.remove_from_wishlist, name='remove_from_wishlist'),
    path('collections/create/', views.create_collection, name='create_collection'),
    path('collections/<int:collection_id>/delete/', views.delete_collection, name='delete_collection'),
    path('collections/<int:collection_id>/share/', views.toggle_share, name='toggle_share'),
    path('items/<int:item_id>/move/', views.move_item, name='move_item'),
    path('items/<int:item_id>/cart/', views.move_to_cart, name='move_to_cart'),
    path('items/<int:item_id>/save-later/', views.toggle_saved_for_later, name='toggle_saved_for_later'),
    path('bulk-remove/', views.bulk_remove, name='bulk_remove'),
    path('shared/<uuid:token>/', views.shared_wishlist, name='shared'),
]
