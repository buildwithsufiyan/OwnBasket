import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings


def _fernet():
    configured = settings.MOBILE_TOKEN_ENCRYPTION_KEY.strip()
    key = configured.encode() if configured else base64.urlsafe_b64encode(hashlib.sha256(settings.SECRET_KEY.encode()).digest())
    return Fernet(key)


def encrypt_provider_token(value):
    return _fernet().encrypt(value.encode()).decode()


def decrypt_provider_token(value):
    try:
        return _fernet().decrypt(value.encode()).decode()
    except InvalidToken as exc:
        raise ValueError('Push provider token cannot be decrypted with the active key.') from exc
