from django.urls import path
from .views import (AuditedPasswordResetConfirmView, AuditedPasswordResetView, SecureLoginView, account_choice,
                    change_password, dashboard, logout_view, profile, register, settings)
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('account/', account_choice, name='account_choice'),
    path('account/dashboard/', dashboard, name='account_dashboard'),
    path('account/profile/', profile, name='account_profile'),
    path('account/settings/', settings, name='account_settings'),
    path('account/password/', change_password, name='account_change_password'),

    path(
        'login/',
        SecureLoginView.as_view(),
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
    path('password-reset/', AuditedPasswordResetView.as_view(), name='password_reset'),
    path('password-reset/done/', auth_views.PasswordResetDoneView.as_view(), name='password_reset_done'),
    path('password-reset/<uidb64>/<token>/', AuditedPasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('password-reset/complete/', auth_views.PasswordResetCompleteView.as_view(), name='password_reset_complete'),
]
