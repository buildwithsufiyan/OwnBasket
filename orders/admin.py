from django.contrib import admin
from django.db.models import Count
from django.utils.html import format_html
from .models import Order, OrderItem, PaymentTransaction, Refund


@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display = ('id', 'order', 'method', 'status', 'amount', 'created_at')
    list_filter = ('method', 'status', 'created_at')
    search_fields = ('order__id', 'provider_reference')
    readonly_fields = ('created_at', 'updated_at')
    list_select_related = ('order',)


@admin.register(Refund)
class RefundAdmin(admin.ModelAdmin):
    list_display = ('id', 'order', 'order_item', 'amount', 'quantity', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('order__id', 'reason')
    readonly_fields = ('created_at',)
    list_select_related = ('order', 'payment', 'order_item__product', 'order_item__seller')


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0

    readonly_fields = (
        'product', 'seller', 'seller_name', 'product_image', 'size', 'color', 'quantity', 'original_price',
        'discount_amount', 'applied_offer_name', 'price', 'marketplace_commission', 'seller_earning',
    )

    fields = (
        'product',
        'seller',
        'seller_name',
        'product_image',
        'size',
        'color',
        'quantity',
        'original_price',
        'discount_amount',
        'applied_offer_name',
        'price',
        'marketplace_commission',
        'seller_earning',
    )

    def product_image(self, obj):
        if obj.product_id and obj.product.image:
            return format_html(
                '<img src="{}" width="80" height="80" style="object-fit:cover;" />',
                obj.product.image.url
            )
        return "No Image"

    product_image.short_description = "Image"

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('product', 'seller')


def _set_order_status(modeladmin, request, queryset, status):
    count = 0
    for order in queryset.exclude(status=status):
        order.status = status
        order.save(update_fields=('status',))
        count += 1
    modeladmin.message_user(request, f'{count} order(s) moved to {status}.')


@admin.action(description='Mark selected orders as Processing')
def mark_processing(modeladmin, request, queryset):
    _set_order_status(modeladmin, request, queryset, 'Processing')


@admin.action(description='Mark selected orders as Shipped')
def mark_shipped(modeladmin, request, queryset):
    _set_order_status(modeladmin, request, queryset, 'Shipped')


@admin.action(description='Mark selected orders as Delivered')
def mark_delivered(modeladmin, request, queryset):
    _set_order_status(modeladmin, request, queryset, 'Delivered')


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    actions = (mark_processing, mark_shipped, mark_delivered)
    list_display = (
        'id',
        'full_name',
        'email',
        'item_count',
        'seller_count',
        'coupon_code',
        'total_price',
        'status_badge',
        'created_at',
    )

    inlines = [OrderItemInline]
    search_fields = ('id', 'full_name', 'email', 'coupon_code', 'items__seller__store_name')
    list_filter = ('status', 'created_at')
    date_hierarchy = 'created_at'
    list_select_related = ('user',)
    list_per_page = 30
    readonly_fields = (
        'user', 'full_name', 'email', 'address', 'subtotal', 'discount_total',
        'shipping_amount', 'coupon_code', 'total_price', 'created_at',
        'tax_amount', 'payment_method', 'payment_status', 'customer_state',
    )
    fieldsets = (
        ('Order', {'fields': ('user', 'status', 'created_at')}),
        ('Customer and delivery', {'fields': ('full_name', 'email', 'address')}),
        ('Payment summary', {'fields': ('subtotal', 'discount_total', 'tax_amount', 'shipping_amount', 'coupon_code', 'total_price', 'payment_method', 'payment_status')}),
        ('Reporting snapshot', {'fields': ('customer_state',)}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user').annotate(
            _item_count=Count('items'),
            _seller_count=Count('items__seller', distinct=True),
        )

    @admin.display(description='Items', ordering='_item_count')
    def item_count(self, obj):
        return obj._item_count

    @admin.display(description='Sellers', ordering='_seller_count')
    def seller_count(self, obj):
        return obj._seller_count

    @admin.display(description='Status', ordering='status')
    def status_badge(self, obj):
        colors = {
            'Pending': ('#b54708', '#fffaeb'),
            'Processing': ('#175cd3', '#eff8ff'),
            'Shipped': ('#5925dc', '#f4f3ff'),
            'Delivered': ('#067647', '#ecfdf3'),
        }
        color, background = colors.get(obj.status, ('#344054', '#f2f4f7'))
        return format_html(
            '<span style="display:inline-flex;padding:4px 9px;border-radius:999px;'
            'font-weight:700;color:{};background:{};">{}</span>',
            color, background, obj.status,
        )
