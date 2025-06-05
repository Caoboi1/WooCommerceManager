"""
Category Dialog - Dialog để thêm/sửa danh mục sản phẩm

FEATURES:
---------
- Thêm/sửa tên danh mục
- Chọn danh mục cha
- Thiết lập slug và mô tả
- Upload hình ảnh danh mục
"""

import logging
from typing import List, Dict, Optional
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *


class CategoryDialog(QDialog):
    """Dialog để thêm/sửa danh mục sản phẩm"""
    
    category_saved = pyqtSignal(dict)  # Signal khi lưu thành công
    
    def __init__(self, parent=None, sites=None, category=None, categories=None):
        super().__init__(parent)
        self.sites = sites or []
        self.category = category  # Category để sửa (None nếu thêm mới)
        self.categories = categories or []  # Danh sách categories để chọn parent
        self.logger = logging.getLogger(__name__)
        
        self.init_ui()
        
        if self.category:
            self.load_category_data()
    
    def init_ui(self):
        """Khởi tạo giao diện dialog"""
        self.setWindowTitle("Thêm Danh mục" if not self.category else "Sửa Danh mục")
        self.setModal(True)
        self.resize(600, 500)
        
        layout = QVBoxLayout(self)
        
        # Tab widget cho các thông tin khác nhau
        tab_widget = QTabWidget()
        
        # Tab 1: Thông tin cơ bản
        basic_tab = self.create_basic_tab()
        tab_widget.addTab(basic_tab, "Thông tin cơ bản")
        
        # Tab 2: Thiết lập
        settings_tab = self.create_settings_tab()
        tab_widget.addTab(settings_tab, "Thiết lập")
        
        layout.addWidget(tab_widget)
        
        # Buttons
        buttons_layout = QHBoxLayout()
        
        self.save_btn = QPushButton("💾 Lưu")
        self.save_btn.clicked.connect(self.save_category)
        buttons_layout.addWidget(self.save_btn)
        
        self.cancel_btn = QPushButton("❌ Hủy")
        self.cancel_btn.clicked.connect(self.reject)
        buttons_layout.addWidget(self.cancel_btn)
        
        layout.addLayout(buttons_layout)
    
    def create_basic_tab(self):
        """Tạo tab thông tin cơ bản"""
        tab = QWidget()
        layout = QFormLayout(tab)
        
        # Site selection
        self.site_combo = QComboBox()
        for site in self.sites:
            self.site_combo.addItem(site.name, site.id)
        layout.addRow("Site *:", self.site_combo)
        
        # Name
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Nhập tên danh mục...")
        self.name_edit.textChanged.connect(self.generate_slug)
        layout.addRow("Tên danh mục *:", self.name_edit)
        
        # Slug
        self.slug_edit = QLineEdit()
        self.slug_edit.setPlaceholderText("URL slug (tự động tạo từ tên)")
        layout.addRow("Slug:", self.slug_edit)
        
        # Description
        self.description_edit = QTextEdit()
        self.description_edit.setPlaceholderText("Mô tả danh mục...")
        self.description_edit.setMaximumHeight(100)
        layout.addRow("Mô tả:", self.description_edit)
        
        return tab
    
    def create_settings_tab(self):
        """Tạo tab thiết lập"""
        tab = QWidget()
        layout = QFormLayout(tab)
        
        # Parent category
        self.parent_combo = QComboBox()
        self.parent_combo.addItem("Không có danh mục cha", 0)
        for category in self.categories:
            if category.get('id') != (self.category.get('id') if self.category else None):
                name = category.get('name', 'Không có tên')
                self.parent_combo.addItem(name, category.get('id'))
        layout.addRow("Danh mục cha:", self.parent_combo)
        
        # Display type
        self.display_combo = QComboBox()
        self.display_combo.addItems(["default", "products", "subcategories", "both"])
        layout.addRow("Kiểu hiển thị:", self.display_combo)
        
        # Menu order
        self.menu_order_spin = QSpinBox()
        self.menu_order_spin.setRange(0, 9999)
        layout.addRow("Thứ tự menu:", self.menu_order_spin)
        
        # Image section
        image_group = QGroupBox("Hình ảnh danh mục")
        image_layout = QVBoxLayout(image_group)
        
        # Image preview
        self.image_preview = QLabel("Chưa có hình ảnh")
        self.image_preview.setFixedSize(150, 150)
        self.image_preview.setStyleSheet("border: 1px solid #ccc; background: #f5f5f5;")
        self.image_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        image_layout.addWidget(self.image_preview)
        
        # Image buttons
        image_buttons = QHBoxLayout()
        
        self.select_image_btn = QPushButton("Chọn hình ảnh")
        self.select_image_btn.clicked.connect(self.select_image)
        image_buttons.addWidget(self.select_image_btn)
        
        self.clear_image_btn = QPushButton("Xóa hình ảnh")
        self.clear_image_btn.clicked.connect(self.clear_image)
        image_buttons.addWidget(self.clear_image_btn)
        
        image_layout.addLayout(image_buttons)
        layout.addRow(image_group)
        
        return tab
    
    def generate_slug(self):
        """Tự động tạo slug từ tên"""
        name = self.name_edit.text()
        if name and not self.slug_edit.text():
            # Tạo slug đơn giản
            slug = name.lower().replace(' ', '-')
            # Loại bỏ ký tự đặc biệt
            import re
            slug = re.sub(r'[^a-z0-9\-]', '', slug)
            slug = re.sub(r'-+', '-', slug).strip('-')
            self.slug_edit.setText(slug)
    
    def select_image(self):
        """Chọn hình ảnh từ máy tính"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Chọn hình ảnh",
            "",
            "Image files (*.jpg *.jpeg *.png *.gif *.bmp)"
        )
        
        if file_path:
            self.load_image_preview(file_path)
    
    def load_image_preview(self, file_path=None):
        """Tải và hiển thị ảnh xem trước"""
        if file_path:
            pixmap = QPixmap(file_path)
            if not pixmap.isNull():
                # Scale image to fit preview
                scaled_pixmap = pixmap.scaled(
                    self.image_preview.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                self.image_preview.setPixmap(scaled_pixmap)
                self.selected_image_path = file_path
            else:
                QMessageBox.warning(self, "Lỗi", "Không thể tải hình ảnh")
    
    def clear_image(self):
        """Xóa hình ảnh đã chọn"""
        self.image_preview.clear()
        self.image_preview.setText("Chưa có hình ảnh")
        self.selected_image_path = None
    
    def load_category_data(self):
        """Load dữ liệu category để sửa"""
        if not self.category:
            return
        
        # Load basic info
        self.name_edit.setText(self.category.get('name', ''))
        self.slug_edit.setText(self.category.get('slug', ''))
        self.description_edit.setPlainText(self.category.get('description', ''))
        
        # Load settings
        parent_id = self.category.get('parent', 0)
        parent_index = self.parent_combo.findData(parent_id)
        if parent_index >= 0:
            self.parent_combo.setCurrentIndex(parent_index)
        
        display = self.category.get('display', 'default')
        display_index = self.display_combo.findText(display)
        if display_index >= 0:
            self.display_combo.setCurrentIndex(display_index)
        
        self.menu_order_spin.setValue(self.category.get('menu_order', 0))
        
        # Set site
        site_id = self.category.get('site_id')
        if site_id:
            site_index = self.site_combo.findData(site_id)
            if site_index >= 0:
                self.site_combo.setCurrentIndex(site_index)
    
    def validate_form(self) -> bool:
        """Kiểm tra tính hợp lệ của form"""
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "Lỗi", "Vui lòng nhập tên danh mục")
            return False
        
        if self.site_combo.currentData() is None:
            QMessageBox.warning(self, "Lỗi", "Vui lòng chọn site")
            return False
        
        return True
    
    def save_category(self):
        """Lưu thông tin category"""
        if self.validate_form():
            try:
                category_data = self.get_category_data()
                self.category_saved.emit(category_data)
                self.accept()
            except Exception as e:
                QMessageBox.critical(self, "Lỗi", f"Không thể lưu danh mục: {str(e)}")
    
    def get_category_data(self) -> dict:
        """Lấy dữ liệu category từ form"""
        return {
            'site_id': self.site_combo.currentData(),
            'name': self.name_edit.text().strip(),
            'slug': self.slug_edit.text().strip(),
            'description': self.description_edit.toPlainText().strip(),
            'parent': self.parent_combo.currentData(),
            'display': self.display_combo.currentText(),
            'menu_order': self.menu_order_spin.value(),
            'image': getattr(self, 'selected_image_path', None)
        }