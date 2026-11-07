from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db import transaction
from django.utils import timezone
from decimal import Decimal
import json

from .models import Order, OrderItem, OrderStatus, PaymentMethod, OrderType, DeliveryType
from apps.products.models import Product, Category, Coupon, ProductStatus
from apps.authentication.models import CustomerProfile, PointTransaction, PointTransactionType
from apps.dashboard.models import StoreSetting, AuditLog, AuditActionType

@login_required
def pos_screen(request):
    """Màn hình cảm ứng POS tại quầy bán lẻ"""
    categories = Category.objects.filter(is_active=True)
    products = Product.objects.filter(status=ProductStatus.ACTIVE).select_related('category').order_by('name')
    setting = StoreSetting.get_settings()

    return render(request, 'pos/index.html', {
        'categories': categories,
        'products': products,
        'setting': setting,
    })


@login_required
def order_list(request):
    """Lịch sử hóa đơn bán hàng"""
    orders = Order.objects.select_related('cashier', 'customer').prefetch_related('items__product').all()
    q = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status')
    payment_filter = request.GET.get('payment')

    if q:
        orders = orders.filter(order_code__icontains=q) | orders.filter(recipient_phone__icontains=q)
    if status_filter:
        orders = orders.filter(status=status_filter)
    if payment_filter:
        orders = orders.filter(payment_method=payment_filter)

    return render(request, 'pos/order_list.html', {
        'orders': orders[:100],
        'search_query': q,
        'status_filter': status_filter,
        'payment_filter': payment_filter,
    })


@login_required
def order_detail(request, pk):
    """Chi tiết và in hóa đơn"""
    order = get_object_or_404(Order.objects.select_related('cashier', 'customer', 'coupon').prefetch_related('items__product'), pk=pk)
    setting = StoreSetting.get_settings()
    return render(request, 'pos/order_detail.html', {
        'order': order,
        'setting': setting,
    })


# ==========================================
# POS AJAX & API ENDPOINTS
# ==========================================

def api_search_products(request):
    """Tìm kiếm nhanh sản phẩm bánh qua SKU / Barcode / Tên"""
    q = request.GET.get('q', '').strip()
    cat_id = request.GET.get('category')

    products = Product.objects.filter(status=ProductStatus.ACTIVE).select_related('category')
    if cat_id:
        products = products.filter(category_id=cat_id)
    if q:
        products = products.filter(name__icontains=q) | products.filter(sku_code__icontains=q)

    data = []
    for p in products:
        freshness = p.get_freshness_status()
        data.append({
            'id': p.id,
            'sku_code': p.sku_code,
            'name': p.name,
            'original_price': float(p.price),
            'price': float(freshness['current_price']),
            'stock_quantity': p.stock_quantity,
            'category_name': p.category.name,
            'category_id': p.category.id,
            'is_in_stock': p.is_in_stock,
            'image_url': p.image_url or (p.image.url if p.image else None),
            'is_near_expiry': freshness.get('is_near_expiry', False),
            'discount_percent': freshness.get('discount_percent', 0),
            'status': freshness.get('status', 'FRESH'),
            'percentage_left': freshness.get('percentage_left', 100.0),
        })
    return JsonResponse({'status': 'success', 'products': data})


def api_lookup_customer(request):
    """
    Tra cứu khách hàng tại POS:
    - Tra cứu bằng SĐT: CHỈ TÍCH ĐIỂM (allow_redeem_points = False)
    - Quét Mã Vạch / QR Thẻ Hội Viên: ĐƯỢC TÍCH ĐIỂM & TIÊU ĐIỂM (allow_redeem_points = True)
    """
    query = (request.GET.get('query') or request.GET.get('phone') or request.GET.get('card_code') or '').strip()
    if not query:
        return JsonResponse({'status': 'error', 'message': 'Vui lòng cung cấp số điện thoại hoặc quét mã thẻ hội viên'}, status=400)

    customer = None
    allow_redeem_points = False
    lookup_method = 'PHONE'
    lookup_message = 'Tra cứu bằng SĐT: Chỉ tích điểm (Không thể dùng điểm để tránh rủi ro đọc trộm SĐT).'

    # 1. Quét Thẻ Hội Viên (bắt đầu bằng CUST- hoặc khớp member_card_code)
    if query.upper().startswith('CUST-') or CustomerProfile.objects.filter(member_card_code__iexact=query).exists():
        customer = CustomerProfile.objects.filter(member_card_code__iexact=query).first()
        if customer:
            allow_redeem_points = True
            lookup_method = 'CARD_CODE'
            lookup_message = 'Quét Thẻ Hội Viên thành công: Cho phép Tích điểm & Dùng điểm thanh toán.'

    # 2. Tra cứu bằng Số điện thoại
    if not customer:
        customer = CustomerProfile.objects.filter(phone=query).first()
        if customer:
            allow_redeem_points = False
            lookup_method = 'PHONE'
            lookup_message = 'Tra cứu qua SĐT: Chỉ tích điểm. Để dùng điểm thanh toán, khách hàng vui lòng xuất trình Mã Thẻ Hội Viên.'

    if not customer:
        return JsonResponse({'status': 'not_found', 'message': f'Không tìm thấy hội viên với thông tin "{query}"'})

    # Lấy các coupon khả dụng
    available_coupons = []
    for c in Coupon.objects.filter(is_active=True):
        ok, _, disc = c.can_apply(customer, order_amount=Decimal('100000'))
        if ok or c.condition_type in ['ALL', 'BIRTHDAY', 'VIP_ONLY']:
            available_coupons.append({
                'code': c.code,
                'title': c.title,
                'condition_type': c.get_condition_type_display(),
            })

    return JsonResponse({
        'status': 'success',
        'customer': {
            'id': customer.id,
            'phone': customer.phone,
            'member_card_code': customer.member_card_code,
            'full_name': customer.full_name,
            'points_balance': customer.points_balance,
            'points_in_vnd': customer.points_in_vnd,
            'tier': customer.get_tier_display(),
            'is_vip': customer.check_vip_active(),
            'vip_expiry_date': customer.vip_expiry_date.strftime("%d/%m/%Y") if customer.vip_expiry_date else None,
            'total_spent': float(customer.total_spent),
            'available_coupons': available_coupons,
            'allow_redeem_points': allow_redeem_points,
            'lookup_method': lookup_method,
            'lookup_message': lookup_message,
        }
    })


def api_generate_vietqr(request):
    """API sinh mã VietQR động cho đơn thanh toán tại POS hoặc Online"""
    amount = request.GET.get('amount')
    order_code = request.GET.get('order_code', '')
    if not amount or not order_code:
        return JsonResponse({'status': 'error', 'message': 'Thiếu tham số amount hoặc order_code'}, status=400)

    try:
        setting = StoreSetting.get_settings()
        qr_url, desc = setting.generate_vietqr_url(float(amount), order_code)
        return JsonResponse({
            'status': 'success',
            'qr_url': qr_url,
            'desc': desc,
            'amount': float(amount),
            'bank_id': setting.vietqr_bank_id,
            'account_no': setting.vietqr_account_no,
            'account_name': setting.vietqr_account_name,
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@login_required
@transaction.atomic
def api_checkout(request):
    """
    Xử lý thanh toán hóa đơn POS:
    1. Kiểm tra tồn kho (chặn nếu hết hàng - TC01, TC02)
    2. Áp dụng điểm ví & coupon
    3. Hỗ trợ Tách thanh toán (Split Payment): Tiền mặt + VietQR + Điểm
    4. Trừ tồn kho bánh thành phẩm
    5. Lưu đơn và tích 10% điểm cho hội viên
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Phương thức không hợp lệ'}, status=405)

    try:
        data = json.loads(request.body)
        items_data = data.get('items', [])
        if not items_data:
            return JsonResponse({'status': 'error', 'message': 'Giỏ hàng đang trống! Vui lòng chọn sản phẩm.'}, status=400)

        # 1. Kiểm tra tồn kho từng sản phẩm
        product_ids = [item['id'] for item in items_data]
        products_map = {p.id: p for p in Product.objects.select_for_update().filter(id__in=product_ids)}

        subtotal = Decimal('0')
        order_items_to_create = []

        for item in items_data:
            pid = int(item['id'])
            qty = int(item.get('quantity', 1))

            if qty <= 0:
                return JsonResponse({'status': 'error', 'message': 'Số lượng mua phải tối thiểu là 1.'}, status=400)
            if qty > 99:
                return JsonResponse({'status': 'error', 'message': 'Số lượng mua vượt quá 99 cái. Vui lòng chuyển sang Đơn sỉ.'}, status=400)

            product = products_map.get(pid)
            if not product:
                return JsonResponse({'status': 'error', 'message': f'Sản phẩm mã #{pid} không tồn tại.'}, status=404)

            # TC02: Chặn chọn bánh khi tồn kho không đủ
            if product.stock_quantity < qty:
                if product.stock_quantity == 0:
                    return JsonResponse({'status': 'error', 'message': f'Sản phẩm "{product.name}" đã hết hàng trong ca!'}, status=400)
                else:
                    return JsonResponse({'status': 'error', 'message': f'Sản phẩm "{product.name}" chỉ còn lại {product.stock_quantity} cái (bạn chọn {qty}).'}, status=400)

            freshness = product.get_freshness_status()
            effective_price = freshness['current_price']
            line_subtotal = effective_price * Decimal(str(qty))
            subtotal += line_subtotal
            order_items_to_create.append({
                'product': product,
                'quantity': qty,
                'unit_price': effective_price,
                'subtotal': line_subtotal
            })

        # 2. Xử lý khách hàng và điểm ví
        customer_phone = data.get('customer_phone', '').strip()
        customer_profile = None
        if customer_phone:
            customer_profile = CustomerProfile.objects.filter(phone=customer_phone).first()

        points_used = int(data.get('points_used', 0))
        points_discount = Decimal('0')

        if points_used > 0:
            if not customer_profile:
                return JsonResponse({'status': 'error', 'message': 'Cần chọn thông tin khách hàng để sử dụng điểm ví.'}, status=400)
            
            # Kiểm tra bảo mật: Bắt buộc quét Mã Vạch / QR Thẻ Hội Viên để tiêu điểm
            card_code = data.get('card_code', '').strip()
            if not card_code or customer_profile.member_card_code != card_code:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Bảo mật: Chỉ được trừ điểm ví khi nhân viên quét Mã Vạch / QR Thẻ Hội Viên của khách! Tra cứu bằng SĐT chỉ dùng để tích điểm.'
                }, status=403)

            if customer_profile.points_balance < points_used:
                return JsonResponse({'status': 'error', 'message': f'Số dư điểm không đủ (Hiện có {customer_profile.points_balance:,} điểm).'}, status=400)
            
            # 1 điểm = 1.000 VNĐ
            points_discount = Decimal(str(points_used * 1000))
            if points_discount > subtotal:
                points_discount = subtotal
                points_used = int(points_discount / 1000)

        # 3. Xử lý Coupon
        coupon_code = data.get('coupon_code', '').strip().upper()
        coupon_obj = None
        coupon_discount = Decimal('0')

        if coupon_code:
            coupon_obj = Coupon.objects.filter(code=coupon_code).first()
            if coupon_obj:
                valid, msg, c_disc = coupon_obj.can_apply(customer_profile, subtotal)
                if not valid:
                    return JsonResponse({'status': 'error', 'message': msg}, status=400)
                coupon_discount = c_disc
                coupon_obj.used_count += 1
                coupon_obj.save(update_fields=['used_count'])

        # Chiết khấu VIP (nếu khách là VIP và chưa áp coupon)
        vip_discount = Decimal('0')
        if customer_profile and customer_profile.check_vip_active() and not coupon_obj:
            setting = StoreSetting.get_settings()
            vip_discount = (subtotal * (setting.vip_discount_percent / Decimal('100'))).quantize(Decimal('1'))

        total_discount = min(subtotal, coupon_discount + vip_discount + points_discount)
        final_amount = max(Decimal('0'), subtotal - total_discount)

        # 4. Xử lý phương thức thanh toán & Tách thanh toán (Split Payment)
        payment_method = data.get('payment_method', PaymentMethod.CASH)
        cash_paid = Decimal(str(data.get('cash_paid', 0)))
        transfer_paid = Decimal(str(data.get('transfer_paid', 0)))
        points_paid = points_discount

        # Kiểm tra tính đầy đủ của số tiền nhận
        total_paid = cash_paid + transfer_paid + points_paid
        change_amount = Decimal('0')

        if payment_method == PaymentMethod.CASH:
            if total_paid < final_amount:
                # Nếu khách thanh toán đủ final_amount bằng tiền mặt mặc định
                if cash_paid == 0:
                    cash_paid = final_amount
                    total_paid = cash_paid + points_paid
                else:
                    return JsonResponse({'status': 'error', 'message': f'Tiền mặt nhận ({cash_paid:,.0f}đ) chưa đủ thanh toán đơn ({final_amount:,.0f}đ).'}, status=400)
            change_amount = max(Decimal('0'), total_paid - final_amount)

        elif payment_method == PaymentMethod.TRANSFER:
            transfer_paid = final_amount
            total_paid = transfer_paid + points_paid

        elif payment_method == PaymentMethod.SPLIT:
            if total_paid < final_amount:
                shortage = final_amount - total_paid
                return JsonResponse({'status': 'error', 'message': f'Tổng tiền thanh toán tách chưa đủ (Thiếu {shortage:,.0f} VNĐ). Vui lòng bù thêm tiền mặt hoặc chuyển khoản.'}, status=400)
            change_amount = max(Decimal('0'), cash_paid - (final_amount - transfer_paid - points_paid))

        # 5. Tạo mã hóa đơn: HD + YYYYMMDD + 6 số ngẫu nhiên/timestamp
        now = timezone.now()
        order_code = f"HD{now.strftime('%Y%m%d%H%M%S')}"

        # 6. Trừ tồn kho bánh thành phẩm (TC01)
        for item in order_items_to_create:
            prod = item['product']
            prod.stock_quantity -= item['quantity']
            prod.save(update_fields=['stock_quantity'])

        # 7. Trừ điểm ví của khách nếu đã dùng
        if points_used > 0 and customer_profile:
            customer_profile.points_balance -= points_used
            customer_profile.save(update_fields=['points_balance'])
            PointTransaction.objects.create(
                customer=customer_profile,
                transaction_type=PointTransactionType.REDEEM,
                points=-points_used,
                amount_money=points_discount,
                notes=f'Sử dụng điểm cho đơn hàng {order_code}'
            )

        # 8. Lưu Order & OrderItems
        order = Order.objects.create(
            order_code=order_code,
            order_type=OrderType.POS,
            cashier=request.user,
            customer=customer_profile,
            subtotal=subtotal,
            coupon=coupon_obj,
            discount_amount=coupon_discount + vip_discount,
            points_used=points_used,
            points_discount_amount=points_discount,
            final_amount=final_amount,
            payment_method=payment_method,
            cash_paid=cash_paid,
            transfer_paid=transfer_paid,
            points_paid=points_paid,
            change_amount=change_amount,
            delivery_type=DeliveryType.STORE_PICKUP,
            status=OrderStatus.COMPLETED
        )

        for item in order_items_to_create:
            OrderItem.objects.create(
                order=order,
                product=item['product'],
                quantity=item['quantity'],
                unit_price=item['unit_price'],
                subtotal=item['subtotal']
            )

        # 9. Tích 10% điểm cho khách hàng
        order.finalize_order_loyalty()

        # 10. Ghi Nhật ký Kiểm toán (Audit Logs)
        AuditLog.log(
            user=request.user,
            action_type=AuditActionType.RECEIPT_PRINT,
            target_code=order.order_code,
            description=f"In hóa đơn bán lẻ {order.order_code}, thu ngân {request.user.get_full_name() or request.user.username}, tổng thanh toán {order.final_amount:,.0f}đ ({order.get_payment_method_display()})",
            request=request
        )

        if points_used > 0 and customer_profile:
            AuditLog.log(
                user=request.user,
                action_type=AuditActionType.POINTS_REDEEM,
                target_code=order.order_code,
                description=f"Khách hàng {customer_profile.full_name} ({customer_profile.phone}) quét Thẻ Hội Viên {card_code} sử dụng {points_used} điểm (giảm {points_discount:,.0f}đ)",
                request=request
            )

        if coupon_obj:
            AuditLog.log(
                user=request.user,
                action_type=AuditActionType.COUPON_APPLY,
                target_code=coupon_obj.code,
                description=f"Áp dụng mã ưu đãi {coupon_obj.code} cho đơn hàng {order.order_code}, giảm {coupon_discount:,.0f}đ",
                request=request
            )

        return JsonResponse({
            'status': 'success',
            'message': 'Thanh toán đơn hàng thành công!',
            'order_id': order.id,
            'order_code': order.order_code,
            'subtotal': float(order.subtotal),
            'discount_amount': float(order.discount_amount),
            'points_discount_amount': float(order.points_discount_amount),
            'final_amount': float(order.final_amount),
            'cash_paid': float(order.cash_paid),
            'transfer_paid': float(order.transfer_paid),
            'change_amount': float(order.change_amount),
            'points_earned': order.points_earned,
            'customer_name': customer_profile.full_name if customer_profile else None,
            'new_points_balance': customer_profile.points_balance if customer_profile else 0,
        })

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': f'Lỗi xử lý đơn: {str(e)}'}, status=500)
