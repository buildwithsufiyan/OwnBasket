from django.contrib import admin

from .models import BehaviorEvent, SearchSynonym


@admin.register(BehaviorEvent)
class BehaviorEventAdmin(admin.ModelAdmin):
    list_display = ('event_type', 'user', 'product', 'category', 'brand', 'created_at')
    list_filter = ('event_type', 'created_at')
    search_fields = ('product__name', 'category__name', 'brand__name', 'search_term')
    readonly_fields = tuple(field.name for field in BehaviorEvent._meta.fields)
    date_hierarchy = 'created_at'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(SearchSynonym)
class SearchSynonymAdmin(admin.ModelAdmin):
    list_display = ('canonical_term', 'is_active', 'updated_at')
    list_filter = ('is_active',)
    search_fields = ('canonical_term',)
