# Dockerfile cho WooCommerce Product Manager
# Ứng dụng Python desktop PyQt6 với VNC support

FROM ubuntu:22.04

# Thiết lập timezone và locale
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Asia/Ho_Chi_Minh
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8

# Cài đặt system dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    # Desktop environment
    xvfb \
    x11vnc \
    fluxbox \
    xterm \
    # Qt dependencies
    libqt6core6 \
    libqt6gui6 \
    libqt6widgets6 \
    qt6-base-dev \
    libxkbcommon0 \
    libxkbcommon-x11-0 \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libxcb-xinerama0 \
    libxcb-cursor0 \
    libfontconfig1 \
    # Network tools
    socat \
    wget \
    curl \
    # Cleanup
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Tạo user không phải root
RUN useradd -m -s /bin/bash appuser
USER appuser
WORKDIR /home/appuser/app

# Copy application files
COPY --chown=appuser:appuser . .

# Cài đặt Python dependencies
RUN python3 -m pip install --user --no-cache-dir \
    PyQt6 \
    requests \
    pandas

# Thiết lập environment variables
ENV DISPLAY=:99
ENV QT_QPA_PLATFORM=xcb
ENV PATH="/home/appuser/.local/bin:$PATH"

# Tạo thư mục cần thiết
RUN mkdir -p /home/appuser/.vnc logs pids

# Copy VNC startup script
RUN chmod +x start_vnc.sh setup_desktop.sh run_app.sh

# Khởi tạo database
RUN python3 -c "from app.database import DatabaseManager; db = DatabaseManager(); db.init_database()"

# Expose VNC port
EXPOSE 5901 6080

# Startup script
CMD ["./start_vnc.sh"]