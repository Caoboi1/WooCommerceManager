
#!/usr/bin/env python3
"""
Safe Mode Runner - Chạy ứng dụng với safe mode để tránh crash
"""

import sys
import os
import logging
import traceback
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import Qt

# Add app directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

def setup_safe_environment():
    """Thiết lập môi trường an toàn"""
    # Thiết lập Qt platform cho Windows
    os.environ['QT_QPA_PLATFORM'] = 'windows'
    
    # Tắt các tính năng có thể gây crash
    os.environ['QT_LOGGING_RULES'] = '*.debug=false'
    os.environ['QT_AUTO_SCREEN_SCALE_FACTOR'] = '0'
    os.environ['QT_SCALE_FACTOR'] = '1'
    
    # Tắt hardware acceleration nếu cần
    os.environ['QT_OPENGL'] = 'software'
    
    # Thiết lập thread-safe
    os.environ['QT_THREAD_POOL_MAX_THREAD_COUNT'] = '1'

def setup_logging():
    """Thiết lập logging an toàn"""
    try:
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('woocommerce_manager_safe.log', encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
    except Exception as e:
        print(f"Logging setup failed: {e}")

def create_safe_application():
    """Tạo QApplication với cấu hình an toàn"""
    try:
        # Tạo QApplication với safe attributes
        app = QApplication(sys.argv)
        
        # Thiết lập safe attributes
        app.setApplicationName("WooCommerce Product Manager")
        app.setApplicationVersion("1.0.0")
        app.setOrganizationName("WooCommerce Tools")
        
        # Thiết lập quit on last window closed
        app.setQuitOnLastWindowClosed(True)
        
        return app
    except Exception as e:
        print(f"Failed to create QApplication: {e}")
        return None

def main():
    """Main function với error handling"""
    print("🚀 Khởi chạy WooCommerce Product Manager (Safe Mode)...")
    
    try:
        # Thiết lập môi trường an toàn
        setup_safe_environment()
        setup_logging()
        
        logger = logging.getLogger(__name__)
        logger.info("Starting application in safe mode...")
        
        # Tạo QApplication
        app = create_safe_application()
        if not app:
            print("❌ Không thể tạo QApplication")
            return 1
        
        # Import và khởi tạo components sau khi QApplication đã sẵn sàng
        try:
            from app.database import DatabaseManager
            from app.main_window import MainWindow
            
            # Khởi tạo database
            db_manager = DatabaseManager()
            db_manager.init_database()
            logger.info("Database initialized successfully")
            
            # Tạo main window với error handling
            try:
                window = MainWindow()
                window.show()
                logger.info("Main window created and shown")
                
                # Chạy event loop
                logger.info("Starting Qt event loop...")
                exit_code = app.exec()
                logger.info(f"Application finished with exit code: {exit_code}")
                
                return exit_code
                
            except Exception as e:
                logger.error(f"Error creating main window: {str(e)}")
                logger.error(traceback.format_exc())
                
                # Hiển thị error dialog
                try:
                    QMessageBox.critical(None, "Lỗi", 
                                       f"Không thể tạo cửa sổ chính:\n{str(e)}")
                except:
                    print(f"Critical error: {e}")
                
                return 1
                
        except ImportError as e:
            logger.error(f"Import error: {str(e)}")
            print(f"❌ Lỗi import: {e}")
            return 1
            
    except Exception as e:
        print(f"❌ Lỗi nghiêm trọng: {e}")
        print(traceback.format_exc())
        return 1

if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n🛑 Ứng dụng bị dừng bởi người dùng")
        sys.exit(0)
    except Exception as e:
        print(f"❌ Lỗi không mong đợi: {e}")
        print(traceback.format_exc())
        sys.exit(1)
