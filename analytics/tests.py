from datetime import date, timedelta
from decimal import Decimal
from io import StringIO

from django.contrib.auth.models import Permission, User
from django.core.management import call_command
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from marketplace.models import SellerProfile
from orders.models import Order, OrderItem, PaymentTransaction, Refund
from products.models import Brand, Category, Coupon, CouponRedemption, Product

from .forms import DateRangeForm
from .models import ScheduledReport
from .services import (brand_performance, category_performance, compare_periods,
                       customer_performance, financial_summary, product_performance,
                       seller_performance)
from .services.exports import safe_cell


class AnalyticsServiceTests(TestCase):
    def setUp(self):
        self.now = timezone.now()
        self.start = self.now - timedelta(days=2)
        self.end = self.now + timedelta(days=1)
        self.customer = User.objects.create_user('customer', password='pw')
        self.category = Category.objects.create(name='Analytics category', slug='analytics-category')
        self.brand = Brand.objects.create(name='Analytics brand')
        self.product = Product.objects.create(
            name='Analytics product', slug='analytics-product', category=self.category,
            brand=self.brand, price=Decimal('100.00'), cost_price=Decimal('40.00'),
            stock=8, description='', short_description='', warranty='', return_policy='',
        )

    def order(self, *, status='Delivered', payment_status='pending', subtotal='100', discount='10', tax='5', shipping='3'):
        order = Order.objects.create(
            user=self.customer, full_name='Customer', email='buyer@example.com', address='Address',
            subtotal=Decimal(subtotal), discount_total=Decimal(discount), tax_amount=Decimal(tax),
            shipping_amount=Decimal(shipping), total_price=Decimal(subtotal) - Decimal(discount) + Decimal(tax) + Decimal(shipping),
            status=status, payment_status=payment_status,
        )
        OrderItem.objects.create(
            order=order, product=self.product, quantity=2, original_price=Decimal('50.00'),
            price=Decimal('45.00'), discount_amount=Decimal('10.00'), cost_price=Decimal('20.00'),
        )
        return order

    def test_revenue_definition_separates_components_and_aov(self):
        self.order()
        result = financial_summary(self.start, self.end)
        self.assertEqual(result['gross_sales'], Decimal('100'))
        self.assertEqual(result['discounts'], Decimal('10'))
        self.assertEqual(result['tax'], Decimal('5'))
        self.assertEqual(result['shipping'], Decimal('3'))
        self.assertEqual(result['net_revenue'], Decimal('98'))
        self.assertEqual(result['average_order_value'], Decimal('98.00'))

    def test_pending_incomplete_and_failed_orders_are_excluded(self):
        self.order(status='Pending')
        self.order(status='Delivered', payment_status='failed')
        self.assertEqual(financial_summary(self.start, self.end)['orders'], 0)

    def test_paid_order_is_included_before_delivery(self):
        self.order(status='Processing', payment_status='paid')
        self.assertEqual(financial_summary(self.start, self.end)['orders'], 1)

    def test_partial_refunds_adjust_net_revenue(self):
        order = self.order()
        Refund.objects.create(order=order, amount=Decimal('20.00'), quantity=1)
        Refund.objects.create(order=order, amount=Decimal('5.00'))
        result = financial_summary(self.start, self.end)
        self.assertEqual(result['refunds'], Decimal('25.00'))
        self.assertEqual(result['net_revenue'], Decimal('73.00'))

    def test_product_category_and_brand_aggregations(self):
        order = self.order()
        Refund.objects.create(order=order, order_item=order.items.first(), amount=Decimal('10'), quantity=1)
        product = product_performance(self.start, self.end).get(pk=self.product.pk)
        self.assertEqual(product.units_sold, 2)
        self.assertEqual(product.refund_quantity, 1)
        self.assertEqual(category_performance(self.start, self.end).get(pk=self.category.pk).units_sold, 2)
        self.assertEqual(brand_performance(self.start, self.end).get(pk=self.brand.pk).units_sold, 2)

    def test_customer_repeat_calculation(self):
        self.order()
        self.order(payment_status='paid', status='Processing')
        row = customer_performance(self.start, self.end).get(pk=self.customer.pk)
        self.assertEqual(row.order_count, 2)
        self.assertEqual(row.total_spend, Decimal('196'))

    def test_seller_isolation_and_commission(self):
        owner = User.objects.create_user('seller-owner', password='pw')
        other_owner = User.objects.create_user('other-seller', password='pw')
        seller = SellerProfile.objects.create(user=owner, store_name='Store A', slug='store-a', legal_name='A', business_email='a@example.com', business_phone='1', verification_status='approved')
        other = SellerProfile.objects.create(user=other_owner, store_name='Store B', slug='store-b', legal_name='B', business_email='b@example.com', business_phone='2', verification_status='approved')
        order = self.order()
        item = order.items.first(); item.seller = seller; item.marketplace_commission = Decimal('9.00'); item.save()
        rows = list(seller_performance(self.start, self.end, seller=seller))
        self.assertEqual([row.pk for row in rows], [seller.pk])
        self.assertEqual(rows[0].commission, Decimal('9.00'))
        self.assertNotEqual(rows[0].pk, other.pk)

    def test_comparison_handles_zero_denominator(self):
        self.order()
        result = compare_periods(self.start, self.end, self.start - timedelta(days=3), self.start)
        self.assertIsNone(result['percentage_change'])


class DateAndSecurityTests(TestCase):
    def test_custom_dates_are_inclusive_and_timezone_aware(self):
        today = timezone.localdate()
        form = DateRangeForm({'preset': 'custom', 'start_date': today, 'end_date': today})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['end'] - form.cleaned_data['start'], timedelta(days=1))
        self.assertTrue(timezone.is_aware(form.cleaned_data['start']))

    def test_invalid_and_future_ranges_are_rejected(self):
        today = timezone.localdate()
        reversed_form = DateRangeForm({'preset': 'custom', 'start_date': today, 'end_date': today - timedelta(days=1)})
        future_form = DateRangeForm({'preset': 'custom', 'start_date': today, 'end_date': today + timedelta(days=1)})
        self.assertFalse(reversed_form.is_valid())
        self.assertFalse(future_form.is_valid())

    def test_csv_injection_is_escaped(self):
        for value in ('=SUM(A1:A2)', '+cmd', '-1+2', '@formula'):
            self.assertTrue(safe_cell(value).startswith("'"))


class AnalyticsViewTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user('finance', password='pw', is_staff=True)

    def test_staff_without_finance_permission_is_forbidden(self):
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(reverse('analytics:dashboard')).status_code, 403)

    def test_finance_permission_allows_dashboard_but_not_export(self):
        self.staff.user_permissions.add(Permission.objects.get(codename='view_financial_reports'))
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(reverse('analytics:dashboard')).status_code, 200)
        self.assertEqual(self.client.get(reverse('analytics:export', args=('orders', 'csv'))).status_code, 403)

    def test_authorized_csv_is_streaming_private_and_utf8(self):
        self.staff.user_permissions.add(*Permission.objects.filter(codename__in=('view_financial_reports', 'export_financial_reports')))
        self.client.force_login(self.staff)
        response = self.client.get(reverse('analytics:export', args=('orders', 'csv')))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.streaming)
        self.assertEqual(response['Cache-Control'], 'no-store')
        self.assertTrue(b''.join(response.streaming_content).startswith('\ufeff'.encode()))

    def test_authorized_excel_has_workbook_signature(self):
        self.staff.user_permissions.add(*Permission.objects.filter(codename__in=('view_financial_reports', 'export_financial_reports')))
        self.client.force_login(self.staff)
        response = self.client.get(reverse('analytics:export', args=('orders', 'xlsx')))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content.startswith(b'PK'))
        self.assertEqual(response['Cache-Control'], 'no-store')

    def test_empty_dashboard_and_mobile_css_are_present(self):
        self.staff.user_permissions.add(Permission.objects.get(codename='view_financial_reports'))
        self.client.force_login(self.staff)
        response = self.client.get(reverse('analytics:dashboard'))
        self.assertContains(response, 'No eligible paid or delivered orders')
        with open('static/admin/analytics.css', encoding='utf-8') as stylesheet:
            self.assertIn('@media(max-width:480px)', stylesheet.read())

    def test_dashboard_query_count_is_bounded(self):
        self.staff.user_permissions.add(Permission.objects.get(codename='view_financial_reports'))
        self.client.force_login(self.staff)
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(reverse('analytics:dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertLess(len(queries), 40)

    def test_scheduled_report_dry_run_is_non_mutating(self):
        report = ScheduledReport.objects.create(report_type='orders', frequency='daily', recipient='finance@example.com', next_run=timezone.now() - timedelta(minutes=1), created_by=self.staff)
        output = StringIO()
        call_command('send_scheduled_reports', '--dry-run', stdout=output)
        report.refresh_from_db()
        self.assertIsNone(report.last_sent)
        self.assertIn('DRY RUN: 1', output.getvalue())
