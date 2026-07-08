from django.contrib import admin
from django.utils.html import format_html

from core.admin_visual_editor import VisualEditorAdminMixin

from .forms import BannerCarouselAdminForm, HomepageCarouselAdminForm, HomepageSettingsAdminForm
from .models import (
    BannerCarousel,
    HomepageCarousel,
    HomepageSettings,
    HomepageFeature,
    HomepageCategory,
)


@admin.action(description='Duplicate selected banners')
def duplicate_selected_banners(modeladmin, request, queryset):
    for banner in queryset:
        banner.duplicate()


@admin.register(HomepageCarousel)
class HomepageCarouselAdmin(VisualEditorAdminMixin, admin.ModelAdmin):
    form = HomepageCarouselAdminForm
    visual_editor_kind = 'homepage-carousel'
    visual_editor_title = 'Homepage Banner Preview'
    visual_editor_description = 'Preview how the homepage banner image and title will appear.'
    visual_editor_file_fields = ('image',)
    list_display = ('preview_image', 'title', 'redirect_url', 'display_order', 'is_active', 'slide_duration', 'created_at')
    list_editable = ('display_order', 'is_active', 'slide_duration')
    list_filter = ('is_active',)
    search_fields = ('title', 'redirect_url')
    ordering = ('display_order', 'created_at', 'id')
    readonly_fields = ('created_at', 'updated_at')

    fieldsets = (
        ('Media', {
            'fields': ('title', 'image', 'redirect_url'),
            'classes': ('visual-card',),
            'description': 'Manage the main homepage banner image and destination.',
        }),
        ('Display Settings', {
            'fields': ('display_order', 'is_active', 'slide_duration', 'created_at', 'updated_at'),
            'classes': ('visual-card', 'collapse', 'section-display', 'initial-open'),
            'description': 'Control order, activation, and autoplay timing.',
        }),
    )

    def preview_image(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="height:60px; width:90px; object-fit:cover; border-radius:8px; border:1px solid #eee;" />',
                obj.image.url
            )
        return 'No image'

    preview_image.short_description = 'Preview'


@admin.register(BannerCarousel)
class BannerCarouselAdmin(VisualEditorAdminMixin, admin.ModelAdmin):
    form = BannerCarouselAdminForm
    visual_editor_kind = 'hero-banner'
    visual_editor_title = 'Hero Banner Live Preview'
    visual_editor_description = 'Experiment with colors, typography, spacing, and images without leaving the admin form.'
    visual_editor_file_fields = ('image', 'background_image')
    actions = [duplicate_selected_banners]
    list_display = ('preview_image', 'heading', 'badge_text', 'display_order', 'is_active', 'slide_duration', 'views_count', 'clicks_count', 'ctr_display', 'created_at')
    list_editable = ('display_order', 'is_active', 'slide_duration')
    list_filter = ('is_active', 'layout_template', 'background_type', 'button_variant')
    search_fields = ('heading', 'badge_text', 'description', 'button_text')
    ordering = ('display_order', 'created_at', 'id')
    readonly_fields = ('created_at', 'updated_at', 'views_count', 'clicks_count', 'ctr_display')

    base_fieldsets = (
        ('Content', {
            'fields': ('image', 'badge_text', 'heading', 'description', 'button_text', 'button_url', 'layout_template'),
            'classes': ('visual-card', 'section-content'),
            'description': 'Core content that appears in the hero banner.',
        }),
        ('Visibility', {
            'fields': ('show_badge', 'show_heading', 'show_description', 'show_button', 'show_image', 'show_left_content', 'show_right_content', 'show_on_desktop', 'show_on_tablet', 'show_on_mobile'),
            'classes': ('visual-card', 'collapse', 'section-visibility', 'initial-open'),
            'description': 'Turn individual elements and breakpoints on or off.',
        }),
        ('Left Panel Content', {
            'fields': ('left_badge_text', 'left_heading', 'left_description', 'left_button_text', 'left_button_url'),
            'classes': ('visual-card', 'collapse', 'section-layout', 'initial-open'),
            'description': 'Optional content used by split layouts.',
        }),
        ('Right Panel Content', {
            'fields': ('right_badge_text', 'right_heading', 'right_description', 'right_button_text', 'right_button_url'),
            'classes': ('visual-card', 'collapse', 'section-layout', 'initial-open'),
            'description': 'Optional content used by split layouts.',
        }),
        ('Typography', {
            'fields': (
                ('badge_font_family', 'badge_font_size', 'badge_font_weight', 'badge_text_color'),
                ('heading_font_family', 'heading_font_size', 'heading_font_weight', 'heading_text_color'),
                ('description_font_family', 'description_font_size', 'description_font_weight', 'description_text_color'),
            ),
            'classes': ('visual-card', 'collapse', 'section-typography', 'initial-open'),
            'description': 'Use searchable dropdowns and visual controls instead of manual CSS typing.',
        }),
        ('Button Builder', {
            'fields': (
                'button_border_radius',
                'button_width',
                'button_height',
                'button_padding',
                ('button_font_family', 'button_font_size', 'button_font_weight'),
                ('button_text_color', 'button_background_color', 'button_border_color'),
                ('button_hover_background_color', 'button_hover_text_color', 'button_hover_border_color'),
                'button_hover_shadow',
                'button_variant',
            ),
            'classes': ('visual-card', 'collapse', 'section-buttons', 'initial-open'),
            'description': 'Build CTA styles visually with synced pickers, sliders, and previews.',
        }),
        ('Images & Background', {
            'fields': ('background_type', 'background_color', 'background_gradient_color_1', 'background_gradient_color_2', 'background_gradient_direction', 'background_image', 'background_position', 'background_size', 'background_repeat', 'enable_overlay'),
            'classes': ('visual-card', 'collapse', 'section-images', 'initial-open'),
            'description': 'Control banner images, gradients, positioning, and responsive background behavior.',
        }),
        ('Animation', {
            'fields': ('badge_animation', 'heading_animation', 'description_animation', 'button_animation', 'image_animation', 'animation_duration', 'animation_delay'),
            'classes': ('visual-card', 'collapse', 'section-animation'),
            'description': 'Keep motion subtle while controlling duration and delay visually.',
        }),
        ('Marketing Analytics', {
            'fields': ('views_count', 'clicks_count', 'ctr_display'),
            'classes': ('visual-card', 'collapse', 'section-analytics'),
            'description': 'Read-only performance stats for this banner.',
        }),
        ('Display Settings', {
            'fields': ('display_order', 'is_active', 'slide_duration', 'created_at', 'updated_at'),
            'classes': ('visual-card', 'collapse', 'section-display'),
            'description': 'Publishing controls and banner lifecycle metadata.',
        }),
    )

    overlay_fieldset = (
        'Overlay Settings',
        {
            'fields': ('background_overlay_color', 'background_overlay_opacity'),
            'classes': ('visual-card', 'collapse', 'section-overlay', 'initial-open'),
            'description': 'Fine-tune overlay tint and opacity when overlay is enabled.',
        },
    )

    def get_fieldsets(self, request, obj=None):
        fieldsets = list(self.base_fieldsets)
        if obj is None or obj.enable_overlay:
            insert_index = 6
            fieldsets.insert(insert_index, self.overlay_fieldset)
        return fieldsets

    def preview_image(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="height:60px; width:90px; object-fit:cover; border-radius:8px; border:1px solid #eee;" />',
                obj.image.url
            )
        return 'No image'

    preview_image.short_description = 'Preview'


@admin.register(HomepageSettings)
class HomepageSettingsAdmin(VisualEditorAdminMixin, admin.ModelAdmin):
    form = HomepageSettingsAdminForm
    visual_editor_kind = 'homepage-settings'
    visual_editor_title = 'Homepage Appearance Preview'
    visual_editor_description = 'Preview hero copy, badge, CTA, and appearance colors while editing homepage settings.'
    visual_editor_file_fields = ('hero_image', 'promo_image')
    list_display = (
        'hero_heading',
        'hero_button_text',
        'hero_color_preview',
        'promo_color_preview',
        'updated_at',
    )
    readonly_fields = ('updated_at', 'hero_image_preview', 'promo_image_preview')

    fieldsets = (
        ('Section Visibility', {
            'fields': (
                'show_top_brands',
                'show_categories',
            ),
            'classes': ('visual-card', 'section-visibility'),
            'description': 'Quickly control which homepage sections are visible.',
        }),
        ('Hero Section', {
            'fields': (
                'hero_badge_text',
                'hero_heading',
                'hero_subheading',
                'hero_button_text',
                'hero_button_link',
                'hero_image',
                'hero_image_preview',
                'hero_background_color',
            ),
            'classes': ('visual-card', 'section-content'),
            'description': 'Primary hero content, image, CTA, and hero background styling.',
        }),
        ('Promotional Yellow Banner', {
            'fields': (
                'promo_small_text',
                'promo_main_heading',
                'promo_tagline',
                'promo_developer_name',
                'promo_email',
                'promo_contact_number',
                'promo_image',
                'promo_image_preview',
                'promo_background_color',
            ),
            'classes': ('visual-card', 'collapse', 'section-content', 'initial-open'),
            'description': 'Secondary promotional strip content and background styling.',
        }),
        ('System', {
            'fields': ('updated_at',),
            'classes': ('visual-card', 'collapse', 'section-display'),
        })
    )

    def has_add_permission(self, request):
        return not HomepageSettings.objects.exists()

    def hero_image_preview(self, obj):
        if obj.hero_image:
            return format_html(
                '<img src="{}" style="height:72px; width:110px; object-fit:cover; border-radius:10px;" />',
                obj.hero_image.url
            )
        return "No image uploaded"

    def promo_image_preview(self, obj):
        if obj.promo_image:
            return format_html(
                '<img src="{}" style="height:72px; width:110px; object-fit:cover; border-radius:10px;" />',
                obj.promo_image.url
            )
        return "No image uploaded"

    def hero_color_preview(self, obj):
        return format_html(
            '<span style="display:inline-block;width:24px;height:24px;border-radius:6px;'
            'background:{};border:1px solid #d0d5dd;"></span> <code>{}</code>',
            obj.hero_background_color,
            obj.hero_background_color,
        )

    def promo_color_preview(self, obj):
        return format_html(
            '<span style="display:inline-block;width:24px;height:24px;border-radius:6px;'
            'background:{};border:1px solid #d0d5dd;"></span> <code>{}</code>',
            obj.promo_background_color,
            obj.promo_background_color,
        )


@admin.register(HomepageFeature)
class HomepageFeatureAdmin(admin.ModelAdmin):
    list_display = ('icon_preview', 'title', 'description', 'display_order', 'is_active')
    list_editable = ('display_order', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('title', 'description')
    ordering = ('display_order', 'id')

    fieldsets = (
        ('Feature Details', {
            'fields': ('icon', 'title', 'description'),
        }),
        ('Display', {
            'fields': ('display_order', 'is_active'),
        }),
    )

    def icon_preview(self, obj):
        return format_html(
            '<i class="bi {}" style="font-size:20px; color:#ffb800;"></i> '
            '<span style="font-size:12px; color:#555;">{}</span>',
            obj.icon, obj.icon
        )
    icon_preview.short_description = 'Preview'


@admin.register(HomepageCategory)
class HomepageCategoryAdmin(admin.ModelAdmin):
    list_display = (
        'preview_image',
        'name',
        'linked_category',
        'display_order',
        'is_active',
    )
    list_editable = ('display_order', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'linked_category__name')
    ordering = ('display_order', 'id')

    fieldsets = (
        ('Category Info', {
            'fields': ('name', 'image', 'linked_category'),
        }),
        ('Display', {
            'fields': ('display_order', 'is_active'),
        }),
    )

    def preview_image(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="height:55px; width:55px; '
                'object-fit:cover; border-radius:50%; border:2px solid #eee;" />',
                obj.image.url
            )
        return format_html(
            '<div style="height:55px; width:55px; border-radius:50%; '
            'background:#f0f0f0; display:flex; align-items:center; '
            'justify-content:center; font-size:22px;">📦</div>{}', ''
        )
    preview_image.short_description = 'Preview'
