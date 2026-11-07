from django import forms
from django.utils.translation import gettext_lazy as _
from .models import KitchenBatch, BillOfMaterials, Material
from apps.products.models import Product

class KitchenBatchForm(forms.ModelForm):
    class Meta:
        model = KitchenBatch
        fields = ['product', 'planned_quantity', 'waste_rate', 'notes']
        widgets = {
            'product': forms.Select(attrs={'class': 'w-full px-4 py-2.5 rounded-xl border border-amber-200 focus:ring-2 focus:ring-amber-500 bg-amber-50/20'}),
            'planned_quantity': forms.NumberInput(attrs={'class': 'w-full px-4 py-2.5 rounded-xl border border-amber-200 focus:ring-2 focus:ring-amber-500 bg-amber-50/20', 'placeholder': 'VD: 50'}),
            'waste_rate': forms.NumberInput(attrs={'class': 'w-full px-4 py-2.5 rounded-xl border border-amber-200 focus:ring-2 focus:ring-amber-500 bg-amber-50/20', 'placeholder': '5.0'}),
            'notes': forms.Textarea(attrs={'class': 'w-full px-4 py-2.5 rounded-xl border border-amber-200 focus:ring-2 focus:ring-amber-500 bg-amber-50/20', 'rows': 2, 'placeholder': _('Ghi chú mẻ bánh...')}),
        }

class BillOfMaterialsForm(forms.ModelForm):
    # Thêm trường nhập lượng cho 1 mẻ tiêu chuẩn để tiện cho Admin
    batch_quantity = forms.DecimalField(
        required=False,
        max_digits=10,
        decimal_places=3,
        label="Lượng nguyên liệu cho 1 mẻ tiêu chuẩn",
        widget=forms.NumberInput(attrs={
            'class': 'w-full px-4 py-2.5 rounded-xl border border-amber-200 focus:ring-2 focus:ring-amber-500 bg-amber-50/20',
            'step': '0.001',
            'placeholder': 'VD: 1.800 (hệ thống tự chia cho số bánh mẻ)'
        })
    )

    class Meta:
        model = BillOfMaterials
        fields = ['material', 'quantity_needed', 'waste_percentage']
        widgets = {
            'material': forms.Select(attrs={'class': 'w-full px-4 py-2.5 rounded-xl border border-amber-200 focus:ring-2 focus:ring-amber-500 bg-amber-50/20'}),
            'quantity_needed': forms.NumberInput(attrs={'class': 'w-full px-4 py-2.5 rounded-xl border border-amber-200 focus:ring-2 focus:ring-amber-500 bg-amber-50/20', 'step': '0.001', 'placeholder': '0.050'}),
            'waste_percentage': forms.NumberInput(attrs={'class': 'w-full px-4 py-2.5 rounded-xl border border-amber-200 focus:ring-2 focus:ring-amber-500 bg-amber-50/20', 'step': '0.1', 'placeholder': '5.0'}),
        }

class MaterialForm(forms.ModelForm):
    class Meta:
        model = Material
        fields = ['code', 'name', 'material_type', 'unit', 'stock_quantity', 'min_threshold', 'unit_cost']
        widgets = {
            'code': forms.TextInput(attrs={'class': 'w-full px-4 py-2.5 rounded-xl border border-amber-200 focus:ring-2 focus:ring-amber-500 bg-amber-50/20', 'placeholder': 'VD: NL_BOT_MI'}),
            'name': forms.TextInput(attrs={'class': 'w-full px-4 py-2.5 rounded-xl border border-amber-200 focus:ring-2 focus:ring-amber-500 bg-amber-50/20', 'placeholder': 'Tên nguyên liệu...'}),
            'material_type': forms.Select(attrs={'class': 'w-full px-4 py-2.5 rounded-xl border border-amber-200 focus:ring-2 focus:ring-amber-500 bg-amber-50/20'}),
            'unit': forms.TextInput(attrs={'class': 'w-full px-4 py-2.5 rounded-xl border border-amber-200 focus:ring-2 focus:ring-amber-500 bg-amber-50/20', 'placeholder': 'kg, g, lít, quả...'}),
            'stock_quantity': forms.NumberInput(attrs={'class': 'w-full px-4 py-2.5 rounded-xl border border-amber-200 focus:ring-2 focus:ring-amber-500 bg-amber-50/20', 'step': '0.001'}),
            'min_threshold': forms.NumberInput(attrs={'class': 'w-full px-4 py-2.5 rounded-xl border border-amber-200 focus:ring-2 focus:ring-amber-500 bg-amber-50/20', 'step': '0.001'}),
            'unit_cost': forms.NumberInput(attrs={'class': 'w-full px-4 py-2.5 rounded-xl border border-amber-200 focus:ring-2 focus:ring-amber-500 bg-amber-50/20', 'step': '1000'}),
        }

