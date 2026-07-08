from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from .models import Theme, TemplateConversionLog, ThemeFileBackup


@admin.register(Theme)
class ThemeAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "slug",
        "version",
        "author",
        "theme_folder",
        "is_active",
        "is_custom",
        "updated_at",
    )
    list_filter = ("is_active", "is_custom", "author")
    search_fields = ("name", "slug", "author", "theme_folder")
    readonly_fields = ("created_at", "updated_at", "theme_manager_link")
    fieldsets = (
        (
            "Theme Metadata",
            {
                "fields": (
                    "theme_manager_link",
                    "name",
                    "slug",
                    "theme_folder",
                    "description",
                    "version",
                    "author",
                    "preview_image",
                    "is_active",
                    "is_custom",
                )
            },
        ),
        (
            "Layout Components",
            {
                "classes": ("collapse",),
                "fields": (
                    "header_layout",
                    "hero_layout",
                    "category_layout",
                    "brand_layout",
                    "product_card_layout",
                    "product_detail_layout",
                    "cart_layout",
                    "checkout_layout",
                    "footer_layout",
                ),
            },
        ),
        (
            "Brand Colors",
            {
                "classes": ("collapse",),
                "fields": (
                    "brand_primary_color",
                    "brand_secondary_color",
                    "brand_accent_color",
                ),
            },
        ),
        (
            "Background Colors",
            {
                "classes": ("collapse",),
                "fields": (
                    "bg_body_color",
                    "bg_section_color",
                    "bg_card_color",
                    "bg_header_color",
                    "bg_footer_color",
                ),
            },
        ),
        (
            "Text Colors",
            {
                "classes": ("collapse",),
                "fields": (
                    "text_primary_color",
                    "text_secondary_color",
                    "text_heading_color",
                    "text_link_color",
                    "text_link_hover_color",
                ),
            },
        ),
        (
            "Button Colors",
            {
                "classes": ("collapse",),
                "fields": (
                    "btn_primary_bg_color",
                    "btn_primary_hover_bg_color",
                    "btn_secondary_bg_color",
                    "btn_secondary_hover_bg_color",
                ),
            },
        ),
        (
            "Product Colors",
            {
                "classes": ("collapse",),
                "fields": (
                    "product_price_color",
                    "product_sale_price_color",
                    "product_discount_badge_bg_color",
                    "product_discount_badge_text_color",
                ),
            },
        ),
        (
            "Status Colors",
            {
                "classes": ("collapse",),
                "fields": (
                    "status_success_color",
                    "status_warning_color",
                    "status_danger_color",
                    "status_info_color",
                ),
            },
        ),
        (
            "Border Colors",
            {
                "classes": ("collapse",),
                "fields": (
                    "border_global_color",
                    "border_input_color",
                    "border_card_color",
                ),
            },
        ),
        (
            "Button Component Styles",
            {
                "classes": ("collapse",),
                "fields": (
                    "btn_border_radius", "btn_padding", "btn_font_size", "btn_font_weight", 
                    "btn_border_width", "btn_border_style", "btn_hover_animation", 
                    "btn_hover_scale", "btn_hover_shadow"
                ),
            },
        ),
        (
            "Card Component Styles",
            {
                "classes": ("collapse",),
                "fields": (
                    "card_border_radius", "card_border_width", "card_box_shadow", 
                    "card_hover_shadow", "card_hover_lift_effect", "card_image_radius"
                ),
            },
        ),
        (
            "Form Component Styles",
            {
                "classes": ("collapse",),
                "fields": (
                    "form_input_height", "form_input_border_radius", "form_input_border_width",
                    "form_input_focus_color", "form_placeholder_color", "form_label_style"
                ),
            },
        ),
        (
            "Badge Component Styles",
            {
                "classes": ("collapse",),
                "fields": ("badge_radius", "badge_padding", "badge_font_size"),
            },
        ),
        (
            "Table Component Styles",
            {
                "classes": ("collapse",),
                "fields": ("table_header_style", "table_row_hover", "table_border_style"),
            },
        ),
        (
            "Alert Component Styles",
            {
                "classes": ("collapse",),
                "fields": ("alert_radius", "alert_shadow", "alert_padding"),
            },
        ),
        (
            "Modal Component Styles",
            {
                "classes": ("collapse",),
                "fields": ("modal_radius", "modal_shadow", "modal_width"),
            },
        ),
        (
            "Typography & Styling",
            {
                "classes": ("collapse",),
                "fields": (
                    "font_family",
                    "border_radius",
                    "button_style",
                    "animation_style",
                ),
            },
        ),
        (
            "Global Theme Settings",
            {
                "classes": ("collapse",),
                "fields": (
                    "container_width",
                    "section_spacing",
                    "navbar_height",
                    "footer_width",
                    "border_width",
                    "border_style",
                    "image_border_radius",
                    "input_border_radius",
                    "card_shadow",
                    "button_shadow",
                    "global_transition_speed",
                    "hover_animation_style",
                    "global_loader_toggle",
                    "scroll_to_top_toggle",
                ),
            },
        ),
        (
            "Timestamps",
            {
                "classes": ("collapse",),
                "fields": ("created_at", "updated_at"),
            },
        ),
    )

    def theme_manager_link(self, obj=None):
        url = reverse("themes:theme_manager")
        return format_html(
            '<a class="button" href="{}">Open WordPress-style Theme Manager</a>', url
        )

    theme_manager_link.short_description = "Theme Manager"


@admin.register(TemplateConversionLog)
class TemplateConversionLogAdmin(admin.ModelAdmin):
    list_display = (
        "theme",
        "file_path",
        "conversion_type",
        "status",
        "confidence",
        "created_at",
    )
    list_filter = ("status", "conversion_type", "theme")
    search_fields = ("file_path", "description")
    readonly_fields = (
        "theme",
        "file_path",
        "line_number",
        "target_selector",
        "original_html",
        "suggested_code",
        "confidence",
        "description",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(ThemeFileBackup)
class ThemeFileBackupAdmin(admin.ModelAdmin):
    list_display = ("theme", "file_path", "version", "created_at")
    list_filter = ("theme",)
    search_fields = ("file_path",)
    readonly_fields = (
        "theme",
        "file_path",
        "version",
        "backup_file_path",
        "created_at",
        "restored_from",
    )

    def has_add_permission(self, request):
        return False
