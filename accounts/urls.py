from django.urls import path
from .views import account_choice, change_password, dashboard, logout_view, profile, register, settings
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('account/', account_choice, name='account_choice'),
    path('account/dashboard/', dashboard, name='account_dashboard'),
    path('account/profile/', profile, name='account_profile'),
    path('account/settings/', settings, name='account_settings'),
    path('account/password/', change_password, name='account_change_password'),

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
