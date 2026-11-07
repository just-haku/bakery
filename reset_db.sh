#!/bin/bash
# ==============================================================================
# Script Quản Trị & Reset Database - Hệ Thống Tiệm Bánh Artisan Bakery
# ==============================================================================
# Cú pháp hỗ trợ:
#   ./reset_db.sh --dev 0  : Reset database Dev về 0 (sạch sẽ, không tài khoản mẫu)
#   ./reset_db.sh --dev 1  : Reset database Dev và nạp bộ dữ liệu mẫu giả lập
#   ./reset_db.sh --prod   : Khởi tạo/Reset database Production (bảo mật cao, yêu cầu nhập admin thật)
# ==============================================================================
set -e

show_help() {
    echo "HƯỚNG DẪN SỬ DỤNG RESET DATABASE:"
    echo "  ./reset_db.sh --dev 0   Reset DB môi trường Phát triển về 0 (Clean slate - 0 user, 0 sản phẩm, 0 đơn)"
    echo "  ./reset_db.sh --dev 1   Reset DB môi trường Phát triển và nạp đầy đủ dữ liệu mẫu (Seeder test)"
    echo "  ./reset_db.sh --prod    Khởi tạo/Reset DB môi trường Sản xuất (Yêu cầu mật khẩu Admin thật, kiểm tra bảo mật)"
    echo "  ./reset_db.sh --help    Hiển thị hướng dẫn này"
}

MODE="dev1"
PROD_USER=""
PROD_PASS=""
PROD_EMAIL=""
PROD_NAME=""
PROD_PHONE=""

case "$1" in
    --dev)
        if [ "$2" = "0" ]; then
            MODE="dev0"
        elif [ "$2" = "1" ]; then
            MODE="dev1"
        else
            echo "❌ Lỗi: Tham số --dev yêu cầu giá trị 0 hoặc 1."
            echo "   Ví dụ: ./reset_db.sh --dev 0  hoặc  ./reset_db.sh --dev 1"
            exit 1
        fi
        ;;
    --prod)
        MODE="prod"
        ;;
    --help|-h)
        show_help
        exit 0
        ;;
    "")
        echo ">>> Không có tham số, mặc định chạy: --dev 1 (Dữ liệu mẫu thử nghiệm)"
        echo ">>> Để reset về 0 hoàn toàn, hãy chạy: ./reset_db.sh --dev 0"
        MODE="dev1"
        ;;
    *)
        echo "❌ Lỗi: Tham số '$1' không hợp lệ."
        show_help
        exit 1
        ;;
esac

# ==============================================================================
# XỬ LÝ RIÊNG CHO CHẾ ĐỘ PRODUCTION (BẢO MẬT & XÁC NHẬN)
# ==============================================================================
if [ "$MODE" = "prod" ]; then
    echo ""
    echo "======================================================================"
    echo "🚨 CẢNH BÁO NGUY HIỂM TỐI CAO: BẠN ĐANG CHỌN RESET DATABASE PRODUCTION"
    echo "======================================================================"
    echo "Thao tác này sẽ XÓA TOÀN BỘ dữ liệu khách hàng, hóa đơn, doanh thu"
    echo "và KHÔNG THỂ HOÀN TÁC sau khi thực hiện!"
    echo "======================================================================"
    echo ""
    read -p "Để tiếp tục, vui lòng gõ chính xác cụm từ 'CONFIRM-RESET-PROD': " CONFIRM_TXT
    if [ "$CONFIRM_TXT" != "CONFIRM-RESET-PROD" ]; then
        echo ""
        echo "❌ Xác nhận không chính xác! Đã hủy bỏ thao tác an toàn."
        exit 1
    fi

    echo ""
    echo ">>> BƯỚC THIẾT LẬP TÀI KHOẢN QUẢN TRỊ VIÊN MASTER (OPERATOR) CHO PRODUCTION:"
    read -p "1. Tên đăng nhập Admin Production (ví dụ: admin_master hoặc email): " PROD_USER
    while [ -z "$PROD_USER" ]; do
        read -p "Tên đăng nhập không được để trống: " PROD_USER
    done

    read -p "2. Email thông báo [$PROD_USER]: " PROD_EMAIL
    if [ -z "$PROD_EMAIL" ]; then
        PROD_EMAIL="$PROD_USER"
    fi

    read -p "3. Họ và tên Quản trị viên [Chủ Tiệm Bánh]: " PROD_NAME
    if [ -z "$PROD_NAME" ]; then
        PROD_NAME="Chủ Tiệm Bánh"
    fi

    read -p "4. Số điện thoại liên hệ: " PROD_PHONE

    # Nhập mật khẩu bảo mật (ẩn ký tự)
    while true; do
        echo ""
        read -sp "5. Mật khẩu Quản trị viên (Tối thiểu 8 ký tự, có chữ và số): " PROD_PASS
        echo ""
        read -sp "   Xác nhận lại mật khẩu: " PROD_PASS_CONFIRM
        echo ""

        if [ "$PROD_PASS" != "$PROD_PASS_CONFIRM" ]; then
            echo "❌ Mật khẩu xác nhận không khớp! Vui lòng nhập lại."
            continue
        fi

        if [ ${#PROD_PASS} -lt 8 ]; then
            echo "❌ Mật khẩu quá ngắn (phải có ít nhất 8 ký tự)! Vui lòng nhập lại."
            continue
        fi

        break
    done
fi

# ==============================================================================
# THỰC THI QUA DOCKER CONTAINER TƯƠNG ỨNG
# ==============================================================================
echo ""
echo "======================================================================"
echo ">>> ĐANG BẮT ĐẦU RESET DATABASE: CHẾ ĐỘ [${MODE^^}]..."
echo "======================================================================"

if [ "$MODE" = "prod" ]; then
    # Môi trường Production
    COMPOSE_FILE="docker-compose.prod.yml"
    CONTAINER_NAME="bakery_web_prod"

    # Kiểm tra xem production đã chạy chưa, nếu chưa thì khởi động
    if ! docker compose -f "$COMPOSE_FILE" ps web 2>/dev/null | grep -q "Up\|running"; then
        echo ">>> Khởi chạy container production trước khi reset..."
        docker compose -f "$COMPOSE_FILE" up -d
        sleep 4
    fi

    docker compose -f "$COMPOSE_FILE" exec -e PROD_ADMIN_PASSWORD="$PROD_PASS" web python manage.py reset_db_test \
        --mode=prod \
        --admin-username="$PROD_USER" \
        --admin-email="$PROD_EMAIL" \
        --admin-name="$PROD_NAME" \
        --admin-phone="$PROD_PHONE" \
        --no-input

    # Xóa sạch mật khẩu khỏi bộ nhớ shell ngay sau khi khởi tạo hoàn tất
    unset PROD_PASS PROD_PASS_CONFIRM
else
    # Môi trường Development (dev0 hoặc dev1)
    COMPOSE_FILE="docker-compose.dev.yml"
    CONTAINER_NAME="bakery_web_dev"

    if ! docker compose -f "$COMPOSE_FILE" ps web 2>/dev/null | grep -q "Up\|running"; then
        echo ">>> Khởi chạy container dev trước khi reset..."
        docker compose -f "$COMPOSE_FILE" up -d
        sleep 3
    fi

    docker compose -f "$COMPOSE_FILE" exec web python manage.py reset_db_test \
        --mode="$MODE" \
        --no-input
fi

