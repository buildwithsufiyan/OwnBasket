from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class ScheduledReport(models.Model):
    class ReportType(models.TextChoices):
        ORDERS = 'orders', 'Orders'
        SALES = 'sales', 'Sales'
        PRODUCTS = 'products', 'Products'
        CATEGORIES = 'categories', 'Categories'
        BRANDS = 'brands', 'Brands'
        CUSTOMERS = 'customers', 'Customers'
        SELLERS = 'sellers', 'Sellers'
        REFUNDS = 'refunds', 'Refunds'
        COUPONS = 'coupons', 'Coupons'
        TAXES = 'taxes', 'Taxes'

    class Frequency(models.TextChoices):
        DAILY = 'daily', 'Daily'
        WEEKLY = 'weekly', 'Weekly'
        MONTHLY = 'monthly', 'Monthly'

    class Format(models.TextChoices):
        CSV = 'csv', 'CSV'
        XLSX = 'xlsx', 'Excel'

    report_type = models.CharField(max_length=40, choices=ReportType.choices)
    frequency = models.CharField(max_length=12, choices=Frequency.choices)
    recipient = models.EmailField()
    format = models.CharField(max_length=8, choices=Format.choices, default=Format.CSV)
    filters = models.JSONField(default=dict, blank=True)
    active = models.BooleanField(default=True, db_index=True)
    last_sent = models.DateTimeField(blank=True, null=True)
    next_run = models.DateTimeField(db_index=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='scheduled_reports')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('next_run', 'id')
        permissions = (('manage_scheduled_reports', 'Can manage scheduled reports'),)

    def clean(self):
        if not isinstance(self.filters, dict):
            raise ValidationError({'filters': 'Filters must be a JSON object.'})

    def __str__(self):
        return f'{self.report_type} to {self.recipient}'
