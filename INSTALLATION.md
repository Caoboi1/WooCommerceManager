# Hướng dẫn cài đặt WooCommerce Product Manager

## Yêu cầu hệ thống
- Python 3.8+
- Windows/Linux/macOS với desktop environment

## Cài đặt trên Windows

### 1. Tải code về máy
```bash
git clone <repository_url>
cd WooCommerceManager
```

### 2. Tạo virtual environment
```bash
python -m venv .venv
.venv\Scripts\activate
```

### 3. Cài đặt dependencies
```bash
pip install PyQt6==6.6.1
pip install requests==2.31.0  
pip install pandas==2.1.4
```

### 4. Chạy ứng dụng
```bash
python main.py
```

## Cài đặt trên Linux

### 1. Cài đặt system dependencies
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install python3-pip python3-venv
sudo apt install libxkbcommon0 libxkbcommon-x11-0
sudo apt install qt6-base-dev libgl1-mesa-glx

# CentOS/RHEL
sudo yum install python3-pip python3-venv
sudo yum install libxkbcommon libxkbcommon-x11
```

### 2. Tạo virtual environment và cài đặt
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install PyQt6 requests pandas
```

### 3. Chạy ứng dụng
```bash
python3 main.py
```

## Troubleshooting

### Lỗi "cannot import name 'QAction'"
- Đảm bảo PyQt6 version >= 6.0
- QAction đã chuyển từ QtWidgets sang QtGui trong PyQt6

### Lỗi "libxkbcommon.so.0: cannot open shared object file"
- Cài đặt desktop libraries:
```bash
sudo apt install libxkbcommon0 libxkbcommon-x11-0 libgl1-mesa-glx
```

### Lỗi "ModuleNotFoundError: No module named 'PyQt6'"
- Kích hoạt virtual environment và cài đặt lại:
```bash
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux
pip install PyQt6
```

## Chạy thành công
Sau khi cài đặt đúng, ứng dụng sẽ hiển thị cửa sổ chính với:
- Tab "Quản lý Site WooCommerce"
- Tab "Quản lý Sản phẩm"
- Menu và toolbar đầy đủ chức năng
- Database SQLite được tạo tự động

## Sử dụng ứng dụng
1. Thêm site WooCommerce trong tab "Quản lý Site"
2. Nhập thông tin API keys (Consumer Key/Secret)
3. Test kết nối để đảm bảo API hoạt động
4. Đồng bộ sản phẩm từ tab "Quản lý Sản phẩm"