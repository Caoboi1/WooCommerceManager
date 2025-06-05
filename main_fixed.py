#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WooCommerce Product Manager - Fixed Entry Point
Phiên bản sửa lỗi để chạy ổn định trên môi trường VNC
"""

import sys
import os
import logging
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QGuiApplication

# Add current directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

def setup_logging():
    """Thiết lập logging đơn giản"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

def main():
    """Hàm main đơn giản và ổn định"""
    logger = logging.getLogger(__name__)
    
    try:
        setup_logging()
        logger.info("Starting WooCommerce Product Manager (Fixed Version)")
        
        # Thiết lập platform cho VNC
        platforms = ['vnc', 'xcb', 'wayland', 'offscreen']
        
        for platform in platforms:
            try:
                logger.info(f"Trying platform: {platform}")
                os.environ['QT_QPA_PLATFORM'] = platform
                
                app = QApplication(sys.argv)
                logger.info(f"Successfully initialized with platform: {platform}")
                break
                
            except Exception as e:
                logger.warning(f"Platform {platform} failed: {str(e)}")
                continue
        else:
            logger.error("No suitable platform found")
            return 1
        
        # Thiết lập các thuộc tính ứng dụng
        app.setApplicationName("WooCommerce Product Manager")
        app.setApplicationVersion("2.0.0")
        app.setOrganizationName("WooCommerce Tools")
        
        # Khởi tạo database
        logger.info("Initializing database...")
        from app.database import DatabaseManager
        db = DatabaseManager()
        logger.info("Database initialized successfully")
        
        # Tạo main window
        logger.info("Creating main window...")
        from app.main_window import MainWindow
        window = MainWindow()
        window.show()
        
        logger.info("Application started successfully")
        print("✅ Ứng dụng đã khởi động thành công!")
        
        # Chạy ứng dụng
        return app.exec()
        
    except Exception as e:
        error_msg = f"Application error: {str(e)}"
        logger.error(error_msg)
        print(f"❌ Lỗi ứng dụng: {str(e)}")
        
        # In stack trace để debug
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)