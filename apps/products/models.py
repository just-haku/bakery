from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from decimal import Decimal

class Category(models.Model):
    name = models.CharField(max_length=100, verbose_name="Tên danh mục")
    slug = models.SlugField(max_length=120, unique=True, verbose_name="Slug / Đường dẫn")
    description = models.TextField(blank=True, verbose_name="Mô tả danh mục")
    icon = models.CharField(max_length=50, default='cake', verbose_name="Icon đại diện")
    is_active = models.BooleanField(default=True, verbose_name="Kích hoạt")

    class Meta:
        verbose_name = "Danh mục bánh"
        verbose_name_plural = "Danh mục bánh"

    def __str__(self):
        return self.name


class ProductStatus(models.TextChoices):
    ACTIVE = 'ACTIVE', _('Đang kinh doanh')
    SUSPENDED = 'SUSPENDED', _('Tạm ngưng bán')

class Product(models.Model):
    sku_code = models.CharField(
        max_length=30,
        unique=True,
        verbose_name="Mã SKU / Barcode"
    )
    name = models.CharField(
        max_length=150,
        verbose_name="Tên sản phẩm bánh"
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name='products',
        verbose_name="Danh mục"
    )
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Đơn giá niêm yết (VNĐ)"
    )
    stock_quantity = models.IntegerField(
        default=0,
        verbose_name="Số lượng tồn kho trong ngày"
    )
    shelf_life_hours = models.IntegerField(
        default=24,
        verbose_name="Thời hạn bảo quản tối đa (Giờ)"
    )
    is_custom_cake = models.BooleanField(
        default=False,
        verbose_name="Bánh kem đặt theo yêu cầu"
    )
    standard_batch_yield = models.IntegerField(
        default=30,
        verbose_name="Số lượng bánh chuẩn cho 1 mẻ công thức"
    )
    is_fast_bread = models.BooleanField(
        default=False,
        verbose_name="Bánh phổ biến bán nhanh (như Baguette - tùy chọn in tem)"
    )
    image = models.ImageField(
        upload_to='products/',
        blank=True,
        null=True,
        verbose_name="Hình ảnh sản phẩm"
    )
    image_url = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        verbose_name="URL hình ảnh thay thế"
    )
    status = models.CharField(
        max_length=20,
        choices=ProductStatus.choices,
        default=ProductStatus.ACTIVE,
        verbose_name="Trạng thái"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Thời điểm tạo"
    )

    class Meta:
        verbose_name = "Sản phẩm bánh"
        verbose_name_plural = "Danh sách bánh thành phẩm"

    def __str__(self):
        return f"[{self.sku_code}] {self.name} - {self.price:,.0f}đ (Tồn: {self.stock_quantity})"

    @property
    def is_in_stock(self):
        return self.stock_quantity > 0

    @property
    def is_low_stock(self):
        return self.stock_quantity <= 5

    def get_freshness_status(self):
        latest_batch = self.kitchen_batches.filter(status='COMPLETED').order_by('-completed_at').first()
        if not latest_batch or not latest_batch.completed_at:
            return {
                'status': 'FRESH',
                'is_near_expiry': False,
                'is_expired': False,
                'current_price': self.price,
                'original_price': self.price,
                'discount_percent': 0,
                'savings': Decimal('0'),
                'expires_at': None,
                'hours_left': None,
                'percentage_left': 100.0,
            }

        expires_at = latest_batch.expires_at
        total_seconds = self.shelf_life_hours * 3600
        remaining_seconds = (expires_at - timezone.now()).total_seconds()

        if remaining_seconds <= 0:
            return {
                'status': 'EXPIRED',
                'is_near_expiry': False,
                'is_expired': True,
                'current_price': self.price,
                'original_price': self.price,
                'discount_percent': 0,
                'savings': Decimal('0'),
                'expires_at': expires_at,
                'hours_left': 0,
                'percentage_left': 0.0,
            }

        ratio = remaining_seconds / total_seconds
        hours_left = max(0, round(remaining_seconds / 3600, 1))
        percentage_left = round(ratio * 100, 1)

        if ratio <= 0.25:
            # Giờ Vàng Cận Date: Giảm giá 40% (làm tròn hàng nghìn)
            disc_price = (self.price * Decimal('0.60') / Decimal('1000')).quantize(Decimal('1')) * Decimal('1000')
            savings = self.price - disc_price
            return {
                'status': 'NEAR_EXPIRY',
                'is_near_expiry': True,
                'is_expired': False,
                'current_price': disc_price,
                'original_price': self.price,
                'discount_percent': 40,
                'savings': savings,
                'expires_at': expires_at,
                'hours_left': hours_left,
                'percentage_left': percentage_left,
            }

        return {
            'status': 'FRESH',
            'is_near_expiry': False,
            'is_expired': False,
            'current_price': self.price,
            'original_price': self.price,
            'discount_percent': 0,
            'savings': Decimal('0'),
            'expires_at': expires_at,
            'hours_left': hours_left,
            'percentage_left': percentage_left,
        }


class CouponDiscountType(models.TextChoices):
    PERCENT = 'PERCENT', _('Giảm theo phần trăm (%)')
    FIXED_AMOUNT = 'FIXED_AMOUNT', _('Giảm số tiền cố định (VNĐ)')

class CouponConditionType(models.TextChoices):
    ALL = 'ALL', _('Mọi khách hàng & Đơn hàng')
    BIRTHDAY = 'BIRTHDAY', _('Ưu đãi Sinh nhật khách hàng')
    STORE_ANNIVERSARY = 'STORE_ANNIVERSARY', _('Kỷ niệm sinh nhật Tiệm Bánh')
    HOLIDAY = 'HOLIDAY', _('Dịp Lễ, Tết & Sự kiện')
    VIP_ONLY = 'VIP_ONLY', _('Đặc quyền Hội viên VIP')

class Coupon(models.Model):
    code = models.CharField(
        max_length=30,
        unique=True,
        verbose_name="Mã khuyến mãi"
    )
    title = models.CharField(
        max_length=150,
        verbose_name="Tên chương trình ưu đãi"
    )
    discount_type = models.CharField(
        max_length=20,
        choices=CouponDiscountType.choices,
        default=CouponDiscountType.PERCENT,
        verbose_name="Loại giảm giá"
    )
    discount_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Giá trị giảm (% hoặc VNĐ)"
    )
    max_discount_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name="Mức giảm tối đa (VNĐ, 0 = không giới hạn)"
    )
    min_order_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name="Giá trị đơn hàng tối thiểu (VNĐ)"
    )
    condition_type = models.CharField(
        max_length=30,
        choices=CouponConditionType.choices,
        default=CouponConditionType.ALL,
        verbose_name="Điều kiện áp dụng"
    )
    valid_from = models.DateTimeField(
        default=timezone.now,
        verbose_name="Hiệu lực từ ngày"
    )
    valid_to = models.DateTimeField(
        verbose_name="Hiệu lực đến ngày"
    )
    usage_limit = models.IntegerField(
        default=100,
        verbose_name="Giới hạn số lượt dùng"
    )
    used_count = models.IntegerField(
        default=0,
        verbose_name="Số lượt đã sử dụng"
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="Đang kích hoạt"
    )

    class Meta:
        verbose_name = "Mã khuyến mãi (Coupon)"
        verbose_name_plural = "Quản lý Coupon khuyến mãi"

    def __str__(self):
        val_str = f"{self.discount_value}%" if self.discount_type == CouponDiscountType.PERCENT else f"{self.discount_value:,.0f}đ"
        return f"{self.code} - {self.title} (Giảm {val_str})"

    def can_apply(self, customer_profile=None, order_amount=0):
        """
        Kiểm tra tính hợp lệ và trả về (is_valid, message, discount_amount)
        """
        now = timezone.now()
        if not self.is_active:
            return False, "Mã khuyến mãi hiện đang bị tạm khóa.", Decimal('0')

        if self.valid_from and now < self.valid_from:
            return False, "Mã khuyến mãi chưa đến thời gian áp dụng.", Decimal('0')

        if self.valid_to and now > self.valid_to:
            return False, "Mã khuyến mãi đã hết hạn sử dụng.", Decimal('0')

        if self.usage_limit and self.used_count >= self.usage_limit:
            return False, "Mã khuyến mãi đã hết lượt sử dụng.", Decimal('0')

        if order_amount < self.min_order_amount:
            return False, f"Đơn hàng phải đạt tối thiểu {self.min_order_amount:,.0f}đ để áp dụng mã này.", Decimal('0')

        # Kiểm tra điều kiện VIP
        if self.condition_type == CouponConditionType.VIP_ONLY:
            if not customer_profile or not customer_profile.check_vip_active():
                return False, "Mã khuyến mãi này chỉ dành riêng cho Hội viên VIP.", Decimal('0')

        # Kiểm tra điều kiện Sinh nhật khách
        if self.condition_type == CouponConditionType.BIRTHDAY:
            if not customer_profile or not customer_profile.user or not customer_profile.user.birthday:
                return False, "Mã ưu đãi này chỉ áp dụng cho khách hàng có ngày sinh nhật được xác thực.", Decimal('0')
            user_bday = customer_profile.user.birthday
            # Kiểm tra cùng tháng sinh
            if user_bday.month != now.month:
                return False, f"Mã khuyến mãi sinh nhật chỉ áp dụng trong tháng sinh của bạn (Tháng {user_bday.month}).", Decimal('0')

        # Tính toán mức giảm
        order_dec = Decimal(str(order_amount))
        if self.discount_type == CouponDiscountType.PERCENT:
            discount = (order_dec * (self.discount_value / Decimal('100'))).quantize(Decimal('1'))
            if self.max_discount_amount > 0 and discount > self.max_discount_amount:
                discount = self.max_discount_amount
        else:
            discount = min(self.discount_value, order_dec)

        return True, "Áp dụng mã giảm giá thành công!", discount
