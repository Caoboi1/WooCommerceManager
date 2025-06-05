#!/usr/bin/env python3
"""
Ultra-minimal Windows launcher for WooCommerce Product Manager
Prevents access violations by using minimal GUI operations
"""

import sys
import os
import logging
from pathlib import Path

def setup_minimal_environment():
    """Setup minimal Windows environment"""
    current_dir = Path(__file__).parent
    sys.path.insert(0, str(current_dir))
    sys.path.insert(0, str(current_dir / 'app'))

    # Minimal PyQt6 settings for Windows
    os.environ['QT_QPA_PLATFORM'] = 'windows'
    os.environ['QT_SCALE_FACTOR'] = '1'
    os.environ['QT_AUTO_SCREEN_SCALE_FACTOR'] = '0'
    os.environ['QT_ACCESSIBILITY'] = '0'
    os.environ['QT_LOGGING_RULES'] = '*.debug=false'

    # Disable problematic features
    os.environ['WOOCOMMERCE_DISABLE_IMAGE_THREADING'] = '1'
    os.environ['WOOCOMMERCE_MINIMAL_MODE'] = '1'

def main():
    """Minimal main entry point"""
    try:
        print("🚀 Starting WooCommerce Manager (Minimal Mode)...")

        setup_minimal_environment()

        # Setup basic logging
        logging.basicConfig(
            level=logging.WARNING,  # Reduce log verbosity
            format='%(levelname)s - %(message)s',
            handlers=[logging.StreamHandler(sys.stdout)]
        )

        # Import PyQt6 with minimal configuration
        from PyQt6.QtWidgets import QApplication, QMessageBox
        from PyQt6.QtCore import Qt, QFont
        from PyQt6.QtGui import QIcon

        def setup_app_icon(app):
            """Set application icon"""
            app_icon = QIcon("app/images/woocommerce.png")  # Replace with your icon path
            app.setWindowIcon(app_icon)


        # Create minimal application
        app = QApplication(sys.argv)
        app.setApplicationName("WooCommerce Product Manager")
        app.setApplicationVersion("1.0.0")

        # Setup application icon
        setup_app_icon(app)

        # Set font for Vietnamese
        app.setFont(QFont("Segoe UI", 9))

        # Set minimal attributes (AA_DisableWindowContextHelpButton removed in PyQt6)

        # Minimal style to prevent rendering issues
        app.setStyleSheet("QWidget { font-family: Arial; }")

        try:
            # Import components after Qt setup
            from app.database import DatabaseManager
            from app.main_window import MainWindow

            # Initialize database
            print("Initializing database...")
            db_manager = DatabaseManager()
            db_manager.init_database()
            print("✓ Database ready")

            # Create main window with error handling
            print("Creating main window...")
            window = MainWindow()

            # Show window carefully
            window.show()
            window.raise_()

            print("✅ Application started successfully!")

            # Run with exception handling
            return app.exec()

        except Exception as e:
            QMessageBox.critical(None, "Error", f"Failed to start application:\n{str(e)}")
            return 1

    except ImportError as e:
        print(f"❌ Missing dependencies: {e}")
        print("Please install: pip install PyQt6 requests pandas")
        return 1
    except Exception as e:
        print(f"❌ Startup error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())