from django.core import signing


NEWSLETTER_SALT = 'ownbasket.marketing.newsletter.v1'
TOKEN_MAX_AGE = 60 * 60 * 24 * 30


def make_subscription_token(subscription):
    return signing.dumps({'token': str(subscription.token_id)}, salt=NEWSLETTER_SALT, compress=True)


def resolve_subscription_token(token, max_age=TOKEN_MAX_AGE):
    from marketing.models import NewsletterSubscription

    try:
        payload = signing.loads(token, salt=NEWSLETTER_SALT, max_age=max_age)
    except (signing.BadSignature, signing.SignatureExpired, TypeError, ValueError):
        return None
    return NewsletterSubscription.objects.filter(token_id=payload.get('token')).first()
