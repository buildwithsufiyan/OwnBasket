from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.http import safe_redirect_target
from products.models import Product

from .forms import NewsletterSubscriptionForm, NotificationPreferenceForm
from .models import EngagementDelivery, LoyaltyAccount, NewsletterSubscription, NotificationPreference, ReferralCode, StockAlert
from .services.email_service import send_branded_email
from .services.tokens import make_subscription_token, resolve_subscription_token


GENERIC_SUBSCRIBE_MESSAGE = 'Please check your inbox for the next step if this address can receive OwnBasket email.'


@require_POST
def newsletter_subscribe(request):
    form = NewsletterSubscriptionForm(request.POST)
    if form.is_valid():
        email = form.cleaned_data['email'].strip().lower()
        user = request.user if request.user.is_authenticated and request.user.email.lower() == email else None
        subscription, _ = NewsletterSubscription.objects.get_or_create(
            email=email,
            defaults={'user': user, 'source': request.POST.get('source', 'footer')[:40]},
        )
        user_link_changed = bool(user and not subscription.user_id)
        if user_link_changed:
            subscription.user = user
        if subscription.status != NewsletterSubscription.Status.ACTIVE:
            subscription.status = NewsletterSubscription.Status.PENDING
            subscription.consent_recorded_at = subscription.consent_recorded_at or timezone.now()
            subscription.save()
            token = make_subscription_token(subscription)
            confirm_url = request.build_absolute_uri(reverse('marketing:newsletter_confirm', args=(token,)))
            send_branded_email(
                subject='Confirm your OwnBasket newsletter subscription', recipient=email,
                template_name='newsletter_confirmation', context={'confirm_url': confirm_url},
                kind=EngagementDelivery.Kind.CAMPAIGN, reference=f'newsletter-{subscription.pk}', user=user,
            )
            subscription.confirmation_sent_at = timezone.now()
            subscription.save(update_fields=('confirmation_sent_at', 'updated_at'))
        elif user_link_changed:
            subscription.save(update_fields=('user', 'updated_at'))
        messages.success(request, GENERIC_SUBSCRIBE_MESSAGE)
    else:
        messages.error(request, 'Please provide a valid email address and consent choice.')
    return redirect(safe_redirect_target(request, request.POST.get('next', ''), 'home'))


def newsletter_confirm(request, token):
    subscription = resolve_subscription_token(token)
    if not subscription:
        raise Http404
    subscription.activate()
    if subscription.user_id:
        preferences, _ = NotificationPreference.objects.get_or_create(user=subscription.user)
        preferences.newsletter = True
        preferences.marketing_consent = True
        preferences.consent_source = subscription.source
        preferences.consent_recorded_at = subscription.consent_recorded_at
        preferences.consent_withdrawn_at = None
        preferences.save()
    return render(request, 'marketing/newsletter_confirmed.html', {'subscription': subscription})


def newsletter_unsubscribe(request, token):
    subscription = resolve_subscription_token(token)
    if not subscription:
        raise Http404
    if request.method == 'POST':
        subscription.unsubscribe()
        if subscription.user_id:
            preferences, _ = NotificationPreference.objects.get_or_create(user=subscription.user)
            preferences.newsletter = False
            preferences.record_consent(False, 'unsubscribe')
        return render(request, 'marketing/newsletter_unsubscribed.html')
    return render(request, 'marketing/newsletter_unsubscribe_confirm.html', {'token': token})


@login_required
def engagement_dashboard(request):
    preferences, _ = NotificationPreference.objects.get_or_create(user=request.user)
    referral_code = ReferralCode.objects.filter(user=request.user).first() or ReferralCode.create_for_user(request.user)
    loyalty, _ = LoyaltyAccount.objects.get_or_create(user=request.user)
    subscription = NewsletterSubscription.objects.filter(email__iexact=request.user.email).first() if request.user.email else None
    return render(request, 'marketing/engagement_dashboard.html', {
        'preferences': preferences, 'referral_code': referral_code,
        'referrals': referral_code.referrals.select_related('referred_user').all()[:20],
        'loyalty': loyalty, 'loyalty_transactions': loyalty.transactions.all()[:20],
        'stock_alerts': request.user.stock_alerts.select_related('product').filter(is_active=True)[:20],
        'subscription': subscription,
        'referral_url': request.build_absolute_uri(reverse('register')) + f'?ref={referral_code.code}',
    })


@login_required
def notification_preferences(request):
    preferences, _ = NotificationPreference.objects.get_or_create(user=request.user)
    previous_consent = preferences.marketing_consent
    form = NotificationPreferenceForm(request.POST or None, instance=preferences)
    if request.method == 'POST' and form.is_valid():
        updated = form.save(commit=False)
        if updated.marketing_consent != previous_consent:
            updated.record_consent(updated.marketing_consent, 'account_settings')
        else:
            updated.save()
        messages.success(request, 'Notification preferences updated.')
        return redirect('marketing:preferences')
    return render(request, 'marketing/preferences.html', {'form': form})


@login_required
@require_POST
def stock_alert_subscribe(request, product_id):
    product = get_object_or_404(Product.objects.marketplace_visible(), pk=product_id, is_active=True)
    preferences, _ = NotificationPreference.objects.get_or_create(user=request.user)
    if not request.user.email or not preferences.back_in_stock_alerts:
        messages.error(request, 'Enable back-in-stock email alerts in notification preferences first.')
        return redirect(product.get_absolute_url())
    StockAlert.objects.update_or_create(
        user=request.user, product=product,
        defaults={'email': request.user.email, 'is_active': True, 'notified_at': None},
    )
    messages.success(request, 'Back-in-stock alert saved.')
    return redirect(product.get_absolute_url())


@login_required
@require_POST
def stock_alert_remove(request, alert_id):
    alert = get_object_or_404(StockAlert, pk=alert_id, user=request.user)
    alert.is_active = False
    alert.save(update_fields=('is_active',))
    return redirect('marketing:engagement_dashboard')
