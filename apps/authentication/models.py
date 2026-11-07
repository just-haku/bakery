from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from datetime import timedelta
from apps.kitchen_bom.barcode_utils import generate_barcode_svg

class UserRole(models.TextChoices):
    ADMIN = 'ADMIN', _('Quản trị viên / Chủ tiệm')
    CASHIER = 'CASHIER', _('Thu ngân quầy POS')
    BAKER = 'BAKER', _('Thợ làm bánh')
    CUSTOMER = 'CUSTOMER', _('Khách hàng')

class User(AbstractUser):
    role = models.CharField(
        max_length=20,
        choices=UserRole.choices,
        default=UserRole.CUSTOMER,
        verbose_name="Vai trò hệ thống"
    )
    phone = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        unique=True,
        verbose_name="Số điện thoại"
    )
    birthday = models.DateField(
        blank=True,
        null=True,
        verbose_name="Ngày sinh"
    )
    avatar = models.ImageField(
        upload_to='avatars/',
        blank=True,
        null=True,
        verbose_name="Ảnh đại diện"
    )

    class Meta:
        verbose_name = "Người dùng"
        verbose_name_plural = "Danh sách người dùng"

    @property
    def order_count(self):
        try:
            return self.cashier_orders.count()
        except Exception:
            return 0

    @property
    def batch_count(self):
        try:
            return self.batches.count()
        except Exception:
            return 0

    def can_be_deleted(self):
        """
        Kiểm tra tài khoản nhân viên / admin có thể xóa được hay không:
        1. Chỉ cho phép xóa nếu KHÔNG có bất kỳ đơn hàng nào (Order) hoặc mẻ bánh nào (KitchenBatch).
        2. Nếu là ADMIN, không thể tự xóa nếu là Admin duy nhất còn lại trong hệ thống.
        """
        if self.order_count > 0 or self.batch_count > 0:
            return False
        if self.role == UserRole.ADMIN:
            if User.objects.filter(role=UserRole.ADMIN).count() <= 1:
                return False
        return True

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        # Chỉ tự động tạo hồ sơ CustomerProfile nếu người dùng là Khách Hàng (CUSTOMER)
        if self.role == UserRole.CUSTOMER:
            try:
                _ = self.customer_profile
            except (CustomerProfile.DoesNotExist, AttributeError):
                CustomerProfile.objects.get_or_create(
                    user=self,
                    defaults={
                        'phone': self.phone or f'USER_{self.id}',
                        'full_name': self.get_full_name() or self.username,
                    }
                )

    @property
    def is_admin_user(self):
        return self.role == UserRole.ADMIN or self.is_superuser

    @property
    def is_cashier_user(self):
        return self.role == UserRole.CASHIER or self.is_admin_user

    @property
    def is_baker_user(self):
        return self.role == UserRole.BAKER or self.is_admin_user


class CustomerTier(models.TextChoices):
    STANDARD = 'STANDARD', _('Đồng (Tiêu chuẩn)')
    SILVER = 'SILVER', _('Bạc')
    GOLD = 'GOLD', _('Vàng')
    DIAMOND = 'DIAMOND', _('Kim Cương')

class CustomerProfile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='customer_profile',
        verbose_name="Tài khoản liên kết"
    )
    phone = models.CharField(
        max_length=20,
        unique=True,
        verbose_name="Số điện thoại hội viên"
    )
    full_name = models.CharField(
        max_length=150,
        verbose_name="Họ và tên khách hàng"
    )
    points_balance = models.IntegerField(
        default=0,
        verbose_name="Số dư điểm ví (1 điểm = 1.000 VNĐ)"
    )
    total_spent = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Tổng chi tiêu tích lũy (VNĐ)"
    )
    tier = models.CharField(
        max_length=20,
        choices=CustomerTier.choices,
        default=CustomerTier.STANDARD,
        verbose_name="Hạng thành viên"
    )
    member_card_code = models.CharField(
        max_length=40,
        unique=True,
        blank=True,
        null=True,
        verbose_name="Mã thẻ thành viên / Barcode"
    )
    is_vip = models.BooleanField(
        default=False,
        verbose_name="Hội viên VIP"
    )
    vip_expiry_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Ngày hết hạn VIP"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Ngày tham gia"
    )

    class Meta:
        verbose_name = "Hồ sơ khách hàng"
        verbose_name_plural = "Danh sách khách hàng & Hội viên"

    def __str__(self):
        vip_tag = " [VIP]" if self.check_vip_active() else ""
        return f"{self.full_name} ({self.phone}){vip_tag} - {self.points_balance:,} điểm"

    def save(self, *args, **kwargs):
        if not self.member_card_code:
            code_base = self.phone or (f"00{self.id}" if self.id else "000000")
            clean_code = ''.join(c for c in code_base if c.isalnum())
            self.member_card_code = f"CUST-{clean_code}"
        super().save(*args, **kwargs)

    @property
    def barcode_svg(self):
        return generate_barcode_svg(self.member_card_code or f"CUST-{self.phone}")

    def check_vip_active(self):
        if self.is_vip and self.vip_expiry_date:
            return self.vip_expiry_date >= timezone.now().date()
        return self.is_vip

    def update_tier(self):
        """Tự động nâng hạng thành viên dựa trên tổng chi tiêu"""
        spent = float(self.total_spent)
        if spent >= 15000000:
            self.tier = CustomerTier.DIAMOND
        elif spent >= 5000000:
            self.tier = CustomerTier.GOLD
        elif spent >= 1500000:
            self.tier = CustomerTier.SILVER
        else:
            self.tier = CustomerTier.STANDARD
        self.save(update_fields=['tier'])

    @property
    def points_in_vnd(self):
        return self.points_balance * 1000


class VIPPackageType(models.TextChoices):
    MONTHLY = 'MONTHLY', _('Gói VIP 1 Tháng')
    YEARLY = 'YEARLY', _('Gói VIP 1 Năm')

class VIPPackage(models.Model):
    package_type = models.CharField(
        max_length=20,
        choices=VIPPackageType.choices,
        unique=True,
        verbose_name="Loại gói VIP"
    )
    name = models.CharField(
        max_length=100,
        verbose_name="Tên gói"
    )
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Giá gói (VNĐ)"
    )
    discount_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=10.0,
        verbose_name="% Chiết khấu đơn hàng"
    )
    duration_days = models.IntegerField(
        default=30,
        verbose_name="Thời hạn (Số ngày)"
    )
    description = models.TextField(
        blank=True,
        verbose_name="Mô tả quyền lợi"
    )

    class Meta:
        verbose_name = "Gói hội viên VIP"
        verbose_name_plural = "Quản lý Gói VIP"

    def __str__(self):
        return f"{self.name} - {self.price:,.0f}đ (Giảm {self.discount_percentage}%)"


class PointTransactionType(models.TextChoices):
    TOPUP = 'TOPUP', _('Nạp điểm ví')
    EARN = 'EARN', _('Tích điểm từ đơn hàng (10%)')
    REDEEM = 'REDEEM', _('Dùng điểm thanh toán')
    ADJUST = 'ADJUST', _('Điều chỉnh bởi Admin')

class PointTransaction(models.Model):
    customer = models.ForeignKey(
        CustomerProfile,
        on_delete=models.CASCADE,
        related_name='point_transactions',
        verbose_name="Khách hàng"
    )
    transaction_type = models.CharField(
        max_length=20,
        choices=PointTransactionType.choices,
        verbose_name="Loại giao dịch"
    )
    points = models.IntegerField(
        verbose_name="Số điểm biến động"
    )
    amount_money = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Số tiền tương ứng (VNĐ)"
    )
    payment_method = models.CharField(
        max_length=20,
        default='TRANSFER',
        verbose_name="Phương thức nạp"
    )
    notes = models.TextField(
        blank=True,
        verbose_name="Ghi chú"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Thời gian giao dịch"
    )

    class Meta:
        verbose_name = "Giao dịch điểm ví"
        verbose_name_plural = "Lịch sử biến động điểm ví"
