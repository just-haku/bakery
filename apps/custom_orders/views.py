from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
import json

from .models import CustomCakeOrder, CakeOrderStatus
from .forms import CustomCakeOrderForm
from apps.dashboard.models import StoreSetting

def custom_order_list(request):
    """Bảng Kanban / Danh sách theo dõi đơn đặt bánh kem hẹn trước"""
    status_filter = request.GET.get('status')
    orders = CustomCakeOrder.objects.all().order_by('pickup_datetime')

    if status_filter:
        orders = orders.filter(status=status_filter)

    received_orders = orders.filter(status=CakeOrderStatus.RECEIVED)
    baking_orders = orders.filter(status=CakeOrderStatus.BAKING)
    ready_orders = orders.filter(status=CakeOrderStatus.READY)
    delivered_orders = orders.filter(status=CakeOrderStatus.DELIVERED)

    return render(request, 'custom_orders/kanban.html', {
        'orders': orders,
        'received_orders': received_orders,
        'baking_orders': baking_orders,
        'ready_orders': ready_orders,
        'delivered_orders': delivered_orders,
        'status_filter': status_filter,
    })


def custom_order_create(request):
    """Tạo đơn đặt bánh kem mới (Thu ngân hoặc Khách hàng online)"""
    setting = StoreSetting.get_settings()

    if request.method == 'POST':
        form = CustomCakeOrderForm(request.POST, request.FILES)
        if form.is_valid():
            order = form.save()
            messages.success(request, f'Đã ghi nhận đơn đặt bánh kem: {order.order_code}! Tiền cọc đã nhận: {order.deposit_amount:,.0f} VNĐ.')
            return redirect('custom_orders:custom_order_detail', pk=order.pk)
    else:
        # Default pickup time: local time + 4 hours
        default_pickup = timezone.localtime() + timedelta(hours=4)
        form = CustomCakeOrderForm(initial={
            'pickup_datetime': default_pickup,
            'total_price': Decimal('380000'),
            'deposit_amount': Decimal('150000'),
        })

    return render(request, 'custom_orders/order_form.html', {
        'form': form,
        'setting': setting,
    })


def custom_order_detail(request, pk):
    """Xem chi tiết đơn bánh và sinh mã VietQR đặt cọc"""
    order = get_object_or_404(CustomCakeOrder, pk=pk)
    setting = StoreSetting.get_settings()

    # Sinh mã VietQR đặt cọc
    deposit_qr_url, deposit_desc = setting.generate_vietqr_url(order.deposit_amount, order.order_code)
    # Sinh mã VietQR phần tiền còn lại
    remaining_qr_url, remaining_desc = setting.generate_vietqr_url(order.remaining_amount, order.order_code)

    return render(request, 'custom_orders/order_detail.html', {
        'order': order,
        'setting': setting,
        'deposit_qr_url': deposit_qr_url,
        'deposit_desc': deposit_desc,
        'remaining_qr_url': remaining_qr_url,
        'remaining_desc': remaining_desc,
    })


@login_required
def api_update_cake_status(request, pk):
    """Cập nhật trạng thái tiến độ bánh (Dành cho Bếp & Quản lý)"""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Phương thức không hợp lệ'}, status=405)

    try:
        data = json.loads(request.body)
        new_status = data.get('status')
        if new_status not in CakeOrderStatus.values:
            return JsonResponse({'status': 'error', 'message': 'Trạng thái không hợp lệ'}, status=400)

        order = get_object_or_404(CustomCakeOrder, pk=pk)
        order.status = new_status
        order.save(update_fields=['status'])

        return JsonResponse({
            'status': 'success',
            'order_id': order.id,
            'new_status': order.status,
            'new_status_display': order.get_status_display(),
            'message': f'Đã cập nhật trạng thái đơn {order.order_code} thành: {order.get_status_display()}'
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
