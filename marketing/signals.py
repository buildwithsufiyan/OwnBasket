from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.db.models.signals import post_migrate, post_save
from django.dispatch import receiver

from .models import LoyaltyAccount, NotificationPreference, ReferralCode


@receiver(post_save, sender=get_user_model())
def create_engagement_foundations(sender, instance, created, **kwargs):
    if not created or instance.is_superuser:
        return
    NotificationPreference.objects.get_or_create(user=instance)
    LoyaltyAccount.objects.get_or_create(user=instance)
    if not ReferralCode.objects.filter(user=instance).exists():
        ReferralCode.create_for_user(instance)


@receiver(post_migrate)
def ensure_marketing_manager_group(sender, **kwargs):
    if sender.name != 'marketing':
        return
    group, _ = Group.objects.get_or_create(name='Marketing Manager')
    codenames = (
        'view_newslettersubscription', 'change_newslettersubscription',
        'view_campaign', 'add_campaign', 'change_campaign',
        'send_test_campaign', 'schedule_campaign', 'view_campaign_results',
        'view_campaigndelivery', 'view_engagementdelivery', 'view_stockalert',
    )
    group.permissions.add(*Permission.objects.filter(content_type__app_label='marketing', codename__in=codenames))
