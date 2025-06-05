
"""
Bulk Folder Edit Dialog - Dialog để sửa hàng loạt thư mục
"""

from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *
from typing import Dict, Any, Optional

class BulkFolderEditDialog(QDialog):
    """Dialog để sửa hàng loạt thư mục"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.db_manager = None
        self.init_ui()
        self.load_data()
    
    def init_ui(self):
        """Khởi tạo giao diện"""
        self.setWindowTitle("Sửa hàng loạt thư mục")
        self.setModal(True)
        self.resize(500, 400)
        
        layout = QVBoxLayout(self)
        
        # Header
        header_label = QLabel("Chọn các trường muốn cập nhật:")
        header_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(header_label)
        
        # Form layout
        form_layout = QFormLayout()
        
        # Site selection
        self.site_check = QCheckBox("Cập nhật Site")
        form_layout.addRow(self.site_check)
        
        self.site_combo = QComboBox()
        self.site_combo.setEnabled(False)
        self.site_check.toggled.connect(self.site_combo.setEnabled)
        # Kết nối signal để filter categories khi chọn site
        self.site_combo.currentIndexChanged.connect(self.on_site_changed)
        form_layout.addRow("  Site:", self.site_combo)
        
        # Category selection
        self.category_check = QCheckBox("Cập nhật Danh mục")
        form_layout.addRow(self.category_check)
        
        self.category_combo = QComboBox()
        self.category_combo.setEnabled(False)
        self.category_check.toggled.connect(self.category_combo.setEnabled)
        form_layout.addRow("  Danh mục:", self.category_combo)
        
        # Status selection
        self.status_check = QCheckBox("Cập nhật Trạng thái")
        form_layout.addRow(self.status_check)
        
        self.status_combo = QComboBox()
        self.status_combo.addItems(["pending", "processing", "completed", "error"])
        self.status_combo.setEnabled(False)
        self.status_check.toggled.connect(self.status_combo.setEnabled)
        form_layout.addRow("  Trạng thái:", self.status_combo)
        
        # Description
        self.description_check = QCheckBox("Cập nhật Mô tả")
        form_layout.addRow(self.description_check)
        
        self.description_edit = QTextEdit()
        self.description_edit.setMaximumHeight(100)
        self.description_edit.setEnabled(False)
        self.description_check.toggled.connect(self.description_edit.setEnabled)
        form_layout.addRow("  Mô tả:", self.description_edit)
        
        layout.addLayout(form_layout)
        
        # Buttons
        buttons_layout = QHBoxLayout()
        
        self.apply_btn = QPushButton("🔄 Áp dụng")
        self.apply_btn.clicked.connect(self.accept)
        buttons_layout.addWidget(self.apply_btn)
        
        self.cancel_btn = QPushButton("❌ Hủy")
        self.cancel_btn.clicked.connect(self.reject)
        buttons_layout.addWidget(self.cancel_btn)
        
        layout.addLayout(buttons_layout)
    
    def load_data(self):
        """Load dữ liệu cho combo boxes"""
        try:
            from .database import DatabaseManager
            self.db_manager = DatabaseManager()
            
            # Load sites
            sites = self.db_manager.get_all_sites()
            self.site_combo.clear()
            self.site_combo.addItem("Chọn site", None)
            for site in sites:
                # site là Site object có thuộc tính name và id
                site_name = site.name if hasattr(site, 'name') else str(site)
                site_id = site.id if hasattr(site, 'id') else site
                self.site_combo.addItem(site_name, site_id)
            
            # Load all categories (sẽ được filter khi chọn site)
            self.load_categories()
                
        except Exception as e:
            print(f"Error loading bulk edit data: {str(e)}")
            # Thêm các item mặc định để tránh combo box rỗng

    def load_categories(self, site_id=None):
        """Load categories, filter theo site nếu có"""
        try:
            self.category_combo.clear()
            self.category_combo.addItem("Chọn danh mục", None)
            
            if site_id:
                # Load categories của site cụ thể
                categories = self.db_manager.get_categories_by_site(site_id)
            else:
                # Load tất cả categories
                categories = self.db_manager.get_all_categories()
            
            for category in categories:
                if isinstance(category, dict):
                    category_name = category.get('name', 'Không tên')
                    site_name = category.get('site_name', '')
                    if site_id:
                        # Nếu đã filter theo site, chỉ hiển thị tên category
                        display_name = category_name
                    else:
                        # Hiển thị cả site name nếu hiển thị tất cả
                        display_name = f"{category_name} ({site_name})" if site_name else category_name
                    self.category_combo.addItem(display_name, category.get('id'))
                else:
                    # Trường hợp category là object
                    category_name = category.name if hasattr(category, 'name') else str(category)
                    self.category_combo.addItem(category_name, category.id if hasattr(category, 'id') else category)
                    
        except Exception as e:
            print(f"Error loading categories: {str(e)}")
            self.category_combo.addItem("Chọn danh mục", None)

    def on_site_changed(self):
        """Xử lý khi thay đổi site - filter categories theo site được chọn"""
        try:
            site_id = self.site_combo.currentData()
            if site_id and site_id != 0:
                # Load categories của site được chọn
                self.load_categories(site_id)
            else:
                # Load tất cả categories
                self.load_categories()
        except Exception as e:
            print(f"Error in on_site_changed: {str(e)}")
            self.site_combo.addItem("Không có site", None)
            self.category_combo.addItem("Không có danh mục", None)
    
    def get_update_data(self) -> Dict[str, Any]:
        """Lấy dữ liệu cập nhật"""
        update_data = {}
        
        if self.site_check.isChecked():
            update_data['site_id'] = self.site_combo.currentData()
        
        if self.category_check.isChecked():
            update_data['category_id'] = self.category_combo.currentData()
        
        if self.status_check.isChecked():
            update_data['status'] = self.status_combo.currentText()
        
        if self.description_check.isChecked():
            update_data['description'] = self.description_edit.toPlainText().strip()
        
        return update_data
