from django.urls import path

from . import views

app_name = 'security'

urlpatterns = [
    path('center/', views.security_center, name='center'),
    path('sessions/logout-others/', views.logout_other_sessions, name='logout_other_sessions'),
    path('sessions/<int:session_id>/revoke/', views.revoke_session, name='revoke_session'),
    path('two-factor/opt-in/', views.two_factor_opt_in, name='two_factor_opt_in'),
    path('two-factor/opt-out/', views.two_factor_opt_out, name='two_factor_opt_out'),
    path('privacy-requests/', views.privacy_requests, name='privacy_requests'),
]
