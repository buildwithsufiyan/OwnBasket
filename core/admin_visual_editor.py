import json
from urllib.parse import quote_plus

from django import forms
from django.forms.widgets import NumberInput, Select, TextInput
from django.urls import reverse


FONT_FAMILY_NAMES = [
    'Inter',
    'Poppins',
    'Montserrat',
    'Roboto',
    'Open Sans',
    'Lato',
    'Nunito',
    'DM Sans',
    'Manrope',
    'Work Sans',
    'Outfit',
    'Plus Jakarta Sans',
    'Urbanist',
    'Sora',
    'Figtree',
    'Public Sans',
    'Space Grotesk',
    'Mulish',
    'Rubik',
    'Quicksand',
    'Raleway',
    'League Spartan',
    'Barlow',
    'Barlow Condensed',
    'Karla',
    'Cabin',
    'Assistant',
    'Heebo',
    'Hind',
    'IBM Plex Sans',
    'Libre Franklin',
    'Playfair Display',
    'Merriweather',
    'Cormorant Garamond',
    'Libre Baskerville',
    'Bebas Neue',
    'Anton',
    'Oswald',
    'Abril Fatface',
    'Pacifico',
    'Lobster',
    'Dancing Script',
    'Caveat',
    'Great Vibes',
    'Fredoka',
    'Comfortaa',
    'Josefin Sans',
    'Exo 2',
    'Teko',
    'Titillium Web',
    'Varela Round',
]

FONT_FAMILY_CHOICES = [(font_name, font_name) for font_name in FONT_FAMILY_NAMES]


def get_google_fonts_url(font_families=None):
    families = font_families or FONT_FAMILY_NAMES
    family_query = '&'.join(
        f"family={quote_plus(font_name)}"
        for font_name in families
    )
    return f"https://fonts.googleapis.com/css2?{family_query}&display=swap"

FONT_WEIGHT_CHOICES = [
    ('100', '100 Thin'),
    ('200', '200 Extra Light'),
    ('300', '300 Light'),
    ('400', '400 Regular'),
    ('500', '500 Medium'),
    ('600', '600 Semi Bold'),
    ('700', '700 Bold'),
    ('800', '800 Extra Bold'),
    ('900', '900 Black'),
]

CSS_UNIT_CHOICES = [
    ('px', 'px'),
    ('rem', 'rem'),
    ('em', 'em'),
    ('%', '%'),
    ('vw', 'vw'),
    ('vh', 'vh'),
]

IMAGE_POSITION_CHOICES = [
    ('center center', 'Center'),
    ('center top', 'Top'),
    ('center bottom', 'Bottom'),
    ('left center', 'Left'),
    ('right center', 'Right'),
]

BACKGROUND_SIZE_CHOICES = [
    ('cover', 'Cover'),
    ('contain', 'Contain'),
    ('auto', 'Auto'),
]

BACKGROUND_REPEAT_CHOICES = [
    ('no-repeat', 'No Repeat'),
    ('repeat', 'Repeat'),
    ('repeat-x', 'Repeat X'),
    ('repeat-y', 'Repeat Y'),
]

DIMENSION_PRESET_CHOICES = [
    ('auto', 'Auto'),
    ('100%', '100%'),
    ('fit-content', 'Fit Content'),
    ('custom', 'Custom'),
]


def _merge_css_classes(existing, new_class):
    class_names = [value for value in (existing or '').split() if value]
    if new_class not in class_names:
        class_names.append(new_class)
    return ' '.join(class_names)


class VisualEditorMediaMixin:
    class Media:
        css = {
            'all': ('admin/ownbasket_visual_editor.css',),
        }
        js = ('admin/ownbasket_visual_editor.js',)


class VisualEditorFormMixin(VisualEditorMediaMixin):
    default_input_class = 've-input'

    def apply_widget_class(self, field_name, css_class):
        field = self.fields.get(field_name)
        if field is None:
            return
        field.widget.attrs['class'] = _merge_css_classes(
            field.widget.attrs.get('class', ''),
            css_class,
        )

    def set_placeholder(self, field_name, placeholder):
        field = self.fields.get(field_name)
        if field is not None:
            field.widget.attrs['placeholder'] = placeholder

    def set_help_text(self, field_name, help_text):
        field = self.fields.get(field_name)
        if field is not None:
            field.help_text = help_text

    def apply_base_input_style(self):
        for field in self.fields.values():
            widget = field.widget
            widget.attrs['class'] = _merge_css_classes(
                widget.attrs.get('class', ''),
                self.default_input_class,
            )


class VisualEditorAdminMixin:
    change_form_template = 'admin/visual_editor_change_form.html'
    visual_editor_kind = 'generic'
    visual_editor_title = 'Live Preview'
    visual_editor_description = 'Changes appear here instantly while you edit settings.'
    visual_editor_file_fields = ()

    def get_visual_editor_file_urls(self, obj=None):
        file_urls = {}
        if obj is None:
            return file_urls

        for field_name in self.visual_editor_file_fields:
            file_value = getattr(obj, field_name, None)
            if not file_value or not getattr(file_value, 'name', ''):
                file_urls[field_name] = ''
                continue
            try:
                file_urls[field_name] = file_value.url
            except ValueError:
                file_urls[field_name] = ''
        return file_urls

    def render_change_form(self, request, context, add=False, change=False, form_url='', obj=None):
        context['visual_editor_enabled'] = True
        context['visual_editor_kind'] = self.visual_editor_kind
        context['visual_editor_title'] = self.visual_editor_title
        context['visual_editor_description'] = self.visual_editor_description
        context['visual_editor_file_urls_json'] = json.dumps(self.get_visual_editor_file_urls(obj))
        context['live_preview_url'] = reverse('home')
        context['live_preview_title'] = self.visual_editor_title
        context['live_preview_update_session_url'] = ''
        return super().render_change_form(request, context, add, change, form_url, obj)


class ColorPickerTextInput(TextInput):
    def __init__(self, attrs=None):
        attrs = attrs or {}
        attrs['class'] = _merge_css_classes(attrs.get('class', ''), 've-color-source')
        super().__init__(attrs=attrs)


class SearchableSelect(Select):
    def __init__(self, attrs=None, choices=(), font_preview=False):
        attrs = attrs or {}
        attrs['class'] = _merge_css_classes(attrs.get('class', ''), 've-searchable-select')
        attrs.setdefault('data-dropdown', 'native-select')
        if font_preview:
            attrs['data-font-preview'] = 'true'
        super().__init__(attrs=attrs, choices=choices)


class RangeNumberInput(NumberInput):
    def __init__(self, attrs=None):
        attrs = attrs or {}
        attrs['class'] = _merge_css_classes(attrs.get('class', ''), 've-range-sync')
        super().__init__(attrs=attrs)


class CssSizeInput(TextInput):
    def __init__(self, attrs=None):
        attrs = attrs or {}
        attrs['class'] = _merge_css_classes(attrs.get('class', ''), 've-css-size')
        super().__init__(attrs=attrs)


class CssPaddingInput(TextInput):
    def __init__(self, attrs=None):
        attrs = attrs or {}
        attrs['class'] = _merge_css_classes(attrs.get('class', ''), 've-css-padding')
        super().__init__(attrs=attrs)


class DimensionOptionInput(TextInput):
    def __init__(self, attrs=None):
        attrs = attrs or {}
        attrs['class'] = _merge_css_classes(attrs.get('class', ''), 've-dimension-input')
        super().__init__(attrs=attrs)
