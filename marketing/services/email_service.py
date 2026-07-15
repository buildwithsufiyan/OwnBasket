import hashlib
import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

from marketing.models import EngagementDelivery


logger = logging.getLogger('marketing')


def recipient_hash(email):
    return hashlib.sha256(email.strip().lower().encode('utf-8')).hexdigest()


def send_branded_email(*, subject, recipient, template_name, context, kind, reference='', user=None):
    recipient = recipient.strip().lower()
    if not recipient or '\n' in recipient or '\r' in recipient or '\n' in subject or '\r' in subject:
        raise ValueError('Invalid email header value.')
    text_body = render_to_string(f'marketing/emails/{template_name}.txt', context)
    html_body = render_to_string(f'marketing/emails/{template_name}.html', context)
    delivery = {
        'user': user,
        'kind': kind,
        'reference': str(reference)[:100],
        'recipient_hash': recipient_hash(recipient),
    }
    try:
        message = EmailMultiAlternatives(
            subject=subject,
            body=text_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=(recipient,),
        )
        message.attach_alternative(html_body, 'text/html')
        sent = message.send(fail_silently=False)
    except Exception as exc:
        logger.warning('Email delivery failed kind=%s reference=%s error=%s', kind, reference, type(exc).__name__)
        EngagementDelivery.objects.create(
            **delivery, status=EngagementDelivery.Status.FAILED, error_code=type(exc).__name__[:40]
        )
        return False
    if sent:
        EngagementDelivery.objects.create(**delivery, status=EngagementDelivery.Status.SENT)
        return True
    EngagementDelivery.objects.create(**delivery, status=EngagementDelivery.Status.FAILED, error_code='backend_zero')
    return False
