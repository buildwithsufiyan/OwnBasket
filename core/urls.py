from django.urls import path
from . import views

urlpatterns = [
    path('', views.landing, name='landing'),
    path('home/', views.home, name='home'),
    path('health/', views.health, name='health'),
    path('robots.txt', views.robots_txt, name='robots_txt'),
    path('banner/<int:banner_id>/track-click/', views.track_banner_click, name='track_banner_click'),
    path('banner/<int:banner_id>/track-view/', views.track_banner_view, name='track_banner_view'),
]
