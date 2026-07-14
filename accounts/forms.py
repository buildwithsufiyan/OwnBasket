from django import forms
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.models import User


class ProfileForm(forms.ModelForm):
    first_name = forms.CharField(max_length=150, required=True)
    last_name = forms.CharField(max_length=150, required=True)
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'email')
        widgets = {
            'first_name': forms.TextInput(attrs={'autocomplete': 'given-name'}),
            'last_name': forms.TextInput(attrs={'autocomplete': 'family-name'}),
            'email': forms.EmailInput(attrs={'autocomplete': 'email'}),
        }

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if User.objects.exclude(pk=self.instance.pk).filter(email__iexact=email).exists():
            raise forms.ValidationError('An account already uses this email address.')
        return email


class AccountPasswordChangeForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['old_password'].widget.attrs.update({'autocomplete': 'current-password'})
        self.fields['new_password1'].widget.attrs.update({'autocomplete': 'new-password'})
        self.fields['new_password2'].widget.attrs.update({'autocomplete': 'new-password'})
