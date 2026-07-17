"""Environment-aware settings for OwnBasket.

Local development works without a .env loader. Production configuration is supplied
by the process environment; see .env.example and docs/PRODUCTION_DEPLOYMENT.md.
"""

import os
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse


BASE_DIR = Path(__file__).resolve().parent.parent


def env_bool(name, default=False):
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def env_list(name, default=""):
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


ENVIRONMENT = os.getenv("DJANGO_ENV", "development").strip().lower()
DEBUG = env_bool("DJANGO_DEBUG", ENVIRONMENT != "production")
IS_PRODUCTION = ENVIRONMENT == "production" or not DEBUG

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    if IS_PRODUCTION:
        raise RuntimeError("DJANGO_SECRET_KEY must be set when production mode is enabled.")
    SECRET_KEY = "local-development-key-never-use-in-production"

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost,testserver")
if IS_PRODUCTION and not ALLOWED_HOSTS:
    raise RuntimeError("DJANGO_ALLOWED_HOSTS must contain at least one production host.")
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")
CSRF_FAILURE_VIEW = "api_v2.http.csrf_failure"

SITE_NAME = os.getenv("SITE_NAME", "OwnBasket")
SITE_DOMAIN = os.getenv("SITE_DOMAIN", ALLOWED_HOSTS[0] if ALLOWED_HOSTS else "localhost")
CANONICAL_BASE_URL = os.getenv(
    "CANONICAL_BASE_URL", f"{'https' if IS_PRODUCTION else 'http'}://{SITE_DOMAIN}"
).rstrip("/")
DEFAULT_META_DESCRIPTION = os.getenv(
    "DEFAULT_META_DESCRIPTION",
    "Shop quality products, trusted brands, and great offers at OwnBasket.",
)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sitemaps",
    "django.contrib.humanize",
    "accounts",
    "marketplace.apps.MarketplaceConfig",
    "marketing.apps.MarketingConfig",
    "products",
    "cart",
    "orders",
    "analytics.apps.AnalyticsConfig",
    "security.apps.SecurityConfig",
    "api_v2.apps.ApiV2Config",
    "personalization.apps.PersonalizationConfig",
    "core",
    "wishlist",
    "banners.apps.BannersConfig",
    "fonts.apps.FontsConfig",
    "site_sections.apps.SiteSectionsConfig",
    "themes",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
]
try:
    import whitenoise  # noqa: F401
except ImportError:
    if IS_PRODUCTION:
        raise RuntimeError("WhiteNoise is required in production; install requirements.txt")
else:
    MIDDLEWARE.append("whitenoise.middleware.WhiteNoiseMiddleware")

MIDDLEWARE += [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "core.middleware.PwaCachePolicyMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "core.middleware.RateLimitMiddleware",
    "core.middleware.ContentSecurityPolicyMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "security.middleware.SecurityMonitoringMiddleware",
]

ROOT_URLCONF = "config.urls"
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [BASE_DIR / "templates", BASE_DIR / "themes"],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
        "core.context_processors.seo_context",
        "core.context_processors.ecommerce_context",
        "themes.context_processors.theme_context",
    ]},
}]
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"


def database_from_url(value):
    parsed = urlparse(value)
    engines = {
        "postgres": "django.db.backends.postgresql",
        "postgresql": "django.db.backends.postgresql",
        "mysql": "django.db.backends.mysql",
        "sqlite": "django.db.backends.sqlite3",
    }
    if parsed.scheme not in engines:
        raise RuntimeError(f"Unsupported DATABASE_URL scheme: {parsed.scheme}")
    if parsed.scheme == "sqlite":
        name = unquote(parsed.path)
        if os.name == "nt" and name.startswith("/"):
            name = name[1:]
        return {"ENGINE": engines[parsed.scheme], "NAME": name or BASE_DIR / "db.sqlite3"}
    options = {key: values[-1] for key, values in parse_qs(parsed.query).items()}
    return {
        "ENGINE": engines[parsed.scheme],
        "NAME": unquote(parsed.path.lstrip("/")),
        "USER": unquote(parsed.username or ""),
        "PASSWORD": unquote(parsed.password or ""),
        "HOST": parsed.hostname or "",
        "PORT": str(parsed.port or ""),
        "CONN_MAX_AGE": int(os.getenv("DB_CONN_MAX_AGE", "60")),
        "CONN_HEALTH_CHECKS": True,
        "OPTIONS": options,
    }


DATABASE_URL = os.getenv("DATABASE_URL")
DATABASES = {"default": database_from_url(DATABASE_URL)} if DATABASE_URL else {
    "default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 12}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
LANGUAGE_CODE = os.getenv("DJANGO_LANGUAGE_CODE", "en-us")
TIME_ZONE = os.getenv("DJANGO_TIME_ZONE", "UTC")
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STORAGES = {
    "default": {"BACKEND": os.getenv("DEFAULT_FILE_STORAGE", "django.core.files.storage.FileSystemStorage")},
    "staticfiles": {"BACKEND": (
        "whitenoise.storage.CompressedManifestStaticFilesStorage"
        if IS_PRODUCTION
        else "django.contrib.staticfiles.storage.StaticFilesStorage"
    )},
}
MEDIA_URL = "/media/"
MEDIA_ROOT = Path(os.getenv("MEDIA_ROOT", BASE_DIR / "media"))
FILE_UPLOAD_MAX_MEMORY_SIZE = int(os.getenv("FILE_UPLOAD_MAX_MEMORY_SIZE", str(5 * 1024 * 1024)))
DATA_UPLOAD_MAX_MEMORY_SIZE = int(os.getenv("DATA_UPLOAD_MAX_MEMORY_SIZE", str(10 * 1024 * 1024)))

CACHE_URL = os.getenv("CACHE_URL")
if CACHE_URL:
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.redis.RedisCache", "LOCATION": CACHE_URL}}
else:
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "ownbasket"}}

SESSION_COOKIE_SECURE = env_bool("SESSION_COOKIE_SECURE", IS_PRODUCTION)
CSRF_COOKIE_SECURE = env_bool("CSRF_COOKIE_SECURE", IS_PRODUCTION)
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = env_bool("CSRF_COOKIE_HTTPONLY", False)
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = int(os.getenv("SESSION_COOKIE_AGE", str(14 * 24 * 60 * 60)))
SESSION_SAVE_EVERY_REQUEST = False
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", IS_PRODUCTION)
SECURE_HSTS_SECONDS = int(os.getenv("SECURE_HSTS_SECONDS", "31536000" if IS_PRODUCTION else "0"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("SECURE_HSTS_INCLUDE_SUBDOMAINS", IS_PRODUCTION)
SECURE_HSTS_PRELOAD = env_bool("SECURE_HSTS_PRELOAD", False)
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
X_FRAME_OPTIONS = "DENY"
if env_bool("TRUST_PROXY_SSL_HEADER", IS_PRODUCTION):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

CSP_REPORT_ONLY = env_bool("CSP_REPORT_ONLY", True)
CSP_POLICY = os.getenv(
    "CSP_POLICY",
    "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; "
    "img-src 'self' data: blob:; font-src 'self' data: https://cdn.jsdelivr.net https://fonts.gstatic.com; "
    "connect-src 'self'; frame-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'",
)
RATE_LIMIT_ENABLED = env_bool("RATE_LIMIT_ENABLED", IS_PRODUCTION)
TRUST_PROXY_HEADERS = env_bool("TRUST_PROXY_HEADERS", False)
SECURITY_SESSION_IDLE_SECONDS = int(os.getenv("SECURITY_SESSION_IDLE_SECONDS", "1800"))

EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = os.getenv("EMAIL_HOST", "")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "OwnBasket <noreply@localhost>")
MARKETING_HIGH_VALUE_THRESHOLD = os.getenv("MARKETING_HIGH_VALUE_THRESHOLD", "50000")
ABANDONED_CART_MIN_HOURS = int(os.getenv("ABANDONED_CART_MIN_HOURS", "24"))
ABANDONED_CART_MAX_REMINDERS = int(os.getenv("ABANDONED_CART_MAX_REMINDERS", "2"))
WISHLIST_REMINDER_DAYS = int(os.getenv("WISHLIST_REMINDER_DAYS", "14"))
WISHLIST_REMINDER_FREQUENCY_DAYS = int(os.getenv("WISHLIST_REMINDER_FREQUENCY_DAYS", "30"))

STRIPE_PUBLIC_KEY = os.getenv("STRIPE_PUBLIC_KEY", "")
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
PAYPAL_CLIENT_ID = os.getenv("PAYPAL_CLIENT_ID", "")
PAYPAL_CLIENT_SECRET = os.getenv("PAYPAL_CLIENT_SECRET", "")

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_HANDLERS = ["console"]
LOGGING_HANDLERS = {"console": {"class": "logging.StreamHandler", "formatter": "standard"}}
if os.getenv("DJANGO_LOG_FILE"):
    LOG_HANDLERS.append("file")
    LOGGING_HANDLERS["file"] = {
        "class": "logging.handlers.RotatingFileHandler",
        "filename": os.getenv("DJANGO_LOG_FILE"),
        "maxBytes": 5 * 1024 * 1024,
        "backupCount": 5,
        "formatter": "standard",
    }
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"standard": {"format": "{asctime} {levelname} {name}: {message}", "style": "{"}},
    "handlers": LOGGING_HANDLERS,
    "loggers": {
        "django": {"handlers": LOG_HANDLERS, "level": LOG_LEVEL, "propagate": False},
        "django.security": {"handlers": LOG_HANDLERS, "level": "WARNING", "propagate": False},
        "orders": {"handlers": LOG_HANDLERS, "level": LOG_LEVEL, "propagate": False},
        "payments": {"handlers": LOG_HANDLERS, "level": LOG_LEVEL, "propagate": False},
        "marketing": {"handlers": LOG_HANDLERS, "level": LOG_LEVEL, "propagate": False},
    },
}

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
