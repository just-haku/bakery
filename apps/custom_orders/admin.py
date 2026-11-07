from django.contrib import admin
from .models import CustomCakeOrder

@admin.register(CustomCakeOrder)
class CustomCakeOrderAdmin(admin.ModelAdmin):
    list_display = ('order_code', 'customer_name', 'customer_phone', 'cake_base', 'size', 'pickup_datetime', 'total_price', 'deposit_amount', 'status')
    list_filter = ('status', 'cake_base', 'size')
    search_fields = ('order_code', 'customer_name', 'customer_phone')
