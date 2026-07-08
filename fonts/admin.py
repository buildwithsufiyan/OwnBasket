from django.contrib import admin
from django.db.models import Q
from django.utils.html import format_html

from .forms import ManagedFontAdminForm
from .models import ManagedFont, ManagedFontPack, ManagedFontPackFont
from django.utils.safestring import mark_safe


@admin.action(description='Activate selected fonts')
def activate_fonts(modeladmin, request, queryset):
    valid_fonts = queryset.filter(
        Q(source='google') |
        (Q(source='upload') & ~Q(font_file='') & Q(font_file__isnull=False))
    )
    activated_count = valid_fonts.update(is_active=True)
    skipped_count = queryset.count() - activated_count
    if skipped_count:
        modeladmin.message_user(
            request,
            f'{activated_count} font(s) activated. {skipped_count} uploaded font(s) skipped because they do not have a file yet.',
        )


@admin.action(description='Deactivate selected fonts')
def deactivate_fonts(modeladmin, request, queryset):
    queryset.update(is_active=False)


@admin.action(description='Activate selected font packs')
def activate_font_packs(modeladmin, request, queryset):
    queryset.update(is_active=True)


@admin.action(description='Deactivate selected font packs')
def deactivate_font_packs(modeladmin, request, queryset):
    queryset.update(is_active=False)


class ManagedFontPackFontInline(admin.TabularInline):
    model = ManagedFontPackFont
    extra = 1
    autocomplete_fields = ('font',)
    fields = ('font', 'sort_order')
    ordering = ('sort_order', 'id')


class ManagedFontPackInline(admin.TabularInline):
    model = ManagedFontPackFont
    extra = 0
    autocomplete_fields = ('pack',)
    fields = ('pack', 'sort_order')
    ordering = ('sort_order', 'id')


@admin.register(ManagedFont)
class ManagedFontAdmin(admin.ModelAdmin):
    form = ManagedFontAdminForm
    actions = [activate_fonts, deactivate_fonts]
    inlines = [ManagedFontPackInline]
    list_display = (
        'preview_card',
        'name',
        'css_name',
        'source',
        'category',
        'pack_summary',
        'file_type',
        'is_active',
        'sort_order',
        'updated_at',
    )
    list_filter = ('is_active', 'category')
    list_editable = ('is_active', 'sort_order')
    search_fields = ('name', 'css_name')
    ordering = ('sort_order', 'name', 'id')
    list_per_page = 20
    readonly_fields = ('font_preview_panel', 'created_at', 'updated_at')

    fieldsets = (
        ('Font Library', {
            'fields': (
                ('name', 'css_name'),
                ('source', 'category', 'is_active'),
                ('google_family', 'style_label'),
                'font_file',
                'preview_image',
                'font_preview_panel',
            ),
            'description': 'Upload and manage reusable fonts for banners and design tools.',
        }),
        ('Publishing', {
            'fields': (
                'sort_order',
                'created_at',
                'updated_at',
            ),
        }),
    )

    def preview_card(self, obj):
        preview_image = ''
        if obj.preview_image:
            preview_image = format_html(
                '<img src="{}" alt="" style="width:52px;height:52px;border-radius:12px;object-fit:cover;border:1px solid #eaecf0;" />',
                obj.preview_image.url,
            )
        else:
            preview_image = mark_safe(
    '<div style="width:52px;height:52px;border-radius:12px;border:1px solid #eaecf0;'
    'display:flex;align-items:center;justify-content:center;'
    'background:#f8fafc;color:#667085;font-weight:700;">Aa</div>'
)

        badge_color = '#039855' if obj.is_active else '#98a2b3'
        badge_label = 'Active' if obj.is_active else 'Inactive'
        return format_html(
            '<div style="display:flex;align-items:center;gap:10px;min-width:220px;">'
            '{}'
            '<div>'
            '<div style="font-weight:700;color:#101828;">{}</div>'
            '<div style="font-size:12px;color:#667085;">{}</div>'
            '<div style="margin-top:4px;display:inline-flex;padding:2px 8px;border-radius:999px;'
            'background:{};color:#fff;font-size:11px;font-weight:700;">{}</div>'
            '</div>'
            '</div>',
            preview_image,
            obj.name,
            obj.css_name,
            badge_color,
            badge_label,
        )

    preview_card.short_description = 'Preview'

    def file_type(self, obj):
        if obj.source == 'google':
            return 'Google'
        return obj.file_extension.upper() if obj.file_extension else 'No file'

    file_type.short_description = 'File'

    def pack_summary(self, obj):
        pack_names = list(obj.packs.order_by('group', 'sort_order', 'name').values_list('name', flat=True)[:4])
        if not pack_names:
            return 'No packs'
        suffix = ' +' if obj.packs.count() > 4 else ''
        return ', '.join(pack_names) + suffix

    pack_summary.short_description = 'Packs'

    def font_preview_panel(self, obj):
        if not obj.pk:
            return 'Save the font to see the preview panel.'

        sample_style = f"font-family:'{obj.css_name}', sans-serif;"
        image_markup = ''
        if obj.preview_image:
            image_markup = format_html(
                '<img src="{}" alt="" style="width:100%;max-width:220px;border-radius:14px;object-fit:cover;'
                'border:1px solid #eaecf0;margin-top:12px;" />',
                obj.preview_image.url,
            )

        return format_html(
            '<div style="padding:18px;border:1px solid #eaecf0;border-radius:16px;background:#fff;">'
            '<div style="display:flex;align-items:center;justify-content:space-between;gap:12px;">'
            '<div>'
            '<div style="font-size:12px;font-weight:800;letter-spacing:.04em;text-transform:uppercase;color:#9a6b00;">Font Preview</div>'
            '<div style="margin-top:4px;font-size:13px;color:#667085;">{}</div>'
            '</div>'
            '<div style="font-size:12px;color:#667085;">{}</div>'
            '</div>'
            '<div style="margin-top:16px;font-size:32px;line-height:1.1;color:#101828;{}">Aa Bb Cc 123</div>'
            '<div style="margin-top:10px;font-size:16px;color:#344054;{}">OwnBasket premium sale banner</div>'
            '{}'
            '</div>',
            obj.get_category_display(),
            'File ready' if obj.font_file else 'Upload required',
            sample_style,
            sample_style,
            image_markup,
        )

    font_preview_panel.short_description = 'Preview Card'


@admin.register(ManagedFontPack)
class ManagedFontPackAdmin(admin.ModelAdmin):
    actions = [activate_font_packs, deactivate_font_packs]
    inlines = [ManagedFontPackFontInline]
    list_display = ('name', 'group', 'font_count', 'is_active', 'sort_order', 'updated_at')
    list_filter = ('group', 'is_active')
    list_editable = ('is_active', 'sort_order')
    search_fields = ('name', 'slug', 'description')
    ordering = ('group', 'sort_order', 'name', 'id')
    list_per_page = 20
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        ('Pack Details', {
            'fields': (
                ('name', 'slug'),
                ('group', 'is_active'),
                'description',
            ),
            'description': 'Create recommended font collections without changing the core font dropdown.',
        }),
        ('Publishing', {
            'fields': (
                'sort_order',
                'created_at',
                'updated_at',
            ),
        }),
    )

    def font_count(self, obj):
        return obj.fonts.count()

    font_count.short_description = 'Fonts'
