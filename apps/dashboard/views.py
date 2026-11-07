import json
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.http import FileResponse, Http404, HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import check_for_language
from django.views.decorators.csrf import ensure_csrf_cookie

from apps.authentication.models import CustomerProfile, PointTransaction, PointTransactionType, UserRole
from apps.custom_orders.models import CakeOrderStatus, CustomCakeOrder
from apps.kitchen_bom.models import BatchStatus, KitchenBatch, Material
from apps.pos.models import DeliveryType, Order, OrderItem, OrderStatus, OrderType, PaymentMethod
from apps.products.models import Category, Coupon, Product, ProductStatus

from .models import AuditActionType, AuditLog, StoreSetting
from .utils import custom_page_not_found_view, get_client_ip, render_security_warning

User = get_user_model()

APK_VERSION_NAME = '1.0.3'
APK_VERSION_CODE = 4


def index(request):
    portal_role = getattr(request, 'portal_role', 'ADMIN')

    if not request.user.is_authenticated:
        if portal_role == 'CUSTOMER':
            return redirect('dashboard:online_catalog')
        return redirect('auth:login')

    if portal_role == 'CUSTOMER' or request.user.role == UserRole.CUSTOMER:
        return redirect('dashboard:online_catalog')
    if portal_role == 'EMPLOYEE' and request.user.role == UserRole.CASHIER:
        return redirect('pos:pos_screen')
    if portal_role == 'EMPLOYEE' and request.user.role == UserRole.BAKER:
        return redirect('kitchen:kitchen_screen')

    now = timezone.now()
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)

    today_orders = Order.objects.filter(created_at__gte=start_of_day, status=OrderStatus.COMPLETED)
    today_revenue = today_orders.aggregate(total=Sum('final_amount'))['total'] or Decimal('0')
    today_order_count = today_orders.count()

    start_of_week = start_of_day - timedelta(days=now.weekday())
    week_orders = Order.objects.filter(created_at__gte=start_of_week, status=OrderStatus.COMPLETED)
    week_revenue = week_orders.aggregate(total=Sum('final_amount'))['total'] or Decimal('0')

    pending_cakes = CustomCakeOrder.objects.filter(
        status__in=[CakeOrderStatus.RECEIVED, CakeOrderStatus.BAKING]
    ).order_by('pickup_datetime')[:5]

    fresh_cakes_warning = Product.objects.filter(status=ProductStatus.ACTIVE, shelf_life_hours__lte=24)[:6]
    critical_materials = [m for m in Material.objects.all() if m.is_low_stock][:6]
    recent_orders = Order.objects.select_related('cashier', 'customer').order_by('-created_at')[:8]
    total_customers = User.objects.filter(role=UserRole.CUSTOMER).count()

    return render(request, 'dashboard/index.html', {
        'today_revenue': today_revenue,
        'today_order_count': today_order_count,
        'week_revenue': week_revenue,
        'pending_cakes': pending_cakes,
        'fresh_cakes_warning': fresh_cakes_warning,
        'critical_materials': critical_materials,
        'recent_orders': recent_orders,
        'total_customers': total_customers,
        'now': now,
    })


@ensure_csrf_cookie
def online_catalog(request):
    category_slug = request.GET.get('category')
    q = request.GET.get('q', '').strip()
    filter_type = request.GET.get('filter', '').strip()

    products = Product.objects.filter(status=ProductStatus.ACTIVE).select_related('category')
    categories = Category.objects.filter(is_active=True)

    if category_slug:
        products = products.filter(category__slug=category_slug)
    if q:
        products = products.filter(Q(name__icontains=q) | Q(sku_code__icontains=q))

    all_active_products = list(Product.objects.filter(status=ProductStatus.ACTIVE).select_related('category'))
    golden_hour_ids = [p.id for p in all_active_products if p.get_freshness_status().get('is_near_expiry')]

    if filter_type == 'bestseller':
        products = products.annotate(total_sold=Sum('order_items__quantity')).order_by('-total_sold', '-id')
    elif filter_type == 'golden_hour':
        products = products.filter(id__in=golden_hour_ids)

    active_coupons = Coupon.objects.filter(is_active=True, valid_to__gte=timezone.now())[:6]

    return render(request, 'customer/catalog.html', {
        'products': products,
        'categories': categories,
        'selected_category_slug': category_slug,
        'filter_type': filter_type,
        'golden_hour_count': len(golden_hour_ids),
        'search_query': q,
        'active_coupons': active_coupons,
    })


@ensure_csrf_cookie
def online_cart(request):
    setting = StoreSetting.get_settings()
    customer_profile = None
    if request.user.is_authenticated and hasattr(request.user, 'customer_profile'):
        customer_profile = request.user.customer_profile

    active_coupons = Coupon.objects.filter(is_active=True).order_by('-discount_value')

    return render(request, 'customer/cart.html', {
        'setting': setting,
        'customer_profile': customer_profile,
        'active_coupons': active_coupons,
    })


@transaction.atomic
def api_online_checkout(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)

    try:
        data = json.loads(request.body)
        items_data = data.get('items', [])
        if not items_data:
            return JsonResponse({'status': 'error', 'message': 'Giỏ hàng của bạn đang trống'}, status=400)

        recipient_name = data.get('recipient_name', '').strip()
        recipient_phone = data.get('recipient_phone', '').strip()
        delivery_type = data.get('delivery_type', DeliveryType.DELIVERY)
        shipping_address = data.get('shipping_address', '').strip()

        if not recipient_name or not recipient_phone:
            return JsonResponse({'status': 'error', 'message': 'Vui lòng cung cấp đầy đủ tên và số điện thoại người nhận'}, status=400)

        if delivery_type == DeliveryType.DELIVERY and not shipping_address:
            return JsonResponse({'status': 'error', 'message': 'Vui lòng cung cấp địa chỉ nhận hàng'}, status=400)

        subtotal = Decimal('0')
        order_items_to_create = []

        for item in items_data:
            pid = int(item['id'])
            qty = int(item.get('quantity', 1))

            product = Product.objects.select_for_update().filter(id=pid, status=ProductStatus.ACTIVE).first()
            if not product:
                return JsonResponse({'status': 'error', 'message': f'Sản phẩm #{pid} hiện không khả dụng'}, status=400)

            if product.stock_quantity < qty:
                return JsonResponse({'status': 'error', 'message': f'Sản phẩm "{product.name}" chỉ còn {product.stock_quantity} trong kho'}, status=400)

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

        setting = StoreSetting.get_settings()
        shipping_fee = Decimal('0')
        if delivery_type == DeliveryType.DELIVERY:
            shipping_fee = setting.default_shipping_fee

        customer_profile = None
        if request.user.is_authenticated and hasattr(request.user, 'customer_profile'):
            customer_profile = request.user.customer_profile
        elif recipient_phone:
            customer_profile, _ = CustomerProfile.objects.get_or_create(
                phone=recipient_phone,
                defaults={'full_name': recipient_name}
            )

        points_used = int(data.get('points_used', 0))
        points_discount = Decimal('0')
        if points_used > 0 and customer_profile:
            if customer_profile.points_balance < points_used:
                return JsonResponse({'status': 'error', 'message': 'Số dư điểm ví không đủ'}, status=400)
            points_discount = Decimal(str(points_used * 1000))
            if points_discount > subtotal:
                points_discount = subtotal
                points_used = int(points_discount / 1000)

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

        vip_discount = Decimal('0')
        if customer_profile and customer_profile.check_vip_active() and not coupon_obj:
            vip_discount = (subtotal * (setting.vip_discount_percent / Decimal('100'))).quantize(Decimal('1'))

        total_discount = min(subtotal, coupon_discount + vip_discount + points_discount)
        final_amount = max(Decimal('0'), subtotal + shipping_fee - total_discount)

        payment_method = data.get('payment_method', PaymentMethod.COD)
        now_str = timezone.now().strftime('%Y%m%d%H%M%S')
        order_code = f"ON{now_str}"

        for it in order_items_to_create:
            p = it['product']
            p.stock_quantity -= it['quantity']
            p.save(update_fields=['stock_quantity'])

        if points_used > 0 and customer_profile:
            customer_profile.points_balance -= points_used
            customer_profile.save(update_fields=['points_balance'])
            PointTransaction.objects.create(
                customer=customer_profile,
                transaction_type=PointTransactionType.REDEEM,
                points=-points_used,
                amount_money=points_discount,
                notes=f'Dùng điểm cho đơn {order_code}'
            )

        order = Order.objects.create(
            order_code=order_code,
            order_type=OrderType.ONLINE,
            customer=customer_profile,
            subtotal=subtotal,
            shipping_fee=shipping_fee,
            coupon=coupon_obj,
            discount_amount=coupon_discount + vip_discount,
            points_used=points_used,
            points_discount_amount=points_discount,
            final_amount=final_amount,
            payment_method=payment_method,
            delivery_type=delivery_type,
            shipping_address=shipping_address,
            recipient_name=recipient_name,
            recipient_phone=recipient_phone,
            notes=data.get('notes', ''),
            status=OrderStatus.PENDING
        )

        for it in order_items_to_create:
            OrderItem.objects.create(
                order=order,
                product=it['product'],
                quantity=it['quantity'],
                unit_price=it['unit_price'],
                subtotal=it['subtotal']
            )

        order.finalize_order_loyalty()

        vietqr_url = None
        vietqr_desc = None
        if payment_method == PaymentMethod.TRANSFER:
            vietqr_url, vietqr_desc = setting.generate_vietqr_url(final_amount, order_code)

        return JsonResponse({
            'status': 'success',
            'order_id': order.id,
            'order_code': order.order_code,
            'subtotal': float(subtotal),
            'shipping_fee': float(shipping_fee),
            'discount_amount': float(total_discount),
            'final_amount': float(final_amount),
            'payment_method': payment_method,
            'payment_method_display': order.get_payment_method_display(),
            'vietqr_url': vietqr_url,
            'vietqr_desc': vietqr_desc,
            'points_earned': order.points_earned,
            'new_points_balance': customer_profile.points_balance if customer_profile else 0,
            'message': 'Đặt hàng online thành công!',
        })

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@login_required
def my_orders(request):
    orders = []
    customer_profile = None
    if hasattr(request.user, 'customer_profile'):
        customer_profile = request.user.customer_profile
        orders = customer_profile.orders.prefetch_related('items__product').all()
    return render(request, 'customer/my_orders.html', {
        'orders': orders,
        'customer_profile': customer_profile
    })


@login_required
def store_settings_view(request):
    if not request.user.is_admin_user:
        messages.error(request, 'Bạn không có quyền truy cập trang cấu hình.')
        return redirect('dashboard:index')

    setting = StoreSetting.get_settings()

    if request.method == 'POST':
        setting.store_name = request.POST.get('store_name', setting.store_name)
        setting.phone = request.POST.get('phone', setting.phone)
        setting.address = request.POST.get('address', setting.address)
        setting.vietqr_bank_id = request.POST.get('vietqr_bank_id', setting.vietqr_bank_id).strip().upper()
        setting.vietqr_account_no = request.POST.get('vietqr_account_no', setting.vietqr_account_no).strip()
        setting.vietqr_account_name = request.POST.get('vietqr_account_name', setting.vietqr_account_name).strip().upper()
        setting.vietqr_template = request.POST.get('vietqr_template', setting.vietqr_template).strip()
        setting.default_shipping_fee = Decimal(request.POST.get('default_shipping_fee', str(setting.default_shipping_fee)))
        setting.vip_monthly_price = Decimal(request.POST.get('vip_monthly_price', str(setting.vip_monthly_price)))
        setting.vip_yearly_price = Decimal(request.POST.get('vip_yearly_price', str(setting.vip_yearly_price)))
        setting.vip_discount_percent = Decimal(request.POST.get('vip_discount_percent', str(setting.vip_discount_percent)))
        setting.save()

        messages.success(request, 'Cài đặt hệ thống đã được cập nhật thành công.')
        return redirect('dashboard:store_settings')

    return render(request, 'dashboard/settings.html', {'setting': setting})


def pwa_manifest(request):
    manifest_path = settings.BASE_DIR / 'static' / 'manifest.webmanifest'
    if manifest_path.exists():
        response = FileResponse(open(manifest_path, 'rb'), content_type='application/manifest+json')
        response['Cache-Control'] = 'public, max-age=86400'
        return response
    return HttpResponse('{}', content_type='application/manifest+json')


def pwa_sw(request):
    sw_path = settings.BASE_DIR / 'static' / 'sw.js'
    if sw_path.exists():
        response = FileResponse(open(sw_path, 'rb'), content_type='application/javascript')
        response['Service-Worker-Allowed'] = '/'
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        return response
    return HttpResponse('// Service Worker not found', content_type='application/javascript')


def pwa_offline(request):
    return render(request, 'offline.html')


def custom_permission_denied_view(request, exception=None):
    reason = str(exception) if exception else None
    return render_security_warning(request, reason=reason, status=403)


def test_403_view(request):
    return render_security_warning(
        request, 
        reason='Bạn không có quyền truy cập khu vực này.'
    )


def test_404_view(request):
    return custom_page_not_found_view(request)


def download_hub_view(request):
    ua = request.META.get('HTTP_USER_AGENT', '').lower()
    if 'iphone' in ua or 'ipad' in ua or 'ipod' in ua:
        detected_os = 'ios'
    elif 'android' in ua:
        detected_os = 'android'
    else:
        detected_os = 'pc'

    portal_role = getattr(request, 'portal_role', 'CUSTOMER')

    apk_info = {
        'CUSTOMER': {
            'role_key': 'customer',
            'role_name': 'Khách Hàng',
            'app_title': 'Artisan Tiệm Bánh',
            'badge': 'Dành Cho Khách Hàng',
            'icon': '🥐',
            'apk_filename': 'Artisan_Bakery_Customer.apk',
            'download_url': '/download/apk/customer/',
            'size': '190 KB',
            'version': f'v{APK_VERSION_NAME} (Build {APK_VERSION_CODE})',
            'desc': 'Xem menu bánh tươi, đặt bánh sinh nhật và tích điểm VIP.',
            'home_url': '/online/',
        },
        'EMPLOYEE': {
            'role_key': 'employee',
            'role_name': 'Nhân Viên (POS & Bếp)',
            'app_title': 'Artisan POS & Bếp',
            'badge': 'Dành Cho Nhân Viên',
            'icon': '⚡',
            'apk_filename': 'Artisan_Bakery_Employee_POS.apk',
            'download_url': '/download/apk/employee/',
            'size': '198 KB',
            'version': f'v{APK_VERSION_NAME} (Build {APK_VERSION_CODE})',
            'desc': 'Bán hàng POS cảm ứng, quản lý mẻ nướng KDS và in tem nhãn.',
            'home_url': '/pos/',
        },
        'ADMIN': {
            'role_key': 'admin',
            'role_name': 'Quản Trị Viên',
            'app_title': 'Artisan Quản Trị',
            'badge': 'Dành Cho Quản Trị',
            'icon': '👑',
            'apk_filename': 'Artisan_Bakery_Admin.apk',
            'download_url': '/download/apk/admin/',
            'size': '190 KB',
            'version': f'v{APK_VERSION_NAME} (Build {APK_VERSION_CODE})',
            'desc': 'Báo cáo doanh thu, quản lý nhân viên và cấu hình hệ thống.',
            'home_url': '/',
        },
    }

    for info in apk_info.values():
        p = settings.BASE_DIR / 'dist_apk' / info['apk_filename']
        if p.exists():
            info['size'] = f'{p.stat().st_size // 1024} KB'
        info['download_url'] += f'?v={APK_VERSION_CODE}'

    current_apk = apk_info.get(portal_role, apk_info['CUSTOMER'])

    return render(request, 'download.html', {
        'detected_os': detected_os,
        'portal_role': portal_role,
        'current_apk': current_apk,
        'all_apks': apk_info,
        'current_url': request.build_absolute_uri(),
    })


def download_apk_file(request, role=None):
    role = (role or request.GET.get('role') or getattr(request, 'portal_role', 'customer')).lower()

    apk_map = {
        'customer': 'Artisan_Bakery_Customer.apk',
        'client': 'Artisan_Bakery_Customer.apk',
        'admin': 'Artisan_Bakery_Admin.apk',
        'employee': 'Artisan_Bakery_Employee_POS.apk',
        'pos': 'Artisan_Bakery_Employee_POS.apk',
        'kitchen': 'Artisan_Bakery_Employee_POS.apk',
    }

    filename = apk_map.get(role, 'Artisan_Bakery_Customer.apk')
    apk_path = settings.BASE_DIR / 'dist_apk' / filename

    if not apk_path.exists():
        raise Http404(f"Không tìm thấy file APK: {filename}")

    response = FileResponse(open(apk_path, 'rb'), content_type='application/vnd.android.package-archive')
    download_name = filename.replace('.apk', f'_v{APK_VERSION_NAME}.apk')
    response['Content-Disposition'] = f'attachment; filename="{download_name}"'
    response['Content-Length'] = apk_path.stat().st_size
    response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    return response


def set_language_view(request, lang_code=None):
    if not lang_code:
        lang_code = request.POST.get('language') or request.GET.get('language', 'vi')

    lang_code = lang_code.strip().lower()
    if not check_for_language(lang_code):
        lang_code = 'vi'

    next_url = request.POST.get('next') or request.GET.get('next') or request.META.get('HTTP_REFERER') or '/'

    response = HttpResponseRedirect(next_url)
    response.set_cookie(
        settings.LANGUAGE_COOKIE_NAME,
        lang_code,
        max_age=365 * 24 * 60 * 60,
        path=settings.LANGUAGE_COOKIE_PATH,
        domain=settings.LANGUAGE_COOKIE_DOMAIN,
        secure=settings.LANGUAGE_COOKIE_SECURE,
        httponly=False,
        samesite=settings.LANGUAGE_COOKIE_SAMESITE,
    )
    if hasattr(request, 'session'):
        request.session['_language'] = lang_code
        request.session.modified = True

    return response


@login_required
def test_printing_view(request):
    sample_products = Product.objects.filter(status=ProductStatus.ACTIVE)[:8]
    setting = StoreSetting.get_settings()
    now = timezone.now()
    return render(request, 'dashboard/test_printing.html', {
        'sample_products': sample_products,
        'setting': setting,
        'now': now,
    })


@login_required
def audit_logs_view(request):
    logs = AuditLog.objects.select_related('user').all()
    
    action_type = request.GET.get('action_type', '').strip()
    q = request.GET.get('q', '').strip()
    
    if action_type:
        logs = logs.filter(action_type=action_type)
    if q:
        logs = logs.filter(
            Q(target_code__icontains=q) |
            Q(description__icontains=q) |
            Q(user__username__icontains=q) |
            Q(user__first_name__icontains=q)
        )
        
    return render(request, 'dashboard/audit_logs.html', {
        'logs': logs[:100],
        'action_choices': AuditActionType.choices,
        'selected_action': action_type,
        'search_query': q,
        'total_logs_count': logs.count(),
    })
