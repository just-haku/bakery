from django.urls import path
from . import views

app_name = 'auth'

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('admin-setup/', views.admin_setup_view, name='admin_setup'),
    path('logout/', views.logout_view, name='logout'),
    path('profile/', views.profile_view, name='profile'),
    path('api/topup-points/', views.api_topup_points, name='api_topup_points'),
    path('api/confirm-topup/', views.api_confirm_topup, name='api_confirm_topup'),
    path('api/subscribe-vip/', views.api_subscribe_vip, name='api_subscribe_vip'),
    path('api/confirm-vip/', views.api_confirm_vip, name='api_confirm_vip'),
    path('api/update-avatar/', views.api_update_avatar, name='api_update_avatar'),
]
