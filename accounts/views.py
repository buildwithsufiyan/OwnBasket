from django.shortcuts import render, redirect
from django.contrib.auth import logout
from django.contrib.auth.forms import UserCreationForm
from django.contrib import messages
from django.db import transaction
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .models import CustomerProfile


def account_choice(request):
    return render(request, 'accounts/account_choice.html')


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
