from django.contrib import admin

from .models import IdempotencyRecord, MobileSession, PushDelivery, PushDevice, SyncOperation, SyncState


class ReadOnlyApiAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(PushDevice)
class PushDeviceAdmin(ReadOnlyApiAdmin):
    list_display = ('user', 'platform', 'provider', 'notifications_enabled', 'last_seen_at')
    list_filter = ('platform', 'provider', 'notifications_enabled')
    list_select_related = ('user',)
    readonly_fields = ('user', 'device_id_hash', 'platform', 'provider', 'notifications_enabled', 'locale', 'app_version', 'token_updated_at', 'disabled_at', 'failure_count', 'created_at', 'last_seen_at')
    search_fields = ('user__username', 'user__email')
    exclude = ('provider_token_hash', 'provider_token_encrypted')



@admin.register(MobileSession)
class MobileSessionAdmin(ReadOnlyApiAdmin):
    list_display = ('user', 'device_name', 'platform', 'last_used_at', 'refresh_expires_at', 'revoked_at')
    list_filter = ('platform', 'revoked_at')
    search_fields = ('user__username', 'user__email', 'device_name')
    exclude = ('access_token_hash', 'refresh_token_hash', 'device_id_hash')


@admin.register(PushDelivery)
class PushDeliveryAdmin(ReadOnlyApiAdmin):
    list_display = ('id', 'device', 'event_key', 'status', 'attempt_count', 'next_attempt_at')
    list_filter = ('status', 'device__provider')
    search_fields = ('event_key', 'device__user__username')


@admin.register(IdempotencyRecord)
class IdempotencyRecordAdmin(ReadOnlyApiAdmin):
    list_display = ('user', 'method', 'path', 'status', 'response_status', 'created_at', 'expires_at')
    list_filter = ('status', 'method')
    exclude = ('key_hash', 'request_hash', 'response_body')


@admin.register(SyncOperation)
class SyncOperationAdmin(ReadOnlyApiAdmin):
    list_display = ('user', 'operation', 'client_action_id', 'status', 'attempt_count', 'updated_at')
    list_filter = ('operation', 'status')
    exclude = ('device_id_hash', 'payload_hash', 'result')


@admin.register(SyncState)
class SyncStateAdmin(ReadOnlyApiAdmin):
    list_display = ('user', 'version', 'updated_at')
