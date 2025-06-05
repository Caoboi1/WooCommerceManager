#!/bin/bash

echo "🚀 WooCommerce Product Manager - Simple Start"
echo

# Kiểm tra dependencies
echo "📦 Kiểm tra dependencies..."
python3 -c "import PyQt6, requests, pandas" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "⚠️  Cài đặt dependencies..."
    python3 -m pip install PyQt6 requests pandas
fi

# Đặt environment variables cho VNC platform
export QT_QPA_PLATFORM=vnc
export QT_LOGGING_RULES='*.debug=false'

echo "✅ Khởi động ứng dụng với VNC platform..."
python3 main_fixed.py