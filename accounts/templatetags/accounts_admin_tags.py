from django import template

from accounts.models import CustomerProfile

register = template.Library()


@register.simple_tag
def total_customers():
    return CustomerProfile.objects.filter(
        user__is_staff=False,
        user__is_superuser=False
    ).count()
