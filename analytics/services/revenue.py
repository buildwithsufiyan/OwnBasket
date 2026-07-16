from decimal import Decimal

from django.db.models import Count, DecimalField, Q, Sum
from django.db.models.functions import Coalesce

from orders.models import Order, Refund

ZERO = Decimal('0.00')
MONEY = DecimalField(max_digits=18, decimal_places=2)


def eligible_orders(queryset=None):
    """Orders count as revenue when paid or operationally completed (Delivered).

    Failed payments are always excluded. Refunded orders remain in gross sales and
    their real Refund rows are subtracted, which supports partial refunds.
    """
    queryset = queryset if queryset is not None else Order.objects.all()
    return queryset.filter(
        Q(payment_status=Order.PaymentStatus.PAID) | Q(status='Delivered')
    ).exclude(payment_status=Order.PaymentStatus.FAILED)


def period_orders(start, end):
    return eligible_orders().filter(created_at__gte=start, created_at__lt=end)


def financial_summary(start, end):
    orders = period_orders(start, end)
    totals = orders.aggregate(
        orders=Count('id'),
        gross_sales=Coalesce(Sum('subtotal'), ZERO, output_field=MONEY),
        discounts=Coalesce(Sum('discount_total'), ZERO, output_field=MONEY),
        tax=Coalesce(Sum('tax_amount'), ZERO, output_field=MONEY),
        shipping=Coalesce(Sum('shipping_amount'), ZERO, output_field=MONEY),
    )
    refunds = Refund.objects.filter(created_at__gte=start, created_at__lt=end).aggregate(
        total=Coalesce(Sum('amount'), ZERO, output_field=MONEY)
    )['total']
    totals['refunds'] = refunds
    totals['total_revenue'] = (
        totals['gross_sales'] - totals['discounts'] + totals['tax'] + totals['shipping']
    )
    totals['net_revenue'] = (
        totals['total_revenue'] - refunds
    )
    totals['average_order_value'] = (
        (totals['net_revenue'] / totals['orders']).quantize(Decimal('0.01'))
        if totals['orders'] else ZERO
    )
    return totals


def compare_periods(start, end, previous_start, previous_end):
    current = financial_summary(start, end)
    previous = financial_summary(previous_start, previous_end)
    absolute = current['net_revenue'] - previous['net_revenue']
    percent = None if previous['net_revenue'] == 0 else (
        absolute / previous['net_revenue'] * Decimal('100')
    ).quantize(Decimal('0.01'))
    return {'current': current, 'previous': previous, 'absolute_change': absolute, 'percentage_change': percent}
