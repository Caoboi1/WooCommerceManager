#!/bin/bash

# VNC Server Startup Script for WooCommerce Product Manager
# Khởi động VNC server để hiển thị ứng dụng PyQt6 desktop

set -e

# Cấu hình VNC
VNC_DISPLAY=":1"
VNC_PORT="5901"
VNC_RESOLUTION="1024x768"
VNC_DEPTH="24"
VNC_PASSWORD=${VNC_PASSWORD:-"woocommerce123"}

# Đường dẫn
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$SCRIPT_DIR/logs"
PID_DIR="$SCRIPT_DIR/pids"

# Tạo thư mục cần thiết
mkdir -p "$LOG_DIR" "$PID_DIR"

echo "🚀 Khởi động VNC Server cho WooCommerce Product Manager..."

# Kiểm tra và dừng VNC server cũ nếu có
if [ -f "$PID_DIR/vnc.pid" ]; then
    OLD_PID=$(cat "$PID_DIR/vnc.pid")
    if ps -p "$OLD_PID" > /dev/null 2>&1; then
        echo "🛑 Dừng VNC server cũ (PID: $OLD_PID)..."
        kill "$OLD_PID" || true
        sleep 2
    fi
    rm -f "$PID_DIR/vnc.pid"
fi

# Dừng tất cả VNC servers trên display :1
vncserver -kill "$VNC_DISPLAY" 2>/dev/null || true
sleep 2

# Thiết lập môi trường
export DISPLAY="$VNC_DISPLAY"
export XAUTHORITY="$HOME/.Xauthority"

# Tạo thư mục VNC config
mkdir -p "$HOME/.vnc"

# Thiết lập mật khẩu VNC
echo "🔑 Thiết lập mật khẩu VNC..."
echo "$VNC_PASSWORD" | vncpasswd -f > "$HOME/.vnc/passwd"
chmod 600 "$HOME/.vnc/passwd"

# Tạo file xstartup cho VNC
cat > "$HOME/.vnc/xstartup" << 'EOF'
#!/bin/bash

# Load system environment
[ -r $HOME/.Xresources ] && xrdb $HOME/.Xresources

# Start window manager
if command -v fluxbox >/dev/null 2>&1; then
    fluxbox &
elif command -v xfce4-session >/dev/null 2>&1; then
    xfce4-session &
elif command -v openbox >/dev/null 2>&1; then
    openbox &
else
    # Fallback to basic X session
    xterm -geometry 80x24+10+10 -ls -title "Terminal" &
    twm &
fi

# Wait for window manager
sleep 2

# Start the WooCommerce Product Manager application
cd "$SCRIPT_DIR"
python3 main.py &

# Keep session alive
wait
EOF

chmod +x "$HOME/.vnc/xstartup"

# Khởi động VNC server
echo "🖥️  Khởi động VNC server trên display $VNC_DISPLAY..."
vncserver "$VNC_DISPLAY" \
    -geometry "$VNC_RESOLUTION" \
    -depth "$VNC_DEPTH" \
    -localhost no \
    -alwaysshared \
    -dpi 96 \
    > "$LOG_DIR/vnc.log" 2>&1

# Lưu PID
VNC_PID=$(pgrep -f "Xvnc.*$VNC_DISPLAY" | head -1)
if [ -n "$VNC_PID" ]; then
    echo "$VNC_PID" > "$PID_DIR/vnc.pid"
    echo "✅ VNC server đã khởi động thành công!"
    echo "📋 Thông tin kết nối:"
    echo "   - Display: $VNC_DISPLAY"
    echo "   - Port: $VNC_PORT"
    echo "   - Resolution: $VNC_RESOLUTION"
    echo "   - Password: $VNC_PASSWORD"
    echo "   - PID: $VNC_PID"
    echo ""
    echo "🌐 Để kết nối VNC:"
    echo "   - VNC Viewer: localhost:$VNC_PORT"
    echo "   - Web Browser: http://localhost:6080/vnc.html (nếu có noVNC)"
    echo ""
    echo "📝 Logs:"
    echo "   - VNC: $LOG_DIR/vnc.log"
    echo "   - App: $LOG_DIR/app.log"
else
    echo "❌ Không thể khởi động VNC server!"
    exit 1
fi

# Thiết lập port forwarding cho Replit/cloud environments
if [ -n "$REPL_ID" ] || [ -n "$CODESPACE_NAME" ]; then
    echo "☁️  Thiết lập port forwarding cho cloud environment..."
    
    # Kill existing port forwards
    pkill -f "socat.*TCP-LISTEN:5000" || true
    
    # Forward port 5000 to VNC port
    socat TCP-LISTEN:5000,fork TCP:localhost:$VNC_PORT &
    SOCAT_PID=$!
    echo "$SOCAT_PID" > "$PID_DIR/socat.pid"
    
    echo "🔄 Port forwarding: 5000 -> $VNC_PORT"
fi

# Theo dõi VNC server
echo "👁️  Theo dõi VNC server..."
tail -f "$LOG_DIR/vnc.log" &
TAIL_PID=$!

# Function để dọn dẹp khi thoát
cleanup() {
    echo ""
    echo "🧹 Đang dọn dẹp..."
    
    # Kill tail process
    [ -n "$TAIL_PID" ] && kill "$TAIL_PID" 2>/dev/null || true
    
    # Kill socat if running
    if [ -f "$PID_DIR/socat.pid" ]; then
        SOCAT_PID=$(cat "$PID_DIR/socat.pid")
        kill "$SOCAT_PID" 2>/dev/null || true
        rm -f "$PID_DIR/socat.pid"
    fi
    
    # Kill VNC server
    if [ -f "$PID_DIR/vnc.pid" ]; then
        VNC_PID=$(cat "$PID_DIR/vnc.pid")
        kill "$VNC_PID" 2>/dev/null || true
        rm -f "$PID_DIR/vnc.pid"
    fi
    
    vncserver -kill "$VNC_DISPLAY" 2>/dev/null || true
    
    echo "✅ Đã dọn dẹp xong."
}

# Đăng ký cleanup function
trap cleanup EXIT INT TERM

# Chờ signal hoặc VNC server thoát
wait "$VNC_PID" 2>/dev/null || true

echo "🏁 VNC server đã thoát."
