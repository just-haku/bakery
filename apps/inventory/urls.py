from django.urls import path
from . import views

app_name = 'inventory'

urlpatterns = [
    path('', views.stock_overview, name='stock_overview'),
    path('materials/', views.materials_list, name='materials_list'),
    path('materials/create/', views.material_create, name='material_create'),
    path('materials/<int:pk>/import/', views.material_import, name='material_import'),
    path('alerts/', views.expiry_alerts, name='expiry_alerts'),
    path('api/qr-stock-in/', views.api_qr_stock_in, name='api_qr_stock_in'),
]

