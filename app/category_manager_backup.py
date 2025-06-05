"""
Category Manager - Tab quản lý danh mục sản phẩm
"""

import logging
from typing import List, Dict, Optional
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *

from .models import Site
from .database import DatabaseManager
from .woocommerce_api import WooCommerceAPI
from .category_dialog import CategoryDialog


class CategorySyncWorker(QThread):
    """Worker thread để đồng bộ categories"""
    
    progress_updated = pyqtSignal(int, str)  # progress value, status message
    finished = pyqtSignal(bool, str)  # success, message
    category_synced = pyqtSignal(dict)  # category data
    
    def __init__(self, site: Site):
        super().__init__()
        self.site = site
        self.logger = logging.getLogger(__name__)
    
    def run(self):
        """Thực hiện đồng bộ categories"""
        try:
            self.progress_updated.emit(10, f"Kết nối đến {self.site.name}...")
            
            # Khởi tạo API
            api = WooCommerceAPI(self.site)
            
            self.progress_updated.emit(30, "Lấy danh sách categories...")
            
            # Lấy tất cả categories từ WooCommerce
            categories = api.get_categories()
            
            if not categories:
                self.finished.emit(False, "Không thể lấy dữ liệu categories từ WooCommerce")
                return
            
            self.progress_updated.emit(50, f"Đồng bộ {len(categories)} categories...")
            
            # Lưu vào database
            db = DatabaseManager()
            db.save_categories_from_api(self.site.id, categories)
            
            self.progress_updated.emit(100, "Hoàn thành!")
            self.finished.emit(True, f"Đã đồng bộ {len(categories)} categories thành công")
            
        except Exception as e:
            self.logger.error(f"Lỗi sync categories: {str(e)}")
            self.finished.emit(False, f"Lỗi đồng bộ: {str(e)}")


class CategoryManagerTab(QWidget):
    """Tab quản lý danh mục sản phẩm"""
    
    def __init__(self):
        super().__init__()
        self.db = DatabaseManager()
        self.logger = logging.getLogger(__name__)
        self.sync_worker = None
        
        self.init_ui()
        self.load_sites()
        self.load_categories()
    
    def init_ui(self):
        """Khởi tạo giao diện"""
        layout = QVBoxLayout(self)
        
        # Header với thống kê
        header_frame = QFrame()
        header_layout = QHBoxLayout(header_frame)
        
        # Site selection
        header_layout.addWidget(QLabel("Site:"))
        self.site_combo = QComboBox()
        self.site_combo.currentTextChanged.connect(self.filter_categories)
        header_layout.addWidget(self.site_combo)
        
        # Search
        header_layout.addWidget(QLabel("Tìm kiếm:"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Nhập tên danh mục...")
        self.search_edit.textChanged.connect(self.filter_categories)
        header_layout.addWidget(self.search_edit)
        
        # Stats
        header_layout.addStretch()
        self.stats_label = QLabel("Tổng: 0 danh mục")
        header_layout.addWidget(self.stats_label)
        
        layout.addWidget(header_frame)
        
        # Toolbar
        toolbar = QHBoxLayout()
        
        self.sync_btn = QPushButton("🔄 Đồng bộ Categories")
        self.sync_btn.clicked.connect(self.sync_categories)
        toolbar.addWidget(self.sync_btn)
        
        self.add_btn = QPushButton("➕ Thêm danh mục")
        self.add_btn.clicked.connect(self.add_category)
        toolbar.addWidget(self.add_btn)
        
        self.edit_btn = QPushButton("✏️ Sửa")
        self.edit_btn.clicked.connect(self.edit_category)
        self.edit_btn.setEnabled(False)
        toolbar.addWidget(self.edit_btn)
        
        self.delete_btn = QPushButton("🗑️ Xóa")
        self.delete_btn.clicked.connect(self.delete_category)
        self.delete_btn.setEnabled(False)
        toolbar.addWidget(self.delete_btn)
        
        toolbar.addStretch()
        
        # Progress bar (ẩn mặc định)
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        toolbar.addWidget(self.progress_bar)
        
        # Status label
        self.status_label = QLabel("Sẵn sàng")
        toolbar.addWidget(self.status_label)
        
        layout.addLayout(toolbar)
        
        # Table
        self.table = QTableWidget()
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        
        # Thiết lập columns
        columns = ["ID", "Site", "Tên", "Slug", "Mô tả", "Parent", "Count", "WC ID"]
        self.table.setColumnCount(len(columns))
        self.table.setHorizontalHeaderLabels(columns)
        
        # Resize columns
        header = self.table.horizontalHeader()
        if header:
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)  # ID
            header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)  # Site
            header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)  # Tên
            header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)  # Slug
            header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)  # Mô tả
            header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)  # Parent
            header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)  # Count
            header.setSectionResizeMode(7, QHeaderView.ResizeMode.ResizeToContents)  # WC ID
        
        # Selection changed
        selection_model = self.table.selectionModel()
        if selection_model:
            selection_model.selectionChanged.connect(self.on_selection_changed)
        
        layout.addWidget(self.table)
        
        # Details panel
        details_group = QGroupBox("Chi tiết danh mục")
        details_layout = QVBoxLayout(details_group)
        self.details_text = QTextEdit()
        self.details_text.setMaximumHeight(150)
        self.details_text.setReadOnly(True)
        details_layout.addWidget(self.details_text)
        layout.addWidget(details_group)
    
    def load_sites(self):
        """Load danh sách sites"""
        try:
            sites = self.db.get_all_sites()
            self.site_combo.clear()
            self.site_combo.addItem("Tất cả sites", None)
            
            for site in sites:
                self.site_combo.addItem(site.name, site.id)
                
        except Exception as e:
            self.logger.error(f"Lỗi load sites: {str(e)}")
    
    def load_categories(self):
        """Load danh sách categories"""
        try:
            categories = self.db.get_all_categories()
            self.display_categories(categories)
            self.update_stats(categories)
            
        except Exception as e:
            self.logger.error(f"Lỗi load categories: {str(e)}")
            QMessageBox.critical(self, "Lỗi", f"Không thể tải categories: {str(e)}")
    
    def display_categories(self, categories: List[Dict]):
        """Hiển thị categories trong table"""
        self.table.setRowCount(len(categories))
        
        for row, category in enumerate(categories):
            # ID
            item = QTableWidgetItem(str(category.get('id', '')))
            item.setData(Qt.ItemDataRole.UserRole, category)
            self.table.setItem(row, 0, item)
            
            # Site name
            site_name = ""
            if category.get('site_id'):
                site = self.db.get_site_by_id(category['site_id'])
                if site:
                    site_name = site.name if hasattr(site, 'name') else str(site.get('name', ''))
            self.table.setItem(row, 1, QTableWidgetItem(site_name))
            
            # Tên
            self.table.setItem(row, 2, QTableWidgetItem(str(category.get('name', ''))))
            
            # Slug
            self.table.setItem(row, 3, QTableWidgetItem(str(category.get('slug', ''))))
            
            # Mô tả (rút gọn)
            description = str(category.get('description', ''))
            if len(description) > 50:
                description = description[:47] + "..."
            self.table.setItem(row, 4, QTableWidgetItem(description))
            
            # Parent
            parent_id = category.get('parent_id', 0)
            self.table.setItem(row, 5, QTableWidgetItem(str(parent_id) if parent_id else ""))
            
            # Count
            self.table.setItem(row, 6, QTableWidgetItem(str(category.get('count', 0))))
            
            # WC ID
            wc_id = category.get('wc_category_id', '')
            self.table.setItem(row, 7, QTableWidgetItem(str(wc_id) if wc_id else ""))
    
    def filter_categories(self):
        """Lọc categories theo site và search"""
        try:
            # Lấy site_id được chọn
            site_id = self.site_combo.currentData()
            search_term = self.search_edit.text().lower()
            
            # Lấy categories
            if site_id:
                categories = self.db.get_categories_by_site(site_id)
            else:
                categories = self.db.get_all_categories()
            
            # Lọc theo search term
            if search_term:
                categories = [cat for cat in categories 
                            if search_term in str(cat.get('name', '')).lower()]
            
            self.display_categories(categories)
            self.update_stats(categories)
            
        except Exception as e:
            self.logger.error(f"Lỗi filter categories: {str(e)}")
    
    def update_stats(self, categories: List[Dict]):
        """Cập nhật thống kê"""
        total = len(categories)
        with_wc_id = len([cat for cat in categories if cat.get('wc_category_id')])
        
        self.stats_label.setText(f"Tổng: {total} danh mục ({with_wc_id} đã đồng bộ)")
    
    def on_selection_changed(self):
        """Xử lý khi selection thay đổi"""
        selected_rows = self.table.selectionModel().selectedRows()
        has_selection = len(selected_rows) > 0
        
        self.edit_btn.setEnabled(has_selection)
        self.delete_btn.setEnabled(has_selection)
        
        if has_selection:
            row = selected_rows[0].row()
            item = self.table.item(row, 0)
            if item:
                category_data = item.data(Qt.ItemDataRole.UserRole)
                if category_data:
                    self.show_category_details(category_data)
        else:
            self.details_text.clear()
    
    def show_category_details(self, category: Dict):
        """Hiển thị chi tiết category"""
        details = f"""
Tên: {category.get('name', '')}
Slug: {category.get('slug', '')}
Mô tả: {category.get('description', '')}
Parent ID: {category.get('parent_id', 0)}
Count: {category.get('count', 0)}
WooCommerce ID: {category.get('wc_category_id', 'Chưa đồng bộ')}
Tạo lúc: {category.get('created_at', '')}
Cập nhật: {category.get('updated_at', '')}
        """.strip()
        
        self.details_text.setText(details)
    
    def sync_categories(self):
        """Đồng bộ categories từ WooCommerce"""
        # Lấy site được chọn
        site_id = self.site_combo.currentData()
        if not site_id:
            QMessageBox.warning(self, "Cảnh báo", "Vui lòng chọn một site để đồng bộ")
            return
        
        site = self.db.get_site_by_id(site_id)
        if not site:
            QMessageBox.warning(self, "Cảnh báo", "Không tìm thấy thông tin site")
            return
        
        self.start_sync(site)
    
    def start_sync(self, site):
        """Bắt đầu đồng bộ categories"""
        if self.sync_worker and self.sync_worker.isRunning():
            QMessageBox.warning(self, "Cảnh báo", "Đang có tiến trình đồng bộ khác")
            return
        
        # Disable buttons
        self.sync_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        
        # Start worker
        self.sync_worker = CategorySyncWorker(site)
        self.sync_worker.progress_updated.connect(self.on_sync_progress)
        self.sync_worker.finished.connect(self.on_sync_finished)
        self.sync_worker.category_synced.connect(self.on_category_synced)
        self.sync_worker.start()
    
    def on_sync_progress(self, value: int, status: str):
        """Cập nhật tiến độ sync"""
        self.progress_bar.setValue(value)
        self.status_label.setText(status)
    
    def on_sync_finished(self, success: bool, message: str):
        """Xử lý khi sync hoàn thành"""
        self.sync_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.status_label.setText("Sẵn sàng")
        
        if success:
            QMessageBox.information(self, "Thành công", message)
            self.load_categories()
        else:
            QMessageBox.critical(self, "Lỗi", message)
    
    def on_category_synced(self, category_data: Dict):
        """Xử lý khi một category được sync"""
        # Có thể cập nhật real-time nếu cần
        pass
    
    def add_category(self):
        """Thêm danh mục mới"""
        try:
            sites = self.db.get_active_sites()
            if not sites:
                QMessageBox.warning(self, "Cảnh báo", "Không có site nào hoạt động")
                return
            
            categories = self.db.get_all_categories()
            
            dialog = CategoryDialog(self, sites=sites, categories=categories)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                category_data = dialog.get_category_data()
                
                # Tạo category mới
                self.db.create_category(category_data)
                
                # Reload categories
                self.load_categories()
                QMessageBox.information(self, "Thành công", "Đã thêm danh mục thành công!")
                
        except Exception as e:
            self.logger.error(f"Lỗi thêm category: {str(e)}")
            QMessageBox.critical(self, "Lỗi", f"Không thể thêm danh mục: {str(e)}")
    
    def edit_category(self):
        """Sửa danh mục đã chọn"""
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            return
        
        row = selected_rows[0].row()
        item = self.table.item(row, 0)
        if not item:
            return
        
        category_data = item.data(Qt.ItemDataRole.UserRole)
        if not category_data:
            return
        
        try:
            sites = self.db.get_active_sites()
            categories = self.db.get_all_categories()
            category_id = category_data.get('id')
            
            dialog = CategoryDialog(self, sites=sites, category=category_data, categories=categories)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                updated_data = dialog.get_category_data()
                
                # Cập nhật database
                self.db.update_category(category_id, updated_data)
                
                # Reload categories để hiển thị thay đổi
                self.load_categories()
                QMessageBox.information(self, "Thành công", "Đã cập nhật danh mục thành công!")
                
        except Exception as e:
            self.logger.error(f"Lỗi sửa category: {str(e)}")
            QMessageBox.critical(self, "Lỗi", f"Không thể cập nhật danh mục: {str(e)}")
    
    def delete_category(self):
        """Xóa danh mục đã chọn"""
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            return
        
        row = selected_rows[0].row()
        item = self.table.item(row, 0)
        if not item:
            return
        
        category_data = item.data(Qt.ItemDataRole.UserRole)
        if not category_data:
            return
        
        category_name = category_data.get('name', 'Không rõ')
        
        # Xác nhận xóa
        reply = QMessageBox.question(
            self, 
            "Xác nhận xóa",
            f"Bạn có chắc muốn xóa danh mục '{category_name}'?\n\nLưu ý: Thao tác này không thể hoàn tác!",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                category_id = category_data.get('id')
                self.db.delete_category(category_id)
                
                # Reload categories
                self.load_categories()
                QMessageBox.information(self, "Thành công", "Đã xóa danh mục thành công!")
                
            except Exception as e:
                self.logger.error(f"Lỗi xóa category: {str(e)}")
                QMessageBox.critical(self, "Lỗi", f"Không thể xóa danh mục: {str(e)}")