from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from apps.dashboard import views as dashboard_views

urlpatterns = [
    path('django-admin/', admin.site.urls),
    path('auth/', include('apps.authentication.urls', namespace='auth')),
    path('pos/', include('apps.pos.urls', namespace='pos')),
    path('products/', include('apps.products.urls', namespace='products')),
    path('custom-orders/', include('apps.custom_orders.urls', namespace='custom_orders')),
    path('kitchen/', include('apps.kitchen_bom.urls', namespace='kitchen')),
    path('inventory/', include('apps.inventory.urls', namespace='inventory')),
    path('employees/', include('apps.dashboard.employee_urls', namespace='employees')),
    path('i18n/', include('django.conf.urls.i18n')),
    path('set-language/<str:lang_code>/', dashboard_views.set_language_view, name='switch_language'),
    path('set-language/', dashboard_views.set_language_view, name='switch_language_query'),
    
    # PWA endpoints
    path('manifest.webmanifest', dashboard_views.pwa_manifest, name='pwa_manifest'),
    path('manifest.json', dashboard_views.pwa_manifest),
    path('sw.js', dashboard_views.pwa_sw, name='pwa_sw'),
    path('offline/', dashboard_views.pwa_offline, name='pwa_offline'),
    
    # Custom error testing
    path('test-403/', dashboard_views.test_403_view, name='test_403'),
    path('test-404/', dashboard_views.test_404_view, name='test_404'),

    # Mobile downloads
    path('download/', dashboard_views.download_hub_view, name='download_hub'),
    path('download/apk/<str:role>/', dashboard_views.download_apk_file, name='download_apk_role'),
    path('download/apk/', dashboard_views.download_apk_file, name='download_apk'),

    path('', include('apps.dashboard.urls', namespace='dashboard')),
]

handler403 = 'apps.dashboard.views.custom_permission_denied_view'
handler404 = 'apps.dashboard.views.custom_page_not_found_view'

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
