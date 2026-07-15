from functools import wraps

from django.contrib import messages
from django.contrib.auth.views import redirect_to_login
from django.shortcuts import redirect

from .models import SellerProfile


def seller_account_required(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        try:
            request.seller = request.user.seller_profile
        except SellerProfile.DoesNotExist:
            messages.info(request, 'Complete seller onboarding to access the seller panel.')
            return redirect('marketplace:onboarding')
        return view(request, *args, **kwargs)
    return wrapped


def approved_seller_required(view):
    @seller_account_required
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.seller.is_approved:
            messages.warning(request, 'This feature becomes available after seller approval.')
            return redirect('marketplace:dashboard')
        return view(request, *args, **kwargs)
    return wrapped
