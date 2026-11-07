from django.db import models
from decimal import Decimal
import urllib.parse
from .utils import get_client_ip

class StoreSetting(models.Model):
    store_name = models.CharField(
        max_length=150,
        default="Tiệm Bánh Artisan Bakery",
        verbose_name="Tên tiệm bánh"
    )
    phone = models.CharField(
        max_length=30,
        default="0912 345 678",
        verbose_name="Hotline tiệm"
    )
    address = models.CharField(
        max_length=255,
        default="123 Đường Bánh Ngọt, Quận 1, TP. Hồ Chí Minh",
        verbose_name="Địa chỉ tiệm"
    )
    
    # Cấu hình VietQR
    vietqr_bank_id = models.CharField(
        max_length=20,
        default="MB",
        verbose_name="Mã Ngân Hàng VietQR (vd: MB, ICB, VCB, ACB, TPB)"
    )
    vietqr_account_no = models.CharField(
        max_length=30,
        default="0912345678",
        verbose_name="Số tài khoản ngân hàng"
    )
    vietqr_account_name = models.CharField(
        max_length=100,
        default="TIEM BANH ARTISAN",
        verbose_name="Tên chủ tài khoản"
    )
    vietqr_template = models.CharField(
        max_length=30,
        default="compact2",
        verbose_name="Mẫu VietQR (compact2 / qr_only / compact)"
    )

    # Cấu hình phí ship & Khách VIP
    default_shipping_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=30000.00,
        verbose_name="Phí giao hàng mặc định (VNĐ)"
    )
    vip_monthly_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=50000.00,
        verbose_name="Giá gói VIP 1 Tháng (VNĐ)"
    )
    vip_yearly_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=500000.00,
        verbose_name="Giá gói VIP 1 Năm (VNĐ)"
    )
    vip_discount_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=10.00,
        verbose_name="% Chiết khấu đơn hàng cho VIP"
    )

    class Meta:
        verbose_name = "Cài đặt hệ thống"
        verbose_name_plural = "Cài đặt hệ thống"

    def __str__(self):
        return f"{self.store_name} ({self.vietqr_bank_id} - {self.vietqr_account_no})"

    @classmethod
    def get_settings(cls):
        setting, _ = cls.objects.get_or_create(id=1)
        return setting

    def generate_vietqr_url(self, amount, order_code):
        """
        Sinh URL VietQR động theo định dạng:
        https://img.vietqr.io/image/<BANK_ID>-<ACCOUNT_NO>-<TEMPLATE>.png?amount=<AMOUNT>&addInfo=<DESCRIPTION>&accountName=<ACCOUNT_NAME>
        Cú pháp description: TB <ORDER_CODE>
        """
        amount_int = int(round(float(amount)))
        desc = f"TB {order_code}"
        params = {
            'amount': amount_int,
            'addInfo': desc,
            'accountName': self.vietqr_account_name
        }
        query_string = urllib.parse.urlencode(params)
        url = f"https://img.vietqr.io/image/{self.vietqr_bank_id}-{self.vietqr_account_no}-{self.vietqr_template}.png?{query_string}"
        return url, desc


class AuditActionType(models.TextChoices):
    MATERIAL_STOCK_IN = 'MATERIAL_STOCK_IN', 'Nhập kho nguyên liệu'
    BATCH_CREATE = 'BATCH_CREATE', 'Khởi tạo mẻ bánh'
    BATCH_COMPLETE = 'BATCH_COMPLETE', 'Nghiệm thu mẻ bánh'
    BATCH_RED_ALERT = 'BATCH_RED_ALERT', 'Cảnh báo hao hụt nghiêm trọng'
    LABEL_PRINT = 'LABEL_PRINT', 'In tem dán bánh'
    RECEIPT_PRINT = 'RECEIPT_PRINT', 'In hóa đơn bán hàng'
    POINTS_REDEEM = 'POINTS_REDEEM', 'Sử dụng điểm tích lũy'
    COUPON_APPLY = 'COUPON_APPLY', 'Áp dụng mã giảm giá'

class AuditLog(models.Model):
    user = models.ForeignKey(
        'authentication.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs',
        verbose_name="Người thực hiện"
    )
    action_type = models.CharField(
        max_length=40,
        choices=AuditActionType.choices,
        verbose_name="Loại hành động"
    )
    target_code = models.CharField(
        max_length=60,
        blank=True,
        verbose_name="Mã đối tượng"
    )
    description = models.TextField(
        verbose_name="Chi tiết"
    )
    ip_address = models.CharField(
        max_length=45,
        blank=True,
        null=True,
        verbose_name="Địa chỉ IP"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Thời gian"
    )

    class Meta:
        verbose_name = "Nhật ký kiểm toán"
        verbose_name_plural = "Nhật ký kiểm toán hệ thống"
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.get_action_type_display()}] {self.target_code} ({self.user}) - {self.created_at:%d/%m/%Y %H:%M}"

    @classmethod
    def log(cls, user, action_type, target_code="", description="", request=None):
        ip = get_client_ip(request) if request else None
        u = user if getattr(user, 'is_authenticated', False) else None
        return cls.objects.create(
            user=u,
            action_type=action_type,
            target_code=target_code,
            description=description,
            ip_address=ip
        )

