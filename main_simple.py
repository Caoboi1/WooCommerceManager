
#!/usr/bin/env python3
"""
WooCommerce Product Manager - Simplified Entry Point
Phiên bản đơn giản để tránh lỗi DoubleClick
"""

import sys
import os
import logging

# Thiết lập môi trường Qt an toàn
os.environ['QT_QPA_PLATFORM'] = 'xcb'
os.environ['QT_LOGGING_RULES'] = '*.debug=false'
os.environ['QT_AUTO_SCREEN_SCALE_FACTOR'] = '0'

# Thiết lập logging đơn giản
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

# Add app directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

def main():
    """Hàm main đơn giản"""
    try:
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtCore import Qt
        
        # Tạo QApplication với cấu hình tối thiểu
        app = QApplication(sys.argv)
        app.setApplicationName("WooCommerce Product Manager")
        app.setQuitOnLastWindowClosed(True)
        
        # Import database manager
        from app.database import DatabaseManager
        print("Khởi tạo database...")
        db_manager = DatabaseManager()
        db_manager.init_database()
        print("Database đã sẵn sàng")
        
        # Thử tạo main window đơn giản
        try:
            from app.main_window import MainWindow
            window = MainWindow()
            window.db_manager = db_manager
            window.show()
            print("Ứng dụng đã khởi động thành công")
        except Exception as e:
            print(f"Lỗi tạo main window: {e}")
            # Fallback: tạo window đơn giản
            from PyQt6.QtWidgets import QMainWindow, QLabel, QVBoxLayout, QWidget
            
            window = QMainWindow()
            window.setWindowTitle("WooCommerce Product Manager - Safe Mode")
            window.setGeometry(100, 100, 800, 600)
            
            central_widget = QWidget()
            layout = QVBoxLayout(central_widget)
            
            label = QLabel("WooCommerce Product Manager đang chạy trong Safe Mode")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(label)
            
            window.setCentralWidget(central_widget)
            window.show()
            print("Chạy trong Safe Mode")
        
        return app.exec()
        
    except Exception as e:
        print(f"Lỗi khởi chạy: {e}")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
