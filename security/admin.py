from django.contrib import admin
from django.utils import timezone

from .models import (AccountSecurityState, AuditEvent, PasswordHistory, PolicyAcceptance, PolicyVersion,
                     PrivacyRequest, SecurityAlert, TwoFactorProfile, UserSession)
from .services import audit


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'category', 'action', 'success', 'user', 'ip_address', 'object_model', 'object_id')
    list_filter = ('category', 'action', 'success', 'timestamp')
    search_fields = ('action', 'user__username', 'ip_address', 'request_id', 'object_repr')
    readonly_fields = tuple(field.name for field in AuditEvent._meta.fields)
    date_hierarchy = 'timestamp'
    list_select_related = ('user',)
    list_per_page = 50

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.action(description='Resolve selected alerts')
def resolve_alerts(modeladmin, request, queryset):
    count = queryset.filter(resolved=False).update(resolved=True, resolved_at=timezone.now())
    audit('security_alerts_resolved', category=AuditEvent.Category.ADMIN, user=request.user,
          request=request, metadata={'count': count})


@admin.register(SecurityAlert)
class SecurityAlertAdmin(admin.ModelAdmin):
    actions = (resolve_alerts,)
    list_display = ('created_at', 'severity', 'alert_type', 'message', 'user', 'resolved')
    list_filter = ('severity', 'alert_type', 'resolved', 'created_at')
    search_fields = ('message', 'user__username')
    readonly_fields = ('created_at', 'resolved_at')


@admin.register(UserSession)
class UserSessionAdmin(admin.ModelAdmin):
    list_display = ('user', 'device', 'browser', 'ip_address', 'last_active', 'ended_at')
    list_filter = ('ended_at', 'browser', 'last_active')
    search_fields = ('user__username', 'ip_address', 'device', 'browser')
    readonly_fields = tuple(field.name for field in UserSession._meta.fields)
    list_select_related = ('user',)
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False


@admin.register(TwoFactorProfile)
class TwoFactorProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'opted_in', 'method', 'verified_at', 'updated_at')
    list_filter = ('opted_in', 'method')
    search_fields = ('user__username', 'user__email')
    readonly_fields = tuple(field.name for field in TwoFactorProfile._meta.fields)
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False


@admin.register(PrivacyRequest)
class PrivacyRequestAdmin(admin.ModelAdmin):
    list_display = ('user', 'request_type', 'status', 'requested_at', 'completed_at')
    list_filter = ('request_type', 'status', 'requested_at')
    search_fields = ('user__username', 'user__email')
    readonly_fields = ('user', 'request_type', 'requested_at')
    list_select_related = ('user',)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser or request.user.has_perm('security.process_privacy_requests')

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        old_status = None
        if change:
            old_status = PrivacyRequest.objects.filter(pk=obj.pk).values_list('status', flat=True).first()
        obj.completed_at = timezone.now() if obj.status == PrivacyRequest.Status.COMPLETED else None
        super().save_model(request, obj, form, change)
        if old_status != obj.status:
            audit('privacy_request_status_changed', category=AuditEvent.Category.COMPLIANCE,
                  user=request.user, request=request, obj=obj,
                  metadata={'old_status': old_status or '', 'new_status': obj.status})


admin.site.register(PolicyVersion)


@admin.register(PolicyAcceptance)
class PolicyAcceptanceAdmin(admin.ModelAdmin):
    list_display = ('user', 'policy', 'accepted_at', 'ip_address')
    list_select_related = ('user', 'policy')
    readonly_fields = tuple(field.name for field in PolicyAcceptance._meta.fields)
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False


@admin.register(AccountSecurityState)
class AccountSecurityStateAdmin(admin.ModelAdmin):
    list_display = ('user', 'failed_login_count', 'locked_until', 'last_failed_login')
    list_select_related = ('user',)
    readonly_fields = tuple(field.name for field in AccountSecurityState._meta.fields)
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False


@admin.register(PasswordHistory)
class PasswordHistoryAdmin(admin.ModelAdmin):
    list_display = ('user', 'created_at')
    readonly_fields = ('user', 'encoded_password', 'created_at')
    exclude = ('encoded_password',)
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False
