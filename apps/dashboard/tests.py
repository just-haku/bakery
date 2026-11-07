from django.test import TestCase, Client
from django.utils import timezone
from datetime import timedelta, date
from decimal import Decimal

from apps.authentication.models import User, UserRole, CustomerProfile, CustomerTier
from apps.products.models import Category, Product, ProductStatus, Coupon, CouponDiscountType, CouponConditionType
from apps.kitchen_bom.models import Material, BillOfMaterials, KitchenBatch, BatchStatus
from apps.pos.models import Order, OrderItem, OrderStatus, PaymentMethod, OrderType
from apps.custom_orders.models import CustomCakeOrder, CakeOrderStatus
from apps.dashboard.models import StoreSetting

class BakerySystemUnitTests(TestCase):

    def setUp(self):
        # Thiết lập cấu hình hệ thống & VietQR
        self.setting = StoreSetting.objects.create(
            id=1,
            store_name="Artisan Bakery Test",
            vietqr_bank_id="MB",
            vietqr_account_no="0912345678",
            vietqr_account_name="TIEM BANH TEST",
            vietqr_template="compact2",
            default_shipping_fee=Decimal('30000'),
            vip_discount_percent=Decimal('10.00'),
        )

        self.category = Category.objects.create(name="Bánh Mì Test", slug="banh-mi-test")
        self.product = Product.objects.create(
            sku_code="B01",
            name="Bánh Mì Hoa Cúc Test",
            category=self.category,
            price=Decimal('50000'),
            stock_quantity=10,
            shelf_life_hours=24,
            status=ProductStatus.ACTIVE
        )

    def test_01_admin_setup_one_time_and_customer_registration(self):
        """Khởi tạo Admin ban đầu 1 lần duy nhất trên Port 8010 & Khách hàng tự do đăng ký luôn là CUSTOMER"""
        client = Client()

        # 1. Ban đầu chưa có Admin: Khởi tạo Operator Admin đầu tiên
        response = client.post('/auth/admin-setup/', {
            'username': 'master_operator',
            'first_name': 'Chủ',
            'last_name': 'Tiệm',
            'email': 'operator@bakery.local',
            'password': 'Op3rat0r@Bakery2026!',
            'password_confirm': 'Op3rat0r@Bakery2026!',
        }, HTTP_X_PORTAL_ROLE='ADMIN')
        self.assertEqual(response.status_code, 302)

        admin = User.objects.get(username='master_operator')
        self.assertEqual(admin.role, UserRole.ADMIN)
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)

        # 2. Sau khi đã có Admin: Thử khởi tạo lại Admin bị chặn ngay lập tức (1-time only)
        response_repeat = client.post('/auth/admin-setup/', {
            'username': 'fake_admin',
            'password': 'Op3rat0r@Bakery2026!',
            'password_confirm': 'Op3rat0r@Bakery2026!',
        }, HTTP_X_PORTAL_ROLE='ADMIN')
        self.assertEqual(response_repeat.status_code, 302)
        self.assertFalse(User.objects.filter(username='fake_admin').exists())

        # 3. Khách hàng tự do đăng ký trên cổng 8008 luôn luôn là CUSTOMER
        client_cust = Client()
        response_cust = client_cust.post('/auth/register/', {
            'username': 'regular_customer',
            'first_name': 'Khách',
            'last_name': 'Hàng',
            'email': 'cust@example.com',
            'password': 'Cust0m3r@Bakery2026!',
            'password_confirm': 'Cust0m3r@Bakery2026!',
        }, HTTP_X_PORTAL_ROLE='CUSTOMER')
        self.assertEqual(response_cust.status_code, 302)


        customer = User.objects.get(username='regular_customer')
        self.assertEqual(customer.role, UserRole.CUSTOMER)
        self.assertFalse(customer.is_superuser)
        self.assertFalse(customer.is_staff)

    def test_02_vietqr_url_format(self):
        """Kiểm tra URL VietQR sinh ra đúng định dạng yêu cầu kỹ thuật"""
        order_code = "HD20260922001"
        amount = 150000
        url, desc = self.setting.generate_vietqr_url(amount, order_code)

        self.assertEqual(desc, "TB HD20260922001")
        self.assertIn("img.vietqr.io/image/MB-0912345678-compact2.png", url)
        self.assertIn("amount=150000", url)
        self.assertIn("addInfo=TB+HD20260922001", url)
        self.assertIn("accountName=TIEM+BANH+TEST", url)

    def test_03_custom_cake_min_deposit_30_percent(self):
        """TC04: Kiểm tra ràng buộc đặt cọc tối thiểu 30% cho đơn đặt bánh kem hẹn trước"""
        total_price = Decimal('500000')

        # Cọc 100.000 (20%) -> Không hợp lệ (< 30%)
        deposit_invalid = Decimal('100000')
        valid_inv, _ = CustomCakeOrder.validate_deposit(total_price, deposit_invalid)
        self.assertFalse(valid_inv)

        # Cọc 150.000 (30%) -> Hợp lệ
        deposit_valid_30 = Decimal('150000')
        valid_30, _ = CustomCakeOrder.validate_deposit(total_price, deposit_valid_30)
        self.assertTrue(valid_30)

        # Cọc 250.000 (50%) -> Hợp lệ
        deposit_valid_50 = Decimal('250000')
        valid_50, _ = CustomCakeOrder.validate_deposit(total_price, deposit_valid_50)
        self.assertTrue(valid_50)

    def test_04_kitchen_batch_bom_deduction_with_5_percent_waste(self):
        """TC03: Nghiệm thu mẻ bánh và trừ kho BOM với tỷ lệ hao hụt chuẩn 5%"""
        # Tạo nguyên liệu thô: Bột mì (tồn ban đầu 10 kg)
        flour = Material.objects.create(
            code="NL_BOT_TEST",
            name="Bột Mì Hoa Ngọc Lan Test",
            unit="kg",
            stock_quantity=Decimal('10.000'),
            unit_cost=Decimal('20000')
        )

        # Thiết lập BOM: Cần 0.200 kg bột cho 1 chiếc bánh, hao hụt 5%
        bom = BillOfMaterials.objects.create(
            product=self.product,
            material=flour,
            quantity_needed=Decimal('0.200'),
            waste_percentage=Decimal('5.00')
        )

        # Thợ bánh nướng mẻ 20 chiếc bánh:
        # Lượng bột thực tế tiêu hao: 20 * 0.200 * (1 + 0.05) = 4.200 kg bột mì
        calculated_material = bom.get_total_for_quantity(20)
        self.assertEqual(calculated_material, Decimal('4.200'))

        batch = KitchenBatch.objects.create(
            batch_code="ME2026TEST01",
            product=self.product,
            planned_quantity=20,
            status=BatchStatus.IN_PROGRESS
        )

        # Nghiệm thu hoàn tất mẻ bánh
        success, msg = batch.complete_batch(actual_qty=20)
        self.assertTrue(success)

        # Kiểm tra tồn kho bột mì giảm từ 10.000 xuống 5.800 kg (10 - 4.2)
        flour.refresh_from_db()
        self.assertEqual(flour.stock_quantity, Decimal('5.800'))

        # Kiểm tra tồn kho bánh thành phẩm tăng từ 10 lên 30 (10 + 20)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 30)

    def test_05_loyalty_point_accumulation_10_percent(self):
        """Tích điểm thành viên 10% mỗi hóa đơn: 1 điểm = 1.000 VNĐ"""
        user = User.objects.create_user(username="cust_loyalty@test.local", password="pass", email="c@test.local", role=UserRole.CUSTOMER)
        profile = user.customer_profile
        profile.points_balance = 0
        profile.save()

        # Tạo đơn hoàn tất giá trị 250.000 VNĐ
        order = Order.objects.create(
            order_code="HDTESTLOYALTY",
            order_type=OrderType.POS,
            customer=profile,
            subtotal=Decimal('250000'),
            final_amount=Decimal('250000'),
            payment_method=PaymentMethod.CASH,
            status=OrderStatus.COMPLETED
        )

        # Tích điểm 10% -> 250.000 * 10% = 25.000 VNĐ = 25 điểm
        order.finalize_order_loyalty()

        order.refresh_from_db()
        profile.refresh_from_db()
        self.assertEqual(order.points_earned, 25)
        self.assertEqual(profile.points_balance, 25)

    def test_06_coupon_condition_and_discount_rules(self):
        """Kiểm tra điều kiện áp dụng Coupon: Sinh nhật, VIP và đơn tối thiểu"""
        # Coupon đơn tối thiểu 100k, giảm 20k
        coupon_min = Coupon.objects.create(
            code="GIAM20K",
            title="Giảm 20k đơn từ 100k",
            discount_type=CouponDiscountType.FIXED_AMOUNT,
            discount_value=Decimal('20000'),
            min_order_amount=Decimal('100000'),
            valid_to=timezone.now() + timedelta(days=10)
        )

        # Đơn 80k < 100k -> Thất bại
        valid_80k, msg_80k, _ = coupon_min.can_apply(order_amount=Decimal('80000'))
        self.assertFalse(valid_80k)
        self.assertIn("Đơn hàng phải đạt tối thiểu", msg_80k)

        # Đơn 120k >= 100k -> Thành công, giảm 20k
        valid_120k, _, disc_120k = coupon_min.can_apply(order_amount=Decimal('120000'))
        self.assertTrue(valid_120k)
        self.assertEqual(disc_120k, Decimal('20000'))

        # Coupon VIP Only
        coupon_vip = Coupon.objects.create(
            code="VIPONLY",
            title="Chỉ dành cho VIP",
            discount_type=CouponDiscountType.PERCENT,
            discount_value=Decimal('15.00'),
            condition_type=CouponConditionType.VIP_ONLY,
            valid_to=timezone.now() + timedelta(days=10)
        )

        user_normal = User.objects.create_user(username="normal@test.local", password="pass", role=UserRole.CUSTOMER)
        valid_norm, msg_norm, _ = coupon_vip.can_apply(user_normal.customer_profile, order_amount=Decimal('200000'))
        self.assertFalse(valid_norm)
        self.assertIn("chỉ dành riêng cho Hội viên VIP", msg_norm)

    def test_07_employee_deletion_and_deactivation_rules(self):
        """Quy tắc xóa nhân viên: Chỉ xóa được khi chưa phát sinh đơn hàng/mẻ bánh. Cho phép vô hiệu hóa."""
        cashier = User.objects.create_user(
            username="cashier_fresh",
            password="password123",
            role=UserRole.CASHIER
        )

        # Khi mới tạo, chưa có đơn -> Xóa được
        self.assertEqual(cashier.order_count, 0)
        self.assertTrue(cashier.can_be_deleted())

        # Gán 1 đơn hàng cho thu ngân này
        Order.objects.create(
            order_code="HDCASHIERTEST",
            order_type=OrderType.POS,
            cashier=cashier,
            subtotal=Decimal('50000'),
            final_amount=Decimal('50000'),
            status=OrderStatus.COMPLETED
        )

        # Đã phát sinh đơn -> KHÔNG THỂ XÓA (bảo toàn sổ sách)
        self.assertEqual(cashier.order_count, 1)
        self.assertFalse(cashier.can_be_deleted())

        # Admin chuyển sang vô hiệu hóa
        cashier.is_active = False
        cashier.save()
        cashier.refresh_from_db()
        self.assertFalse(cashier.is_active)

    def test_08_multiport_security_access_rules(self):
        """Kiểm tra phân luồng bảo mật trên 3 cổng Multiport"""
        client = Client()

        # 1. Cổng khách hàng (8008) truy cập POS -> Bị chặn chuyển hướng
        resp_cust_pos = client.get('/pos/', HTTP_X_PORTAL_ROLE='CUSTOMER')
        self.assertEqual(resp_cust_pos.status_code, 302)

        # 2. Cổng nhân viên (8009) tự đăng ký tài khoản -> Bị trả về 403 Forbidden
        resp_staff_reg = client.get('/auth/register/', HTTP_X_PORTAL_ROLE='EMPLOYEE')
        self.assertEqual(resp_staff_reg.status_code, 403)

    def test_09_customer_count_and_profile_isolation(self):
        """Kiểm tra tài khoản Admin/Staff không bị gán CustomerProfile và đếm số lượng khách hàng chính xác"""
        # 1. Tạo tài khoản Admin
        admin = User.objects.create_user(
            username='admin_test_acc',
            password='AdminPassword123!',
            role=UserRole.ADMIN
        )
        # Kiểm tra Admin không có CustomerProfile
        self.assertFalse(CustomerProfile.objects.filter(user=admin).exists())

        # 2. Tạo tài khoản Thu ngân
        cashier = User.objects.create_user(
            username='cashier_test_acc',
            password='CashierPassword123!',
            role=UserRole.CASHIER
        )
        self.assertFalse(CustomerProfile.objects.filter(user=cashier).exists())

        # 3. Đếm số khách hàng trên Dashboard: phải là 0
        client = Client()
        client.force_login(admin)
        resp_dash = client.get('/', HTTP_X_PORTAL_ROLE='ADMIN')
        self.assertEqual(resp_dash.context['total_customers'], 0)

        # 4. Tạo tài khoản Khách hàng
        customer = User.objects.create_user(
            username='real_customer_acc',
            password='CustPassword123!',
            role=UserRole.CUSTOMER
        )
        # Khách hàng có CustomerProfile
        self.assertTrue(CustomerProfile.objects.filter(user=customer).exists())

        # 5. Đếm số khách hàng trên Dashboard sau khi có 1 khách: phải là 1
        resp_dash2 = client.get('/', HTTP_X_PORTAL_ROLE='ADMIN')
        self.assertEqual(resp_dash2.context['total_customers'], 1)

    def test_10_i18n_translation_switching(self):
        """Kiểm tra đa ngôn ngữ Tiếng Việt (VI) và Tiếng Anh (EN) trên toàn hệ thống"""
        from django.utils import translation
        client = Client()

        # 1. Chuyển sang Tiếng Anh qua endpoint /i18n/setlang/
        response_set_en = client.post('/i18n/setlang/', {'language': 'en', 'next': '/online/'})
        self.assertEqual(response_set_en.status_code, 302)
        self.assertEqual(client.cookies.get('django_language').value, 'en')

        # 2. Truy cập thực đơn online bằng Tiếng Anh
        response_en = client.get('/online/', HTTP_X_PORTAL_ROLE='CUSTOMER')
        self.assertEqual(response_en.status_code, 200)
        self.assertContains(response_en, "Pastry Menu")
        self.assertContains(response_en, "Cart")

        # 3. Chuyển lại sang Tiếng Việt
        response_set_vi = client.post('/i18n/setlang/', {'language': 'vi', 'next': '/online/'})
        self.assertEqual(response_set_vi.status_code, 302)
        self.assertEqual(client.cookies.get('django_language').value, 'vi')

        # 4. Truy cập thực đơn online bằng Tiếng Việt
        response_vi = client.get('/online/', HTTP_X_PORTAL_ROLE='CUSTOMER')
        self.assertEqual(response_vi.status_code, 200)
        self.assertContains(response_vi, "Thực Đơn")
        self.assertContains(response_vi, "Giỏ Hàng")

        # 5. Kiểm tra lazy translation trong Model choices
        with translation.override('vi'):
            self.assertEqual(str(UserRole.CUSTOMER.label), "Khách hàng")
        with translation.override('en'):
            self.assertEqual(str(UserRole.CUSTOMER.label), "Customer")

