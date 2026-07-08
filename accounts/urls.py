from django.urls import path
from .views import register, account_choice, logout_view
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('account/', account_choice, name='account_choice'),

    path(
        'login/',
        auth_views.LoginView.as_view(),
        name='login'
    ),

    path(
        'logout/',
        logout_view,
        name='logout'
    ),

    path(
        'register/',
        register,
        name='register'
    ),
]
