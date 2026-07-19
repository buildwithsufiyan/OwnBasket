from django.contrib import admin

from .models import Wishlist, WishlistCollection, WishlistSettings


@admin.register(WishlistCollection)
class WishlistCollectionAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'is_public', 'created_at')
    list_filter = ('is_public', 'created_at')
    search_fields = ('name', 'user__username', 'user__email')
    readonly_fields = ('share_token', 'created_at')


@admin.register(Wishlist)
class WishlistAdmin(admin.ModelAdmin):
    list_display = ('product', 'user', 'collection', 'saved_for_later', 'price_at_add', 'created_at')
    list_filter = ('saved_for_later', 'created_at')
    search_fields = ('product__name', 'user__username', 'collection__name')
    list_select_related = ('product', 'user', 'collection')


@admin.register(WishlistSettings)
class WishlistSettingsAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return not WishlistSettings.objects.exists()
