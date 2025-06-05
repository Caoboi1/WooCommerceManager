# Added get_category_by_wc_id and find_category_by_name_or_slug methods to DatabaseManager for improved category handling.
"""
Database Manager - Quản lý cơ sở dữ liệu SQLite

COMPONENT OVERVIEW:
------------------
SQLite database manager cho ứng dụng WooCommerce Product Manager.
Quản lý 2 bảng chính: sites và products với foreign key relationships.

DATABASE SCHEMA:
---------------
sites table:
- id (PRIMARY KEY): Unique identifier
- name: Tên hiển thị của site
- url: URL của WooCommerce site
- consumer_key: WooCommerce REST API consumer key
- consumer_secret: WooCommerce REST API consumer secret
- is_active: Boolean flag cho trạng thái hoạt động
- notes: Ghi chú về site
- created_at, updated_at: Timestamps

products table:
- id (PRIMARY KEY): Unique identifier
- site_id (FOREIGN KEY): Liên kết với sites.id
- wc_product_id: ID sản phẩm trên WooCommerce
- name, sku, price, regular_price, sale_price: Thông tin sản phẩm
- stock_quantity: Số lượng kho
- status: Trạng thái sản phẩm (publish, draft, private)
- description, short_description: Mô tả sản phẩm
- categories, tags: Phân loại (comma-separated strings)
- images: URLs hình ảnh (comma-separated)
- last_sync: Timestamp đồng bộ cuối cùng
- created_at, updated_at: Timestamps

INDEXES:
--------
- idx_products_site_id: Index trên site_id cho performance
- idx_products_sku: Index trên SKU cho tìm kiếm
- idx_products_wc_id: Index trên wc_product_id

OPERATIONS:
-----------
Sites: create, get, get_all, get_active, update, delete
Products: create, get, get_all, get_by_site, update, delete, search
Statistics: get_products_stats

ERROR HANDLING:
--------------
- Tất cả operations đều có try/catch với logging
- Connection management với context managers
- Foreign key constraints được enforce
"""

import sqlite3
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
import os

from app.models import Site, Product

class DatabaseManager:
    """Quản lý cơ sở dữ liệu SQLite"""

    def __init__(self, db_path: str = "woocommerce_manager.db"):
        self.db_path = db_path
        # Initialize logger with safe configuration
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)

        # Prevent recursion by limiting handlers
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter('%(levelname)s - %(message)s'))
            self.logger.addHandler(handler)

        self.logger.propagate = False

    def get_connection(self) -> sqlite3.Connection:
        """Lấy kết nối database với timeout và retry"""
        import time
        max_retries = 3
        retry_delay = 0.1

        for attempt in range(max_retries):
            try:
                conn = sqlite3.connect(self.db_path, timeout=30.0)  # 30 second timeout
                conn.row_factory = sqlite3.Row
                # Enable WAL mode for better concurrency
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("PRAGMA synchronous=NORMAL")
                conn.execute("PRAGMA cache_size=10000")
                conn.execute("PRAGMA temp_store=MEMORY")
                return conn
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e) and attempt < max_retries - 1:
                    time.sleep(retry_delay * (attempt + 1))
                    continue
                else:
                    raise e

    def init_database(self):
        """Khởi tạo database và các bảng"""
        try:
            # Tạo thư mục chứa database nếu chưa có
            db_dir = os.path.dirname(self.db_path)
            if db_dir and not os.path.exists(db_dir):
                os.makedirs(db_dir, exist_ok=True)

            # Kiểm tra quyền ghi file
            try:
                test_conn = sqlite3.connect(self.db_path)
                test_conn.close()
            except Exception as e:
                self.logger.error(f"Cannot create database file: {e}")
                # Thử tạo trong thư mục temp
                import tempfile
                self.db_path = os.path.join(tempfile.gettempdir(), "woocommerce_manager.db")
                self.logger.info(f"Using temporary database: {self.db_path}")

            with self.get_connection() as conn:
                # Tạo bảng sites
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS sites (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        url TEXT NOT NULL,
                        consumer_key TEXT NOT NULL,
                        consumer_secret TEXT NOT NULL,
                        wp_username TEXT,
                        wp_app_password TEXT,
                        is_active BOOLEAN DEFAULT 1,
                        notes TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # Tạo bảng products
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS products (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        site_id INTEGER NOT NULL,
                        wc_product_id INTEGER,
                        name TEXT,
                        sku TEXT,
                        price REAL,
                        regular_price REAL,
                        sale_price REAL,
                        stock_quantity INTEGER,
                        status TEXT,
                        description TEXT,
                        short_description TEXT,
                        categories TEXT,
                        tags TEXT,
                        images TEXT,
                        view_count INTEGER DEFAULT 0,
                        order_count INTEGER DEFAULT 0,
                        last_sync TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (site_id) REFERENCES sites (id) ON DELETE CASCADE
                    )
                """)

                # Create categories table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS categories (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        site_id INTEGER NOT NULL,
                        wc_category_id INTEGER,
                        name TEXT NOT NULL,
                        slug TEXT,
                        parent_id INTEGER,
                        description TEXT,
                        count INTEGER,
                        image TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (site_id) REFERENCES sites (id) ON DELETE CASCADE
                    )
                """)

                # Create pages table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS pages (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        site_id INTEGER NOT NULL,
                        wp_page_id INTEGER,
                        title TEXT,
                        content TEXT,
                        excerpt TEXT,
                        status TEXT,
                        slug TEXT,
                        parent_id INTEGER,
                        menu_order INTEGER,
                        featured_media INTEGER,
                        author INTEGER,
                        last_sync TIMESTAMP,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (site_id) REFERENCES sites (id) ON DELETE CASCADE
                    )
                """)

                # Create folder_scans table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS folder_scans (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        original_title TEXT NOT NULL,
                        path TEXT NOT NULL UNIQUE,
                        image_count INTEGER DEFAULT 0,
                        description TEXT,
                        status TEXT DEFAULT 'pending',
                        new_title TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # Create saved_scans table for managing scan results
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS saved_scans (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL UNIQUE,
                        description TEXT,
                        folder_count INTEGER DEFAULT 0,
                        data TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # Thêm cột mới nếu chưa có
                try:
                    conn.execute("ALTER TABLE folder_scans ADD COLUMN data_name TEXT")
                except Exception:
                    pass  # Cột đã tồn tại

                try:
                    conn.execute("ALTER TABLE folder_scans ADD COLUMN category_id INTEGER")
                except Exception:
                    pass  # Cột đã tồn tại

                try:
                    conn.execute("ALTER TABLE folder_scans ADD COLUMN site_id INTEGER")
                except Exception:
                    pass  # Cột đã tồn tại

                # Thêm cột wc_product_id vào bảng folder_scans nếu chưa có
                try:
                    conn.execute("ALTER TABLE folder_scans ADD COLUMN wc_product_id INTEGER")
                except Exception:
                    pass  # Cột đã tồn tại

                # Thêm các cột upload status
                try:
                    conn.execute("ALTER TABLE folder_scans ADD COLUMN uploaded_at TEXT")
                except Exception:
                    pass  # Cột đã tồn tại

                try:
                    conn.execute("ALTER TABLE folder_scans ADD COLUMN upload_success BOOLEAN DEFAULT 0")
                except Exception:
                    pass  # Cột đã tồn tại

                try:
                    conn.execute("ALTER TABLE folder_scans ADD COLUMN error_message TEXT")
                except Exception:
                    pass  # Cột đã tồn tại

                try:
                    conn.execute("ALTER TABLE folder_scans ADD COLUMN product_url TEXT")
                except Exception:
                    pass  # Cột đã tồn tại

                # Tạo indexes (sau khi đã thêm cột)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_products_site_id ON products (site_id)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_products_sku ON products (sku)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_products_wc_id ON products (wc_product_id)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_folder_scans_path ON folder_scans (path)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_folder_scans_status ON folder_scans (status)")

                # Kiểm tra xem cột data_name có tồn tại trước khi tạo index
                try:
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_folder_scans_data_name ON folder_scans (data_name)")
                except Exception:
                    pass  # Cột chưa tồn tại hoặc index đã có

                try:
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_folder_scans_category ON folder_scans (category_id)")
                except Exception:
                    pass  # Cột chưa tồn tại hoặc index đã có

                try:
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_folder_scans_site ON folder_scans (site_id)")
                except Exception:
                    pass  # Cột chưa tồn tại hoặc index đã có

                # Thêm cột wp_username và wp_app_password nếu chưa có
                try:
                    conn.execute("ALTER TABLE sites ADD COLUMN wp_username TEXT")
                except Exception:
                    pass  # Cột đã tồn tại

                try:
                    conn.execute("ALTER TABLE sites ADD COLUMN wp_app_password TEXT")
                except Exception:
                    pass  # Cột đã tồn tại

                # Cập nhật indexes cho hiệu suất
                try:
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_sites_active ON sites(is_active)")
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_products_site ON products(site_id)")
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_categories_site ON categories(site_id)")
                except Exception:
                    pass

                conn.commit()
                self.logger.info("Database initialized successfully")

        except Exception as e:
            self.logger.error(f"Database initialization failed: {str(e)}")
            # Thử tạo database đơn giản hơn
            try:
                self.create_minimal_database()
                self.logger.info("Created minimal database successfully")
            except Exception as fallback_error:
                self.logger.error(f"Fallback database creation failed: {fallback_error}")
                raise e

    def create_minimal_database(self):
        """Tạo database tối thiểu với các bảng cơ bản"""
        with self.get_connection() as conn:
            # Chỉ tạo bảng sites cơ bản
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sites (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    url TEXT NOT NULL,
                    consumer_key TEXT NOT NULL,
                    consumer_secret TEXT NOT NULL,
                    is_active BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Chỉ tạo bảng products cơ bản
            conn.execute("""
                CREATE TABLE IF NOT EXISTS products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    site_id INTEGER NOT NULL,
                    name TEXT,
                    status TEXT DEFAULT 'draft',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (site_id) REFERENCES sites (id)
                )
            """)

            conn.commit()

    # Site operations
    def create_site(self, site_data: Dict[str, Any]) -> int:
        """Tạo site mới"""
        try:
            with self.get_connection() as conn:
                cursor = conn.execute("""
                    INSERT INTO sites (name, url, consumer_key, consumer_secret, wp_username, wp_app_password, is_active, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    site_data['name'],
                    site_data['url'],
                    site_data['consumer_key'],
                    site_data['consumer_secret'],
                    site_data.get('wp_username', ''),
                    site_data.get('wp_app_password', ''),
                    site_data.get('is_active', True),
                    site_data.get('notes', '')
                ))
                conn.commit()
                return cursor.lastrowid

        except Exception as e:
            self.logger.error(f"Error creating site: {str(e)}")
            raise

    def get_site(self, site_id: int) -> Optional[Site]:
        """Lấy thông tin site theo ID"""
        try:
            with self.get_connection() as conn:
                cursor = conn.execute("SELECT * FROM sites WHERE id = ?", (site_id,))
                row = cursor.fetchone()
                if row:
                    return Site.from_dict(dict(row))
                return None

        except Exception as e:
            self.logger.error(f"Error getting site {site_id}: {str(e)}")
            return None

    def get_site_by_id(self, site_id: int) -> Optional[Site]:
        """Alias cho get_site để tương thích"""
        return self.get_site(site_id)

    def get_all_sites(self) -> List[Site]:
        """Lấy tất cả sites"""
        try:
            with self.get_connection() as conn:
                cursor = conn.execute("SELECT * FROM sites ORDER BY name")
                rows = cursor.fetchall()
                return [Site.from_dict(dict(row)) for row in rows]

        except Exception as e:
            self.logger.error(f"Error getting all sites: {str(e)}")
            return []

    def get_active_sites(self) -> List[Site]:
        """Lấy các sites đang hoạt động"""
        try:
            with self.get_connection() as conn:
                cursor = conn.execute("SELECT * FROM sites WHERE is_active = 1 ORDER BY name")
                rows = cursor.fetchall()
                return [Site.from_dict(dict(row)) for row in rows]

        except Exception as e:
            self.logger.error(f"Error getting active sites: {str(e)}")
            return []

    def update_site(self, site_id: int, site_data: Dict[str, Any]):
        """Cập nhật thông tin site"""
        try:
            with self.get_connection() as conn:
                conn.execute("""
                    UPDATE sites 
                    SET name = ?, url = ?, consumer_key = ?, consumer_secret = ?, 
                        wp_username = ?, wp_app_password = ?, is_active = ?, notes = ?, 
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (
                    site_data['name'],
                    site_data['url'],
                    site_data['consumer_key'],
                    site_data['consumer_secret'],
                    site_data.get('wp_username', ''),
                    site_data.get('wp_app_password', ''),
                    site_data.get('is_active', True),
                    site_data.get('notes', ''),
                    site_id
                ))
                conn.commit()

        except Exception as e:
            self.logger.error(f"Error updating site {site_id}: {str(e)}")
            raise

    def delete_site(self, site_id: int):
        """Xóa site"""
        try:
            with self.get_connection() as conn:
                # Xóa tất cả sản phẩm của site trước
                conn.execute("DELETE FROM products WHERE site_id = ?", (site_id,))
                # Xóa site
                conn.execute("DELETE FROM sites WHERE id = ?", (site_id,))
                conn.commit()

        except Exception as e:
            self.logger.error(f"Error deleting site {site_id}: {str(e)}")
            raise

    # Product operations
    def create_product(self, product_data: Dict[str, Any]) -> int:
        """Tạo sản phẩm mới"""
        try:
            with self.get_connection() as conn:
                cursor = conn.execute("""
                    INSERT INTO products (
                        site_id, wc_product_id, name, sku, price, regular_price, sale_price,
                        stock_quantity, status, description, short_description,
                        categories, tags, images, last_sync
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    product_data['site_id'],
                    product_data.get('wc_product_id'),
                    product_data.get('name'),
                    product_data.get('sku'),
                    product_data.get('price'),
                    product_data.get('regular_price'),
                    product_data.get('sale_price'),
                    product_data.get('stock_quantity'),
                    product_data.get('status'),
                    product_data.get('description'),
                    product_data.get('short_description'),
                    product_data.get('categories'),
                    product_data.get('tags'),
                    product_data.get('images'),
                    product_data.get('last_sync')
                ))
                conn.commit()
                return cursor.lastrowid

        except Exception as e:
            self.logger.error(f"Error creating product: {str(e)}")
            raise

    def get_product(self, product_id: int) -> Optional[Product]:
        """Lấy thông tin sản phẩm theo ID"""
        try:
            with self.get_connection() as conn:
                cursor = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,))
                row = cursor.fetchone()
                if row:
                    return Product.from_dict(dict(row))
                return None

        except Exception as e:
            self.logger.error(f"Error getting product {product_id}: {str(e)}")
            return None

    def get_product_by_site_and_wc_id(self, site_id: int, wc_product_id: int) -> Optional[Product]:
        """Lấy sản phẩm theo site_id và wc_product_id"""
        try:
            with self.get_connection() as conn:
                cursor = conn.execute(
                    "SELECT * FROM products WHERE site_id = ? AND wc_product_id = ?", 
                    (site_id, wc_product_id)
                )
                row = cursor.fetchone()
                if row:
                    return Product.from_dict(dict(row))
                return None

        except Exception as e:
            self.logger.error(f"Error getting product by site and wc id: {str(e)}")
            return None

    def get_all_products(self) -> List[Product]:
        """Lấy tất cả sản phẩm"""
        try:
            with self.get_connection() as conn:
                cursor = conn.execute("SELECT * FROM products ORDER BY name")
                rows = cursor.fetchall()
                return [Product.from_dict(dict(row)) for row in rows]

        except Exception as e:
            self.logger.error(f"Error getting all products: {str(e)}")
            return []

    def get_products_by_site(self, site_id: int) -> List[Product]:
        """Lấy sản phẩm theo site"""
        try:
            with self.get_connection() as conn:
                cursor = conn.execute(
                    "SELECT * FROM products WHERE site_id = ? ORDER BY name", 
                    (site_id,)
                )
                rows = cursor.fetchall()
                return [Product.from_dict(dict(row)) for row in rows]

        except Exception as e:
            self.logger.error(f"Error getting products by site {site_id}: {str(e)}")
            return []

    def update_product(self, product_id: int, product_data: Dict[str, Any]):
        """Cập nhật thông tin sản phẩm với retry logic"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                with self.get_connection() as conn:
                    conn.execute("BEGIN IMMEDIATE")
                    conn.execute("""
                        UPDATE products 
                        SET site_id = ?, wc_product_id = ?, name = ?, sku = ?, 
                            price = ?, regular_price = ?, sale_price = ?,
                            stock_quantity = ?, status = ?, description = ?, 
                            short_description = ?, categories = ?, tags = ?, 
                            images = ?, last_sync = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    """, (
                        product_data['site_id'],
                        product_data.get('wc_product_id'),
                        product_data.get('name'),
                        product_data.get('sku'),
                        product_data.get('price'),
                        product_data.get('regular_price'),
                        product_data.get('sale_price'),
                        product_data.get('stock_quantity'),
                        product_data.get('status'),
                        product_data.get('description'),
                        product_data.get('short_description'),
                        product_data.get('categories'),
                        product_data.get('tags'),
                        product_data.get('images'),
                        product_data.get('last_sync'),
                        product_id
                    ))
                    conn.commit()
                    return  # Success, exit function

            except sqlite3.OperationalError as e:
                if "database is locked" in str(e) and attempt < max_retries - 1:
                    import time
                    time.sleep(0.1 * (attempt + 1))
                    continue
                else:
                    self.logger.error(f"Error updating product {product_id}: {str(e)}")
                    raise
            except Exception as e:
                self.logger.error(f"Error updating product {product_id}: {str(e)}")
                raise

    def delete_product(self, product_id: int) -> bool:
        """Xóa sản phẩm"""
        try:
            with self.get_connection() as conn:
                cursor = conn.execute("DELETE FROM products WHERE id = ?", (product_id,))
                conn.commit()
                return cursor.rowcount > 0

        except Exception as e:
            self.logger.error(f"Error deleting product {product_id}: {str(e)}")
            return False

    def search_products(self, search_term: str) -> List[Product]:
        """Tìm kiếm sản phẩm"""
        try:
            with self.get_connection() as conn:
                search_pattern = f"%{search_term}%"
                cursor = conn.execute("""
                    SELECT * FROM products 
                    WHERE name LIKE ? OR sku LIKE ? OR description LIKE ?
                    ORDER BY name
                """, (search_pattern, search_pattern, search_pattern))
                rows = cursor.fetchall()
                return [Product.from_dict(dict(row)) for row in rows]

        except Exception as e:
            self.logger.error(f"Error searching products: {str(e)}")
            return []

    def get_products_stats(self) -> Dict[str, Any]:
        """Lấy thống kê sản phẩm"""
        try:
            with self.get_connection() as conn:
                # Tổng số sản phẩm
                cursor = conn.execute("SELECT COUNT(*) as total FROM products")
                total = cursor.fetchone()['total']

                # Sản phẩm theo trạng thái
                cursor = conn.execute("""
                    SELECT status, COUNT(*) as count 
                    FROM products 
                    GROUP BY status
                """)
                status_stats = {row['status']: row['count'] for row in cursor.fetchall()}

                # Sản phẩm theo site
                cursor = conn.execute("""
                    SELECT s.name, COUNT(p.id) as count
                    FROM sites s
                    LEFT JOIN products p ON s.id = p.site_id
                    GROUP BY s.id, s.name
                """)
                site_stats = {row['name']: row['count'] for row in cursor.fetchall()}

                return {
                    'total_products': total,
                    'by_status': status_stats,
                    'by_site': site_stats
                }

        except Exception as e:
            self.logger.error(f"Error getting product stats: {str(e)}")
            return {}

    # Category operations
    def create_category(self, category_data: Dict[str, Any]) -> int:
        """Tạo category mới"""
        try:
            with self.get_connection() as conn:
                cursor = conn.execute("""
                    INSERT INTO categories (
                        site_id, wc_category_id, name, slug, parent_id,
                        description, count, image
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    category_data['site_id'],
                    category_data.get('wc_category_id'),
                    category_data['name'],
                    category_data.get('slug', ''),
                    category_data.get('parent_id', 0),
                    category_data.get('description', ''),
                    category_data.get('count', 0),
                    category_data.get('image', '')
                ))
                conn.commit()
                return cursor.lastrowid

        except Exception as e:
            self.logger.error(f"Error creating category: {str(e)}")
            raise

    def get_category_by_id(self, category_id: int) -> Optional[Dict]:
        """Lấy thông tin category theo ID"""
        try:
            with self.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT c.*, s.name as site_name 
                    FROM categories c
                    LEFT JOIN sites s ON c.site_id = s.id
                    WHERE c.id = ?
                """, (category_id,))

                row = cursor.fetchone()
                if row:
                    return dict(row)
                return None

        except Exception as e:
            self.logger.error(f"Error getting category by ID {category_id}: {str(e)}")
            return None

    def get_category_by_wc_id(self, site_id: int, wc_category_id: int) -> Optional[Dict]:
        """Lấy thông tin category theo WooCommerce ID và site ID"""
        try:
            with self.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT c.*, s.name as site_name 
                    FROM categories c
                    LEFT JOIN sites s ON c.site_id = s.id
                    WHERE c.site_id = ? AND c.wc_category_id = ?
                """, (site_id, wc_category_id))

                row = cursor.fetchone()
                if row:
                    return dict(row)
                return None

        except Exception as e:
            self.logger.error(f"Error getting category by WC ID {wc_category_id} for site {site_id}: {str(e)}")
            return None

    def find_category_by_name_or_slug(self, site_id: int, name: str = None, slug: str = None) -> Optional[Dict]:
        """Tìm category theo tên hoặc slug trong site"""
        try:
            with self.get_connection() as conn:
                if name and slug:
                    # Tìm theo cả tên và slug
                    cursor = conn.execute("""
                        SELECT c.*, s.name as site_name 
                        FROM categories c
                        LEFT JOIN sites s ON c.site_id = s.id
                        WHERE c.site_id = ? AND (LOWER(c.name) = ? OR LOWER(c.slug) = ?)
                        ORDER BY 
                            CASE WHEN LOWER(c.name) = ? THEN 1 ELSE 2 END,
                            c.id DESC
                        LIMIT 1
                    """, (site_id, name.lower(), slug.lower(), name.lower()))
                elif name:
                    # Chỉ tìm theo tên
                    cursor = conn.execute("""
                        SELECT c.*, s.name as site_name 
                        FROM categories c
                        LEFT JOIN sites s ON c.site_id = s.id
                        WHERE c.site_id = ? AND LOWER(c.name) = ?
                        ORDER BY c.id DESC
                        LIMIT 1
                    """, (site_id, name.lower()))
                elif slug:
                    # Chỉ tìm theo slug
                    cursor = conn.execute("""
                        SELECT c.*, s.name as site_name 
                        FROM categories c
                        LEFT JOIN sites s ON c.site_id = s.id
                        WHERE c.site_id = ? AND LOWER(c.slug) = ?
                        ORDER BY c.id DESC
                        LIMIT 1
                    """, (site_id, slug.lower()))
                else:
                    return None

                row = cursor.fetchone()
                if row:
                    return dict(row)
                return None

        except Exception as e:
            self.logger.error(f"Error finding category by name/slug for site {site_id}: {str(e)}")
            return None

    def get_all_categories(self) -> List[Dict[str, Any]]:
        """Lấy tất cả categories"""
        try:
            with self.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT c.*, s.name as site_name 
                    FROM categories c
                    LEFT JOIN sites s ON c.site_id = s.id
                    ORDER BY c.name
                """)
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            self.logger.error(f"Error getting all categories: {str(e)}")
            return []

    def get_categories_by_site(self, site_id: int) -> List[Dict[str, Any]]:
        """Lấy categories theo site"""
        try:
            with self.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT c.*, s.name as site_name 
                    FROM categories c
                    LEFT JOIN sites s ON c.site_id = s.id
                    WHERE c.site_id = ?
                    ORDER BY 
                        CASE WHEN c.parent_id IS NULL OR c.parent_id = 0 THEN 0 ELSE 1 END,
                        c.name
                """, (site_id,))
                rows = cursor.fetchall()
                categories = [dict(row) for row in rows]

                self.logger.debug(f"Found {len(categories)} categories for site {site_id}")
                return categories

        except Exception as e:
            self.logger.error(f"Error getting categories by site {site_id}: {str(e)}")
            return []

    def update_category(self, category_id: int, category_data: Dict[str, Any]):
        """Cập nhật category"""
        try:
            with self.get_connection() as conn:
                # Tạo câu UPDATE động từ category_data, bỏ qua các cột không tồn tại
                set_clauses = []
                values = []

                # Danh sách các cột hợp lệ trong bảng categories
                valid_columns = {
                    'site_id', 'wc_category_id', 'name', 'slug', 'parent_id', 
                    'description', 'count', 'image'
                }

                for key, value in category_data.items():
                    if key != 'id' and key in valid_columns:  # Chỉ update các cột hợp lệ
                        set_clauses.append(f"{key} = ?")
                        values.append(value)

                if set_clauses:
                    set_clauses.append("updated_at = CURRENT_TIMESTAMP")
                    values.append(category_id)

                    query = f"UPDATE categories SET {', '.join(set_clauses)} WHERE id = ?"
                    conn.execute(query, values)
                    conn.commit()

        except Exception as e:
            self.logger.error(f"Error updating category {category_id}: {str(e)}")
            raise

    def get_category_by_id(self, category_id: int) -> Optional[Dict[str, Any]]:
        """Lấy category theo ID"""
        try:
            with self.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT id, site_id, wc_category_id, name, slug, parent_id, 
                           description, count, image, created_at, updated_at
                    FROM categories WHERE id = ?
                """, (category_id,))

                row = cursor.fetchone()
                if row:
                    return {
                        'id': row[0],
                        'site_id': row[1],
                        'wc_category_id': row[2],
                        'name': row[3],
                        'slug': row[4],
                        'parent_id': row[5],
                        'description': row[6],
                        'count': row[7],
                        'image': row[8],
                        'created_at': row[9],
                        'updated_at': row[10]
                    }
                return None

        except Exception as e:
            self.logger.error(f"Error getting category {category_id}: {str(e)}")
            return None

    def delete_category(self, category_id: int):
        """Xóa category"""
        try:
            with self.get_connection() as conn:
                conn.execute("DELETE FROM categories WHERE id = ?", (category_id,))
                conn.commit()

        except Exception as e:
            self.logger.error(f"Error deleting category {category_id}: {str(e)}")
            raise



    def update_saved_scan(self, scan_id: int, scan_data: Dict[str, Any]) -> bool:
        """Cập nhật saved scan"""
        try:
            with self.get_connection() as conn:
                # Tạo câu UPDATE động từ scan_data
                set_clauses = []
                values = []

                valid_columns = {'name', 'description', 'folder_count', 'data', 'updated_at'}

                for key, value in scan_data.items():
                    if key in valid_columns:
                        set_clauses.append(f"{key} = ?")
                        values.append(value)

                if set_clauses:
                    values.append(scan_id)
                    query = f"UPDATE saved_scans SET {', '.join(set_clauses)} WHERE id = ?"

                    cursor = conn.execute(query, values)
                    conn.commit()

                    if cursor.rowcount > 0:
                        self.logger.info(f"Updated saved scan {scan_id}")
                        return True
                    else:
                        self.logger.warning(f"No saved scan found with id {scan_id}")
                        return False
                else:
                    self.logger.warning(f"No valid columns to update for saved scan {scan_id}")
                    return False

        except Exception as e:
            self.logger.error(f"Error updating saved scan {scan_id}: {str(e)}")
            return False


    def remove_duplicate_categories(self):
        """Xóa các categories bị duplicate"""
        try:
            with self.get_connection() as conn:
                # Xóa categories trùng lặp, giữ lại record có id nhỏ nhất
                conn.execute("""
                    DELETE FROM categories 
                    WHERE id NOT IN (
                        SELECT MIN(id) 
                        FROM categories 
                        GROUP BY site_id, wc_category_id, name
                    )
                """)

                deleted_count = conn.total_changes
                conn.commit()

                self.logger.info(f"Removed {deleted_count} duplicate categories")
                return deleted_count

        except Exception as e:
            self.logger.error(f"Error removing duplicate categories: {str(e)}")
            raise

    def save_categories_from_api(self, site_id: int, categories_data: List[Dict]):
        """Lưu categories từ API vào database"""
        try:
            with self.get_connection() as conn:
                # Xóa categories cũ của site này trước
                conn.execute("DELETE FROM categories WHERE site_id = ?", (site_id,))

                # Thêm categories mới với INSERT OR IGNORE để tránh duplicate
                for category in categories_data:
                    wc_category_id = category.get('id')

                    # Kiểm tra xem category đã tồn tại chưa
                    existing = conn.execute("""
                        SELECT id FROM categories 
                        WHERE site_id = ? AND wc_category_id = ?
                    """, (site_id, wc_category_id)).fetchone()

                    if not existing:
                        conn.execute("""
                            INSERT INTO categories (
                                site_id, wc_category_id, name, slug, parent_id,
                                description, count, image, updated_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                        """, (
                            site_id,
                            wc_category_id,
                            category.get('name', ''),
                            category.get('slug', ''),
                            category.get('parent', 0),
                            category.get('description', ''),
                            category.get('count', 0),
                            category.get('image', {}).get('src', '') if category.get('image') else ''
                        ))
                    else:
                        # Cập nhật nếu đã tồn tại
                        conn.execute("""
                            UPDATE categories SET
                                name = ?, slug = ?, parent_id = ?, description = ?,
                                count = ?, image = ?, updated_at = CURRENT_TIMESTAMP
                            WHERE site_id = ? AND wc_category_id = ?
                        """, (
                            category.get('name', ''),
                            category.get('slug', ''),
                            category.get('parent', 0),
                            category.get('description', ''),
                            category.get('count', 0),
                            category.get('image', {}).get('src', '') if category.get('image') else '',
                            site_id,
                            wc_category_id
                        ))

                conn.commit()
                self.logger.info(f"Saved {len(categories_data)} categories for site {site_id}")

        except Exception as e:
            self.logger.error(f"Error saving categories from API: {str(e)}")
            raise

    def fix_category_mapping_for_folder_scan(self, folder_id: int, correct_category_name: str) -> bool:
        """Fix category mapping cho folder scan dựa vào tên category"""
        try:
            with self.get_connection() as conn:
                # Lấy thông tin folder scan
                folder_scan = self.get_folder_scan_by_id(folder_id)
                if not folder_scan:
                    return False

                site_id = folder_scan.get('site_id')
                if not site_id:
                    return False

                # Tìm category với tên đúng trong site
                cursor = conn.execute("""
                    SELECT id, wc_category_id FROM categories 
                    WHERE site_id = ? AND name = ?
                """, (site_id, correct_category_name))

                correct_category = cursor.fetchone()
                if not correct_category:
                    self.logger.warning(f"Không tìm thấy category '{correct_category_name}' trong site {site_id}")
                    return False

                # Cập nhật folder scan với category ID đúng
                conn.execute("""
                    UPDATE folder_scans 
                    SET category_id = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (correct_category['id'], folder_id))

                conn.commit()
                self.logger.info(f"Fixed category mapping for folder {folder_id} to '{correct_category_name}'")
                return True

        except Exception as e:
            self.logger.error(f"Error fixing category mapping: {str(e)}")
            return False

    # Page operations
    def get_all_pages(self) -> List[Dict[str, Any]]:
        """Lấy tất cả pages"""
        try:
            with self.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT p.*, s.name as site_name 
                    FROM pages p 
                    LEFT JOIN sites s ON p.site_id = s.id 
                    ORDER BY p.updated_at DESC
                """)
                rows = cursor.fetchall()
                return [dict(row) for row in rows]

        except Exception as e:
            self.logger.error(f"Error getting all pages: {str(e)}")
            return []

    def get_pages_by_site(self, site_id: int) -> List[Dict[str, Any]]:
        """Lấy pages theo site"""
        try:
            with self.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT p.*, s.name as site_name 
                    FROM pages p 
                    LEFT JOIN sites s ON p.site_id = s.id 
                    WHERE p.site_id = ?
                    ORDER BY p.updated_at DESC
                """, (site_id,))
                rows = cursor.fetchall()
                return [dict(row) for row in rows]

        except Exception as e:
            self.logger.error(f"Error getting pages by site {site_id}: {str(e)}")
            return []

    def create_page(self, page_data: Dict[str, Any]) -> int:
        """Tạo page mới"""
        try:
            with self.get_connection() as conn:
                cursor = conn.execute("""
                    INSERT INTO pages (
                        site_id, wp_page_id, title, slug, content, excerpt, status,
                        parent_id, menu_order, featured_media, author, last_sync
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    page_data['site_id'],
                    page_data.get('wp_page_id'),
                    page_data.get('title', ''),
                    page_data.get('slug', ''),
                    page_data.get('content', ''),
                    page_data.get('excerpt', ''),
                    page_data.get('status', 'draft'),
                    page_data.get('parent_id', 0),
                    page_data.get('menu_order', 0),
                    page_data.get('featured_media', 0),
                    page_data.get('author', 0),
                    datetime.now().isoformat()
                ))
                conn.commit()
                return cursor.lastrowid

        except Exception as e:
            self.logger.error(f"Error creating page: {str(e)}")
            raise

    def update_page(self, page_id: int, page_data: Dict[str, Any]) -> bool:
        """Cập nhật page"""
        try:
            with self.get_connection() as conn:
                conn.execute("""
                    UPDATE pages 
                    SET title = ?, slug = ?, content = ?, excerpt = ?, status = ?,
                        parent_id = ?, menu_order = ?, featured_media = ?, author = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (
                    page_data.get('title', ''),
                    page_data.get('slug', ''),
                    page_data.get('content', ''),
                    page_data.get('excerpt', ''),
                    page_data.get('status', 'draft'),
                    page_data.get('parent_id', 0),
                    page_data.get('menu_order', 0),
                    page_data.get('featured_media', 0),
                    page_data.get('author', 0),
                    page_id
                ))
                conn.commit()
                return True

        except Exception as e:
            self.logger.error(f"Error updating page {page_id}: {str(e)}")
            return False

    def delete_page(self, page_id: int) -> bool:
        """Xóa page"""
        try:
            with self.get_connection() as conn:
                cursor = conn.execute("DELETE FROM pages WHERE id = ?", (page_id,))
                conn.commit()
                return cursor.rowcount > 0

        except Exception as e:
            self.logger.error(f"Error deleting page {page_id}: {str(e)}")
            return False

    # Folder scan operations
    def get_all_folder_scans(self) -> List[Dict[str, Any]]:
        """Lấy tất cả folder scans với thông tin site và category"""
        try:
            with self.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT 
                        fs.*,
                        s.name as site_name,
                        c.name as category_name
                    FROM folder_scans fs
                    LEFT JOIN sites s ON fs.site_id = s.id
                    LEFT JOIN categories c ON fs.category_id = c.id
                    ORDER BY fs.created_at DESC
                """)

                columns = [description[0] for description in cursor.description]
                rows = cursor.fetchall()
                return [dict(zip(columns, row)) for row in rows]

        except Exception as e:
            self.logger.error(f"Error getting all folder scans: {str(e)}")
            return []

    def get_folder_scan_by_id(self, folder_id: int) -> Optional[Dict[str, Any]]:
        """Lấy folder scan theo ID"""
        try:
            with self.get_connection() as conn:
                cursor = conn.execute("SELECT * FROM folder_scans WHERE id = ?", (folder_id,))
                row = cursor.fetchone()
                return dict(row) if row else None

        except Exception as e:
            self.logger.error(f"Error getting folder scan {folder_id}: {str(e)}")
            return None

    def update_folder_scan(self, folder_id: int, update_data: Dict[str, Any]) -> bool:
        """Cập nhật folder scan với improved error handling và transaction isolation"""
        try:
            if not folder_id or not update_data:
                self.logger.warning(f"Invalid input: folder_id={folder_id}, update_data={bool(update_data)}")
                return False

            # Use separate connection for this update to avoid conflicts
            max_retries = 3
            retry_delay = 0.1

            for attempt in range(max_retries):
                try:
                    conn = self.get_connection()

                    # Begin immediate transaction to lock the row
                    conn.execute("BEGIN IMMEDIATE")

                    # Kiểm tra folder có tồn tại không
                    check_cursor = conn.execute("SELECT id, status FROM folder_scans WHERE id = ?", (folder_id,))
                    existing_folder = check_cursor.fetchone()

                    if not existing_folder:
                        self.logger.error(f"Folder scan {folder_id} not found in database")
                        conn.rollback()
                        conn.close()
                        return False

                    current_status = existing_folder[1] if existing_folder else None
                    self.logger.info(f"🔍 Folder {folder_id} current status: {current_status}")

                    # Lấy danh sách cột có sẵn trong bảng folder_scans  
                    cursor = conn.execute("PRAGMA table_info(folder_scans)")
                    available_columns = {row[1] for row in cursor.fetchall()}

                    # Tạo câu UPDATE động từ update_data, chỉ với các cột tồn tại
                    set_clauses = []
                    values = []
                    skipped_columns = []

                    for key, value in update_data.items():
                        if key != 'id':
                            if key in available_columns:
                                set_clauses.append(f"{key} = ?")
                                values.append(value)
                            else:
                                skipped_columns.append(key)

                    if skipped_columns:
                        self.logger.debug(f"Skipped non-existent columns for folder {folder_id}: {skipped_columns}")

                    if set_clauses:
                        set_clauses.append("updated_at = CURRENT_TIMESTAMP")
                        values.append(folder_id)

                        query = f"UPDATE folder_scans SET {', '.join(set_clauses)} WHERE id = ?"
                        self.logger.info(f"🔄 Executing update query for folder {folder_id}: {query[:100]}...")
                        self.logger.info(f"📝 Update values: {values}")

                        cursor = conn.execute(query, values)
                        rows_affected = cursor.rowcount

                        # Verify the update before committing
                        verify_cursor = conn.execute("SELECT status, wc_product_id FROM folder_scans WHERE id = ?", (folder_id,))
                        verify_result = verify_cursor.fetchone()

                        if verify_result:
                            new_status = verify_result[0]
                            new_product_id = verify_result[1]
                            self.logger.info(f"🔍 Folder {folder_id} new status: {new_status}, product_id: {new_product_id}")

                        if rows_affected > 0:
                            conn.commit()
                            conn.close()
                            self.logger.info(f"✅ Successfully updated {rows_affected} row(s) for folder {folder_id}")
                            return True
                        else:
                            conn.rollback()
                            conn.close()
                            self.logger.warning(f"⚠️ No rows affected when updating folder {folder_id}")
                            return False
                    else:
                        conn.rollback()
                        conn.close()
                        self.logger.warning(f"⚠️ No valid columns to update for folder {folder_id}")
                        return False

                except Exception as e:
                    try:
                        conn.rollback()
                        conn.close()
                    except:
                        pass

                    if "database is locked" in str(e) and attempt < max_retries - 1:
                        import time
                        time.sleep(retry_delay * (attempt + 1))
                        self.logger.warning(f"⚠️ Database locked, retrying attempt {attempt + 2}/{max_retries} for folder {folder_id}")
                        continue
                    else:
                        self.logger.error(f"❌ Error updating folder scan {folder_id} on attempt {attempt + 1}: {str(e)}")
                        if attempt == max_retries - 1:
                            import traceback
                            self.logger.error(f"❌ Final attempt failed. Traceback: {traceback.format_exc()}")
                        continue

            return False

        except Exception as e:
            self.logger.error(f"❌ Critical error updating folder scan {folder_id}: {str(e)}")
            import traceback
            self.logger.error(f"❌ Traceback: {traceback.format_exc()}")
            return False

    def bulk_update_folder_scans(self, folder_ids: List[int], update_data: Dict[str, Any]) -> int:
        """Cập nhật hàng loạt folder scans"""
        try:
            updated_count = 0
            with self.get_connection() as conn:
                # Tạo câu UPDATE động từ update_data
                set_clauses = []
                values = []

                for key, value in update_data.items():
                    if key != 'id':  # Không update id
                        set_clauses.append(f"{key} = ?")
                        values.append(value)

                if set_clauses:
                    set_clauses.append("updated_at = CURRENT_TIMESTAMP")

                    # Tạo placeholders cho folder_ids
                    placeholders = ', '.join(['?'] * len(folder_ids))
                    query = f"UPDATE folder_scans SET {', '.join(set_clauses)} WHERE id IN ({placeholders})"

                    # Kết hợp values với folder_ids
                    all_values = values + folder_ids

                    cursor = conn.execute(query, all_values)
                    updated_count = cursor.rowcount
                    conn.commit()

            self.logger.info(f"Bulk updated {updated_count} folder scans")
            return updated_count

        except Exception as e:
            self.logger.error(f"Error bulk updating folder scans: {str(e)}")
            return 0

    def create_saved_scan(self, scan_data: Dict[str, Any]) -> int:
        """Tạo saved scan mới"""
        try:
            with self.get_connection() as conn:
                cursor = conn.execute("""
                    INSERT INTO saved_scans (name, description, folder_count, data)
                    VALUES (?, ?, ?, ?)
                """, (
                    scan_data['name'],
                    scan_data.get('description', ''),
                    scan_data.get('folder_count', 0),
                    scan_data.get('data', '')
                ))
                conn.commit()
                return cursor.lastrowid

        except Exception as e:
            self.logger.error(f"Error creating saved scan: {str(e)}")
            raise

    def get_all_saved_scans(self) -> List[Dict[str, Any]]:
        """Lấy tất cả saved scans"""
        try:
            with self.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT * FROM saved_scans 
                    ORDER BY created_at DESC
                """)
                rows = cursor.fetchall()
                return [dict(row) for row in rows]

        except Exception as e:
            self.logger.error(f"Error getting all saved scans: {str(e)}")
            return []

    def get_saved_scan_by_id(self, scan_id: int) -> Optional[Dict[str, Any]]:
        """Lấy saved scan theo ID"""
        try:
            with self.get_connection() as conn:
                cursor = conn.execute("SELECT * FROM saved_scans WHERE id = ?", (scan_id,))
                row = cursor.fetchone()
                return dict(row) if row else None

        except Exception as e:
            self.logger.error(f"Error getting saved scan {scan_id}: {str(e)}")
            return None

    def delete_saved_scan(self, scan_id: int):
        """Xóa saved scan"""
        try:
            with self.get_connection() as conn:
                conn.execute("DELETE FROM saved_scans WHERE id = ?", (scan_id,))
                conn.commit()

        except Exception as e:
            self.logger.error(f"Error deleting saved scan {scan_id}: {str(e)}")
            raise

    def delete_folder_scan(self, folder_id: int) -> bool:
        """Xóa folder scan với retry logic"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                with self.get_connection() as conn:
                    # Begin transaction explicitly
                    conn.execute("BEGIN IMMEDIATE")
                    cursor = conn.execute("DELETE FROM folder_scans WHERE id = ?", (folder_id,))
                    conn.commit()
                    return cursor.rowcount > 0

            except sqlite3.OperationalError as e:
                if "database is locked" in str(e) and attempt < max_retries - 1:
                    import time
                    time.sleep(0.1 * (attempt + 1))
                    continue
                else:
                    self.logger.error(f"Error deleting folder scan {folder_id}: {str(e)}")
                    return False
            except Exception as e:
                self.logger.error(f"Error deleting folder scan {folder_id}: {str(e)}")
                return False

        return False

    def get_folder_scan_by_path(self, path: str) -> Optional[Dict[str, Any]]:
        """Lấy folder scan theo đường dẫn"""
        try:
            with self.get_connection() as conn:
                cursor = conn.execute("SELECT * FROM folder_scans WHERE path = ?", (path,))
                row = cursor.fetchone()
                return dict(row) if row else None

        except Exception as e:
            self.logger.error(f"Error getting folder scan by path {path}: {str(e)}")
            return None

    def create_folder_scan(self, folder_data: Dict[str, Any]) -> int:
        """Tạo folder scan mới"""
        try:
            with self.get_connection() as conn:
                cursor = conn.execute("""
                    INSERT INTO folder_scans (
                        original_title, path, image_count, description, 
                        status, new_title, data_name, category_id, site_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    folder_data.get('original_title', ''),
                    folder_data.get('path', ''),
                    folder_data.get('image_count', 0),
                    folder_data.get('description', ''),
                    folder_data.get('status', 'pending'),
                    folder_data.get('new_title', ''),
                    folder_data.get('data_name', ''),
                    folder_data.get('category_id'),
                    folder_data.get('site_id')
                ))
                conn.commit()
                return cursor.lastrowid

        except Exception as e:
            self.logger.error(f"Error creating folder scan: {str(e)}")
            raise

    def search_folder_scans(self, search_term: str) -> List[Dict[str, Any]]:
        """Tìm kiếm folder scans theo từ khóa"""
        try:
            with self.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT * FROM folder_scans 
                    WHERE original_title LIKE ? OR new_title LIKE ? OR path LIKE ?
                    ORDER BY id DESC
                """, (f"%{search_term}%", f"%{search_term}%", f"%{search_term}%"))

                columns = [description[0] for description in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]

        except Exception as e:
            self.logger.error(f"Error searching folder scans: {str(e)}")
            return []

    def update_folder_ai_content(self, folder_id: int, new_title: str, description: str) -> bool:
        """Cập nhật nội dung AI cho folder scan"""
        try:
            with self.get_connection() as conn:
                conn.execute("""
                    UPDATE folder_scans 
                    SET new_title = ?, description = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (new_title, description, folder_id))
                conn.commit()
                return True

        except Exception as e:
            self.logger.error(f"Error updating folder AI content {folder_id}: {str(e)}")
            return False

    def get_folder_scans_by_status(self, status: str) -> List[Dict[str, Any]]:
        """Lấy folder scans theo trạng thái"""
        try:
            with self.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT 
                        fs.*,
                        s.name as site_name,
                        c.name as category_name
                    FROM folder_scans fs
                    LEFT JOIN sites s ON fs.site_id = s.id
                    LEFT JOIN categories c ON fs.category_id = c.id
                    WHERE fs.status = ?
                    ORDER BY fs.created_at DESC
                """, (status,))

                columns = [description[0] for description in cursor.description]
                rows = cursor.fetchall()
                return [dict(zip(columns, row)) for row in rows]

        except Exception as e:
            self.logger.error(f"Error getting folder scans by status {status}: {str(e)}")
            return []

    def get_folder_scans_summary(self) -> Dict[str, Any]:
        """Lấy tổng quan folder scans"""
        try:
            with self.get_connection() as conn:
                # Tổng số folder scans
                cursor = conn.execute("SELECT COUNT(*) as total FROM folder_scans")
                total = cursor.fetchone()['total']

                # Folder scans theo trạng thái
                cursor = conn.execute("""
                    SELECT status, COUNT(*) as count 
                    FROM folder_scans 
                    GROUP BY status
                """)
                status_stats = {row['status']: row['count'] for row in cursor.fetchall()}

                # Folder scans theo site
                cursor = conn.execute("""
                    SELECT s.name, COUNT(fs.id) as count
                    FROM sites s
                    LEFT JOIN folder_scans fs ON s.id = fs.site_id
                    GROUP BY s.id, s.name
                """)
                site_stats = {row['name']: row['count'] for row in cursor.fetchall()}

                # Tổng số ảnh
                cursor = conn.execute("SELECT SUM(image_count) as total_images FROM folder_scans")
                total_images = cursor.fetchone()['total_images'] or 0

                return {
                    'total_folders': total,
                    'total_images': total_images,
                    'by_status': status_stats,
                    'by_site': site_stats
                }

        except Exception as e:
            self.logger.error(f"Error getting folder scans summary: {str(e)}")
            return {}

    def cleanup_orphaned_folder_scans(self) -> int:
        """Dọn dẹp folder scans không có đường dẫn hợp lệ"""
        try:
            import os
            deleted_count = 0

            with self.get_connection() as conn:
                # Lấy tất cả folder scans
                cursor = conn.execute("SELECT id, path FROM folder_scans")
                folders = cursor.fetchall()

                for folder in folders:
                    if not os.path.exists(folder['path']):
                        conn.execute("DELETE FROM folder_scans WHERE id = ?", (folder['id'],))
                        deleted_count += 1
                        self.logger.info(f"Deleted orphaned folder scan {folder['id']}: {folder['path']}")

                conn.commit()
                self.logger.info(f"Cleaned up {deleted_count} orphaned folder scans")
                return deleted_count

        except Exception as e:
            self.logger.error(f"Error cleaning up orphaned folder scans: {str(e)}")
            return 0

    def get_duplicate_folder_scans(self) -> List[Dict[str, Any]]:
        """Tìm các folder scans trùng lặp theo đường dẫn"""
        try:
            with self.get_connection() as conn:
                cursor = conn.execute("""
                    SELECT path, COUNT(*) as count, GROUP_CONCAT(id) as ids
                    FROM folder_scans 
                    GROUP BY path 
                    HAVING COUNT(*) > 1
                    ORDER BY count DESC
                """)

                duplicates = []
                for row in cursor.fetchall():
                    duplicates.append({
                        'path': row['path'],
                        'count': row['count'],
                        'ids': [int(id_str) for id_str in row['ids'].split(',')]
                    })

                return duplicates

        except Exception as e:
            self.logger.error(f"Error finding duplicate folder scans: {str(e)}")
            return []

    def merge_duplicate_folder_scans(self, keep_id: int, merge_ids: List[int]) -> bool:
        """Gộp các folder scans trùng lặp"""
        try:
            with self.get_connection() as conn:
                # Lấy thông tin folder giữ lại
                keeper = self.get_folder_scan_by_id(keep_id)
                if not keeper:
                    return False

                # Gộp thông tin từ các folder bị merge
                for merge_id in merge_ids:
                    merge_folder = self.get_folder_scan_by_id(merge_id)
                    if merge_folder:
                        # Cập nhật keeper với thông tin tốt nhất
                        update_data = {}

                        # Ưu tiên data_name có nội dung
                        if not keeper.get('data_name') and merge_folder.get('data_name'):
                            update_data['data_name'] = merge_folder['data_name']

                        # Ưu tiên description có nội dung
                        if not keeper.get('description') and merge_folder.get('description'):
                            update_data['description'] = merge_folder['description']

                        # Ưu tiên new_title có nội dung
                        if not keeper.get('new_title') and merge_folder.get('new_title'):
                            update_data['new_title'] = merge_folder['new_title']

                        # Ưu tiên site_id và category_id có giá trị
                        if not keeper.get('site_id') and merge_folder.get('site_id'):
                            update_data['site_id'] = merge_folder['site_id']

                        if not keeper.get('category_id') and merge_folder.get('category_id'):
                            update_data['category_id'] = merge_folder['category_id']

                        # Cập nhật keeper nếu có thông tin mới
                        if update_data:
                            self.update_folder_scan(keep_id, update_data)
                            keeper.update(update_data)

                # Xóa các folder bị merge
                for merge_id in merge_ids:
                    conn.execute("DELETE FROM folder_scans WHERE id = ?", (merge_id,))

                conn.commit()
                self.logger.info(f"Merged {len(merge_ids)} folder scans into {keep_id}")
                return True

        except Exception as e:
            self.logger.error(f"Error merging duplicate folder scans: {str(e)}")
            return False

    def optimize_folder_scans_table(self):
        """Tối ưu bảng folder_scans"""
        try:
            with self.get_connection() as conn:
                # Vacuum để tối ưu database
                conn.execute("VACUUM")

                # Reindex để tối ưu indexes
                conn.execute("REINDEX")

                # Analyze để cập nhật statistics
                conn.execute("ANALYZE")

                self.logger.info("Optimized folder_scans table")

        except Exception as e:
            self.logger.error(f"Error optimizing folder_scans table: {str(e)}")

    def export_folder_scans_to_json(self, file_path: str = None) -> str:
        """Export folder scans ra file JSON"""
        try:
            import json
            from datetime import datetime

            if not file_path:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                file_path = f"folder_scans_export_{timestamp}.json"

            folders = self.get_all_folder_scans()

            export_data = {
                'export_timestamp': datetime.now().isoformat(),
                'total_folders': len(folders),
                'folders': folders
            }

            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2, default=str)

            self.logger.info(f"Exported {len(folders)} folder scans to {file_path}")
            return file_path

        except Exception as e:
            self.logger.error(f"Error exporting folder scans: {str(e)}")
            raise

    def save_pages_from_api(self, site_id: int, pages: list):
        """Lưu pages từ API vào database"""
        try:
            with self.get_connection() as conn:
                # Xóa pages cũ của site này trước
                conn.execute("DELETE FROM pages WHERE site_id = ?", (site_id,))

                # Lưu từng page
                for page in pages:
                    wp_page_id = page.get('id')
                    title = page.get('title', {})
                    if isinstance(title, dict):
                        title = title.get('rendered', '')
                    
                    content = page.get('content', {})
                    if isinstance(content, dict):
                        content = content.get('rendered', '')
                    
                    excerpt = page.get('excerpt', {})
                    if isinstance(excerpt, dict):
                        excerpt = excerpt.get('rendered', '')

                    conn.execute("""
                        INSERT INTO pages (
                            site_id, wp_page_id, title, slug, content, excerpt, status,
                            parent_id, menu_order, featured_media, author, last_sync
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        site_id,
                        wp_page_id,
                        title,
                        page.get('slug', ''),
                        content,
                        excerpt,
                        page.get('status', 'publish'),
                        page.get('parent', 0),
                        page.get('menu_order', 0),
                        page.get('featured_media', 0),
                        page.get('author', 0),
                        datetime.now().isoformat()
                    ))

                conn.commit()
                self.logger.info(f"Saved {len(pages)} pages for site {site_id}")

        except Exception as e:
            self.logger.error(f"Error saving pages from API: {str(e)}")
            raise