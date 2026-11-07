import json
from datetime import timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.authentication.models import UserRole
from apps.dashboard.models import AuditActionType, AuditLog
from apps.kitchen_bom.forms import MaterialForm
from apps.kitchen_bom.models import Material
from apps.products.models import Product, ProductStatus


def admin_required(view_func):
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('auth:login')
        if getattr(request.user, 'role', None) != UserRole.ADMIN and not request.user.is_superuser:
            messages.error(request, _('Nhân viên không có quyền xem thông tin kho hàng.'))
            return redirect('pos:pos_screen')
        return view_func(request, *args, **kwargs)
    return _wrapped


@login_required
@admin_required
def stock_overview(request):
    products = Product.objects.select_related('category').all().order_by('stock_quantity')
    materials = Material.objects.all().order_by('stock_quantity')

    fresh_cakes_warning = products.filter(status=ProductStatus.ACTIVE, shelf_life_hours__lte=24)
    low_stock_cakes = products.filter(status=ProductStatus.ACTIVE, stock_quantity__lte=5)
    low_stock_materials = [m for m in materials if m.is_low_stock]

    return render(request, 'inventory/stock_overview.html', {
        'products': products,
        'materials': materials,
        'fresh_cakes_warning': fresh_cakes_warning,
        'low_stock_cakes': low_stock_cakes,
        'low_stock_materials': low_stock_materials,
    })


@login_required
@admin_required
def materials_list(request):
    q = request.GET.get('q', '').strip()
    materials = Material.objects.all().order_by('code')

    if q:
        materials = materials.filter(name__icontains=q) | materials.filter(code__icontains=q)

    return render(request, 'inventory/materials_list.html', {
        'materials': materials,
        'search_query': q,
    })


@login_required
@admin_required
def material_create(request):
    if request.method == 'POST':
        form = MaterialForm(request.POST)
        if form.is_valid():
            material = form.save()
            AuditLog.log(
                request.user,
                AuditActionType.MATERIAL_STOCK_IN,
                target_code=material.code,
                description=f"Tạo mới nguyên liệu [{material.code}] {material.name} ({material.get_material_type_display()}) - Tồn: {material.stock_quantity} {material.unit}, Đơn giá: {material.unit_cost:,.0f} đ",
                request=request
            )
            messages.success(request, f'Đã thêm mới nguyên liệu [{material.code}] {material.name}.')
            return redirect('inventory:materials_list')
    else:
        form = MaterialForm()

    return render(request, 'inventory/material_form.html', {
        'form': form,
    })


@login_required
def material_import(request, pk):
    material = get_object_or_404(Material, pk=pk)

    if request.method == 'POST':
        qty_add = Decimal(request.POST.get('quantity_add', '0'))
        unit_cost = request.POST.get('unit_cost')

        if qty_add > 0:
            material.stock_quantity += qty_add
            if unit_cost:
                material.unit_cost = Decimal(unit_cost)
            material.save()
            
            AuditLog.log(
                request.user,
                AuditActionType.MATERIAL_STOCK_IN,
                target_code=material.code,
                description=f"Nhập thêm +{qty_add} {material.unit} cho nguyên liệu {material.name}. Tồn mới: {material.stock_quantity} {material.unit}",
                request=request
            )
            
            messages.success(request, f'Đã nhập thêm {qty_add} {material.unit} {material.name}. Tồn mới: {material.stock_quantity} {material.unit}.')
            return redirect('inventory:materials_list')
        else:
            messages.error(request, 'Số lượng nhập phải lớn hơn 0.')

    return render(request, 'inventory/material_import.html', {
        'material': material,
    })


@login_required
def expiry_alerts(request):
    products = Product.objects.filter(status=ProductStatus.ACTIVE).select_related('category')
    materials = Material.objects.all()

    fresh_cakes = products.filter(shelf_life_hours__lte=24).order_by('shelf_life_hours')
    out_of_stock_cakes = products.filter(stock_quantity=0)
    near_out_cakes = products.filter(stock_quantity__gt=0, stock_quantity__lte=5)
    critical_materials = [m for m in materials if m.is_low_stock]

    return render(request, 'inventory/expiry_alerts.html', {
        'fresh_cakes': fresh_cakes,
        'out_of_stock_cakes': out_of_stock_cakes,
        'near_out_cakes': near_out_cakes,
        'critical_materials': critical_materials,
    })


@login_required
def api_qr_stock_in(request):
    user_role = getattr(request.user, 'role', None)
    if user_role not in [UserRole.ADMIN, UserRole.BAKER, UserRole.CASHIER] and not request.user.is_staff and not request.user.is_superuser:
        return JsonResponse({'success': False, 'message': _('Tài khoản không có quyền thực hiện nhập hàng.')}, status=403)

    if request.method == 'GET':
        code = request.GET.get('code', '').strip()
        if not code:
            return JsonResponse({'success': False, 'message': _('Mã QR/Barcode không được để trống.')}, status=400)

        product = Product.objects.filter(sku_code__iexact=code).first()
        if not product:
            product = Product.objects.filter(sku_code__icontains=code).first()

        if product:
            return JsonResponse({
                'success': True,
                'found': True,
                'item_type': 'product',
                'id': product.id,
                'code': product.sku_code,
                'name': product.name,
                'current_stock': product.stock_quantity,
                'unit': 'cái',
                'price': str(product.price),
                'shelf_life_hours': product.shelf_life_hours,
                'category': product.category.name if product.category else '',
            })

        material = Material.objects.filter(code__iexact=code).first()
        if not material:
            material = Material.objects.filter(code__icontains=code).first()

        if material:
            return JsonResponse({
                'success': True,
                'found': True,
                'item_type': 'material',
                'id': material.id,
                'code': material.code,
                'name': material.name,
                'current_stock': float(material.stock_quantity),
                'unit': material.unit,
                'price': str(material.unit_cost),
                'shelf_life_hours': None,
                'category': 'Nguyên vật liệu',
            })

        return JsonResponse({
            'success': False,
            'found': False,
            'message': _(f'Không tìm thấy sản phẩm hay nguyên vật liệu khớp với mã "{code}".')
        }, status=404)

    elif request.method == 'POST':
        try:
            if request.content_type == 'application/json':
                data = json.loads(request.body.decode('utf-8'))
            else:
                data = request.POST
        except Exception:
            return JsonResponse({'success': False, 'message': 'Dữ liệu không hợp lệ.'}, status=400)

        code = str(data.get('code', '')).strip()
        item_type = str(data.get('item_type', '')).strip()
        item_id = data.get('id')
        try:
            quantity = float(data.get('quantity', 0))
        except (ValueError, TypeError):
            quantity = 0

        if quantity <= 0:
            return JsonResponse({'success': False, 'message': _('Số lượng nhập kho phải lớn hơn 0.')}, status=400)

        if item_type == 'product' or (not item_type and Product.objects.filter(sku_code__iexact=code).exists()):
            product = None
            if item_id:
                product = Product.objects.filter(id=item_id).first()
            if not product and code:
                product = Product.objects.filter(sku_code__iexact=code).first()

            if not product:
                return JsonResponse({'success': False, 'message': 'Không tìm thấy sản phẩm bánh.'}, status=404)

            qty_int = int(quantity)
            product.stock_quantity += qty_int
            product.save(update_fields=['stock_quantity'])

            AuditLog.log(
                request.user,
                AuditActionType.MATERIAL_STOCK_IN,
                target_code=product.sku_code,
                description=f"Quét mã QR/Barcode nhập kho +{qty_int} cái cho bánh {product.name}. Tồn mới: {product.stock_quantity} cái",
                request=request
            )

            return JsonResponse({
                'success': True,
                'message': _(f'Đã nhập thành công +{qty_int} cái cho "{product.name}". Tồn mới: {product.stock_quantity}.'),
                'new_stock': product.stock_quantity,
                'unit': 'cái',
                'item_name': product.name,
                'code': product.sku_code
            })

        elif item_type == 'material' or (not item_type and Material.objects.filter(code__iexact=code).exists()):
            material = None
            if item_id:
                material = Material.objects.filter(id=item_id).first()
            if not material and code:
                material = Material.objects.filter(code__iexact=code).first()

            if not material:
                return JsonResponse({'success': False, 'message': 'Không tìm thấy nguyên vật liệu.'}, status=404)

            material.stock_quantity += Decimal(str(quantity))
            material.save(update_fields=['stock_quantity'])

            AuditLog.log(
                request.user,
                AuditActionType.MATERIAL_STOCK_IN,
                target_code=material.code,
                description=f"Quét mã QR/Barcode nhập kho +{quantity} {material.unit} cho {material.name}. Tồn mới: {material.stock_quantity} {material.unit}",
                request=request
            )

            return JsonResponse({
                'success': True,
                'message': _(f'Đã nhập thành công +{quantity} {material.unit} cho "{material.name}". Tồn mới: {material.stock_quantity} {material.unit}.'),
                'new_stock': float(material.stock_quantity),
                'unit': material.unit,
                'item_name': material.name,
                'code': material.code
            })

        return JsonResponse({'success': False, 'message': 'Mặt hàng không xác định.'}, status=400)
