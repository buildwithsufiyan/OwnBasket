from django import forms

from core.admin_visual_editor import (
    BACKGROUND_REPEAT_CHOICES,
    BACKGROUND_SIZE_CHOICES,
    CSS_UNIT_CHOICES,
    DIMENSION_PRESET_CHOICES,
    FONT_WEIGHT_CHOICES,
    IMAGE_POSITION_CHOICES,
    ColorPickerTextInput,
    CssPaddingInput,
    CssSizeInput,
    DimensionOptionInput,
    RangeNumberInput,
    SearchableSelect,
    VisualEditorFormMixin,
)
from fonts.services import (
    get_active_font_entries,
    get_designer_font_library_entries,
    get_font_pack_entries,
)
from fonts.widgets import FontPickerSelect

from .models import BannerCarousel, HomepageCarousel, HomepageSettings


class HomepageCarouselAdminForm(VisualEditorFormMixin, forms.ModelForm):
    class Meta:
        model = HomepageCarousel
        fields = '__all__'
        widgets = {
            'title': forms.TextInput(attrs={'placeholder': 'Optional homepage banner title'}),
            'redirect_url': forms.URLInput(attrs={'placeholder': 'https://example.com/offer'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_base_input_style()
        help_texts = {
            'title': 'Short label used for the homepage banner preview.',
            'image': 'Upload the visual that should appear in the homepage banner.',
            'redirect_url': 'Optional link that opens when the visitor clicks the banner.',
            'display_order': 'Lower numbers appear first in the carousel.',
            'slide_duration': 'Autoplay duration in milliseconds.',
            'is_active': 'Only active homepage banners appear on the storefront.',
        }
        for field_name, help_text in help_texts.items():
            self.set_help_text(field_name, help_text)


class BannerCarouselAdminForm(VisualEditorFormMixin, forms.ModelForm):
    badge_font_family = forms.ChoiceField(
        choices=(),
        widget=FontPickerSelect(),
        required=False,
    )
    heading_font_family = forms.ChoiceField(
        choices=(),
        widget=FontPickerSelect(),
        required=False,
    )
    description_font_family = forms.ChoiceField(
        choices=(),
        widget=FontPickerSelect(),
        required=False,
    )
    button_font_family = forms.ChoiceField(
        choices=(),
        widget=FontPickerSelect(),
        required=False,
    )
    badge_font_weight = forms.ChoiceField(
        choices=FONT_WEIGHT_CHOICES,
        widget=SearchableSelect(),
        required=False,
    )
    heading_font_weight = forms.ChoiceField(
        choices=FONT_WEIGHT_CHOICES,
        widget=SearchableSelect(),
        required=False,
    )
    description_font_weight = forms.ChoiceField(
        choices=FONT_WEIGHT_CHOICES,
        widget=SearchableSelect(),
        required=False,
    )
    button_font_weight = forms.ChoiceField(
        choices=FONT_WEIGHT_CHOICES,
        widget=SearchableSelect(),
        required=False,
    )
    background_position = forms.ChoiceField(
        choices=IMAGE_POSITION_CHOICES,
        widget=SearchableSelect(),
        required=False,
    )
    background_size = forms.ChoiceField(
        choices=BACKGROUND_SIZE_CHOICES,
        widget=SearchableSelect(),
        required=False,
    )
    background_repeat = forms.ChoiceField(
        choices=BACKGROUND_REPEAT_CHOICES,
        widget=SearchableSelect(),
        required=False,
    )

    class Meta:
        model = BannerCarousel
        fields = '__all__'
        widgets = {
            'badge_text_color': ColorPickerTextInput(),
            'heading_text_color': ColorPickerTextInput(),
            'description_text_color': ColorPickerTextInput(),
            'button_text_color': ColorPickerTextInput(),
            'button_background_color': ColorPickerTextInput(),
            'button_border_color': ColorPickerTextInput(),
            'button_hover_background_color': ColorPickerTextInput(),
            'button_hover_text_color': ColorPickerTextInput(),
            'button_hover_border_color': ColorPickerTextInput(),
            'background_color': ColorPickerTextInput(),
            'background_gradient_color_1': ColorPickerTextInput(),
            'background_gradient_color_2': ColorPickerTextInput(),
            'background_overlay_color': ColorPickerTextInput(),
            'badge_font_size': CssSizeInput(),
            'heading_font_size': CssSizeInput(),
            'description_font_size': CssSizeInput(),
            'button_font_size': CssSizeInput(),
            'button_width': DimensionOptionInput(),
            'button_height': DimensionOptionInput(),
            'button_padding': CssPaddingInput(),
            'button_border_radius': RangeNumberInput(attrs={'min': 0, 'max': 48, 'step': 1}),
            'animation_duration': RangeNumberInput(attrs={'min': 0, 'max': 3000, 'step': 50}),
            'animation_delay': RangeNumberInput(attrs={'min': 0, 'max': 2000, 'step': 50}),
            'background_overlay_opacity': RangeNumberInput(attrs={'min': 0, 'max': 1, 'step': 0.05}),
            'display_order': RangeNumberInput(attrs={'min': 0, 'max': 50, 'step': 1}),
            'slide_duration': RangeNumberInput(attrs={'min': 1000, 'max': 15000, 'step': 500}),
            'heading': forms.TextInput(attrs={'placeholder': 'Main hero heading'}),
            'description': forms.TextInput(attrs={'placeholder': 'Short supporting copy for the banner'}),
            'button_text': forms.TextInput(attrs={'placeholder': 'Primary CTA label'}),
            'button_url': forms.URLInput(attrs={'placeholder': 'https://example.com/shop'}),
            'badge_text': forms.TextInput(attrs={'placeholder': 'Optional badge label'}),
            'left_heading': forms.TextInput(attrs={'placeholder': 'Left heading'}),
            'left_description': forms.TextInput(attrs={'placeholder': 'Left description'}),
            'left_button_text': forms.TextInput(attrs={'placeholder': 'Left button text'}),
            'left_button_url': forms.URLInput(attrs={'placeholder': 'https://example.com/left'}),
            'right_heading': forms.TextInput(attrs={'placeholder': 'Right heading'}),
            'right_description': forms.TextInput(attrs={'placeholder': 'Right description'}),
            'right_button_text': forms.TextInput(attrs={'placeholder': 'Right button text'}),
            'right_button_url': forms.URLInput(attrs={'placeholder': 'https://example.com/right'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_base_input_style()
        self.apply_widget_class('layout_template', 've-searchable-select')
        if 'layout_template' in self.fields:
            self.fields['layout_template'].widget.attrs['data-dropdown'] = 'banner-layout'
        self.apply_widget_class('background_type', 've-searchable-select')
        self.apply_widget_class('background_gradient_direction', 've-searchable-select')
        self.apply_widget_class('button_variant', 've-searchable-select')
        self.apply_widget_class('badge_animation', 've-searchable-select')
        self.apply_widget_class('heading_animation', 've-searchable-select')
        self.apply_widget_class('description_animation', 've-searchable-select')
        self.apply_widget_class('button_animation', 've-searchable-select')
        self.apply_widget_class('image_animation', 've-searchable-select')
        self.configure_font_picker_fields()

        for field_name in (
            'badge_font_size',
            'heading_font_size',
            'description_font_size',
            'button_font_size',
        ):
            field = self.fields.get(field_name)
            if field is not None:
                field.widget.attrs['data-unit-options'] = ','.join(unit for unit, _ in CSS_UNIT_CHOICES)

        for field_name in ('button_width', 'button_height'):
            field = self.fields.get(field_name)
            if field is not None:
                field.widget.attrs['data-dimension-presets'] = ','.join(
                    value for value, _ in DIMENSION_PRESET_CHOICES
                )

        help_texts = {
            'badge_font_family': 'This font family is used for the banner badge.',
            'heading_font_family': 'This font family is used for the main hero heading.',
            'description_font_family': 'This font family is used for the supporting description.',
            'button_font_family': 'This font family is used for the CTA button label.',
            'badge_text_color': 'This color is used for the banner badge text.',
            'heading_text_color': 'This color is used for the main heading.',
            'description_text_color': 'This color is used for the supporting description.',
            'button_background_color': 'Primary button background color.',
            'button_text_color': 'Primary button text color.',
            'button_border_color': 'Primary button border color.',
            'button_hover_background_color': 'Button background color on hover.',
            'button_hover_text_color': 'Button text color on hover.',
            'button_hover_border_color': 'Button border color on hover.',
            'background_overlay_color': 'Overlay tint color placed above the background image.',
            'background_color': 'Fallback solid background for the hero banner.',
            'badge_font_size': 'Use a visual size builder or switch to advanced mode for clamp() and calc().',
            'heading_font_size': 'Use the size builder for standard units or advanced mode for clamp() values.',
            'description_font_size': 'Use the size builder for standard units or advanced mode for calc() values.',
            'button_font_size': 'This controls the CTA font size.',
            'button_border_radius': 'Higher values create more rounded buttons.',
            'button_width': 'Choose a preset width or switch to custom CSS values.',
            'button_height': 'Choose a preset height or switch to custom CSS values.',
            'button_padding': 'Adjust button padding visually instead of typing CSS shorthand.',
            'background_position': 'Controls how the background image is positioned inside the banner.',
            'background_size': 'Controls how the background image scales.',
            'background_repeat': 'Choose whether the background image repeats.',
            'background_overlay_opacity': 'Lower values keep the image more visible.',
            'animation_duration': 'Animation timing in milliseconds.',
            'animation_delay': 'Delay before animation starts in milliseconds.',
        }
        for field_name, help_text in help_texts.items():
            self.set_help_text(field_name, help_text)

    def configure_font_picker_fields(self):
        field_names = (
            'badge_font_family',
            'heading_font_family',
            'description_font_family',
            'button_font_family',
        )
        current_values = [
            getattr(self.instance, field_name, '')
            for field_name in field_names
            if getattr(self.instance, field_name, '')
        ]
        entries = get_active_font_entries(current_values=current_values)
        font_packs = get_font_pack_entries()
        designer_font_libraries = get_designer_font_library_entries()
        choices = [(entry['css_name'], entry['name']) for entry in entries]

        for field_name in field_names:
            field = self.fields.get(field_name)
            if field is None:
                continue
            field.choices = choices
            if hasattr(field.widget, 'set_font_entries'):
                field.widget.set_font_entries(entries)
            if hasattr(field.widget, 'set_font_packs'):
                field.widget.set_font_packs(font_packs)
            if hasattr(field.widget, 'set_designer_font_libraries'):
                field.widget.set_designer_font_libraries(designer_font_libraries)


class HomepageSettingsAdminForm(VisualEditorFormMixin, forms.ModelForm):
    class Meta:
        model = HomepageSettings
        fields = '__all__'
        widgets = {
            'hero_background_color': ColorPickerTextInput(),
            'promo_background_color': ColorPickerTextInput(),
            'hero_badge_text': forms.TextInput(attrs={'placeholder': 'Short badge text'}),
            'hero_heading': forms.TextInput(attrs={'placeholder': 'Main hero heading'}),
            'hero_subheading': forms.TextInput(attrs={'placeholder': 'Supporting hero copy'}),
            'hero_button_text': forms.TextInput(attrs={'placeholder': 'Primary CTA label'}),
            'hero_button_link': forms.TextInput(attrs={'placeholder': '/products/ or https://example.com'}),
            'promo_small_text': forms.TextInput(attrs={'placeholder': 'Small promo eyebrow'}),
            'promo_main_heading': forms.TextInput(attrs={'placeholder': 'Main promo heading'}),
            'promo_tagline': forms.TextInput(attrs={'placeholder': 'Optional promo tagline'}),
            'promo_developer_name': forms.TextInput(attrs={'placeholder': 'Optional highlight label'}),
            'promo_contact_number': forms.TextInput(attrs={'placeholder': '+92 ...'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_base_input_style()
        help_texts = {
            'hero_background_color': 'This color is used behind the homepage hero content.',
            'promo_background_color': 'This color is used behind the promotional banner.',
            'hero_image': 'Upload the hero visual that appears in the homepage banner.',
            'promo_image': 'Upload the right-side promotional image.',
            'hero_button_link': 'Leave blank to fall back to the homepage route.',
            'show_top_brands': 'Enable or hide the Top Brands section on the homepage.',
            'show_categories': 'Enable or hide the Categories section on the homepage.',
        }
        for field_name, help_text in help_texts.items():
            self.set_help_text(field_name, help_text)
