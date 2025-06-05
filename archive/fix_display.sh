#!/bin/bash

# Khắc phục vấn đề display cho PyQt6
echo "Khắc phục vấn đề display..."

# Dừng các process cũ
pkill -f "vnc" 2>/dev/null || true
pkill -f "Xvfb" 2>/dev/null || true
sleep 2

# Xóa các file lock
rm -f /tmp/.X*-lock 2>/dev/null || true

# Thiết lập Xvfb với cấu hình đơn giản
echo "Khởi động Xvfb..."
Xvfb :99 -screen 0 1024x768x24 -ac -nolisten tcp &
sleep 3

# Kiểm tra Xvfb đã chạy
if pgrep -x "Xvfb" > /dev/null; then
    echo "Xvfb đã khởi động thành công"
    export DISPLAY=:99
    
    # Thiết lập môi trường PyQt6
    export QT_QPA_PLATFORM=offscreen
    export QT_LOGGING_RULES="*.debug=false"
    
    # Chạy ứng dụng với offscreen platform
    echo "Khởi động ứng dụng PyQt6..."
    python3 run_simple.py
else
    echo "Không thể khởi động Xvfb"
    # Thử chạy với minimal platform
    export QT_QPA_PLATFORM=minimal
    python3 run_simple.py
fi