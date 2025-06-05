#!/bin/bash

echo "🚀 WooCommerce Product Manager"
echo

# Kiểm tra và cài đặt dependencies
echo "📦 Kiểm tra dependencies..."
python3 -c "import PyQt6, requests, pandas" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "⚠️  Cài đặt dependencies..."
    python3 -m pip install PyQt6 requests pandas
fi

# Thiết lập VNC cho Linux
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    echo "🖥️  Thiết lập VNC display..."
    
    # Dọn dẹp VNC server cũ nếu có
    if pgrep -f "Xvnc.*:1" > /dev/null; then
        echo "🔄 Dừng VNC server cũ..."
        pkill -f "Xvnc.*:1" 2>/dev/null || true
        sleep 1
    fi
    
    # Xóa lock files cũ
    rm -f /tmp/.X1-lock /tmp/.X11-unix/X1 2>/dev/null || true
    
    # Khởi động VNC server mới
    echo "🔧 Khởi động VNC server..."
    vncserver :1 -geometry 1920x1080 -depth 24 -localhost no 2>/dev/null || true
    sleep 3
    
    # Thiết lập environment
    export DISPLAY=:1
    export QT_QPA_PLATFORM=xcb
    export QT_QPA_PLATFORM_PLUGIN_PATH=/usr/lib/x86_64-linux-gnu/qt6/plugins/platforms
    
    # Kiểm tra VNC đã chạy chưa
    if ! pgrep -f "Xvnc.*:1" > /dev/null; then
        echo "⚠️  VNC server không khởi động được, thử chế độ fallback..."
        export QT_QPA_PLATFORM=minimal
    fi
else
    # Không phải Linux, dùng platform mặc định
    export QT_QPA_PLATFORM=
fi

echo "✅ Khởi động ứng dụng..."
python3 main_fixed.py