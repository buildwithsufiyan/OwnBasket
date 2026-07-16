from django.contrib import admin

from .models import ScheduledReport


@admin.register(ScheduledReport)
class ScheduledReportAdmin(admin.ModelAdmin):
    list_display = ('report_type', 'frequency', 'recipient', 'format', 'active', 'next_run', 'last_sent')
    list_filter = ('active', 'frequency', 'format', 'report_type')
    search_fields = ('recipient', 'report_type')
    readonly_fields = ('last_sent', 'created_at')
    list_select_related = ('created_by',)
