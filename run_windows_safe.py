
#!/usr/bin/env python3
"""
Windows-safe launcher for WooCommerce Product Manager
Handles Windows-specific PyQt6 issues and access violations
"""

import sys
import os
import logging
from pathlib import Path
import traceback

def setup_windows_environment():
    """Setup Windows-specific environment variables for maximum stability"""
    # Add current directory to Python path
    current_dir = Path(__file__).parent
    sys.path.insert(0, str(current_dir))
    sys.path.insert(0, str(current_dir / 'app'))
    
    # Windows-specific PyQt6 settings for stability
    os.environ['QT_QPA_PLATFORM'] = 'windows'
    os.environ['QT_SCALE_FACTOR'] = '1'
    os.environ['QT_AUTO_SCREEN_SCALE_FACTOR'] = '0'
    
    # PyQt6 DPI settings (high DPI is enabled by default in PyQt6)
    os.environ['QT_SCALE_FACTOR_ROUNDING_POLICY'] = 'RoundPreferFloor'
    
    # Disable problematic Qt features to prevent crashes
    os.environ['QT_ACCESSIBILITY'] = '0'
    os.environ['QT_LOGGING_RULES'] = '*.debug=false'
    
    # Windows-specific stability settings
    os.environ['QT_OPENGL'] = 'software'  # Use software rendering
    os.environ['QT_ANGLE_PLATFORM'] = 'warp'  # Use WARP for graphics
    
    # Disable hardware acceleration to prevent access violations
    os.environ['QT_NO_GLIB'] = '1'
    os.environ['QT_HASH_SEED'] = '0'
    
    # Application-specific settings for stability
    os.environ['WOOCOMMERCE_DISABLE_IMAGE_THREADING'] = '1'
    os.environ['WOOCOMMERCE_MINIMAL_MODE'] = '1'
    os.environ['WOOCOMMERCE_SAFE_MODE'] = '1'
    
    # Memory management settings
    os.environ['PYTHONMALLOC'] = 'malloc'

def setup_logging():
    """Setup logging for Windows"""
    log_file = "woocommerce_manager.log"
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )

def main():
    """Main entry point for Windows"""
    try:
        print("🚀 Khởi động WooCommerce Product Manager trên Windows (Safe Mode)...")
        
        # Setup Windows environment
        setup_windows_environment()
        setup_logging()
        
        logger = logging.getLogger(__name__)
        
        # Import after environment setup
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtCore import Qt
        from PyQt6.QtGui import QFont
        
        # Create QApplication with Windows-specific attributes
        # Note: AA_EnableHighDpiScaling removed in PyQt6 (enabled by default)
        # AA_DisableWindowContextHelpButton also removed in PyQt6
        
        app = QApplication(sys.argv)
        app.setApplicationName("WooCommerce Product Manager")
        app.setApplicationVersion("1.0.0")
        app.setOrganizationName("WooCommerce Tools")
        
        # Set font for Vietnamese support
        font = QFont("Segoe UI", 9)
        font.setStyleHint(QFont.StyleHint.SansSerif)
        app.setFont(font)
        
        # Apply minimal styles to avoid rendering issues
        app.setStyleSheet("""
            QMainWindow {
                background-color: #f5f5f5;
            }
            QPushButton {
                background-color: #0078d4;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #106ebe;
            }
        """)
        
        # Import app modules after Qt setup
        from app.main_window import MainWindow
        from app.database import DatabaseManager
        
        # Initialize database
        logger.info("Initializing database...")
        db_manager = DatabaseManager()
        db_manager.init_database()
        
        # Create and show main window
        logger.info("Creating main window...")
        window = MainWindow()
        
        # Show window with safe settings
        window.show()
        window.raise_()
        window.activateWindow()
        
        logger.info("✅ Ứng dụng đã khởi chạy thành công trên Windows!")
        print("✅ Ứng dụng đã khởi chạy thành công trên Windows!")
        
        # Run event loop with exception handling
        try:
            # Set exception hook for better error handling
            def handle_exception(exc_type, exc_value, exc_traceback):
                if issubclass(exc_type, KeyboardInterrupt):
                    sys.__excepthook__(exc_type, exc_value, exc_traceback)
                    return
                
                logger.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))
                print(f"❌ Lỗi ứng dụng: {exc_value}")
                
            sys.excepthook = handle_exception
            
            return app.exec()
        except Exception as e:
            logger.error(f"Runtime error: {str(e)}")
            traceback.print_exc()
            return 1
        finally:
            # Cleanup
            try:
                app.quit()
            except:
                pass
        
    except ImportError as e:
        print(f"❌ Lỗi import module: {str(e)}")
        print("Hãy đảm bảo đã cài đặt: pip install PyQt6 requests pandas")
        return 1
    except Exception as e:
        print(f"❌ Lỗi khi khởi chạy ứng dụng: {str(e)}")
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
