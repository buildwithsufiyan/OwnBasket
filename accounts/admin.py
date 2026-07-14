from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from django.db.models import Count, DecimalField, Sum, Value
from django.db.models.functions import Coalesce

from .models import CustomerProfile


@admin.register(CustomerProfile)
class CustomerProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'email', 'date_joined', 'order_count', 'lifetime_value', 'created_at')
    search_fields = ('user__username', 'user__email', 'user__first_name', 'user__last_name')
    list_filter = ('user__is_active', 'created_at')
    readonly_fields = ('user', 'email', 'date_joined', 'order_count', 'lifetime_value', 'created_at', 'updated_at')
    date_hierarchy = 'created_at'
    list_per_page = 30

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user').annotate(
            _order_count=Count('user__order', distinct=True),
            _lifetime_value=Coalesce(
                Sum('user__order__total_price'),
                Value(0),
                output_field=DecimalField(max_digits=12, decimal_places=2),
            ),
        )

    def email(self, obj):
        return obj.user.email or '-'

    def date_joined(self, obj):
        return obj.user.date_joined

    @admin.display(description='Orders', ordering='_order_count')
    def order_count(self, obj):
        return getattr(obj, '_order_count', 0)

    @admin.display(description='Lifetime value', ordering='_lifetime_value')
    def lifetime_value(self, obj):
        return f'Rs. {getattr(obj, "_lifetime_value", 0):,.2f}'

    def has_add_permission(self, request):
        return False


admin.site.unregister(User)


@admin.register(User)
class StaffOnlyUserAdmin(UserAdmin):
    list_filter = ('is_active', 'is_superuser', 'groups')

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.filter(is_staff=True)

    def get_readonly_fields(self, request, obj=None):
        readonly = list(super().get_readonly_fields(request, obj))
        if not request.user.is_superuser:
            readonly.extend(('is_staff', 'is_superuser', 'groups', 'user_permissions'))
        return tuple(dict.fromkeys(readonly))

    def has_change_permission(self, request, obj=None):
        if obj and obj.is_superuser and not request.user.is_superuser:
            return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        if obj and (obj.is_superuser or obj == request.user):
            return False
        return super().has_delete_permission(request, obj)
