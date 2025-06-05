"""
Page Dialog - Dialog để thêm/sửa trang WordPress

FEATURES:
---------
- Thêm/sửa tiêu đề trang
- Soạn thảo nội dung với editor
- Chọn trạng thái (publish, draft, private)
- Chọn trang cha
- Tự động tạo slug
- Upload hình ảnh đại diện
"""

import logging
from typing import List, Dict, Optional
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *


class PageDialog(QDialog):
    """Dialog để thêm/sửa trang WordPress"""
    
    page_saved = pyqtSignal(dict)  # Signal khi lưu thành công
    
    def __init__(self, parent=None, sites=None, page=None, pages=None):
        super().__init__(parent)
        self.sites = sites or []
        self.page = page  # Page để sửa (None nếu thêm mới)
        self.pages = pages or []  # Danh sách pages để chọn parent
        self.logger = logging.getLogger(__name__)
        
        self.init_ui()
        
        if self.page:
            self.load_page_data()
    
    def init_ui(self):
        """Khởi tạo giao diện dialog"""
        self.setWindowTitle("Thêm Trang" if not self.page else "Sửa Trang")
        self.setModal(True)
        self.resize(800, 600)
        
        layout = QVBoxLayout(self)
        
        # Tab widget cho các thông tin khác nhau
        tab_widget = QTabWidget()
        
        # Tab 1: Thông tin cơ bản
        basic_tab = self.create_basic_tab()
        tab_widget.addTab(basic_tab, "Thông tin cơ bản")
        
        # Tab 2: Nội dung
        content_tab = self.create_content_tab()
        tab_widget.addTab(content_tab, "Nội dung")
        
        # Tab 3: Thiết lập
        settings_tab = self.create_settings_tab()
        tab_widget.addTab(settings_tab, "Thiết lập")
        
        layout.addWidget(tab_widget)
        
        # Buttons
        buttons_layout = QHBoxLayout()
        
        self.save_btn = QPushButton("💾 Lưu")
        self.save_btn.clicked.connect(self.save_page)
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
        
        # Title
        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("Nhập tiêu đề trang...")
        self.title_edit.textChanged.connect(self.generate_slug)
        layout.addRow("Tiêu đề *:", self.title_edit)
        
        # Slug
        self.slug_edit = QLineEdit()
        self.slug_edit.setPlaceholderText("URL slug (tự động tạo từ tiêu đề)")
        layout.addRow("Slug:", self.slug_edit)
        
        # Excerpt
        self.excerpt_edit = QTextEdit()
        self.excerpt_edit.setPlaceholderText("Mô tả ngắn về trang...")
        self.excerpt_edit.setMaximumHeight(80)
        layout.addRow("Mô tả ngắn:", self.excerpt_edit)
        
        return tab
    
    def create_content_tab(self):
        """Tạo tab nội dung"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Content editor
        content_group = QGroupBox("Nội dung trang")
        content_layout = QVBoxLayout(content_group)
        
        # Toolbar
        toolbar = QHBoxLayout()
        
        bold_btn = QPushButton("B")
        bold_btn.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        bold_btn.clicked.connect(self.format_bold)
        toolbar.addWidget(bold_btn)
        
        italic_btn = QPushButton("I")
        italic_btn.setFont(QFont("Arial", 10, QFont.Weight.Normal))
        italic_btn.setStyleSheet("font-style: italic;")
        italic_btn.clicked.connect(self.format_italic)
        toolbar.addWidget(italic_btn)
        
        toolbar.addStretch()
        content_layout.addLayout(toolbar)
        
        # Content editor
        self.content_edit = QTextEdit()
        self.content_edit.setPlaceholderText("Nhập nội dung trang...")
        self.content_edit.setMinimumHeight(300)
        content_layout.addWidget(self.content_edit)
        
        layout.addWidget(content_group)
        
        return tab
    
    def create_settings_tab(self):
        """Tạo tab thiết lập"""
        tab = QWidget()
        layout = QFormLayout(tab)
        
        # Status
        self.status_combo = QComboBox()
        self.status_combo.addItems(["publish", "draft", "private"])
        layout.addRow("Trạng thái:", self.status_combo)
        
        # Parent page
        self.parent_combo = QComboBox()
        self.parent_combo.addItem("Không có trang cha", 0)
        for page in self.pages:
            if page.get('id') != (self.page.get('id') if self.page else None):
                title = page.get('title', 'Không có tiêu đề')
                self.parent_combo.addItem(title, page.get('id'))
        layout.addRow("Trang cha:", self.parent_combo)
        
        # Menu order
        self.menu_order_spin = QSpinBox()
        self.menu_order_spin.setRange(0, 9999)
        layout.addRow("Thứ tự menu:", self.menu_order_spin)
        
        # Featured image
        featured_group = QGroupBox("Hình ảnh đại diện")
        featured_layout = QVBoxLayout(featured_group)
        
        # Image preview
        self.image_preview = QLabel("Chưa có hình ảnh")
        self.image_preview.setFixedSize(200, 150)
        self.image_preview.setStyleSheet("border: 1px solid #ccc; background: #f5f5f5;")
        self.image_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        featured_layout.addWidget(self.image_preview)
        
        # Image buttons
        image_buttons = QHBoxLayout()
        
        self.select_image_btn = QPushButton("Chọn hình ảnh")
        self.select_image_btn.clicked.connect(self.select_image)
        image_buttons.addWidget(self.select_image_btn)
        
        self.clear_image_btn = QPushButton("Xóa hình ảnh")
        self.clear_image_btn.clicked.connect(self.clear_image)
        image_buttons.addWidget(self.clear_image_btn)
        
        featured_layout.addLayout(image_buttons)
        layout.addRow(featured_group)
        
        return tab
    
    def generate_slug(self):
        """Tự động tạo slug từ tiêu đề"""
        title = self.title_edit.text()
        if title and not self.slug_edit.text():
            # Tạo slug đơn giản
            slug = title.lower().replace(' ', '-')
            # Loại bỏ ký tự đặc biệt
            import re
            slug = re.sub(r'[^a-z0-9\-]', '', slug)
            slug = re.sub(r'-+', '-', slug).strip('-')
            self.slug_edit.setText(slug)
    
    def format_bold(self):
        """Format text thành bold"""
        cursor = self.content_edit.textCursor()
        format = cursor.charFormat()
        if format.fontWeight() == QFont.Weight.Bold:
            format.setFontWeight(QFont.Weight.Normal)
        else:
            format.setFontWeight(QFont.Weight.Bold)
        cursor.setCharFormat(format)
    
    def format_italic(self):
        """Format text thành italic"""
        cursor = self.content_edit.textCursor()
        format = cursor.charFormat()
        format.setFontItalic(not format.fontItalic())
        cursor.setCharFormat(format)
    
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
    
    def load_page_data(self):
        """Load dữ liệu page để sửa"""
        if not self.page:
            return
        
        # Load basic info
        self.title_edit.setText(self.page.get('title', ''))
        self.slug_edit.setText(self.page.get('slug', ''))
        self.excerpt_edit.setPlainText(self.page.get('excerpt', ''))
        
        # Load content
        self.content_edit.setPlainText(self.page.get('content', ''))
        
        # Load settings
        status = self.page.get('status', 'draft')
        status_index = self.status_combo.findText(status)
        if status_index >= 0:
            self.status_combo.setCurrentIndex(status_index)
        
        parent_id = self.page.get('parent_id', 0)
        parent_index = self.parent_combo.findData(parent_id)
        if parent_index >= 0:
            self.parent_combo.setCurrentIndex(parent_index)
        
        self.menu_order_spin.setValue(self.page.get('menu_order', 0))
        
        # Set site
        site_id = self.page.get('site_id')
        if site_id:
            site_index = self.site_combo.findData(site_id)
            if site_index >= 0:
                self.site_combo.setCurrentIndex(site_index)
    
    def validate_form(self) -> bool:
        """Kiểm tra tính hợp lệ của form"""
        if not self.title_edit.text().strip():
            QMessageBox.warning(self, "Lỗi", "Vui lòng nhập tiêu đề trang")
            return False
        
        if self.site_combo.currentData() is None:
            QMessageBox.warning(self, "Lỗi", "Vui lòng chọn site")
            return False
        
        return True
    
    def save_page(self):
        """Lưu thông tin page"""
        if self.validate_form():
            try:
                page_data = self.get_page_data()
                self.page_saved.emit(page_data)
                self.accept()
            except Exception as e:
                QMessageBox.critical(self, "Lỗi", f"Không thể lưu trang: {str(e)}")
    
    def get_page_data(self) -> dict:
        """Lấy dữ liệu page từ form"""
        return {
            'site_id': self.site_combo.currentData(),
            'title': self.title_edit.text().strip(),
            'slug': self.slug_edit.text().strip(),
            'content': self.content_edit.toPlainText(),
            'excerpt': self.excerpt_edit.toPlainText().strip(),
            'status': self.status_combo.currentText(),
            'parent_id': self.parent_combo.currentData(),
            'menu_order': self.menu_order_spin.value(),
            'featured_media': getattr(self, 'selected_image_path', None)
        }