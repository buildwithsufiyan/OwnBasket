from django.contrib import admin

from .models import HeroSection, HomepageSection


@admin.register(HomepageSection)
class HomepageSectionAdmin(admin.ModelAdmin):
    list_display = ("name", "section_type", "display_order", "is_active")
    list_editable = ("display_order", "is_active")
    list_filter = ("section_type", "is_active")
    search_fields = ("name",)
    ordering = ("display_order",)

    def has_add_permission(self, request):
        return False


@admin.register(HeroSection)
class HeroSectionAdmin(admin.ModelAdmin):
    list_display = ("name", "heading", "display_order", "is_active")
    list_editable = ("display_order", "is_active")
    search_fields = ("name", "heading", "subheading")
    ordering = ("display_order",)
    fieldsets = (
        ("General", {"fields": ("name", "display_order", "is_active")}),
        (
            "Content",
            {
                "fields": (
                    "heading",
                    "subheading",
                    "background_image",
                    "background_color",
                )
            },
        ),
        ("Call to Action", {"fields": ("button_text", "button_url")}),
    )
