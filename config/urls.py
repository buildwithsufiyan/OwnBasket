from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.views.decorators.cache import cache_page
from django.urls import path, include
from core.sitemaps import sitemaps
from themes.views import theme_asset

urlpatterns = [
    path('sitemap.xml', cache_page(3600)(sitemap), {'sitemaps': sitemaps}, name='django.contrib.sitemaps.views.sitemap'),
    path('admin/themes/', include('themes.urls')),
    path('theme-assets/<str:theme_folder>/<path:asset_path>', theme_asset, name='theme_asset'),
    path('admin/', admin.site.urls),

    path('', include('core.urls')),
    path('', include('products.urls')),
    path('', include('cart.urls')),
    path('', include('accounts.urls')),
    path('', include('orders.urls')),
    path('fonts/', include('fonts.urls')),
    
    path('wishlist/', include('wishlist.urls')),  # ← Add this
]

if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT
    )

handler400 = 'core.views.error_400'
handler403 = 'core.views.error_403'
handler404 = 'core.views.error_404'
handler500 = 'core.views.error_500'
