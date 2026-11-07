from django.core.management.base import BaseCommand, CommandError
from django.core.management import call_command
from django.core.cache import cache
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import connection, transaction
from django.utils import timezone
import getpass
import os
from datetime import timedelta, date
from decimal import Decimal

from apps.authentication.models import User, UserRole, CustomerProfile, CustomerTier, VIPPackage, VIPPackageType, PointTransaction, PointTransactionType
from apps.products.models import Category, Product, ProductStatus, Coupon, CouponDiscountType, CouponConditionType
from apps.kitchen_bom.models import Material, MaterialType, BillOfMaterials, KitchenBatch, BatchStatus
from apps.pos.models import Order, OrderItem, OrderStatus, PaymentMethod, OrderType
from apps.custom_orders.models import CustomCakeOrder, CakeOrderStatus
from apps.dashboard.models import StoreSetting, AuditLog, AuditActionType

class Command(BaseCommand):
    help = 'Reset database linh hoạt theo các chế độ: --dev 0 (trắng), --dev 1 (dữ liệu mẫu), --prod (production an toàn)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--mode',
            type=str,
            choices=['dev0', 'dev1', 'prod'],
            default='dev1',
            help='Chế độ reset: dev0 (reset về 0 trống trơn), dev1 (reset và nạp dữ liệu mẫu), prod (production yêu cầu tài khoản admin thật)'
        )
        parser.add_argument('--admin-username', type=str, help='Tên đăng nhập hoặc Email của Admin Production')
        parser.add_argument('--admin-password', type=str, help='Mật khẩu của Admin Production')
        parser.add_argument('--admin-email', type=str, help='Email liên hệ của Admin Production')
        parser.add_argument('--admin-name', type=str, help='Họ và tên của Admin Production')
        parser.add_argument('--admin-phone', type=str, help='Số điện thoại của Admin Production')
        parser.add_argument('--no-input', action='store_true', help='Không hỏi xác nhận tương tác (dành cho automation script)')

    def handle(self, *args, **options):
        mode = options['mode']
        no_input = options['no_input']

        # ========================================================
        # BƯỚC 0: KIỂM TRA BẢO MẬT & THU THẬP THÔNG TIN CHO PRODUCTION
        # ========================================================
        admin_data = {}
        if mode == 'prod':
            self.stdout.write(self.style.ERROR('\n============================================================'))
            self.stdout.write(self.style.ERROR('⚠️  CẢNH BÁO BẢO MẬT: BẠN ĐANG CHẠY CHẾ ĐỘ PRODUCTION!'))
            self.stdout.write(self.style.ERROR('Toàn bộ cơ sở dữ liệu sẽ bị xóa và khởi tạo lại sạch sẽ.'))
            self.stdout.write(self.style.ERROR('============================================================\n'))

            admin_user = options.get('admin_username')
            admin_pass = options.get('admin_password') or os.environ.get('PROD_ADMIN_PASSWORD')
            admin_email = options.get('admin_email')
            admin_name = options.get('admin_name')
            admin_phone = options.get('admin_phone')

            if not admin_user or not admin_pass:
                if no_input:
                    raise CommandError("Trong chế độ --prod, bắt buộc phải cung cấp username và password (qua --admin-username/--admin-password hoặc biến môi trường PROD_ADMIN_PASSWORD)!")


                # Hỏi thông tin tương tác với bảo mật che mật khẩu
                self.stdout.write("Vui lòng thiết lập tài khoản Quản trị viên Master (Operator) cho Production:")
                admin_user = input("Tên đăng nhập / Email Admin: ").strip()
                while not admin_user:
                    admin_user = input("Tên đăng nhập không được để trống: ").strip()

                admin_email = input(f"Email thông báo [{admin_user}]: ").strip() or admin_user
                admin_name = input("Họ và tên Quản trị viên: ").strip() or "Chủ Tiệm Bánh"
                admin_phone = input("Số điện thoại liên hệ: ").strip() or ""

                while True:
                    admin_pass = getpass.getpass("Mật khẩu Quản trị viên (tối thiểu 8 ký tự): ")
                    admin_pass_confirm = getpass.getpass("Xác nhận lại mật khẩu: ")
                    if admin_pass != admin_pass_confirm:
                        self.stdout.write(self.style.ERROR("❌ Mật khẩu xác nhận không khớp. Vui lòng nhập lại!"))
                        continue
                    try:
                        validate_password(admin_pass)
                        break
                    except ValidationError as err:
                        self.stdout.write(self.style.ERROR(f"❌ Mật khẩu chưa đạt tiêu chuẩn bảo mật: {', '.join(err.messages)}"))

            else:
                # Kiểm tra độ an toàn của mật khẩu được truyền vào
                try:
                    validate_password(admin_pass)
                except ValidationError as err:
                    raise CommandError(f"Mật khẩu admin chưa đạt chuẩn bảo mật Production: {', '.join(err.messages)}")

            admin_data = {
                'username': admin_user,
                'email': admin_email or admin_user,
                'password': admin_pass,
                'first_name': admin_name or "Quản trị viên",
                'phone': admin_phone or ""
            }

        # ========================================================
        # BƯỚC 1: XÓA SẠCH DỮ LIỆU CŨ (CLEAN SLATE TRUNCATE)
        # ========================================================
        self.stdout.write(self.style.WARNING(f'>>> Đang tiến hành làm sạch cơ sở dữ liệu (Chế độ: {mode.upper()})...'))
        with connection.cursor() as cursor:
            cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")
            tables = [
                'pos_orderitem', 'pos_order',
                'custom_orders_customcakeorder',
                'kitchen_bom_kitchenbatch', 'kitchen_bom_billofmaterials', 'kitchen_bom_material',
                'products_coupon', 'products_product', 'products_category',
                'authentication_pointtransaction', 'authentication_customerprofile', 'authentication_vippackage',
                'authentication_user_groups', 'authentication_user_user_permissions', 'authentication_user',
                'dashboard_auditlog', 'dashboard_storesetting',
                'django_session', 'django_admin_log',
            ]
            for tbl in tables:
                try:
                    cursor.execute(f"TRUNCATE TABLE `{tbl}`;")
                except Exception:
                    pass
            cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")

        cache.clear()

        self.stdout.write(self.style.SUCCESS('✓ Đã xóa trắng dữ liệu cũ và bộ nhớ cache thành công.'))

        # ========================================================
        # BƯỚC 2: KIỂM TRA VÀ CHẠY MIGRATIONS
        # ========================================================
        self.stdout.write('>>> Đang kiểm tra schema migrations...')
        call_command('migrate', interactive=False)
        self.stdout.write(self.style.SUCCESS('✓ Migrations hoàn tất.'))

        # ========================================================
        # BƯỚC 3: THIẾT LẬP CẤU HÌNH CƠ BẢN (STORE SETTING & VIETQR)
        # ========================================================
        self.stdout.write('>>> Đang khởi tạo Cài Đặt Hệ Thống & Cấu Hình VietQR...')
        vietqr_bank = os.getenv('VIETQR_BANK_ID', 'MB')
        vietqr_acc = os.getenv('VIETQR_ACCOUNT_NO', '0912345678')
        vietqr_name = os.getenv('VIETQR_ACCOUNT_NAME', 'TIEM BANH ARTISAN')
        vietqr_tmpl = os.getenv('VIETQR_TEMPLATE', 'compact2')
        shipping_fee = Decimal(str(os.getenv('DEFAULT_SHIPPING_FEE', '30000')))

        setting, _ = StoreSetting.objects.get_or_create(
            id=1,
            defaults={
                'store_name': 'Tiệm Bánh Ngọt Artisan Bakery',
                'phone': '0912 345 678',
                'address': '123 Đường Bánh Mì Hoa Cúc, Quận 1, TP. Hồ Chí Minh',
                'vietqr_bank_id': vietqr_bank,
                'vietqr_account_no': vietqr_acc,
                'vietqr_account_name': vietqr_name,
                'vietqr_template': vietqr_tmpl,
                'default_shipping_fee': shipping_fee,
                'vip_monthly_price': Decimal('50000'),
                'vip_yearly_price': Decimal('500000'),
                'vip_discount_percent': Decimal('10.00'),
            }
        )
        self.stdout.write(self.style.SUCCESS(f'✓ Cấu hình VietQR: {setting.vietqr_bank_id} - {setting.vietqr_account_no} ({setting.vietqr_account_name})'))

        # ========================================================
        # BƯỚC 4: TẠO GÓI HỘI VIÊN VIP MẶC ĐỊNH
        # ========================================================
        self.stdout.write('>>> Đang khởi tạo các Gói Hội Viên VIP...')
        VIPPackage.objects.get_or_create(
            package_type=VIPPackageType.MONTHLY,
            defaults={
                'name': 'Hội Viên VIP 1 Tháng',
                'price': Decimal('50000'),
                'discount_percentage': Decimal('10.00'),
                'duration_days': 30,
                'description': 'Giảm 10% cho toàn bộ các đơn hàng bánh, tặng voucher sinh nhật đặc biệt.'
            }
        )
        VIPPackage.objects.get_or_create(
            package_type=VIPPackageType.YEARLY,
            defaults={
                'name': 'Hội Viên VIP 1 Năm (Tiết kiệm 17%)',
                'price': Decimal('500000'),
                'discount_percentage': Decimal('10.00'),
                'duration_days': 365,
                'description': 'Đặc quyền VIP 365 ngày: Giảm 10% trọn đời, miễn phí vận chuyển cho đơn từ 200k.'
            }
        )

        # ========================================================
        # BƯỚC 5: TẠO CÁC DANH MỤC SẢN PHẨM CHUẨN
        # ========================================================
        self.stdout.write('>>> Đang tạo danh mục bánh cơ bản...')
        cat_bread, _ = Category.objects.get_or_create(name='Bánh Mì Nướng', slug='banh-mi-nuong', defaults={'icon': 'bread'})
        cat_cake, _ = Category.objects.get_or_create(name='Bánh Kem & Lạnh', slug='banh-kem-lanh', defaults={'icon': 'cake'})
        cat_custom, _ = Category.objects.get_or_create(name='Bánh Sinh Nhật & Sự Kiện', slug='banh-sinh-nhat', defaults={'icon': 'gift'})
        cat_pastry, _ = Category.objects.get_or_create(name='Tráng Miệng & Bánh Nhỏ', slug='trang-mieng-banh-nho', defaults={'icon': 'sparkles'})

        # ========================================================
        # XỬ LÝ THEO TỪNG CHẾ ĐỘ
        # ========================================================

        # --------------------------------------------------------
        # CHẾ ĐỘ 1: DEV 0 (HOÀN TOÀN TRẮNG - ZERO DUMMY DATA)
        # --------------------------------------------------------
        if mode == 'dev0':
            self.stdout.write(self.style.SUCCESS('\n============================================================'))
            self.stdout.write(self.style.SUCCESS('🎉 RESET DATABASE DEV VỀ 0 (CLEAN SLATE) THÀNH CÔNG!'))
            self.stdout.write(self.style.SUCCESS('============================================================'))
            self.stdout.write('• Trạng thái:        HOÀN TOÀN TRẮNG (0 người dùng, 0 sản phẩm, 0 đơn)')
            self.stdout.write('• Khởi tạo Admin:    Truy cập Cổng Quản Trị (Port 8010) tại đường dẫn:')
            self.stdout.write('                     http://localhost:8010/auth/admin-setup/')
            self.stdout.write('                     để tự tạo tài khoản Quản trị viên đầu tiên (1 lần duy nhất).')
            self.stdout.write('• Danh mục chuẩn:    Đã nạp sẵn 4 danh mục chính (Bánh Mì, Bánh Kem, Sự Kiện, Tráng Miệng).')
            self.stdout.write('• Cổng Khách hàng:   http://localhost:8008')
            self.stdout.write('• Cổng Nhân viên:    http://localhost:8009')
            self.stdout.write('• Cổng Quản trị:     http://localhost:8010')
            self.stdout.write(self.style.SUCCESS('============================================================\n'))
            return

        # --------------------------------------------------------
        # CHẾ ĐỘ 2: PROD (PRODUCTION AN TOÀN - CHỈ TẠO ADMIN THẬT)
        # --------------------------------------------------------
        elif mode == 'prod':
            self.stdout.write('>>> Đang khởi tạo tài khoản Quản trị viên Master (Production)...')
            admin_user = User.objects.create_user(
                username=admin_data['username'],
                email=admin_data['email'],
                password=admin_data['password'],
                first_name=admin_data['first_name'],
                phone=admin_data['phone'],
                role=UserRole.ADMIN
            )
            admin_user.is_staff = True
            admin_user.is_superuser = True
            admin_user.is_active = True
            admin_user.save()

            self.stdout.write(self.style.SUCCESS('\n============================================================'))
            self.stdout.write(self.style.SUCCESS('🛡️  KHỞI TẠO DATABASE PRODUCTION THÀNH CÔNG RỰC RỠ!'))
            self.stdout.write(self.style.SUCCESS('============================================================'))
            self.stdout.write(f'• Quản trị viên Master: {admin_user.username} ({admin_user.email})')
            self.stdout.write(f'• Họ và tên:            {admin_user.get_full_name() or admin_user.first_name}')
            self.stdout.write('• Phân quyền:           ADMIN (Operator / Toàn quyền Superuser)')
            self.stdout.write('• Dữ liệu rác/mẫu:      0 (Không chứa bất kỳ tài khoản hoặc đơn hàng giả lập nào)')
            self.stdout.write('• Bảo mật:              Trang đăng ký Admin tự do (/auth/admin-setup/) đã được KHÓA VĨNH VIỄN.')
            self.stdout.write('• Cổng Khách Hàng (Prod):   http://localhost:9008/')
            self.stdout.write('• Cổng Nhân Viên (Prod):     http://localhost:9009/')
            self.stdout.write('• Cổng Quản Trị (Prod):      http://localhost:9010/')
            self.stdout.write('• Đăng nhập Admin:           http://localhost:9010/auth/login/')
            self.stdout.write('• Quản lý nhân viên:         http://localhost:9010/employees/ (Cấp tài khoản thu ngân/thợ bánh)')
            self.stdout.write(self.style.SUCCESS('============================================================\n'))
            return


        # --------------------------------------------------------
        # CHẾ ĐỘ 3: DEV 1 (GIẢ LẬP ĐẦY ĐỦ TEST DATA SEEDER)
        # --------------------------------------------------------
        self.stdout.write('>>> Đang tạo tài khoản Người Dùng thử nghiệm (Admin, Thu Ngân, Thợ Bánh, Khách Hàng)...')

        # Admin mẫu
        admin_user = User.objects.create_user(
            username='admin@bakery.local',
            email='admin@bakery.local',
            password='admin123',
            first_name='Quản Trị',
            last_name='Viên',
            phone='0900000001',
            role=UserRole.ADMIN
        )
        admin_user.is_staff = True
        admin_user.is_superuser = True
        admin_user.save()

        # Thu ngân mẫu
        cashier_user = User.objects.create_user(
            username='cashier@bakery.local',
            email='cashier@bakery.local',
            password='cashier123',
            first_name='Thu Ngân',
            last_name='Quầy POS',
            phone='0900000002',
            role=UserRole.CASHIER
        )

        # Thợ bánh mẫu
        baker_user = User.objects.create_user(
            username='baker@bakery.local',
            email='baker@bakery.local',
            password='baker123',
            first_name='Thợ Bánh',
            last_name='Bếp Chính',
            phone='0900000003',
            role=UserRole.BAKER
        )

        # Khách hàng thân thiết có điểm
        cust_user_1 = User.objects.create_user(
            username='khachhang1@gmail.com',
            email='khachhang1@gmail.com',
            password='customer123',
            first_name='Nguyễn Văn',
            last_name='An',
            phone='0912345678',
            birthday=date(1995, timezone.now().month, 15),
            role=UserRole.CUSTOMER
        )
        profile_1 = cust_user_1.customer_profile
        profile_1.points_balance = 50
        profile_1.member_card_code = 'CUST-0912345678'
        profile_1.tier = CustomerTier.GOLD
        profile_1.total_spent = Decimal('2500000')
        profile_1.save()

        # Khách hàng VIP
        cust_user_vip = User.objects.create_user(
            username='khachvip@gmail.com',
            email='khachvip@gmail.com',
            password='customer123',
            first_name='Trần Thị',
            last_name='Bích VIP',
            phone='0987654321',
            role=UserRole.CUSTOMER
        )
        profile_vip = cust_user_vip.customer_profile
        profile_vip.points_balance = 120
        profile_vip.member_card_code = 'CUST-0987654321'
        profile_vip.is_vip = True
        profile_vip.vip_expiry = timezone.now() + timedelta(days=365)
        profile_vip.tier = CustomerTier.DIAMOND
        profile_vip.total_spent = Decimal('8000000')
        profile_vip.save()

        # Tạo kho nguyên liệu BOM có SKU và Loại nguyên liệu
        self.stdout.write('>>> Đang tạo kho Nguyên Vật Liệu (BOM & SKU)...')
        mat_flour = Material.objects.create(code='NL_BOT_MI_13', name='Bột Mì Hoa Ngọc Lan Số 13', material_type=MaterialType.FLOUR, unit='kg', stock_quantity=Decimal('100.000'), min_threshold=Decimal('20.000'), unit_cost=Decimal('22000'))
        mat_sugar = Material.objects.create(code='NL_DUONG_CAT', name='Đường Cát Trắng Tinh Luyện', material_type=MaterialType.SWEETENER, unit='kg', stock_quantity=Decimal('60.000'), min_threshold=Decimal('15.000'), unit_cost=Decimal('26000'))
        mat_butter = Material.objects.create(code='NL_BO_PHAP', name='Bơ Lạt Động Vật Elle & Vire Pháp', material_type=MaterialType.DAIRY_FAT, unit='kg', stock_quantity=Decimal('35.000'), min_threshold=Decimal('8.000'), unit_cost=Decimal('180000'))
        mat_egg = Material.objects.create(code='NL_TRUNG_GA', name='Trứng Gà Tươi Tiệt Trùng CP', material_type=MaterialType.EGG_PROTEIN, unit='quả', stock_quantity=Decimal('350.000'), min_threshold=Decimal('50.000'), unit_cost=Decimal('3500'))
        mat_milk = Material.objects.create(code='NL_SUA_TUOI', name='Sữa Tươi Tiệt Trùng Vinamilk 100%', material_type=MaterialType.DAIRY_FAT, unit='lít', stock_quantity=Decimal('60.000'), min_threshold=Decimal('15.000'), unit_cost=Decimal('32000'))
        mat_yeast = Material.objects.create(code='NL_MEN_NO', name='Men Nở Saf-Instant Vàng Nhập Khẩu', material_type=MaterialType.YEAST_ADDITIVE, unit='kg', stock_quantity=Decimal('12.000'), min_threshold=Decimal('2.000'), unit_cost=Decimal('120000'))
        mat_cream = Material.objects.create(code='NL_WHIPPING', name='Whipping Cream Anchor 35.5% New Zealand', material_type=MaterialType.DAIRY_FAT, unit='hộp 1L', stock_quantity=Decimal('25.000'), min_threshold=Decimal('5.000'), unit_cost=Decimal('145000'))
        mat_chocolate = Material.objects.create(code='NL_SOCOLA', name='Sô-cô-la Đen Nguyên Chất 70% Callebaut', material_type=MaterialType.CHOCOLATE_NUTS, unit='kg', stock_quantity=Decimal('20.000'), min_threshold=Decimal('4.000'), unit_cost=Decimal('250000'))
        mat_cheese = Material.objects.create(code='NL_CREAM_CHEESE', name='Cream Cheese Philadelphia Úc', material_type=MaterialType.DAIRY_FAT, unit='kg', stock_quantity=Decimal('20.000'), min_threshold=Decimal('4.000'), unit_cost=Decimal('220000'))
        mat_matcha = Material.objects.create(code='NL_BOT_MATCHA', name='Bột Trà Xanh Uji Matcha Nhật Bản', material_type=MaterialType.YEAST_ADDITIVE, unit='kg', stock_quantity=Decimal('4.000'), min_threshold=Decimal('1.000'), unit_cost=Decimal('850000'))
        mat_strawberry = Material.objects.create(code='NL_DAU_TAY', name='Dâu Tây Đà Lạt Tươi Loại 1', material_type=MaterialType.FRUIT_TOPPING, unit='kg', stock_quantity=Decimal('15.000'), min_threshold=Decimal('3.000'), unit_cost=Decimal('190000'))
        mat_box = Material.objects.create(code='NL_HOP_GIAY', name='Hộp Giấy Kraft Đựng Bánh Cao Cấp', material_type=MaterialType.PACKAGING_OTHER, unit='cái', stock_quantity=Decimal('300.000'), min_threshold=Decimal('50.000'), unit_cost=Decimal('5000'))

        # Tạo danh sách bánh thành phẩm với ảnh chất lượng cao
        self.stdout.write('>>> Đang tạo danh sách Bánh Thành Phẩm sinh động (Vivid Realistic Images)...')
        p_croissant = Product.objects.create(
            sku_code='BM01',
            name='Bánh Sừng Bò Bơ Pháp (Croissant)',
            category=cat_bread,
            price=Decimal('28000'),
            stock_quantity=24,
            shelf_life_hours=18,
            standard_batch_yield=30,
            image='products/croissant.jpg',
            image_url='/media/products/croissant.jpg'
        )
        p_pain_choco = Product.objects.create(
            sku_code='BM02',
            name='Bánh Mì Sô-cô-la (Pain au Chocolat)',
            category=cat_bread,
            price=Decimal('32000'),
            stock_quantity=18,
            shelf_life_hours=18,
            standard_batch_yield=20,
            image='products/pain_au_chocolat.jpg',
            image_url='/media/products/pain_au_chocolat.jpg'
        )
        p_baguette = Product.objects.create(
            sku_code='BM03',
            name='Bánh Mì Baguette Truyền Thống',
            category=cat_bread,
            price=Decimal('18000'),
            stock_quantity=15,
            shelf_life_hours=12,
            is_fast_bread=True,
            standard_batch_yield=30,
            image='products/baguette.jpg',
            image_url='/media/products/baguette.jpg'
        )
        p_brioche = Product.objects.create(
            sku_code='BM04',
            name='Bánh Mì Hoa Cúc Pháp (Brioche Tressée)',
            category=cat_bread,
            price=Decimal('45000'),
            stock_quantity=16,
            shelf_life_hours=24,
            standard_batch_yield=20,
            image='products/brioche.jpg',
            image_url='/media/products/brioche.jpg'
        )
        p_tiramisu = Product.objects.create(
            sku_code='BK01',
            name='Bánh Tiramisu Cổ Điển Ý',
            category=cat_cake,
            price=Decimal('48000'),
            stock_quantity=12,
            shelf_life_hours=24,
            standard_batch_yield=15,
            image='products/tiramisu.jpg',
            image_url='/media/products/tiramisu.jpg'
        )
        p_red_velvet = Product.objects.create(
            sku_code='BK02',
            name='Bánh Kem Nhung Đỏ (Red Velvet)',
            category=cat_cake,
            price=Decimal('52000'),
            stock_quantity=8,
            shelf_life_hours=24,
            standard_batch_yield=12,
            image='products/red_velvet.jpg',
            image_url='/media/products/red_velvet.jpg'
        )
        p_matcha = Product.objects.create(
            sku_code='BK03',
            name='Bánh Cheesecake Trà Xanh Nhật Bản',
            category=cat_cake,
            price=Decimal('55000'),
            stock_quantity=10,
            shelf_life_hours=24,
            standard_batch_yield=12,
            image='products/matcha_cake.jpg',
            image_url='/media/products/matcha_cake.jpg'
        )
        p_cheesecake = Product.objects.create(
            sku_code='BK04',
            name='Bánh Phô Mai Nướng (Basque Cheesecake)',
            category=cat_cake,
            price=Decimal('58000'),
            stock_quantity=12,
            shelf_life_hours=24,
            standard_batch_yield=10,
            image='products/cheesecake.jpg',
            image_url='/media/products/cheesecake.jpg'
        )
        p_flan_caramel = Product.objects.create(
            sku_code='BK05',
            name='Bánh Flan Caramel Trứng Nướng',
            category=cat_cake,
            price=Decimal('22000'),
            stock_quantity=20,
            shelf_life_hours=24,
            standard_batch_yield=40,
            image='products/flan_caramel.jpg',
            image_url='/media/products/flan_caramel.jpg'
        )
        p_birthday = Product.objects.create(
            sku_code='SN01',
            name='Bánh Kem Dâu Tây Tươi (Strawberry Shortcake)',
            category=cat_custom,
            price=Decimal('280000'),
            stock_quantity=4,
            shelf_life_hours=48,
            is_custom_cake=True,
            standard_batch_yield=5,
            image='products/strawberry_cake.jpg',
            image_url='/media/products/strawberry_cake.jpg'
        )
        p_black_forest = Product.objects.create(
            sku_code='SN02',
            name='Bánh Kem Rừng Đen (Black Forest)',
            category=cat_custom,
            price=Decimal('295000'),
            stock_quantity=3,
            shelf_life_hours=48,
            is_custom_cake=True,
            standard_batch_yield=5,
            image='products/black_forest.jpg',
            image_url='/media/products/black_forest.jpg'
        )
        p_macaron = Product.objects.create(
            sku_code='TM01',
            name='Bánh Macaron Đủ Vị (Hộp 6 cái)',
            category=cat_pastry,
            price=Decimal('85000'),
            stock_quantity=20,
            shelf_life_hours=72,
            standard_batch_yield=20,
            image='products/macaron.jpg',
            image_url='/media/products/macaron.jpg'
        )
        p_tart = Product.objects.create(
            sku_code='TM02',
            name='Bánh Tart Chanh Vàng Meringue',
            category=cat_pastry,
            price=Decimal('35000'),
            stock_quantity=14,
            shelf_life_hours=24,
            standard_batch_yield=18,
            image='products/lemon_tart.jpg',
            image_url='/media/products/lemon_tart.jpg'
        )
        p_egg_tart = Product.objects.create(
            sku_code='TM03',
            name='Bánh Tart Trứng Nướng Bồ Đào Nha',
            category=cat_pastry,
            price=Decimal('20000'),
            stock_quantity=25,
            shelf_life_hours=18,
            standard_batch_yield=30,
            image='products/egg_tart.jpg',
            image_url='/media/products/egg_tart.jpg'
        )
        p_choux = Product.objects.create(
            sku_code='TM04',
            name='Bánh Su Kem Giòn Choux Craquelin',
            category=cat_pastry,
            price=Decimal('22000'),
            stock_quantity=20,
            shelf_life_hours=24,
            standard_batch_yield=30,
            image='products/choux.jpg',
            image_url='/media/products/choux.jpg'
        )

        # Định mức BOM chuẩn trung bình cho từng mẻ bánh
        self.stdout.write('>>> Đang thiết lập công thức định mức nguyên vật liệu (BOM)...')
        BillOfMaterials.objects.create(product=p_croissant, material=mat_flour, quantity_needed=Decimal('0.060'), waste_percentage=Decimal('5.00'))
        BillOfMaterials.objects.create(product=p_croissant, material=mat_butter, quantity_needed=Decimal('0.035'), waste_percentage=Decimal('5.00'))
        BillOfMaterials.objects.create(product=p_croissant, material=mat_milk, quantity_needed=Decimal('0.020'), waste_percentage=Decimal('5.00'))

        BillOfMaterials.objects.create(product=p_baguette, material=mat_flour, quantity_needed=Decimal('0.070'), waste_percentage=Decimal('3.00'))
        BillOfMaterials.objects.create(product=p_baguette, material=mat_yeast, quantity_needed=Decimal('0.002'), waste_percentage=Decimal('2.00'))
        BillOfMaterials.objects.create(product=p_baguette, material=mat_sugar, quantity_needed=Decimal('0.005'), waste_percentage=Decimal('2.00'))

        BillOfMaterials.objects.create(product=p_pain_choco, material=mat_flour, quantity_needed=Decimal('0.060'), waste_percentage=Decimal('5.00'))
        BillOfMaterials.objects.create(product=p_pain_choco, material=mat_butter, quantity_needed=Decimal('0.035'), waste_percentage=Decimal('5.00'))
        BillOfMaterials.objects.create(product=p_pain_choco, material=mat_chocolate, quantity_needed=Decimal('0.025'), waste_percentage=Decimal('3.00'))

        BillOfMaterials.objects.create(product=p_brioche, material=mat_flour, quantity_needed=Decimal('0.150'), waste_percentage=Decimal('5.00'))
        BillOfMaterials.objects.create(product=p_brioche, material=mat_butter, quantity_needed=Decimal('0.080'), waste_percentage=Decimal('5.00'))
        BillOfMaterials.objects.create(product=p_brioche, material=mat_egg, quantity_needed=Decimal('2.000'), waste_percentage=Decimal('5.00'))

        BillOfMaterials.objects.create(product=p_flan_caramel, material=mat_sugar, quantity_needed=Decimal('0.030'), waste_percentage=Decimal('2.00'))
        BillOfMaterials.objects.create(product=p_flan_caramel, material=mat_egg, quantity_needed=Decimal('1.000'), waste_percentage=Decimal('2.00'))
        BillOfMaterials.objects.create(product=p_flan_caramel, material=mat_milk, quantity_needed=Decimal('0.050'), waste_percentage=Decimal('2.00'))

        BillOfMaterials.objects.create(product=p_egg_tart, material=mat_flour, quantity_needed=Decimal('0.030'), waste_percentage=Decimal('4.00'))
        BillOfMaterials.objects.create(product=p_egg_tart, material=mat_butter, quantity_needed=Decimal('0.020'), waste_percentage=Decimal('4.00'))
        BillOfMaterials.objects.create(product=p_egg_tart, material=mat_egg, quantity_needed=Decimal('1.000'), waste_percentage=Decimal('3.00'))
        BillOfMaterials.objects.create(product=p_egg_tart, material=mat_milk, quantity_needed=Decimal('0.030'), waste_percentage=Decimal('3.00'))

        BillOfMaterials.objects.create(product=p_tiramisu, material=mat_cream, quantity_needed=Decimal('0.050'), waste_percentage=Decimal('3.00'))
        BillOfMaterials.objects.create(product=p_tiramisu, material=mat_cheese, quantity_needed=Decimal('0.040'), waste_percentage=Decimal('3.00'))
        BillOfMaterials.objects.create(product=p_tiramisu, material=mat_sugar, quantity_needed=Decimal('0.025'), waste_percentage=Decimal('2.00'))

        # Lệnh nướng bếp giả lập (Kitchen Batches) - Thể hiện đầy đủ 4 Mức Tỉ Lệ Hao Hụt & Giờ Vàng
        self.stdout.write('>>> Đang tạo các mẻ nướng bếp phủ đủ 4 Mức Hao Hụt (Tốt, Bình Thường, Cảnh Báo, Báo Động Đỏ)...')
        now_dt = timezone.now()

        # Mức 1: TỐT (0 - 5%): Kế hoạch 30, Thực tế 29 -> Hao hụt: 3.3%
        KitchenBatch.objects.create(
            batch_code='ME-2026-0901-01',
            product=p_croissant,
            planned_quantity=30,
            actual_quantity=29,
            waste_rate=Decimal('3.33'),
            materials_deducted=True,
            baker=baker_user,
            status=BatchStatus.COMPLETED,
            completed_at=now_dt - timedelta(hours=2)
        )

        # Mức 2: BÌNH THƯỜNG (5 - 10%): Kế hoạch 30, Thực tế 28 -> Hao hụt: 6.7%
        KitchenBatch.objects.create(
            batch_code='ME-2026-0901-02',
            product=p_brioche,
            planned_quantity=30,
            actual_quantity=28,
            waste_rate=Decimal('6.67'),
            materials_deducted=True,
            baker=baker_user,
            status=BatchStatus.COMPLETED,
            completed_at=now_dt - timedelta(hours=5)
        )

        # Mức 3: CẢNH BÁO (10 - 15%): Kế hoạch 30, Thực tế 26 -> Hao hụt: 13.3%
        KitchenBatch.objects.create(
            batch_code='ME-2026-0901-03',
            product=p_egg_tart,
            planned_quantity=30,
            actual_quantity=26,
            waste_rate=Decimal('13.33'),
            materials_deducted=True,
            baker=baker_user,
            status=BatchStatus.COMPLETED,
            completed_at=now_dt - timedelta(hours=8)
        )

        # Mức 4: BÁO ĐỘNG ĐỎ (> 15%): Kế hoạch 30, Thực tế 24 -> Hao hụt: 20.0% (Kích hoạt Red Alert)
        KitchenBatch.objects.create(
            batch_code='ME-2026-0901-04',
            product=p_flan_caramel,
            planned_quantity=30,
            actual_quantity=24,
            waste_rate=Decimal('20.00'),
            materials_deducted=True,
            baker=baker_user,
            status=BatchStatus.COMPLETED,
            completed_at=now_dt - timedelta(hours=11)
        )

        # Mẻ Pain au Chocolat nướng cách đây 15 tiếng (HSD 18h -> còn 3h <= 25% -> Kích hoạt Giờ Vàng -40%)
        KitchenBatch.objects.create(
            batch_code='ME-2026-0901-05',
            product=p_pain_choco,
            planned_quantity=20,
            actual_quantity=20,
            waste_rate=Decimal('0.00'),
            materials_deducted=True,
            baker=baker_user,
            status=BatchStatus.COMPLETED,
            completed_at=now_dt - timedelta(hours=15)
        )

        # Mẻ Baguette đang nướng trong lò (KDS bếp)
        KitchenBatch.objects.create(
            batch_code='ME-2026-0901-06',
            product=p_baguette,
            planned_quantity=30,
            materials_deducted=True,
            baker=baker_user,
            status=BatchStatus.IN_PROGRESS
        )

        # Đơn bánh kem đặt trước theo hẹn (Custom Orders)
        self.stdout.write('>>> Đang tạo danh sách Đơn đặt bánh sinh nhật theo hẹn (Kanban)...')
        CustomCakeOrder.objects.create(
            order_code='ORD-CAKE-001',
            customer_name='Chị Ngọc Thảo',
            customer_phone='0918111222',
            cake_base='Red Velvet',
            cream_flavor='Cream Cheese & Dâu Tây',
            size='20cm',
            custom_message='Chúc Mừng Sinh Nhật Bé Sam 5 Tuổi!',
            notes='Trang trí nhiều dâu tây tươi xung quanh viền bánh, ít ngọt',
            sample_image='custom_cakes/sample_strawberry.jpg',
            sample_image_url='/media/custom_cakes/sample_strawberry.jpg',
            pickup_datetime=now_dt + timedelta(days=1, hours=4),
            total_price=Decimal('450000'),
            deposit_amount=Decimal('200000'),
            status=CakeOrderStatus.RECEIVED
        )
        CustomCakeOrder.objects.create(
            order_code='ORD-CAKE-002',
            customer_name='Anh Minh Quân',
            customer_phone='0988777666',
            cake_base='Socola Đen Thụy Sĩ',
            cream_flavor='Ganache & Cherry Rừng',
            size='25cm',
            custom_message='Kỷ Niệm 10 Năm Ngày Cưới Anh & Em',
            notes='Phủ socola gương bóng mờ, kèm nến số 10',
            sample_image='custom_cakes/sample_blackforest.jpg',
            sample_image_url='/media/custom_cakes/sample_blackforest.jpg',
            pickup_datetime=now_dt + timedelta(hours=6),
            total_price=Decimal('550000'),
            deposit_amount=Decimal('300000'),
            status=CakeOrderStatus.BAKING
        )
        CustomCakeOrder.objects.create(
            order_code='ORD-CAKE-003',
            customer_name='Bạn Thùy Dương',
            customer_phone='0909555444',
            cake_base='Trà Xanh Matcha Uji',
            cream_flavor='Kem Phô Mai Mascarpone',
            size='16cm',
            custom_message='Happy Birthday Princess Dương!',
            notes='Vẽ hoa trà xanh tối giản phong cách Hàn Quốc',
            sample_image='custom_cakes/sample_matcha.jpg',
            sample_image_url='/media/custom_cakes/sample_matcha.jpg',
            pickup_datetime=now_dt + timedelta(hours=2),
            total_price=Decimal('380000'),
            deposit_amount=Decimal('380000'),
            status=CakeOrderStatus.READY
        )

        # Coupons
        self.stdout.write('>>> Đang tạo hệ thống Mã Khuyến Mãi (Coupons)...')
        Coupon.objects.create(code='WELCOME10', title='Chào mừng thành viên mới', discount_type=CouponDiscountType.PERCENT, discount_value=Decimal('10.00'), max_discount_amount=Decimal('50000'), valid_from=timezone.now() - timedelta(days=1), valid_to=timezone.now() + timedelta(days=90))
        Coupon.objects.create(code='SINHNHATBAN', title='Ưu đãi tháng sinh nhật', discount_type=CouponDiscountType.PERCENT, discount_value=Decimal('20.00'), condition_type=CouponConditionType.BIRTHDAY, valid_from=timezone.now() - timedelta(days=10), valid_to=timezone.now() + timedelta(days=365))
        Coupon.objects.create(code='VIPONLY', title='Đặc quyền Hội viên VIP', discount_type=CouponDiscountType.PERCENT, discount_value=Decimal('15.00'), condition_type=CouponConditionType.VIP_ONLY, valid_from=timezone.now() - timedelta(days=5), valid_to=timezone.now() + timedelta(days=365))
        Coupon.objects.create(code='GIAM30K', title='Giảm 30k cho đơn từ 200k', discount_type=CouponDiscountType.FIXED_AMOUNT, discount_value=Decimal('30000'), min_order_amount=Decimal('200000'), valid_from=timezone.now() - timedelta(days=1), valid_to=timezone.now() + timedelta(days=60))

        # Đơn hàng mẫu POS
        self.stdout.write('>>> Đang tạo hóa đơn bán lẻ POS mẫu...')
        pos_order = Order.objects.create(
            order_code='POS-2026-0901-001',
            order_type=OrderType.POS,
            cashier=cashier_user,
            customer=profile_1,
            subtotal=Decimal('101000'),
            discount_amount=Decimal('10000'),
            final_amount=Decimal('91000'),
            payment_method=PaymentMethod.TRANSFER,
            status=OrderStatus.COMPLETED
        )
        OrderItem.objects.create(order=pos_order, product=p_croissant, quantity=2, unit_price=Decimal('28000'), subtotal=Decimal('56000'))
        OrderItem.objects.create(order=pos_order, product=p_brioche, quantity=1, unit_price=Decimal('45000'), subtotal=Decimal('45000'))

        # Nhật Ký Kiểm Toán Hệ Thống Mẫu (Audit Trail)
        self.stdout.write('>>> Đang khởi tạo dữ liệu Nhật Ký Kiểm Toán (Audit Trail)...')
        AuditLog.objects.create(
            user=admin_user,
            action_type=AuditActionType.MATERIAL_STOCK_IN,
            target_code='NL_BOT_MI_13',
            description='Quét mã QR nhập kho 50.0 kg Bột Mì Hoa Ngọc Lan Số 13 từ Nhà Cung Cấp Hưng Phát'
        )
        AuditLog.objects.create(
            user=admin_user,
            action_type=AuditActionType.MATERIAL_STOCK_IN,
            target_code='NL_BO_PHAP',
            description='Quét mã QR nhập kho 15.0 kg Bơ Lạt Động Vật Elle & Vire Pháp'
        )
        AuditLog.objects.create(
            user=baker_user,
            action_type=AuditActionType.BATCH_CREATE,
            target_code='ME-2026-0901-01',
            description='Khởi tạo mẻ bánh Croissant Bơ Pháp ME-2026-0901-01 (Kế hoạch: 30 cái) và tự động trừ kho nguyên liệu'
        )
        AuditLog.objects.create(
            user=baker_user,
            action_type=AuditActionType.BATCH_COMPLETE,
            target_code='ME-2026-0901-01',
            description='Nghiệm thu mẻ bánh ME-2026-0901-01: Thực tế đạt 29/30 cái. Tỉ lệ hao hụt: 3.3% (Mức: Tốt)'
        )
        AuditLog.objects.create(
            user=baker_user,
            action_type=AuditActionType.BATCH_RED_ALERT,
            target_code='ME-2026-0901-04',
            description='🚨 BÁO ĐỘNG ĐỎ HAO HỤT: Mẻ bánh ME-2026-0901-04 thực tế chỉ đạt 24/30 cái. Tỉ lệ hao hụt lên đến 20.0% (vượt ngưỡng cảnh báo an toàn 15.0%)'
        )
        AuditLog.objects.create(
            user=baker_user,
            action_type=AuditActionType.LABEL_PRINT,
            target_code='ME-2026-0901-01',
            description='In 29 tem nhãn nhiệt Niimbot 50x30mm kèm mã vạch định danh mẻ bánh BM01-ME-2026-0901-01'
        )
        AuditLog.objects.create(
            user=cashier_user,
            action_type=AuditActionType.RECEIPT_PRINT,
            target_code='POS-2026-0901-001',
            description='In hóa đơn bán lẻ POS-2026-0901-001, khách hàng Nguyễn Văn An, tổng thanh toán 91.000đ'
        )
        AuditLog.objects.create(
            user=cashier_user,
            action_type=AuditActionType.POINTS_REDEEM,
            target_code='POS-2026-0901-001',
            description='Khách hàng Nguyễn Văn An xuất trình Thẻ Hội Viên CUST-0912345678 dùng 10 điểm (giảm 10.000đ)'
        )

        self.stdout.write(self.style.SUCCESS('\n============================================================'))
        self.stdout.write(self.style.SUCCESS('🎉 RESET DATABASE DEV 1 (FULL SIMULATED DATA) THÀNH CÔNG!'))
        self.stdout.write(self.style.SUCCESS('============================================================'))
        self.stdout.write('• Quản trị viên (Admin): admin@bakery.local / admin123')
        self.stdout.write('• Thu ngân (Cashier):    cashier@bakery.local / cashier123')
        self.stdout.write('• Thợ bánh (Baker):      baker@bakery.local / baker123')
        self.stdout.write('• Khách hàng có điểm:    khachhang1@gmail.com / customer123 (50.000 điểm)')
        self.stdout.write('• Khách hàng VIP:        khachvip@gmail.com / customer123 (Gói VIP)')
        self.stdout.write('• Cổng Khách hàng:       http://localhost:8008')
        self.stdout.write('• Cổng Nhân viên:        http://localhost:8009')
        self.stdout.write('• Cổng Quản trị:         http://localhost:8010')
        self.stdout.write(self.style.SUCCESS('============================================================\n'))
