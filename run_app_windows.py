
#!/usr/bin/env python3
"""
Windows-specific launcher for WooCommerce Product Manager
Handles Windows-specific PyQt6 issues and access violations
"""

import sys
import os
import logging
from pathlib import Path

def setup_windows_environment():
    """Setup Windows-specific environment variables"""
    # Add current directory to Python path
    current_dir = Path(__file__).parent
    sys.path.insert(0, str(current_dir))
    sys.path.insert(0, str(current_dir / 'app'))
    
    # Windows-specific PyQt6 settings
    os.environ['QT_QPA_PLATFORM'] = 'windows'
    os.environ['QT_SCALE_FACTOR'] = '1'
    os.environ['QT_AUTO_SCREEN_SCALE_FACTOR'] = '1'
    
    # Disable high DPI scaling issues
    os.environ['QT_ENABLE_HIGHDPI_SCALING'] = '0'
    os.environ['QT_SCALE_FACTOR_ROUNDING_POLICY'] = 'RoundPreferFloor'

def setup_logging():
    """Setup logging for Windows"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('woocommerce_manager.log', encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )

def main():
    """Main entry point for Windows"""
    try:
        print("🚀 Khởi động WooCommerce Product Manager trên Windows...")
        
        # Setup Windows environment
        setup_windows_environment()
        setup_logging()
        
        # Import after environment setup
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtCore import Qt
        from PyQt6.QtGui import QFont
        
        # Import app modules
        from app.main_window import MainWindow
        from app.database import DatabaseManager
        
        # Create QApplication with Windows-specific attributes
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, False)
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_DisableWindowContextHelpButton, True)
        
        app = QApplication(sys.argv)
        app.setApplicationName("WooCommerce Product Manager")
        app.setApplicationVersion("1.0.0")
        app.setOrganizationName("WooCommerce Tools")
        
        # Thiết lập icon cho ứng dụng trên Windows
        try:
            from PyQt6.QtGui import QIcon
            app_icon = QIcon("icon.png")
            app.setWindowIcon(app_icon)
            print("✅ Đã thiết lập icon cho ứng dụng")
        except Exception as e:
            print(f"⚠️ Không thể load icon: {str(e)}")
        
        # Set font for Vietnamese support
        app.setFont(QFont("Segoe UI", 9))
        
        # Apply styles
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
            QTableWidget {
                gridline-color: #d0d0d0;
                background-color: white;
                alternate-background-color: #f8f8f8;
            }
        """)
        
        # Initialize database
        db_manager = DatabaseManager()
        db_manager.init_database()
        
        # Create and show main window
        window = MainWindow()
        window.show()
        
        print("✅ Ứng dụng đã khởi chạy thành công trên Windows!")
        
        # Run event loop
        return app.exec()
        
    except Exception as e:
        print(f"❌ Lỗi khi khởi chạy ứng dụng: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
