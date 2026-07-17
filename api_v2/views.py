from django.urls import reverse

from .http import api_endpoint


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
            'jwt': {'available': False, 'status': 'planned-adapter'},
        },
        'endpoints': {
            'session': url('api-v2:session'), 'products': url('api-v2:products'),
            'categories': url('api-v2:categories'), 'brands': url('api-v2:brands'),
            'cart': url('api-v2:cart'), 'checkout': url('api-v2:checkout'),
            'orders': url('api-v2:orders'), 'wishlist': url('api-v2:wishlist'),
            'profile': url('api-v2:profile'), 'sellerDashboard': url('api-v2:seller-dashboard'),
            'pushDevices': url('api-v2:push-devices'), 'sync': url('api-v2:sync-capabilities'),
        },
    }


@api_endpoint(auth=True)
def sync_capabilities(request):
    return {
        'backgroundSync': {
            'enabled': True,
            'requiresOpenClientForCsrf': True,
            'supportedOperations': [
                'cart:add', 'cart:update', 'cart:remove',
                'wishlist:add', 'wishlist:remove',
            ],
            'excludedOperations': ['checkout', 'payment', 'profile:update', 'review:create'],
        },
        'push': {'deviceRegistration': True, 'deliveryConfigured': False},
    }
