#!/bin/bash

# Script khởi động ổn định cho WooCommerce Manager
# Khắc phục vấn đề VNC dừng bằng cách sử dụng offscreen platform

echo "Khởi động WooCommerce Manager (Stable Version)..."

# Dọn dẹp processes cũ
pkill -f "python.*main.py" 2>/dev/null || true
pkill -f "python.*run_simple.py" 2>/dev/null || true

# Thiết lập môi trường
export QT_QPA_PLATFORM=offscreen
export QT_LOGGING_RULES="*.debug=false"
export XDG_RUNTIME_DIR=/tmp/runtime-runner
mkdir -p $XDG_RUNTIME_DIR

# Khởi động ứng dụng trong background
echo "Đang khởi động ứng dụng..."
python3 run_simple.py &
APP_PID=$!

echo "✅ Ứng dụng đã khởi động thành công"
echo "PID: $APP_PID"
echo ""
echo "Ứng dụng đang chạy với platform offscreen"
echo "Database sẽ được tạo tại: woocommerce_manager.db"
echo ""
echo "Để dừng ứng dụng: kill $APP_PID"

# Theo dõi process
sleep 5
if ps -p $APP_PID > /dev/null; then
    echo "🎯 Ứng dụng đang chạy ổn định"
else
    echo "❌ Ứng dụng đã dừng"
fi