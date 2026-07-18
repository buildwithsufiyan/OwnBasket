from uuid import UUID, uuid4

from django.utils.cache import patch_cache_control

from .context import reset_current_request, set_current_request
from .services import touch_session


class SecurityMonitoringMiddleware:
    SENSITIVE_PREFIXES = ('/admin/', '/account/', '/checkout/', '/cart/', '/wishlist/', '/my-orders/', '/marketplace/seller/', '/api/v2/')

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            request.security_request_id = str(UUID(request.headers.get('X-Request-ID', '')))
        except (ValueError, AttributeError):
            request.security_request_id = str(uuid4())
        token = set_current_request(request)
        try:
            response = self.get_response(request)
            if (
                getattr(request, 'user', None) and request.user.is_authenticated
                and getattr(request, 'mobile_session', None) is None
            ):
                touch_session(request)
        finally:
            reset_current_request(token)
        response.setdefault('X-Request-ID', request.security_request_id)
        response.setdefault('Permissions-Policy', 'camera=(), microphone=(), geolocation=(), payment=(self)')
        response.setdefault('Cross-Origin-Opener-Policy', 'same-origin')
        response.setdefault('X-Permitted-Cross-Domain-Policies', 'none')
        if request.path.startswith(self.SENSITIVE_PREFIXES) and not response.has_header('Cache-Control'):
            patch_cache_control(response, private=True, no_store=True, max_age=0)
        return response
