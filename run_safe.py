
#!/usr/bin/env python3
"""
Safe launcher for WooCommerce Product Manager
Prevents access violations on Windows
"""

import sys
import os
import logging
from pathlib import Path

def setup_safe_environment():
    """Setup safe environment"""
    current_dir = Path(__file__).parent
    sys.path.insert(0, str(current_dir))
    sys.path.insert(0, str(current_dir / 'app'))

    # Safe PyQt6 settings
    os.environ['QT_QPA_PLATFORM'] = 'windows'
    os.environ['QT_SCALE_FACTOR'] = '1'
    os.environ['QT_AUTO_SCREEN_SCALE_FACTOR'] = '0'
    os.environ['QT_LOGGING_RULES'] = '*.debug=false'
    
    # Disable threading for images
    os.environ['WOOCOMMERCE_DISABLE_IMAGE_THREADING'] = '1'

def setup_logging():
    """Setup basic logging"""
    logging.basicConfig(
        level=logging.WARNING,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('woocommerce_manager.log', encoding='utf-8'),
            logging.StreamHandler()
        ]
    )

def main():
    """Safe main entry point"""
    try:
        print("🚀 Starting WooCommerce Product Manager (Safe Mode)...")
        
        setup_safe_environment()
        setup_logging()
        
        from PyQt6.QtWidgets import QApplication, QMessageBox
        from PyQt6.QtCore import Qt
        from PyQt6.QtGui import QFont
        
        # Create application with minimal attributes
        app = QApplication(sys.argv)
        app.setApplicationName("WooCommerce Product Manager")
        
        # Set font for Vietnamese support
        app.setFont(QFont("Arial", 10))
        
        # Minimal styles
        app.setStyleSheet("""
            QWidget { font-family: Arial; }
            QMainWindow { background-color: #f5f5f5; }
            QPushButton { 
                background-color: #0078d4; 
                color: white; 
                border: none; 
                padding: 8px 16px; 
                border-radius: 4px; 
            }
        """)
        
        try:
            from app.database import DatabaseManager
            from app.main_window import MainWindow
            
            # Initialize database
            print("Initializing database...")
            db_manager = DatabaseManager()
            db_manager.init_database()
            print("✓ Database ready")
            
            # Create main window
            print("Creating main window...")
            window = MainWindow()
            window.show()
            
            print("✅ Application started successfully!")
            return app.exec()
            
        except Exception as e:
            QMessageBox.critical(None, "Error", f"Failed to start:\n{str(e)}")
            return 1
            
    except ImportError as e:
        print(f"❌ Missing dependencies: {e}")
        return 1
    except Exception as e:
        print(f"❌ Startup error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
