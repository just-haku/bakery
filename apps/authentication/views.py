from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
import json

from .models import User, UserRole, CustomerProfile, VIPPackage, PointTransaction, PointTransactionType
from .forms import LoginForm, RegisterForm
from apps.dashboard.models import StoreSetting

from django.core.cache import cache
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

def get_client_ip(request):
    """Lấy địa chỉ IP của client (hỗ trợ reverse proxy / nginx header)"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '127.0.0.1')

def login_view(request):
    if request.user.is_authenticated:
        if request.user.role == UserRole.CASHIER:
            return redirect('pos:pos_screen')
        elif request.user.role == UserRole.BAKER:
            return redirect('kitchen:kitchen_screen')
        return redirect('dashboard:index')

    portal_role = getattr(request, 'portal_role', None)

    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            username_input = form.cleaned_data['username'].strip()
            password = form.cleaned_data['password']

            # Kiểm tra phòng chống Brute Force (Tối đa 5 lần thử sai trong 5 phút)
            client_ip = get_client_ip(request)
            rate_limit_key = f"login_attempts_{client_ip}_{username_input.lower()}"
            failed_attempts = cache.get(rate_limit_key, 0)

            if failed_attempts >= 5:
                messages.error(
                    request,
                    'Tài khoản tạm thời bị khóa do nhập sai thông tin quá 5 lần liên tiếp. '
                    'Vui lòng chờ 5 phút trước khi thử lại để đảm bảo an toàn!'
                )
                return render(request, 'auth/login.html', {'form': form})

            # Cho phép đăng nhập bằng cả username, email hoặc số điện thoại
            user = authenticate(request, username=username_input, password=password)
            if not user:
                try:
                    user_obj = User.objects.filter(phone=username_input).first() or User.objects.filter(email=username_input).first()
                    if user_obj:
                        user = authenticate(request, username=user_obj.username, password=password)
                except Exception:
                    user = None

            if user is not None:
                # Kiểm tra phân quyền truy cập theo Cổng (Portal Isolation)
                if portal_role == 'EMPLOYEE' and user.role == UserRole.CUSTOMER:
                    messages.error(
                        request,
                        'Tài khoản Khách Hàng không có quyền đăng nhập vào Cổng Vận Hành Nội Bộ (Port 8009). '
                        'Vui lòng truy cập Cổng Khách Hàng (Port 8008).'
                    )
                    return render(request, 'auth/login.html', {'form': form})

                if portal_role == 'ADMIN' and user.role != UserRole.ADMIN:
                    messages.error(
                        request,
                        'Chỉ Quản trị viên (Admin) mới có quyền đăng nhập vào Cổng Quản Trị Hệ Thống (Port 8010).'
                    )
                    return render(request, 'auth/login.html', {'form': form})

                if not user.is_active:
                    messages.error(request, 'Tài khoản của bạn đã bị vô hiệu hóa bởi Quản trị viên.')
                else:
                    # Đăng nhập thành công -> Xóa bộ đếm brute force
                    cache.delete(rate_limit_key)

                    login(request, user)
                    messages.success(request, f'Chào mừng {user.get_full_name() or user.username} quay trở lại!')
                    next_url = request.GET.get('next')
                    if next_url:
                        return redirect(next_url)
                    if user.role == UserRole.CASHIER:
                        return redirect('pos:pos_screen')
                    elif user.role == UserRole.BAKER:
                        return redirect('kitchen:kitchen_screen')
                    elif user.role == UserRole.CUSTOMER:
                        return redirect('dashboard:online_catalog')
                    return redirect('dashboard:index')
            else:
                # Tăng số lần thử sai và đặt thời gian chờ 5 phút
                cache.set(rate_limit_key, failed_attempts + 1, timeout=300)
                remaining = 5 - (failed_attempts + 1)
                if remaining > 0:
                    messages.error(request, f'Tên đăng nhập hoặc mật khẩu không chính xác. (Còn {remaining} lần thử)')
                else:
                    messages.error(request, 'Bạn đã nhập sai quá số lần quy định. Tài khoản bị tạm khóa 5 phút!')
    else:
        form = LoginForm()

    return render(request, 'auth/login.html', {'form': form})



def register_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard:online_catalog')

    # Nếu đang ở cổng nhân viên, từ chối
    if getattr(request, 'portal_role', None) == 'EMPLOYEE':
        messages.error(request, 'Cổng Nhân Viên (Port 8009) không cho phép tự đăng ký tài khoản.')
        return redirect('auth:login')

    if request.method == 'POST':
        form = RegisterForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save(commit=False)
            raw_password = form.cleaned_data['password']
            user.set_password(raw_password)

            # Khách hàng tự do đăng ký trên cổng 8008 luôn luôn là CUSTOMER
            user.role = UserRole.CUSTOMER
            user.is_staff = False
            user.is_superuser = False

            # Gán avatar placeholder sinh bằng AI tương ứng với giới tính đã chọn nếu chưa chọn ảnh
            gender = form.cleaned_data.get('gender', 'MALE')
            if not user.avatar:
                if gender == 'FEMALE':
                    user.avatar = 'avatars/avatar_female.jpg'
                elif gender == 'OTHER':
                    user.avatar = 'avatars/avatar_neutral.jpg'
                else:
                    user.avatar = 'avatars/avatar_male.jpg'

            user.save()

            login(request, user)
            messages.success(request, "Đăng ký tài khoản Khách Hàng thành công! Chào mừng bạn đến với tiệm bánh.")
            return redirect('dashboard:online_catalog')
    else:
        form = RegisterForm()

    return render(request, 'auth/register.html', {
        'form': form,
    })


@login_required
def api_update_avatar(request):
    """API cho phép khách hàng cập nhật ảnh đại diện cá nhân"""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Phương thức không hợp lệ'}, status=405)

    avatar_file = request.FILES.get('avatar')
    if not avatar_file:
        return JsonResponse({'status': 'error', 'message': 'Vui lòng chọn một tệp ảnh đại diện.'}, status=400)

    if avatar_file.size > 5 * 1024 * 1024:
        return JsonResponse({'status': 'error', 'message': 'Kích thước ảnh tối đa 5MB.'}, status=400)

    user = request.user
    user.avatar = avatar_file
    user.save(update_fields=['avatar'])

    return JsonResponse({
        'status': 'success',
        'message': 'Cập nhật ảnh đại diện thành công!',
        'avatar_url': user.avatar.url
    })


def admin_setup_view(request):
    """
    Trang khởi tạo tài khoản Quản trị viên ban đầu (Operator) DUY NHẤT 1 LẦN.
    Chỉ cho phép truy cập khi hệ thống CHƯA CÓ bất kỳ tài khoản ADMIN nào.
    Các Admin sau này phải do Admin đầu tiên tạo từ cổng Quản Trị (Port 8010).
    """
    admin_exists = User.objects.filter(role=UserRole.ADMIN).exists()
    if admin_exists:
        messages.warning(request, "Hệ thống đã có Quản trị viên ban đầu (Operator). Không thể khởi tạo lại!")
        return redirect('auth:login')

    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            raw_password = form.cleaned_data['password']
            user.set_password(raw_password)
            user.role = UserRole.ADMIN
            user.is_staff = True
            user.is_superuser = True
            user.is_active = True
            user.save()

            login(request, user)
            messages.success(request, f"Khởi tạo Quản trị viên ban đầu ({user.username}) thành công!")
            return redirect('dashboard:index')
    else:
        form = RegisterForm()

    return render(request, 'auth/admin_setup.html', {'form': form})


def logout_view(request):
    logout(request)
    messages.info(request, 'Bạn đã đăng xuất khỏi hệ thống.')
    return redirect('auth:login')


@login_required
def profile_view(request):
    user = request.user
    customer_profile, _ = CustomerProfile.objects.get_or_create(
        user=user,
        defaults={
            'phone': user.phone or f'USER_{user.id}',
            'full_name': user.get_full_name() or user.username
        }
    )
    transactions = customer_profile.point_transactions.order_by('-created_at')[:20]
    vip_packages = VIPPackage.objects.all()
    setting = StoreSetting.get_settings()

    return render(request, 'auth/profile.html', {
        'user': user,
        'profile': customer_profile,
        'transactions': transactions,
        'vip_packages': vip_packages,
        'setting': setting,
    })


@login_required
def api_topup_points(request):
    """Sinh mã VietQR để nạp điểm ví (1 điểm = 1.000 VNĐ)"""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Phương thức không hợp lệ'}, status=405)

    try:
        data = json.loads(request.body)
        points = int(data.get('points', 0))
        if points <= 0:
            return JsonResponse({'status': 'error', 'message': 'Số điểm nạp phải lớn hơn 0'}, status=400)

        amount_vnd = points * 1000
        setting = StoreSetting.get_settings()
        order_code = f"NAP{request.user.id}{int(timezone.now().timestamp())%100000}"
        qr_url, desc = setting.generate_vietqr_url(amount_vnd, order_code)

        return JsonResponse({
            'status': 'success',
            'points': points,
            'amount_vnd': amount_vnd,
            'qr_url': qr_url,
            'order_code': order_code,
            'desc': desc,
            'bank_id': setting.vietqr_bank_id,
            'account_no': setting.vietqr_account_no,
            'account_name': setting.vietqr_account_name,
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@login_required
def api_confirm_topup(request):
    """Xác nhận đã chuyển khoản thành công và cộng điểm ví"""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Phương thức không hợp lệ'}, status=405)

    try:
        data = json.loads(request.body)
        points = int(data.get('points', 0))
        order_code = data.get('order_code', '')

        if points <= 0:
            return JsonResponse({'status': 'error', 'message': 'Số điểm nạp không hợp lệ'}, status=400)

        profile, _ = CustomerProfile.objects.get_or_create(user=request.user)
        profile.points_balance += points
        profile.save(update_fields=['points_balance'])

        PointTransaction.objects.create(
            customer=profile,
            transaction_type=PointTransactionType.TOPUP,
            points=points,
            amount_money=Decimal(str(points * 1000)),
            payment_method='TRANSFER',
            notes=f'Nạp tiền qua VietQR ({order_code})'
        )

        return JsonResponse({
            'status': 'success',
            'message': f'Nạp thành công {points:,} điểm vào ví!',
            'new_balance': profile.points_balance,
            'points_in_vnd': profile.points_in_vnd,
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@login_required
def api_subscribe_vip(request):
    """Tạo mã VietQR mua / gia hạn gói hội viên VIP"""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Phương thức không hợp lệ'}, status=405)

    try:
        data = json.loads(request.body)
        package_id = data.get('package_id')
        package = get_object_or_404(VIPPackage, id=package_id)

        setting = StoreSetting.get_settings()
        order_code = f"VIP{request.user.id}{int(timezone.now().timestamp())%100000}"
        qr_url, desc = setting.generate_vietqr_url(package.price, order_code)

        return JsonResponse({
            'status': 'success',
            'package_name': package.name,
            'price': float(package.price),
            'qr_url': qr_url,
            'order_code': order_code,
            'desc': desc,
            'duration_days': package.duration_days,
            'bank_id': setting.vietqr_bank_id,
            'account_no': setting.vietqr_account_no,
            'account_name': setting.vietqr_account_name,
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@login_required
def api_confirm_vip(request):
    """Kích hoạt gói VIP sau khi chuyển khoản"""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Phương thức không hợp lệ'}, status=405)

    try:
        data = json.loads(request.body)
        package_id = data.get('package_id')
        package = get_object_or_404(VIPPackage, id=package_id)

        profile, _ = CustomerProfile.objects.get_or_create(user=request.user)
        profile.is_vip = True

        current_expiry = profile.vip_expiry_date
        now_date = timezone.now().date()
        if current_expiry and current_expiry > now_date:
            profile.vip_expiry_date = current_expiry + timedelta(days=package.duration_days)
        else:
            profile.vip_expiry_date = now_date + timedelta(days=package.duration_days)

        profile.save(update_fields=['is_vip', 'vip_expiry_date'])

        return JsonResponse({
            'status': 'success',
            'message': f'Chúc mừng bạn đã nâng cấp {package.name} thành công! Hạn dùng đến {profile.vip_expiry_date.strftime("%d/%m/%Y")}.',
            'expiry_date': profile.vip_expiry_date.strftime("%d/%m/%Y"),
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
