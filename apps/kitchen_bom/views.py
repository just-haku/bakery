import json
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext_lazy as _, gettext

from apps.authentication.models import UserRole
from apps.custom_orders.models import CakeOrderStatus, CustomCakeOrder
from apps.dashboard.models import AuditActionType, AuditLog
from apps.dashboard.utils import render_security_warning
from apps.products.models import Product, ProductStatus

from .barcode_utils import generate_barcode_svg
from .forms import BillOfMaterialsForm, KitchenBatchForm
from .models import BatchStatus, BillOfMaterials, KitchenBatch, Material


@login_required
def kitchen_screen(request):
    portal_role = getattr(request, 'portal_role', 'ADMIN')
    if portal_role == 'EMPLOYEE' and getattr(request.user, 'role', None) == UserRole.CASHIER:
        return redirect('pos:pos_screen')

    batches_in_progress = KitchenBatch.objects.filter(
        status=BatchStatus.IN_PROGRESS
    ).select_related('product', 'baker').order_by('-created_at')

    batches_completed_today = KitchenBatch.objects.filter(
        status=BatchStatus.COMPLETED,
        completed_at__date=timezone.now().date()
    ).select_related('product', 'baker').order_by('-completed_at')[:10]

    custom_cakes_received = CustomCakeOrder.objects.filter(
        status__in=[CakeOrderStatus.RECEIVED, CakeOrderStatus.BAKING]
    ).order_by('pickup_datetime')

    products = Product.objects.filter(status=ProductStatus.ACTIVE).order_by('name')

    return render(request, 'kitchen_bom/kitchen_screen.html', {
        'batches_in_progress': batches_in_progress,
        'batches_completed_today': batches_completed_today,
        'custom_cakes_received': custom_cakes_received,
        'products': products,
    })


@login_required
def bom_list(request):
    products = Product.objects.prefetch_related('bom_items__material').all().order_by('name')
    return render(request, 'kitchen_bom/bom_list.html', {
        'products': products,
    })


@login_required
def bom_detail(request, product_id):
    product = get_object_or_404(Product, pk=product_id)
    boms = product.bom_items.select_related('material').all()

    if request.method == 'POST':
        form = BillOfMaterialsForm(request.POST)
        if form.is_valid():
            bom = form.save(commit=False)
            bom.product = product
            batch_qty = form.cleaned_data.get('batch_quantity')
            if batch_qty and batch_qty > 0 and product.standard_batch_yield > 0:
                bom.quantity_needed = (batch_qty / Decimal(str(product.standard_batch_yield))).quantize(Decimal('0.001'))
            bom.save()
            messages.success(request, f'Đã thêm nguyên liệu {bom.material.name} vào công thức bánh {product.name}.')
            return redirect('kitchen:bom_detail', product_id=product.id)
    else:
        form = BillOfMaterialsForm()

    return render(request, 'kitchen_bom/bom_detail.html', {
        'product': product,
        'boms': boms,
        'form': form,
    })


@login_required
def bom_delete(request, pk):
    bom = get_object_or_404(BillOfMaterials, pk=pk)
    prod_id = bom.product.id
    mat_name = bom.material.name
    bom.delete()
    messages.success(request, f'Đã xóa nguyên liệu {mat_name} khỏi công thức.')
    return redirect('kitchen:bom_detail', product_id=prod_id)


@login_required
def batch_create(request):
    if getattr(request.user, 'role', None) == UserRole.CASHIER:
        return render_security_warning(
            request,
            reason=_('Nhân viên thu ngân không có quyền tạo lệnh nướng bánh.')
        )

    if request.method == 'POST':
        form = KitchenBatchForm(request.POST)
        if form.is_valid():
            batch = form.save(commit=False)
            now_str = timezone.now().strftime('%Y%m%d%H%M')
            batch.batch_code = f"MB{now_str}"
            batch.baker = request.user
            batch.status = BatchStatus.IN_PROGRESS
            
            is_sufficient, materials_needed = batch.calculate_materials_needed()
            if not is_sufficient:
                missing = [f"{m['material'].name} (cần {m['needed']} {m['material'].unit}, tồn {m['in_stock']} {m['material'].unit})" for m in materials_needed if not m['has_enough']]
                messages.error(request, f"Kho không đủ nguyên liệu: {', '.join(missing)}")
                return render(request, 'kitchen_bom/batch_form.html', {'form': form, 'products': Product.objects.filter(status=ProductStatus.ACTIVE)})

            batch.save()
            batch.deduct_materials()

            AuditLog.log(
                request.user,
                AuditActionType.BATCH_CREATE,
                target_code=batch.batch_code,
                description=f"Khởi tạo mẻ bánh {batch.batch_code} ({batch.product.name} - SL: {batch.planned_quantity}) và trừ nguyên liệu kho.",
                request=request
            )

            messages.success(request, f'Đã tạo lệnh mẻ bánh: {batch.batch_code} ({batch.product.name} - SL: {batch.planned_quantity}).')
            return redirect('kitchen:kitchen_screen')
    else:
        initial_prod = Product.objects.filter(status=ProductStatus.ACTIVE).first()
        init_qty = initial_prod.standard_batch_yield if initial_prod else 30
        form = KitchenBatchForm(initial={'planned_quantity': init_qty, 'waste_rate': Decimal('5.0')})

    products = Product.objects.filter(status=ProductStatus.ACTIVE).order_by('name')
    return render(request, 'kitchen_bom/batch_form.html', {
        'form': form,
        'products': products,
    })


@login_required
def batch_complete(request, pk):
    batch = get_object_or_404(KitchenBatch.objects.select_related('product', 'baker'), pk=pk)

    if getattr(request.user, 'role', None) == UserRole.CASHIER:
        return render_security_warning(
            request,
            reason=_('Nhân viên thu ngân không có quyền nghiệm thu mẻ bánh.')
        )

    if request.method == 'POST':
        actual_qty = int(request.POST.get('actual_quantity', batch.planned_quantity))
        notes = request.POST.get('notes', '')

        success, msg = batch.complete_batch(actual_qty=actual_qty, notes=notes)
        if success:
            tier = batch.waste_tier
            AuditLog.log(
                request.user,
                AuditActionType.BATCH_COMPLETE,
                target_code=batch.batch_code,
                description=f"Nghiệm thu mẻ {batch.batch_code} ({batch.product.name}): Đạt {actual_qty}/{batch.planned_quantity}. Hao hụt: {batch.waste_rate}% ({tier['label']}).",
                request=request
            )
            if tier['code'] == 'CRITICAL':
                AuditLog.log(
                    request.user,
                    AuditActionType.BATCH_RED_ALERT,
                    target_code=batch.batch_code,
                    description=f"Cảnh báo: Mẻ bánh {batch.batch_code} ({batch.product.name}) hao hụt {batch.waste_rate}% vượt ngưỡng cho phép (>15%). Đạt {actual_qty}/{batch.planned_quantity}.",
                    request=request
                )

            messages.success(request, msg)
            return redirect('kitchen:batch_print_labels', pk=batch.pk)
        else:
            messages.error(request, msg)

    is_sufficient, materials_needed = batch.calculate_materials_needed()
    return render(request, 'kitchen_bom/batch_complete.html', {
        'batch': batch,
        'materials_needed': materials_needed,
        'is_sufficient': is_sufficient,
    })


@login_required
def batch_print_labels(request, pk):
    if getattr(request.user, 'role', None) not in [UserRole.BAKER, UserRole.ADMIN] and not request.user.is_superuser:
        return render_security_warning(
            request,
            reason=_('Chức năng in tem chỉ dành cho Thợ làm bánh và Quản trị viên.')
        )

    batch = get_object_or_404(KitchenBatch.objects.select_related('product'), pk=pk)
    
    batch_barcode_str = batch.batch_barcode
    batch_barcode_svg = generate_barcode_svg(batch_barcode_str)
    
    sample_barcode_str = batch.product.sku_code
    sample_barcode_svg = generate_barcode_svg(sample_barcode_str)

    label_type = request.GET.get('type', 'batch')
    label_count = int(request.GET.get('qty', batch.actual_quantity or batch.planned_quantity or 1))
    label_count = max(1, min(label_count, 100))

    baked_at = batch.completed_at or batch.created_at
    expires_at = batch.expires_at or (baked_at + timezone.timedelta(hours=batch.product.shelf_life_hours))

    if request.GET.get('audit') == '1':
        AuditLog.log(
            request.user,
            AuditActionType.LABEL_PRINT,
            target_code=batch.batch_code,
            description=f"In {label_count} tem ({label_type}) cho mẻ bánh {batch.batch_code} ({batch.product.name})",
            request=request
        )

    return render(request, 'kitchen_bom/batch_labels_print.html', {
        'batch': batch,
        'product': batch.product,
        'batch_barcode_str': batch_barcode_str,
        'batch_barcode_svg': batch_barcode_svg,
        'sample_barcode_str': sample_barcode_str,
        'sample_barcode_svg': sample_barcode_svg,
        'label_type': label_type,
        'baked_at': baked_at,
        'expires_at': expires_at,
        'label_count': label_count,
        'labels_list': range(label_count),
    })


@login_required
def api_preview_batch_materials(request):
    product_id = request.GET.get('product_id')
    quantity = int(request.GET.get('quantity', 0))

    if not product_id or quantity <= 0:
        return JsonResponse({'status': 'error', 'message': 'Tham số không hợp lệ'}, status=400)

    product = get_object_or_404(Product, id=product_id)
    boms = product.bom_items.select_related('material').all()

    materials_data = []
    is_sufficient = True

    for bom in boms:
        needed = bom.get_total_for_quantity(quantity)
        in_stock = bom.material.stock_quantity
        diff = in_stock - needed
        has_enough = diff >= Decimal('0')
        if not has_enough:
            is_sufficient = False

        materials_data.append({
            'material_name': bom.material.name,
            'unit': bom.material.unit,
            'needed': float(needed),
            'in_stock': float(in_stock),
            'has_enough': has_enough,
            'shortage': float(abs(diff)) if not has_enough else 0,
        })

    return JsonResponse({
        'status': 'success',
        'product_name': product.name,
        'quantity': quantity,
        'is_sufficient': is_sufficient,
        'materials': materials_data,
    })


@login_required
def batch_reports(request):
    user_role = getattr(request.user, 'role', None)
    if user_role not in [UserRole.ADMIN, UserRole.BAKER] and not request.user.is_staff and not request.user.is_superuser:
        return render_security_warning(
            request,
            reason=_('Chức năng Báo Cáo Mẻ Bánh chỉ dành cho Quản trị viên và Thợ làm bánh.')
        )

    tier_filter = request.GET.get('tier', '').strip()
    date_filter = request.GET.get('date', '').strip()
    status_filter = request.GET.get('status', '').strip()

    batches = KitchenBatch.objects.select_related('product', 'baker').order_by('-created_at')

    if status_filter:
        batches = batches.filter(status=status_filter)
    if date_filter:
        batches = batches.filter(created_at__date=date_filter)

    all_completed = KitchenBatch.objects.filter(status=BatchStatus.COMPLETED)
    total_batches = all_completed.count()
    total_baked_cakes = all_completed.aggregate(total=Sum('actual_quantity'))['total'] or 0
    avg_waste = all_completed.aggregate(avg=Avg('waste_rate'))['avg'] or Decimal('0.00')

    critical_count = sum(1 for b in all_completed if b.waste_tier['code'] == 'CRITICAL')
    warning_count = sum(1 for b in all_completed if b.waste_tier['code'] == 'WARNING')
    normal_count = sum(1 for b in all_completed if b.waste_tier['code'] == 'NORMAL')
    good_count = sum(1 for b in all_completed if b.waste_tier['code'] == 'GOOD')

    batch_list = []
    for b in batches:
        tier = b.waste_tier
        if tier_filter and tier['code'] != tier_filter:
            continue
        batch_list.append({
            'obj': b,
            'tier': tier,
        })

    return render(request, 'kitchen_bom/batch_reports.html', {
        'batches': batch_list,
        'total_batches': total_batches,
        'total_baked_cakes': total_baked_cakes,
        'avg_waste': round(float(avg_waste), 2),
        'critical_count': critical_count,
        'warning_count': warning_count,
        'normal_count': normal_count,
        'good_count': good_count,
        'selected_tier': tier_filter,
        'selected_status': status_filter,
        'selected_date': date_filter,
    })


@login_required
def counter_barcode_sheet(request):
    products = Product.objects.filter(status=ProductStatus.ACTIVE).select_related('category').order_by('category', 'name')
    
    items = []
    for p in products:
        items.append({
            'product': p,
            'barcode_svg': generate_barcode_svg(p.sku_code),
            'freshness': p.get_freshness_status(),
        })

    return render(request, 'kitchen_bom/counter_barcode_sheet.html', {
        'items': items,
        'now': timezone.now(),
    })
