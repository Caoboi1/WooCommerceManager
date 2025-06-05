
#!/usr/bin/env python3
"""
Safe Main Entry Point - Phiên bản an toàn của main.py
"""

import sys
import os
import logging
import traceback
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon, QFont

# Add app directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

def setup_logging():
    """Thiết lập logging cho ứng dụng"""
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
        print(f"Warning: Could not setup logging: {e}")

def main():
    """Hàm main khởi chạy ứng dụng với safe mode"""
    # Thiết lập logging
    setup_logging()
    
    # Thiết lập Qt environment variables cho Windows
    if sys.platform.startswith('win'):
        os.environ['QT_QPA_PLATFORM'] = 'windows'
        
    # Tắt debug logging
    os.environ['QT_LOGGING_RULES'] = '*.debug=false'
    os.environ['QT_AUTO_SCREEN_SCALE_FACTOR'] = '0'
    
    logger = logging.getLogger(__name__)
    logger.info("Starting WooCommerce Product Manager (Safe Mode)")

    try:
        # Khởi tạo QApplication với minimal setup
        app = QApplication(sys.argv)
        app.setApplicationName("WooCommerce Product Manager")
        app.setApplicationVersion("1.0.0")
        app.setOrganizationName("WooCommerce Tools")
        
        # Thiết lập font an toàn
        try:
            app.setFont(QFont("Arial", 10))
        except Exception as e:
            logger.warning(f"Could not set font: {e}")
        
        # Thiết lập icon an toàn
        try:
            if os.path.exists("attached_assets/woo-Photoroom.png"):
                app_icon = QIcon("attached_assets/woo-Photoroom.png")
                if not app_icon.isNull():
                    app.setWindowIcon(app_icon)
                    logger.info("Icon loaded successfully")
        except Exception as e:
            logger.warning(f"Could not load icon: {e}")

        # Import và khởi tạo database
        try:
            from app.database import DatabaseManager
            
            db_manager = DatabaseManager()
            db_manager.init_database()
            logger.info("Database initialized successfully")
            
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            QMessageBox.critical(None, "Lỗi Database", 
                               f"Không thể khởi tạo database:\n{str(e)}")
            return 1

        # Import và tạo main window
        try:
            from app.main_window_safe import SafeMainWindow
            
            # Tạo safe main window
            window = SafeMainWindow()
            window.db_manager = db_manager
            window.show()
            
            logger.info("Application started successfully")
            
            # Chạy event loop
            exit_code = app.exec()
            logger.info(f"Application finished with exit code: {exit_code}")
            
            return exit_code
            
        except Exception as e:
            logger.error(f"Error creating main window: {str(e)}")
            logger.error(traceback.format_exc())
            
            try:
                QMessageBox.critical(None, "Lỗi", 
                                   f"Không thể khởi tạo cửa sổ chính:\n{str(e)}")
            except:
                print(f"Critical error: {e}")
            
            return 1

    except Exception as e:
        logger.error(f"Critical application error: {str(e)}")
        logger.error(traceback.format_exc())
        print(f"❌ Lỗi nghiêm trọng: {e}")
        return 1

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n🛑 Ứng dụng bị dừng bởi người dùng")
        sys.exit(0)
    except Exception as e:
        print(f"❌ Lỗi không mong đợi: {e}")
        sys.exit(1)
