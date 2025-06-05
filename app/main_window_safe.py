
"""
Safe Main Window - Phiên bản an toàn của main window
"""

import logging
import os
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QTabWidget, QStatusBar, QMenuBar, QMenu, QMessageBox,
    QProgressBar, QLabel, QToolBar
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QIcon, QKeySequence, QAction

class SafeMainWindow(QMainWindow):
    """Cửa sổ chính an toàn với error handling tốt hơn"""
    
    # Signals
    status_message = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.db_manager = None
        
        try:
            self.init_ui()
            self.create_menu_bar()
            self.create_status_bar()
            self.setup_connections()
            
            # Timer để cập nhật thời gian trên status bar
            self.timer = QTimer()
            self.timer.timeout.connect(self.update_time)
            self.timer.start(1000)
            
            # Delay load data để tránh crash
            QTimer.singleShot(500, self.delayed_load_data)
            
        except Exception as e:
            self.logger.error(f"Error initializing SafeMainWindow: {e}")
            raise
        
    def init_ui(self):
        """Khởi tạo giao diện người dùng an toàn"""
        try:
            self.setWindowTitle("WooCommerce Product Manager (Safe Mode)")
            self.setGeometry(100, 100, 1000, 700)
            self.setMinimumSize(800, 600)
            
            # Thiết lập icon an toàn
            try:
                if os.path.exists("attached_assets/woo-Photoroom.png"):
                    window_icon = QIcon("attached_assets/woo-Photoroom.png")
                    if not window_icon.isNull():
                        self.setWindowIcon(window_icon)
                        self.logger.info("Window icon loaded successfully")
            except Exception as e:
                self.logger.warning(f"Could not load window icon: {e}")
            
            # Widget trung tâm
            central_widget = QWidget()
            self.setCentralWidget(central_widget)
            
            # Layout chính
            layout = QVBoxLayout(central_widget)
            layout.setContentsMargins(10, 10, 10, 10)
            
            # Tạo tab widget
            self.tab_widget = QTabWidget()
            self.tab_widget.setTabPosition(QTabWidget.TabPosition.North)
            
            # Tạo các tab an toàn
            self.create_safe_tabs()
            
            layout.addWidget(self.tab_widget)
            
        except Exception as e:
            self.logger.error(f"Error in init_ui: {e}")
            raise
            
    def create_safe_tabs(self):
        """Tạo các tab một cách an toàn"""
        try:
            # Tab thông tin đơn giản
            info_tab = QWidget()
            info_layout = QVBoxLayout(info_tab)
            
            info_label = QLabel("""
                <h2>🚀 WooCommerce Product Manager</h2>
                <p><strong>Phiên bản:</strong> 1.0.0 (Safe Mode)</p>
                <p><strong>Trạng thái:</strong> Ứng dụng đang chạy trong chế độ an toàn</p>
                <br>
                <h3>📋 Tính năng chính:</h3>
                <ul>
                    <li>🌐 Quản lý nhiều site WooCommerce</li>
                    <li>📦 Quản lý sản phẩm</li>
                    <li>📁 Quản lý danh mục</li>
                    <li>📄 Quản lý trang</li>
                    <li>📂 Quét thư mục</li>
                </ul>
                <br>
                <p><em>Các tab khác sẽ được tải dần để tránh crash...</em></p>
            """)
            info_label.setWordWrap(True)
            info_layout.addWidget(info_label)
            
            self.tab_widget.addTab(info_tab, "ℹ️ Thông tin")
            
            # Load các tab khác từ từ
            QTimer.singleShot(1000, self.load_site_manager_tab)
            QTimer.singleShot(2000, self.load_product_manager_tab)
            QTimer.singleShot(3000, self.load_other_tabs)
            
        except Exception as e:
            self.logger.error(f"Error creating safe tabs: {e}")
    
    def load_site_manager_tab(self):
        """Load tab quản lý sites"""
        try:
            from .site_manager import SiteManagerTab
            
            self.site_manager_tab = SiteManagerTab()
            self.site_manager_tab.db_manager = self.db_manager
            self.tab_widget.addTab(self.site_manager_tab, "🌐 Quản lý Site")
            
            # Kết nối signals
            self.site_manager_tab.status_message.connect(self.status_message)
            
            self.logger.info("Site manager tab loaded")
            
        except Exception as e:
            self.logger.error(f"Error loading site manager tab: {e}")
            self.show_error_tab("Site Manager", str(e))
    
    def load_product_manager_tab(self):
        """Load tab quản lý sản phẩm"""
        try:
            from .product_manager import ProductManagerTab
            
            self.product_manager_tab = ProductManagerTab()
            self.product_manager_tab.db_manager = self.db_manager
            self.tab_widget.addTab(self.product_manager_tab, "📦 Quản lý Sản phẩm")
            
            # Kết nối signals
            self.product_manager_tab.status_message.connect(self.status_message)
            
            self.logger.info("Product manager tab loaded")
            
        except Exception as e:
            self.logger.error(f"Error loading product manager tab: {e}")
            self.show_error_tab("Product Manager", str(e))
    
    def load_other_tabs(self):
        """Load các tab khác"""
        # Load Category Manager
        try:
            from .category_manager import CategoryManagerTab
            
            self.category_manager_tab = CategoryManagerTab()
            self.category_manager_tab.db_manager = self.db_manager
            self.tab_widget.addTab(self.category_manager_tab, "📁 Quản lý Danh mục")
            
            self.logger.info("Category manager tab loaded")
            
        except Exception as e:
            self.logger.error(f"Error loading category manager tab: {e}")
            self.show_error_tab("Category Manager", str(e))
        
        # Load Page Manager
        try:
            from .page_manager import PageManagerTab
            
            self.page_manager_tab = PageManagerTab()
            self.page_manager_tab.db_manager = self.db_manager
            self.tab_widget.addTab(self.page_manager_tab, "📄 Quản lý Trang")
            
            self.logger.info("Page manager tab loaded")
            
        except Exception as e:
            self.logger.error(f"Error loading page manager tab: {e}")
            self.show_error_tab("Page Manager", str(e))
        
        # Load Folder Scanner (có thể gây crash nhiều nhất)
        try:
            from .folder_scanner import FolderScannerTab
            
            self.folder_scanner_tab = FolderScannerTab()
            self.folder_scanner_tab.db_manager = self.db_manager
            self.tab_widget.addTab(self.folder_scanner_tab, "📂 Quét thư mục")
            
            self.logger.info("Folder scanner tab loaded")
            
        except Exception as e:
            self.logger.error(f"Error loading folder scanner tab: {e}")
            self.show_error_tab("Folder Scanner", str(e))
    
    def show_error_tab(self, tab_name: str, error_msg: str):
        """Hiển thị tab lỗi thay vì tab bị crash"""
        error_tab = QWidget()
        error_layout = QVBoxLayout(error_tab)
        
        error_label = QLabel(f"""
            <h3>❌ Lỗi tải {tab_name}</h3>
            <p><strong>Chi tiết lỗi:</strong></p>
            <pre>{error_msg}</pre>
            <br>
            <p><em>Tab này có thể được tải lại sau khi khắc phục lỗi.</em></p>
        """)
        error_label.setWordWrap(True)
        error_layout.addWidget(error_label)
        
        self.tab_widget.addTab(error_tab, f"❌ {tab_name}")
        
    def create_menu_bar(self):
        """Tạo menu bar đơn giản"""
        try:
            menubar = self.menuBar()
            
            # Menu File
            file_menu = menubar.addMenu("&File")
            
            # Exit
            exit_action = QAction("❌ Thoát", self)
            exit_action.setShortcut(QKeySequence.StandardKey.Quit)
            exit_action.triggered.connect(self.close)
            file_menu.addAction(exit_action)
            
            # Menu Help
            help_menu = menubar.addMenu("&Help")
            
            # About
            about_action = QAction("ℹ️ Về ứng dụng", self)
            about_action.triggered.connect(self.show_about)
            help_menu.addAction(about_action)
            
        except Exception as e:
            self.logger.error(f"Error creating menu bar: {e}")
        
    def create_status_bar(self):
        """Tạo status bar"""
        try:
            self.status_bar = QStatusBar()
            self.setStatusBar(self.status_bar)
            
            # Label cho thời gian
            self.time_label = QLabel()
            self.status_bar.addPermanentWidget(self.time_label)
            
            # Hiển thị thông báo khởi tạo
            self.status_bar.showMessage("Safe mode - Sẵn sàng", 2000)
            
        except Exception as e:
            self.logger.error(f"Error creating status bar: {e}")
        
    def delayed_load_data(self):
        """Load data sau khi UI đã được khởi tạo hoàn toàn"""
        try:
            if hasattr(self, 'site_manager_tab') and hasattr(self.site_manager_tab, 'load_sites'):
                self.site_manager_tab.load_sites()
                
        except Exception as e:
            self.logger.error(f"Error in delayed_load_data: {e}")

    def setup_connections(self):
        """Thiết lập kết nối signals/slots"""
        try:
            self.status_message.connect(self.status_bar.showMessage)
        except Exception as e:
            self.logger.error(f"Error setting up connections: {e}")
        
    def update_time(self):
        """Cập nhật thời gian trên status bar"""
        try:
            from datetime import datetime
            current_time = datetime.now().strftime("%H:%M:%S - %d/%m/%Y")
            self.time_label.setText(f"Safe Mode | {current_time}")
        except Exception as e:
            self.logger.error(f"Error updating time: {e}")
            
    def show_about(self):
        """Hiển thị thông tin về ứng dụng"""
        try:
            QMessageBox.about(self, "Về ứng dụng", 
                             "WooCommerce Product Manager v1.0.0 (Safe Mode)\n\n"
                             "Ứng dụng quản lý sản phẩm đa site WooCommerce\n"
                             "Chạy trong chế độ an toàn để tránh crash\n\n"
                             "Tính năng:\n"
                             "• Quản lý nhiều site WooCommerce\n"
                             "• CRUD sản phẩm\n"
                             "• Import/Export CSV\n"
                             "• Đồng bộ dữ liệu\n"
                             "• Tìm kiếm và lọc")
        except Exception as e:
            self.logger.error(f"Error showing about: {e}")
                             
    def closeEvent(self, event):
        """Xử lý sự kiện đóng ứng dụng"""
        try:
            reply = QMessageBox.question(self, "Xác nhận", 
                                       "Bạn có chắc chắn muốn thoát ứng dụng?",
                                       QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                       QMessageBox.StandardButton.No)
            
            if reply == QMessageBox.StandardButton.Yes:
                self.logger.info("Closing application (safe mode)")
                event.accept()
            else:
                event.ignore()
        except Exception as e:
            self.logger.error(f"Error in closeEvent: {e}")
            event.accept()  # Cho phép đóng nếu có lỗi
