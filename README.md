# 🥐 Hệ Thống Quản Lý Tiệm Bánh (Artisan Bakery Management System)

[![Python 3.11](https://img.shields.io/badge/Python-3.11-3776AB?style=flat&logo=python&logoColor=white)](https://python.org)
[![Django 5.1](https://img.shields.io/badge/Django-5.1-092E20?style=flat&logo=django&logoColor=white)](https://djangoproject.com)
[![MySQL 8.0](https://img.shields.io/badge/MySQL-8.0-4479A1?style=flat&logo=mysql&logoColor=white)](https://mysql.com)
[![Nginx Alpine](https://img.shields.io/badge/Nginx-Gateway-009639?style=flat&logo=nginx&logoColor=white)](https://nginx.org)
[![Docker Compose](https://img.shields.io/badge/Docker-Compose-2496ED?style=flat&logo=docker&logoColor=white)](https://docker.com)
[![i18n](https://img.shields.io/badge/i18n-VI%20%7C%20EN-blue?style=flat)](locale/)
[![Security Hardened](https://img.shields.io/badge/Security-Hardened-success?style=flat&logo=shield)](config/settings.py)

Hệ thống Quản lý Tiệm Bánh (Bakery Management System) xây dựng trên nền tảng **Django 5.1**, **MySQL 8.0**, **Nginx Multiport Gateway**, **Tailwind CSS** và **Docker Compose**. Hệ thống hỗ trợ đa ngôn ngữ (**Tiếng Việt / English**), giao diện POS quầy thu ngân, màn hình bếp KDS tính hao hụt định mức nguyên liệu (BOM), cổng đặt bánh online và quản trị nhân sự phân quyền theo cổng truy cập.

---

## 📑 Mục Lục
1. [Kiến Trúc Đa Cổng (Multiport Gateway)](#1-kiến-trúc-đa-cổng-multiport-gateway)
2. [Khởi Động Nhanh (Quick Start)](#2-khởi-động-nhanh-quick-start)
3. [Quản Trị Cơ Sở Dữ Liệu (`reset_db.sh`)](#3-quản-trị-cơ-sở-dữ-liệu-reset_dbsh)
4. [Danh Sách Tài Khoản Mẫu & Cổng Truy Cập](#4-danh-sách-tài-khoản-mẫu--cổng-truy-cập)
5. [Các Phân Hệ Nghiệp Vụ Cốt Lõi](#5-các-phân-hệ-nghiệp-vụ-cốt-lõi)
6. [Cơ Chế Bảo Mật Toàn Diện (Security Hardening)](#6-cơ-chế-bảo-mật-toàn-diện-security-hardening)
7. [Hỗ Trợ Đa Ngôn Ngữ (i18n: VI / EN)](#7-hỗ-trợ-đa-ngôn-ngữ-i18n-vi--en)
8. [Cấu Trúc Thư Mục & Hướng Dẫn Nạp Ảnh (Asset Sourcing)](#8-cấu-trúc-thư-mục--hướng-dẫn-nạp-ảnh-asset-sourcing)
9. [Lệnh Vận Hành Thường Dùng & Kiểm Thử Tự Động](#9-lệnh-vận-hành-thường-dùng--kiểm-thử-tự-động)

---

## 🌐 1. Kiến Trúc Đa Cổng (Multiport Gateway: 3 Cổng Dev + 3 Cổng Prod)

Hệ thống tích hợp cổng phân luồng **Nginx Gateway**, chia tách ứng dụng thành **tổng cộng 6 cổng độc lập** (3 cổng cho môi trường Development và 3 cổng riêng biệt cho môi trường Production). Cả hai môi trường có thể chạy song song trên cùng một máy chủ mà không hề xảy ra xung đột cổng hay ghi đè dữ liệu cơ sở dữ liệu:

```
[ MÔI TRƯỜNG DEV: 3 PORTS ]                [ MÔI TRƯỜNG PRODUCTION: 3 PORTS ]
┌───────────────────────────────┐          ┌───────────────────────────────────────────────┐
│ • Port 8008: Khách Hàng (Dev) │          │ • Port 9008: Khách Hàng Prod (shop.domain.com)│
│ • Port 8009: Nhân Viên (Dev)  │          │ • Port 9009: Nhân Viên Prod  (staff.domain.com)│
│ • Port 8010: Quản Trị (Dev)   │          │ • Port 9010: Quản Trị Prod   (admin.domain.com)│
│ • Port 3307: MySQL 8.0 (Dev)  │          │ • Port 3308: MySQL 8.0 (Prod)                │
└───────────────────────────────┘          └───────────────────────────────────────────────┘
```

### Bảng Ma Trận 6 Cổng & Phân Quyền Truy Cập:

| Môi trường | Cổng (Port) | Đối tượng phục vụ | Subdomain Cloudflare | Quyền hạn & Chức năng |
| :--- | :--- | :--- | :--- | :--- |
| **DEV** | **8008** | **Khách Hàng Dev** | *Nội bộ Dev* | Mua bánh online, giỏ hàng, tra cứu hóa đơn, đăng ký tự do (`CUSTOMER`). |
| **DEV** | **8009** | **Nhân Viên Dev** | *Nội bộ Dev* | Màn hình POS cảm ứng, Bếp KDS, Kho hàng. Khóa tự đăng ký (HTTP 403). |
| **DEV** | **8010** | **Quản Trị Dev** | *Nội bộ Dev* | Bảng điều khiển quản trị, Quản lý nhân sự, Onboarding Master Admin (`/auth/admin-setup/`). |
| **PROD** | **9008** | **Khách Hàng Prod** | `shop.tiembanh.com` | Cổng thương mại điện tử chính thức cho khách hàng đặt bánh online, nạp điểm ví VietQR. |
| **PROD** | **9009** | **Nhân Viên Prod** | `staff.tiembanh.com` | Cổng vận hành nội bộ tại quầy thu ngân và khu vực bếp làm bánh. Khóa tự đăng ký. |
| **PROD** | **9010** | **Quản Trị Prod** | `admin.tiembanh.com` | **Cổng Quản trị Tách Biệt cho Admin:** Cấu hình VietQR, doanh thu, quản lý nhân viên. |

> [!IMPORTANT]
> **Quy Tắc Khởi Tạo Admin Ban Đầu (1-Time Setup):**
> - Trang khởi tạo Admin ban đầu (`/auth/admin-setup/`) chỉ mở duy nhất trên **Port 8010 (Dev)** hoặc **Port 9010 (Prod)** và **DUY NHẤT 1 LẦN** khi hệ thống chưa có Admin nào.
> - Sau khi Master Admin được tạo (hoặc sau khi chạy `./reset_db.sh --prod`), trang setup tự động **khóa vĩnh viễn**. Mọi nhân viên và admin tiếp theo phải do Admin đăng nhập tạo tại phân hệ Quản lý Nhân sự (`/employees/`).


---

## 🚀 2. Khởi Động Nhanh (Quick Start)

Yêu cầu máy chủ/máy phát triển đã cài đặt **Docker** và **Docker Compose**.

```bash
# 1. Di chuyển vào thư mục dự án
cd bakery

# 2. Khởi động toàn bộ container môi trường Dev (Nginx, Django, MySQL 8.0)
docker compose -f docker-compose.dev.yml up -d

# 3. Khởi tạo cơ sở dữ liệu và nạp dữ liệu mẫu giả lập
./reset_db.sh --dev 1

# 4. Chạy 8/8 bài kiểm thử tự động
docker compose -f docker-compose.dev.yml exec web python manage.py test apps.dashboard.tests
```

Sau khi khởi chạy thành công:
- **Cổng Khách Hàng:** [http://localhost:8008](http://localhost:8008)
- **Cổng Nhân Viên:** [http://localhost:8009](http://localhost:8009)
- **Cổng Quản Trị:** [http://localhost:8010](http://localhost:8010)

---

## 🗄️ 3. Quản Trị Cơ Sở Dữ Liệu (`reset_db.sh`)

Kịch bản [reset_db.sh](file:///home/haku/bakery/reset_db.sh) được xây dựng an toàn, hỗ trợ 3 chế độ tương ứng với từng giai đoạn:

```bash
./reset_db.sh [TUỲ CHỌN]
```

### 3.1. Chế độ Phát triển Trắng (`--dev 0`)
- **Lệnh:** `./reset_db.sh --dev 0`
- **Mục đích:** Xóa toàn bộ dữ liệu, trả về trạng thái trắng tinh (0 user, 0 sản phẩm, 0 đơn hàng).
- **Quy trình tiếp theo:** Truy cập [http://localhost:8010/auth/admin-setup/](http://localhost:8010/auth/admin-setup/) để tự thiết lập tài khoản Master Admin đầu tiên (chỉ mở 1 lần).

### 3.2. Chế độ Phát triển Giả Lập (`--dev 1`) - *Mặc định*
- **Lệnh:** `./reset_db.sh --dev 1` hoặc chỉ gõ `./reset_db.sh`
- **Mục đích:** Khởi tạo môi trường kiểm thử hoàn chỉnh với đầy đủ các vai trò: Admin, Thu ngân, Thợ bánh, Khách hàng, 12 món bánh thành phẩm, 11 loại nguyên liệu BOM, công thức định mức, và 4 mã giảm giá (coupons).

### 3.3. Chế độ Môi Trường Sản Xuất (`--prod`)
- **Lệnh:** `./reset_db.sh --prod`
- **Cơ chế an toàn tối cao:**
  1. Yêu cầu người vận hành xác nhận bằng cách gõ chính xác cụm từ: `CONFIRM-RESET-PROD`.
  2. Yêu cầu nhập tên đăng nhập và mật khẩu Admin thật (màn hình ẩn ký tự nhập `read -sp`).
  3. Kiểm tra độ phức tạp của mật khẩu qua chuẩn Django Validator (tối thiểu 8 ký tự, không dùng mật khẩu phổ biến, có độ phức tạp cao).
  4. Mật khẩu được truyền vào container qua biến môi trường an toàn `PROD_ADMIN_PASSWORD` (không lộ trong lệnh `ps aux` trên server).
  5. Biến mật khẩu được xóa khỏi bộ nhớ shell (`unset PROD_PASS`) ngay khi hoàn tất.
  6. **Tuyệt đối 0 dữ liệu rác/mẫu:** Không tạo bất kỳ đơn hàng hay tài khoản giả lập nào; tự động khóa trang setup 1-time.
- **Các Cổng Truy Cập Production:**
  - **Cổng Khách Hàng Prod:** [http://localhost:9008](http://localhost:9008) *(hoặc `https://shop.domain.com`)*
  - **Cổng Nhân Viên Prod:** [http://localhost:9009](http://localhost:9009) *(hoặc `https://staff.domain.com`)*
  - **Cổng Quản Trị Prod:** [http://localhost:9010](http://localhost:9010) *(hoặc `https://admin.domain.com`)*


---

## 👥 4. Danh Sách Tài Khoản Mẫu & Cổng Truy Cập

*(Áp dụng khi khởi tạo bằng `./reset_db.sh --dev 1`)*

| Phân quyền | Cổng truy cập phù hợp | Tài khoản (Email / Username) | Mật khẩu | Chức năng chính |
| :--- | :--- | :--- | :--- | :--- |
| **Quản trị viên (Admin)** | **Port 8010** | `admin@bakery.local` | `admin123` | Quản lý hệ thống, cấu hình VietQR, duyệt nhân sự, báo cáo doanh thu & kho |
| **Thu ngân (Cashier)** | **Port 8009** | `cashier@bakery.local` | `cashier123` | Màn hình POS cảm ứng, quét mã SKU, thanh toán gộp 3 nguồn, in hóa đơn nhiệt 80mm |
| **Thợ làm bánh (Baker)** | **Port 8009** | `baker@bakery.local` | `baker123` | Màn hình bếp KDS, tạo & nghiệm thu mẻ bánh, tự động trừ kho nguyên liệu (+5% hao hụt) |
| **Khách hàng thân thiết** | **Port 8008** | `khachhang1@gmail.com` *(SĐT: 0912345678)* | `customer123` | Mua bánh online, có sẵn **50.000 điểm** ví để khấu trừ tiền hàng |
| **Khách hàng VIP** | **Port 8008** | `khachvip@gmail.com` *(SĐT: 0987654321)* | `customer123` | Hội viên VIP 1 năm, hưởng chiết khấu tự động và mã giảm giá VIP |

---

## 🥐 5. Các Phân Hệ Nghiệp Vụ Cốt Lõi

### 5.1. Màn Hình POS Bán Lẻ Cảm Ứng (Point of Sale)
- **Tối ưu màn hình cảm ứng:** Nút bấm to rõ, phân nhóm danh mục bánh trực quan.
- **Phím tắt tiện dụng:** Phím `F2` đưa con trỏ vào ô quét mã vạch SKU; phím `Space` xác nhận thanh toán.
- **Thanh toán gộp đa nguồn:** Trong cùng 1 đơn hàng, thu ngân có thể thu phối hợp:
  $$\text{Tổng thanh toán} = \text{Tiền mặt} + \text{Chuyển khoản VietQR} + \text{Điểm ví thành viên}$$
- **Hóa đơn in nhiệt 80mm:** Hỗ trợ xem trước và in trực tiếp ra máy in nhiệt khổ tiêu chuẩn 80mm với đầy đủ mã QR thanh toán và thông tin tích điểm.
- **Phản hồi âm thanh:** Tích hợp âm thanh tương tác xúc giác (tactile click) tạo cảm giác như máy POS chuyên nghiệp qua Web Audio API thuần.

### 5.2. Định Mức Nguyên Vật Liệu (BOM) & Tự Động Tính Hao Hụt 5%
- Quản lý công thức làm bánh (Bill of Materials) chi tiết đến từng gram/ml cho từng loại bánh.
- **Quy tắc hao hụt 5%:** Khi mẻ bánh hoàn thành, hệ thống tự động cộng thêm $5\%$ lượng hao hụt tự nhiên trong quá trình nhào bột/nướng bánh vào kho trước khi trừ tồn:
  $$\text{Lượng nguyên liệu thực tế trừ kho} = \text{Định mức BOM} \times \text{Số lượng bánh} \times 1.05$$

### 5.3. Màn Hình Bếp KDS (Kitchen Display System)
- Hiển thị theo thời gian thực các mẻ bánh cần nướng và bánh sinh nhật đặt trước.
- Thao tác 1 chạm: Nhận mẻ bánh $\rightarrow$ Đang nướng $\rightarrow$ Hoàn thành $\rightarrow$ Tự động tăng tồn kho bánh thành phẩm và trừ kho nguyên liệu.

### 5.4. Đặt Bánh Sinh Nhật & Sự Kiện Theo Hẹn (Custom Cake Orders)
- Tiếp nhận yêu cầu kích thước, cốt bánh, nhân bánh, mẫu chữ viết và ảnh thiết kế mẫu.
- **Quy tắc đặt cọc $\ge 30\%$:** Khách hàng bắt buộc phải thanh toán đặt cọc tối thiểu $30\%$ giá trị đơn hàng mới chuyển trạng thái xác nhận làm bánh.
- Quản lý tiến độ làm bánh theo mô hình Kanban (Đã tiếp nhận $\rightarrow$ Đang làm $\rightarrow$ Hoàn thành $\rightarrow$ Đã giao).

### 5.5. Cảnh Báo Bánh Cận Date Dưới 24 Giờ
- Tự động lọc các mẻ bánh có hạn sử dụng dưới 24 giờ.
- Hiển thị cảnh báo trực quan trên Dashboard quản trị để quản lý kịp thời đưa ra chương trình khuyến mãi xả hàng tươi cuối ngày.

### 5.6. Tích Điểm Ví (10%) & Gói Hội Viên VIP
- Mỗi đơn hàng thành công tự động tích lũy $10\%$ tổng giá trị hóa đơn thành điểm ví (tỷ lệ quy đổi: $1\text{ điểm} = 1.000\text{ VNĐ}$).
- Khách hàng có thể nạp thêm tiền vào ví điểm thông qua mã VietQR động sinh tức thì.
- Gói VIP Tháng / VIP Năm: Tự động áp dụng chiết khấu đặc quyền $10\%$ cho toàn bộ hóa đơn.

### 5.7. Quản Lý Nhân Sự & Nguyên Tắc Bảo Toàn Sổ Sách Tài Chính
- Quản trị viên cấp tài khoản cho Thu Ngân, Thợ Bánh, hoặc Admin phụ.
- **Nguyên tắc kiểm toán tài chính (Financial Audit Guard):**
  - Chỉ cho phép **Xóa vĩnh viễn** tài khoản nhân viên khi nhân viên đó **chưa từng phát sinh bất kỳ đơn hàng nào** (`order_count == 0`) hoặc **mẻ bánh nào** (`batch_count == 0`).
  - Đối với nhân viên đã có lịch sử làm việc/bán hàng, nút Xóa tự động bị vô hiệu hóa; Admin sử dụng tính năng **Khóa tài khoản** (`is_active = False`) nhằm bảo toàn toàn vẹn lịch sử hóa đơn tài chính.

### 5.8. Tích Hợp VietQR Napas Động
- Tự động sinh mã VietQR theo chuẩn Napas của ngân hàng thụ hưởng (MB, Vietcombank, Techcombank,...).
- Mã QR tích hợp sẵn số tiền chính xác và nội dung chuyển khoản mã hóa (ví dụ: `HD20260922001` hoặc `NAPDIEM_USER_1`).
- Đồng hồ đếm ngược giao dịch trong **10 phút**.

---

## 🛡️ 6. Cơ Chế Bảo Mật Toàn Diện (Security Hardening)

Hệ thống được gia cố bảo mật theo các tiêu chuẩn OWASP và thiết kế nhiều tầng:

1. **Phòng Chống Dò Mật Khẩu (Brute-Force Rate Limiting):**
   - Theo dõi số lần đăng nhập thất bại theo cặp `Client IP + Username`.
   - Nhập sai quá 5 lần trong vòng 5 phút sẽ tự động khóa tài khoản tạm thời trong 5 phút.
2. **Bảo Mật Cookie & Phiên Làm Việc (Session Security):**
   - `SESSION_COOKIE_HTTPONLY = True`: Ngăn chặn mã độc JavaScript/XSS đọc cookie phiên.
   - `SESSION_COOKIE_SAMESITE = 'Lax'` & `CSRF_COOKIE_SAMESITE = 'Lax'`: Ngăn chặn tấn công CSRF.
3. **Bảo Vệ Tiêu Đề HTTP (HTTP Security Headers):**
   - `X_FRAME_OPTIONS = 'DENY'`: Chống tấn công Clickjacking.
   - `SECURE_CONTENT_TYPE_NOSNIFF = True`: Chống MIME-sniffing.
   - `SECURE_BROWSER_XSS_FILTER = True`: Bật bộ lọc XSS của trình duyệt.
4. **Phân Vùng & Cách Ly Cổng Nghiêm Ngặt (`PortalAccessMiddleware`):**
   - Khách hàng không thể duyệt vào hay đăng nhập vào Cổng Nhân Viên (8009) hoặc Cổng Admin (8010).
   - Cổng 8009 khóa tuyệt đối chức năng tự đăng ký.
   - Trang `/auth/admin-setup/` khóa vĩnh viễn ngay khi có 1 Admin tồn tại.
   - Trang chủ `/` tự động nhận diện portal để chuyển hướng hợp lý (khách hàng vào menu bánh, nhân viên vào màn hình làm việc, không để lộ dashboard nội bộ cho khách vãng lai).
5. **Tiêu Chuẩn Mật Khẩu Khắt Khe:**
   - Bắt buộc kiểm tra độ an toàn mật khẩu qua 4 bộ lọc chuẩn của Django (`UserAttributeSimilarityValidator`, `MinimumLengthValidator >= 8`, `CommonPasswordValidator`, `NumericPasswordValidator`).
6. **Bảo Mật Tiến Trình Reset Production:**
   - Mật khẩu không truyền qua đối số dòng lệnh mà truyền qua biến môi trường an toàn của container, ngăn chặn rò rỉ qua `ps aux`.

---

## 🌍 7. Hỗ Trợ Đa Ngôn Ngữ (i18n: VI / EN)

Hệ thống hỗ trợ song ngữ toàn diện:
- **Tiếng Việt (VI 🇻🇳)** - Ngôn ngữ mặc định
- **English (EN 🇬🇧)**

Người dùng có thể chuyển đổi ngôn ngữ nhanh chóng tại thanh Header trên mọi trang màn hình. Tất cả nhãn chức năng, thông báo hệ thống và giao diện mua hàng đều được định nghĩa thông qua catalog dịch thuật GNU gettext (`locale/vi/` và `locale/en/`).

---

## 📁 8. Cấu Trúc Thư Mục & Hướng Dẫn Nạp Ảnh (Asset Sourcing)

### 8.1. Cấu Trúc Thư Mục Dự Án
```
bakery/
├── apps/
│   ├── authentication/     # Tài khoản, phân quyền, hồ sơ khách hàng, ví điểm
│   ├── products/           # Danh mục bánh, sản phẩm, mã giảm giá (coupons)
│   ├── pos/                # Quầy bán hàng POS cảm ứng, đơn hàng, hóa đơn
│   ├── custom_orders/      # Đặt bánh sinh nhật/sự kiện theo hẹn
│   ├── kitchen_bom/        # Màn hình bếp KDS, kho nguyên liệu, định mức BOM
│   ├── inventory/          # Nhập xuất tồn kho
│   └── dashboard/          # Báo cáo, cài đặt VietQR, quản lý nhân viên, middleware
├── config/                 # Cấu hình Django (settings, urls, wsgi)
├── docker-compose.dev.yml  # Docker Compose môi trường Phát triển
├── docker-compose.prod.yml # Docker Compose môi trường Sản xuất (Gunicorn)
├── Dockerfile              # Dockerfile đa tầng tối ưu
├── nginx/
│   └── nginx.conf          # Cấu hình Gateway phân luồng Multiport (8008, 8009, 8010)
├── locale/                 # Tệp dịch ngôn ngữ (vi, en)
├── static/                 # Tài nguyên tĩnh (CSS, JS, SVG logos)
│   └── images/             # Logo, icon, ảnh mặc định
├── media/                  # Thư mục lưu trữ media động (mount ra máy host)
│   ├── products/           # Ảnh các món bánh bán lẻ
│   ├── custom_orders/      # Ảnh mẫu bánh kem theo hẹn
│   └── avatars/            # Ảnh đại diện người dùng
├── templates/              # Giao diện HTML (Tailwind CSS Server-side Rendering)
├── reset_db.sh             # Script quản trị & reset cơ sở dữ liệu
└── manage.py
```

### 8.2. Danh Mục Tệp Ảnh Khuyến Nghị Nạp Vào Hệ Thống
Hệ thống đã chuẩn bị sẵn các placeholder vector SVG sắc nét. Bạn có thể thay thế bằng ảnh chụp thực tế theo danh sách sau:

#### A. Ảnh Giao Diện & Logo (`static/images/`)
- `logo.svg` *(hoặc `logo.png`)*: Logo thương hiệu tiệm bánh ($120 \times 120\text{ px}$).
- `favicon.ico`: Icon tab trình duyệt ($32 \times 32\text{ px}$).
- `placeholder-cake.svg`: Ảnh mặc định khi món chưa tải ảnh ($600 \times 600\text{ px}$).
- `default-avatar.svg`: Ảnh đại diện mặc định ($150 \times 150\text{ px}$).

#### B. Ảnh Các Món Bánh Bán Lẻ (`media/products/`)
*Khuyến nghị: Định dạng `.jpg` hoặc `.webp`, kích thước $600 \times 600\text{ px}$ hoặc $800 \times 800\text{ px}$, dung lượng $< 300\text{ KB}$*:
- `croissant.jpg`: Bánh Sừng Bò Bơ Pháp (Croissant)
- `pain_au_chocolat.jpg`: Bánh Mì Sô-cô-la (Pain au Chocolat)
- `baguette.jpg`: Bánh Mì Baguette Truyền Thống
- `tiramisu.jpg`: Bánh Tiramisu Cổ Điển Ý
- `red_velvet.jpg`: Bánh Kem Nhung Đỏ (Red Velvet)
- `matcha_cheesecake.jpg`: Bánh Cheesecake Trà Xanh Nhật Bản
- `custard_strawberry_cake.jpg`: Bánh Kem Dâu Tây Tươi
- `black_forest_cake.jpg`: Bánh Kem Rừng Đen (Black Forest)
- `mango_mousse_cake.jpg`: Bánh Mousse Xoài Nhiệt Đới
- `macaron.jpg`: Bánh Macaron Đủ Vị (Hộp 6 cái)
- `lemon_tart.jpg`: Bánh Tart Chanh Vàng Meringue
- `almond_croissant.jpg`: Bánh Sừng Bò Hạnh Nhân

---

## 🛠️ 9. Lệnh Vận Hành Thường Dùng & Kiểm Thử Tự Động

### Xem Trạng Thái & Log Hệ Thống
```bash
# Xem trạng thái các container đang chạy
docker compose -f docker-compose.dev.yml ps

# Xem log thời gian thực của web backend
docker compose -f docker-compose.dev.yml logs -f web

# Xem log Nginx Gateway
docker compose -f docker-compose.dev.yml logs -f gateway
```

### Chạy Kiểm Thử Tự Động (Automated Unit Tests)
```bash
docker compose -f docker-compose.dev.yml exec web python manage.py test apps.dashboard.tests
```

### Biên Dịch Lại Ngôn Ngữ (Khi Chỉnh Sửa Dịch Thuật)
```bash
docker compose -f docker-compose.dev.yml exec web python manage.py compilemessages
```

### Vận Hành Môi Trường Sản Xuất (Production)
```bash
# Khởi chạy bản production với Gunicorn
docker compose -f docker-compose.prod.yml up -d --build

# Khởi tạo dữ liệu sạch cho Production
./reset_db.sh --prod
```

---

**© 2026 Artisan Bakery Management System. Built with Django, MySQL, Nginx & Docker.**
