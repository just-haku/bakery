from django.contrib import admin
from .models import StoreSetting

@admin.register(StoreSetting)
class StoreSettingAdmin(admin.ModelAdmin):
    list_display = ('store_name', 'phone', 'vietqr_bank_id', 'vietqr_account_no', 'vietqr_account_name', 'default_shipping_fee')
