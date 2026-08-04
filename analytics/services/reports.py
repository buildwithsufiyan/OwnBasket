from collections import defaultdict
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db.models import Avg, Case, Count, DecimalField, F, IntegerField, Max, OuterRef, Q, Subquery, Sum, Value, When
from django.db.models.functions import Coalesce, TruncDay, TruncMonth, TruncWeek, TruncYear

from marketplace.models import SellerPayout, SellerProfile
from orders.models import Order, OrderItem, Refund
from products.models import Brand, Category, Coupon, Product, ProductReview
from wishlist.models import Wishlist

from .revenue import (
    MONEY, ZERO, average_order_value, eligible_orders, financial_summary, gross_revenue,
    money_sum, order_total_aggregates, period_orders,
)


def dashboard_summary(start, end):
    User = get_user_model()
    all_orders = Order.objects.filter(created_at__gte=start, created_at__lt=end)
    valid = period_orders(start, end)
    finance = financial_summary(start, end)
    customers = User.objects.filter(is_staff=False, is_superuser=False)
    repeat = customers.annotate(valid_orders=Count('order', filter=Q(order__in=valid))).filter(valid_orders__gt=1)
    return {
        **finance,
        'total_orders': all_orders.count(),
        'paid_orders': all_orders.filter(payment_status=Order.PaymentStatus.PAID).count(),
        'pending_orders': all_orders.filter(status='Pending').count(),
        'cancelled_orders': 0,
        'refunded_orders': Refund.objects.filter(created_at__gte=start, created_at__lt=end).values('order_id').distinct().count(),
        'total_customers': customers.count(),
        'new_customers': customers.filter(date_joined__gte=start, date_joined__lt=end).count(),
        'repeat_customers': repeat.count(),
        'total_products': Product.objects.count(),
        'low_stock_products': Product.objects.filter(stock__gt=0, stock__lte=F('low_stock_alert')).count(),
        'active_sellers': SellerProfile.objects.filter(verification_status=SellerProfile.VerificationStatus.APPROVED).count(),
        'pending_seller_payouts': SellerPayout.objects.exclude(status__in=(SellerPayout.Status.PAID, SellerPayout.Status.FAILED)).aggregate(total=money_sum('amount'))['total'],
    }


def sales_trend(start, end, granularity='daily'):
    trunc = {'daily': TruncDay, 'weekly': TruncWeek, 'monthly': TruncMonth, 'yearly': TruncYear}.get(granularity, TruncDay)
    rows = list(period_orders(start, end).annotate(period=trunc('created_at')).values('period').annotate(
        **order_total_aggregates()
    ).order_by('period'))
    refunds = Refund.objects.filter(created_at__gte=start, created_at__lt=end).annotate(period=trunc('created_at')).values('period').annotate(total=Sum('amount'))
    refund_map = {row['period']: row['total'] or ZERO for row in refunds}
    for row in rows:
        row['refunds'] = refund_map.get(row['period'], ZERO)
        row['net_revenue'] = gross_revenue(row) - row['refunds']
        row['average_order_value'] = average_order_value(row['net_revenue'], row['orders'])
    return rows


def status_breakdown(start, end):
    counts = dict(Order.objects.filter(created_at__gte=start, created_at__lt=end).values_list('status').annotate(total=Count('id')))
    return [{'status': value, 'label': label, 'orders': counts.get(value, 0)} for value, label in Order.STATUS_CHOICES]


def payment_performance(start, end):
    return list(Order.objects.filter(created_at__gte=start, created_at__lt=end).values('payment_method').annotate(
        successful=Count('id', filter=Q(payment_status=Order.PaymentStatus.PAID) | Q(status='Delivered')),
        failed=Count('id', filter=Q(payment_status=Order.PaymentStatus.FAILED)),
        pending=Count('id', filter=Q(payment_status=Order.PaymentStatus.PENDING) & ~Q(status='Delivered')),
        refunded=Count('id', filter=Q(payment_status=Order.PaymentStatus.REFUNDED)),
        total_collected=money_sum('total_price', filter=Q(payment_status=Order.PaymentStatus.PAID) | Q(status='Delivered')),
        average_transaction=Coalesce(Avg('total_price', filter=Q(payment_status=Order.PaymentStatus.PAID) | Q(status='Delivered')), ZERO, output_field=MONEY),
    ).order_by('-total_collected', 'payment_method'))


def _item_sales_subquery(start, end, field):
    valid = Q(order__payment_status=Order.PaymentStatus.PAID) | Q(order__status='Delivered')
    qs = OrderItem.objects.filter(product_id=OuterRef('pk'), order__created_at__gte=start, order__created_at__lt=end).filter(valid).exclude(order__payment_status=Order.PaymentStatus.FAILED).values('product_id')
    expressions = {
        'units_sold': Sum('quantity'),
        'gross_sales': Sum(F('original_price') * F('quantity'), output_field=MONEY),
        'net_sales': Sum(F('price') * F('quantity'), output_field=MONEY),
    }
    return qs.annotate(value=expressions[field]).values('value')[:1]


def product_performance(start, end):
    refund_qty = Refund.objects.filter(order_item__product_id=OuterRef('pk'), created_at__gte=start, created_at__lt=end).values('order_item__product_id').annotate(value=Sum('quantity')).values('value')[:1]
    qs = Product.objects.select_related('category', 'brand', 'seller').annotate(
        units_sold=Coalesce(Subquery(_item_sales_subquery(start, end, 'units_sold'), output_field=IntegerField()), 0),
        gross_sales=Coalesce(Subquery(_item_sales_subquery(start, end, 'gross_sales'), output_field=MONEY), ZERO, output_field=MONEY),
        net_sales=Coalesce(Subquery(_item_sales_subquery(start, end, 'net_sales'), output_field=MONEY), ZERO, output_field=MONEY),
        refund_quantity=Coalesce(Subquery(refund_qty, output_field=IntegerField()), 0),
        real_review_count=Count('reviews', filter=Q(reviews__moderation_status=ProductReview.ModerationStatus.APPROVED), distinct=True),
        average_rating=Avg('reviews__rating', filter=Q(reviews__moderation_status=ProductReview.ModerationStatus.APPROVED)),
        real_wishlist_count=Count('wishlist', distinct=True),
    )
    return qs.annotate(
        average_selling_price=Case(When(units_sold__gt=0, then=F('net_sales') / F('units_sold')), default=Value(ZERO), output_field=MONEY),
        return_rate=Case(When(units_sold__gt=0, then=Value(Decimal('100')) * F('refund_quantity') / F('units_sold')), default=Value(ZERO), output_field=DecimalField(max_digits=8, decimal_places=2)),
    ).order_by('-net_sales', '-units_sold', 'name')


def _dimension_performance(model, dimension_field, start, end):
    valid_items = OrderItem.objects.filter(**{f'product__{dimension_field}_id': OuterRef('pk')}, order__created_at__gte=start, order__created_at__lt=end).filter(Q(order__payment_status=Order.PaymentStatus.PAID) | Q(order__status='Delivered')).exclude(order__payment_status=Order.PaymentStatus.FAILED).values(f'product__{dimension_field}_id')
    refunds = Refund.objects.filter(**{f'order_item__product__{dimension_field}_id': OuterRef('pk')}, created_at__gte=start, created_at__lt=end).values(f'order_item__product__{dimension_field}_id')
    top_product = valid_items.values('product__name').annotate(total=Sum(F('price') * F('quantity'), output_field=MONEY)).order_by('-total', 'product__name').values('product__name')[:1]
    qs = model.objects.annotate(
        units_sold=Coalesce(Subquery(valid_items.annotate(v=Sum('quantity')).values('v')[:1], output_field=IntegerField()), 0),
        revenue=Coalesce(Subquery(valid_items.annotate(v=Sum(F('original_price') * F('quantity'), output_field=MONEY)).values('v')[:1], output_field=MONEY), ZERO, output_field=MONEY),
        item_net_sales=Coalesce(Subquery(valid_items.annotate(v=Sum(F('price') * F('quantity'), output_field=MONEY)).values('v')[:1], output_field=MONEY), ZERO, output_field=MONEY),
        refunds=Coalesce(Subquery(refunds.annotate(v=Sum('amount')).values('v')[:1], output_field=MONEY), ZERO, output_field=MONEY),
        refund_count=Coalesce(Subquery(refunds.annotate(v=Count('id')).values('v')[:1], output_field=IntegerField()), 0),
        order_count=Coalesce(Subquery(valid_items.annotate(v=Count('order_id', distinct=True)).values('v')[:1], output_field=IntegerField()), 0),
        product_count=Count('product', distinct=True),
        top_product=Subquery(top_product),
    )
    return qs.annotate(
        net_revenue=F('item_net_sales') - F('refunds'),
        average_order_value=Case(When(order_count__gt=0, then=F('item_net_sales') / F('order_count')), default=Value(ZERO), output_field=MONEY),
    ).order_by('-net_revenue', 'name')


def category_performance(start, end):
    return _dimension_performance(Category, 'category', start, end)


def brand_performance(start, end):
    return _dimension_performance(Brand, 'brand', start, end)


def customer_performance(start, end):
    User = get_user_model()
    valid_filter = (Q(order__payment_status=Order.PaymentStatus.PAID) | Q(order__status='Delivered')) & ~Q(order__payment_status=Order.PaymentStatus.FAILED)
    return User.objects.filter(is_staff=False, is_superuser=False).annotate(
        order_count=Count('order', filter=valid_filter, distinct=True),
        total_spend=money_sum('order__total_price', filter=valid_filter),
        last_order=Max('order__created_at', filter=valid_filter),
        coupon_orders=Count('order', filter=valid_filter & Q(order__coupon_code__isnull=False) & ~Q(order__coupon_code=''), distinct=True),
    ).order_by('-total_spend', 'id')


def seller_performance(start, end, seller=None):
    qs = SellerProfile.objects.all()
    if seller is not None:
        qs = qs.filter(pk=seller.pk)
    items = OrderItem.objects.filter(seller_id=OuterRef('pk'), order__created_at__gte=start, order__created_at__lt=end).filter(Q(order__payment_status=Order.PaymentStatus.PAID) | Q(order__status='Delivered')).exclude(order__payment_status=Order.PaymentStatus.FAILED).values('seller_id')
    refund_rows = Refund.objects.filter(order_item__seller_id=OuterRef('pk'), created_at__gte=start, created_at__lt=end).values('order_item__seller_id')
    pending_payouts = SellerPayout.objects.filter(seller_id=OuterRef('pk')).exclude(status__in=(SellerPayout.Status.PAID, SellerPayout.Status.FAILED)).values('seller_id')
    paid_payouts = SellerPayout.objects.filter(seller_id=OuterRef('pk'), status=SellerPayout.Status.PAID).values('seller_id')
    return qs.annotate(
        units_sold=Coalesce(Subquery(items.annotate(v=Sum('quantity')).values('v')[:1], output_field=IntegerField()), 0),
        revenue=Coalesce(Subquery(items.annotate(v=Sum(F('price') * F('quantity'), output_field=MONEY)).values('v')[:1], output_field=MONEY), ZERO, output_field=MONEY),
        commission=Coalesce(Subquery(items.annotate(v=Sum('marketplace_commission')).values('v')[:1], output_field=MONEY), ZERO, output_field=MONEY),
        order_count=Coalesce(Subquery(items.annotate(v=Count('order_id', distinct=True)).values('v')[:1], output_field=IntegerField()), 0),
        refunds=Coalesce(Subquery(refund_rows.annotate(v=Sum('amount')).values('v')[:1], output_field=MONEY), ZERO, output_field=MONEY),
        active_products=Count('products', filter=Q(products__is_active=True), distinct=True),
        low_stock_products=Count('products', filter=Q(products__is_active=True, products__stock__gt=0, products__stock__lte=F('products__low_stock_alert')), distinct=True),
        average_rating=Avg('products__reviews__rating', filter=Q(products__reviews__moderation_status=ProductReview.ModerationStatus.APPROVED)),
        pending_payout=Coalesce(Subquery(pending_payouts.annotate(v=Sum('amount')).values('v')[:1], output_field=MONEY), ZERO, output_field=MONEY),
        paid_payout=Coalesce(Subquery(paid_payouts.annotate(v=Sum('amount')).values('v')[:1], output_field=MONEY), ZERO, output_field=MONEY),
    ).order_by('-revenue', 'store_name')


def refund_performance(start, end):
    return Refund.objects.filter(created_at__gte=start, created_at__lt=end).select_related('order', 'order_item__product', 'order_item__seller', 'payment').order_by('-created_at')


def coupon_performance(start, end):
    return Coupon.objects.annotate(
        usage_count=Count('redemptions', filter=Q(redemptions__used_at__gte=start, redemptions__used_at__lt=end)),
        attributed_revenue=money_sum('redemptions__order__total_price', filter=Q(redemptions__used_at__gte=start, redemptions__used_at__lt=end)),
        attributed_discount=money_sum('redemptions__order__discount_total', filter=Q(redemptions__used_at__gte=start, redemptions__used_at__lt=end)),
    ).order_by('-usage_count', 'code')


def inventory_performance():
    return Product.objects.select_related('category', 'brand', 'seller').annotate(
        stock_value=Case(When(cost_price__gt=0, then=F('cost_price') * F('stock')), default=Value(None), output_field=MONEY)
    ).order_by('stock', 'name')
