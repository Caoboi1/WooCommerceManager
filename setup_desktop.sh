#!/bin/bash

# Desktop Environment Setup Script for WooCommerce Product Manager
# Thiết lập môi trường desktop và dependencies cho ứng dụng PyQt6

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "🔧 Thiết lập môi trường desktop cho WooCommerce Product Manager..."

# Detect OS
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    OS="linux"
elif [[ "$OSTYPE" == "darwin"* ]]; then
    OS="macos"
elif [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "cygwin" ]]; then
    OS="windows"
else
    echo "❌ Hệ điều hành không được hỗ trợ: $OSTYPE"
    exit 1
fi

echo "🖥️  Phát hiện hệ điều hành: $OS"

# Linux setup
setup_linux() {
    echo "🐧 Thiết lập môi trường Linux..."
    
    # Update package list
    if command -v apt-get >/dev/null 2>&1; then
        echo "📦 Cập nhật danh sách packages (apt)..."
        sudo apt-get update -y
        
        # Install desktop environment packages
        echo "🖼️  Cài đặt desktop environment..."
        sudo apt-get install -y \
            xvfb \
            x11vnc \
            fluxbox \
            xterm \
            socat \
            wget \
            curl \
            unzip \
            git
            
        # Install Python and PyQt6 dependencies
        echo "🐍 Cài đặt Python dependencies..."
        sudo apt-get install -y \
            python3 \
            python3-pip \
            python3-venv \
            python3-dev \
            python3-pyqt6 \
            python3-pyqt6.qtwidgets \
            python3-pyqt6.qtcore \
            python3-pyqt6.qtgui
            
        # Install additional Qt libraries
        sudo apt-get install -y \
            qt6-base-dev \
            libqt6widgets6 \
            libqt6core6 \
            libqt6gui6 \
            libgl1-mesa-glx \
            libxcb-xinerama0 \
            libxcb-cursor0 \
            libfontconfig1 \
            libxkbcommon-x11-0
            
    elif command -v yum >/dev/null 2>&1; then
        echo "📦 Cập nhật packages (yum)..."
        sudo yum update -y
        
        # Install desktop environment packages
        sudo yum install -y \
            xorg-x11-server-Xvfb \
            x11vnc \
            fluxbox \
            xterm \
            socat \
            wget \
            curl \
            unzip \
            git
            
        # Install Python and PyQt6
        sudo yum install -y \
            python3 \
            python3-pip \
            python3-devel \
            python3-pyqt6
            
    elif command -v dnf >/dev/null 2>&1; then
        echo "📦 Cập nhật packages (dnf)..."
        sudo dnf update -y
        
        # Install packages
        sudo dnf install -y \
            xorg-x11-server-Xvfb \
            x11vnc \
            fluxbox \
            xterm \
            socat \
            wget \
            curl \
            unzip \
            git \
            python3 \
            python3-pip \
            python3-devel \
            python3-pyqt6
    else
        echo "❌ Package manager không được hỗ trợ"
        exit 1
    fi
    
    # Install TigerVNC if x11vnc not available
    if ! command -v x11vnc >/dev/null 2>&1; then
        echo "🐅 Cài đặt TigerVNC..."
        if command -v apt-get >/dev/null 2>&1; then
            sudo apt-get install -y tigervnc-standalone-server
        elif command -v yum >/dev/null 2>&1; then
            sudo yum install -y tigervnc-server
        elif command -v dnf >/dev/null 2>&1; then
            sudo dnf install -y tigervnc-server
        fi
    fi
}

# macOS setup
setup_macos() {
    echo "🍎 Thiết lập môi trường macOS..."
    
    # Check if Homebrew is installed
    if ! command -v brew >/dev/null 2>&1; then
        echo "🍺 Cài đặt Homebrew..."
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    fi
    
    # Install packages
    echo "📦 Cài đặt packages..."
    brew install \
        python@3.11 \
        pyqt@6 \
        tiger-vnc \
        socat
        
    # Create symlinks
    brew link python@3.11
}

# Windows setup (WSL/Cygwin)
setup_windows() {
    echo "🪟 Thiết lập môi trường Windows..."
    echo "⚠️  Lưu ý: Trên Windows, khuyên dùng WSL hoặc Docker"
    
    # Check if we're in WSL
    if grep -qi microsoft /proc/version 2>/dev/null; then
        echo "🐧 Phát hiện WSL, chuyển sang setup Linux..."
        setup_linux
        return
    fi
    
    echo "📥 Tải và cài đặt dependencies thủ công:"
    echo "1. Python 3.8+: https://www.python.org/downloads/"
    echo "2. VNC Server: https://www.realvnc.com/download/vnc/"
    echo "3. Git: https://git-scm.com/download/win"
}

# Create Python virtual environment
setup_python_env() {
    echo "🐍 Thiết lập Python virtual environment..."
    
    cd "$SCRIPT_DIR"
    
    # Create virtual environment if not exists
    if [ ! -d "venv" ]; then
        python3 -m venv venv
    fi
    
    # Activate virtual environment
    source venv/bin/activate
    
    # Upgrade pip
    pip install --upgrade pip
    
    # Install Python packages
    echo "📦 Cài đặt Python packages..."
    pip install \
        PyQt6 \
        requests \
        pandas \
        sqlite3
}

# Create desktop configuration
setup_desktop_config() {
    echo "🎨 Thiết lập cấu hình desktop..."
    
    # Create .vnc directory
    mkdir -p "$HOME/.vnc"
    
    # Create fluxbox config
    mkdir -p "$HOME/.fluxbox"
    
    # Basic fluxbox menu
    cat > "$HOME/.fluxbox/menu" << 'EOF'
[begin] (WooCommerce Manager)
    [exec] (Terminal) {xterm}
    [exec] (WooCommerce Manager) {python3 main.py}
    [separator]
    [restart] (Restart)
    [exit] (Exit)
[end]
EOF

    # Fluxbox startup
    cat > "$HOME/.fluxbox/startup" << 'EOF'
#!/bin/bash
# Fluxbox startup script

# Start applications
python3 main.py &

# Start fluxbox
exec fluxbox
EOF
    chmod +x "$HOME/.fluxbox/startup"
    
    # Create Xresources for better fonts
    cat > "$HOME/.Xresources" << 'EOF'
! Font settings
Xft.dpi: 96
Xft.antialias: true
Xft.hinting: true
Xft.hintstyle: hintslight
Xft.rgba: rgb

! Terminal colors
XTerm*faceName: DejaVu Sans Mono
XTerm*faceSize: 10
XTerm*background: black
XTerm*foreground: white
EOF
}

# Create launcher scripts
create_launchers() {
    echo "🚀 Tạo launcher scripts..."
    
    # Make start_vnc.sh executable
    chmod +x "$SCRIPT_DIR/start_vnc.sh"
    
    # Create desktop launcher
    cat > "$SCRIPT_DIR/launch_app.sh" << 'EOF'
#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Activate virtual environment if exists
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
fi

# Start the application
python3 main.py "$@"
EOF
    chmod +x "$SCRIPT_DIR/launch_app.sh"
    
    # Create VNC launcher with noVNC support
    cat > "$SCRIPT_DIR/start_vnc_web.sh" << 'EOF'
#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Start VNC server
./start_vnc.sh &
VNC_PID=$!

# Download and start noVNC for web access
if [ ! -d "noVNC" ]; then
    echo "📥 Tải noVNC..."
    git clone https://github.com/novnc/noVNC.git
    git clone https://github.com/novnc/websockify noVNC/utils/websockify
fi

# Wait for VNC to start
sleep 5

# Start noVNC
echo "🌐 Khởi động noVNC web interface..."
cd noVNC
./utils/novnc_proxy --vnc localhost:5901 --listen 6080 &
NOVNC_PID=$!

echo "✅ Ứng dụng đã sẵn sàng!"
echo "🔗 Truy cập qua web: http://localhost:6080/vnc.html"
echo "🖥️  Hoặc VNC client: localhost:5901"

# Cleanup function
cleanup() {
    echo "🧹 Đang dọn dẹp..."
    kill $NOVNC_PID 2>/dev/null || true
    kill $VNC_PID 2>/dev/null || true
}

trap cleanup EXIT INT TERM

# Wait for processes
wait
EOF
    chmod +x "$SCRIPT_DIR/start_vnc_web.sh"
}

# Check system requirements
check_requirements() {
    echo "✅ Kiểm tra system requirements..."
    
    # Check Python
    if ! command -v python3 >/dev/null 2>&1; then
        echo "❌ Python 3 chưa được cài đặt"
        return 1
    fi
    
    PYTHON_VERSION=$(python3 -c "import sys; print('.'.join(map(str, sys.version_info[:2])))")
    echo "🐍 Python version: $PYTHON_VERSION"
    
    # Check PyQt6
    if ! python3 -c "import PyQt6" 2>/dev/null; then
        echo "⚠️  PyQt6 chưa được cài đặt, sẽ cài đặt sau..."
    else
        echo "✅ PyQt6 đã có sẵn"
    fi
    
    return 0
}

# Main setup function
main() {
    echo "🎯 Bắt đầu thiết lập môi trường..."
    
    # Run OS-specific setup
    case $OS in
        linux)
            setup_linux
            ;;
        macos)
            setup_macos
            ;;
        windows)
            setup_windows
            ;;
    esac
    
    # Common setup steps
    setup_python_env
    setup_desktop_config
    create_launchers
    
    # Final check
    if check_requirements; then
        echo ""
        echo "🎉 Thiết lập hoàn tất thành công!"
        echo ""
        echo "📋 Các lệnh có sẵn:"
        echo "   ./start_vnc.sh          - Khởi động VNC server"
        echo "   ./start_vnc_web.sh      - Khởi động VNC + Web interface"
        echo "   ./launch_app.sh         - Chạy ứng dụng trực tiếp"
        echo ""
        echo "🔗 Cách sử dụng:"
        echo "   1. Chạy: ./start_vnc.sh"
        echo "   2. Kết nối VNC tới: localhost:5901"
        echo "   3. Mật khẩu mặc định: woocommerce123"
        echo ""
    else
        echo "❌ Thiết lập thất bại, vui lòng kiểm tra lại requirements"
        exit 1
    fi
}

# Run main function
main "$@"
