from django.shortcuts import render, redirect
from django.contrib.auth import logout
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib import messages
from django.db import transaction
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .models import CustomerProfile
from .forms import AccountPasswordChangeForm, ProfileForm
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
    if request.method == 'POST':
        form = UserCreationForm(request.POST)

        if form.is_valid():
            with transaction.atomic():
                user = form.save(commit=False)
                user.is_staff = False
                user.is_superuser = False
                user.save()
                CustomerProfile.objects.get_or_create(user=user)

            messages.success(
                request,
                'Account created successfully. Please login.'
            )

            return redirect('login')

    else:
        form = UserCreationForm()

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
