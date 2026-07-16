from datetime import timedelta
from functools import wraps

from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import PermissionDenied
from django.core.cache import cache
from django.db.models import Q
from django.shortcuts import render

from orders.models import Order, Refund

from .forms import validated_period
from .services import (brand_performance, category_performance, compare_periods,
                       coupon_performance, customer_performance, dashboard_summary,
                       inventory_performance, payment_performance, product_performance,
                       refund_performance, sales_trend, seller_performance,
                       status_breakdown)
from .services.exports import csv_response, excel_response


def finance_staff(view):
    @staff_member_required
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not (request.user.is_superuser or request.user.has_perm('orders.view_financial_reports')):
            raise PermissionDenied
        return view(request, *args, **kwargs)
    return wrapped


def _period_context(request):
    form, period = validated_period(request.GET)
    if period is None:
        return form, None, {'date_form': form}
    start, end = period
    duration = end - start
    comparison = compare_periods(start, end, start - duration, start)
    return form, period, {
        'date_form': form, 'start': start, 'end': end,
        'comparison': comparison,
        'query_string': request.GET.urlencode(),
    }


@finance_staff
def dashboard(request):
    form, period, context = _period_context(request)
    if period:
        start, end = period
        version = cache.get_or_set('analytics-cache-version', 1, None)
        cache_key = f'analytics:dashboard:v{version}:{start.isoformat()}:{end.isoformat()}'
        summary = cache.get(cache_key)
        if summary is None:
            summary = dashboard_summary(start, end)
            cache.set(cache_key, summary, 300)
        context.update({
            'summary': summary,
            'trend': sales_trend(start, end, request.GET.get('granularity', 'daily')),
            'statuses': status_breakdown(start, end),
            'payments': payment_performance(start, end),
            'top_products': product_performance(start, end)[:10],
            'granularity': request.GET.get('granularity', 'daily'),
        })
    return render(request, 'analytics/dashboard.html', context)


@finance_staff
def sales(request):
    form, period, context = _period_context(request)
    if period:
        start, end = period
        context.update({'trend': sales_trend(start, end, request.GET.get('granularity', 'daily')), 'statuses': status_breakdown(start, end), 'payments': payment_performance(start, end), 'granularity': request.GET.get('granularity', 'daily')})
    return render(request, 'analytics/sales.html', context)


@finance_staff
def products(request):
    form, period, context = _period_context(request)
    if period:
        start, end = period
        context.update({'products': product_performance(start, end)[:200], 'categories': category_performance(start, end)[:100], 'brands': brand_performance(start, end)[:100], 'inventory': inventory_performance()[:200]})
    return render(request, 'analytics/products.html', context)


@finance_staff
def customers(request):
    form, period, context = _period_context(request)
    if period:
        context.update({'customers': customer_performance(*period)[:200], 'coupons': coupon_performance(*period)[:100]})
    return render(request, 'analytics/customers.html', context)


@finance_staff
def sellers(request):
    form, period, context = _period_context(request)
    if period:
        context['sellers'] = seller_performance(*period)[:200]
    return render(request, 'analytics/sellers.html', context)


@finance_staff
def refunds(request):
    form, period, context = _period_context(request)
    if period:
        context['refunds'] = refund_performance(*period)[:200]
    return render(request, 'analytics/refunds.html', context)


@finance_staff
def tax(request):
    form, period, context = _period_context(request)
    if period:
        orders = Order.objects.filter(created_at__gte=period[0], created_at__lt=period[1]).exclude(tax_amount=0)
        context.update({'tax_orders': orders[:200], 'tax_data_available': orders.exists()})
    return render(request, 'analytics/tax.html', context)


def _export_definition(report, start, end):
    if report == 'orders':
        qs = Order.objects.filter(created_at__gte=start, created_at__lt=end).select_related('user').order_by('id')
        return ('Orders', ['Order', 'Date', 'Status', 'Payment method', 'Payment status', 'Gross', 'Discount', 'Tax', 'Shipping', 'Total'], ((o.pk, o.created_at, o.status, o.payment_method, o.payment_status, o.subtotal, o.discount_total, o.tax_amount, o.shipping_amount, o.total_price) for o in qs.iterator(chunk_size=1000)))
    if report == 'products':
        qs = product_performance(start, end)
        return ('Products', ['Product', 'SKU', 'Units sold', 'Gross sales', 'Net sales', 'Refund quantity', 'Stock', 'Views', 'Wishlists', 'Reviews', 'Average rating'], ((p.name, p.sku, p.units_sold, p.gross_sales, p.net_sales, p.refund_quantity, p.stock, p.total_views, p.real_wishlist_count, p.real_review_count, p.average_rating) for p in qs.iterator(chunk_size=500)))
    if report in ('categories', 'brands'):
        qs = category_performance(start, end) if report == 'categories' else brand_performance(start, end)
        title = 'Categories' if report == 'categories' else 'Brands'
        return (title, [title[:-1], 'Products', 'Orders', 'Units', 'Gross sales', 'Refunds', 'Net revenue', 'Average order value', 'Top product'], ((r.name, r.product_count, r.order_count, r.units_sold, r.revenue, r.refunds, r.net_revenue, r.average_order_value, r.top_product) for r in qs.iterator(chunk_size=500)))
    if report == 'sales':
        rows = sales_trend(start, end, 'daily')
        return ('Sales', ['Period', 'Orders', 'Gross sales', 'Discounts', 'Tax', 'Shipping', 'Refunds', 'Net revenue', 'Average order value'], ((r['period'], r['orders'], r['gross_sales'], r['discounts'], r['tax'], r['shipping'], r['refunds'], r['net_revenue'], r['average_order_value']) for r in rows))
    if report == 'refunds':
        qs = refund_performance(start, end)
        return ('Refunds', ['Refund', 'Date', 'Order', 'Product', 'Seller', 'Quantity', 'Amount', 'Reason'], ((r.pk, r.created_at, r.order_id, r.order_item.product.name if r.order_item_id else '', r.order_item.seller_name if r.order_item_id else '', r.quantity, r.amount, r.reason) for r in qs.iterator(chunk_size=500)))
    if report == 'taxes':
        qs = Order.objects.filter(created_at__gte=start, created_at__lt=end).exclude(tax_amount=0).order_by('id')
        return ('Taxes', ['Order', 'Date', 'State', 'Tax amount'], ((o.pk, o.created_at, o.customer_state, o.tax_amount) for o in qs.iterator(chunk_size=1000)))
    if report == 'customers':
        qs = customer_performance(start, end)
        return ('Customers', ['Customer ID', 'Joined', 'Orders', 'Total spend', 'Coupon orders'], ((u.pk, u.date_joined, u.order_count, u.total_spend, u.coupon_orders) for u in qs.iterator(chunk_size=500)))
    if report == 'sellers':
        qs = seller_performance(start, end)
        return ('Sellers', ['Seller', 'Orders', 'Units', 'Revenue', 'Commission', 'Refunds', 'Pending payout', 'Paid payout', 'Average rating', 'Active products', 'Low stock'], ((s.store_name, s.order_count, s.units_sold, s.revenue, s.commission, s.refunds, s.pending_payout, s.paid_payout, s.average_rating, s.active_products, s.low_stock_products) for s in qs.iterator(chunk_size=500)))
    if report == 'coupons':
        qs = coupon_performance(start, end)
        return ('Coupons', ['Coupon', 'Usage count', 'Attributed revenue', 'Attributed discount', 'Active'], ((c.code, c.usage_count, c.attributed_revenue, c.attributed_discount, c.is_active) for c in qs.iterator(chunk_size=500)))
    raise PermissionDenied('Unknown report type.')


@finance_staff
def export_report(request, report, file_format):
    if not (request.user.is_superuser or request.user.has_perm('orders.export_financial_reports')):
        raise PermissionDenied
    form, period = validated_period(request.GET)
    if period is None:
        return render(request, 'analytics/export_error.html', {'date_form': form}, status=400)
    title, headers, rows = _export_definition(report, *period)
    filename = f'ownbasket-{report}-{form.cleaned_data["resolved_start_date"]}-{form.cleaned_data["resolved_end_date"]}'
    if file_format == 'csv':
        return csv_response(filename, headers, rows)
    if file_format == 'xlsx':
        return excel_response(filename, title, headers, rows)
    raise PermissionDenied('Unsupported export format.')
