from django.contrib import admin
from .models import Material, BillOfMaterials, KitchenBatch

@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'unit', 'stock_quantity', 'min_threshold', 'unit_cost')
    search_fields = ('code', 'name')

@admin.register(BillOfMaterials)
class BillOfMaterialsAdmin(admin.ModelAdmin):
    list_display = ('product', 'material', 'quantity_needed', 'waste_percentage')
    list_filter = ('product',)

@admin.register(KitchenBatch)
class KitchenBatchAdmin(admin.ModelAdmin):
    list_display = ('batch_code', 'product', 'planned_quantity', 'actual_quantity', 'status', 'created_at', 'completed_at')
    list_filter = ('status', 'product')
    search_fields = ('batch_code',)
