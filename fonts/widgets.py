import json

from django.urls import reverse

from core.admin_visual_editor import SearchableSelect


class FontPickerSelect(SearchableSelect):
    def __init__(self, attrs=None, choices=()):
        super().__init__(attrs=attrs, choices=choices, font_preview=True)
        self.font_entries = []
        self.font_packs = []
        self.designer_font_libraries = []

    def set_font_entries(self, entries):
        self.font_entries = entries

    def set_font_packs(self, packs):
        self.font_packs = packs

    def set_designer_font_libraries(self, libraries):
        self.designer_font_libraries = libraries

    def get_context(self, name, value, attrs):
        context = super().get_context(name, value, attrs)
        widget_attrs = context['widget']['attrs']
        widget_attrs['data-dropdown'] = 'font-picker'
        widget_attrs['data-font-picker'] = 'true'
        widget_attrs['data-font-options'] = json.dumps(self.font_entries)
        widget_attrs['data-font-packs'] = json.dumps(self.font_packs)
        widget_attrs['data-designer-font-libraries'] = json.dumps(self.designer_font_libraries)
        widget_attrs['data-font-recent-key'] = 'ownbasket-recent-fonts'
        widget_attrs['data-font-favorites-key'] = 'ownbasket-favorite-fonts'
        widget_attrs['data-font-api-url'] = reverse('fonts:active-fonts-api')
        return context
