from django.db import models, transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from decimal import Decimal
from apps.products.models import Product, Coupon
from apps.authentication.models import User, CustomerProfile, PointTransaction, PointTransactionType

class OrderType(models.TextChoices):
    POS = 'POS', _('Bán lẻ tại quầy POS')
    ONLINE = 'ONLINE', _('Khách đặt qua Web')

class PaymentMethod(models.TextChoices):
    CASH = 'CASH', _('Tiền mặt')
    TRANSFER = 'TRANSFER', _('Chuyển khoản VietQR')
    SPLIT = 'SPLIT', _('Tách thanh toán (Tiền mặt + Chuyển khoản + Điểm)')
    COD = 'COD', _('Thanh toán khi nhận hàng (COD)')

class DeliveryType(models.TextChoices):
    STORE_PICKUP = 'STORE_PICKUP', _('Nhận trực tiếp tại tiệm')
    DELIVERY = 'DELIVERY', _('Giao hàng tận nơi')

class OrderStatus(models.TextChoices):
    PENDING = 'PENDING', _('Chờ xử lý')
    PROCESSING = 'PROCESSING', _('Đang đóng gói')
    COMPLETED = 'COMPLETED', _('Đã hoàn tất')
    CANCELLED = 'CANCELLED', _('Đã hủy đơn')

class Order(models.Model):
    order_code = models.CharField(
        max_length=30,
        unique=True,
        verbose_name="Mã hóa đơn"
    )
    order_type = models.CharField(
        max_length=20,
        choices=OrderType.choices,
        default=OrderType.POS,
        verbose_name="Kênh bán"
    )
    cashier = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cashier_orders',
        verbose_name="Thu ngân phụ trách"
    )
    customer = models.ForeignKey(
        CustomerProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='orders',
        verbose_name="Khách hàng tích điểm"
    )
    subtotal = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Tổng tiền hàng (trước giảm giá)"
    )
    shipping_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        verbose_name="Phí vận chuyển (VNĐ)"
    )
    coupon = models.ForeignKey(
        Coupon,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='orders',
        verbose_name="Mã khuyến mãi đã áp dụng"
    )
    discount_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Tiền giảm giá từ Coupon / VIP (VNĐ)"
    )
    points_used = models.IntegerField(
        default=0,
        verbose_name="Số điểm ví đã dùng"
    )
    points_discount_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Tiền giảm tương ứng từ điểm ví (1 điểm = 1.000 VNĐ)"
    )
    final_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Tổng tiền thanh toán cuối cùng (VNĐ)"
    )
    points_earned = models.IntegerField(
        default=0,
        verbose_name="Điểm tích lũy nhận được (10% giá trị đơn)"
    )
    payment_method = models.CharField(
        max_length=20,
        choices=PaymentMethod.choices,
        default=PaymentMethod.CASH,
        verbose_name="Phương thức thanh toán"
    )
    
    # Chi tiết tách thanh toán (Split Payment)
    cash_paid = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Số tiền mặt trả (VNĐ)"
    )
    transfer_paid = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Số tiền chuyển khoản VietQR (VNĐ)"
    )
    points_paid = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Số tiền trả bằng điểm ví (VNĐ)"
    )
    change_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Tiền thừa thối lại khách (VNĐ)"
    )

    # Thông tin giao nhận
    delivery_type = models.CharField(
        max_length=20,
        choices=DeliveryType.choices,
        default=DeliveryType.STORE_PICKUP,
        verbose_name="Hình thức nhận hàng"
    )
    shipping_address = models.TextField(
        blank=True,
        verbose_name="Địa chỉ giao hàng"
    )
    recipient_name = models.CharField(
        max_length=150,
        blank=True,
        verbose_name="Tên người nhận"
    )
    recipient_phone = models.CharField(
        max_length=20,
        blank=True,
        verbose_name="SĐT người nhận"
    )
    notes = models.TextField(
        blank=True,
        verbose_name="Ghi chú đơn hàng"
    )
    status = models.CharField(
        max_length=20,
        choices=OrderStatus.choices,
        default=OrderStatus.COMPLETED,
        verbose_name="Trạng thái đơn hàng"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Thời điểm lập hóa đơn"
    )

    class Meta:
        verbose_name = "Hóa đơn bán lẻ & Đơn hàng"
        verbose_name_plural = "Quản lý Hóa đơn & Bán hàng"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.order_code} - {self.final_amount:,.0f}đ ({self.get_payment_method_display()}) - {self.get_status_display()}"

    def finalize_order_loyalty(self):
        """
        Nghiệp vụ tích 10% điểm cho mỗi đơn hàng hoàn tất:
        1 điểm = 1.000 VNĐ -> Điểm = int(final_amount * 0.10 / 1000)
        """
        if self.customer and self.points_earned == 0 and (self.status == OrderStatus.COMPLETED or self.order_type == OrderType.ONLINE):
            earned_pts = int((Decimal(str(self.final_amount)) * Decimal('0.10')) / Decimal('1000'))
            if earned_pts > 0:
                self.points_earned = earned_pts
                self.save(update_fields=['points_earned'])

                # Cộng vào ví khách
                self.customer.points_balance += earned_pts
                self.customer.total_spent += Decimal(str(self.final_amount))
                self.customer.update_tier()
                self.customer.save(update_fields=['points_balance', 'total_spent'])

                # Ghi lịch sử biến động điểm
                PointTransaction.objects.create(
                    customer=self.customer,
                    transaction_type=PointTransactionType.EARN,
                    points=earned_pts,
                    amount_money=self.final_amount,
                    notes=f"Tích lũy 10% từ đơn hàng {self.order_code}"
                )


class OrderItem(models.Model):
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name="Hóa đơn"
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name='order_items',
        verbose_name="Sản phẩm bánh"
    )
    quantity = models.IntegerField(
        default=1,
        verbose_name="Số lượng mua"
    )
    unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="Đơn giá tại thời điểm bán"
    )
    subtotal = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="Thành tiền"
    )

    class Meta:
        verbose_name = "Chi tiết hóa đơn"
        verbose_name_plural = "Danh sách chi tiết hóa đơn"

    def __str__(self):
        return f"{self.product.name} x {self.quantity} = {self.subtotal:,.0f}đ"
