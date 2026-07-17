from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import PrivacyRequest


class SecureAuthenticationForm(AuthenticationForm):
    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        from .models import AccountSecurityState
        state, _ = AccountSecurityState.objects.get_or_create(user=user)
        if state.locked_until and state.locked_until > timezone.now():
            raise ValidationError('Unable to sign in. Try again later or reset your password.', code='account_locked')


class SecuritySettingsForm(forms.Form):
    password = forms.CharField(widget=forms.PasswordInput(attrs={'autocomplete': 'current-password'}))


class PrivacyRequestForm(forms.ModelForm):
    class Meta:
        model = PrivacyRequest
        fields = ('request_type', 'notes')
        widgets = {'notes': forms.Textarea(attrs={'rows': 3, 'maxlength': 2000})}

    def clean_notes(self):
        notes = (self.cleaned_data.get('notes') or '').strip()
        if len(notes) > 2000:
            raise ValidationError('Notes may not exceed 2000 characters.')
        return notes
