from django.urls import path
from . import views

app_name = "themes"

urlpatterns = [
    path("", views.theme_manager, name="theme_manager"),
    path("scan/", views.scan_themes, name="scan_themes"),
    path("builder/", views.theme_builder, name="theme_builder"),
    path("settings/", views.theme_settings, name="theme_settings"),
    path("import/", views.import_theme, name="import_theme"),
    path("export/<int:theme_id>/", views.export_theme, name="export_theme"),
    path("apply/<int:theme_id>/", views.apply_theme, name="apply_theme"),
    path("preview/<int:theme_id>/", views.preview_theme, name="preview_theme"),
    path("preview-clear/", views.preview_clear, name="preview_clear"),
    path("delete/<int:theme_id>/", views.delete_theme, name="delete_theme"),
    path("mapping/<int:theme_id>/", views.template_mapping, name="template_mapping"),
    path(
        "converter/<int:theme_id>/",
        views.template_converter_review,
        name="template_converter_review",
    ),
    path(
        "converter/apply/<int:log_id>/",
        views.apply_suggestion,
        name="apply_suggestion",
        kwargs={"log_id": 0},  # Default for bulk actions
    ),
    path("history/<int:theme_id>/", views.file_history, name="file_history"),
    path("restore/<int:backup_id>/", views.restore_backup, name="restore_backup"),
]
