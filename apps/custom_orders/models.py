from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from decimal import Decimal

class CakeOrderStatus(models.TextChoices):
    RECEIVED = 'RECEIVED', _('Đã tiếp nhận đơn')
    BAKING = 'BAKING', _('Bếp đang làm bánh')
    READY = 'READY', _('Bánh đã sẵn sàng nhận')
    DELIVERED = 'DELIVERED', _('Đã giao cho khách')
    CANCELLED = 'CANCELLED', _('Đã hủy đơn')

class CustomCakeOrder(models.Model):
    order_code = models.CharField(
        max_length=30,
        unique=True,
        verbose_name="Mã đơn đặt bánh"
    )
    customer_name = models.CharField(
        max_length=150,
        verbose_name="Tên khách hàng"
    )
    customer_phone = models.CharField(
        max_length=20,
        verbose_name="Số điện thoại"
    )
    cake_base = models.CharField(
        max_length=50,
        default='Vani',
        verbose_name="Cốt bánh (Vani, Socola, Red Velvet, Matcha)"
    )
    cream_flavor = models.CharField(
        max_length=50,
        default='Kem bơ sữa',
        verbose_name="Vị kem (Kem bơ, Whipping cream, Phô mai, Ganache...)"
    )
    size = models.CharField(
        max_length=30,
        default='20cm',
        verbose_name="Kích thước (16cm, 20cm, 25cm, 2 tầng)"
    )
    custom_message = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Lời chúc viết lên bánh nghệ thuật"
    )
    notes = models.TextField(
        blank=True,
        verbose_name="Ghi chú đặc biệt (độ ngọt, hoa quả, chi tiết riêng)"
    )
    sample_image = models.ImageField(
        upload_to='custom_cakes/',
        blank=True,
        null=True,
        verbose_name="Ảnh mẫu trang trí"
    )
    sample_image_url = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        verbose_name="URL ảnh mẫu tham khảo"
    )
    pickup_datetime = models.DateTimeField(
        verbose_name="Ngày giờ hẹn lấy bánh"
    )
    total_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Tổng giá trị đơn bánh (VNĐ)"
    )
    deposit_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Tiền đặt cọc (Bắt buộc tối thiểu 30%)"
    )
    remaining_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Tiền còn lại phải thanh toán"
    )
    status = models.CharField(
        max_length=20,
        choices=CakeOrderStatus.choices,
        default=CakeOrderStatus.RECEIVED,
        verbose_name="Trạng thái đơn hàng"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Thời điểm đặt"
    )

    class Meta:
        verbose_name = "Đơn đặt bánh kem theo hẹn"
        verbose_name_plural = "Quản lý Đặt bánh kem theo hẹn"

    def __str__(self):
        return f"{self.order_code} - {self.customer_name} ({self.cake_base} {self.size}) - {self.get_status_display()}"

    def save(self, *args, **kwargs):
        if not self.order_code:
            now_str = timezone.now().strftime('%Y%m%d%H%M%S')
            self.order_code = f"BK{now_str}"
        self.remaining_amount = max(Decimal('0'), Decimal(str(self.total_price)) - Decimal(str(self.deposit_amount)))
        super().save(*args, **kwargs)

    @classmethod
    def validate_deposit(cls, total_price, deposit_amount):
        """Quy định bắt buộc đặt cọc tối thiểu 30% giá trị bánh (TC04)"""
        total_dec = Decimal(str(total_price))
        dep_dec = Decimal(str(deposit_amount))
        min_deposit = (total_dec * Decimal('0.30')).quantize(Decimal('1'))
        if dep_dec < min_deposit:
            return False, f"Yêu cầu đặt cọc tối thiểu 30% ({min_deposit:,.0f} VNĐ). Số tiền bạn nhập ({dep_dec:,.0f} VNĐ) chưa đủ."
        return True, "Hợp lệ"
