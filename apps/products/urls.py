from django.urls import path
from . import views

app_name = 'products'

urlpatterns = [
    path('', views.product_list, name='product_list'),
    path('add/', views.product_create, name='product_create'),
    path('<int:pk>/edit/', views.product_update, name='product_update'),
    path('<int:pk>/delete/', views.product_delete, name='product_delete'),
    
    path('coupons/', views.coupon_list, name='coupon_list'),
    path('coupons/add/', views.coupon_create, name='coupon_create'),
    path('coupons/<int:pk>/edit/', views.coupon_update, name='coupon_update'),
    path('coupons/<int:pk>/delete/', views.coupon_delete, name='coupon_delete'),
    
    path('api/validate-coupon/', views.api_validate_coupon, name='api_validate_coupon'),
]
