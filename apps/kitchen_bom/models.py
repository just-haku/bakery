from django.db import models, transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from datetime import timedelta
from decimal import Decimal
from apps.products.models import Product
from django.contrib.auth import get_user_model

User = get_user_model()

class MaterialType(models.TextChoices):
    FLOUR = 'FLOUR', _('Bột & Tinh bột')
    DAIRY_FAT = 'DAIRY_FAT', _('Bơ sữa & Chất béo')
    SWEETENER = 'SWEETENER', _('Đường & Chất ngọt')
    EGG_PROTEIN = 'EGG_PROTEIN', _('Trứng & Đạm')
    YEAST_ADDITIVE = 'YEAST_ADDITIVE', _('Men nở & Phụ gia')
    FRUIT_TOPPING = 'FRUIT_TOPPING', _('Trái cây & Topping')
    CHOCOLATE_NUTS = 'CHOCOLATE_NUTS', _('Sô-cô-la & Các loại hạt')
    PACKAGING_OTHER = 'PACKAGING_OTHER', _('Bao bì & Khác')

class Material(models.Model):
    code = models.CharField(
        max_length=30,
        unique=True,
        verbose_name="Mã nguyên vật liệu"
    )
    name = models.CharField(
        max_length=150,
        verbose_name="Tên nguyên liệu (Bột, bơ, sữa...)"
    )
    material_type = models.CharField(
        max_length=30,
        choices=MaterialType.choices,
        default=MaterialType.FLOUR,
        verbose_name="Phân loại nguyên liệu"
    )
    unit = models.CharField(
        max_length=30,
        default='kg',
        verbose_name="Đơn vị tính (kg, g, lít, quả, hộp...)"
    )
    stock_quantity = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        default=0,
        verbose_name="Số lượng tồn kho hiện tại"
    )
    min_threshold = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        default=5.000,
        verbose_name="Ngưỡng cảnh báo tối thiểu"
    )
    unit_cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Đơn giá nhập trung bình (VNĐ)"
    )

    class Meta:
        verbose_name = "Nguyên vật liệu"
        verbose_name_plural = "Quản lý Nguyên vật liệu"

    def __str__(self):
        return f"[{self.code}] {self.name} ({self.get_material_type_display()}) - Tồn: {self.stock_quantity} {self.unit}"

    @property
    def is_low_stock(self):
        return self.stock_quantity <= self.min_threshold


class BillOfMaterials(models.Model):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='bom_items',
        verbose_name="Sản phẩm bánh áp dụng"
    )
    material = models.ForeignKey(
        Material,
        on_delete=models.CASCADE,
        related_name='bom_products',
        verbose_name="Nguyên liệu thô"
    )
    quantity_needed = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        verbose_name="Định mức cho 1 chiếc bánh"
    )
    waste_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=5.00,
        verbose_name="Hao hụt tiêu chuẩn (%) - Mặc định 5%"
    )

    class Meta:
        verbose_name = "Định mức BOM (Công thức)"
        verbose_name_plural = "Bảng định mức BOM"
        unique_together = ('product', 'material')

    def __str__(self):
        return f"{self.product.name} -> {self.material.name}: {self.quantity_needed} {self.material.unit} (+{self.waste_percentage}% hao hụt)"

    def get_total_for_quantity(self, batch_quantity):
        """Tính tổng lượng nguyên liệu cần dùng bao gồm hao hụt tiêu chuẩn"""
        waste_mult = Decimal('1') + (self.waste_percentage / Decimal('100'))
        return (Decimal(str(batch_quantity)) * self.quantity_needed * waste_mult).quantize(Decimal('0.001'))


class BatchStatus(models.TextChoices):
    PENDING = 'PENDING', _('Chờ chuẩn bị')
    IN_PROGRESS = 'IN_PROGRESS', _('Đang nướng bánh')
    COMPLETED = 'COMPLETED', _('Đã nghiệm thu & Nhập kho')
    CANCELLED = 'CANCELLED', _('Đã hủy mẻ')

class KitchenBatch(models.Model):
    batch_code = models.CharField(
        max_length=30,
        unique=True,
        verbose_name="Mã mẻ nướng (Lệnh sản xuất)"
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='kitchen_batches',
        verbose_name="Loại bánh nướng"
    )
    planned_quantity = models.IntegerField(
        verbose_name="Số lượng dự kiến nướng"
    )
    actual_quantity = models.IntegerField(
        default=0,
        verbose_name="Số lượng đạt chuẩn nghiệm thu"
    )
    baker = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='batches',
        verbose_name="Thợ làm bánh chịu trách nhiệm"
    )
    waste_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=5.00,
        verbose_name="Tỷ lệ hao hụt thực tế (%)"
    )
    materials_deducted = models.BooleanField(
        default=False,
        verbose_name="Đã trừ nguyên liệu kho"
    )
    status = models.CharField(
        max_length=20,
        choices=BatchStatus.choices,
        default=BatchStatus.PENDING,
        verbose_name="Trạng thái mẻ bánh"
    )
    notes = models.TextField(
        blank=True,
        verbose_name="Ghi chú mẻ bánh / Lý do hao hụt"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Thời điểm tạo lệnh"
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Thời điểm hoàn thành nghiệm thu"
    )

    class Meta:
        verbose_name = "Lệnh sản xuất mẻ bánh"
        verbose_name_plural = "Bếp & Lệnh sản xuất"

    def __str__(self):
        return f"{self.batch_code} - {self.product.name} (SL: {self.planned_quantity})"

    @property
    def expires_at(self):
        """Hạn sử dụng tính từ thời điểm hoàn thành + shelf_life_hours của bánh"""
        if self.completed_at:
            return self.completed_at + timedelta(hours=self.product.shelf_life_hours)
        return None

    @property
    def is_near_expiry(self):
        """Kiểm tra nếu mẻ bánh này còn <= 25% thời hạn bảo quản"""
        if not self.completed_at or not self.product.shelf_life_hours:
            return False
        total_seconds = self.product.shelf_life_hours * 3600
        remaining_seconds = (self.expires_at - timezone.now()).total_seconds()
        return 0 < remaining_seconds <= (total_seconds * 0.25)

    @property
    def is_expired(self):
        """Kiểm tra mẻ bánh đã hết hạn hay chưa"""
        if not self.expires_at:
            return False
        return timezone.now() >= self.expires_at

    @property
    def discounted_price_40(self):
        """Đơn giá giảm 40% (làm tròn hàng nghìn)"""
        disc = self.product.price * Decimal('0.60')
        return (disc / Decimal('1000')).quantize(Decimal('1')) * Decimal('1000')

    def calculate_materials_needed(self):
        """Tính toán và kiểm tra tồn kho nguyên vật liệu cần cho mẻ bánh"""
        boms = self.product.bom_items.select_related('material').all()
        results = []
        is_sufficient = True

        for bom in boms:
            needed = bom.get_total_for_quantity(self.planned_quantity)
            in_stock = bom.material.stock_quantity
            diff = in_stock - needed
            has_enough = diff >= Decimal('0')
            if not has_enough:
                is_sufficient = False
            results.append({
                'material': bom.material,
                'needed': needed,
                'in_stock': in_stock,
                'has_enough': has_enough,
                'shortage': abs(diff) if not has_enough else Decimal('0'),
            })
        return is_sufficient, results

    @property
    def batch_barcode(self):
        """Mã Barcode định danh cho từng chiếc bánh thuộc mẻ (SKU + Mã Mẻ)"""
        return f"{self.product.sku_code}-{self.batch_code}"

    @property
    def waste_tier(self):
        rate = float(self.waste_rate or 0)
        if rate <= 5.0:
            return {
                'code': 'GOOD',
                'label': 'Tốt',
                'badge_class': 'badge-success',
                'color': '#15803d',
                'bg_color': '#dcfce7',
                'border_color': '#86efac',
                'icon': 'shield-check',
                'description': 'Hao hụt mức tối ưu (<= 5%)'
            }
        elif rate <= 10.0:
            return {
                'code': 'NORMAL',
                'label': 'Bình thường',
                'badge_class': 'badge-info',
                'color': '#2563eb',
                'bg_color': '#dbeafe',
                'border_color': '#93c5fd',
                'icon': 'check-circle',
                'description': 'Hao hụt trong mức cho phép (5 - 10%)'
            }
        elif rate <= 15.0:
            return {
                'code': 'WARNING',
                'label': 'Cảnh báo',
                'badge_class': 'badge-warning',
                'color': '#d97706',
                'bg_color': '#fef3c7',
                'border_color': '#fde68a',
                'icon': 'alert-triangle',
                'description': 'Hao hụt cao (10 - 15%)'
            }
        else:
            return {
                'code': 'CRITICAL',
                'label': 'Báo động đỏ',
                'badge_class': 'badge-danger',
                'color': '#dc2626',
                'bg_color': '#fee2e2',
                'border_color': '#fca5a5',
                'icon': 'alert-octagon',
                'description': 'Hao hụt vượt ngưỡng cảnh báo (> 15%)'
            }

    @transaction.atomic
    def deduct_materials(self):
        """Trừ nguyên liệu tồn kho khi bắt đầu nướng mẻ bánh"""
        if self.materials_deducted:
            return True, "Nguyên liệu đã được trừ trước đó."
        is_sufficient, materials_needed = self.calculate_materials_needed()
        if not is_sufficient:
            missing = [f"{m['material'].name} (thiếu {m['shortage']} {m['material'].unit})" for m in materials_needed if not m['has_enough']]
            return False, f"Kho không đủ nguyên liệu: {', '.join(missing)}"
        
        for item in materials_needed:
            mat = item['material']
            mat.stock_quantity -= item['needed']
            mat.save(update_fields=['stock_quantity'])
        
        self.materials_deducted = True
        self.save(update_fields=['materials_deducted'])
        return True, "Đã trừ nguyên liệu kho thành công."

    @transaction.atomic
    def complete_batch(self, actual_qty=None, notes=None):
        """
        Nghiệm thu mẻ bánh:
        1. Trừ nguyên liệu nếu chưa trừ.
        2. Tăng tồn kho bánh thành phẩm.
        3. Tính toán tỷ lệ hao hụt thực tế:
           - 0-5%: Tốt
           - 5-10%: Bình thường
           - 10-15%: Cảnh báo
           - Trên 15%: Báo động đỏ
        4. Cập nhật trạng thái COMPLETED.
        """
        if self.status == BatchStatus.COMPLETED:
            return False, "Mẻ bánh này đã được nghiệm thu trước đó."

        if actual_qty is None:
            actual_qty = self.planned_quantity

        if not self.materials_deducted:
            ok, msg = self.deduct_materials()
            if not ok:
                return False, msg

        # Tính tỷ lệ hao hụt (%)
        if self.planned_quantity > 0:
            if actual_qty < self.planned_quantity:
                waste = (Decimal(str(self.planned_quantity - actual_qty)) / Decimal(str(self.planned_quantity))) * Decimal('100')
                self.waste_rate = waste.quantize(Decimal('0.01'))
            else:
                self.waste_rate = Decimal('0.00')

        if notes:
            self.notes = (self.notes + "\n" + notes).strip()

        # Tăng tồn kho bánh thành phẩm
        self.product.stock_quantity += actual_qty
        self.product.save(update_fields=['stock_quantity'])

        # Cập nhật thông tin mẻ
        self.actual_quantity = actual_qty
        self.status = BatchStatus.COMPLETED
        self.completed_at = timezone.now()
        self.save()

        tier = self.waste_tier
        return True, f"Nghiệm thu thành công mẻ {self.batch_code}! Đạt chuẩn {actual_qty}/{self.planned_quantity} cái. Tỷ lệ hao hụt: {self.waste_rate}% ({tier['label']})."

