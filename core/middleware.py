from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse


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
        "/login/": (10, 300),
        "/register/": (5, 600),
        "/search/live/": (60, 60),
        "/api/search-suggestions/": (60, 60),
        "/checkout/": (10, 300),
        "/marketing/newsletter/subscribe/": (5, 600),
    }

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        config = self.LIMITS.get(request.path)
        if settings.RATE_LIMIT_ENABLED and config and request.method == "POST":
            limit, window = config
            forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip()
            client = forwarded or request.META.get("REMOTE_ADDR", "unknown")
            key = f"rate-limit:{request.path}:{client}"
            try:
                count = cache.incr(key)
            except ValueError:
                cache.set(key, 1, window)
                count = 1
            if count > limit:
                response = JsonResponse({"detail": "Too many requests. Please try again shortly."}, status=429)
                response["Retry-After"] = str(window)
                return response
        return self.get_response(request)
