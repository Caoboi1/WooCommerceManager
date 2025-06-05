"""
WooCommerce Product Manager Application Package
"""

__version__ = '1.0.0'
__author__ = "Học Trần"
__telegram__ = "@anh2nd"
__description__ = "Ứng dụng quản lý sản phẩm đa site WooCommerce"

# Package initialization
from . import models  # Import models module
from . import utils  # Import utils module
from . import main_window  # Import main window module
from . import site_manager  # Import site manager module 
from . import product_manager  # Import product manager module
from . import woocommerce_api  # Import WooCommerce API module
from . import database  # Import database module
from . import folder_scanner  # Import folder scanner module