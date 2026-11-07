from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from .models import User, UserRole, CustomerProfile

class LoginForm(forms.Form):
    username = forms.CharField(
        label=_("Tên đăng nhập hoặc Email"),
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 rounded-xl border border-amber-200 focus:outline-none focus:ring-2 focus:ring-amber-500 bg-amber-50/30 text-gray-800 placeholder-gray-400 text-base',
            'placeholder': _('admin@bakery.local hoặc 0912345678'),
            'autofocus': True,
        })
    )
    password = forms.CharField(
        label=_("Mật khẩu"),
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-4 py-3 rounded-xl border border-amber-200 focus:outline-none focus:ring-2 focus:ring-amber-500 bg-amber-50/30 text-gray-800 placeholder-gray-400 text-base',
            'placeholder': '••••••••',
        })
    )

class RegisterForm(forms.ModelForm):
    username = forms.CharField(
        label=_("Tên tài khoản"),
        widget=forms.TextInput(attrs={'class': 'w-full px-4 py-3 rounded-xl border border-amber-200 focus:ring-2 focus:ring-amber-500 bg-amber-50/30', 'placeholder': _('Tên tài khoản')})
    )
    first_name = forms.CharField(
        label=_("Họ và tên đệm"),
        required=False,
        widget=forms.TextInput(attrs={'class': 'w-full px-4 py-3 rounded-xl border border-amber-200 focus:ring-2 focus:ring-amber-500 bg-amber-50/30', 'placeholder': _('Họ và tên đệm')})
    )
    last_name = forms.CharField(
        label=_("Tên"),
        required=False,
        widget=forms.TextInput(attrs={'class': 'w-full px-4 py-3 rounded-xl border border-amber-200 focus:ring-2 focus:ring-amber-500 bg-amber-50/30', 'placeholder': _('Tên')})
    )
    email = forms.EmailField(
        label=_("Email liên hệ"),
        required=False,
        widget=forms.EmailInput(attrs={'class': 'w-full px-4 py-3 rounded-xl border border-amber-200 focus:ring-2 focus:ring-amber-500 bg-amber-50/30', 'placeholder': 'email@example.com'})
    )
    phone = forms.CharField(
        label=_("Số điện thoại"),
        required=False,
        widget=forms.TextInput(attrs={'class': 'w-full px-4 py-3 rounded-xl border border-amber-200 focus:ring-2 focus:ring-amber-500 bg-amber-50/30', 'placeholder': _('Số điện thoại (09xx...)')})
    )
    birthday = forms.DateField(
        label=_("Ngày sinh"),
        required=False,
        widget=forms.DateInput(attrs={'class': 'w-full px-4 py-3 rounded-xl border border-amber-200 focus:ring-2 focus:ring-amber-500 bg-amber-50/30', 'type': 'date'})
    )
    GENDER_CHOICES = [
        ('MALE', _('Nam (Anh)')),
        ('FEMALE', _('Nữ (Chị)')),
        ('OTHER', _('Khác / Không tiết lộ')),
    ]
    gender = forms.ChoiceField(
        label=_("Giới tính"),
        choices=GENDER_CHOICES,
        initial='MALE',
        required=False,
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-3 rounded-xl border border-amber-200 focus:ring-2 focus:ring-amber-500 bg-amber-50/30 font-medium'
        })
    )
    password = forms.CharField(
        label=_("Mật khẩu"),
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-4 py-3 rounded-xl border border-amber-200 focus:outline-none focus:ring-2 focus:ring-amber-500 bg-amber-50/30 text-gray-800 placeholder-gray-400 text-base',
            'placeholder': _('Tối thiểu 6 ký tự'),
        })
    )
    password_confirm = forms.CharField(
        label=_("Xác nhận mật khẩu"),
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-4 py-3 rounded-xl border border-amber-200 focus:outline-none focus:ring-2 focus:ring-amber-500 bg-amber-50/30 text-gray-800 placeholder-gray-400 text-base',
            'placeholder': _('Nhập lại mật khẩu'),
        })
    )

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'phone', 'birthday', 'password']

    def clean_phone(self):
        phone = self.cleaned_data.get('phone')
        if not phone:
            return None
        return phone

    def clean(self):
        cleaned_data = super().clean()
        p1 = cleaned_data.get('password')
        p2 = cleaned_data.get('password_confirm')
        if p1 and p2 and p1 != p2:
            self.add_error('password_confirm', _('Mật khẩu xác nhận không khớp.'))
        elif p1:
            try:
                validate_password(p1, self.instance)
            except ValidationError as e:
                self.add_error('password', e)
        return cleaned_data

