
#!/usr/bin/env python3
"""
Ultra-safe Windows launcher for WooCommerce Product Manager
Maximum stability with minimal features to prevent access violations
"""

import sys
import os
import logging
from pathlib import Path
import traceback

def setup_ultra_safe_environment():
    """Setup ultra-safe Windows environment"""
    current_dir = Path(__file__).parent
    sys.path.insert(0, str(current_dir))
    sys.path.insert(0, str(current_dir / 'app'))

    # Ultra-safe PyQt6 settings
    os.environ['QT_QPA_PLATFORM'] = 'windows'
    os.environ['QT_SCALE_FACTOR'] = '1'
    os.environ['QT_AUTO_SCREEN_SCALE_FACTOR'] = '0'
    os.environ['QT_ACCESSIBILITY'] = '0'
    os.environ['QT_LOGGING_RULES'] = '*.debug=false'
    
    # Force software rendering
    os.environ['QT_OPENGL'] = 'software'
    os.environ['QT_ANGLE_PLATFORM'] = 'warp'
    
    # Disable all problematic features
    os.environ['WOOCOMMERCE_DISABLE_IMAGE_THREADING'] = '1'
    os.environ['WOOCOMMERCE_MINIMAL_MODE'] = '1'
    os.environ['WOOCOMMERCE_SAFE_MODE'] = '1'
    os.environ['WOOCOMMERCE_NO_IMAGES'] = '1'
    os.environ['WOOCOMMERCE_FIXED_COLUMNS'] = '1'
    
    # Memory settings
    os.environ['PYTHONMALLOC'] = 'malloc'

class SafeProductManagerTab:
    """Ultra-safe product manager with minimal features"""
    
    def __init__(self, db_manager):
        self.db_manager = db_manager
        self.logger = logging.getLogger(__name__)
        
    def setup_safe_table(self):
        """Setup table with maximum safety"""
        from PyQt6.QtWidgets import QTableWidget, QHeaderView, QAbstractItemView
        from PyQt6.QtCore import Qt
        
        self.table = QTableWidget()
        
        # Minimal columns for safety
        self.columns = ["ID", "Site", "Tên", "SKU", "Giá", "Trạng thái"]
        self.table.setColumnCount(len(self.columns))
        self.table.setHorizontalHeaderLabels(self.columns)
        
        # Ultra-safe table settings
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(False)  # Disable sorting for safety
        
        # Fixed header - no resizing allowed
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        header.setSectionsMovable(False)
        header.setSectionsClickable(False)
        
        # Set fixed widths
        widths = [60, 150, 250, 100, 80, 100]
        for i, width in enumerate(widths):
            header.resizeSection(i, width)
            
        return self.table

def main():
    """Ultra-safe main entry point"""
    try:
        print("🚀 Starting WooCommerce Manager (Ultra-Safe Mode)...")
        print("⚠️  Running with minimal features for maximum stability")

        setup_ultra_safe_environment()

        # Minimal logging
        logging.basicConfig(
            level=logging.WARNING,
            format='%(levelname)s - %(message)s',
            handlers=[logging.StreamHandler(sys.stdout)]
        )

        # Import PyQt6 with ultra-safe configuration
        from PyQt6.QtWidgets import (
            QApplication, QMainWindow, QWidget, QVBoxLayout, 
            QHBoxLayout, QPushButton, QLabel, QMessageBox,
            QTabWidget, QTableWidget, QHeaderView, QAbstractItemView
        )
        from PyQt6.QtCore import Qt

        # Create ultra-safe application
        app = QApplication(sys.argv)
        app.setApplicationName("WooCommerce Manager (Safe)")

        # Minimal attributes (AA_DisableWindowContextHelpButton removed in PyQt6)

        # Ultra-minimal style
        app.setStyleSheet("""
            QWidget { 
                font-family: Arial; 
                font-size: 9pt;
            }
            QTableWidget {
                gridline-color: #ccc;
                background-color: white;
            }
            QPushButton {
                background-color: #0078d4;
                color: white;
                padding: 5px 10px;
                border: none;
            }
        """)

        try:
            # Import minimal components
            from app.database import DatabaseManager
            
            print("Initializing database...")
            db_manager = DatabaseManager()
            db_manager.init_database()
            print("✓ Database ready")

            # Create ultra-safe main window
            class UltraSafeMainWindow(QMainWindow):
                def __init__(self):
                    super().__init__()
                    self.setWindowTitle("WooCommerce Manager (Ultra-Safe Mode)")
                    self.setGeometry(100, 100, 1000, 600)
                    
                    # Central widget
                    central = QWidget()
                    self.setCentralWidget(central)
                    layout = QVBoxLayout(central)
                    
                    # Warning label
                    warning = QLabel("⚠️ Chạy ở chế độ an toàn - một số tính năng bị tắt để tránh crash")
                    warning.setStyleSheet("color: orange; font-weight: bold; padding: 10px;")
                    layout.addWidget(warning)
                    
                    # Safe table
                    safe_manager = SafeProductManagerTab(db_manager)
                    table = safe_manager.setup_safe_table()
                    layout.addWidget(table)
                    
                    # Load basic data
                    self.load_safe_data(table, db_manager)
                    
                def load_safe_data(self, table, db_manager):
                    """Load data safely without images or complex features"""
                    try:
                        products = db_manager.get_all_products()
                        table.setRowCount(len(products))
                        
                        for row, product in enumerate(products):
                            table.setItem(row, 0, table.itemPrototype())
                            table.item(row, 0).setText(str(product.get('id', '')))
                            table.setItem(row, 1, table.itemPrototype())
                            table.item(row, 1).setText(str(product.get('site_name', '')))
                            table.setItem(row, 2, table.itemPrototype())
                            table.item(row, 2).setText(str(product.get('name', '')))
                            table.setItem(row, 3, table.itemPrototype())
                            table.item(row, 3).setText(str(product.get('sku', '')))
                            table.setItem(row, 4, table.itemPrototype())
                            table.item(row, 4).setText(str(product.get('price', '')))
                            table.setItem(row, 5, table.itemPrototype())
                            table.item(row, 5).setText(str(product.get('status', '')))
                            
                        print(f"✓ Loaded {len(products)} products safely")
                        
                    except Exception as e:
                        print(f"⚠️  Error loading data: {e}")

            print("Creating ultra-safe main window...")
            window = UltraSafeMainWindow()
            window.show()
            window.raise_()

            print("✅ Application started in ultra-safe mode!")
            print("💡 Nếu ứng dụng chạy ổn định, thử chế độ bình thường với run_windows_safe.py")

            return app.exec()

        except Exception as e:
            QMessageBox.critical(None, "Error", f"Failed to start:\n{str(e)}")
            traceback.print_exc()
            return 1

    except ImportError as e:
        print(f"❌ Missing dependencies: {e}")
        return 1
    except Exception as e:
        print(f"❌ Startup error: {e}")
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
