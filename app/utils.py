"""
Utility Functions - Các hàm tiện ích cho ứng dụng
"""

import os
import re
import logging
import json
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import csv
from urllib.parse import urlparse
import hashlib

def validate_url(url: str) -> Tuple[bool, str]:
    """
    Validate URL format
    
    Args:
        url: URL to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not url:
        return False, "URL không được để trống"
    
    try:
        parsed = urlparse(url)
        if not parsed.scheme:
            return False, "URL phải có scheme (http:// hoặc https://)"
        if not parsed.netloc:
            return False, "URL phải có domain name"
        if parsed.scheme not in ['http', 'https']:
            return False, "URL phải bắt đầu bằng http:// hoặc https://"
        return True, ""
    except Exception as e:
        return False, f"URL không hợp lệ: {str(e)}"

def validate_consumer_key(key: str) -> Tuple[bool, str]:
    """
    Validate WooCommerce Consumer Key format
    
    Args:
        key: Consumer key to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not key:
        return False, "Consumer Key không được để trống"
    
    # WooCommerce consumer key usually starts with 'ck_'
    if not key.startswith('ck_'):
        return False, "Consumer Key phải bắt đầu bằng 'ck_'"
    
    # Check minimum length
    if len(key) < 20:
        return False, "Consumer Key quá ngắn (tối thiểu 20 ký tự)"
    
    return True, ""

def validate_consumer_secret(secret: str) -> Tuple[bool, str]:
    """
    Validate WooCommerce Consumer Secret format
    
    Args:
        secret: Consumer secret to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not secret:
        return False, "Consumer Secret không được để trống"
    
    # WooCommerce consumer secret usually starts with 'cs_'
    if not secret.startswith('cs_'):
        return False, "Consumer Secret phải bắt đầu bằng 'cs_'"
    
    # Check minimum length
    if len(secret) < 20:
        return False, "Consumer Secret quá ngắn (tối thiểu 20 ký tự)"
    
    return True, ""

def validate_sku(sku: str) -> Tuple[bool, str]:
    """
    Validate product SKU format
    
    Args:
        sku: SKU to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not sku:
        return True, ""  # SKU is optional
    
    # SKU should only contain alphanumeric characters, hyphens, and underscores
    if not re.match(r'^[a-zA-Z0-9_-]+$', sku):
        return False, "SKU chỉ được chứa chữ cái, số, dấu gạch ngang và gạch dưới"
    
    # Check length
    if len(sku) > 100:
        return False, "SKU quá dài (tối đa 100 ký tự)"
    
    return True, ""

def format_price(price: float, currency: str = "USD") -> str:
    """
    Format price for display
    
    Args:
        price: Price value
        currency: Currency symbol
        
    Returns:
        Formatted price string
    """
    if price is None:
        return "$0.00"
    
    if currency == "USD":
        return f"${price:,.2f}"
    else:
        return f"{price:,.2f} {currency}"

def format_price_usd(price: Optional[float]) -> str:
    """
    Format price specifically for USD display
    
    Args:
        price: Price value
        
    Returns:
        Formatted USD price string
    """
    if price is None or price == 0:
        return "$0.00"
    
    try:
        return f"${price:,.2f}"
    except (ValueError, TypeError):
        return "N/A"

def format_datetime(dt_str: str, format_str: str = "%d/%m/%Y %H:%M") -> str:
    """
    Format datetime string for display
    
    Args:
        dt_str: ISO datetime string
        format_str: Target format string
        
    Returns:
        Formatted datetime string
    """
    if not dt_str:
        return "N/A"
    
    try:
        # Parse ISO datetime
        if 'T' in dt_str:
            dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
        else:
            dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
        
        return dt.strftime(format_str)
    except (ValueError, TypeError):
        return dt_str

def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename for safe file operations
    
    Args:
        filename: Original filename
        
    Returns:
        Sanitized filename
    """
    # Remove or replace invalid characters
    sanitized = re.sub(r'[<>:"/\\|?*]', '_', filename)
    
    # Remove multiple consecutive underscores
    sanitized = re.sub(r'_+', '_', sanitized)
    
    # Trim and ensure not empty
    sanitized = sanitized.strip('_')
    if not sanitized:
        sanitized = "file"
    
    return sanitized

def export_to_csv(data: List[Dict[str, Any]], filename: str, headers: List[str] = None) -> bool:
    """
    Export data to CSV file
    
    Args:
        data: List of dictionaries to export
        filename: Output filename
        headers: Optional custom headers
        
    Returns:
        Success status
    """
    try:
        if not data:
            return False
        
        # Use provided headers or extract from first row
        if not headers:
            headers = list(data[0].keys())
        
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=headers)
            writer.writeheader()
            
            for row in data:
                # Filter row to only include header fields
                filtered_row = {k: v for k, v in row.items() if k in headers}
                writer.writerow(filtered_row)
        
        return True
    except Exception as e:
        logging.getLogger(__name__).error(f"Error exporting to CSV: {str(e)}")
        return False

def import_from_csv(filename: str) -> List[Dict[str, Any]]:
    """
    Import data from CSV file
    
    Args:
        filename: Input filename
        
    Returns:
        List of dictionaries
    """
    try:
        data = []
        with open(filename, 'r', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                data.append(dict(row))
        return data
    except Exception as e:
        logging.getLogger(__name__).error(f"Error importing from CSV: {str(e)}")
        return []

def generate_hash(text: str) -> str:
    """
    Generate SHA256 hash of text
    
    Args:
        text: Text to hash
        
    Returns:
        Hex digest of hash
    """
    return hashlib.sha256(text.encode('utf-8')).hexdigest()

def safe_int(value: Any, default: int = 0) -> int:
    """
    Safely convert value to integer
    
    Args:
        value: Value to convert
        default: Default value if conversion fails
        
    Returns:
        Integer value
    """
    try:
        return int(value)
    except (ValueError, TypeError):
        return default

def safe_float(value: Any, default: float = 0.0) -> float:
    """
    Safely convert value to float
    
    Args:
        value: Value to convert
        default: Default value if conversion fails
        
    Returns:
        Float value
    """
    try:
        return float(value)
    except (ValueError, TypeError):
        return default

def truncate_text(text: str, max_length: int = 50, suffix: str = "...") -> str:
    """
    Truncate text to maximum length
    
    Args:
        text: Text to truncate
        max_length: Maximum length
        suffix: Suffix to add if truncated
        
    Returns:
        Truncated text
    """
    if not text:
        return ""
    
    if len(text) <= max_length:
        return text
    
    return text[:max_length - len(suffix)] + suffix

def clean_html(text: str) -> str:
    """
    Remove HTML tags from text
    
    Args:
        text: HTML text
        
    Returns:
        Plain text
    """
    if not text:
        return ""
    
    # Simple HTML tag removal
    clean_text = re.sub(r'<[^>]+>', '', text)
    
    # Clean up extra whitespace
    clean_text = re.sub(r'\s+', ' ', clean_text).strip()
    
    return clean_text

def get_file_size_mb(file_path: str) -> float:
    """
    Get file size in MB
    
    Args:
        file_path: Path to file
        
    Returns:
        File size in MB
    """
    try:
        size_bytes = os.path.getsize(file_path)
        return size_bytes / (1024 * 1024)
    except (OSError, IOError):
        return 0.0

def ensure_directory(directory: str) -> bool:
    """
    Ensure directory exists, create if not
    
    Args:
        directory: Directory path
        
    Returns:
        Success status
    """
    try:
        os.makedirs(directory, exist_ok=True)
        return True
    except OSError:
        return False

def load_json_config(file_path: str) -> Dict[str, Any]:
    """
    Load JSON configuration file
    
    Args:
        file_path: Path to JSON file
        
    Returns:
        Configuration dictionary
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logging.getLogger(__name__).error(f"Error loading JSON config: {str(e)}")
        return {}

def save_json_config(data: Dict[str, Any], file_path: str) -> bool:
    """
    Save configuration to JSON file
    
    Args:
        data: Data to save
        file_path: Path to JSON file
        
    Returns:
        Success status
    """
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except (OSError, IOError) as e:
        logging.getLogger(__name__).error(f"Error saving JSON config: {str(e)}")
        return False

def parse_categories_string(categories_str: str) -> List[str]:
    """
    Parse categories string into list
    
    Args:
        categories_str: Comma-separated categories
        
    Returns:
        List of category names
    """
    if not categories_str:
        return []
    
    categories = [cat.strip() for cat in categories_str.split(',')]
    return [cat for cat in categories if cat]

def parse_tags_string(tags_str: str) -> List[str]:
    """
    Parse tags string into list
    
    Args:
        tags_str: Comma-separated tags
        
    Returns:
        List of tag names
    """
    if not tags_str:
        return []
    
    tags = [tag.strip() for tag in tags_str.split(',')]
    return [tag for tag in tags if tag]

def format_status_display(status: str) -> str:
    """
    Format product status for display
    
    Args:
        status: Product status
        
    Returns:
        Formatted status with emoji
    """
    status_map = {
        'publish': '✅ Xuất bản',
        'draft': '📝 Nháp',
        'private': '🔒 Riêng tư',
        'pending': '⏳ Chờ duyệt',
        'trash': '🗑️ Thùng rác'
    }
    
    return status_map.get(status, f"❓ {status}")

def get_app_version() -> str:
    """
    Get application version
    
    Returns:
        Version string
    """
    return "1.0.0"

def get_app_info() -> Dict[str, str]:
    """
    Get application information
    
    Returns:
        Application info dictionary
    """
    return {
        'name': 'WooCommerce Product Manager',
        'version': get_app_version(),
        'author': 'WooCommerce Tools',
        'description': 'Ứng dụng quản lý sản phẩm đa site WooCommerce'
    }

class ProgressCallback:
    """Callback class for progress tracking"""
    
    def __init__(self, callback_func=None):
        self.callback_func = callback_func
        self.current = 0
        self.total = 100
        
    def update(self, current: int, total: int = None, message: str = ""):
        """Update progress"""
        self.current = current
        if total is not None:
            self.total = total
            
        if self.callback_func:
            percentage = int((current / self.total) * 100) if self.total > 0 else 0
            self.callback_func(percentage, message)
    
    def increment(self, step: int = 1, message: str = ""):
        """Increment progress"""
        self.update(self.current + step, self.total, message)
    
    def finish(self, message: str = "Hoàn thành"):
        """Finish progress"""
        self.update(self.total, self.total, message)

def setup_logging(log_file: str = "woocommerce_manager.log", level: int = logging.INFO):
    """
    Setup logging configuration
    
    Args:
        log_file: Log file path
        level: Logging level
    """
    # Create logs directory if not exists
    log_dir = os.path.dirname(log_file)
    if log_dir:
        ensure_directory(log_dir)
    
    # Configure logging
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )

def get_system_info() -> Dict[str, str]:
    """
    Get system information
    
    Returns:
        System info dictionary
    """
    import platform
    import sys
    
    return {
        'platform': platform.platform(),
        'system': platform.system(),
        'release': platform.release(),
        'version': platform.version(),
        'machine': platform.machine(),
        'processor': platform.processor(),
        'python_version': sys.version,
        'python_executable': sys.executable
    }

def count_images_in_folder(folder_path: str, extensions: List[str] = None) -> int:
    """
    Count images in a folder
    
    Args:
        folder_path: Path to folder
        extensions: List of image extensions
        
    Returns:
        Number of images
    """
    if extensions is None:
        extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']
    
    try:
        count = 0
        for file in os.listdir(folder_path):
            if any(file.lower().endswith(ext) for ext in extensions):
                count += 1
        return count
    except (OSError, IOError):
        return 0

def get_folder_info(folder_path: str) -> Dict[str, Any]:
    """
    Get folder information including image count
    
    Args:
        folder_path: Path to folder
        
    Returns:
        Folder info dictionary
    """
    try:
        folder_name = os.path.basename(folder_path)
        if not folder_name:
            folder_name = os.path.basename(os.path.dirname(folder_path))
        
        image_count = count_images_in_folder(folder_path)
        
        return {
            'name': folder_name,
            'path': folder_path,
            'image_count': image_count,
            'exists': os.path.exists(folder_path),
            'is_dir': os.path.isdir(folder_path)
        }
    except Exception:
        return {
            'name': '',
            'path': folder_path,
            'image_count': 0,
            'exists': False,
            'is_dir': False
        }

def scan_folders_for_images(root_path: str, min_images: int = 1, extensions: List[str] = None) -> List[Dict[str, Any]]:
    """
    Scan folders for images
    
    Args:
        root_path: Root path to scan
        min_images: Minimum number of images required
        extensions: List of image extensions
        
    Returns:
        List of folder info dictionaries
    """
    if extensions is None:
        extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']
    
    folders = []
    
    try:
        for root, dirs, files in os.walk(root_path):
            image_count = count_images_in_folder(root, extensions)
            
            if image_count >= min_images:
                folder_name = os.path.basename(root)
                if not folder_name:
                    folder_name = os.path.basename(root_path)
                
                folders.append({
                    'original_title': folder_name,
                    'path': root,
                    'image_count': image_count,
                    'description': f"Thư mục chứa {image_count} ảnh",
                    'status': 'pending',
                    'new_title': ''
                })
    
    except Exception as e:
        logging.getLogger(__name__).error(f"Error scanning folders: {str(e)}")
    
    return folders

def validate_folder_path(path: str) -> Tuple[bool, str]:
    """
    Validate folder path
    
    Args:
        path: Folder path to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not path:
        return False, "Đường dẫn không được để trống"
    
    if not os.path.exists(path):
        return False, "Đường dẫn không tồn tại"
    
    if not os.path.isdir(path):
        return False, "Đường dẫn không phải là thư mục"
    
    try:
        # Test if we can read the directory
        os.listdir(path)
        return True, ""
    except PermissionError:
        return False, "Không có quyền truy cập thư mục"
    except Exception as e:
        return False, f"Lỗi truy cập thư mục: {str(e)}"

def get_image_extensions() -> List[str]:
    """
    Get list of supported image extensions
    
    Returns:
        List of image extensions
    """
    return ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff', '.tif']

def format_folder_status(status: str) -> str:
    """
    Format folder status for display
    
    Args:
        status: Folder status
        
    Returns:
        Formatted status with emoji
    """
    status_map = {
        'pending': '⏳ Chờ xử lý',
        'processing': '🔄 Đang xử lý',
        'completed': '✅ Hoàn thành',
        'error': '❌ Lỗi'
    }
    
    return status_map.get(status, f"❓ {status}")

def generate_folder_description(folder_path: str, image_count: int) -> str:
    """
    Generate description for folder
    
    Args:
        folder_path: Path to folder
        image_count: Number of images
        
    Returns:
        Generated description
    """
    folder_name = os.path.basename(folder_path)
    
    descriptions = [
        f"Thư mục '{folder_name}' chứa {image_count} ảnh",
        f"Bộ sưu tập {image_count} hình ảnh trong thư mục {folder_name}",
        f"Tổng cộng {image_count} ảnh được tìm thấy trong {folder_name}"
    ]
    
    # Choose description based on image count
    if image_count <= 5:
        return descriptions[0]
    elif image_count <= 20:
        return descriptions[1]
    else:
        return descriptions[2]
