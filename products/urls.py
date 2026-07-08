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
    path('api/search-suggestions/', views.search_suggestions_api, name='search_suggestions_api'),
    path('brands/', views.brand_list, name='brand_list'),
    path('brand/<int:pk>/', views.brand_detail, name='brand_detail'),
    path('categories/', views.category_list, name='category_list'),
    path('category/<slug:slug>/', views.category_detail, name='category_detail'),
    path('product/<slug:slug>/', views.product_detail, name='product_detail'),
    path('search/', views.search_results, name='search_results'),
    path('search/live/', views.live_search, name='live_search'),
]
