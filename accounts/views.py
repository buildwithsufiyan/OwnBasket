from django.shortcuts import render, redirect
from django.contrib.auth import logout
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .models import CustomerProfile
from .forms import AccountPasswordChangeForm, ProfileForm
from marketing.forms import AccountRegistrationForm
from marketing.models import NotificationPreference
from marketing.models import Referral, ReferralCode
from marketing.models import EngagementDelivery
from marketing.services.email_service import send_branded_email
from orders.models import Order
from wishlist.models import Wishlist


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


@csrf_exempt
@require_http_methods(["GET", "POST"])
def logout_view(request):
    if request.user.is_authenticated:
        logout(request)

    return redirect('home')
