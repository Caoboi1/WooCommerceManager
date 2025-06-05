#!/bin/bash

# Script khắc phục VNC cho WooCommerce Product Manager
# Sửa lỗi VNC dừng hoặc không kết nối được

echo "🔧 Khắc phục VNC cho ứng dụng PyQt6..."

# Dọn dẹp các process cũ
echo "🧹 Dọn dẹp processes cũ..."
pkill -f "vnc" || true
pkill -f "Xvnc" || true
pkill -f "x11vnc" || true
sleep 2

# Xóa các file lock cũ
rm -rf /tmp/.X*-lock
rm -rf /tmp/.X11-unix/*
rm -rf ~/.vnc/*.pid
rm -rf ~/.vnc/*.log

# Thiết lập environment variables
export DISPLAY=:1
export QT_QPA_PLATFORM=xcb
export XDG_RUNTIME_DIR=/tmp/runtime-$USER
mkdir -p $XDG_RUNTIME_DIR

# Khởi động Xvfb nếu chưa có
if ! pgrep -x "Xvfb" > /dev/null; then
    echo "🖥️  Khởi động Xvfb..."
    Xvfb :1 -screen 0 1024x768x24 -ac +extension GLX +render -noreset &
    sleep 3
fi

# Kiểm tra TigerVNC
if command -v vncserver >/dev/null 2>&1; then
    echo "🐅 Sử dụng TigerVNC..."
    
    # Tạo thư mục VNC
    mkdir -p ~/.vnc
    
    # Tạo mật khẩu VNC
    echo "woocommerce123" | vncpasswd -f > ~/.vnc/passwd
    chmod 600 ~/.vnc/passwd
    
    # Tạo xstartup
    cat > ~/.vnc/xstartup << 'EOF'
#!/bin/bash
export XKL_XMODMAP_DISABLE=1
export QT_QPA_PLATFORM=xcb
export DISPLAY=:1

# Khởi động window manager
if command -v fluxbox >/dev/null 2>&1; then
    fluxbox &
elif command -v openbox >/dev/null 2>&1; then
    openbox &
else
    twm &
fi

# Đợi window manager khởi động
sleep 2

# Khởi động ứng dụng
cd "$(dirname "$0")"
python3 main.py &

# Giữ session alive
wait
EOF
    chmod +x ~/.vnc/xstartup
    
    # Khởi động VNC server
    vncserver :1 -geometry 1024x768 -depth 24 -localhost no
    
elif command -v x11vnc >/dev/null 2>&1; then
    echo "🔗 Sử dụng x11vnc..."
    
    # Khởi động x11vnc
    x11vnc -display :1 -forever -usepw -create -shared -noxdamage -passwd woocommerce123 &
    
else
    echo "❌ Không tìm thấy VNC server"
    exit 1
fi

sleep 3

# Kiểm tra VNC đã chạy chưa
if netstat -ln | grep -q ":590[0-9]"; then
    echo "✅ VNC server đã khởi động thành công"
    echo "🌐 Kết nối: localhost:5901"
    echo "🔑 Mật khẩu: woocommerce123"
    
    # Khởi động ứng dụng nếu chưa có trong xstartup
    if ! pgrep -f "python.*main.py" > /dev/null; then
        echo "🚀 Khởi động ứng dụng WooCommerce Manager..."
        cd "$(dirname "$0")"
        DISPLAY=:1 python3 main.py &
    fi
    
else
    echo "❌ VNC server không khởi động được"
    exit 1
fi

echo "🎯 VNC đã sẵn sàng. Sử dụng VNC client để kết nối."