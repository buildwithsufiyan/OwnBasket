from django.contrib import admin
from django.utils.html import format_html
from .models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0

    readonly_fields = ('product_image',)

    fields = (
        'product',
        'product_image',
        'size',
        'color',
        'quantity',
        'original_price',
        'discount_amount',
        'applied_offer_name',
        'price',
    )

    def product_image(self, obj):
        if obj.product.image:
            return format_html(
                '<img src="{}" width="80" height="80" style="object-fit:cover;" />',
                obj.product.image.url
            )
        return "No Image"

    product_image.short_description = "Image"


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'full_name',
        'email',
        'address',
        'subtotal',
        'discount_total',
        'shipping_amount',
        'coupon_code',
        'total_price',
        'status',
        'created_at',
    )

    inlines = [OrderItemInline]
    search_fields = ('id', 'full_name', 'email', 'coupon_code')
