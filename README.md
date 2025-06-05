# WooCommerce Product Manager

Ứng dụng desktop PyQt6 quản lý sản phẩm đa site WooCommerce với giao diện tiếng Việt.

## 📋 Tổng quan

Ứng dụng này cho phép bạn:
- Quản lý nhiều cửa hàng WooCommerce từ một giao diện duy nhất
- Đồng bộ sản phẩm từ các site về database local
- Thêm, sửa, xóa sản phẩm với auto-load danh mục từ folder scanner
- Quản lý danh mục với mô tả chi tiết (200 ký tự)
- Bulk upload sản phẩm hàng loạt
- Import/Export dữ liệu dạng CSV
- Test kết nối API WooCommerce
- AI tạo nội dung sản phẩm tự động

## 🏗️ Kiến trúc ứng dụng

```
WooCommerce Product Manager/
├── main.py                    # Entry point chính
├── app/                       # Thư mục source code
│   ├── __init__.py           # Package initialization
│   ├── main_window.py        # Cửa sổ chính với tab interface
│   ├── site_manager.py       # Tab quản lý sites WooCommerce
│   ├── product_manager.py    # Tab quản lý sản phẩm
│   ├── database.py           # SQLite database manager
│   ├── models.py             # Data models (Site, Product)
│   ├── woocommerce_api.py    # WooCommerce REST API client
│   ├── dialogs.py            # Dialog forms cho thêm/sửa
│   └── utils.py              # Utility functions
├── start_vnc.sh              # Script khởi động VNC server
├── setup_desktop.sh          # Script thiết lập desktop environment
└── README.md                 # Tài liệu này
```

## 🚀 Cài đặt và chạy

### Yêu cầu hệ thống

- Python 3.8+
- PyQt6
- Desktop environment hoặc VNC server (cho cloud deployment)
- Docker (khuyến nghị cho deployment)

### Phương pháp 1: Chạy với Docker (Khuyến nghị)

```bash
# Build và chạy container
docker-compose up --build

# Hoặc chỉ build image
docker build -t woocommerce-manager .
docker run -p 5901:5901 woocommerce-manager
```

Truy cập ứng dụng qua VNC client: `localhost:5901` (mật khẩu: `woocommerce123`)

### Phương pháp 2: Cài đặt local

```bash
# Cài đặt Python packages
pip install PyQt6 requests pandas

# Cài đặt system dependencies (Ubuntu/Debian)
sudo apt install libxkbcommon0 libxkbcommon-x11-0 libqt6core6 libqt6gui6 libqt6widgets6
```

#### Chạy trực tiếp (có desktop)
```bash
python3 main.py
```

#### Chạy với VNC (cloud/headless)
```bash
# Thiết lập desktop environment
chmod +x setup_desktop.sh
./setup_desktop.sh

# Khởi động VNC server
chmod +x start_vnc.sh
./start_vnc.sh
```

### Phương pháp 3: Deployment trên Cloud

Cho các platform cloud như Replit, do thiếu thư viện desktop, khuyến nghị sử dụng Docker hoặc deploy trên VPS có desktop support.

**Replit Limitation:** 
```
ImportError: libxkbcommon.so.0: cannot open shared object file: No such file or directory
```

**Giải pháp:**
- Sử dụng Docker với desktop environment đầy đủ
- Deploy trên VPS có GUI support  
- Chạy local với desktop environment

## 📊 Database Schema

Ứng dụng sử dụng SQLite với 2 bảng chính:

### Bảng `sites`
```sql
CREATE TABLE sites (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,              -- Tên site
    url TEXT NOT NULL,               -- URL của site WooCommerce
    consumer_key TEXT NOT NULL,      -- WooCommerce Consumer Key
    consumer_secret TEXT NOT NULL,   -- WooCommerce Consumer Secret
    is_active BOOLEAN DEFAULT 1,     -- Trạng thái hoạt động
    notes TEXT,                      -- Ghi chú
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Bảng `products`
```sql
CREATE TABLE products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    site_id INTEGER NOT NULL,        -- Liên kết với sites.id
    wc_product_id INTEGER,           -- ID sản phẩm trên WooCommerce
    name TEXT,                       -- Tên sản phẩm
    sku TEXT,                        -- SKU sản phẩm
    price REAL,                      -- Giá hiện tại
    regular_price REAL,              -- Giá gốc
    sale_price REAL,                 -- Giá sale
    stock_quantity INTEGER,          -- Số lượng kho
    status TEXT,                     -- Trạng thái (publish, draft, private)
    description TEXT,                -- Mô tả chi tiết
    short_description TEXT,          -- Mô tả ngắn
    categories TEXT,                 -- Danh mục (comma-separated)
    tags TEXT,                       -- Tags (comma-separated)
    images TEXT,                     -- URLs hình ảnh (comma-separated)
    last_sync TIMESTAMP,             -- Lần đồng bộ cuối
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (site_id) REFERENCES sites (id) ON DELETE CASCADE
);
```

## 🔌 WooCommerce API

### Thiết lập API Keys

1. Vào WordPress Admin → WooCommerce → Settings → Advanced → REST API
2. Click "Add key"
3. Chọn permissions: **Read/Write**
4. Copy Consumer Key và Consumer Secret
5. Thêm vào ứng dụng qua tab "Quản lý Site"

### API Endpoints được sử dụng

- `GET /wp-json/wc/v3/system_status` - Test kết nối
- `GET /wp-json/wc/v3/products` - Lấy danh sách sản phẩm
- `POST /wp-json/wc/v3/products` - Tạo sản phẩm mới
- `PUT /wp-json/wc/v3/products/{id}` - Cập nhật sản phẩm
- `DELETE /wp-json/wc/v3/products/{id}` - Xóa sản phẩm

## 🖥️ Giao diện người dùng

### Tab "Quản lý Site"
- **Danh sách sites**: Hiển thị tất cả sites đã thêm
- **Thêm site**: Form nhập thông tin site mới
- **Sửa site**: Chỉnh sửa thông tin site đã có
- **Test kết nối**: Kiểm tra kết nối API
- **Import/Export**: CSV import/export cho sites

### Tab "Quản lý Sản phẩm"
- **Danh sách sản phẩm**: Hiển thị sản phẩm từ tất cả sites
- **Tìm kiếm & lọc**: Theo tên, SKU, site, giá, trạng thái
- **Đồng bộ**: Đồng bộ sản phẩm từ các sites
- **CRUD operations**: Thêm/sửa/xóa sản phẩm
- **Chi tiết sản phẩm**: Panel hiển thị thông tin chi tiết

## 📁 Import/Export

### Format CSV cho Sites
```csv
Tên Site,URL,Consumer Key,Consumer Secret,Hoạt động,Ghi chú
My Shop,https://myshop.com,ck_abc123,cs_def456,Có,Site chính
Test Shop,https://test.com,ck_xyz789,cs_uvw012,Không,Site test
```

### Format CSV cho Products
```csv
Site,Tên sản phẩm,SKU,Giá gốc,Giá sale,Kho,Trạng thái,Mô tả
My Shop,Áo thun nam,AT001,200000,150000,50,publish,Áo thun cotton 100%
```

## 🔧 Cấu hình VNC

### File cấu hình VNC
- **Display**: `:1`
- **Port**: `5901`
- **Resolution**: `1024x768`
- **Password**: `woocommerce123`

### Xstartup script
```bash
#!/bin/bash
# Load system environment
[ -r $HOME/.Xresources ] && xrdb $HOME/.Xresources

# Start window manager
fluxbox &

# Wait for window manager
sleep 2

# Start the WooCommerce Product Manager application
cd "$SCRIPT_DIR"
python3 main.py &

# Keep session alive
wait
```

## 🐛 Troubleshooting

### Lỗi thường gặp

1. **ImportError: No module named 'PyQt6'**
   ```bash
   pip install PyQt6
   ```

2. **qt.qpa.plugin: Could not load the Qt platform plugin "xcb"**
   ```bash
   export QT_QPA_PLATFORM=offscreen
   # Hoặc cài đặt desktop environment
   ```

3. **VNC connection refused**
   ```bash
   # Kiểm tra VNC server
   ps aux | grep vnc
   
   # Restart VNC
   ./start_vnc.sh
   ```

4. **WooCommerce API 401 Unauthorized**
   - Kiểm tra Consumer Key/Secret
   - Đảm bảo API permissions là Read/Write
   - Kiểm tra SSL certificate nếu dùng HTTPS

### Logs

- **Application logs**: `woocommerce_manager.log`
- **VNC logs**: `logs/vnc.log`
- **Database**: `woocommerce_manager.db`

## 🔐 Bảo mật

- Consumer Key/Secret được lưu trong database local
- Kết nối API qua HTTPS (khuyến nghị)
- VNC password có thể thay đổi trong script
- Database SQLite không mã hóa (chỉ phù hợp cho local use)

## 📝 Development Notes

### Thêm tính năng mới

1. **Models**: Cập nhật `app/models.py` với data structures
2. **Database**: Thêm migrations trong `app/database.py`
3. **API**: Mở rộng `app/woocommerce_api.py` cho API calls
4. **UI**: Tạo components trong `app/` directory

### Code Style

- Sử dụng type hints
- Docstrings cho functions/classes
- Comments bằng tiếng Việt cho business logic
- Error handling với try/catch blocks
- Logging cho debug và monitoring

### Testing

```bash
# Test database
python3 -c "from app.database import DatabaseManager; db = DatabaseManager(); db.init_database()"

# Test UI
python3 main.py

# Test API
python3 -c "from app.woocommerce_api import WooCommerceAPI; from app.models import Site; site = Site(url='test', consumer_key='test', consumer_secret='test'); api = WooCommerceAPI(site); print(api.test_connection())"
```

## 👨‍💻 Tác giả

**Học Trần**  
Telegram: [@anh2nd](https://t.me/anh2nd)

## 📞 Support

Để báo cáo bug hoặc request tính năng mới, vui lòng liên hệ:
- Telegram: [@anh2nd](https://t.me/anh2nd)
- Thông tin cần cung cấp:
  - Phiên bản Python
  - Phiên bản PyQt6
  - Log errors
  - Steps to reproduce

## 📄 License

MIT License - Xem file LICENSE để biết chi tiết.