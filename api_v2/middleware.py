import json
import logging
import time

from django.core.cache import cache

from .auth import authenticate_access_token


logger = logging.getLogger('api_v2')


class MobileTokenAuthenticationMiddleware:
    """Authenticate Bearer credentials without changing session/CSRF behavior."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.mobile_session = None
        request.mobile_auth_error = None
        authorization = request.headers.get('Authorization', '')
        if authorization:
            scheme, separator, token = authorization.partition(' ')
            if scheme.lower() != 'bearer' or not separator or not token.strip():
                request.mobile_auth_error = 'invalid_authorization_header'
            else:
                session, error = authenticate_access_token(token.strip())
                if session:
                    request.user = session.user
                    request.mobile_session = session
                    request._dont_enforce_csrf_checks = True
                else:
                    request.mobile_auth_error = error
        return self.get_response(request)


class ApiObservabilityMiddleware:
    """Bounded API logs and cache-backed counters; never logs bodies or credentials."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.path.startswith('/api/v2/'):
            return self.get_response(request)
        started = time.perf_counter()
        response = self.get_response(request)
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        request_id = getattr(request, 'security_request_id', request.headers.get('X-Request-ID', ''))
        route = getattr(getattr(request, 'resolver_match', None), 'url_name', None) or 'unmatched'
        status_group = f'{response.status_code // 100}xx'
        for key in ('requests:total', f'requests:status:{status_group}', f'requests:route:{route}'):
            try:
                cache.incr(f'api-metrics:{key}')
            except ValueError:
                cache.set(f'api-metrics:{key}', 1, None)
        cache.set('api-metrics:last-request-at', time.time(), None)
        response.setdefault('Server-Timing', f'app;dur={elapsed_ms}')
        logger.info(json.dumps({
            'event': 'api_request', 'request_id': request_id, 'method': request.method,
            'route': route, 'status': response.status_code, 'duration_ms': elapsed_ms,
            'user_id': request.user.pk if getattr(request, 'user', None) and request.user.is_authenticated else None,
        }, separators=(',', ':')))
        if response.status_code >= 500:
            logger.error('api_error_hook request_id=%s route=%s status=%s', request_id, route, response.status_code)
        return response
