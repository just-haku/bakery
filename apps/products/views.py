from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from decimal import Decimal
import json

from .models import Product, Category, Coupon, ProductStatus
from .forms import ProductForm, CouponForm
from apps.authentication.models import CustomerProfile

@login_required
def product_list(request):
    """Quản lý danh sách sản phẩm bánh (Dành cho Admin/Quản lý)"""
    category_id = request.GET.get('category')
    search_query = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status')

    products = Product.objects.select_related('category').all().order_by('-id')

    if category_id:
        products = products.filter(category_id=category_id)
    if search_query:
        products = products.filter(name__icontains=search_query) | products.filter(sku_code__icontains=search_query)
    if status_filter:
        products = products.filter(status=status_filter)

    categories = Category.objects.all()
    return render(request, 'products/product_list.html', {
        'products': products,
        'categories': categories,
        'selected_category': category_id,
        'search_query': search_query,
        'status_filter': status_filter,
    })


@login_required
def product_create(request):
    """Admin thêm món bánh mới"""
    if not request.user.is_admin_user:
        messages.error(request, 'Bạn không có quyền thực hiện chức năng này.')
        return redirect('products:product_list')

    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            product = form.save()
            messages.success(request, f'Đã thêm sản phẩm bánh mới: {product.name} ({product.sku_code})')
            return redirect('products:product_list')
    else:
        form = ProductForm()

    return render(request, 'products/product_form.html', {
        'form': form,
        'title': 'Thêm Món Bánh Mới',
        'is_edit': False
    })


@login_required
def product_update(request, pk):
    """Admin chỉnh sửa món bánh"""
    if not request.user.is_admin_user:
        messages.error(request, 'Bạn không có quyền thực hiện chức năng này.')
        return redirect('products:product_list')

    product = get_object_or_404(Product, pk=pk)
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES, instance=product)
        if form.is_valid():
            product = form.save()
            messages.success(request, f'Đã cập nhật sản phẩm: {product.name}')
            return redirect('products:product_list')
    else:
        form = ProductForm(instance=product)

    return render(request, 'products/product_form.html', {
        'form': form,
        'product': product,
        'title': f'Chỉnh Sửa: {product.name}',
        'is_edit': True
    })


@login_required
def product_delete(request, pk):
    """Admin xóa món bánh"""
    if not request.user.is_admin_user:
        messages.error(request, 'Bạn không có quyền thực hiện chức năng này.')
        return redirect('products:product_list')

    product = get_object_or_404(Product, pk=pk)
    if request.method == 'POST':
        name = product.name
        sku = product.sku_code
        product.delete()
        messages.success(request, f'Đã xóa món bánh: {name} ({sku}) thành công.')
        return redirect('products:product_list')

    return render(request, 'products/product_confirm_delete.html', {'product': product})


# ==========================================
# QUẢN LÝ COUPON & MÃ KHUYẾN MÃI (ADMIN)
# ==========================================
@login_required
def coupon_list(request):
    """Admin xem danh sách Coupon"""
    coupons = Coupon.objects.all().order_by('-id')
    return render(request, 'products/coupon_list.html', {
        'coupons': coupons,
        'now': timezone.now()
    })


@login_required
def coupon_create(request):
    """Admin tạo mã Coupon mới với các điều kiện"""
    if not request.user.is_admin_user:
        messages.error(request, 'Bạn không có quyền thực hiện chức năng này.')
        return redirect('products:coupon_list')

    if request.method == 'POST':
        form = CouponForm(request.POST)
        if form.is_valid():
            coupon = form.save()
            messages.success(request, f'Đã tạo thành công mã khuyến mãi: {coupon.code}')
            return redirect('products:coupon_list')
    else:
        form = CouponForm(initial={
            'valid_from': timezone.now(),
            'valid_to': timezone.now() + timezone.timedelta(days=30),
            'usage_limit': 100,
        })

    return render(request, 'products/coupon_form.html', {
        'form': form,
        'title': 'Tạo Mã Khuyến Mãi (Coupon) Mới',
        'is_edit': False
    })


@login_required
def coupon_update(request, pk):
    """Admin sửa Coupon"""
    if not request.user.is_admin_user:
        messages.error(request, 'Bạn không có quyền thực hiện chức năng này.')
        return redirect('products:coupon_list')

    coupon = get_object_or_404(Coupon, pk=pk)
    if request.method == 'POST':
        form = CouponForm(request.POST, instance=coupon)
        if form.is_valid():
            coupon = form.save()
            messages.success(request, f'Đã cập nhật mã khuyến mãi: {coupon.code}')
            return redirect('products:coupon_list')
    else:
        form = CouponForm(instance=coupon)

    return render(request, 'products/coupon_form.html', {
        'form': form,
        'coupon': coupon,
        'title': f'Chỉnh Sửa Coupon: {coupon.code}',
        'is_edit': True
    })


@login_required
def coupon_delete(request, pk):
    """Admin xóa Coupon"""
    if not request.user.is_admin_user:
        messages.error(request, 'Bạn không có quyền thực hiện chức năng này.')
        return redirect('products:coupon_list')

    coupon = get_object_or_404(Coupon, pk=pk)
    if request.method == 'POST':
        code = coupon.code
        coupon.delete()
        messages.success(request, f'Đã xóa mã khuyến mãi: {code}')
        return redirect('products:coupon_list')

    return render(request, 'products/coupon_confirm_delete.html', {'coupon': coupon})


def api_validate_coupon(request):
    """API kiểm tra hợp lệ và tính mức giảm giá của Coupon"""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Phương thức không hợp lệ'}, status=405)

    try:
        data = json.loads(request.body)
        code = data.get('code', '').strip().upper()
        order_amount = Decimal(str(data.get('order_amount', 0)))
        phone = data.get('customer_phone', '').strip()

        customer_profile = None
        if phone:
            customer_profile = CustomerProfile.objects.filter(phone=phone).first()

        coupon = Coupon.objects.filter(code=code).first()
        if not coupon:
            return JsonResponse({'status': 'error', 'message': f'Mã khuyến mãi "{code}" không tồn tại.'}, status=404)

        is_valid, msg, discount = coupon.can_apply(customer_profile, order_amount)
        if not is_valid:
            return JsonResponse({'status': 'error', 'message': msg}, status=400)

        return JsonResponse({
            'status': 'success',
            'code': coupon.code,
            'title': coupon.title,
            'discount_amount': float(discount),
            'message': msg,
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
