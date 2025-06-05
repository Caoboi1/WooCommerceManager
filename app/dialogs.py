"""
Dialogs - Các hộp thoại của ứng dụng
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QTextEdit, QComboBox, QSpinBox, QDoubleSpinBox,
    QPushButton, QMessageBox, QCheckBox, QFileDialog, QLabel,
    QProgressBar, QGraphicsOpacityEffect, QGroupBox, QTabWidget,
    QWidget, QListWidget, QListWidgetItem, QScrollArea
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QPixmap, QPalette, QFont, QTextCharFormat
import logging

from .models import Site, Product

class SiteSelectionDialog(QDialog):
    """Dialog để chọn site để đồng bộ"""

    def __init__(self, parent=None, sites=None):
        super().__init__(parent)
        self.sites = sites or []
        self.selected_sites = []

        self.init_ui()

    def init_ui(self):
        """Khởi tạo giao diện"""
        self.setWindowTitle("Chọn Sites để đồng bộ")
        self.setModal(True)
        self.resize(400, 300)

        layout = QVBoxLayout(self)

        # Instruction label
        instruction_label = QLabel("Chọn các sites bạn muốn đồng bộ sản phẩm:")
        layout.addWidget(instruction_label)

        # Sites list with checkboxes
        self.sites_group = QGroupBox("Danh sách Sites")
        sites_layout = QVBoxLayout(self.sites_group)

        self.site_checkboxes = []
        for site in self.sites:
            if site.is_active:
                checkbox = QCheckBox(f"{site.name} ({site.url})")
                checkbox.setChecked(True)  # Default checked
                checkbox.site_id = site.id
                self.site_checkboxes.append(checkbox)
                sites_layout.addWidget(checkbox)

        if not self.site_checkboxes:
            no_sites_label = QLabel("Không có sites nào được kích hoạt")
            no_sites_label.setStyleSheet("color: #666; font-style: italic;")
            sites_layout.addWidget(no_sites_label)

        layout.addWidget(self.sites_group)

        # Select all/none buttons
        select_buttons_layout = QHBoxLayout()

        select_all_btn = QPushButton("Chọn tất cả")
        select_all_btn.clicked.connect(self.select_all)
        select_buttons_layout.addWidget(select_all_btn)

        select_none_btn = QPushButton("Bỏ chọn tất cả")
        select_none_btn.clicked.connect(self.select_none)
        select_buttons_layout.addWidget(select_none_btn)

        select_buttons_layout.addStretch()
        layout.addLayout(select_buttons_layout)

        # Dialog buttons
        buttons_layout = QHBoxLayout()

        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self.accept_selection)
        buttons_layout.addWidget(ok_btn)

        cancel_btn = QPushButton("Hủy")
        cancel_btn.clicked.connect(self.reject)
        buttons_layout.addWidget(cancel_btn)

        layout.addLayout(buttons_layout)

    def select_all(self):
        """Chọn tất cả sites"""
        for checkbox in self.site_checkboxes:
            checkbox.setChecked(True)

    def select_none(self):
        """Bỏ chọn tất cả sites"""
        for checkbox in self.site_checkboxes:
            checkbox.setChecked(False)

    def accept_selection(self):
        """Xác nhận lựa chọn"""
        self.selected_sites = []
        for checkbox in self.site_checkboxes:
            if checkbox.isChecked():
                self.selected_sites.append(checkbox.site_id)

        if not self.selected_sites:
            QMessageBox.warning(self, "Cảnh báo", "Vui lòng chọn ít nhất một site")
            return

        self.accept()

    def get_selected_sites(self):
        """Lấy danh sách sites đã chọn"""
        return self.selected_sites

class AnimatedProgressDialog(QDialog):
    """Dialog hiển thị tiến độ với animation sinh động"""

    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setFixedSize(400, 200)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.CustomizeWindowHint | Qt.WindowType.WindowTitleHint)

        # Animation properties
        self.animation_step = 0
        self.is_running = False

        self.init_ui()
        self.setup_animation()

    def init_ui(self):
        """Khởi tạo giao diện"""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # Title label
        self.title_label = QLabel("Đang xử lý...")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #2c5aa0;")
        layout.addWidget(self.title_label)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid #cccccc;
                border-radius: 5px;
                text-align: center;
                font-weight: bold;
            }
            QProgressBar::chunk {
                background-color: #4CAF50;
                border-radius: 3px;
            }
        """)
        layout.addWidget(self.progress_bar)

        # Status label
        self.status_label = QLabel("Chuẩn bị...")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("color: #666; font-size: 12px;")
        layout.addWidget(self.status_label)

        # Detail label
        self.detail_label = QLabel("")
        self.detail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.detail_label.setStyleSheet("color: #888; font-size: 10px;")
        layout.addWidget(self.detail_label)

        # Cancel button
        self.cancel_btn = QPushButton("Hủy")
        self.cancel_btn.clicked.connect(self.reject)
        layout.addWidget(self.cancel_btn)

    def setup_animation(self):
        """Thiết lập animation timer"""
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_animation)
        self.timer.setInterval(100)  # Update every 100ms

    def start_progress(self, indeterminate=True):
        """Bắt đầu hiển thị tiến độ"""
        self.is_running = True
        if indeterminate:
            self.progress_bar.setRange(0, 0)  # Indeterminate progress
        self.timer.start()

    def set_progress(self, value, maximum=100):
        """Cập nhật tiến độ"""
        self.progress_bar.setRange(0, maximum)
        self.progress_bar.setValue(value)

    def set_title(self, title):
        """Cập nhật tiêu đề"""
        self.title_label.setText(title)

    def set_status(self, status):
        """Cập nhật trạng thái"""
        self.status_label.setText(status)

    def set_detail(self, detail):
        """Cập nhật chi tiết"""
        self.detail_label.setText(detail)

    def update_animation(self):
        """Cập nhật animation"""
        if self.is_running:
            self.animation_step = (self.animation_step + 1) % 8
            dots = "." * (self.animation_step % 4)

            # Animate title if needed
            if "..." not in self.title_label.text():
                original_title = self.title_label.text()
                self.title_label.setText(f"{original_title}{dots}")

    def finish_progress(self, success=True, message=""):
        """Kết thúc tiến độ"""
        self.is_running = False
        self.timer.stop()

        if success:
            self.progress_bar.setValue(100)
            self.set_title("✅ Hoàn thành!")
            self.set_status(message or "Thành công!")
            self.cancel_btn.setText("Đóng")
        else:
            self.set_title("❌ Có lỗi xảy ra")
            self.set_status(message or "Thất bại!")
            self.cancel_btn.setText("Đóng")

        # Auto close after 2 seconds if successful
        if success:
            QTimer.singleShot(2000, self.accept)

class SiteDialog(QDialog):
    """Dialog để thêm/sửa thông tin site"""

    def __init__(self, parent=None, site=None):
        super().__init__(parent)
        self.site = site
        self.logger = logging.getLogger(__name__)

        self.init_ui()

        if site:
            self.load_site_data()

    def init_ui(self):
        """Khởi tạo giao diện"""
        self.setWindowTitle("Thêm Site" if not self.site else "Sửa Site")
        self.setModal(True)
        self.resize(500, 400)

        layout = QVBoxLayout(self)

        # Form layout
        form_group = QGroupBox("Thông tin Site")
        form_layout = QFormLayout(form_group)

        # Tên site
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Nhập tên site...")
        form_layout.addRow("Tên Site *:", self.name_edit)

        # URL
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("https://yoursite.com")
        form_layout.addRow("URL *:", self.url_edit)

        # Consumer Key
        self.key_edit = QLineEdit()
        self.key_edit.setPlaceholderText("ck_xxxxxxxxxxxxxxxx")
        form_layout.addRow("Consumer Key *:", self.key_edit)

        # Consumer Secret
        self.secret_edit = QLineEdit()
        self.secret_edit.setPlaceholderText("cs_xxxxxxxxxxxxxxxx")
        self.secret_edit.setEchoMode(QLineEdit.EchoMode.Password)
        form_layout.addRow("Consumer Secret *:", self.secret_edit)

        # Checkbox để hiện/ẩn password
        self.show_password_cb = QCheckBox("Hiển thị Consumer Secret")
        self.show_password_cb.toggled.connect(self.toggle_password_visibility)
        form_layout.addRow("", self.show_password_cb)

        # WordPress Authentication
        wp_group = QGroupBox("WordPress Authentication (cho Pages)")
        wp_layout = QFormLayout(wp_group)

        # WordPress Username
        self.wp_username_edit = QLineEdit()
        self.wp_username_edit.setPlaceholderText("adminvoguepony")
        wp_layout.addRow("WordPress Username:", self.wp_username_edit)

        # WordPress Application Password
        self.wp_app_password_edit = QLineEdit()
        self.wp_app_password_edit.setPlaceholderText("xxxx xxxx xxxx xxxx xxxx xxxx")
        self.wp_app_password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        wp_layout.addRow("Application Password:", self.wp_app_password_edit)

        # Checkbox để hiện/ẩn WordPress password
        self.show_wp_password_cb = QCheckBox("Hiển thị Application Password")
        self.show_wp_password_cb.toggled.connect(self.toggle_wp_password_visibility)
        wp_layout.addRow("", self.show_wp_password_cb)

        layout.addWidget(wp_group)

        # Trạng thái hoạt động
        self.active_cb = QCheckBox("Site đang hoạt động")
        self.active_cb.setChecked(True)
        form_layout.addRow("Trạng thái:", self.active_cb)

        # Ghi chú
        self.notes_edit = QTextEdit()
        self.notes_edit.setPlaceholderText("Ghi chú về site...")
        self.notes_edit.setMaximumHeight(80)
        form_layout.addRow("Ghi chú:", self.notes_edit)

        layout.addWidget(form_group)

        # Hướng dẫn
        help_group = QGroupBox("Hướng dẫn lấy API Key")
        help_layout = QVBoxLayout(help_group)

        help_text = QLabel(
            "1. Vào WooCommerce → Settings → Advanced → REST API\n"
            "2. Click 'Add key'\n"
            "3. Chọn permissions: Read/Write\n"
            "4. Copy Consumer key và Consumer secret"
        )
        help_text.setStyleSheet("color: #666; font-size: 11px;")
        help_layout.addWidget(help_text)

        layout.addWidget(help_group)

        # Buttons
        buttons_layout = QHBoxLayout()

        self.save_btn = QPushButton("💾 Lưu")
        self.save_btn.clicked.connect(self.save_site)
        buttons_layout.addWidget(self.save_btn)

        self.cancel_btn = QPushButton("❌ Hủy")
        self.cancel_btn.clicked.connect(self.reject)
        buttons_layout.addWidget(self.cancel_btn)

        layout.addLayout(buttons_layout)

        # Set focus
        self.name_edit.setFocus()

    def toggle_password_visibility(self, checked):
        """Toggle hiển thị/ẩn password"""
        if checked:
            self.secret_edit.setEchoMode(QLineEdit.EchoMode.Normal)
        else:
            self.secret_edit.setEchoMode(QLineEdit.EchoMode.Password)

    def toggle_wp_password_visibility(self, checked):
        """Toggle hiển thị/ẩn WordPress password"""
        if checked:
            self.wp_app_password_edit.setEchoMode(QLineEdit.EchoMode.Normal)
        else:
            self.wp_app_password_edit.setEchoMode(QLineEdit.EchoMode.Password)

    def load_site_data(self):
        """Load dữ liệu site để sửa"""
        if self.site:
            self.name_edit.setText(self.site.name)
            self.url_edit.setText(self.site.url)
            self.key_edit.setText(self.site.consumer_key)
            self.secret_edit.setText(self.site.consumer_secret)
            self.wp_username_edit.setText(getattr(self.site, 'wp_username', ''))
            self.wp_app_password_edit.setText(getattr(self.site, 'wp_app_password', ''))
            self.active_cb.setChecked(self.site.is_active)
            self.notes_edit.setPlainText(self.site.notes)

    def validate_form(self) -> bool:
        """Validate form data"""
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "Lỗi", "Vui lòng nhập tên site")
            self.name_edit.setFocus()
            return False

        if not self.url_edit.text().strip():
            QMessageBox.warning(self, "Lỗi", "Vui lòng nhập URL site")
            self.url_edit.setFocus()
            return False

        url = self.url_edit.text().strip()
        if not (url.startswith('http://') or url.startswith('https://')):
            QMessageBox.warning(self, "Lỗi", "URL phải bắt đầu bằng http:// hoặc https://")
            self.url_edit.setFocus()
            return False

        if not self.key_edit.text().strip():
            QMessageBox.warning(self, "Lỗi", "Vui lòng nhập Consumer Key")
            self.key_edit.setFocus()
            return False

        if not self.secret_edit.text().strip():
            QMessageBox.warning(self, "Lỗi", "Vui lòng nhập Consumer Secret")
            self.secret_edit.setFocus()
            return False

        return True

    def save_site(self):
        """Lưu thông tin site"""
        if self.validate_form():
            self.accept()

    def get_site_data(self) -> dict:
        """Lấy dữ liệu site từ form"""
        return {
            'name': self.name_edit.text().strip(),
            'url': self.url_edit.text().strip().rstrip('/'),
            'consumer_key': self.key_edit.text().strip(),
            'consumer_secret': self.secret_edit.text().strip(),
            'wp_username': self.wp_username_edit.text().strip(),
            'wp_app_password': self.wp_app_password_edit.text().strip(),
            'is_active': self.active_cb.isChecked(),
            'notes': self.notes_edit.toPlainText().strip()
        }

class ProductDialog(QDialog):
    """Dialog để thêm/sửa thông tin sản phẩm"""

    def __init__(self, parent=None, sites=None, product=None):
        super().__init__(parent)
        self.sites = sites or []
        self.product = product
        self.logger = logging.getLogger(__name__)

        self.init_ui()

        if product:
            self.load_product_data()

    def init_ui(self):
        """Khởi tạo giao diện"""
        self.setWindowTitle("Thêm Sản phẩm" if not self.product else "Sửa Sản phẩm")
        self.setModal(True)
        self.resize(600, 500)

        layout = QVBoxLayout(self)

        # Tab widget
        tab_widget = QTabWidget()

        # Tab 1: Thông tin cơ bản
        basic_tab = QWidget()
        basic_layout = QFormLayout(basic_tab)

        # Site
        self.site_combo = QComboBox()
        for site in self.sites:
            self.site_combo.addItem(site.name, site.id)
        basic_layout.addRow("Site *:", self.site_combo)

        # Tên sản phẩm
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Nhập tên sản phẩm...")
        basic_layout.addRow("Tên sản phẩm *:", self.name_edit)

        # SKU
        self.sku_edit = QLineEdit()
        self.sku_edit.setPlaceholderText("SKU sản phẩm...")
        basic_layout.addRow("SKU:", self.sku_edit)

        # Giá
        price_layout = QHBoxLayout()

        # Giá gốc
        self.regular_price_spin = QDoubleSpinBox()
        self.regular_price_spin.setRange(0, 999999.99)
        self.regular_price_spin.setDecimals(2)
        self.regular_price_spin.setPrefix("$ ")
        price_layout.addWidget(QLabel("Giá gốc:"))
        price_layout.addWidget(self.regular_price_spin)

        # Giá sale
        self.sale_price_spin = QDoubleSpinBox()
        self.sale_price_spin.setRange(0, 999999.99)
        self.sale_price_spin.setDecimals(2)
        self.sale_price_spin.setPrefix("$ ")
        price_layout.addWidget(QLabel("Giá sale:"))
        price_layout.addWidget(self.sale_price_spin)

        basic_layout.addRow("Giá:", price_layout)

        # Số lượng kho
        self.stock_spin = QSpinBox()
        self.stock_spin.setRange(-1, 999999)
        self.stock_spin.setSpecialValueText("Không quản lý kho")
        basic_layout.addRow("Số lượng kho:", self.stock_spin)

        # Trạng thái
        self.status_combo = QComboBox()
        self.status_combo.addItems(["draft", "publish", "private"])
        basic_layout.addRow("Trạng thái:", self.status_combo)

        tab_widget.addTab(basic_tab, "Thông tin cơ bản")

        # Tab 2: Mô tả
        desc_tab = QWidget()
        desc_layout = QFormLayout(desc_tab)

        # Mô tả ngắn
        self.short_desc_edit = QTextEdit()
        self.short_desc_edit.setMaximumHeight(80)
        self.short_desc_edit.setPlaceholderText("Mô tả ngắn gọn...")
        self.short_desc_edit.setAcceptRichText(False)  # Chỉ cho phép text thuần
        desc_layout.addRow("Mô tả ngắn:", self.short_desc_edit)

        # Mô tả đầy đủ với toolbar formatting
        desc_full_widget = QWidget()
        desc_full_layout = QVBoxLayout(desc_full_widget)
        desc_full_layout.setContentsMargins(0, 0, 0, 0)
        
        # Toolbar cho formatting
        toolbar = QHBoxLayout()
        toolbar.setSpacing(5)
        
        self.bold_btn = QPushButton("B")
        self.bold_btn.setFont(QFont("Arial", 9, QFont.Weight.Bold))
        self.bold_btn.setMaximumSize(30, 25)
        self.bold_btn.setCheckable(True)
        self.bold_btn.clicked.connect(self.toggle_bold)
        toolbar.addWidget(self.bold_btn)
        
        self.italic_btn = QPushButton("I")
        self.italic_btn.setFont(QFont("Arial", 9))
        self.italic_btn.setStyleSheet("font-style: italic;")
        self.italic_btn.setMaximumSize(30, 25)
        self.italic_btn.setCheckable(True)
        self.italic_btn.clicked.connect(self.toggle_italic)
        toolbar.addWidget(self.italic_btn)
        
        self.underline_btn = QPushButton("U")
        self.underline_btn.setFont(QFont("Arial", 9))
        self.underline_btn.setStyleSheet("text-decoration: underline;")
        self.underline_btn.setMaximumSize(30, 25)
        self.underline_btn.setCheckable(True)
        self.underline_btn.clicked.connect(self.toggle_underline)
        toolbar.addWidget(self.underline_btn)
        
        toolbar.addWidget(QLabel("|"))  # Separator
        
        self.bullet_btn = QPushButton("• List")
        self.bullet_btn.setMaximumSize(50, 25)
        self.bullet_btn.clicked.connect(self.insert_bullet_list)
        toolbar.addWidget(self.bullet_btn)
        
        self.number_btn = QPushButton("1. List")
        self.number_btn.setMaximumSize(50, 25)
        self.number_btn.clicked.connect(self.insert_number_list)
        toolbar.addWidget(self.number_btn)
        
        toolbar.addStretch()
        
        # HTML/Text toggle
        self.html_mode_cb = QCheckBox("Chế độ HTML")
        self.html_mode_cb.toggled.connect(self.toggle_html_mode)
        toolbar.addWidget(self.html_mode_cb)
        
        desc_full_layout.addLayout(toolbar)
        
        # Text editor
        self.description_edit = QTextEdit()
        self.description_edit.setPlaceholderText("Mô tả chi tiết sản phẩm...")
        self.description_edit.setMinimumHeight(200)
        
        # Thiết lập rich text với HTML support nhưng hiển thị như text editor
        self.description_edit.setAcceptRichText(True)
        self.description_edit.cursorPositionChanged.connect(self.update_format_buttons)
        
        desc_full_layout.addWidget(self.description_edit)
        
        desc_layout.addRow("Mô tả chi tiết:", desc_full_widget)

        tab_widget.addTab(desc_tab, "Mô tả")

        # Tab 3: Phân loại
        category_tab = QWidget()
        category_layout = QFormLayout(category_tab)

        # Danh mục
        self.categories_edit = QLineEdit()
        self.categories_edit.setPlaceholderText("Danh mục 1, Danh mục 2, ...")
        category_layout.addRow("Danh mục:", self.categories_edit)

        # Tags
        self.tags_edit = QLineEdit()
        self.tags_edit.setPlaceholderText("tag1, tag2, tag3, ...")
        category_layout.addRow("Tags:", self.tags_edit)

        # URL hình ảnh
        self.images_edit = QTextEdit()
        self.images_edit.setMaximumHeight(100)
        self.images_edit.setPlaceholderText("URL hình ảnh, mỗi dòng một URL...")
        category_layout.addRow("Hình ảnh:", self.images_edit)

        tab_widget.addTab(category_tab, "Phân loại & Hình ảnh")

        layout.addWidget(tab_widget)

        # Buttons
        buttons_layout = QHBoxLayout()

        self.save_btn = QPushButton("💾 Lưu")
        self.save_btn.clicked.connect(self.save_product)
        buttons_layout.addWidget(self.save_btn)

        self.cancel_btn = QPushButton("❌ Hủy")
        self.cancel_btn.clicked.connect(self.reject)
        buttons_layout.addWidget(self.cancel_btn)

        layout.addLayout(buttons_layout)

        # Set focus
        self.name_edit.setFocus()

    def load_product_data(self):
        """Load dữ liệu sản phẩm để sửa"""
        if self.product:
            # Set site
            for i in range(self.site_combo.count()):
                if self.site_combo.itemData(i) == self.product.site_id:
                    self.site_combo.setCurrentIndex(i)
                    break

            self.name_edit.setText(self.product.name or "")
            self.sku_edit.setText(self.product.sku or "")

            if self.product.regular_price:
                self.regular_price_spin.setValue(self.product.regular_price)
            if self.product.sale_price:
                self.sale_price_spin.setValue(self.product.sale_price)
            if self.product.stock_quantity is not None:
                self.stock_spin.setValue(self.product.stock_quantity)

            # Set status
            status_index = self.status_combo.findText(self.product.status or "draft")
            if status_index >= 0:
                self.status_combo.setCurrentIndex(status_index)

            self.short_desc_edit.setPlainText(self.product.short_description or "")
            
            # Load mô tả - kiểm tra xem có phải HTML không
            description = self.product.description or ""
            if description and ('<' in description and '>' in description):
                # Nếu là HTML, hiển thị dạng text thuần
                from PyQt6.QtGui import QTextDocument
                doc = QTextDocument()
                doc.setHtml(description)
                self.description_edit.setPlainText(doc.toPlainText())
            else:
                # Nếu là text thuần, hiển thị bình thường
                self.description_edit.setPlainText(description)
            self.categories_edit.setText(self.product.categories or "")
            self.tags_edit.setText(self.product.tags or "")

            # Convert images from comma-separated to line-separated
            if self.product.images:
                images = self.product.images.split(',')
                self.images_edit.setPlainText('\n'.join(images))

    def validate_form(self) -> bool:
        """Validate form data"""
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "Lỗi", "Vui lòng nhập tên sản phẩm")
            self.name_edit.setFocus()
            return False

        if self.site_combo.currentData() is None:
            QMessageBox.warning(self, "Lỗi", "Vui lòng chọn site")
            self.site_combo.setFocus()
            return False

        return True

    def save_product(self):
        """Lưu thông tin sản phẩm"""
        if self.validate_form():
            self.accept()

    def toggle_bold(self):
        """Toggle định dạng đậm"""
        fmt = self.description_edit.currentCharFormat()
        if fmt.fontWeight() == QFont.Weight.Bold:
            fmt.setFontWeight(QFont.Weight.Normal)
        else:
            fmt.setFontWeight(QFont.Weight.Bold)
        self.description_edit.setCurrentCharFormat(fmt)
        self.description_edit.setFocus()

    def toggle_italic(self):
        """Toggle định dạng nghiêng"""
        fmt = self.description_edit.currentCharFormat()
        fmt.setFontItalic(not fmt.fontItalic())
        self.description_edit.setCurrentCharFormat(fmt)
        self.description_edit.setFocus()

    def toggle_underline(self):
        """Toggle định dạng gạch chân"""
        fmt = self.description_edit.currentCharFormat()
        fmt.setFontUnderline(not fmt.fontUnderline())
        self.description_edit.setCurrentCharFormat(fmt)
        self.description_edit.setFocus()

    def insert_bullet_list(self):
        """Chèn danh sách bullet"""
        cursor = self.description_edit.textCursor()
        cursor.insertText("• ")
        self.description_edit.setFocus()

    def insert_number_list(self):
        """Chèn danh sách số"""
        cursor = self.description_edit.textCursor()
        cursor.insertText("1. ")
        self.description_edit.setFocus()

    def update_format_buttons(self):
        """Cập nhật trạng thái các nút formatting"""
        if hasattr(self, 'bold_btn'):
            fmt = self.description_edit.currentCharFormat()
            self.bold_btn.setChecked(fmt.fontWeight() == QFont.Weight.Bold)
            self.italic_btn.setChecked(fmt.fontItalic())
            self.underline_btn.setChecked(fmt.fontUnderline())

    def toggle_html_mode(self, checked):
        """Chuyển đổi giữa chế độ HTML và text"""
        if checked:
            # Chuyển sang chế độ HTML (hiển thị HTML code)
            html_content = self.description_edit.toHtml()
            self.description_edit.setAcceptRichText(False)
            self.description_edit.setPlainText(html_content)
            
            # Disable formatting buttons
            self.bold_btn.setEnabled(False)
            self.italic_btn.setEnabled(False)
            self.underline_btn.setEnabled(False)
            self.bullet_btn.setEnabled(False)
            self.number_btn.setEnabled(False)
        else:
            # Chuyển về chế độ rich text
            plain_content = self.description_edit.toPlainText()
            self.description_edit.setAcceptRichText(True)
            
            # Nếu content là HTML, parse nó
            if '<' in plain_content and '>' in plain_content:
                self.description_edit.setHtml(plain_content)
            else:
                self.description_edit.setPlainText(plain_content)
            
            # Enable formatting buttons
            self.bold_btn.setEnabled(True)
            self.italic_btn.setEnabled(True)
            self.underline_btn.setEnabled(True)
            self.bullet_btn.setEnabled(True)
            self.number_btn.setEnabled(True)

    def clean_html_to_text(self, html_content):
        """Chuyển đổi HTML thành text thuần túy có format"""
        from PyQt6.QtGui import QTextDocument
        doc = QTextDocument()
        doc.setHtml(html_content)
        return doc.toPlainText()

    def get_product_data(self) -> dict:
        """Lấy dữ liệu sản phẩm từ form"""
        # Convert images from line-separated to comma-separated
        images_text = self.images_edit.toPlainText().strip()
        images = ','.join([line.strip() for line in images_text.split('\n') if line.strip()])

        # Xử lý mô tả dựa trên chế độ hiện tại
        if hasattr(self, 'html_mode_cb') and self.html_mode_cb.isChecked():
            # Nếu đang ở chế độ HTML, lấy HTML content
            description_content = self.description_edit.toPlainText().strip()
        else:
            # Nếu đang ở chế độ rich text, chuyển thành text thuần có format cơ bản
            description_content = self.description_edit.toPlainText().strip()

        return {
            'site_id': self.site_combo.currentData(),
            'name': self.name_edit.text().strip(),
            'sku': self.sku_edit.text().strip(),
            'regular_price': self.regular_price_spin.value() if self.regular_price_spin.value() > 0 else None,
            'sale_price': self.sale_price_spin.value() if self.sale_price_spin.value() > 0 else None,
            'price': self.sale_price_spin.value() if self.sale_price_spin.value() > 0 else self.regular_price_spin.value(),
            'stock_quantity': self.stock_spin.value() if self.stock_spin.value() >= 0 else None,
            'status': self.status_combo.currentText(),
            'short_description': self.short_desc_edit.toPlainText().strip(),
            'description': description_content,
            'categories': self.categories_edit.text().strip(),
            'tags': self.tags_edit.text().strip(),
            'images': images
        }