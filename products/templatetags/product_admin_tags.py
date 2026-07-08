from collections import OrderedDict
from datetime import timedelta

from django import template
from django.db.models import Count, F, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from orders.models import Order, OrderItem
from products.models import Product

register = template.Library()


@register.simple_tag
def product_dashboard_stats():
    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    return {
        'today_orders': Order.objects.filter(created_at__gte=today_start).count(),
        'today_revenue': Order.objects.filter(created_at__gte=today_start).aggregate(total=Sum('total_price'))['total'] or 0,
        'monthly_revenue': Order.objects.filter(created_at__gte=month_start).aggregate(total=Sum('total_price'))['total'] or 0,
        'total_products': Product.objects.count(),
        'low_stock_products': Product.objects.filter(stock__gt=0, stock__lte=F('low_stock_alert')).count(),
        'out_of_stock_products': Product.objects.filter(stock__lte=0).count(),
    }


@register.simple_tag
def dashboard_best_selling_products(limit=5):
    return Product.objects.order_by('-total_sold', '-total_views', 'name')[:limit]


@register.simple_tag
def dashboard_top_categories(limit=5):
    return (
        OrderItem.objects.values('product__category__name')
        .annotate(total_qty=Sum('quantity'), total_orders=Count('id'))
        .order_by('-total_qty', '-total_orders')[:limit]
    )


@register.simple_tag
def dashboard_recent_orders(limit=5):
    return Order.objects.select_related('user').order_by('-created_at')[:limit]


@register.simple_tag
def dashboard_sales_analytics(days=7):
    now = timezone.now()
    start_date = now.date() - timedelta(days=days - 1)
    labels = OrderedDict()
    for offset in range(days):
        current_date = start_date + timedelta(days=offset)
        labels[current_date] = {
            'label': current_date.strftime('%d %b'),
            'orders': 0,
            'revenue': 0,
        }

    daily_orders = (
        Order.objects.filter(created_at__date__gte=start_date)
        .annotate(day=TruncDate('created_at'))
        .values('day')
        .annotate(total_orders=Count('id'), total_revenue=Sum('total_price'))
        .order_by('day')
    )
    for row in daily_orders:
        day = row['day']
        if day in labels:
            labels[day]['orders'] = row['total_orders'] or 0
            labels[day]['revenue'] = row['total_revenue'] or 0
    return list(labels.values())
