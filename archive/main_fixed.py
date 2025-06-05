#!/usr/bin/env python3
"""
WooCommerce Product Manager - Fixed Main Entry Point
Phiên bản đã sửa lỗi recursion trong logging system
"""

import sys
import os
import logging
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon, QFont

# Thiết lập logging an toàn trước khi import app modules
def setup_safe_logging():
    """Thiết lập logging an toàn để tránh recursion"""
    # Xóa tất cả handlers hiện tại
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Tạo handler đơn giản
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter('%(levelname)s: %(message)s')
    handler.setFormatter(formatter)
    
    # Cấu hình root logger
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(handler)
    
    # Tắt propagation để tránh recursion
    for logger_name in ['app.database', 'app.folder_scanner', '__main__']:
        logger = logging.getLogger(logger_name)
        logger.propagate = False

# Thiết lập logging ngay từ đầu
setup_safe_logging()

# Add app directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

# Import sau khi đã thiết lập logging an toàn
try:
    from app.main_window import MainWindow
    from app.database import DatabaseManager
except ImportError as e:
    print(f"Lỗi import: {e}")
    sys.exit(1)

def main():
    """Hàm main khởi chạy ứng dụng với xử lý lỗi an toàn"""
    
    # Thiết lập môi trường Qt an toàn
    os.environ['QT_LOGGING_RULES'] = '*.debug=false'
    os.environ['QT_AUTO_SCREEN_SCALE_FACTOR'] = '0'
    
    # Tự động phát hiện platform
    if 'QT_QPA_PLATFORM' not in os.environ:
        if sys.platform.startswith('win'):
            os.environ['QT_QPA_PLATFORM'] = 'windows'
        elif sys.platform.startswith('darwin'):
            os.environ['QT_QPA_PLATFORM'] = 'cocoa'
        else:
            # Cho Linux/cloud environment
            os.environ['QT_QPA_PLATFORM'] = 'xcb'
    
    print("Đang khởi động WooCommerce Product Manager...")
    
    try:
        # Khởi tạo QApplication với xử lý lỗi
        app = QApplication(sys.argv)
        app.setApplicationName("WooCommerce Product Manager")
        app.setApplicationVersion("1.0.0")
        app.setOrganizationName("WooCommerce Tools")
        
        # Thiết lập font mặc định
        try:
            font = QFont("Arial", 9)
            app.setFont(font)
        except:
            pass  # Bỏ qua nếu không thiết lập được font
        
        print("Đang khởi tạo database...")
        
        # Khởi tạo database với xử lý lỗi an toàn
        try:
            db_manager = DatabaseManager()
            db_manager.init_database()
            print("Database đã sẵn sàng")
        except Exception as e:
            print(f"Cảnh báo: Lỗi khởi tạo database: {e}")
            # Tiếp tục chạy app ngay cả khi có lỗi database
        
        print("Đang tạo cửa sổ chính...")
        
        # Tạo cửa sổ chính
        main_window = MainWindow()
        main_window.show()
        
        print("Ứng dụng đã sẵn sàng!")
        
        # Chạy event loop
        return app.exec()
        
    except Exception as e:
        print(f"Lỗi khởi động ứng dụng: {e}")
        
        # Thử hiển thị lỗi qua QMessageBox nếu có thể
        try:
            if 'app' in locals():
                msg = QMessageBox()
                msg.setIcon(QMessageBox.Icon.Critical)
                msg.setWindowTitle("Lỗi khởi động")
                msg.setText(f"Không thể khởi động ứng dụng:\n{str(e)}")
                msg.exec()
        except:
            pass
        
        return 1

if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\nỨng dụng đã bị dừng bởi người dùng")
        sys.exit(0)
    except Exception as e:
        print(f"Lỗi không xử lý được: {e}")
        sys.exit(1)