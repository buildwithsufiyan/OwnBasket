from django.urls import path

from . import views


app_name = 'fonts'

urlpatterns = [
    path('api/', views.active_fonts_api, name='active-fonts-api'),
    path('library.css', views.managed_fonts_stylesheet, name='stylesheet'),
    path('file/<int:pk>/', views.managed_font_file, name='font-file'),
]
