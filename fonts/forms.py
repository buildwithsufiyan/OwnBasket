from django import forms

from .models import FONT_FILE_EXTENSIONS, ManagedFont


class ManagedFontAdminForm(forms.ModelForm):
    class Meta:
        model = ManagedFont
        fields = '__all__'
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'Example: Brittany'}),
            'css_name': forms.TextInput(attrs={'placeholder': 'Example: Brittany'}),
            'google_family': forms.TextInput(attrs={'placeholder': 'Example: Plus Jakarta Sans'}),
            'style_label': forms.TextInput(attrs={'placeholder': 'Example: Modern Sans Serif'}),
            'font_file': forms.ClearableFileInput(attrs={
                'class': 'font-dropzone-input',
                'accept': '.ttf,.otf,.woff,.woff2',
            }),
            'preview_image': forms.ClearableFileInput(attrs={
                'class': 'font-dropzone-input',
                'accept': 'image/*',
            }),
        }

    class Media:
        css = {
            'all': ('admin/font_manager.css',),
        }
        js = ('admin/font_manager.js',)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['font_file'].help_text = (
            'Upload .ttf, .otf, .woff, or .woff2. WOFF2 is preferred for the fastest delivery.'
        )
        self.fields['preview_image'].help_text = (
            'Optional preview image for the library card.'
        )
        self.fields['css_name'].help_text = (
            'The exact value used in CSS font-family declarations.'
        )
        self.fields['source'].help_text = (
            'Use Google Font for dynamic Google Fonts loading, or Uploaded Font for custom files.'
        )
        self.fields['google_family'].help_text = (
            'Used only for Google Font source. Leave blank to reuse CSS Font Family Name.'
        )
        self.fields['style_label'].help_text = (
            'Short descriptor shown below the font name in the typography picker.'
        )
        self.fields['sort_order'].help_text = 'Lower numbers appear first in the picker.'

    def clean_name(self):
        name = (self.cleaned_data.get('name') or '').strip()
        if ManagedFont.objects.exclude(pk=self.instance.pk).filter(name__iexact=name).exists():
            raise forms.ValidationError('A font with this name already exists.')
        return name

    def clean_css_name(self):
        css_name = (self.cleaned_data.get('css_name') or self.cleaned_data.get('name') or '').strip()
        if ManagedFont.objects.exclude(pk=self.instance.pk).filter(css_name__iexact=css_name).exists():
            raise forms.ValidationError('A font with this CSS font family name already exists.')
        return css_name

    def clean_font_file(self):
        font_file = self.cleaned_data.get('font_file')
        if not font_file:
            return font_file

        extension = font_file.name.rsplit('.', 1)[-1].lower()
        if extension not in FONT_FILE_EXTENSIONS:
            raise forms.ValidationError('Only .ttf, .otf, .woff, and .woff2 files are allowed.')
        return font_file
