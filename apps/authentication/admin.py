from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, CustomerProfile, VIPPackage, PointTransaction

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'role', 'phone', 'is_staff', 'is_superuser')
    list_filter = ('role', 'is_staff', 'is_superuser', 'is_active')
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Thông tin tiệm bánh', {'fields': ('role', 'phone', 'birthday', 'avatar')}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('Thông tin tiệm bánh', {'fields': ('role', 'phone', 'birthday', 'avatar')}),
    )

@admin.register(CustomerProfile)
class CustomerProfileAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'phone', 'points_balance', 'tier', 'is_vip', 'vip_expiry_date', 'total_spent')
    list_filter = ('tier', 'is_vip')
    search_fields = ('full_name', 'phone')

@admin.register(VIPPackage)
class VIPPackageAdmin(admin.ModelAdmin):
    list_display = ('name', 'package_type', 'price', 'discount_percentage', 'duration_days')

@admin.register(PointTransaction)
class PointTransactionAdmin(admin.ModelAdmin):
    list_display = ('customer', 'transaction_type', 'points', 'amount_money', 'payment_method', 'created_at')
    list_filter = ('transaction_type', 'payment_method')
