from decimal import Decimal

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.views import LoginView
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Avg, Count, F, Q, Sum
from django.db.models.functions import TruncDate
from django.http import Http404, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render

from orders.models import OrderItem
from products.models import Product, ProductReview
from products.pricing import attach_pricing_to_products
from security.forms import SecureAuthenticationForm

from .decorators import approved_seller_required, seller_account_required
from .forms import (
    SellerDocumentForm,
    SellerInventoryForm,
    SellerOnboardingForm,
    SellerOrderStatusForm,
    SellerPayoutAccountForm,
    SellerProductForm,
    SellerProductImageFormSet,
    SellerProductSpecificationFormSet,
    SellerProductVariantFormSet,
    SellerRegistrationForm,
    SellerSettingsForm,
)
from .models import (
    SellerInventory,
    SellerNotification,
    SellerOrderFulfillment,
    SellerPayout,
    SellerPayoutAccount,
    SellerProfile,
)
from .services import marketplace_settings, update_fulfillment, update_inventory


ZERO = Decimal('0.00')


class SellerLoginView(LoginView):
    template_name = 'marketplace/login.html'
    authentication_form = SecureAuthenticationForm

    def get_success_url(self):
        return self.get_redirect_url() or str('/marketplace/seller/')


def seller_register(request):
    if not marketplace_settings().accepts_sellers:
        raise Http404('Seller registration is not available.')
    if request.user.is_authenticated:
        return redirect('marketplace:onboarding')
    form = SellerRegistrationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            user = form.save()
        login(request, user)
        messages.success(request, 'Seller account created. Your store is now awaiting verification.')
        return redirect('marketplace:dashboard')
    return render(request, 'marketplace/register.html', {'form': form})


def seller_onboarding(request):
    if not marketplace_settings().accepts_sellers:
        raise Http404('Seller onboarding is not available.')
    if not request.user.is_authenticated:
        return redirect(f"/marketplace/seller/login/?next=/marketplace/seller/onboarding/")
    seller = SellerProfile.objects.filter(user=request.user).first()
    if seller:
        return redirect('marketplace:dashboard')
    initial = {
        'legal_name': request.user.get_full_name(),
        'business_email': request.user.email,
    }
    form = SellerOnboardingForm(request.POST or None, request.FILES or None, initial=initial)
    if request.method == 'POST' and form.is_valid():
        seller = form.save(commit=False)
        seller.user = request.user
        seller.save()
        messages.success(request, 'Your seller application has been submitted for review.')
        return redirect('marketplace:dashboard')
    return render(request, 'marketplace/onboarding.html', {'form': form})


def _seller_line_items(seller):
    return OrderItem.objects.filter(seller=seller).select_related(
        'order', 'order__user', 'product', 'product__brand', 'product__category'
    )


def _earning_summary(seller):
    line_items = _seller_line_items(seller)
    totals = line_items.aggregate(
        earnings=Sum('seller_earning'),
        commission=Sum('marketplace_commission'),
    )
    total_earnings = totals['earnings'] or ZERO
    delivered_earnings = line_items.filter(order__status='Delivered').aggregate(
        total=Sum('seller_earning')
    )['total'] or ZERO
    total_commission = totals['commission'] or ZERO
    paid = seller.payouts.filter(status=SellerPayout.Status.PAID).aggregate(total=Sum('amount'))['total'] or ZERO
    pending = seller.payouts.exclude(status__in=(SellerPayout.Status.PAID, SellerPayout.Status.FAILED)).aggregate(total=Sum('amount'))['total'] or ZERO
    return {
        'total_earnings': total_earnings,
        'marketplace_commission': total_commission,
        'paid': paid,
        'pending': pending,
        'available': max(delivered_earnings - paid - pending, ZERO),
    }


@seller_account_required
def dashboard(request):
    seller = request.seller
    products = seller.products.all()
    line_items = _seller_line_items(seller)
    product_summary = products.aggregate(
        product_count=Count('id'),
        active_product_count=Count('id', filter=Q(is_active=True)),
        low_stock_count=Count('id', filter=Q(stock__gt=0, stock__lte=F('low_stock_alert'), is_active=True)),
        out_of_stock_count=Count('id', filter=Q(stock=0, is_active=True)),
    )
    review_summary = ProductReview.objects.filter(
        product__seller=seller,
        moderation_status=ProductReview.ModerationStatus.APPROVED,
    ).aggregate(average_rating=Avg('rating'), review_count=Count('id'))
    context = {
        'seller': seller,
        'order_count': line_items.values('order_id').distinct().count(),
        'recent_items': line_items.order_by('-order__created_at', '-id')[:8],
        'recent_reviews': ProductReview.objects.filter(
            product__seller=seller,
            moderation_status=ProductReview.ModerationStatus.APPROVED,
        ).select_related('product', 'user').order_by('-created_at')[:5],
        'reserved_stock': seller.inventory_records.aggregate(total=Sum('reserved_stock'))['total'] or 0,
        'unread_notifications': seller.notifications.filter(is_read=False).count(),
        **product_summary,
        **review_summary,
        **_earning_summary(seller),
    }
    return render(request, 'marketplace/dashboard.html', context)


@approved_seller_required
def product_list(request):
    query = request.GET.get('q', '').strip()
    products = request.seller.products.select_related('brand', 'category', 'subcategory', 'warehouse')
    if query:
        products = products.filter(Q(name__icontains=query) | Q(sku__icontains=query))
    products = products.order_by('-created_at', '-id')
    page_obj = Paginator(products, 20).get_page(request.GET.get('page'))
    return render(request, 'marketplace/products.html', {'page_obj': page_obj, 'query': query})


@approved_seller_required
def product_create(request):
    form = SellerProductForm(request.POST or None, request.FILES or None)
    product = Product(seller=request.seller)
    formsets = _product_formsets(request, product)
    if request.method == 'POST' and form.is_valid() and _product_formsets_valid(request, formsets):
        with transaction.atomic():
            product = form.save(commit=False)
            product.seller = request.seller
            product.save()
            for formset in formsets.values():
                if f'{formset.prefix}-TOTAL_FORMS' in request.POST:
                    formset.instance = product
                    formset.save()
        messages.success(request, 'Product, images, variants, and attributes created successfully.')
        return redirect('marketplace:products')
    return render(request, 'marketplace/product_form.html', {
        'form': form, 'formsets': formsets, 'title': 'Add product',
    })


@approved_seller_required
def product_update(request, product_id):
    product = get_object_or_404(request.seller.products.all(), pk=product_id)
    form = SellerProductForm(request.POST or None, request.FILES or None, instance=product)
    formsets = _product_formsets(request, product)
    if request.method == 'POST' and form.is_valid() and _product_formsets_valid(request, formsets):
        with transaction.atomic():
            updated = form.save(commit=False)
            updated.seller = request.seller
            updated.save()
            for formset in formsets.values():
                if f'{formset.prefix}-TOTAL_FORMS' in request.POST:
                    formset.save()
        messages.success(request, 'Product, images, variants, and attributes updated successfully.')
        return redirect('marketplace:products')
    return render(request, 'marketplace/product_form.html', {
        'form': form, 'formsets': formsets, 'title': 'Edit product', 'product': product,
    })


def _product_formsets(request, product):
    data = request.POST if request.method == 'POST' else None
    files = request.FILES if request.method == 'POST' else None
    return {
        'images': SellerProductImageFormSet(data, files, instance=product, prefix='images'),
        'variants': SellerProductVariantFormSet(data, instance=product, prefix='variants'),
        'attributes': SellerProductSpecificationFormSet(data, instance=product, prefix='attributes'),
    }


def _product_formsets_valid(request, formsets):
    return all(
        f'{formset.prefix}-TOTAL_FORMS' not in request.POST or formset.is_valid()
        for formset in formsets.values()
    )


@approved_seller_required
def product_archive(request, product_id):
    if request.method != 'POST':
        return HttpResponseNotAllowed(('POST',))
    product = get_object_or_404(request.seller.products.all(), pk=product_id)
    product.is_active = False
    product.save(update_fields=('is_active',))
    messages.success(request, 'Product archived. Historical order data was preserved.')
    return redirect('marketplace:products')


@approved_seller_required
def orders(request):
    status = request.GET.get('status', '').strip()
    line_items = _seller_line_items(request.seller).order_by('-order__created_at', '-id')
    if status:
        line_items = line_items.filter(order__status=status)
    page_obj = Paginator(line_items, 25).get_page(request.GET.get('page'))
    return render(request, 'marketplace/orders.html', {
        'page_obj': page_obj,
        'selected_status': status,
        'status_choices': ('Pending', 'Processing', 'Shipped', 'Delivered'),
    })


@approved_seller_required
def order_detail(request, order_id):
    items = _seller_line_items(request.seller).filter(order_id=order_id).order_by('id')
    first_item = items.first()
    if first_item is None:
        raise Http404('Order not found.')
    fulfillment, created = SellerOrderFulfillment.objects.get_or_create(
        seller=request.seller,
        order=first_item.order,
    )
    if created:
        fulfillment.history.create(
            status=SellerOrderFulfillment.Status.RECEIVED,
            note='Seller order received.',
        )
    form = SellerOrderStatusForm(request.POST or None, instance=fulfillment)
    if request.method == 'POST' and form.is_valid():
        update_fulfillment(
            fulfillment=fulfillment,
            status=form.cleaned_data['status'],
            note=form.cleaned_data['seller_note'],
            user=request.user,
        )
        messages.success(request, 'Seller fulfillment status updated.')
        return redirect('marketplace:order_detail', order_id=order_id)
    fulfillment.refresh_from_db()
    return render(request, 'marketplace/order_detail.html', {
        'order': first_item.order,
        'items': items,
        'fulfillment': fulfillment,
        'form': form,
        'status_history': fulfillment.history.select_related('changed_by'),
    })


@approved_seller_required
def inventory(request):
    records = SellerInventory.objects.filter(seller=request.seller).select_related(
        'product', 'product__category', 'product__brand',
    ).order_by('product__name')
    existing_product_ids = records.values_list('product_id', flat=True)
    missing = request.seller.products.exclude(pk__in=existing_product_ids).only('id', 'seller_id')
    SellerInventory.objects.bulk_create(
        [SellerInventory(seller=request.seller, product=product) for product in missing],
        ignore_conflicts=True,
    )
    records = SellerInventory.objects.filter(seller=request.seller).select_related(
        'product', 'product__category', 'product__brand',
    ).order_by('product__name')
    page_obj = Paginator(records, 25).get_page(request.GET.get('page'))
    return render(request, 'marketplace/inventory.html', {'page_obj': page_obj})


@approved_seller_required
def inventory_update(request, product_id):
    product = get_object_or_404(request.seller.products.all(), pk=product_id)
    record, _ = SellerInventory.objects.get_or_create(seller=request.seller, product=product)
    form = SellerInventoryForm(request.POST or None, instance=record)
    if request.method == 'POST' and form.is_valid():
        update_inventory(
            inventory=record,
            current_stock=form.cleaned_data['current_stock'],
            reserved_stock=form.cleaned_data['reserved_stock'],
            user=request.user,
            note='Seller dashboard adjustment',
        )
        messages.success(request, 'Inventory updated and recorded in history.')
        return redirect('marketplace:inventory_update', product_id=product_id)
    return render(request, 'marketplace/inventory_form.html', {
        'product': product,
        'inventory': record,
        'form': form,
        'history': record.history.select_related('created_by')[:50],
    })


@approved_seller_required
def analytics(request):
    seller = request.seller
    products = seller.products.order_by('-total_sold', '-total_views')
    daily_sales = list(
        _seller_line_items(seller).annotate(day=TruncDate('order__created_at')).values('day').annotate(
            earnings=Sum('seller_earning'), orders=Count('order_id', distinct=True)
        ).order_by('-day')[:30]
    )
    real_reviews = ProductReview.objects.filter(
        product__seller=seller,
        moderation_status=ProductReview.ModerationStatus.APPROVED,
    ).aggregate(rating=Avg('rating'), reviews=Count('id'))
    return render(request, 'marketplace/analytics.html', {
        'top_products': products[:10], 'daily_sales': daily_sales,
        'real_rating': real_reviews['rating'], 'real_review_count': real_reviews['reviews'],
        **_earning_summary(seller),
    })


@approved_seller_required
def payouts(request):
    account, _ = SellerPayoutAccount.objects.get_or_create(seller=request.seller)
    form = SellerPayoutAccountForm(request.POST or None, instance=account)
    if request.method == 'POST' and form.is_valid():
        payout_account = form.save(commit=False)
        payout_account.seller = request.seller
        payout_account.is_verified = False
        payout_account.save()
        messages.success(request, 'Payout settings saved and marked for verification.')
        return redirect('marketplace:payouts')
    return render(request, 'marketplace/payouts.html', {
        'form': form,
        'payouts': request.seller.payouts.all()[:25],
        **_earning_summary(request.seller),
    })


@seller_account_required
def documents(request):
    form = SellerDocumentForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        document = form.save(commit=False)
        document.seller = request.seller
        document.save()
        messages.success(request, 'Document uploaded for verification.')
        return redirect('marketplace:documents')
    return render(request, 'marketplace/documents.html', {
        'form': form, 'documents': request.seller.documents.all()[:50],
    })


@seller_account_required
def settings(request):
    form = SellerSettingsForm(request.POST or None, request.FILES or None, instance=request.seller)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Seller settings updated.')
        return redirect('marketplace:settings')
    return render(request, 'marketplace/settings.html', {'form': form})


@seller_account_required
def notifications(request):
    if request.method == 'POST':
        request.seller.notifications.filter(is_read=False).update(is_read=True)
        return redirect('marketplace:notifications')
    page_obj = Paginator(request.seller.notifications.all(), 25).get_page(request.GET.get('page'))
    return render(request, 'marketplace/notifications.html', {'page_obj': page_obj})


def store_list(request):
    settings = marketplace_settings()
    if not settings.enabled or settings.mode != settings.Mode.MULTI_VENDOR:
        raise Http404('Marketplace stores are not available.')
    query = request.GET.get('q', '').strip()
    sellers = SellerProfile.objects.filter(
        verification_status=SellerProfile.VerificationStatus.APPROVED,
    ).annotate(
        product_count=Count('products', filter=Q(products__is_active=True), distinct=True),
        real_rating=Avg('products__reviews__rating', filter=Q(
            products__reviews__moderation_status=ProductReview.ModerationStatus.APPROVED,
        )),
        real_review_count=Count('products__reviews', filter=Q(
            products__reviews__moderation_status=ProductReview.ModerationStatus.APPROVED,
        ), distinct=True),
    )
    if query:
        sellers = sellers.filter(Q(store_name__icontains=query) | Q(description__icontains=query) | Q(city__icontains=query))
    page_obj = Paginator(sellers.order_by('store_name', 'id'), 18).get_page(request.GET.get('page'))
    return render(request, 'marketplace/store_list.html', {'page_obj': page_obj, 'query': query})


def store_detail(request, slug):
    settings = marketplace_settings()
    if not settings.enabled or settings.mode != settings.Mode.MULTI_VENDOR:
        raise Http404('Marketplace stores are not available.')
    seller = get_object_or_404(
        SellerProfile.objects.annotate(
            real_rating=Avg('products__reviews__rating', filter=Q(
                products__reviews__moderation_status=ProductReview.ModerationStatus.APPROVED,
            )),
            real_review_count=Count('products__reviews', filter=Q(
                products__reviews__moderation_status=ProductReview.ModerationStatus.APPROVED,
            ), distinct=True),
        ),
        slug=slug,
        verification_status=SellerProfile.VerificationStatus.APPROVED,
    )
    products = seller.products.select_related('brand', 'category', 'subcategory').filter(
        is_active=True, brand__is_active=True, category__is_active=True,
    ).order_by('-featured_product', '-created_at', '-id')
    query = request.GET.get('q', '').strip()
    if query:
        products = products.filter(
            Q(name__icontains=query) |
            Q(short_description__icontains=query) |
            Q(category__name__icontains=query) |
            Q(brand__name__icontains=query)
        )
    page_obj = Paginator(products, 18).get_page(request.GET.get('page'))
    page_obj.object_list = attach_pricing_to_products(list(page_obj.object_list))
    return render(request, 'marketplace/store_detail.html', {
        'seller': seller, 'page_obj': page_obj, 'query': query,
    })
