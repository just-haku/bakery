from django.urls import path
from . import views

app_name = 'pos'

urlpatterns = [
    path('', views.pos_screen, name='pos_screen'),
    path('orders/', views.order_list, name='order_list'),
    path('orders/<int:pk>/', views.order_detail, name='order_detail'),
    
    # API endpoints for touch interface
    path('api/search-products/', views.api_search_products, name='api_search_products'),
    path('api/lookup-customer/', views.api_lookup_customer, name='api_lookup_customer'),
    path('api/generate-vietqr/', views.api_generate_vietqr, name='api_generate_vietqr'),
    path('api/checkout/', views.api_checkout, name='api_checkout'),
]
