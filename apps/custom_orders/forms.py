from django import forms
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from datetime import timedelta
from decimal import Decimal
from .models import CustomCakeOrder

class CustomCakeOrderForm(forms.ModelForm):
    CAKE_BASE_CHOICES = [
        ('Vani', _('Cốt bánh Vani truyền thống')),
        ('Socola', _('Cốt bánh Chocolate Bỉ đậm vị')),
        ('Red Velvet', _('Cốt bánh Red Velvet nhung đỏ quý phái')),
        ('Matcha', _('Cốt bánh Trà xanh Matcha Nhật Bản')),
    ]
    CREAM_CHOICES = [
        ('Kem bơ sữa', _('Kem bơ sữa tươi béo ngậy')),
        ('Whipping cream', _('Whipping cream thanh mát ít ngọt')),
        ('Phô mai kem', _('Cream Cheese béo ngậy vị chua nhẹ')),
        ('Socola Ganache', _('Socola Ganache thượng hạng bóng bẩy')),
    ]
    SIZE_CHOICES = [
        ('16cm', _('Size 16cm (4 - 6 người ăn) - 280.000 VNĐ')),
        ('20cm', _('Size 20cm (6 - 10 người ăn) - 380.000 VNĐ')),
        ('25cm', _('Size 25cm (10 - 15 người ăn) - 520.000 VNĐ')),
        ('2 tầng', _('Bánh 2 tầng Tiệc (15 - 25 người ăn) - 850.000 VNĐ')),
    ]

    cake_base = forms.ChoiceField(
        label=_("Cốt bánh"),
        choices=CAKE_BASE_CHOICES,
        widget=forms.Select(attrs={'class': 'w-full px-4 py-2.5 rounded-xl border border-amber-200 focus:ring-2 focus:ring-amber-500 bg-amber-50/20'})
    )
    cream_flavor = forms.ChoiceField(
        label=_("Vị kem"),
        choices=CREAM_CHOICES,
        widget=forms.Select(attrs={'class': 'w-full px-4 py-2.5 rounded-xl border border-amber-200 focus:ring-2 focus:ring-amber-500 bg-amber-50/20'})
    )
    size = forms.ChoiceField(
        label=_("Kích thước"),
        choices=SIZE_CHOICES,
        widget=forms.Select(attrs={'class': 'w-full px-4 py-2.5 rounded-xl border border-amber-200 focus:ring-2 focus:ring-amber-500 bg-amber-50/20'})
    )

    class Meta:
        model = CustomCakeOrder
        fields = [
            'customer_name', 'customer_phone', 'cake_base', 'cream_flavor', 'size',
            'custom_message', 'notes', 'pickup_datetime', 'total_price', 'deposit_amount', 'sample_image_url'
        ]
        widgets = {
            'customer_name': forms.TextInput(attrs={'class': 'w-full px-4 py-2.5 rounded-xl border border-amber-200 focus:ring-2 focus:ring-amber-500 bg-amber-50/20', 'placeholder': _('Họ và tên người nhận')}),
            'customer_phone': forms.TextInput(attrs={'class': 'w-full px-4 py-2.5 rounded-xl border border-amber-200 focus:ring-2 focus:ring-amber-500 bg-amber-50/20', 'placeholder': '09xxxxxxxx'}),
            'custom_message': forms.TextInput(attrs={'class': 'w-full px-4 py-2.5 rounded-xl border border-amber-200 focus:ring-2 focus:ring-amber-500 bg-amber-50/20', 'placeholder': _('VD: Chúc Mừng Sinh Nhật Bé Bắp 3 Tuổi')}),
            'notes': forms.Textarea(attrs={'class': 'w-full px-4 py-2.5 rounded-xl border border-amber-200 focus:ring-2 focus:ring-amber-500 bg-amber-50/20', 'rows': 3, 'placeholder': _('Ghi chú đặc biệt: giảm đường, hoa quả tươi, tông màu nơ trang trí...')}),
            'pickup_datetime': forms.DateTimeInput(attrs={'class': 'w-full px-4 py-2.5 rounded-xl border border-amber-200 focus:ring-2 focus:ring-amber-500 bg-amber-50/20', 'type': 'datetime-local'}),
            'total_price': forms.NumberInput(attrs={'class': 'w-full px-4 py-2.5 rounded-xl border border-amber-200 focus:ring-2 focus:ring-amber-500 bg-amber-50/20', 'placeholder': '350000'}),
            'deposit_amount': forms.NumberInput(attrs={'class': 'w-full px-4 py-2.5 rounded-xl border border-amber-200 focus:ring-2 focus:ring-amber-500 bg-amber-50/20', 'placeholder': _('Tối thiểu 30% giá bánh')}),
            'sample_image_url': forms.URLInput(attrs={'class': 'w-full px-4 py-2.5 rounded-xl border border-amber-200 focus:ring-2 focus:ring-amber-500 bg-amber-50/20', 'placeholder': 'https://...'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        pickup = cleaned_data.get('pickup_datetime')
        total_price = cleaned_data.get('total_price')
        deposit = cleaned_data.get('deposit_amount')

        # 1. Kiểm tra hẹn giờ lấy bánh (phải ở thời điểm tương lai)
        if pickup:
            now_local = timezone.localtime()
            pickup_aware = timezone.make_aware(pickup) if timezone.is_naive(pickup) else pickup
            if pickup_aware < now_local:
                self.add_error('pickup_datetime', _('Thời gian hẹn lấy bánh không được ở trong quá khứ.'))

        # 2. Kiểm tra cọc tối thiểu 30% (TC04)
        if total_price and deposit is not None:
            is_valid, msg = CustomCakeOrder.validate_deposit(total_price, deposit)
            if not is_valid:
                self.add_error('deposit_amount', msg)

        return cleaned_data
