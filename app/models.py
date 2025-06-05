"""
Data Models - Định nghĩa các model dữ liệu
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any
from datetime import datetime

@dataclass
class Site:
    """Model cho WooCommerce Site"""
    id: Optional[int] = None
    name: str = ""
    url: str = ""
    consumer_key: str = ""
    consumer_secret: str = ""
    wp_username: str = ""
    wp_app_password: str = ""
    is_active: bool = True
    notes: str = ""
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Site':
        """Tạo Site từ dictionary"""
        return cls(
            id=data.get('id'),
            name=data.get('name', ''),
            url=data.get('url', ''),
            consumer_key=data.get('consumer_key', ''),
            consumer_secret=data.get('consumer_secret', ''),
            wp_username=data.get('wp_username', ''),
            wp_app_password=data.get('wp_app_password', ''),
            is_active=bool(data.get('is_active', True)),
            notes=data.get('notes', ''),
            created_at=data.get('created_at'),
            updated_at=data.get('updated_at')
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Chuyển Site thành dictionary"""
        return {
            'id': self.id,
            'name': self.name,
            'url': self.url,
            'consumer_key': self.consumer_key,
            'consumer_secret': self.consumer_secret,
            'wp_username': self.wp_username,
            'wp_app_password': self.wp_app_password,
            'is_active': self.is_active,
            'notes': self.notes,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }

@dataclass
class Product:
    """Model cho WooCommerce Product"""
    id: Optional[int] = None
    site_id: int = 0
    wc_product_id: Optional[int] = None
    name: str = ""
    sku: str = ""
    price: Optional[float] = None
    regular_price: Optional[float] = None
    sale_price: Optional[float] = None
    stock_quantity: Optional[int] = None
    stock_status: str = "instock"  # instock, outofstock, onbackorder
    status: str = "draft"
    description: str = ""
    short_description: str = ""
    categories: str = ""
    tags: str = ""
    images: str = ""
    view_count: int = 0
    order_count: int = 0
    last_sync: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Product':
        """Tạo Product từ dictionary"""
        return cls(
            id=data.get('id'),
            site_id=data.get('site_id', 0),
            wc_product_id=data.get('wc_product_id'),
            name=data.get('name', ''),
            sku=data.get('sku', ''),
            price=data.get('price'),
            regular_price=data.get('regular_price'),
            sale_price=data.get('sale_price'),
            stock_quantity=data.get('stock_quantity'),
            status=data.get('status', 'draft'),
            description=data.get('description', ''),
            short_description=data.get('short_description', ''),
            categories=data.get('categories', ''),
            tags=data.get('tags', ''),
            images=data.get('images', ''),
            view_count=data.get('view_count', 0),
            order_count=data.get('order_count', 0),
            last_sync=data.get('last_sync'),
            created_at=data.get('created_at'),
            updated_at=data.get('updated_at')
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Chuyển Product thành dictionary"""
        return {
            'id': self.id,
            'site_id': self.site_id,
            'wc_product_id': self.wc_product_id,
            'name': self.name,
            'sku': self.sku,
            'price': self.price,
            'regular_price': self.regular_price,
            'sale_price': self.sale_price,
            'stock_quantity': self.stock_quantity,
            'status': self.status,
            'description': self.description,
            'short_description': self.short_description,
            'categories': self.categories,
            'tags': self.tags,
            'images': self.images,
            'view_count': self.view_count,
            'order_count': self.order_count,
            'last_sync': self.last_sync,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }

@dataclass
class ApiCredentials:
    """Model cho thông tin xác thực API"""
    consumer_key: str
    consumer_secret: str
    
    def is_valid(self) -> bool:
        """Kiểm tra tính hợp lệ của credentials"""
        return bool(self.consumer_key and self.consumer_secret)

@dataclass
class Category:
    """Model cho WooCommerce Category"""
    id: Optional[int] = None
    site_id: int = 0
    wc_category_id: Optional[int] = None
    name: str = ""
    slug: str = ""
    parent_id: Optional[int] = None
    description: str = ""
    count: int = 0
    image: str = ""
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Category':
        """Tạo Category từ dictionary"""
        return cls(
            id=data.get('id'),
            site_id=data.get('site_id', 0),
            wc_category_id=data.get('wc_category_id'),
            name=data.get('name', ''),
            slug=data.get('slug', ''),
            parent_id=data.get('parent_id'),
            description=data.get('description', ''),
            count=data.get('count', 0),
            image=data.get('image', ''),
            created_at=data.get('created_at'),
            updated_at=data.get('updated_at')
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Chuyển Category thành dictionary"""
        return {
            'id': self.id,
            'site_id': self.site_id,
            'wc_category_id': self.wc_category_id,
            'name': self.name,
            'slug': self.slug,
            'parent_id': self.parent_id,
            'description': self.description,
            'count': self.count,
            'image': self.image,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }

@dataclass
class SyncResult:
    """Model cho kết quả đồng bộ"""
    success: bool
    products_synced: int = 0
    products_updated: int = 0
    products_created: int = 0
    errors: list = None
    message: str = ""
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []

@dataclass
class FolderScan:
    """Model cho thư mục ảnh được quét"""
    id: Optional[int] = None
    data_name: str = ""  # Tên data để quản lý
    original_title: str = ""  # Tên folder gốc
    path: str = ""  # Đường dẫn tới folder
    image_count: int = 0  # Số lượng ảnh
    description: str = ""  # Mô tả để AI phát triển
    category_id: Optional[int] = None  # ID danh mục
    site_id: Optional[int] = None  # ID site
    status: str = "pending"  # pending, processing, completed, error
    new_title: str = ""  # Tiêu đề viết lại bằng AI
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FolderScan':
        """Tạo FolderScan từ dictionary"""
        return cls(
            id=data.get('id'),
            data_name=data.get('data_name', ''),
            original_title=data.get('original_title', ''),
            path=data.get('path', ''),
            image_count=data.get('image_count', 0),
            description=data.get('description', ''),
            category_id=data.get('category_id'),
            site_id=data.get('site_id'),
            status=data.get('status', 'pending'),
            new_title=data.get('new_title', ''),
            created_at=data.get('created_at'),
            updated_at=data.get('updated_at')
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Chuyển FolderScan thành dictionary"""
        return {
            'id': self.id,
            'data_name': self.data_name,
            'original_title': self.original_title,
            'path': self.path,
            'image_count': self.image_count,
            'description': self.description,
            'category_id': self.category_id,
            'site_id': self.site_id,
            'status': self.status,
            'new_title': self.new_title,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
