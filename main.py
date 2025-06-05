#!/usr/bin/env python3
"""
WooCommerce Product Manager - Main Entry Point
Ứng dụng quản lý sản phẩm đa site WooCommerce

DEVELOPMENT DOCUMENTATION:
==========================

OVERVIEW:
---------
Ứng dụng desktop PyQt6 để quản lý sản phẩm từ nhiều site WooCommerce.
Cho phép kết nối, đồng bộ, thêm/sửa/xóa sản phẩm từ nhiều cửa hàng WooCommerce.

FEATURES:
---------
1. Quản lý Sites WooCommerce:
   - Thêm/sửa/xóa thông tin site
   - Test kết nối API
   - Import/Export danh sách sites

2. Quản lý Sản phẩm:
   - Đồng bộ sản phẩm từ các sites
   - CRUD operations cho sản phẩm
   - Tìm kiếm và lọc sản phẩm
   - Import/Export CSV

ARCHITECTURE:
-------------
- main.py: Entry point, khởi tạo ứng dụng
- app/main_window.py: Cửa sổ chính với tab interface
- app/site_manager.py: Tab quản lý sites WooCommerce
- app/product_manager.py: Tab quản lý sản phẩm
- app/database.py: SQLite database manager
- app/models.py: Data models (Site, Product)
- app/woocommerce_api.py: WooCommerce REST API client
- app/dialogs.py: Dialog forms cho thêm/sửa
- app/utils.py: Utility functions

DEPLOYMENT NOTES:
----------------
- Requires PyQt6, requests, pandas packages
- Uses SQLite for local database
- VNC server required for cloud/headless deployment
- Desktop environment needed for GUI display

CONFIGURATION:
--------------
- Database: SQLite file (woocommerce_manager.db)
- Logs: woocommerce_manager.log
- VNC: Port 5901, Display :1
"""

import sys
import os
import logging
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon, QFont

# Add app directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

from app.main_window import MainWindow
from app.database import DatabaseManager

def setup_logging():
    """Thiết lập logging cho ứng dụng"""
    # Clear any existing handlers to prevent recursion
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)

    # Create a simple, safe logging configuration
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ],
        force=True
    )

    # Disable debug logging for Qt to reduce noise
    logging.getLogger('PyQt6').setLevel(logging.WARNING)
    logging.getLogger('qt').setLevel(logging.WARNING)

def main():
    """Hàm main khởi chạy ứng dụng với xử lý lỗi an toàn"""
    # Thiết lập logging
    setup_logging()

    # Thiết lập Qt platform tự động
    if sys.platform.startswith('win'):
        os.environ['QT_QPA_PLATFORM'] = 'windows'
    elif sys.platform.startswith('darwin'):
        os.environ['QT_QPA_PLATFORM'] = 'cocoa'
    else:
        # Linux - thử các platform theo thứ tự ưu tiên
        if 'DISPLAY' in os.environ:
            # Có display, thử xcb trước
            if not os.environ.get('QT_QPA_PLATFORM'):
                os.environ['QT_QPA_PLATFORM'] = 'xcb'
        else:
            # Không có display, dùng headless
            os.environ['QT_QPA_PLATFORM'] = 'minimal'

    # Tắt debug logging và cải thiện hiệu suất
    os.environ['QT_LOGGING_RULES'] = '*.debug=false;qt.qpa.xcb.warning=false'
    os.environ['QT_AUTO_SCREEN_SCALE_FACTOR'] = '0'
    os.environ['QT_ENABLE_HIGHDPI_SCALING'] = '0'

    logger = logging.getLogger(__name__)
    logger.info("Starting WooCommerce Product Manager")

    # Khởi tạo QApplication với xử lý lỗi platform
    app = None
    platforms_to_try = []

    if sys.platform.startswith('linux'):
        if 'DISPLAY' in os.environ:
            platforms_to_try = ['xcb', 'minimal', 'offscreen']
        else:
            platforms_to_try = ['minimal', 'offscreen']
    elif sys.platform.startswith('win'):
        platforms_to_try = ['windows']
    elif sys.platform.startswith('darwin'):
        platforms_to_try = ['cocoa']
    else:
        platforms_to_try = ['minimal', 'offscreen']

    # Thử từng platform cho đến khi thành công
    for platform in platforms_to_try:
        try:
            logger.info(f"Trying Qt platform: {platform}")
            os.environ['QT_QPA_PLATFORM'] = platform
            app = QApplication(sys.argv)
            logger.info(f"Successfully initialized QApplication with platform: {platform}")
            break
        except Exception as e:
            logger.warning(f"Failed to initialize QApplication with platform {platform}: {e}")
            if app:
                try:
                    app.quit()
                    del app
                    app = None
                except:
                    pass

    if not app:
        logger.error("Failed to initialize QApplication with any platform")
        print("❌ Không thể khởi tạo giao diện đồ họa")
        return 1

    app.setApplicationName("WooCommerce Product Manager")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("WooCommerce Tools")

    # Thiết lập icon cho ứng dụng và taskbar
    app_icon = None
    try:
        # Thử load logo theo thứ tự ưu tiên, looking for larger icons first
        icon_paths = [
            "attached_assets/woo-Photoroom_128.png", # Added a possible larger icon
            "attached_assets/image_1749110052406_128.png", # Added a possible larger icon
            "attached_assets/woo-Photoroom.png",
            "attached_assets/image_1749110052406.png",
            "icon_128.png", # Added a possible larger icon
            "icon.png"
        ]

        for icon_path in icon_paths:
            if os.path.exists(icon_path):
                app_icon = QIcon(icon_path)
                if not app_icon.isNull():
                    logger.info(f"Đã load icon từ {icon_path}")
                    break

        # Thiết lập icon cho ứng dụng nếu có
        if app_icon and not app_icon.isNull():
            app.setWindowIcon(app_icon)

            # Thiết lập cho taskbar/dock trên các OS khác nhau
            if sys.platform.startswith('linux'):
                # Linux - thiết lập WM_CLASS để taskbar nhận diện
                app.setDesktopFileName("woocommerce-product-manager")
                os.environ['XDG_CURRENT_DESKTOP'] = os.environ.get('XDG_CURRENT_DESKTOP', 'GNOME')
            elif sys.platform.startswith('win'):
                # Windows - thiết lập app ID
                import ctypes
                myappid = 'woocommerce.productmanager.1.0'
                try:
                    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
                except:
                    pass
            elif sys.platform.startswith('darwin'):
                # macOS - thiết lập bundle identifier
                app.setApplicationName("WooCommerce Product Manager")

            logger.info("Đã thiết lập icon cho ứng dụng và taskbar")
        else:
            logger.warning("Không thể tạo icon hợp lệ từ các file có sẵn")

    except Exception as e:
        logger.warning(f"Lỗi khi thiết lập icon: {str(e)}")

    # Thiết lập font hỗ trợ tiếng Việt
    app.setFont(QFont("Arial", 10))

    # Thiết lập style cho ứng dụng
    app.setStyleSheet("""
        QMainWindow {
            background-color: #f5f5f5;
        }
        QTabWidget::pane {
            border: 1px solid #c0c0c0;
            background-color: white;
        }
        QTabWidget::tab-bar {
            alignment: left;
        }
        QTabBar::tab {
            background-color: #e1e1e1;
            padding: 8px 16px;
            margin-right: 2px;
            border-top-left-radius: 4px;
            border-top-right-radius: 4px;
        }
        QTabBar::tab:selected {
            background-color: white;
            border-bottom: 2px solid #0078d4;
        }
        QTabBar::tab:hover {
            background-color: #d1d1d1;
        }
        QPushButton {
            background-color: #0078d4;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 4px;
            font-weight: bold;
        }
        QPushButton:hover {
            background-color: #106ebe;
        }
        QPushButton:pressed {
            background-color: #005a9e;
        }
        QPushButton:disabled {
            background-color: #cccccc;
            color: #666666;
        }
        QTableWidget {
            gridline-color: #d0d0d0;
            background-color: white;
            alternate-background-color: #f8f8f8;
        }
        QTableWidget::item {
            padding: 4px;
        }
        QTableWidget::item:selected {
            background-color: #0078d4;
            color: white;
        }
        QHeaderView::section {
            background-color: #e1e1e1;
            padding: 8px;
            border: 1px solid #c0c0c0;
            font-weight: bold;
        }
        QLineEdit, QTextEdit, QComboBox {
            border: 1px solid #c0c0c0;
            padding: 4px;
            border-radius: 2px;
        }
        QLineEdit:focus, QTextEdit:focus, QComboBox:focus {
            border: 2px solid #0078d4;
        }
        QGroupBox {
            font-weight: bold;
            border: 2px solid #c0c0c0;
            border-radius: 4px;
            margin-top: 1ex;
            padding-top: 10px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 5px 0 5px;
        }
    """)

    try:
        # Thiết lập font an toàn
        try:
            app.setFont(QFont("Arial", 10))
        except Exception as e:
            logger.warning(f"Could not set font: {e}")

        # Thiết lập icon an toàn
        try:
            # Looking for larger icons first
            icon_paths = [
                "attached_assets/woo-Photoroom_128.png", # Added a possible larger icon
                "attached_assets/image_1749110052406_128.png", # Added a possible larger icon
                "attached_assets/woo-Photoroom.png",
                "attached_assets/image_1749110052406.png",
                "icon_128.png", # Added a possible larger icon
                "icon.png"
            ]

            for icon_path in icon_paths:
                if os.path.exists(icon_path):
                    app_icon = QIcon(icon_path)
                    if not app_icon.isNull():
                        app.setWindowIcon(app_icon)
                        logger.info(f"Icon loaded successfully from {icon_path}")
                        break

        except Exception as e:
            logger.warning(f"Could not load icon: {e}")

        # Import và khởi tạo database
        try:
            print("Đang khởi tạo database...")
            db_manager = DatabaseManager()
            db_manager.init_database()
            print("Database đã sẵn sàng")
            logger.info("Database initialized successfully")

        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(None, "Lỗi Database", 
                               f"Không thể khởi tạo database:\n{str(e)}")
            return 1

        # Import và tạo main window
        try:
            # Tạo main window
            window = MainWindow()
            window.db_manager = db_manager
            window.show()

            logger.info("Application started successfully")

            # Chạy event loop
            exit_code = app.exec()
            logger.info(f"Application finished with exit code: {exit_code}")

            return exit_code

        except Exception as e:
            logger.error(f"Failed to create main window: {e}")
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(None, "Lỗi Khởi chạy", 
                               f"Không thể tạo cửa sổ chính:\n{str(e)}")
            return 1

    except Exception as e:
        logger.error(f"Critical error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    main()