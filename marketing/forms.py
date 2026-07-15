from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm

from .models import NotificationPreference


class NewsletterSubscriptionForm(forms.Form):
    email = forms.EmailField(max_length=254)
    consent = forms.BooleanField(required=True, label='I want OwnBasket marketing emails and can unsubscribe at any time.')
    website = forms.CharField(required=False, widget=forms.HiddenInput)

    def clean_website(self):
        if self.cleaned_data.get('website'):
            raise forms.ValidationError('Unable to process subscription.')
        return ''


class NotificationPreferenceForm(forms.ModelForm):
    class Meta:
        model = NotificationPreference
        fields = (
            'order_updates', 'delivery_updates', 'promotional_emails', 'newsletter',
            'abandoned_cart_reminders', 'wishlist_reminders', 'back_in_stock_alerts', 'marketing_consent',
        )
        labels = {'marketing_consent': 'I consent to optional marketing email processing.'}

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get('marketing_consent'):
            for field in ('promotional_emails', 'abandoned_cart_reminders', 'wishlist_reminders'):
                cleaned[field] = False
        return cleaned


class AccountRegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    marketing_consent = forms.BooleanField(required=False, label='Send me optional OwnBasket offers and product updates.')

    class Meta(UserCreationForm.Meta):
        model = get_user_model()
        fields = ('username', 'email')

    def clean_email(self):
        value = self.cleaned_data['email'].strip().lower()
        if get_user_model().objects.filter(email__iexact=value).exists():
            raise forms.ValidationError('An account already uses this email address.')
        return value

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
        return user
