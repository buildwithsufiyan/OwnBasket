from cryptography.fernet import Fernet
from django.conf import settings
from django.core.checks import Error, Warning, Tags, register


@register(Tags.security, deploy=True)
def mobile_api_security_checks(app_configs, **kwargs):
    messages = []
    key = settings.MOBILE_TOKEN_ENCRYPTION_KEY
    if settings.IS_PRODUCTION:
        try:
            Fernet(key.encode())
        except Exception:
            messages.append(Error(
                'MOBILE_TOKEN_ENCRYPTION_KEY must be a valid Fernet key.',
                id='api_v2.E001',
            ))
    elif not key:
        messages.append(Warning(
            'Push tokens use a development-only key derived from SECRET_KEY.',
            hint='Set MOBILE_TOKEN_ENCRYPTION_KEY before production.',
            id='api_v2.W001',
        ))
    if not 5 <= settings.MOBILE_ACCESS_TOKEN_MINUTES <= 60:
        messages.append(Error('MOBILE_ACCESS_TOKEN_MINUTES must be between 5 and 60.', id='api_v2.E002'))
    if not 1 <= settings.MOBILE_REFRESH_TOKEN_DAYS <= 90:
        messages.append(Error('MOBILE_REFRESH_TOKEN_DAYS must be between 1 and 90.', id='api_v2.E003'))
    if not settings.MOBILE_REFRESH_TOKEN_DAYS <= settings.MOBILE_SESSION_MAX_DAYS <= 365:
        messages.append(Error('MOBILE_SESSION_MAX_DAYS must be between refresh expiry and 365.', id='api_v2.E004'))
    return messages
