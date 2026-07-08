from django.urls import path

from . import views

app_name = "banners"

urlpatterns = [
    path(
        "track-click/<int:banner_id>/",
        views.track_banner_click,
        name="track_banner_click",
    ),
    path(
        "track-view/<int:banner_id>/", views.track_banner_view, name="track_banner_view"
    ),
    path(
        "api/update-preview-session/",
        views.update_preview_session,
        name="update_preview_session",
    ),
]
