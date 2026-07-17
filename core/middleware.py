from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse
import hashlib

from security.models import AuditEvent
from security.services import audit, client_ip, create_alert


class ContentSecurityPolicyMiddleware:
    """Add an environment-configurable CSP without coupling templates to a package."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        header = "Content-Security-Policy-Report-Only" if settings.CSP_REPORT_ONLY else "Content-Security-Policy"
        response.setdefault(header, settings.CSP_POLICY)
        if request.path.startswith(("/admin/", "/account/", "/checkout/", "/cart/", "/wishlist/", "/my-orders/", "/marketing/")):
            response.setdefault("X-Robots-Tag", "noindex, nofollow")
        return response


class RateLimitMiddleware:
    """Conservative production-only protection for high-risk POST endpoints."""

    LIMITS = {
        "/login/": (10, 300, ("POST",)),
        "/register/": (5, 600, ("POST",)),
        "/marketplace/seller/register/": (5, 600, ("POST",)),
        "/marketplace/seller/login/": (10, 300, ("POST",)),
        "/password-reset/": (5, 900, ("POST",)),
        "/search/live/": (60, 60, ("GET",)),
        "/api/search-suggestions/": (60, 60, ("GET",)),
        "/checkout/": (10, 300, ("POST",)),
        "/cart/apply-coupon/": (20, 300, ("POST",)),
        "/security/privacy-requests/": (5, 900, ("POST",)),
        "/security/two-factor/opt-in/": (5, 900, ("POST",)),
        "/security/two-factor/opt-out/": (5, 900, ("POST",)),
        "/marketing/newsletter/subscribe/": (5, 600, ("POST",)),
    }

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        config = self.LIMITS.get(request.path)
        if settings.RATE_LIMIT_ENABLED and config and request.method in config[2]:
            limit, window, _ = config
            client = client_ip(request) or "unknown"
            identity = self._identity(request)
            key = f"rate-limit:{request.path}:{client}:{identity}"
            try:
                count = cache.incr(key)
            except ValueError:
                cache.set(key, 1, window)
                count = 1
            if count > limit:
                audit('rate_limit_exceeded', category=AuditEvent.Category.SECURITY, request=request, success=False, metadata={'path': request.path, 'method': request.method})
                if cache.add(f'rate-alert:{key}', 1, window):
                    create_alert('rate_limit', f'Rate limit exceeded for {request.path}')
                response = JsonResponse({"detail": "Too many requests. Please try again shortly."}, status=429)
                response["Retry-After"] = str(window)
                return response
        return self.get_response(request)

    @staticmethod
    def _identity(request):
        if request.user.is_authenticated:
            return f'user-{request.user.pk}'
        identity_fields = {
            '/login/': ('username',),
            '/marketplace/seller/login/': ('username',),
            '/register/': ('username', 'email'),
            '/marketplace/seller/register/': ('username', 'email'),
            '/password-reset/': ('email',),
        }.get(request.path, ())
        value = '|'.join((request.POST.get(field) or '').strip().lower() for field in identity_fields)
        return hashlib.sha256(value.encode()).hexdigest()[:16] if value else ''
