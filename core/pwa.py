from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.template.loader import render_to_string
from django.views.decorators.cache import cache_control
from django.views.decorators.http import require_GET


@require_GET
@cache_control(public=True, max_age=3600)
def manifest(request):
    payload = {
        'id': '/',
        'name': 'OwnBasket - Shop Smart, Live Better',
        'short_name': 'OwnBasket',
        'description': 'Mobile shopping for products, sellers, orders and wishlists.',
        'start_url': '/home/?source=pwa',
        'scope': '/',
        'display': 'standalone',
        'display_override': ['window-controls-overlay', 'standalone', 'minimal-ui'],
        'background_color': '#ffffff',
        'theme_color': '#ffb800',
        'orientation': 'any',
        'lang': 'en',
        'dir': 'ltr',
        'categories': ['shopping', 'lifestyle'],
        'icons': [
            {'src': '/static/images/pwa/icon-192.png', 'sizes': '192x192', 'type': 'image/png', 'purpose': 'any'},
            {'src': '/static/images/pwa/icon-512.png', 'sizes': '512x512', 'type': 'image/png', 'purpose': 'any'},
            {'src': '/static/images/pwa/icon-maskable-512.png', 'sizes': '512x512', 'type': 'image/png', 'purpose': 'maskable'},
        ],
        'shortcuts': [
            {'name': 'Shop products', 'short_name': 'Shop', 'url': '/shop/?source=pwa-shortcut', 'icons': [{'src': '/static/images/pwa/icon-192.png', 'sizes': '192x192'}]},
            {'name': 'My cart', 'short_name': 'Cart', 'url': '/cart/?source=pwa-shortcut', 'icons': [{'src': '/static/images/pwa/icon-192.png', 'sizes': '192x192'}]},
            {'name': 'My orders', 'short_name': 'Orders', 'url': '/my-orders/?source=pwa-shortcut', 'icons': [{'src': '/static/images/pwa/icon-192.png', 'sizes': '192x192'}]},
        ],
    }
    response = JsonResponse(payload)
    response['Content-Type'] = 'application/manifest+json'
    return response


@require_GET
@cache_control(no_cache=True, must_revalidate=True)
def service_worker(request):
    response = HttpResponse(render_to_string('pwa/service-worker.js', request=request), content_type='application/javascript; charset=utf-8')
    response['Service-Worker-Allowed'] = '/'
    response['X-Content-Type-Options'] = 'nosniff'
    return response


@require_GET
@cache_control(public=True, max_age=3600)
def offline(request):
    return render(request, 'pwa/offline.html')
