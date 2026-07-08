from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User

from .models import CustomerProfile


@admin.register(CustomerProfile)
class CustomerProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'email', 'date_joined', 'created_at')
    search_fields = ('user__username', 'user__email', 'user__first_name', 'user__last_name')
    readonly_fields = ('created_at', 'updated_at')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')

    def email(self, obj):
        return obj.user.email or '-'

    def date_joined(self, obj):
        return obj.user.date_joined

    def has_add_permission(self, request):
        return False


admin.site.unregister(User)


@admin.register(User)
class StaffOnlyUserAdmin(UserAdmin):
    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.filter(is_staff=True)
