from django.shortcuts import redirect
from django.contrib import messages
from apps.authentication.models import User, UserRole
from apps.dashboard.utils import render_security_warning, custom_page_not_found_view

EXEMPT_PREFIXES = ('/static/', '/media/', '/i18n/', '/favicon.ico')
EXEMPT_EXACT = {'/sw.js', '/manifest.webmanifest', '/manifest.json', '/offline/'}


class PortalAccessMiddleware:
    """Multiport access control: CUSTOMER (8008), EMPLOYEE (8009), ADMIN (8010)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path

        if path.startswith(EXEMPT_PREFIXES) or path in EXEMPT_EXACT:
            return self.get_response(request)

        portal_role = request.META.get('HTTP_X_PORTAL_ROLE')
        if not portal_role:
            host = request.get_host().lower()
            if 'admin' in host:
                portal_role = 'ADMIN'
            elif 'employee' in host or 'staff' in host:
                portal_role = 'EMPLOYEE'
            elif 'customer' in host or 'shop' in host:
                portal_role = 'CUSTOMER'
            else:
                port = str(request.get_port())
                if port in ('8008', '9008'):
                    portal_role = 'CUSTOMER'
                elif port in ('8009', '9009'):
                    portal_role = 'EMPLOYEE'
                elif port in ('8010', '9010'):
                    portal_role = 'ADMIN'
                else:
                    portal_role = 'ADMIN'

        request.portal_role = portal_role

        if portal_role == 'CUSTOMER':
            if path == '/':
                return redirect('dashboard:online_catalog')

            blocked_prefixes = [
                '/pos/', '/kitchen/', '/inventory/',
                '/employees/', '/settings/', '/django-admin/',
                '/products/create/', '/products/delete/', '/products/coupons/',
                '/auth/admin-setup/'
            ]
            for prefix in blocked_prefixes:
                if path.startswith(prefix):
                    messages.error(request, 'Cổng Khách Hàng không có quyền truy cập khu vực này.')
                    return redirect('dashboard:online_catalog')

            if path in ('/custom-orders', '/custom-orders/') or '/api/update-status/' in path:
                messages.error(request, 'Khu vực này chỉ dành cho Nhân Viên vận hành.')
                return redirect('dashboard:online_catalog')

        elif portal_role == 'EMPLOYEE':
            if path.startswith('/auth/register/'):
                return render_security_warning(
                    request,
                    reason="Cổng Nhân Viên không hỗ trợ tự đăng ký. Vui lòng liên hệ Quản trị viên để được cấp tài khoản."
                )

            if path.startswith('/auth/admin-setup/'):
                return render_security_warning(
                    request,
                    reason="Khởi tạo quản trị viên chỉ được phép thực hiện trên Cổng Quản Trị."
                )

            if request.user.is_authenticated and request.user.role == UserRole.CUSTOMER:
                if not (path.startswith('/auth/logout') or path.startswith('/auth/login')):
                    return render_security_warning(
                        request,
                        reason="Tài khoản Khách Hàng không có quyền truy cập Cổng Nhân Viên."
                    )

            if path.startswith('/online/'):
                messages.info(request, 'Khu vực đặt hàng online chỉ hoạt động trên Cổng Khách Hàng.')
                return redirect('pos:pos_screen')

            admin_only_prefixes = [
                '/inventory/',
                '/employees/', '/settings/', '/django-admin/',
                '/products/create/', '/products/delete/', '/products/coupons/',
            ]
            for prefix in admin_only_prefixes:
                if path.startswith(prefix):
                    return render_security_warning(
                        request,
                        reason=f"Yêu cầu quyền Quản trị viên để truy cập ({prefix})."
                    )

        elif portal_role == 'ADMIN':
            if path.startswith('/online/'):
                messages.info(request, 'Khu vực đặt hàng online chỉ hoạt động trên Cổng Khách Hàng.')
                return redirect('dashboard:index')

            employee_only_prefixes = ['/pos/', '/kitchen/', '/custom-orders/']
            for prefix in employee_only_prefixes:
                if path.startswith(prefix):
                    messages.info(request, 'Khu vực vận hành POS/Bếp chỉ hoạt động trên Cổng Nhân Viên.')
                    return redirect('dashboard:index')

            if path.startswith('/auth/register/'):
                messages.info(request, 'Đăng ký tài khoản dành cho khách hàng tại Cổng Khách Hàng.')
                return redirect('auth:login')

            if path.startswith('/auth/admin-setup/'):
                if User.objects.filter(role=UserRole.ADMIN).exists():
                    messages.warning(request, 'Hệ thống đã có tài khoản Quản trị viên. Trang này đã đóng.')
                    return redirect('auth:login')

            if request.user.is_authenticated and request.user.role != UserRole.ADMIN:
                if not (path.startswith('/auth/logout') or path.startswith('/auth/login') or path.startswith('/download')):
                    return render_security_warning(
                        request,
                        reason="Yêu cầu quyền Quản trị viên để truy cập cổng này."
                    )

        response = self.get_response(request)

        if response.status_code == 404 and not path.startswith('/static/') and not path.startswith('/media/'):
            return custom_page_not_found_view(request)
        elif response.status_code == 403:
            return render_security_warning(request)

        return response
