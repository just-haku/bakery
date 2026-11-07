from django.shortcuts import render
from django.utils import timezone
from django.contrib.auth import get_user_model
from apps.authentication.models import UserRole

User = get_user_model()


def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '127.0.0.1')


def render_security_warning(request, reason=None, status=403):
    context = {
        'reason': reason or 'Bạn không có quyền truy cập khu vực này.',
        'current_time': timezone.now(),
        'client_ip': get_client_ip(request),
    }
    return render(request, '403.html', context, status=status)


def custom_page_not_found_view(request, exception=None):
    try:
        admin_user = User.objects.filter(role=UserRole.ADMIN).order_by('id').first()
        admin_email = getattr(admin_user, 'email', None) or 'admin@artisanbakery.vn'
    except Exception:
        admin_email = 'admin@artisanbakery.vn'

    return render(request, '404.html', {'admin_email': admin_email}, status=404)

