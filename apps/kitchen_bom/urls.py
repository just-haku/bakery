from django.urls import path
from . import views

app_name = 'kitchen'

urlpatterns = [
    path('', views.kitchen_screen, name='kitchen_screen'),
    path('bom/', views.bom_list, name='bom_list'),
    path('bom/<int:product_id>/', views.bom_detail, name='bom_detail'),
    path('bom/<int:pk>/delete/', views.bom_delete, name='bom_delete'),
    
    path('batches/create/', views.batch_create, name='batch_create'),
    path('batches/<int:pk>/complete/', views.batch_complete, name='batch_complete'),
    path('batches/<int:pk>/labels/', views.batch_print_labels, name='batch_print_labels'),
    path('batches/<int:pk>/print-labels/', views.batch_print_labels, name='batch_print_labels_alias'),
    path('reports/', views.batch_reports, name='batch_reports'),
    path('counter-barcodes/', views.counter_barcode_sheet, name='counter_barcode_sheet'),
    path('counter-sheet/', views.counter_barcode_sheet, name='counter_sheet'),
    
    path('api/preview-materials/', views.api_preview_batch_materials, name='api_preview_materials'),
]

