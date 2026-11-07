from django.contrib import admin
from .models import Order, OrderItem

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('order_code', 'order_type', 'cashier', 'customer', 'final_amount', 'payment_method', 'status', 'created_at')
    list_filter = ('order_type', 'payment_method', 'status', 'created_at')
    search_fields = ('order_code', 'recipient_phone')
    inlines = [OrderItemInline]

@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('order', 'product', 'quantity', 'unit_price', 'subtotal')
