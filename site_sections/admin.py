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
    list_filter = ("source_type", "is_active", "brand", "category")
    search_fields = ("name", "title", "subtitle")
    ordering = ("display_order",)
    autocomplete_fields = ("manual_products", "category", "brand")

    fieldsets = (
        (
            "General",
            {
                "fields": ("name", "display_order", "is_active"),
                "description": "Internal name and display settings.",
            },
        ),
        (
            "Content",
            {
                "fields": ("title", "subtitle", "button_text", "button_url"),
                "description": "Text content for the section.",
            },
        ),
        (
            "Product Source",
            {
                "fields": (
                    "source_type",
                    "category",
                    "brand",
                    "manual_products",
                    "products_limit",
                ),
                "description": "Choose how to populate products. Some fields are only required for specific source types.",
            },
        ),
        (
            "Appearance",
            {
                "fields": (
                    "layout_style",
                    "background_color",
                    "background_image",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    class Media:
        js = ("admin/js/product_carousel_admin.js",)

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("category", "brand")
            .prefetch_related("manual_products")
        )
