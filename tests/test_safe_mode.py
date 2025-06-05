
import sys
import os
import logging

# Thiết lập logging trước khi import PyQt6
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

try:
    # Test import PyQt6 components
    from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel
    from PyQt6.QtCore import Qt
    
    # Test tạo QApplication
    app = QApplication(sys.argv)
    app.setApplicationName("Safe Mode Test")
    
    # Test tạo cửa sổ đơn giản
    window = QWidget()
    window.setWindowTitle("Safe Mode Test")
    window.setGeometry(100, 100, 400, 300)
    
    layout = QVBoxLayout(window)
    label = QLabel("PyQt6 Test - Safe Mode")
    layout.addWidget(label)
    
    window.show()
    
    print("✅ PyQt6 test thành công!")
    
    # Test database
    sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))
    from app.database import DatabaseManager
    
    db = DatabaseManager()
    db.init_database()
    print("✅ Database test thành công!")
    
    # Test main window creation
    from app.main_window import MainWindow
    main_window = MainWindow()
    print("✅ Main window test thành công!")
    
    # Chạy 5 giây rồi thoát
    from PyQt6.QtCore import QTimer
    QTimer.singleShot(5000, app.quit)
    
    sys.exit(app.exec())
    
except Exception as e:
    print(f"❌ Lỗi trong safe mode test: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
