from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.contrib import messages
from django.db import transaction
from django import forms
from django.utils.translation import gettext_lazy as _

from apps.authentication.models import User, UserRole

class EmployeeCreationForm(forms.Form):
    ROLE_CHOICES = [
        (UserRole.CASHIER, _('Thu ngân quầy POS (Cashier)')),
        (UserRole.BAKER, _('Thợ làm bánh (Baker)')),
        (UserRole.ADMIN, _('Quản trị viên bổ sung (Admin)')),
    ]

    username = forms.CharField(
        label=_("Tên đăng nhập / Email"),
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 rounded-xl border border-amber-200 focus:ring-2 focus:ring-amber-500 bg-amber-50/20 text-gray-800',
            'placeholder': 'nhanvien@bakery.local'
        })
    )
    first_name = forms.CharField(
        label=_("Họ và tên đệm"),
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 rounded-xl border border-amber-200 focus:ring-2 focus:ring-amber-500 bg-amber-50/20 text-gray-800',
            'placeholder': _('Nguyễn Văn')
        })
    )
    last_name = forms.CharField(
        label=_("Tên"),
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 rounded-xl border border-amber-200 focus:ring-2 focus:ring-amber-500 bg-amber-50/20 text-gray-800',
            'placeholder': _('An')
        })
    )
    phone = forms.CharField(
        label=_("Số điện thoại"),
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 rounded-xl border border-amber-200 focus:ring-2 focus:ring-amber-500 bg-amber-50/20 text-gray-800',
            'placeholder': '0988123456'
        })
    )
    role = forms.ChoiceField(
        label=_("Vị trí & Phân quyền"),
        choices=ROLE_CHOICES,
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-3 rounded-xl border border-amber-200 focus:ring-2 focus:ring-amber-500 bg-amber-50/20 text-gray-800 font-medium'
        })
    )
    password = forms.CharField(
        label=_("Mật khẩu đăng nhập"),
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-4 py-3 rounded-xl border border-amber-200 focus:ring-2 focus:ring-amber-500 bg-amber-50/20 text-gray-800',
            'placeholder': _('Tối thiểu 6 ký tự')
        })
    )

    def clean_username(self):
        username = self.cleaned_data['username'].strip()
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError("Tên đăng nhập này đã tồn tại trong hệ thống.")
        return username

    def clean_password(self):
        pwd = self.cleaned_data.get('password')
        if pwd:
            try:
                validate_password(pwd)
            except ValidationError as e:
                raise forms.ValidationError(e.messages)
        return pwd


@login_required
def employee_list_view(request):
    """Danh sách toàn bộ nhân viên và quản trị viên trong hệ thống"""
    if not request.user.is_admin_user:
        messages.error(request, "Bạn không có quyền truy cập khu vực Quản lý nhân viên.")
        return redirect('dashboard:index')

    employees = User.objects.filter(role__in=[UserRole.ADMIN, UserRole.CASHIER, UserRole.BAKER]).order_by('-date_joined')
    
    return render(request, 'dashboard/employees/list.html', {
        'employees': employees
    })

@login_required
def employee_create_view(request):
    """Admin tạo tài khoản cho nhân viên mới hoặc admin bổ sung"""
    if not request.user.is_admin_user:
        messages.error(request, "Chỉ Quản trị viên mới có quyền tạo tài khoản nhân viên.")
        return redirect('dashboard:index')

    if request.method == 'POST':
        form = EmployeeCreationForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            user = User.objects.create_user(
                username=data['username'],
                email=data['username'] if '@' in data['username'] else f"{data['username']}@bakery.local",
                password=data['password'],
                first_name=data['first_name'],
                last_name=data['last_name'],
                phone=data['phone'],
                role=data['role']
            )
            if data['role'] == UserRole.ADMIN:
                user.is_staff = True
                user.is_superuser = True
                user.save()

            messages.success(request, f"Tạo tài khoản nhân viên {user.get_full_name() or user.username} ({user.get_role_display()}) thành công!")
            return redirect('employees:employee_list')
    else:
        form = EmployeeCreationForm()

    return render(request, 'dashboard/employees/form.html', {'form': form})

@login_required
def employee_toggle_active_view(request, user_id):
    """Admin bật hoặc tắt trạng thái kích hoạt của nhân viên"""
    if not request.user.is_admin_user:
        messages.error(request, "Chỉ Quản trị viên mới có quyền thao tác.")
        return redirect('dashboard:index')

    target_user = get_object_or_404(User, id=user_id)

    if target_user.id == request.user.id:
        messages.error(request, "Bạn không thể tự vô hiệu hóa tài khoản của chính mình!")
        return redirect('employees:employee_list')

    target_user.is_active = not target_user.is_active
    target_user.save()

    status_str = "kích hoạt" if target_user.is_active else "vô hiệu hóa"
    messages.success(request, f"Đã {status_str} tài khoản {target_user.username} thành công.")
    return redirect('employees:employee_list')

@login_required
def employee_delete_view(request, user_id):
    """
    Xóa tài khoản nhân viên:
    Chỉ cho phép xóa nếu nhân viên CHƯA TỪNG phát sinh đơn hàng (Order) hoặc mẻ bánh (KitchenBatch).
    """
    if not request.user.is_admin_user:
        messages.error(request, "Chỉ Quản trị viên mới có quyền xóa nhân viên.")
        return redirect('dashboard:index')

    target_user = get_object_or_404(User, id=user_id)

    if target_user.id == request.user.id:
        messages.error(request, "Bạn không thể tự xóa tài khoản của chính mình!")
        return redirect('employees:employee_list')

    if not target_user.can_be_deleted():
        order_count = target_user.order_count
        batch_count = target_user.batch_count
        messages.error(
            request,
            f"Không thể xóa nhân viên {target_user.username} vì đã phát sinh "
            f"{order_count} hóa đơn bán hàng và {batch_count} mẻ bánh trong hệ thống. "
            f"Vui lòng sử dụng tính năng 'Vô hiệu hóa' để bảo vệ toàn vẹn lịch sử sổ sách!"
        )
        return redirect('employees:employee_list')

    username = target_user.username
    target_user.delete()
    messages.success(request, f"Đã xóa vĩnh viễn tài khoản nhân viên {username} thành công.")
    return redirect('employees:employee_list')
