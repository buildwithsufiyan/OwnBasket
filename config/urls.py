from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
from themes.views import theme_asset

urlpatterns = [
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
