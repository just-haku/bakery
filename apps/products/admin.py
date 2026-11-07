from django.contrib import admin
from .models import Category, Product, Coupon

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'icon', 'is_active')
    prepopulated_fields = {'slug': ('name',)}

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('sku_code', 'name', 'category', 'price', 'stock_quantity', 'shelf_life_hours', 'status')
    list_filter = ('category', 'status', 'is_custom_cake')
    search_fields = ('name', 'sku_code')

@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ('code', 'title', 'discount_type', 'discount_value', 'condition_type', 'valid_from', 'valid_to', 'usage_limit', 'used_count', 'is_active')
    list_filter = ('condition_type', 'discount_type', 'is_active')
    search_fields = ('code', 'title')
