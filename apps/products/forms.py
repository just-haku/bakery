from django import forms
from django.utils.translation import gettext_lazy as _
from .models import Product, Category, Coupon, CouponDiscountType, CouponConditionType

class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['sku_code', 'name', 'category', 'price', 'stock_quantity', 'shelf_life_hours', 'is_custom_cake', 'image_url', 'image', 'status']
        widgets = {
            'sku_code': forms.TextInput(attrs={'class': 'w-full px-4 py-2.5 rounded-xl border border-amber-200 focus:ring-2 focus:ring-amber-500 bg-amber-50/20', 'placeholder': 'VD: B13'}),
            'name': forms.TextInput(attrs={'class': 'w-full px-4 py-2.5 rounded-xl border border-amber-200 focus:ring-2 focus:ring-amber-500 bg-amber-50/20', 'placeholder': _('Tên món bánh')}),
            'category': forms.Select(attrs={'class': 'w-full px-4 py-2.5 rounded-xl border border-amber-200 focus:ring-2 focus:ring-amber-500 bg-amber-50/20'}),
            'price': forms.NumberInput(attrs={'class': 'w-full px-4 py-2.5 rounded-xl border border-amber-200 focus:ring-2 focus:ring-amber-500 bg-amber-50/20', 'placeholder': _('Đơn giá (VNĐ)')}),
            'stock_quantity': forms.NumberInput(attrs={'class': 'w-full px-4 py-2.5 rounded-xl border border-amber-200 focus:ring-2 focus:ring-amber-500 bg-amber-50/20'}),
            'shelf_life_hours': forms.NumberInput(attrs={'class': 'w-full px-4 py-2.5 rounded-xl border border-amber-200 focus:ring-2 focus:ring-amber-500 bg-amber-50/20', 'placeholder': '24'}),
            'is_custom_cake': forms.CheckboxInput(attrs={'class': 'w-5 h-5 text-amber-600 rounded border-gray-300 focus:ring-amber-500'}),
            'image_url': forms.URLInput(attrs={'class': 'w-full px-4 py-2.5 rounded-xl border border-amber-200 focus:ring-2 focus:ring-amber-500 bg-amber-50/20', 'placeholder': 'https://...'}),
            'status': forms.Select(attrs={'class': 'w-full px-4 py-2.5 rounded-xl border border-amber-200 focus:ring-2 focus:ring-amber-500 bg-amber-50/20'}),
        }

class CouponForm(forms.ModelForm):
    class Meta:
        model = Coupon
        fields = ['code', 'title', 'discount_type', 'discount_value', 'max_discount_amount', 'min_order_amount', 'condition_type', 'valid_from', 'valid_to', 'usage_limit', 'is_active']
        widgets = {
            'code': forms.TextInput(attrs={'class': 'w-full px-4 py-2.5 rounded-xl border border-amber-200 focus:ring-2 focus:ring-amber-500 bg-amber-50/20 font-mono uppercase', 'placeholder': 'VD: GIAM20K'}),
            'title': forms.TextInput(attrs={'class': 'w-full px-4 py-2.5 rounded-xl border border-amber-200 focus:ring-2 focus:ring-amber-500 bg-amber-50/20', 'placeholder': _('Tên chương trình ưu đãi')}),
            'discount_type': forms.Select(attrs={'class': 'w-full px-4 py-2.5 rounded-xl border border-amber-200 focus:ring-2 focus:ring-amber-500 bg-amber-50/20'}),
            'discount_value': forms.NumberInput(attrs={'class': 'w-full px-4 py-2.5 rounded-xl border border-amber-200 focus:ring-2 focus:ring-amber-500 bg-amber-50/20', 'placeholder': _('% hoặc số tiền')}),
            'max_discount_amount': forms.NumberInput(attrs={'class': 'w-full px-4 py-2.5 rounded-xl border border-amber-200 focus:ring-2 focus:ring-amber-500 bg-amber-50/20', 'placeholder': _('0 = Không giới hạn')}),
            'min_order_amount': forms.NumberInput(attrs={'class': 'w-full px-4 py-2.5 rounded-xl border border-amber-200 focus:ring-2 focus:ring-amber-500 bg-amber-50/20', 'placeholder': '0'}),
            'condition_type': forms.Select(attrs={'class': 'w-full px-4 py-2.5 rounded-xl border border-amber-200 focus:ring-2 focus:ring-amber-500 bg-amber-50/20'}),
            'valid_from': forms.DateTimeInput(attrs={'class': 'w-full px-4 py-2.5 rounded-xl border border-amber-200 focus:ring-2 focus:ring-amber-500 bg-amber-50/20', 'type': 'datetime-local'}),
            'valid_to': forms.DateTimeInput(attrs={'class': 'w-full px-4 py-2.5 rounded-xl border border-amber-200 focus:ring-2 focus:ring-amber-500 bg-amber-50/20', 'type': 'datetime-local'}),
            'usage_limit': forms.NumberInput(attrs={'class': 'w-full px-4 py-2.5 rounded-xl border border-amber-200 focus:ring-2 focus:ring-amber-500 bg-amber-50/20'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'w-5 h-5 text-amber-600 rounded border-gray-300 focus:ring-amber-500'}),
        }
