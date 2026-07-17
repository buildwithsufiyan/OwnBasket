from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.utils.text import slugify

from products.models import Product

from .models import SellerDocument, SellerPayoutAccount, SellerProfile
from security.uploads import SecureUploadFormMixin


User = get_user_model()


class SellerRegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    store_name = forms.CharField(max_length=160)
    legal_name = forms.CharField(max_length=180)
    business_phone = forms.CharField(max_length=32)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'email', 'store_name', 'legal_name', 'business_phone')

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('An account already uses this email address.')
        return email

    def clean_store_name(self):
        store_name = self.cleaned_data['store_name'].strip()
        if SellerProfile.objects.filter(store_name__iexact=store_name).exists():
            raise forms.ValidationError('A store already uses this name.')
        return store_name

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
            SellerProfile.objects.create(
                user=user,
                store_name=self.cleaned_data['store_name'],
                slug=unique_store_slug(self.cleaned_data['store_name']),
                legal_name=self.cleaned_data['legal_name'],
                business_email=user.email,
                business_phone=self.cleaned_data['business_phone'],
            )
        return user


def unique_store_slug(name, instance=None):
    base = slugify(name)[:160] or 'store'
    candidate = base
    counter = 2
    queryset = SellerProfile.objects.exclude(pk=getattr(instance, 'pk', None))
    while queryset.filter(slug=candidate).exists():
        candidate = f'{base[:154]}-{counter}'
        counter += 1
    return candidate


class SellerOnboardingForm(SecureUploadFormMixin, forms.ModelForm):
    class Meta:
        model = SellerProfile
        fields = (
            'store_name', 'legal_name', 'business_email', 'business_phone',
            'description', 'address', 'city', 'tax_identifier', 'logo', 'banner',
            'shipping_policy', 'return_policy', 'privacy_policy',
        )
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'address': forms.Textarea(attrs={'rows': 3}),
            'shipping_policy': forms.Textarea(attrs={'rows': 4}),
            'return_policy': forms.Textarea(attrs={'rows': 4}),
            'privacy_policy': forms.Textarea(attrs={'rows': 4}),
        }

    def clean_store_name(self):
        value = self.cleaned_data['store_name'].strip()
        if SellerProfile.objects.exclude(pk=self.instance.pk).filter(store_name__iexact=value).exists():
            raise forms.ValidationError('A store already uses this name.')
        return value

    def save(self, commit=True):
        seller = super().save(commit=False)
        if not seller.slug or 'store_name' in self.changed_data:
            seller.slug = unique_store_slug(seller.store_name, seller)
        if seller.verification_status in {
            SellerProfile.VerificationStatus.DRAFT,
            SellerProfile.VerificationStatus.REJECTED,
        }:
            seller.verification_status = SellerProfile.VerificationStatus.PENDING
        if commit:
            seller.save()
        return seller


class SellerProductForm(SecureUploadFormMixin, forms.ModelForm):
    class Meta:
        model = Product
        fields = (
            'name', 'category', 'subcategory', 'brand', 'short_description', 'description',
            'image', 'video', 'price', 'cost_price', 'selling_price', 'mrp', 'discount_price',
            'offer_start_at', 'offer_end_at', 'tax_percentage', 'stock', 'low_stock_alert',
            'allow_backorder', 'warehouse', 'weight', 'length_cm', 'width_cm', 'height_cm',
            'warranty', 'return_policy', 'delivery_text', 'free_delivery', 'cash_on_delivery',
        )
        widgets = {
            'description': forms.Textarea(attrs={'rows': 5}),
            'return_policy': forms.Textarea(attrs={'rows': 4}),
            'offer_start_at': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'offer_end_at': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }

    def clean(self):
        cleaned = super().clean()
        selling_price = cleaned.get('selling_price') or cleaned.get('price')
        mrp = cleaned.get('mrp')
        discount = cleaned.get('discount_price')
        if mrp is not None and selling_price is not None and mrp < selling_price:
            self.add_error('mrp', 'MRP cannot be lower than the selling price.')
        if discount is not None and selling_price is not None and discount > selling_price:
            self.add_error('discount_price', 'Discount price cannot exceed the selling price.')
        return cleaned


class SellerSettingsForm(SecureUploadFormMixin, forms.ModelForm):
    class Meta:
        model = SellerProfile
        fields = (
            'store_name', 'business_email', 'business_phone', 'description', 'logo', 'banner',
            'address', 'city', 'shipping_policy', 'return_policy', 'privacy_policy',
            'order_notifications', 'inventory_notifications', 'marketing_notifications',
        )
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'address': forms.Textarea(attrs={'rows': 3}),
            'shipping_policy': forms.Textarea(attrs={'rows': 4}),
            'return_policy': forms.Textarea(attrs={'rows': 4}),
            'privacy_policy': forms.Textarea(attrs={'rows': 4}),
        }

    def clean_store_name(self):
        value = self.cleaned_data['store_name'].strip()
        if SellerProfile.objects.exclude(pk=self.instance.pk).filter(store_name__iexact=value).exists():
            raise forms.ValidationError('A store already uses this name.')
        return value

    def save(self, commit=True):
        seller = super().save(commit=False)
        if 'store_name' in self.changed_data:
            seller.slug = unique_store_slug(seller.store_name, seller)
        if commit:
            seller.save()
        return seller


class SellerDocumentForm(SecureUploadFormMixin, forms.ModelForm):
    class Meta:
        model = SellerDocument
        fields = ('document_type', 'file')


class SellerPayoutAccountForm(forms.ModelForm):
    class Meta:
        model = SellerPayoutAccount
        fields = ('method', 'account_title', 'account_reference')

    def clean_account_reference(self):
        value = self.cleaned_data['account_reference'].strip()
        if value and not ('*' in value or len(value) <= 8):
            raise forms.ValidationError('Use a masked account number or provider reference only.')
        return value
