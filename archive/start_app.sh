#!/bin/bash

# Script khởi động đơn giản cho WooCommerce Manager
# Khắc phục vấn đề VNC dừng bằng cách sử dụng Xvfb có sẵn

echo "Khởi động WooCommerce Product Manager..."

# Kiểm tra Xvfb đang chạy
if pgrep -x "Xvfb" > /dev/null; then
    echo "Xvfb đã chạy, sử dụng display hiện tại"
    export DISPLAY=:99
else
    echo "Khởi động Xvfb..."
    Xvfb :99 -screen 0 1024x768x24 &
    sleep 2
    export DISPLAY=:99
fi

# Thiết lập môi trường PyQt6
export QT_QPA_PLATFORM=xcb
export QT_LOGGING_RULES="*.debug=false"

# Khởi động ứng dụng
echo "Chạy ứng dụng WooCommerce Manager..."
python3 run_simple.py

echo "Ứng dụng đã dừng."