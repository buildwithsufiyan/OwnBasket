from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from core.admin_visual_editor import VisualEditorAdminMixin

from .forms import (
    BrandAdminForm,
    BrandHeroBannerAdminForm,
    CategoryAdminForm,
    ProductAdminForm,
    SubCategoryAdminForm,
    WarehouseAdminForm,
)
from .models import (
    Category,
    Brand,
    BrandHeroBanner,
    Product,
    ProductListingSettings,
    ProductVariant,
    ProductImage,
    ProductFeature,
    ProductSpecification,
    SubCategory,
    Warehouse,
    BuyXGetYOffer,
    CategoryDiscount,
    Coupon,
    CouponRedemption,
    FlashSale,
    FreeShippingOffer,
    ProductDiscount,
)


@admin.register(ProductListingSettings)
class ProductListingSettingsAdmin(admin.ModelAdmin):
    list_display = ("products_per_page", "default_sort", "default_view", "enable_filters", "enable_sidebar")
    fieldsets = (("Listing", {"fields": ("products_per_page", "default_sort", "default_view")}), ("Controls", {"fields": ("enable_filters", "enable_view_toggle", "enable_sidebar", "enable_sticky_filters")}))

    def has_add_permission(self, request):
        return not ProductListingSettings.objects.exists()


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    form = CategoryAdminForm
    list_display = ('name', 'image_preview', 'is_active', 'sort_order')
    list_editable = ('is_active', 'sort_order')
    list_filter = ('is_active',)
    search_fields = ('name', 'slug')
    ordering = ('sort_order', 'name', 'id')
    prepopulated_fields = {
        'slug': ('name',)
    }

    fieldsets = (
        ('Category Details', {
            'fields': ('name', 'slug', 'category_image'),
        }),
        ('Display Settings', {
            'fields': ('is_active', 'sort_order'),
        }),
    )

    def image_preview(self, obj):
        if obj.category_image:
            return format_html(
                '<img src="{}" width="60" height="60" style="object-fit:cover;'
                'border-radius:12px;border:1px solid #e5e7eb;" />',
                obj.category_image.url,
            )
        return "No Image"

    image_preview.short_description = 'Category Image Preview'


@admin.register(SubCategory)
class SubCategoryAdmin(admin.ModelAdmin):
    form = SubCategoryAdminForm
    list_display = ('name', 'category', 'is_active', 'sort_order')
    list_editable = ('is_active', 'sort_order')
    list_filter = ('is_active', 'category')
    search_fields = ('name', 'slug', 'category__name')
    ordering = ('category__name', 'sort_order', 'name', 'id')
    prepopulated_fields = {
        'slug': ('name',)
    }


class BrandHeroBannerInline(admin.StackedInline):
    model = BrandHeroBanner
    form = BrandHeroBannerAdminForm
    extra = 0
    show_change_link = True
    fields = (
        'banner_title',
        'banner_subtitle',
        ('button_text', 'button_url'),
        'cover_image',
        ('display_order', 'is_active'),
    )
    ordering = ('display_order', 'id')


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    form = BrandAdminForm
    list_display = ('name', 'logo_preview', 'is_active', 'display_order')
    list_editable = ('is_active', 'display_order')
    list_filter = ('is_active',)
    search_fields = ('name',)
    ordering = ('display_order', 'name', 'id')

    fieldsets = (
        ('Brand Details', {
            'fields': ('name', 'logo'),
        }),
        ('Display Settings', {
            'fields': ('is_active', 'display_order'),
        }),
    )
    inlines = [BrandHeroBannerInline]

    def logo_preview(self, obj):
        if obj.logo:
            return format_html(
                '<img src="{}" width="60" height="60" style="object-fit:contain;'
                'border-radius:12px;border:1px solid #e5e7eb;background:#fff;padding:4px;" />',
                obj.logo.url,
            )
        return "No Logo"

    logo_preview.short_description = 'Brand Logo Preview'


@admin.register(BrandHeroBanner)
class BrandHeroBannerAdmin(VisualEditorAdminMixin, admin.ModelAdmin):
    form = BrandHeroBannerAdminForm
    visual_editor_kind = 'brand-hero-banner'
    visual_editor_title = 'Brand Banner Live Preview'
    visual_editor_description = 'Preview title, subtitle, button, and cover image instantly while editing the brand banner.'
    visual_editor_file_fields = ('cover_image',)
    list_display = (
        'banner_title',
        'brand',
        'display_order',
        'is_active',
        'created_at',
    )
    list_editable = ('display_order', 'is_active')
    list_filter = ('is_active', 'brand')
    search_fields = ('banner_title', 'banner_subtitle', 'brand__name')
    autocomplete_fields = ('brand',)
    ordering = ('brand__name', 'display_order', 'id')

    fieldsets = (
        ('Banner Content', {
            'fields': (
                'brand',
                ('banner_title', 'banner_subtitle'),
                ('button_text', 'button_url'),
                'cover_image',
            ),
            'classes': ('visual-card', 'section-content'),
            'description': 'Main brand banner content and media.',
        }),
        ('Publishing', {
            'fields': (
                ('display_order', 'is_active'),
                'created_at',
            ),
            'classes': ('visual-card', 'collapse', 'section-display', 'initial-open'),
            'description': 'Publishing controls and ordering.',
        }),
    )
    readonly_fields = ('created_at',)


@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    form = WarehouseAdminForm
    list_display = ('name', 'code', 'city', 'is_active')
    list_editable = ('is_active',)
    search_fields = ('name', 'code', 'city')
    list_filter = ('is_active',)


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 1


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1


class ProductFeatureInline(admin.TabularInline):
    model = ProductFeature
    extra = 1


class ProductSpecificationInline(admin.TabularInline):
    model = ProductSpecification
    extra = 1


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    form = ProductAdminForm
    list_display = (
        'name',
        'sku',
        'category',
        'subcategory',
        'brand',
        'display_price_block',
        'stock',
        'inventory_state',
        'analytics_snapshot',
        'badge_snapshot',
        'is_active',
    )
    list_filter = (
        'is_active',
        'category',
        'subcategory',
        'brand',
        'featured_product',
        'recommended_product',
        'flash_sale_product',
        'deal_of_the_day',
        'premium_choice',
        'verified_product',
        'free_delivery',
        'cash_on_delivery',
        'allow_backorder',
    )
    list_editable = ('is_active',)

    search_fields = ('name', 'slug', 'brand__name', 'category__name')
    autocomplete_fields = ('brand', 'category', 'subcategory', 'warehouse')
    readonly_fields = (
        'slug',
        'sku',
        'discount_percentage',
        'profit_margin',
        'out_of_stock',
        'created_at',
        'analytics_snapshot_readonly',
        'badge_snapshot_readonly',
        'primary_image_preview',
    )
    fieldsets = (
        ('Product Information', {
            'fields': (
                'name',
                ('slug', 'sku', 'barcode'),
                ('brand', 'category', 'subcategory'),
                'primary_image_preview',
                ('image', 'video'),
                ('short_description', 'description'),
                ('warranty', 'return_policy'),
            ),
        }),
        ('Pricing', {
            'fields': (
                ('cost_price', 'selling_price', 'price'),
                ('mrp', 'discount_price'),
                ('discount_percentage', 'profit_margin'),
                ('offer_start_at', 'offer_end_at'),
                ('tax_percentage', 'delivery_text'),
            ),
        }),
        ('Product Badges', {
            'fields': (
                ('featured_product', 'recommended_product', 'flash_sale_product', 'deal_of_the_day'),
                ('premium_choice', 'verified_product', 'free_delivery', 'cash_on_delivery'),
                'badge_snapshot_readonly',
            ),
        }),
        ('Inventory', {
            'fields': (
                ('stock', 'low_stock_alert', 'out_of_stock'),
                ('allow_backorder', 'warehouse', 'is_active'),
                ('weight', 'length_cm', 'width_cm', 'height_cm'),
            ),
        }),
        ('Ratings And Analytics', {
            'fields': (
                ('rating', 'reviews_count'),
                ('total_sold', 'total_views', 'wishlist_count'),
                'analytics_snapshot_readonly',
                'created_at',
                'last_viewed_at',
            ),
        }),
    )

    inlines = [
        ProductVariantInline,
        ProductImageInline,
        ProductFeatureInline,
        ProductSpecificationInline,
    ]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('brand', 'category', 'subcategory', 'warehouse')

    def primary_image_preview(self, obj):
        if obj.pk and obj.image:
            return format_html(
                '<img src="{}" width="90" height="90" style="object-fit:contain;border-radius:14px;border:1px solid #e5e7eb;background:#fff;padding:6px;" />',
                obj.image.url,
            )
        return "No Primary Image"

    def display_price_block(self, obj):
        price = obj.selling_price or obj.price
        compare = obj.mrp or obj.old_price
        if compare and compare > price:
            return format_html(
                '<div><strong>Rs. {}</strong><br><span style="color:#98a2b3;text-decoration:line-through;">Rs. {}</span></div>',
                price,
                compare,
            )
        return f"Rs. {price}"

    def inventory_state(self, obj):
        if obj.out_of_stock:
            return format_html('<span style="color:#b42318;font-weight:700;">{}</span>', 'Out of Stock')
        if obj.is_limited_stock:
            return format_html('<span style="color:#b54708;font-weight:700;">Low Stock ({})</span>', obj.stock)
        return format_html('<span style="color:#067647;font-weight:700;">In Stock ({})</span>', obj.stock)

    def analytics_snapshot(self, obj):
        return f"Sold {obj.total_sold} | Views {obj.total_views} | Wishlist {obj.wishlist_count}"

    def analytics_snapshot_readonly(self, obj):
        if not obj.pk:
            return "Analytics will appear after the product is created."
        return format_html(
            '<div><strong>Total Sold:</strong> {}<br><strong>Total Views:</strong> {}<br><strong>Wishlist Count:</strong> {}<br><strong>Average Rating:</strong> {}<br><strong>Total Reviews:</strong> {}</div>',
            obj.total_sold,
            obj.total_views,
            obj.wishlist_count,
            obj.rating,
            obj.reviews_count,
        )

    def badge_snapshot(self, obj):
        return ", ".join(obj.active_badges[:3]) or "No badges"

    def badge_snapshot_readonly(self, obj):
        if not obj.pk:
            return "Badges will be calculated after the product is saved."
        badges = obj.active_badges
        if not badges:
            return "No badges active."
        return mark_safe(
            ''.join(
                f'<span style="display:inline-flex;margin:0 6px 6px 0;padding:4px 10px;border-radius:999px;background:#fff8e1;color:#7a4f00;font-weight:700;">{badge}</span>'
                for badge in badges
            )
        )


@admin.register(ProductDiscount)
class ProductDiscountAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'product',
        'discount_type',
        'value',
        'is_active',
        'start_at',
        'end_at',
        'priority',
    )
    list_filter = ('is_active', 'discount_type')
    search_fields = ('name', 'product__name')
    autocomplete_fields = ('product',)


@admin.register(CategoryDiscount)
class CategoryDiscountAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'category',
        'discount_type',
        'value',
        'is_active',
        'start_at',
        'end_at',
        'priority',
    )
    list_filter = ('is_active', 'discount_type')
    search_fields = ('name', 'category__name')
    autocomplete_fields = ('category',)


@admin.register(FlashSale)
class FlashSaleAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'discount_type',
        'value',
        'is_active',
        'start_at',
        'end_at',
        'priority',
    )
    list_filter = ('is_active', 'discount_type')
    search_fields = ('name',)
    filter_horizontal = ('products', 'categories')


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = (
        'code',
        'title',
        'discount_type',
        'value',
        'min_order_amount',
        'free_shipping',
        'is_active',
        'start_at',
        'end_at',
    )
    list_filter = ('is_active', 'discount_type', 'free_shipping')
    search_fields = ('code', 'title')


@admin.register(FreeShippingOffer)
class FreeShippingOfferAdmin(admin.ModelAdmin):
    list_display = ('name', 'min_order_amount', 'is_active', 'start_at', 'end_at')
    list_filter = ('is_active',)
    search_fields = ('name',)


@admin.register(BuyXGetYOffer)
class BuyXGetYOfferAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'buy_product',
        'buy_category',
        'buy_quantity',
        'get_product',
        'get_category',
        'get_quantity',
        'is_active',
        'start_at',
        'end_at',
    )
    list_filter = ('is_active',)
    search_fields = ('name',)
    autocomplete_fields = ('buy_product', 'buy_category', 'get_product', 'get_category')


@admin.register(CouponRedemption)
class CouponRedemptionAdmin(admin.ModelAdmin):
    list_display = ('coupon', 'user', 'order', 'used_at')
    list_filter = ('coupon',)
    search_fields = ('coupon__code', 'user__username', 'user__email')
    autocomplete_fields = ('coupon', 'user', 'order')
