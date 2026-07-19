from django.urls import reverse
from django.core.cache import cache
from django.db import connection
from django.http import JsonResponse
from django.utils import timezone

from .http import ApiError, api_endpoint


@api_endpoint(public_cache_seconds=300)
def index(request):
    def url(name, *args):
        return request.build_absolute_uri(reverse(name, args=args))
    return {
        'name': 'OwnBasket Mobile API',
        'version': '2.0',
        'authentication': {
            'session': True,
            'csrfRequiredForUnsafeMethods': True,
            'bearer': {'available': True, 'format': 'opaque', 'refreshRotation': True, 'revocation': True},
            'jwt': {'available': False, 'reason': 'Opaque server-revocable credentials are used instead.'},
        },
        'endpoints': {
            'session': url('api-v2:session'), 'token': url('api-v2:token-login'),
            'tokenRefresh': url('api-v2:token-refresh'), 'openapi': url('api-v2:openapi'),
            'swagger': url('api-v2:swagger'), 'redoc': url('api-v2:redoc'),
            'products': url('api-v2:products'),
            'categories': url('api-v2:categories'), 'brands': url('api-v2:brands'),
            'cart': url('api-v2:cart'), 'checkout': url('api-v2:checkout'),
            'orders': url('api-v2:orders'), 'wishlist': url('api-v2:wishlist'),
            'profile': url('api-v2:profile'), 'sellerDashboard': url('api-v2:seller-dashboard'),
            'pushDevices': url('api-v2:push-devices'), 'sync': url('api-v2:sync-capabilities'),
            'syncBatch': url('api-v2:sync-batch'), 'health': url('api-v2:health'),
            'recommendations': url('api-v2:recommendations'), 'trending': url('api-v2:trending'),
            'intelligentSearch': url('api-v2:intelligent-search'),
        },
    }


@api_endpoint(auth=True)
def sync_capabilities(request):
    from .models import SyncState
    state, _ = SyncState.objects.get_or_create(user=request.user)
    return {
        'serverVersion': state.version,
        'backgroundSync': {
            'enabled': True,
            'requiresOpenClientForCsrf': False,
            'serverBatchEndpoint': reverse('api-v2:sync-batch'),
            'supportedOperations': [
                'cart:add', 'cart:update', 'cart:remove',
                'wishlist:add', 'wishlist:remove',
            ],
            'excludedOperations': ['checkout', 'payment', 'profile:update', 'review:create'],
            'conflictStrategy': 'base-version-and-client-action-id',
            'maximumBatchSize': 50,
        },
        'push': {'deviceRegistration': True, 'tokenRefresh': True, 'deliveryStatus': True, 'providerAdapters': True, 'providerCredentialsBundled': False},
    }


@api_endpoint(summary='API health and dependency readiness', tags=('Operations',))
def health(request):
    checks = {'database': False, 'cache': False}
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
            checks['database'] = cursor.fetchone()[0] == 1
    except Exception:
        pass
    try:
        marker = f'api-health-{timezone.now().timestamp()}'
        cache.set('api-health-probe', marker, 10)
        checks['cache'] = cache.get('api-health-probe') == marker
    except Exception:
        pass
    healthy = all(checks.values())
    return JsonResponse({'status': 'ok' if healthy else 'degraded', 'version': '2.0', 'checks': checks}, status=200 if healthy else 503)


@api_endpoint(auth=True, summary='Operational API counters', tags=('Operations',))
def metrics(request):
    if not request.user.is_staff:
        raise ApiError('permission_denied', 'Staff access is required.', 403)
    groups = ('2xx', '3xx', '4xx', '5xx')
    return {
        'requestsTotal': cache.get('api-metrics:requests:total', 0),
        'statusGroups': {group: cache.get(f'api-metrics:requests:status:{group}', 0) for group in groups},
        'lastRequestAtEpoch': cache.get('api-metrics:last-request-at'),
        'backend': 'django-cache',
    }
