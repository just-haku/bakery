from django.urls import path
from . import employee_views

app_name = 'employees'

urlpatterns = [
    path('', employee_views.employee_list_view, name='employee_list'),
    path('create/', employee_views.employee_create_view, name='employee_create'),
    path('<int:user_id>/toggle-active/', employee_views.employee_toggle_active_view, name='employee_toggle_active'),
    path('<int:user_id>/delete/', employee_views.employee_delete_view, name='employee_delete'),
]
