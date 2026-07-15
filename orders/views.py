from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.db import transaction
from django.db.models import F, Q
from decimal import Decimal
from reportlab.pdfgen import canvas

from .models import Order, OrderItem
from cart.models import Cart, CartItem
from products.models import CouponRedemption
from products.pricing import build_cart_summary
from marketplace.models import SellerNotification
from marketing.models import EngagementDelivery, NotificationPreference
from marketing.services.email_service import send_branded_email



@login_required
def checkout(request):
    cart, _ = Cart.objects.get_or_create(id=request.user.id, defaults={'user': request.user})
    if cart.user_id != request.user.id:
        cart.user = request.user
        cart.save(update_fields=('user', 'updated_at'))
    items = CartItem.objects.filter(cart=cart, product__is_active=True).filter(
        Q(product__seller__isnull=True) |
        Q(product__seller__verification_status='approved')
    ).select_related('product', 'product__seller', 'product__brand', 'product__category')
    coupon_code = request.session.get('active_coupon_code', '')
    summary = build_cart_summary(items, user=request.user, coupon_code=coupon_code)

    if not items.exists():
        messages.error(request, "Your cart is empty.")
        return redirect('cart_detail')

    if request.method == "POST":
        with transaction.atomic():
            order = Order.objects.create(
                user=request.user,
                full_name=request.POST['full_name'],
                email=request.POST['email'],
                address=request.POST['address'],
                subtotal=summary.subtotal_original,
                discount_total=summary.total_discount,
                shipping_amount=summary.shipping_amount,
                coupon_code=summary.applied_coupon.code if summary.applied_coupon else '',
                total_price=summary.grand_total,
            )

            ordered_sellers = {}
            for line in summary.line_items:
                seller = line.item.product.seller
                line_total = line.unit_final_price * line.quantity
                commission_rate = seller.commission_rate if seller else Decimal('0.00')
                marketplace_commission = (
                    line_total * commission_rate / Decimal('100')
                ).quantize(Decimal('0.01'))
                OrderItem.objects.create(
                    order=order,
                    product=line.item.product,
                    quantity=line.quantity,
                    price=line.unit_final_price,
                    original_price=line.unit_original_price,
                    discount_amount=line.line_discount_total,
                    applied_offer_name=line.pricing.source_name or line.pricing.badge_text,
                    size=line.item.size,
                    color=line.item.color,
                    seller=seller,
                    seller_name=seller.store_name if seller else '',
                    marketplace_commission=marketplace_commission,
                    seller_earning=line_total - marketplace_commission,
                )
                if seller:
                    ordered_sellers[seller.pk] = seller
                type(line.item.product).objects.filter(pk=line.item.product.pk).update(
                    total_sold=F('total_sold') + line.quantity
                )

            SellerNotification.objects.bulk_create([
                SellerNotification(
                    seller=seller,
                    title=f'New order #{order.pk}',
                    message='A customer placed an order containing one or more of your products.',
                    link='/marketplace/seller/orders/',
                )
                for seller in ordered_sellers.values()
                if seller.order_notifications
            ])

            if summary.applied_coupon:
                CouponRedemption.objects.create(
                    coupon=summary.applied_coupon,
                    user=request.user,
                    order=order,
                )

            items.delete()
            cart.is_active = False
            cart.save(update_fields=('is_active', 'updated_at'))
            request.session.pop('active_coupon_code', None)

            if request.POST.get('marketing_consent') == 'on':
                preferences, _ = NotificationPreference.objects.get_or_create(user=request.user)
                preferences.promotional_emails = True
                preferences.record_consent(True, 'checkout')

        send_branded_email(
            subject=f'OwnBasket order #{order.pk} confirmation', recipient=order.email,
            template_name='order_confirmation',
            context={'order': order, 'order_url': request.build_absolute_uri(reverse('order_detail', args=(order.pk,)))},
            kind=EngagementDelivery.Kind.TRANSACTIONAL, reference=order.pk, user=request.user,
        )

        messages.success(
            request,
            "Order placed successfully!"
        )

        return redirect('order_success', order_id=order.id)

    return render(
        request,
        'orders/checkout.html',
        {
            'items': summary.items,
            'summary': summary,
            'total': summary.grand_total,
            'coupon_code': coupon_code,
        }
    )


@login_required
def order_success(request, order_id):
    order = get_object_or_404(
        Order.objects.prefetch_related('items__product'),
        id=order_id,
        user=request.user,
    )
    return render(request, 'orders/order_success.html', {'order': order})


@login_required
def my_orders(request):

    orders = Order.objects.filter(
        user=request.user
    ).order_by('-created_at')

    return render(
        request,
        'orders/my_orders.html',
        {'orders': orders}
    )


@login_required
def order_detail(request, order_id):
    order = get_object_or_404(
        Order.objects.prefetch_related('items__product'),
        id=order_id,
        user=request.user,
    )
    return render(request, 'orders/order_detail.html', {'order': order})

@login_required
def invoice_pdf(request, order_id):

    order = get_object_or_404(Order, id=order_id, user=request.user)

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="invoice_{order.id}.pdf"'

    p = canvas.Canvas(response)

    # Header
    p.setFont("Helvetica-Bold", 24)
    p.drawString(50, 800, "OWNCART")

    p.drawString(420, 800, "INVOICE")

    # Invoice Details
    p.setFont("Helvetica", 12)
    p.drawString(50, 760, f"Invoice No: INV-{order.id}")
    p.drawString(50, 740, f"Customer: {order.full_name}")
    p.drawString(50, 720, f"Email: {order.email}")
    p.drawString(50, 700, f"Total: Rs. {order.total_price}")

    # Product Section
    y = 650

    for item in order.items.all():

        p.drawString(
            50,
            y,
            f"{item.product.name}"
        )

        p.drawString(
            250,
            y,
            f"Qty: {item.quantity}"
        )

        p.drawString(
            350,
            y,
            f"Price: Rs. {item.price}"
        )

        y -= 25

    p.save()

    return response
