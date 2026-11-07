from django.urls import path
from . import views

app_name = 'custom_orders'

urlpatterns = [
    path('', views.custom_order_list, name='custom_order_list'),
    path('create/', views.custom_order_create, name='custom_order_create'),
    path('order/', views.custom_order_create, name='custom_order_order'),
    path('<int:pk>/', views.custom_order_detail, name='custom_order_detail'),
    path('<int:pk>/api/update-status/', views.api_update_cake_status, name='api_update_cake_status'),
]
