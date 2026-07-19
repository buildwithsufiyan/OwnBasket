# from django.urls import path
# from . import views

# urlpatterns = [
#     path('product/<slug:slug>/', views.product_detail, name='product_detail'),
#     path('search/', views.search_products, name='search_products'),
# ]
# from django.urls import path
# from . import views

# app_name = 'products'

# urlpatterns = [
#     path('search/', views.live_search, name='live_search'),
#     path('product/<slug:slug>/', views.product_detail, name='product_detail'),
# ]
from django.urls import path
from . import views

app_name = 'products'

urlpatterns = [
    path('shop/', views.product_list, name='product_list'),
    path('api/search-suggestions/', views.search_suggestions_api, name='search_suggestions_api'),
    path('brands/', views.brand_list, name='brand_list'),
    path('brand/<int:pk>/', views.brand_detail, name='brand_detail'),
    path('categories/', views.category_list, name='category_list'),
    path('category/<slug:slug>/', views.category_detail, name='category_detail'),
    path('product/<slug:slug>/', views.product_detail, name='product_detail'),
    path('product/<slug:slug>/review/', views.submit_review, name='submit_review'),
    path('reviews/<int:review_id>/delete/', views.delete_review, name='delete_review'),
    path('reviews/<int:review_id>/helpful/', views.helpful_review, name='helpful_review'),
    path('compare/', views.compare_products, name='compare'),
    path('compare/add/<int:product_id>/', views.compare_add, name='compare_add'),
    path('compare/remove/<int:product_id>/', views.compare_remove, name='compare_remove'),
    path('search/', views.search_results, name='search_results'),
    path('search/live/', views.live_search, name='live_search'),
]
