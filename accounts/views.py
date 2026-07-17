from django.shortcuts import render, redirect
from django.contrib.auth import logout
from django.contrib.auth.views import LoginView, PasswordResetConfirmView, PasswordResetView
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.views.decorators.http import require_POST

from .models import CustomerProfile
from .forms import AccountPasswordChangeForm, ProfileForm
from marketing.forms import AccountRegistrationForm
from marketing.models import NotificationPreference
from marketing.models import Referral, ReferralCode
from marketing.models import EngagementDelivery
from marketing.services.email_service import send_branded_email
from orders.models import Order
from wishlist.models import Wishlist
from security.models import AuditEvent
from security.services import audit
from security.forms import SecureAuthenticationForm


class SecureLoginView(LoginView):
    template_name = 'registration/login.html'
    authentication_form = SecureAuthenticationForm

    def form_valid(self, form):
        response = super().form_valid(form)
        self.request.session.set_expiry(None if self.request.POST.get('remember_me') == 'on' else 0)
        return response

    def form_invalid(self, form):
        if form.has_error(None, 'account_locked'):
            audit('locked_account_login_attempt', category=AuditEvent.Category.AUTH, request=self.request, success=False)
        return super().form_invalid(form)


class AuditedPasswordResetView(PasswordResetView):
    template_name = 'registration/password_reset_form.html'
    email_template_name = 'registration/password_reset_email.txt'
    subject_template_name = 'registration/password_reset_subject.txt'
    success_url = '/password-reset/done/'

    def form_valid(self, form):
        audit('password_reset_requested', category=AuditEvent.Category.AUTH, request=self.request)
        return super().form_valid(form)


class AuditedPasswordResetConfirmView(PasswordResetConfirmView):
    template_name = 'registration/password_reset_confirm.html'

    def form_valid(self, form):
        response = super().form_valid(form)
        audit('password_reset_completed', category=AuditEvent.Category.AUTH, user=form.user, request=self.request)
        return response


def account_choice(request):
    if request.user.is_authenticated:
        return redirect('account_dashboard')
    return render(request, 'accounts/account_choice.html')


@login_required
def dashboard(request):
    orders = Order.objects.filter(user=request.user).prefetch_related('items__product')
    return render(request, 'accounts/dashboard.html', {
        'order_count': orders.count(),
        'wishlist_count': Wishlist.objects.filter(user=request.user).count(),
        'recent_orders': orders.order_by('-created_at')[:4],
    })


@login_required
def profile(request):
    form = ProfileForm(request.POST or None, instance=request.user)
    if request.method == 'POST' and form.is_valid():
        form.save()
        audit('profile_updated', category=AuditEvent.Category.ACCOUNT, user=request.user, request=request)
        messages.success(request, 'Your profile has been updated.')
        return redirect('account_profile')
    return render(request, 'accounts/profile.html', {'form': form})


@login_required
def settings(request):
    return render(request, 'accounts/settings.html')


@login_required
def change_password(request):
    form = AccountPasswordChangeForm(request.user, request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        update_session_auth_hash(request, user)
        audit('password_changed', category=AuditEvent.Category.ACCOUNT, user=request.user, request=request)
        messages.success(request, 'Your password has been changed securely.')
        return redirect('account_settings')
    return render(request, 'accounts/change_password.html', {'form': form})


def register(request):
    referral_value = (request.GET.get('ref') or '').strip().upper()
    if referral_value:
        request.session['pending_referral_code'] = referral_value
    if request.method == 'POST':
        form = AccountRegistrationForm(request.POST)

        if form.is_valid():
            with transaction.atomic():
                user = form.save(commit=False)
                user.is_staff = False
                user.is_superuser = False
                user.save()
                audit('account_registered', category=AuditEvent.Category.ACCOUNT, user=user, request=request)
                CustomerProfile.objects.get_or_create(user=user)
                preferences, _ = NotificationPreference.objects.get_or_create(user=user)
                if form.cleaned_data.get('marketing_consent'):
                    preferences.promotional_emails = True
                    preferences.record_consent(True, 'registration')
                referral_code = ReferralCode.objects.filter(code=request.session.pop('pending_referral_code', '')).first()
                if referral_code and referral_code.user_id != user.id:
                    referral = Referral(referral_code=referral_code, referred_user=user)
                    referral.full_clean()
                    referral.save()

            messages.success(
                request,
                'Account created successfully. Please login.'
            )

            send_branded_email(
                subject='Welcome to OwnBasket', recipient=user.email,
                template_name='welcome', context={'user': user},
                kind=EngagementDelivery.Kind.TRANSACTIONAL, reference=f'welcome-{user.pk}', user=user,
            )

            return redirect('login')

    else:
        form = AccountRegistrationForm()

    return render(
        request,
        'accounts/register.html',
        {'form': form}
    )


@require_POST
def logout_view(request):
    if request.user.is_authenticated:
        logout(request)

    return redirect('home')
