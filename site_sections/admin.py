from django.contrib import admin

from .models import HeroSection, HomepageSection, ProductCarouselSection


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


@admin.register(ProductCarouselSection)
class ProductCarouselSectionAdmin(admin.ModelAdmin):
    list_display = ("name", "title", "source_type", "display_order", "is_active")
    list_editable = ("display_order", "is_active")
    list_filter = ("source_type", "is_active", "category", "brand")
    search_fields = ("name", "title", "subtitle", "manual_products__name")
    filter_horizontal = ("manual_products",)
    ordering = ("display_order", "id")
    fieldsets = (
        ("General", {"fields": ("name", "title", "subtitle", "display_order", "is_active")}),
        ("Product source", {"fields": ("source_type", "manual_products", "category", "brand", "products_limit")} ),
        ("Call to action", {"fields": ("show_view_all", "view_all_text", "view_all_url")} ),
        ("Carousel controls", {"fields": ("autoplay", "loop", "autoplay_speed", "show_navigation", "show_pagination")} ),
        ("Visibility", {"fields": ("show_on_mobile", "show_on_desktop")} ),
    )
