from django.contrib import admin
from django.db.models import Count
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import path
from django.utils import timezone

from .models import (
    Campaign, CampaignDelivery, EngagementDelivery, LoyaltyAccount, LoyaltyTransaction,
    NewsletterSubscription, NotificationPreference, Referral, ReferralCode, StockAlert,
)
from .services.email_service import send_branded_email
from .services.segments import recipient_count


@admin.register(NewsletterSubscription)
class NewsletterSubscriptionAdmin(admin.ModelAdmin):
    list_display = ('id', 'masked_email', 'status', 'source', 'subscribed_at', 'unsubscribed_at', 'created_at')
    list_filter = ('status', 'source', 'created_at')
    search_fields = ('email',)
    readonly_fields = ('token_id', 'consent_recorded_at', 'subscribed_at', 'unsubscribed_at', 'confirmation_sent_at', 'created_at', 'updated_at')
    list_select_related = ('user',)
    list_per_page = 50

    @admin.display(description='Email')
    def masked_email(self, obj):
        name, _, domain = obj.email.partition('@')
        return f'{name[:2]}***@{domain}'


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = ('user', 'marketing_consent', 'promotional_emails', 'newsletter', 'updated_at')
    list_filter = ('marketing_consent', 'promotional_emails', 'newsletter')
    search_fields = ('user__username', 'user__email')
    readonly_fields = ('consent_recorded_at', 'consent_source', 'consent_withdrawn_at', 'updated_at')
    list_select_related = ('user',)


class CampaignDeliveryInline(admin.TabularInline):
    model = CampaignDelivery
    extra = 0
    can_delete = False
    readonly_fields = ('recipient_hash', 'status', 'error_code', 'sent_at')
    max_num = 50

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = ('name', 'status', 'target_segment', 'recipient_total', 'sent_count', 'failed_count', 'scheduled_at', 'created_by')
    list_filter = ('status', 'target_segment', 'created_at')
    search_fields = ('name', 'subject')
    autocomplete_fields = ('coupon',)
    readonly_fields = ('created_by', 'sent_count', 'failed_count', 'unsubscribed_count', 'created_at', 'updated_at', 'completed_at', 'recipient_total')
    list_select_related = ('coupon', 'created_by')
    list_per_page = 30
    inlines = (CampaignDeliveryInline,)
    fieldsets = (
        ('Campaign', {'fields': ('name', 'subject', 'preview_text', 'content')}),
        ('Targeting', {'fields': ('target_segment', 'recipient_total', 'coupon')}),
        ('Schedule', {'fields': ('starts_at', 'scheduled_at', 'status')}),
        ('Results', {'fields': ('sent_count', 'failed_count', 'unsubscribed_count', 'completed_at')}),
        ('Audit', {'fields': ('created_by', 'created_at', 'updated_at')}),
    )

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    def get_readonly_fields(self, request, obj=None):
        fields = list(super().get_readonly_fields(request, obj))
        if not request.user.has_perm('marketing.schedule_campaign'):
            fields.extend(('scheduled_at', 'status'))
        if obj and obj.status in {Campaign.Status.PROCESSING, Campaign.Status.SENT}:
            fields.extend(('name', 'subject', 'preview_text', 'content', 'target_segment', 'coupon', 'starts_at', 'scheduled_at', 'status'))
        return tuple(dict.fromkeys(fields))

    @admin.display(description='Recipients')
    def recipient_total(self, obj):
        return recipient_count(obj.target_segment) if obj and obj.target_segment else 0

    def get_urls(self):
        return [
            path('<int:campaign_id>/preview/', self.admin_site.admin_view(self.preview_view), name='marketing_campaign_preview'),
            path('<int:campaign_id>/test-email/', self.admin_site.admin_view(self.test_email_view), name='marketing_campaign_test_email'),
        ] + super().get_urls()

    def preview_view(self, request, campaign_id):
        campaign = get_object_or_404(Campaign.objects.select_related('coupon'), pk=campaign_id)
        return render(request, 'admin/marketing/campaign/preview.html', {
            **self.admin_site.each_context(request), 'campaign': campaign,
            'recipient_count': recipient_count(campaign.target_segment),
        })

    def test_email_view(self, request, campaign_id):
        if not request.user.has_perm('marketing.send_test_campaign') or request.method != 'POST':
            return HttpResponseForbidden()
        campaign = get_object_or_404(Campaign.objects.select_related('coupon'), pk=campaign_id)
        if not request.user.email:
            self.message_user(request, 'Your staff account needs an email address.', level='ERROR')
        else:
            send_branded_email(
                subject=f'[TEST] {campaign.subject}', recipient=request.user.email,
                template_name='campaign', context={'campaign': campaign, 'user': request.user, 'coupon': campaign.coupon, 'unsubscribe_url': '', 'preview_text': campaign.preview_text},
                kind=EngagementDelivery.Kind.CAMPAIGN, reference=f'test-{campaign.pk}', user=request.user,
            )
            self.message_user(request, 'Test email sent to your staff account email.')
        return redirect('admin:marketing_campaign_preview', campaign_id=campaign.pk)


@admin.register(StockAlert)
class StockAlertAdmin(admin.ModelAdmin):
    list_display = ('user', 'product', 'is_active', 'created_at', 'notified_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('user__username', 'product__name')
    list_select_related = ('user', 'product')


@admin.register(ReferralCode)
class ReferralCodeAdmin(admin.ModelAdmin):
    list_display = ('code', 'user', 'referral_count', 'created_at')
    search_fields = ('code', 'user__username')
    list_select_related = ('user',)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user').annotate(_referral_count=Count('referrals'))

    def referral_count(self, obj):
        return obj._referral_count


@admin.register(Referral)
class ReferralAdmin(admin.ModelAdmin):
    list_display = ('referral_code', 'referred_user', 'status', 'created_at', 'qualified_at')
    list_filter = ('status', 'created_at')
    search_fields = ('referral_code__code', 'referred_user__username')
    list_select_related = ('referral_code', 'referred_user')


@admin.register(LoyaltyAccount)
class LoyaltyAccountAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'ledger_balance', 'is_active', 'created_at')
    search_fields = ('user__username',)
    list_select_related = ('user',)

    def ledger_balance(self, obj):
        return obj.balance


@admin.register(LoyaltyTransaction)
class LoyaltyTransactionAdmin(admin.ModelAdmin):
    list_display = ('account', 'transaction_type', 'points', 'reference', 'created_by', 'created_at')
    list_filter = ('transaction_type', 'created_at')
    search_fields = ('account__user__username', 'reference')
    readonly_fields = ('created_by', 'created_at')
    list_select_related = ('account', 'account__user', 'created_by')

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    def has_change_permission(self, request, obj=None):
        return False if obj else super().has_change_permission(request, obj)


@admin.register(EngagementDelivery)
class EngagementDeliveryAdmin(admin.ModelAdmin):
    list_display = ('kind', 'reference', 'recipient_hash', 'status', 'error_code', 'sent_at')
    list_filter = ('kind', 'status', 'sent_at')
    readonly_fields = ('user', 'kind', 'reference', 'recipient_hash', 'status', 'error_code', 'sent_at')
    list_select_related = ('user',)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
