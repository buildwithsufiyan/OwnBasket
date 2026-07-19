from pathlib import Path

from django import forms

from core.admin_visual_editor import VisualEditorFormMixin

from .models import Brand, BrandHeroBanner, Category, Product, ProductReview, SubCategory, Warehouse
from security.uploads import SecureUploadFormMixin


class ProductReviewForm(forms.ModelForm):
    website = forms.CharField(required=False, widget=forms.HiddenInput, label='')

    class Meta:
        model = ProductReview
        fields = ('rating', 'title', 'body')
        widgets = {
            'rating': forms.Select(choices=((5, '5 - Excellent'), (4, '4 - Good'), (3, '3 - Average'), (2, '2 - Poor'), (1, '1 - Very poor'))),
            'title': forms.TextInput(attrs={'maxlength': 160, 'placeholder': 'Summarize your experience'}),
            'body': forms.Textarea(attrs={'rows': 5, 'maxlength': 4000, 'placeholder': 'What should other customers know?'}),
        }

    def __init__(self, *args, minimum_characters=20, **kwargs):
        self.minimum_characters = minimum_characters
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('website'):
            raise forms.ValidationError('Review could not be submitted.')
        body = (cleaned.get('body') or '').strip()
        if len(body) < self.minimum_characters:
            self.add_error('body', f'Please write at least {self.minimum_characters} characters.')
        if body.count('http://') + body.count('https://') > 2:
            self.add_error('body', 'Reviews may contain at most two links.')
        return cleaned


class CategoryAdminForm(SecureUploadFormMixin, forms.ModelForm):
    class Meta:
        model = Category
        fields = '__all__'


class SubCategoryAdminForm(SecureUploadFormMixin, forms.ModelForm):
    class Meta:
        model = SubCategory
        fields = '__all__'


class WarehouseAdminForm(forms.ModelForm):
    class Meta:
        model = Warehouse
        fields = '__all__'


class BrandAdminForm(SecureUploadFormMixin, forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        name_field = self.fields.get('name')
        if name_field is not None:
            name_field.required = False
            name_field.help_text = "Optional. Blank chhorne par system default name save kar dega."

    def clean_name(self):
        name = (self.cleaned_data.get('name') or '').strip()
        if name:
            return name

        if self.instance.pk and self.instance.name:
            return self.instance.name

        logo = self.cleaned_data.get('logo')
        if logo and getattr(logo, 'name', ''):
            derived_name = Path(logo.name).stem.replace('-', ' ').replace('_', ' ').strip()
            if derived_name:
                return derived_name.title()

        return "Brand"

    class Meta:
        model = Brand
        fields = '__all__'


class BrandHeroBannerAdminForm(SecureUploadFormMixin, VisualEditorFormMixin, forms.ModelForm):
    class Meta:
        model = BrandHeroBanner
        fields = '__all__'
        widgets = {
            'banner_title': forms.TextInput(attrs={'placeholder': 'Optional. Premium Summer Sale'}),
            'banner_subtitle': forms.TextInput(attrs={'placeholder': 'Optional. Add a short supporting line'}),
            'button_text': forms.TextInput(attrs={'placeholder': 'Optional. Shop Now'}),
            'button_url': forms.URLInput(attrs={'placeholder': 'Optional. https://example.com/promo'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.apply_base_input_style()
        optional_field_help_texts = {
            'banner_title': 'Optional. Leave blank to show only the banner image.',
            'banner_subtitle': 'Optional. Subtitle will only show when provided.',
            'button_text': 'Optional. Button is hidden when this field is empty.',
            'button_url': 'Optional. If button text is set but URL is blank, the button uses #.',
            'cover_image': 'Upload the premium cover image shown in the brand banner slider.',
            'display_order': 'Lower numbers appear earlier in the brand slider.',
            'is_active': 'Only active brand banners appear on the frontend.',
        }

        for field_name, help_text in optional_field_help_texts.items():
            field = self.fields.get(field_name)
            if field is not None:
                field.required = False
                field.help_text = help_text


class CouponApplyForm(forms.Form):
    code = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.TextInput(
            attrs={
                'class': 'form-control',
                'placeholder': 'Enter coupon code',
                'autocomplete': 'off',
            }
        ),
    )

    def clean_code(self):
        return (self.cleaned_data.get('code') or '').upper().strip()


class ProductAdminForm(SecureUploadFormMixin, forms.ModelForm):
    class Meta:
        model = Product
        fields = '__all__'
        widgets = {
            'description': forms.Textarea(attrs={'rows': 5}),
            'return_policy': forms.Textarea(attrs={'rows': 4}),
            'delivery_text': forms.TextInput(attrs={'placeholder': 'FREE delivery Saturday, 28 June.'}),
        }

    def _configure_optional_field(self, field_name, *, disabled=False):
        field = self.fields.get(field_name)
        if field is None:
            return None

        field.required = False
        field.disabled = disabled
        return field

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._configure_optional_field('slug')
        self._configure_optional_field('sku')
        self._configure_optional_field('discount_percentage', disabled=True)
        self._configure_optional_field('profit_margin', disabled=True)

        subcategory_field = self.fields.get('subcategory')
        if subcategory_field is not None:
            subcategory_field.queryset = SubCategory.objects.none()

        category_id = None
        if self.is_bound:
            category_id = self.data.get('category')
        elif self.instance.pk:
            category_id = self.instance.category_id

        if subcategory_field is not None:
            if category_id:
                subcategory_field.queryset = SubCategory.objects.filter(
                    category_id=category_id
                ).order_by('sort_order', 'name')
            else:
                subcategory_field.queryset = SubCategory.objects.order_by(
                    'category__name',
                    'sort_order',
                    'name',
                )
