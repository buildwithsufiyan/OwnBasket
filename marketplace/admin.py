from django.contrib import admin, messages
from django.db.models import Count, Sum
from django.utils import timezone

from .models import (
    CommissionRule,
    InventoryHistory,
    MarketplaceSettings,
    SellerDocument,
    SellerInventory,
    SellerNotification,
    SellerOrderFulfillment,
    SellerOrderStatusHistory,
    SellerPayout,
    SellerPayoutAccount,
    SellerProfile,
)


@admin.action(description='Approve selected sellers', permissions=('review',))
def approve_sellers(modeladmin, request, queryset):
    count = 0
    for seller in queryset:
        if not seller.is_approved:
            seller.approve(request.user)
            SellerNotification.objects.create(
                seller=seller,
                event_type=SellerNotification.EventType.SELLER_APPROVED,
                title='Store approved',
                message='Your OwnBasket store is approved. You can now manage products and orders.',
                link='/marketplace/seller/',
                email_status=SellerNotification.EmailStatus.QUEUED,
            )
            count += 1
    modeladmin.message_user(request, f'{count} seller(s) approved.')


@admin.action(description='Reject selected sellers', permissions=('review',))
def reject_sellers(modeladmin, request, queryset):
    count = 0
    for seller in queryset.exclude(verification_status=SellerProfile.VerificationStatus.REJECTED):
        seller.verification_status = SellerProfile.VerificationStatus.REJECTED
        seller.approved_by = None
        seller.approved_at = None
        seller.save(update_fields=('verification_status', 'approved_by', 'approved_at', 'updated_at'))
        SellerNotification.objects.create(
            seller=seller,
            event_type=SellerNotification.EventType.SELLER_REJECTED,
            title='Seller application rejected',
            message=seller.verification_notes or 'Your seller application was not approved. Contact support for details.',
            link='/marketplace/seller/',
            email_status=SellerNotification.EmailStatus.QUEUED,
        )
        count += 1
    modeladmin.message_user(request, f'{count} seller(s) rejected.', messages.WARNING)


@admin.action(description='Suspend selected sellers', permissions=('suspend',))
def suspend_sellers(modeladmin, request, queryset):
    count = 0
    for seller in queryset.exclude(verification_status=SellerProfile.VerificationStatus.SUSPENDED):
        seller.verification_status = SellerProfile.VerificationStatus.SUSPENDED
        seller.save(update_fields=('verification_status', 'updated_at'))
        count += 1
    modeladmin.message_user(request, f'{count} seller(s) suspended.', messages.WARNING)


class SellerDocumentInline(admin.TabularInline):
    model = SellerDocument
    extra = 0
    fields = ('document_type', 'file', 'status', 'review_notes', 'uploaded_at', 'reviewed_at')
    readonly_fields = ('uploaded_at',)


@admin.register(SellerProfile)
class SellerProfileAdmin(admin.ModelAdmin):
    actions = (approve_sellers, reject_sellers, suspend_sellers)
    list_display = (
        'store_name', 'user', 'verification_status', 'product_total', 'order_total',
        'earnings_total', 'commission_rate', 'created_at',
    )
    list_filter = ('verification_status', 'created_at', 'city')
    search_fields = ('store_name', 'legal_name', 'business_email', 'business_phone', 'user__username')
    autocomplete_fields = ('user', 'approved_by')
    readonly_fields = ('created_at', 'updated_at', 'approved_at')
    list_select_related = ('user', 'approved_by')
    list_per_page = 30
    inlines = (SellerDocumentInline,)
    fieldsets = (
        ('Account', {'fields': ('user', 'store_name', 'slug', 'legal_name', 'contact_person', 'business_email', 'business_phone')}),
        ('Store', {'fields': ('description', 'logo', 'banner', 'address', 'city')}),
        ('Verification', {'fields': ('verification_status', 'identity_reference', 'tax_identifier', 'tax_registration_type', 'verification_notes', 'approved_by', 'approved_at')}),
        ('Commercial', {'fields': ('commission_rate',)}),
        ('Policies', {'fields': ('shipping_policy', 'return_policy', 'privacy_policy')}),
        ('Notifications', {'fields': ('order_notifications', 'inventory_notifications', 'marketing_notifications')}),
        ('Audit', {'fields': ('created_at', 'updated_at')}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'approved_by').annotate(
            _product_total=Count('products', distinct=True),
            _order_total=Count('order_items__order_id', distinct=True),
            _earnings_total=Sum('order_items__seller_earning'),
        )

    def has_review_permission(self, request):
        return request.user.is_superuser or request.user.has_perm('marketplace.review_seller')

    def has_suspend_permission(self, request):
        return request.user.is_superuser or request.user.has_perm('marketplace.suspend_seller')

    def get_readonly_fields(self, request, obj=None):
        readonly = list(super().get_readonly_fields(request, obj))
        if not self.has_review_permission(request):
            readonly.extend(('verification_status', 'verification_notes', 'approved_by'))
        return tuple(dict.fromkeys(readonly))

    @admin.display(description='Products', ordering='_product_total')
    def product_total(self, obj):
        return obj._product_total

    @admin.display(description='Orders', ordering='_order_total')
    def order_total(self, obj):
        return obj._order_total

    @admin.display(description='Seller earnings', ordering='_earnings_total')
    def earnings_total(self, obj):
        return obj._earnings_total or 0


@admin.action(description='Verify selected documents', permissions=('review',))
def verify_documents(modeladmin, request, queryset):
    count = queryset.update(status=SellerDocument.ReviewStatus.VERIFIED, reviewed_at=timezone.now())
    modeladmin.message_user(request, f'{count} document(s) verified.')


@admin.action(description='Reject selected documents', permissions=('review',))
def reject_documents(modeladmin, request, queryset):
    count = queryset.update(status=SellerDocument.ReviewStatus.REJECTED, reviewed_at=timezone.now())
    modeladmin.message_user(request, f'{count} document(s) rejected.', messages.WARNING)


@admin.register(SellerDocument)
class SellerDocumentAdmin(admin.ModelAdmin):
    actions = (verify_documents, reject_documents)
    list_display = ('seller', 'document_type', 'status', 'uploaded_at', 'reviewed_at')
    list_filter = ('status', 'document_type', 'uploaded_at')
    search_fields = ('seller__store_name', 'seller__business_email')
    autocomplete_fields = ('seller',)
    list_select_related = ('seller',)

    def has_review_permission(self, request):
        return request.user.is_superuser or request.user.has_perm('marketplace.review_seller')

    def get_readonly_fields(self, request, obj=None):
        readonly = list(super().get_readonly_fields(request, obj))
        if not self.has_review_permission(request):
            readonly.extend(('status', 'review_notes', 'reviewed_at'))
        return tuple(dict.fromkeys(readonly))


@admin.register(SellerPayoutAccount)
class SellerPayoutAccountAdmin(admin.ModelAdmin):
    list_display = ('seller', 'method', 'account_title', 'account_reference', 'is_verified', 'updated_at')
    list_filter = ('is_verified', 'method')
    search_fields = ('seller__store_name', 'account_title', 'account_reference')
    autocomplete_fields = ('seller',)
    list_select_related = ('seller',)


@admin.register(SellerPayout)
class SellerPayoutAdmin(admin.ModelAdmin):
    list_display = ('seller', 'amount', 'period_start', 'period_end', 'status', 'requested_at', 'processed_at')
    list_filter = ('status', 'requested_at')
    search_fields = ('seller__store_name', 'provider_reference')
    autocomplete_fields = ('seller',)
    list_select_related = ('seller',)
    date_hierarchy = 'requested_at'
    list_per_page = 30


@admin.register(SellerNotification)
class SellerNotificationAdmin(admin.ModelAdmin):
    list_display = ('seller', 'event_type', 'title', 'email_status', 'is_read', 'created_at')
    list_filter = ('event_type', 'email_status', 'is_read', 'created_at')
    search_fields = ('seller__store_name', 'title', 'message')
    autocomplete_fields = ('seller',)
    list_select_related = ('seller',)


@admin.register(MarketplaceSettings)
class MarketplaceSettingsAdmin(admin.ModelAdmin):
    list_display = ('enabled', 'mode', 'seller_registration_enabled', 'global_commission_rate', 'updated_at')

    def has_add_permission(self, request):
        return super().has_add_permission(request) and not MarketplaceSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(CommissionRule)
class CommissionRuleAdmin(admin.ModelAdmin):
    list_display = ('name', 'scope_display', 'seller', 'category', 'rate', 'priority', 'is_active')
    list_filter = ('is_active', 'category')
    search_fields = ('name', 'seller__store_name', 'category__name')
    autocomplete_fields = ('seller', 'category')
    list_select_related = ('seller', 'category')
    ordering = ('priority', 'id')

    @admin.display(description='Scope')
    def scope_display(self, obj):
        return obj.scope.replace('_', ' ').title()


class InventoryHistoryInline(admin.TabularInline):
    model = InventoryHistory
    extra = 0
    readonly_fields = (
        'stock_change', 'reserved_change', 'stock_after', 'reserved_after', 'reason',
        'reference', 'note', 'created_by', 'created_at',
    )
    can_delete = False


@admin.register(SellerInventory)
class SellerInventoryAdmin(admin.ModelAdmin):
    list_display = ('seller', 'product', 'current_stock', 'reserved_stock', 'available', 'updated_at')
    search_fields = ('seller__store_name', 'product__name', 'product__sku')
    autocomplete_fields = ('seller', 'product')
    list_select_related = ('seller', 'product')
    inlines = (InventoryHistoryInline,)

    @admin.display(description='Current stock', ordering='product__stock')
    def current_stock(self, obj):
        return obj.product.stock

    @admin.display(description='Available')
    def available(self, obj):
        return obj.available_stock


class SellerOrderStatusHistoryInline(admin.TabularInline):
    model = SellerOrderStatusHistory
    extra = 0
    readonly_fields = ('status', 'note', 'changed_by', 'created_at')
    can_delete = False


@admin.register(SellerOrderFulfillment)
class SellerOrderFulfillmentAdmin(admin.ModelAdmin):
    list_display = ('order', 'seller', 'status', 'ready_at', 'updated_at')
    list_filter = ('status', 'updated_at')
    search_fields = ('order__id', 'seller__store_name')
    autocomplete_fields = ('seller', 'order')
    list_select_related = ('seller', 'order')
    inlines = (SellerOrderStatusHistoryInline,)
