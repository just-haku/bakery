from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.index, name='index'),
    
    # Customer online portal
    path('online/', views.online_catalog, name='online_catalog'),
    path('online/cart/', views.online_cart, name='online_cart'),
    path('online/my-orders/', views.my_orders, name='my_orders'),
    path('online/api/checkout/', views.api_online_checkout, name='api_online_checkout'),
    
    # Store settings & audit
    path('settings/', views.store_settings_view, name='store_settings'),
    path('test-printing/', views.test_printing_view, name='test_printing'),
    path('dashboard/test-printing/', views.test_printing_view),
    path('audit-logs/', views.audit_logs_view, name='audit_logs'),
    path('dashboard/audit-logs/', views.audit_logs_view),
]
