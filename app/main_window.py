"""
Main Window - Cửa sổ chính của ứng dụng

COMPONENT OVERVIEW:
------------------
Cửa sổ chính chứa giao diện tab cho ứng dụng WooCommerce Product Manager.
Bao gồm menu bar, toolbar, status bar và hai tab chính:
- Tab 1: Quản lý Sites WooCommerce 
- Tab 2: Quản lý Sản phẩm

FEATURES:
---------
- Tab-based interface với PyQt6 QTabWidget
- Menu system với shortcuts
- Toolbar với quick actions
- Status bar với thời gian và progress indicator
- Signal/slot connections giữa các components
- Auto-refresh functionality

SIGNALS:
--------
- status_message(str): Hiển thị thông báo trên status bar
- progress_started(): Bắt đầu hiển thị progress bar
- progress_finished(): Ẩn progress bar

DEPENDENCIES:
-------------
- SiteManagerTab: Tab quản lý sites
- ProductManagerTab: Tab quản lý sản phẩm  
- DatabaseManager: Quản lý SQLite database
"""

import logging
import os
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QTabWidget, QStatusBar, QMenuBar, QMenu, QMessageBox,
    QProgressBar, QLabel, QToolBar
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QIcon, QKeySequence, QAction, QPixmap, QPainter, QBrush

from .site_manager import SiteManagerTab
from .product_manager import ProductManagerTab
from .category_manager import CategoryManagerTab
from app.page_manager import PageManagerTab
from .folder_scanner import FolderScannerTab
from .database import DatabaseManager
# Assuming DataManagerTab is in data_manager.py
from .data_manager import DataManagerTab


class MainWindow(QMainWindow):
    """Cửa sổ chính của ứng dụng"""

    # Signals
    status_message = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.db_manager = DatabaseManager()

        self.init_ui()
        self.create_menu_bar()
        self.create_tool_bar()
        self.create_status_bar()
        self.setup_connections()

        # Timer để cập nhật thời gian trên status bar
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_time)
        self.timer.start(1000)

    def init_ui(self):
        """Khởi tạo giao diện người dùng"""
        self.setWindowTitle("WooCommerce Product Manager")
        self.setGeometry(100, 100, 1200, 800)
        self.setMinimumSize(1000, 600)

        # Thiết lập icon cho cửa sổ - tạo icon mặc định nếu không có file
        try:
            window_icon = self.create_default_icon()
            if window_icon and not window_icon.isNull():
                self.setWindowIcon(window_icon)
                self.logger.info("Đã thiết lập icon cho cửa sổ chính")
            else:
                # Bỏ qua icon nếu không tạo được
                self.logger.info("Ứng dụng khởi động thành công")

        except Exception as e:
            self.logger.info("Ứng dụng khởi động thành công")

        # Widget trung tâm
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Layout chính
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(5, 5, 5, 5)

        # Tạo tab widget
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabPosition(QTabWidget.TabPosition.North)
        self.tab_widget.setMovable(True)

        # Tạo các tab
        self.site_manager_tab = SiteManagerTab()
        self.site_manager_tab.db_manager = self.db_manager

        self.product_manager_tab = ProductManagerTab()
        self.product_manager_tab.db_manager = self.db_manager

        self.category_manager_tab = CategoryManagerTab()
        self.category_manager_tab.db_manager = self.db_manager

        self.page_manager_tab = PageManagerTab()
        self.page_manager_tab.db_manager = self.db_manager

        # Khởi tạo FolderScannerTab với error handling
        try:
            self.folder_scanner_tab = FolderScannerTab()
            self.folder_scanner_tab.db_manager = self.db_manager
        except Exception as e:
            self.logger.error(f"Error initializing FolderScannerTab: {e}")
            # Tạo tab replacement đơn giản
            self.folder_scanner_tab = QWidget()
            layout = QVBoxLayout(self.folder_scanner_tab)
            error_label = QLabel(f"Lỗi khởi tạo tab quét thư mục: {e}")
            layout.addWidget(error_label)

        # Delay load data để tránh access violation khi khởi tạo
        QTimer.singleShot(200, self.delayed_load_data)

        # Thêm các tab vào tab widget
        self.tab_widget.addTab(self.site_manager_tab, "🌐 Quản lý Site")
        self.tab_widget.addTab(self.product_manager_tab, "📦 Quản lý Sản phẩm")
        self.tab_widget.addTab(self.category_manager_tab, "📁 Quản lý Danh mục")
        self.tab_widget.addTab(self.page_manager_tab, "📄 Quản lý Trang")
        self.tab_widget.addTab(self.folder_scanner_tab, "📂 Quét thư mục")

        # Tab Quản lý Data
        try:
            self.data_manager_tab = DataManagerTab()
            self.data_manager_tab.db_manager = self.db_manager # Assuming the tab uses db_manager
            self.tab_widget.addTab(self.data_manager_tab, "📊 Quản lý Data")
        except Exception as e:
            self.logger.error(f"Error creating Data Manager tab: {str(e)}")
            # Thêm tab placeholder nếu lỗi
            error_tab = QWidget()
            error_layout = QVBoxLayout(error_tab)
            error_label = QLabel(f"Lỗi tải Data Manager: {str(e)}")
            error_layout.addWidget(error_label)
            self.tab_widget.addTab(error_tab, "❌ Data Manager")

        layout.addWidget(self.tab_widget)

    def create_menu_bar(self):
        """Tạo menu bar"""
        menubar = self.menuBar()

        # Menu File
        file_menu = menubar.addMenu("&File")

        # Import CSV
        import_action = QAction("📥 Import CSV", self)
        import_action.setShortcut(QKeySequence.StandardKey.Open)
        import_action.triggered.connect(self.import_csv)
        file_menu.addAction(import_action)

        # Export CSV
        export_action = QAction("📤 Export CSV", self)
        export_action.setShortcut(QKeySequence.StandardKey.SaveAs)
        export_action.triggered.connect(self.export_csv)
        file_menu.addAction(export_action)

        file_menu.addSeparator()

        # Exit
        exit_action = QAction("❌ Thoát", self)
        exit_action.setShortcut(QKeySequence.StandardKey.Quit)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Menu Tools
        tools_menu = menubar.addMenu("&Tools")

        # Refresh All
        refresh_action = QAction("🔄 Làm mới tất cả", self)
        refresh_action.setShortcut(QKeySequence.StandardKey.Refresh)
        refresh_action.triggered.connect(self.refresh_all)
        tools_menu.addAction(refresh_action)

        # Sync Products
        sync_action = QAction("🔄 Đồng bộ sản phẩm", self)
        sync_action.triggered.connect(self.sync_products)
        tools_menu.addAction(sync_action)

        # Menu Help
        help_menu = menubar.addMenu("&Help")

        # About
        about_action = QAction("ℹ️ Về ứng dụng", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def create_tool_bar(self):
        """Tạo toolbar"""
        toolbar = QToolBar("Main Toolbar")
        self.addToolBar(toolbar)

        # Refresh button
        refresh_action = QAction("🔄", self)
        refresh_action.setToolTip("Làm mới dữ liệu")
        refresh_action.triggered.connect(self.refresh_all)
        toolbar.addAction(refresh_action)

        toolbar.addSeparator()

        # Import button
        import_action = QAction("📥", self)
        import_action.setToolTip("Import CSV")
        import_action.triggered.connect(self.import_csv)
        toolbar.addAction(import_action)

        # Export button
        export_action = QAction("📤", self)
        export_action.setToolTip("Export CSV")
        export_action.triggered.connect(self.export_csv)
        toolbar.addAction(export_action)

        toolbar.addSeparator()

        # Sync button
        sync_action = QAction("🔄", self)
        sync_action.setToolTip("Đồng bộ sản phẩm")
        sync_action.triggered.connect(self.sync_products)
        toolbar.addAction(sync_action)

    def create_status_bar(self):
        """Tạo status bar"""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        # Label cho thời gian
        self.time_label = QLabel()
        self.status_bar.addPermanentWidget(self.time_label)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.status_bar.addPermanentWidget(self.progress_bar)

        # Hiển thị thông báo khởi tạo
        self.status_bar.showMessage("Sẵn sàng", 2000)

    def delayed_load_data(self):
        """Load data sau khi UI đã được khởi tạo hoàn toàn"""
        try:
            # Load sites với error handling
            if hasattr(self.site_manager_tab, 'load_sites'):
                try:
                    self.site_manager_tab.load_sites()
                    print("Đã load sites thành công")
                except Exception as e:
                    print(f"Lỗi load sites: {e}")

            # Load categories với error handling
            if hasattr(self.category_manager_tab, 'load_sites'):
                try:
                    self.category_manager_tab.load_sites()
                    print("Đã load categories sites thành công")
                except Exception as e:
                    print(f"Lỗi load categories sites: {e}")

            # Load product data
            if hasattr(self.product_manager_tab, 'load_data'):
                try:
                    self.product_manager_tab.load_data()
                    print("Đã load products thành công")
                except Exception as e:
                    print(f"Lỗi load products: {e}")

            # Tạm thời bỏ qua folder scanner để tránh lỗi
            # if hasattr(self.folder_scanner_tab, 'load_data'):
            #     self.folder_scanner_tab.load_data()

        except Exception as e:
            print(f"Lỗi load data: {str(e)}")

    def setup_connections(self):
        """Thiết lập kết nối signals/slots"""
        # Kết nối signal status_message
        self.status_message.connect(self.status_bar.showMessage)

        # Kết nối từ các tab
        self.site_manager_tab.status_message.connect(self.status_bar.showMessage)
        self.product_manager_tab.status_message.connect(self.status_bar.showMessage)

        # Kết nối progress signals
        self.site_manager_tab.progress_started.connect(self.show_progress)
        self.site_manager_tab.progress_finished.connect(self.hide_progress)
        self.product_manager_tab.progress_started.connect(self.show_progress)
        self.product_manager_tab.progress_finished.connect(self.hide_progress)

    def update_time(self):
        """Cập nhật thời gian trên status bar"""
        from datetime import datetime
        current_time = datetime.now().strftime("%H:%M:%S - %d/%m/%Y")
        self.time_label.setText(current_time)

    def show_progress(self):
        """Hiển thị progress bar"""
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminate progress

    def hide_progress(self):
        """Ẩn progress bar"""
        self.progress_bar.setVisible(False)

    def refresh_all(self):
        """Làm mới tất cả dữ liệu"""
        try:
            self.show_progress()
            self.status_message.emit("Đang làm mới dữ liệu...")

            # Refresh site manager
            self.site_manager_tab.refresh_data()

            # Refresh product manager
            self.product_manager_tab.refresh_data()

            self.status_message.emit("Đã làm mới dữ liệu thành công")

        except Exception as e:
            self.logger.error(f"Lỗi khi làm mới dữ liệu: {str(e)}")
            QMessageBox.critical(self, "Lỗi", f"Không thể làm mới dữ liệu:\n{str(e)}")
        finally:
            self.hide_progress()

    def import_csv(self):
        """Import dữ liệu từ CSV"""
        current_tab = self.tab_widget.currentWidget()
        if hasattr(current_tab, 'import_csv'):
            current_tab.import_csv()
        else:
            QMessageBox.information(self, "Thông báo", "Chức năng import không khả dụng cho tab này")

    def export_csv(self):
        """Export dữ liệu ra CSV"""
        current_tab = self.tab_widget.currentWidget()
        if hasattr(current_tab, 'export_csv'):
            current_tab.export_csv()
        else:
            QMessageBox.information(self, "Thông báo", "Chức năng export không khả dụng cho tab này")

    def sync_products(self):
        """Đồng bộ sản phẩm từ các site"""
        if self.tab_widget.currentWidget() == self.product_manager_tab:
            self.product_manager_tab.sync_all_products()
        else:
            # Switch to product tab and sync
            self.tab_widget.setCurrentWidget(self.product_manager_tab)
            self.product_manager_tab.sync_all_products()

    def show_about(self):
        """Hiển thị thông tin về ứng dụng"""
        about_text = f"""
        <h2>WooCommerce Product Manager v1.0.0</h2>
        <p><b>Ứng dụng quản lý sản phẩm đa site WooCommerce</b></p>
        <p>Hỗ trợ kết nối và quản lý sản phẩm từ nhiều cửa hàng WooCommerce</p>

        <h3>Tính năng:</h3>
        <ul>
        <li>• Quản lý nhiều site WooCommerce</li>
        <li>• CRUD sản phẩm</li>
        <li>• Import/Export CSV</li>
        <li>• Đồng bộ dữ liệu</li>
        <li>• Tìm kiếm và lọc</li>
        </ul>

        <h3>Tác giả:</h3>
        <p><b>Học Trần</b></p>
        <p>Telegram: <a href="https://t.me/anh2nd">@anh2nd</a></p>
        """

        QMessageBox.about(self, "Về ứng dụng", about_text)

    def create_default_icon(self):
        """Tạo icon mặc định đơn giản"""
        try:
            # Thử load từ file trước
            if os.path.exists("attached_assets/woo-Photoroom.png"):
                return QIcon("attached_assets/woo-Photoroom.png")
            elif os.path.exists("icon.png"):
                return QIcon("icon.png")

            # Tạo icon đơn giản bằng code
            pixmap = QPixmap(32, 32)
            pixmap.fill(Qt.GlobalColor.blue)
            return QIcon(pixmap)

        except Exception:
            # Trả về icon rỗng nếu không tạo được
            return QIcon()

    def closeEvent(self, event):
        """Xử lý sự kiện đóng ứng dụng"""
        reply = QMessageBox.question(self, "Xác nhận", 
                                   "Bạn có chắc chắn muốn thoát ứng dụng?",
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                   QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.Yes:
            self.logger.info("Đóng ứng dụng")
            event.accept()
        else:
            event.ignore()