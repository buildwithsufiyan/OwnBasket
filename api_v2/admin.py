from django.contrib import admin

from .models import PushDevice


@admin.register(PushDevice)
class PushDeviceAdmin(admin.ModelAdmin):
    list_display = ('user', 'platform', 'provider', 'notifications_enabled', 'last_seen_at')
    list_filter = ('platform', 'provider', 'notifications_enabled')
    list_select_related = ('user',)
    readonly_fields = tuple(field.name for field in PushDevice._meta.fields)
    search_fields = ('user__username', 'user__email')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
