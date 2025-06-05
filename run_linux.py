#!/usr/bin/env python3
"""
Linux launcher for WooCommerce Product Manager
Optimized for Linux/VNC environment
"""

import sys
import os
import logging
from pathlib import Path

def setup_linux_environment():
    """Setup Linux environment for PyQt6"""
    current_dir = Path(__file__).parent
    sys.path.insert(0, str(current_dir))
    sys.path.insert(0, str(current_dir / 'app'))

    # Linux PyQt6 settings
    os.environ['QT_QPA_PLATFORM'] = 'xcb'
    os.environ['DISPLAY'] = ':1'
    os.environ['QT_SCALE_FACTOR'] = '1'
    os.environ['QT_AUTO_SCREEN_SCALE_FACTOR'] = '0'
    os.environ['QT_LOGGING_RULES'] = '*.debug=false'
    
    # Disable problematic features for stability
    os.environ['WOOCOMMERCE_DISABLE_IMAGE_THREADING'] = '1'
    os.environ['QT_X11_NO_MITSHM'] = '1'

def setup_logging():
    """Setup logging for Linux"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('woocommerce_manager.log', encoding='utf-8'),
            logging.StreamHandler()
        ]
    )

def main():
    """Main entry point for Linux"""
    print("🚀 Starting WooCommerce Product Manager (Linux Mode)...")
    
    try:
        setup_linux_environment()
        setup_logging()
        
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtCore import Qt
        
        # Create application with safe settings
        app = QApplication(sys.argv)
        app.setAttribute(Qt.ApplicationAttribute.AA_DisableWindowContextHelpButton)
        app.setQuitOnLastWindowClosed(True)
        
        # Import and create main window
        from app.main_window import MainWindow
        
        window = MainWindow()
        window.show()
        
        logging.info("Ứng dụng đã khởi động thành công trên Linux")
        print("✅ Ứng dụng đã khởi động thành công!")
        
        return app.exec()
        
    except Exception as e:
        error_msg = f"Lỗi khởi động ứng dụng: {str(e)}"
        print(f"❌ {error_msg}")
        logging.error(error_msg, exc_info=True)
        return 1

if __name__ == "__main__":
    sys.exit(main())