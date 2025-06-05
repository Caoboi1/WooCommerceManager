"""
Folder Scanner Tab - Tab quét thư mục ảnh
"""

import os
import logging
from typing import List, Dict, Any
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLineEdit, QLabel, QComboBox, QTextEdit, QDialog,
    QFormLayout, QFileDialog, QMessageBox, QProgressDialog, QGroupBox,
    QSpinBox, QCheckBox, QSplitter, QFrame, QInputDialog, QAbstractItemView
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QMutex, QMutexLocker
from PyQt6.QtGui import QFont, QPixmap, QIcon

from .database import DatabaseManager
from .models import FolderScan
from .bulk_folder_edit_dialog import BulkFolderEditDialog


class FolderScanWorker(QThread):
    """Worker thread để quét thư mục"""

    progress_update = pyqtSignal(int, str)
    folder_found = pyqtSignal(dict)
    finished = pyqtSignal(bool, str)

    def __init__(self, root_path: str, extensions: List[str], min_images: int = 1, delete_empty: bool = False):
        super().__init__()
        self.root_path = root_path
        self.extensions = extensions
        self.min_images = min_images
        self.delete_empty = delete_empty
        self._is_cancelled = False
        self._mutex = QMutex()
        self.folders_processed = 0
        self.total_folders = 0
        self.deleted_folders = 0

        # Set termination enabled for safe cancellation
        self.setTerminationEnabled(True)

    def run(self):
        """Chạy quét thư mục"""
        try:
            self.logger = logging.getLogger(__name__ + ".FolderScanWorker")

            if not os.path.exists(self.root_path):
                self.finished.emit(False, "Đường dẫn không tồn tại")
                return

            # Hiển thị thông tin cấu hình
            extensions_str = ", ".join(self.extensions)
            self.progress_update.emit(0, f"Bắt đầu quét thư mục với extensions: {extensions_str}, tối thiểu {self.min_images} ảnh...")

            # Giới hạn để tránh memory issues
            MAX_FOLDERS = 5000
            MAX_FILES_PER_FOLDER = 1000
            folders_found = 0
            processed_paths = set()

            try:
                # Quét trực tiếp với os.walk và xử lý từng thư mục
                for root, dirs, files in os.walk(self.root_path):
                    if self.is_cancelled():
                        break

                    # Skip if already processed
                    if root in processed_paths:
                        continue
                    processed_paths.add(root)

                    # Giới hạn số thư mục
                    self.folders_processed += 1
                    if self.folders_processed > MAX_FOLDERS:
                        self.finished.emit(False, f"Quá nhiều thư mục (>{MAX_FOLDERS}). Vui lòng chọn thư mục nhỏ hơn.")
                        return

                    try:
                        # Đếm số file ảnh trong thư mục - cải thiện logic
                        image_count = 0
                        file_count = 0

                        # Chuẩn bị danh sách extensions đã clean
                        clean_extensions = [ext.lower().strip() for ext in self.extensions if ext.strip()]

                        for file in files:
                            if self.is_cancelled():
                                break

                            file_count += 1
                            if file_count > MAX_FILES_PER_FOLDER:
                                self.logger.warning(f"Thư mục {root} có quá nhiều file ({file_count}), bỏ qua")
                                break  # Skip folders with too many files

                            try:
                                file_lower = file.lower()
                                # Kiểm tra từng extension một cách chính xác
                                for ext in clean_extensions:
                                    if ext and file_lower.endswith(ext):
                                        image_count += 1
                                        # Log để debug
                                        if image_count <= 3:  # Chỉ log vài file đầu
                                            self.logger.debug(f"Tìm thấy ảnh: {file} trong {root}")
                                        break
                            except (UnicodeDecodeError, OSError) as e:
                                self.logger.debug(f"Lỗi đọc file {file}: {e}")
                                continue  # Skip problematic files

                        if self.is_cancelled():
                            break

                        # Log thông tin để debug
                        if image_count > 0:
                            self.logger.info(f"Thư mục '{root}': {image_count} ảnh (tối thiểu: {self.min_images})")

                        # Chỉ thêm thư mục có đủ số ảnh tối thiểu
                        if image_count >= self.min_images:
                            folder_name = os.path.basename(root) or os.path.basename(self.root_path)

                            folder_data = {
                                'original_title': folder_name,
                                'path': root,
                                'image_count': image_count,
                                'description': '',  # Để trống để AI làm nội dung điền vào sau
                                'status': 'pending',
                                'new_title': ''
                            }

                            self.folder_found.emit(folder_data)
                            folders_found += 1
                            self.logger.info(f"Đã thêm thư mục: {folder_name} ({image_count} ảnh)")
                        elif image_count == 0 and len(files) == 0 and self.delete_empty:
                            # Thư mục rỗng hoàn toàn - xóa nếu được phép
                            if self.delete_empty_folder(root):
                                self.deleted_folders += 1

                        # Cập nhật tiến độ mỗi 10 thư mục
                        if self.folders_processed % 10 == 0:
                            progress = min(int((self.folders_processed / max(self.folders_processed + 100, 1000)) * 100), 90)
                            self.progress_update.emit(
                                progress, 
                                f"Đã quét {self.folders_processed} thư mục, tìm thấy {folders_found} thư mục có ảnh"
                            )

                        # Memory cleanup
                        if self.folders_processed % 50 == 0:
                            self.msleep(50)  # Short pause for memory cleanup

                    except (OSError, PermissionError, UnicodeDecodeError) as e:
                        # Skip problematic folders
                        self.logger.warning(f"Skip folder {root}: {str(e)}")
                        continue
                    except Exception as e:
                        # Log unexpected errors but continue
                        self.logger.error(f"Unexpected error in folder {root}: {str(e)}")
                        continue

                if not self.is_cancelled():
                    self.progress_update.emit(100, f"Hoàn thành! Tìm thấy {folders_found} thư mục có ảnh")
                    self.finished.emit(True, f"Hoàn thành quét {self.folders_processed} thư mục, tìm thấy {folders_found} thư mục có ảnh")
                else:
                    self.finished.emit(False, "Đã hủy quét thư mục")

            except Exception as e:
                self.logger.error(f"Error during folder scanning: {str(e)}")
                self.finished.emit(False, f"Lỗi khi quét: {str(e)}")

        except Exception as e:
            self.finished.emit(False, f"Lỗi nghiêm trọng khi quét: {str(e)}")
        finally:
            # Cleanup
            self.folders_processed = 0
            self.total_folders = 0

    def is_cancelled(self):
        """Thread-safe check for cancellation"""
        with QMutexLocker(self._mutex):
            return self._is_cancelled

    def cancel(self):
        """Hủy quét"""
        with QMutexLocker(self._mutex):
            self._is_cancelled = True

    def delete_empty_folder(self, folder_path: str) -> bool:
        """Xóa thư mục rỗng"""
        try:
            # Kiểm tra thư mục có thực sự rỗng không
            if os.path.exists(folder_path) and os.path.isdir(folder_path):
                # Kiểm tra không có file ẩn hoặc subdirectory
                contents = os.listdir(folder_path)
                if len(contents) == 0:
                    os.rmdir(folder_path)
                    return True
            return False
        except (OSError, PermissionError):
            # Không thể xóa - có thể do quyền truy cập
            return False


class FolderScanDialog(QDialog):
    """Dialog thêm/sửa folder scan"""

    def __init__(self, parent=None, folder_data=None):
        super().__init__(parent)
        self.folder_data = folder_data
        self.db_manager = None
        self.init_ui()
        self.load_sites()

        if folder_data:
            self.load_data()

    def init_ui(self):
        """Khởi tạo giao diện"""
        self.setWindowTitle("Thêm Thư mục" if not self.folder_data else "Sửa Thư mục")
        self.setModal(True)
        self.resize(600, 500)

        layout = QVBoxLayout(self)

        # Form layout
        form_layout = QFormLayout()

        # Tên data
        self.data_name_edit = QLineEdit()
        self.data_name_edit.setPlaceholderText("Tên data để quản lý...")
        form_layout.addRow("Tên Data:", self.data_name_edit)

        # Tiêu đề gốc
        self.original_title_edit = QLineEdit()
        self.original_title_edit.setPlaceholderText("Tên thư mục gốc...")
        form_layout.addRow("Tiêu đề gốc:", self.original_title_edit)

        # Đường dẫn
        path_layout = QHBoxLayout()
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("Đường dẫn thư mục...")
        path_layout.addWidget(self.path_edit)

        self.browse_btn = QPushButton("📁 Duyệt")
        self.browse_btn.clicked.connect(self.browse_folder)
        path_layout.addWidget(self.browse_btn)

        form_layout.addRow("Đường dẫn:", path_layout)

        # Số lượng ảnh
        self.image_count_spin = QSpinBox()
        self.image_count_spin.setRange(0, 999999)
        self.image_count_spin.setReadOnly(True)
        form_layout.addRow("Số lượng ảnh:", self.image_count_spin)

        # Trạng thái
        self.status_combo = QComboBox()
        self.status_combo.addItems(["pending", "processing", "completed", "error"])
        form_layout.addRow("Trạng thái:", self.status_combo)

        # Site selection
        self.site_combo = QComboBox()
        self.site_combo.addItem("Chọn site...", None)
        self.site_combo.currentIndexChanged.connect(self.load_categories_for_site)
        form_layout.addRow("Site:", self.site_combo)

        # Category selection
        self.category_combo = QComboBox()
        self.category_combo.addItem("Chọn danh mục...", None)
        form_layout.addRow("Danh mục:", self.category_combo)

        # Tiêu đề mới
        self.new_title_edit = QLineEdit()
        self.new_title_edit.setPlaceholderText("Tiêu đề viết lại bằng AI...")
        form_layout.addRow("Tiêu đề mới:", self.new_title_edit)

        layout.addLayout(form_layout)

        # Mô tả
        desc_group = QGroupBox("Mô tả")
        desc_layout = QVBoxLayout(desc_group)

        self.description_edit = QTextEdit()
        self.description_edit.setPlaceholderText("Mô tả để AI phát triển nội dung...")
        self.description_edit.setMaximumHeight(100)
        desc_layout.addWidget(self.description_edit)

        layout.addWidget(desc_group)

        # Buttons
        buttons_layout = QHBoxLayout()

        self.save_btn = QPushButton("💾 Lưu")
        self.save_btn.clicked.connect(self.accept)
        buttons_layout.addWidget(self.save_btn)

        self.cancel_btn = QPushButton("❌ Hủy")
        self.cancel_btn.clicked.connect(self.reject)
        buttons_layout.addWidget(self.cancel_btn)

        layout.addLayout(buttons_layout)

    def browse_folder(self):
        """Chọn thư mục"""
        folder = QFileDialog.getExistingDirectory(self, "Chọn thư mục")
        if folder:
            self.path_edit.setText(folder)
            # Tự động đếm ảnh
            self.count_images()
            # Tự động set tiêu đề
            folder_name = os.path.basename(folder)
            if not self.original_title_edit.text():
                self.original_title_edit.setText(folder_name)
            # Tự động set data name
            if not self.data_name_edit.text():
                self.data_name_edit.setText(folder_name)

    def count_images(self):
        """Đếm số ảnh trong thư mục"""
        path = self.path_edit.text()
        if not path or not os.path.exists(path):
            return

        extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']
        count = 0

        try:
            for file in os.listdir(path):
                if any(file.lower().endswith(ext) for ext in extensions):
                    count += 1

            self.image_count_spin.setValue(count)

        except Exception as e:
            QMessageBox.warning(self, "Lỗi", f"Không thể đếm ảnh: {str(e)}")

    def load_sites(self):
        """Load danh sách sites"""
        try:
            if not self.db_manager:
                from .database import DatabaseManager
                self.db_manager = DatabaseManager()

            sites = self.db_manager.get_all_sites()
            self.site_combo.clear()
            self.site_combo.addItem("Chọn site...", None)

            for site in sites:
                self.site_combo.addItem(site.name, site.id)

        except Exception as e:
            pass  # Không hiển thị lỗi nếu không load được sites

    def load_categories_for_site(self):
        """Load categories cho site được chọn"""
        try:
            site_id = self.site_combo.currentData()
            self.category_combo.clear()
            self.category_combo.addItem("Chọn danh mục...", None)

            if site_id and self.db_manager:
                categories = self.db_manager.get_categories_by_site(site_id)
                for category in categories:
                    category_name = category.get('name', '')
                    category_id = category.get('id')
                    if category_name and category_id:
                        self.category_combo.addItem(category_name, category_id)

        except Exception as e:
            self.logger.error(f"Lỗi load categories for site {site_id}: {str(e)}")
            # Thêm option mặc định nếu lỗi
            self.category_combo.addItem("Lỗi load danh mục", None)

    def load_data(self):
        """Load dữ liệu vào form"""
        if not self.folder_data:
            return

        self.data_name_edit.setText(self.folder_data.get('data_name', ''))
        self.original_title_edit.setText(self.folder_data.get('original_title', ''))
        self.path_edit.setText(self.folder_data.get('path', ''))
        self.image_count_spin.setValue(self.folder_data.get('image_count', 0))
        self.description_edit.setPlainText(self.folder_data.get('description', ''))

        # Load site
        site_id = self.folder_data.get('site_id')
        if site_id:
            for i in range(self.site_combo.count()):
                if self.site_combo.itemData(i) == site_id:
                    self.site_combo.setCurrentIndex(i)
                    self.load_categories_for_site()
                    break

        # Load category
        category_id = self.folder_data.get('category_id')
        if category_id:
            for i in range(self.category_combo.count()):
                if self.category_combo.itemData(i) == category_id:
                    self.category_combo.setCurrentIndex(i)
                    break

        status = self.folder_data.get('status', 'pending')
        index = self.status_combo.findText(status)
        if index >= 0:
            self.status_combo.setCurrentIndex(index)

        self.new_title_edit.setText(self.folder_data.get('new_title', ''))

    def get_data(self) -> Dict[str, Any]:
        """Lấy dữ liệu từ form"""
        data_name = self.data_name_edit.text().strip()
        if not data_name:
            data_name = self.original_title_edit.text().strip()

        return {
            'data_name': data_name,
            'original_title': self.original_title_edit.text().strip(),
            'path': self.path_edit.text().strip(),
            'image_count': self.image_count_spin.value(),
            'description': self.description_edit.toPlainText().strip(),
            'category_id': self.category_combo.currentData(),
            'site_id': self.site_combo.currentData(),
            'status': self.status_combo.currentText(),
            'new_title': self.new_title_edit.text().strip()
        }


class FolderScannerTab(QWidget):
    """Tab quét thư mục ảnh"""

    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.scan_worker = None
        self.progress_dialog = None
        self._is_initialized = False
        self._is_loading = False  # Flag để ngăn đệ quy

        try:
            # Khởi tạo database manager ngay từ đầu
            from .database import DatabaseManager
            self.db_manager = DatabaseManager()

            self.init_ui()
            self._is_initialized = True
            # Delay load data to avoid initialization issues
            QTimer.singleShot(1000, self.safe_load_data)
        except Exception as e:
            print(f"Error initializing FolderScannerTab: {e}")
            # Create minimal UI on error
            layout = QVBoxLayout(self)
            error_label = QLabel(f"Lỗi khởi tạo tab quét thư mục: {e}")
            layout.addWidget(error_label)
            self._is_initialized = False

    def __del__(self):
        """Destructor to cleanup resources"""
        try:
            if hasattr(self, 'scan_worker') and self.scan_worker:
                self.cleanup_scan()
        except:
            pass

    def closeEvent(self, event):
        """Handle close event"""
        try:
            self.cleanup_scan()
        except:
            pass
        super().closeEvent(event)

    def init_ui(self):
        """Khởi tạo giao diện"""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)

        # Header controls
        header_layout = QHBoxLayout()

        # Quét thư mục button
        self.scan_btn = QPushButton("🔍 Quét thư mục")
        self.scan_btn.clicked.connect(self.scan_folders)
        header_layout.addWidget(self.scan_btn)

        # Lưu kết quả quét button
        self.save_scan_btn = QPushButton("💾 Lưu kết quả")
        self.save_scan_btn.clicked.connect(self.save_scan_results)
        self.save_scan_btn.setEnabled(False)  # Disable until scan completes
        header_layout.addWidget(self.save_scan_btn)

        # Load kết quả đã lưu button
        self.load_saved_btn = QPushButton("📂 Load đã lưu")
        self.load_saved_btn.clicked.connect(self.load_saved_results)
        header_layout.addWidget(self.load_saved_btn)

        header_layout.addSpacing(20)

        # Search
        search_label = QLabel("Tìm kiếm:")
        search_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        header_layout.addWidget(search_label)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Nhập tên thư mục hoặc đường dẫn...")
        self.search_edit.textChanged.connect(self.search_folders)
        header_layout.addWidget(self.search_edit)

        # Site filter
        site_label = QLabel("Site:")
        site_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        header_layout.addWidget(site_label)

        self.filter_site_combo = QComboBox()
        self.filter_site_combo.addItem("Tất cả sites", None)
        self.filter_site_combo.currentTextChanged.connect(self.filter_data)
        header_layout.addWidget(self.filter_site_combo)

        # Category filter
        category_label = QLabel("Danh mục:")
        category_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        header_layout.addWidget(category_label)

        self.filter_category_combo = QComboBox()
        self.filter_category_combo.addItem("Tất cả danh mục", None)
        self.filter_category_combo.currentTextChanged.connect(self.filter_data)
        header_layout.addWidget(self.filter_category_combo)

        # Status filter
        status_label = QLabel("Trạng thái:")
        status_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        header_layout.addWidget(status_label)

        self.status_combo = QComboBox()
        self.status_combo.addItems(["Tất cả", "pending", "processing", "completed", "error", "Chưa hoàn thành"])
        self.status_combo.currentTextChanged.connect(self.filter_data)
        header_layout.addWidget(self.status_combo)

        header_layout.addStretch()

        layout.addLayout(header_layout)

        # Splitter cho table và detail
        splitter = QSplitter(Qt.Orientation.Vertical)

        # Table group
        table_group = QGroupBox("Danh sách thư mục đã quét")
        table_layout = QVBoxLayout(table_group)

        # Table
        self.table = QTableWidget()
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSortingEnabled(True)

        # Set columns
        columns = [
            "ID", "Tên Data", "Tiêu đề gốc", "Đường dẫn", "Số ảnh", 
            "Mô tả", "Site", "Danh mục", "Trạng thái", "Tiêu đề mới", "Ngày tạo"
        ]
        self.table.setColumnCount(len(columns))
        self.table.setHorizontalHeaderLabels(columns)

        # Set column widths
        self.table.setColumnWidth(0, 50)   # ID
        self.table.setColumnWidth(1, 120)  # Tên Data
        self.table.setColumnWidth(2, 120)  # Tiêu đề gốc
        self.table.setColumnWidth(3, 180)  # Đường dẫn
        self.table.setColumnWidth(4, 60)   # Số ảnh
        self.table.setColumnWidth(5, 150)  # Mô tả
        self.table.setColumnWidth(6, 100)  # Site
        self.table.setColumnWidth(7, 120)  # Danh mục
        self.table.setColumnWidth(8, 100)  # Trạng thái
        self.table.setColumnWidth(9, 120)  # Tiêu đề mới
        self.table.setColumnWidth(10, 100) # Ngày tạo

        self.table.selectionModel().selectionChanged.connect(self.on_selection_changed)
        table_layout.addWidget(self.table)

        # Table buttons
        table_buttons = QHBoxLayout()

        self.add_btn = QPushButton("➕ Thêm")
        self.add_btn.clicked.connect(self.add_folder)
        table_buttons.addWidget(self.add_btn)

        self.edit_btn = QPushButton("✏️ Sửa")
        self.edit_btn.clicked.connect(self.edit_folder)
        self.edit_btn.setEnabled(False)
        table_buttons.addWidget(self.edit_btn)

        self.delete_btn = QPushButton("🗑️ Xóa")
        self.delete_btn.clicked.connect(self.delete_folder)
        self.delete_btn.setEnabled(False)
        table_buttons.addWidget(self.delete_btn)

        table_buttons.addSpacing(20)

        self.bulk_edit_btn = QPushButton("📋 Sửa hàng loạt")
        self.bulk_edit_btn.clicked.connect(self.bulk_edit_folders)
        table_buttons.addWidget(self.bulk_edit_btn)

        self.ai_generate_btn = QPushButton("🤖 AI Tạo mô tả")
        self.ai_generate_btn.clicked.connect(self.ai_generate_descriptions)
        self.ai_generate_btn.setToolTip("Sử dụng AI để tạo mô tả cho các thư mục được chọn")
        table_buttons.addWidget(self.ai_generate_btn)

        self.ai_config_btn = QPushButton("⚙️ Cấu hình AI")
        self.ai_config_btn.clicked.connect(self.open_ai_config_dialog)
        self.ai_config_btn.setToolTip("Cấu hình API key và prompts cho AI")
        table_buttons.addWidget(self.ai_config_btn)

        self.refresh_btn = QPushButton("🔄 Làm mới")
        self.refresh_btn.clicked.connect(self.load_data)
        table_buttons.addWidget(self.refresh_btn)

        table_buttons.addStretch()

        # Export/Import buttons
        self.export_btn = QPushButton("📤 Export CSV")
        self.export_btn.clicked.connect(self.export_csv)
        table_buttons.addWidget(self.export_btn)

        self.upload_btn = QPushButton("🚀 Đăng lên WooCommerce")
        self.upload_btn.clicked.connect(self.upload_to_woocommerce)
        self.upload_btn.setToolTip("Đăng các thư mục đã chọn lên WooCommerce")
        table_buttons.addWidget(self.upload_btn)

        table_layout.addLayout(table_buttons)

        splitter.addWidget(table_group)

        # Detail panel
        detail_group = QGroupBox("Chi tiết thư mục")
        detail_layout = QVBoxLayout(detail_group)

        self.detail_text = QTextEdit()
        self.detail_text.setMaximumHeight(150)
        self.detail_text.setReadOnly(True)
        detail_layout.addWidget(self.detail_text)

        splitter.addWidget(detail_group)

        # Set splitter sizes
        splitter.setSizes([400, 150])
        layout.addWidget(splitter)

        # Stats
        stats_layout = QHBoxLayout()

        self.stats_label = QLabel("Tổng: 0 thư mục")
        self.stats_label.setFont(QFont("Arial", 9))
        stats_layout.addWidget(self.stats_label)

        stats_layout.addStretch()

        layout.addLayout(stats_layout)

    def safe_load_data(self):
        """Load dữ liệu an toàn"""
        if not self._is_initialized or self._is_loading:
            return

        try:
            # Load filter options và dữ liệu
            self.load_filter_options()
            self.load_data()

        except Exception as e:
            self.logger.error(f"Error in safe_load_data: {e}")
            # Fallback UI
            if hasattr(self, 'table') and self.table:
                self.table.setRowCount(0)
            if hasattr(self, 'stats_label') and self.stats_label:
                self.stats_label.setText("Lỗi load dữ liệu")

    def scan_folders(self):
        """Quét thư mục"""
        # Dialog cấu hình quét
        dialog = QDialog(self)
        dialog.setWindowTitle("Cấu hình quét thư mục")
        dialog.setModal(True)
        dialog.resize(500, 300)

        layout = QVBoxLayout(dialog)
        form_layout = QFormLayout()

        # Root path
        root_layout = QHBoxLayout()
        root_edit = QLineEdit()
        root_edit.setPlaceholderText("Chọn thư mục gốc để quét...")
        root_layout.addWidget(root_edit)

        browse_btn = QPushButton("📁 Duyệt")
        browse_btn.clicked.connect(lambda: self.browse_root_folder(root_edit))
        root_layout.addWidget(browse_btn)

        form_layout.addRow("Thư mục gốc:", root_layout)

        # Minimum images
        min_images_spin = QSpinBox()
        min_images_spin.setRange(1, 100)
        min_images_spin.setValue(1)  # Giảm xuống 1 để tìm nhiều thư mục hơn
        form_layout.addRow("Số ảnh tối thiểu:", min_images_spin)

        # Extensions
        extensions_edit = QLineEdit()
        extensions_edit.setText(".jpg,.jpeg,.png,.gif,.bmp,.webp")
        form_layout.addRow("Phần mở rộng:", extensions_edit)

        # Delete empty folders option
        delete_empty_check = QCheckBox("Xóa thư mục rỗng khi quét")
        delete_empty_check.setToolTip("Tự động xóa các thư mục không chứa file nào")
        form_layout.addRow(delete_empty_check)

        layout.addLayout(form_layout)

        # Buttons
        buttons = QHBoxLayout()

        start_btn = QPushButton("🚀 Bắt đầu quét")
        start_btn.clicked.connect(dialog.accept)
        buttons.addWidget(start_btn)

        cancel_btn = QPushButton("❌ Hủy")
        cancel_btn.clicked.connect(dialog.reject)
        buttons.addWidget(cancel_btn)

        layout.addLayout(buttons)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            root_path = root_edit.text().strip()
            if not root_path or not os.path.exists(root_path):
                QMessageBox.warning(self, "Lỗi", "Vui lòng chọn thư mục hợp lệ!")
                return

            min_images = min_images_spin.value()
            extensions = [ext.strip() for ext in extensions_edit.text().split(',')]
            delete_empty = delete_empty_check.isChecked()

            self.start_scan(root_path, extensions, min_images, delete_empty)

    def browse_root_folder(self, line_edit):
        """Chọn thư mục gốc"""
        folder = QFileDialog.getExistingDirectory(self, "Chọn thư mục gốc")
        if folder:
            line_edit.setText(folder)

    def start_scan(self, root_path: str, extensions: List[str], min_images: int, delete_empty: bool = False):
        """Bắt đầu quét thư mục"""
        try:
            # Cleanup any existing scan first
            self.cleanup_scan()

            # Progress dialog
            self.progress_dialog = QProgressDialog("Đang quét thư mục...", "Hủy", 0, 100, self)
            self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
            self.progress_dialog.setMinimumDuration(0)
            self.progress_dialog.canceled.connect(self.cancel_scan)
            self.progress_dialog.show()

            # Worker thread with delete empty folder option
            self.scan_worker = FolderScanWorker(root_path, extensions, min_images, delete_empty)

            # Connect signals with QueuedConnection for thread safety
            self.scan_worker.progress_update.connect(self.on_scan_progress, Qt.ConnectionType.QueuedConnection)
            self.scan_worker.folder_found.connect(self.on_folder_found, Qt.ConnectionType.QueuedConnection)
            self.scan_worker.finished.connect(self.on_scan_finished, Qt.ConnectionType.QueuedConnection)

            # Disable scan button
            self.scan_btn.setEnabled(False)

            self.scan_worker.start()

        except Exception as e:
            self.logger.error(f"Error starting scan: {str(e)}")
            QMessageBox.critical(self, "Lỗi", f"Không thể bắt đầu quét: {str(e)}")
            self.cleanup_scan()

    def cleanup_scan(self):
        """Cleanup scan resources safely"""
        try:
            if self.scan_worker and self.scan_worker.isRunning():
                self.scan_worker.cancel()
                # Đợi thread kết thúc gracefully với timeout ngắn hơn
                if not self.scan_worker.wait(3000):  # Wait 3 seconds max
                    self.logger.warning("Force terminating scan worker")
                    self.scan_worker.terminate()
                    self.scan_worker.wait(1000)

            if self.scan_worker:
                try:
                    # Disconnect all signals```python
                    self.scan_worker.progress_update.disconnect()
                    self.scan_worker.folder_found.disconnect()
                    self.scan_worker.finished.disconnect()
                except:
                    pass

                self.scan_worker.deleteLater()
                self.scan_worker = None

            if self.progress_dialog:
                try:
                    self.progress_dialog.close()
                    self.progress_dialog.deleteLater()
                    self.progress_dialog = None
                except:
                    pass

            # Re-enable scan button với kiểm tra an toàn
            try:
                if hasattr(self, 'scan_btn') and self.scan_btn is not None:
                    # Kiểm tra widget chưa bị xóa
                    if not hasattr(self.scan_btn, 'deleteLater') or self.scan_btn.parent() is not None:
                        self.scan_btn.setEnabled(True)
            except RuntimeError:
                # Widget đã bị xóa, bỏ qua
                pass
        except Exception as e:
            self.logger.error(f"Error in cleanup_scan: {str(e)}")

    def cancel_scan(self):
        """Cancel current scan"""
        try:
            if self.scan_worker:
                self.scan_worker.cancel()

        except Exception as e:
            self.logger.error(f"Error canceling scan: {str(e)}")

    def on_scan_progress(self, percent, message):
        """Cập nhật tiến độ quét"""
        try:
            if self.progress_dialog:
                self.progress_dialog.setValue(percent)
                self.progress_dialog.setLabelText(message)
        except:
            pass

    def on_folder_found(self, folder_data):
        """Xử lý khi tìm thấy thư mục"""
        try:
            if not self.db_manager:
                self.logger.warning("Database manager not available")
                return

            if not folder_data or not folder_data.get('path'):
                self.logger.warning("Invalid folder data")
                return

            # Kiểm tra xem thư mục đã tồn tại chưa
            existing = self.db_manager.get_folder_scan_by_path(folder_data['path'])
            if not existing:
                self.db_manager.create_folder_scan(folder_data)
                self.logger.debug(f"Created new folder scan: {folder_data['path']}")
            else:
                # Chỉ cập nhật nếu chưa completed để tránh ghi đè
                if existing.get('status') != 'completed':
                    # Cập nhật số lượng ảnh nếu thay đổi
                    if existing['image_count'] != folder_data['image_count']:
                        folder_data['id'] = existing['id']
                        # Giữ nguyên trạng thái hiện tại
                        folder_data['status'] = existing.get('status', 'pending')
                        self.db_manager.update_folder_scan(existing['id'], folder_data)
                        self.logger.debug(f"Updated folder scan: {folder_data['path']}")
                else:
                    self.logger.debug(f"Skipped completed folder: {folder_data['path']}")

        except Exception as e:
            self.logger.error(f"Lỗi lưu folder scan: {str(e)}")
            # Don't propagate the error to avoid crashing the scan

    def on_scan_finished(self, success, message):
        """Hoàn thành quét"""
        try:
            # Cleanup resources first
            self.cleanup_scan()

            # Show result với kiểm tra widget còn tồn tại
            if success:
                # Enable save button với kiểm tra an toàn
                try:
                    if hasattr(self, 'save_scan_btn') and self.save_scan_btn is not None:
                        if not hasattr(self.save_scan_btn, 'deleteLater') or self.save_scan_btn.parent() is not None:
                            self.save_scan_btn.setEnabled(True)
                except RuntimeError:
                    pass

                try:
                    if self.parent() is not None:  # Kiểm tra parent widget còn tồn tại
                        QMessageBox.information(self, "Thành công", message)
                        # Delay load to ensure cleanup and avoid conflicts
                        QTimer.singleShot(500, self.load_data)
                except RuntimeError:
                    pass
            else:
                try:
                    if self.parent() is not None:
                        QMessageBox.critical(self, "Lỗi", message)
                except RuntimeError:
                    pass

        except Exception as e:
            self.logger.error(f"Error in on_scan_finished: {str(e)}")
            try:
                if self.parent() is not None:
                    QMessageBox.critical(self, "Lỗi", f"Lỗi khi hoàn thành quét: {str(e)}")
            except RuntimeError:
                pass

    def load_data(self):
        """Load dữ liệu với bảo vệ chống đệ quy"""
        # Ngăn đệ quy
        if self._is_loading:
            return

        self._is_loading = True
        try:
            if not self.db_manager:
                print("Database manager not initialized")
                return

            folders = self.db_manager.get_all_folder_scans()

            # Tự động cập nhật data_name nếu trống
            self.fix_missing_data_names(folders)

            if folders is not None:
                self.populate_table(folders)
                self.update_stats(folders)
                # Không gọi load_filter_options để tránh đệ quy
            else:
                print("No folder data returned from database")
                if hasattr(self, 'table'):
                    self.table.setRowCount(0)
                    self.update_stats([])

        except Exception as e:
            print(f"Lỗi load data trong folder_scanner: {str(e)}")
            if hasattr(self, 'table'):
                self.table.setRowCount(0)
                self.update_stats([])
        finally:
            self._is_loading = False

    def fix_missing_data_names(self, folder_scans):
        """Tự động điền data_name từ original_title nếu trống"""
        try:
            updated_count = 0
            for folder in folder_scans:
                # Nếu data_name trống hoặc None, sử dụng original_title
                if not folder.get('data_name') or folder.get('data_name', '').strip() == '':
                    original_title = folder.get('original_title', '')
                    if original_title and folder.get('id'):
                        # Cập nhật database
                        update_data = {'data_name': original_title}
                        success = self.db_manager.update_folder_scan(folder.get('id'), update_data)
                        if success:
                            folder['data_name'] = original_title  # Cập nhật trong memory
                            updated_count += 1

            if updated_count > 0:
                self.logger.info(f"Đã tự động cập nhật data_name cho {updated_count} folder scans")

        except Exception as e:
            self.logger.error(f"Lỗi fix missing data names: {str(e)}")

    def load_filter_options(self):
        """Load options cho filter combo boxes"""
        try:
            if not self.db_manager:
                self.logger.warning("Database manager not available for loading filter options")
                return

            # Load sites cho filter
            sites = self.db_manager.get_all_sites()
            self.filter_site_combo.clear()
            self.filter_site_combo.addItem("Tất cả sites", None)

            for site in sites:
                site_name = site.name if hasattr(site, 'name') else str(site.get('name', 'Unknown'))
                site_id = site.id if hasattr(site, 'id') else site.get('id')
                if site_name and site_id:
                    self.filter_site_combo.addItem(site_name, site_id)

            # Load categories cho filter với thông tin site
            categories = self.db_manager.get_all_categories()
            self.filter_category_combo.clear()
            self.filter_category_combo.addItem("Tất cả danh mục", None)

            for category in categories:
                category_name = category.get('name', '')
                category_id = category.get('id')

                if category_name and category_id:
                    # Lấy tên site cho category
                    site_name = ""
                    site_id = category.get('site_id')
                    if site_id:
                        site = self.db_manager.get_site_by_id(site_id)
                        if site:
                            site_name = site.name if hasattr(site, 'name') else str(site.get('name', ''))

                    # Tạo display name với site info
                    if site_name:
                        display_name = f"{category_name} ({site_name})"
                    else:
                        display_name = category_name

                    self.filter_category_combo.addItem(display_name, category_id)

        except Exception as e:
            self.logger.error(f"Error loading filter options: {str(e)}")
            # Đảm bảo có ít nhất option mặc định
            if hasattr(self, 'filter_site_combo'):
                self.filter_site_combo.clear()
                self.filter_site_combo.addItem("Tất cả sites", None)
            if hasattr(self, 'filter_category_combo'):
                self.filter_category_combo.clear()
                self.filter_category_combo.addItem("Tất cả danh mục", None)

    def bulk_edit_folders(self):
        """Sửa hàng loạt các folder được chọn"""
        try:
            selected_rows = self.table.selectionModel().selectedRows()
            if not selected_rows:
                QMessageBox.warning(self, "Cảnh báo", "Vui lòng chọn ít nhất một thư mục!")
                return

            # Tạo dialog bulk edit
            dialog = BulkFolderEditDialog(self)
            dialog.db_manager = self.db_manager
            if dialog.exec() == QDialog.DialogCode.Accepted:
                update_data = dialog.get_update_data()
                if not update_data:
                    return

                # Lấy IDs của các folder được chọn
                folder_ids = []
                for selected_row in selected_rows:
                    row = selected_row.row()
                    folder_id = self.table.item(row, 0).text()
                    if folder_id:
                        folder_ids.append(int(folder_id))

                # Thực hiện bulk update
                updated_count = self.db_manager.bulk_update_folder_scans(folder_ids, update_data)

                # Reload data
                self.load_data()

                QMessageBox.information(
                    self, "Thành công", 
                    f"Đã cập nhật {updated_count} thư mục thành công!"
                )

        except Exception as e:
            self.logger.error(f"Error bulk editing folders: {str(e)}")
            QMessageBox.critical(self, "Lỗi", f"Không thể sửa hàng loạt: {str(e)}")

    def filter_data(self):
        """Lọc dữ liệu theo các tiêu chí"""
        try:
            if not self.db_manager:
                return

            search_term = self.search_edit.text().strip()
            site_id = self.filter_site_combo.currentData()
            category_id = self.filter_category_combo.currentData()
            status_filter = self.status_combo.currentText()

            # Lấy dữ liệu ban đầu
            if search_term:
                folders = self.db_manager.search_folder_scans(search_term)
            else:
                folders = self.db_manager.get_all_folder_scans()

            # Apply filters
            if site_id:
                folders = [f for f in folders if f.get('site_id') == site_id]

            if category_id:
                folders = [f for f in folders if f.get('category_id') == category_id]

            if status_filter and status_filter != "Tất cả":
                if status_filter == "Chưa hoàn thành":
                    # Lọc những thư mục chưa hoàn thành (không phải completed)
                    folders = [f for f in folders if f.get('status') != 'completed']
                else:
                    folders = [f for f in folders if f.get('status') == status_filter]

            self.populate_table(folders)
            self.update_stats(folders)

        except Exception as e:
            self.logger.error(f"Error filtering data: {str(e)}")

    def populate_table(self, folders: List[Dict[str, Any]]):
        """Điền dữ liệu vào table"""
        try:
            self.table.setRowCount(len(folders))

            for row, folder in enumerate(folders):
                # ID
                self.table.setItem(row, 0, QTableWidgetItem(str(folder.get('id', ''))))

                # Tên data - ưu tiên data_name, fallback về original_title
                data_name = folder.get('data_name', '') or folder.get('original_title', 'Unknown')
                self.table.setItem(row, 1, QTableWidgetItem(data_name))

                # Tiêu đề gốc
                self.table.setItem(row, 2, QTableWidgetItem(folder.get('original_title', '')))

                # Đường dẫn
                path_item = QTableWidgetItem(folder.get('path', ''))
                path_item.setToolTip(folder.get('path', ''))
                self.table.setItem(row, 3, path_item)

                # Số ảnh
                count_item = QTableWidgetItem(str(folder.get('image_count', 0)))
                count_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row, 4, count_item)

                # Mô tả
                desc = folder.get('description', '')
                if len(desc) > 50:
                    desc = desc[:50] + "..."
                desc_item = QTableWidgetItem(desc)
                desc_item.setToolTip(folder.get('description', ''))
                self.table.setItem(row, 5, desc_item)

                # Site
                site_name = folder.get('site_name', '')
                self.table.setItem(row, 6, QTableWidgetItem(site_name))

                # Danh mục
                category_name = folder.get('category_name', '')
                self.table.setItem(row, 7, QTableWidgetItem(category_name))

                # Trạng thái
                status = folder.get('status', 'pending')
                status_item = QTableWidgetItem(self.format_status(status))
                self.table.setItem(row, 8, status_item)

                # Tiêu đề mới
                new_title = folder.get('new_title', '')
                if len(new_title) > 30:
                    new_title = new_title[:30] + "..."
                new_title_item = QTableWidgetItem(new_title)
                new_title_item.setToolTip(folder.get('new_title', ''))
                self.table.setItem(row, 9, new_title_item)

                # Ngày tạo
                created_at = folder.get('created_at', '')
                if created_at:
                    try:
                        from datetime import datetime
                        dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                        created_at = dt.strftime('%d/%m/%Y %H:%M')
                    except:
                        pass
                self.table.setItem(row, 10, QTableWidgetItem(created_at))
        except Exception as e:
            self.logger.error(f"Error populating table: {str(e)}")

    def format_status(self, status: str) -> str:
        """Format trạng thái hiển thị"""
        status_map = {
            'pending': '⏳ Chờ xử lý',
            'processing': '🔄 Đang xử lý',
            'completed': '✅ Hoàn thành',
            'error': '❌ Lỗi'
        }
        return status_map.get(status, f"❓ {status}")

    def update_stats(self, folders: List[Dict[str, Any]]):
        """Cập nhật thống kê"""
        total = len(folders)
        if hasattr(self, 'stats_label'):
            self.stats_label.setText(f"Tổng: {total} thư mục")

    def search_folders(self):
        """Tìm kiếm thư mục"""
        search_term = self.search_edit.text().strip()
        if not search_term:
            self.load_data()
            return

        if not self.db_manager:
            return

        try:
            folders = self.db_manager.search_folder_scans(search_term)
            self.populate_table(folders)
            self.update_stats(folders)

        except Exception as e:
            print(f"Lỗi tìm kiếm trong folder_scanner: {str(e)}")

    def filter_data(self):
        """Lọc dữ liệu theo trạng thái"""
        # Không gọi load_data() để tránh recursion
        # Chỉ filter dữ liệu hiện có
        try:
            if hasattr(self, 'table') and self.table is not None:
                # Chỉ hiển thị dữ liệu đã có, không reload
                pass
        except Exception as e:
            print(f"Lỗi filter data: {str(e)}")

    def on_selection_changed(self):
        """Xử lý khi selection thay đổi"""
        try:
            selected_rows = self.table.selectionModel().selectedRows()
            has_selection = len(selected_rows) > 0

            self.edit_btn.setEnabled(has_selection)
            self.delete_btn.setEnabled(has_selection)

            if has_selection:
                row = selected_rows[0].row()
                self.show_folder_detail(row)
            else:
                self.detail_text.clear()
        except Exception as e:
            self.logger.error(f"Error in selection changed: {str(e)}")

    def show_folder_detail(self, row: int):
        """Hiển thị chi tiết thư mục"""
        try:
            folder_id = self.table.item(row, 0).text()
            if not folder_id or not self.db_manager:
                return

            folder = self.db_manager.get_folder_scan_by_id(int(folder_id))
            if folder:
                detail = f"""
<b>Tiêu đề gốc:</b> {folder.get('original_title', '')}<br>
<b>Đường dẫn:</b> {folder.get('path', '')}<br>
<b>Số lượng ảnh:</b> {folder.get('image_count', 0)}<br>
<b>Trạng thái:</b> {self.format_status(folder.get('status', ''))}<br>
<b>Tiêu đề mới:</b> {folder.get('new_title', 'Chưa có')}<br><br>
<b>Mô tả:</b><br>
{folder.get('description', 'Chưa có mô tả')}
                """.strip()
                self.detail_text.setHtml(detail)

        except Exception as e:
            self.logger.error(f"Lỗi hiển thị detail: {str(e)}")

    def add_folder(self):
        """Thêm thư mục mới"""
        try:
            dialog = FolderScanDialog(self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                folder_data = dialog.get_data()
                if not folder_data['original_title'] or not folder_data['path']:
                    QMessageBox.warning(self, "Lỗi", "Vui lòng nhập đầy đủ thông tin!")
                    return

                self.db_manager.create_folder_scan(folder_data)
                self.load_data()
                QMessageBox.information(self, "Thành công", "Đã thêm thư mục thành công!")

        except Exception as e:
            self.logger.error(f"Lỗi thêm folder: {str(e)}")
            QMessageBox.critical(self, "Lỗi", f"Không thể thêm thư mục: {str(e)}")

    def edit_folder(self):
        """Sửa thư mục"""
        try:
            selected_rows = self.table.selectionModel().selectedRows()
            if not selected_rows:
                return

            row = selected_rows[0].row()
            folder_id = self.table.item(row, 0).text()

            folder = self.db_manager.get_folder_scan_by_id(int(folder_id))
            if not folder:
                QMessageBox.warning(self, "Lỗi", "Không tìm thấy thư mục!")
                return

            dialog = FolderScanDialog(self, folder)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                folder_data = dialog.get_data()
                self.db_manager.update_folder_scan(int(folder_id), folder_data)
                self.load_data()
                QMessageBox.information(self, "Thành công", "Đã cập nhật thư mục thành công!")

        except Exception as e:
            self.logger.error(f"Lỗi sửa folder: {str(e)}")
            QMessageBox.critical(self, "Lỗi", f"Không thể sửa thư mục: {str(e)}")

    def delete_folder(self):
        """Xóa thư mục"""
        try:
            selected_rows = self.table.selectionModel().selectedRows()
            if not selected_rows:
                return

            reply = QMessageBox.question(
                self, "Xác nhận", 
                "Bạn có chắc chắn muốn xóa thư mục đã chọn?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )

            if reply == QMessageBox.StandardButton.Yes:
                # Lấy danh sách ID để xóa (phải lấy trước khi xóa để tránh thay đổi index)
                folder_ids = []
                for selected_row in selected_rows:
                    row = selected_row.row()
                    folder_id = self.table.item(row, 0).text()
                    folder_ids.append(int(folder_id))

                # Xóa từng folder
                deleted_count = 0
                failed_count = 0
                for folder_id in folder_ids:
                    try:
                        self.db_manager.delete_folder_scan(folder_id)
                        deleted_count += 1
                        self.logger.info(f"Đã xóa folder {folder_id} khỏi database")
                    except Exception as e:
                        failed_count += 1
                        self.logger.error(f"Lỗi xóa folder {folder_id}: {str(e)}")

                # Refresh dữ liệu sau khi xóa
                self.load_data()

                # Hiển thị kết quả chi tiết
                if failed_count > 0:
                    QMessageBox.warning(self, "Hoàn thành", 
                        f"Đã xóa {deleted_count} thư mục thành công!\n{failed_count} thư mục không thể xóa.")
                else:
                    QMessageBox.information(self, "Thành công", 
                        f"Đã xóa {deleted_count} thư mục khỏi database thành công!")

        except Exception as e:
            self.logger.error(f"Lỗi xóa folder: {str(e)}")
            QMessageBox.critical(self, "Lỗi", f"Không thể xóa thư mục: {str(e)}")

    def ai_generate_descriptions(self):
        """Sử dụng AI để tạo mô tả cho các thư mục được chọn"""
        try:
            # Lấy các folders được chọn
            selected_rows = self.table.selectionModel().selectedRows()
            if not selected_rows:
                QMessageBox.information(self, "Thông báo", "Vui lòng chọn ít nhất một thư mục!")
                return

            # Chuẩn bị danh sách folders cho AI
            selected_folders = []
            for selected_row in selected_rows:
                row = selected_row.row()
                folder_id = int(self.table.item(row, 0).text())

                # Lấy thông tin folder từ database
                folder_data = self.db_manager.get_folder_scan_by_id(folder_id)
                if folder_data:
                    selected_folders.append({
                        'path': folder_data.get('path', ''),
                        'original_title': folder_data.get('original_title', ''),
                        'id': folder_id
                    })

            if not selected_folders:
                QMessageBox.warning(self, "Lỗi", "Không thể lấy thông tin các thư mục được chọn!")
                return

            # Import và mở AI Generate Dialog
            from .ai_generate_dialog import AIGenerateDialog

            dialog = AIGenerateDialog(self, selected_folders)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                # Lấy kết quả AI
                results = dialog.get_results()

                if results:
                    # Cập nhật database với kết quả AI
                    updated_count = 0
                    for folder_path, result in results.items():
                        # Tìm folder ID từ path
                        folder_id = None
                        for folder in selected_folders:
                            if folder['path'] == folder_path:
                                folder_id = folder['id']
                                break

                        if folder_id:
                            try:
                                # Cập nhật cả new_title và description trong database
                                self.db_manager.update_folder_ai_content(
                                    folder_id, 
                                    result.get('title', ''),
                                    result.get('description', '')
                                )
                                updated_count += 1
                                self.logger.info(f"Updated folder {folder_id} with AI title and description")
                            except Exception as e:
                                self.logger.error(f"Error updating folder {folder_id}: {str(e)}")

                    # Refresh table để hiển thị kết quả mới
                    self.load_data()

                    QMessageBox.information(
                        self, "Thành công", 
                        f"Đã cập nhật {updated_count}/{len(results)} thư mục với nội dung AI!"
                    )
                else:
                    QMessageBox.information(self, "Thông báo", "Không có kết quả AI nào để áp dụng!")

        except ImportError:
            QMessageBox.critical(self, "Lỗi", "Không thể import AI Generate Dialog!")
        except Exception as e:
            self.logger.error(f"Lỗi AI generate: {str(e)}")
            QMessageBox.critical(self, "Lỗi", f"Không thể thực hiện AI generate: {str(e)}")

    def open_ai_config_dialog(self):
        """Mở dialog cấu hình AI"""
        try:
            from .ai_config_dialog import AIConfigDialog

            dialog = AIConfigDialog(self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                QMessageBox.information(self, "Thành công", "Đã lưu cấu hình AI thành công!")

        except ImportError:
            QMessageBox.critical(self, "Lỗi", "Không thể import AI Config Dialog!")
        except Exception as e:
            self.logger.error(f"Lỗi mở AI config: {str(e)}")
            QMessageBox.critical(self, "Lỗi", f"Không thể mở cấu hình AI: {str(e)}")

    def ai_generate_descriptions_placeholder(self):
        """Placeholder function cho AI generate descriptions của thư mục được chọn"""
        try:
            if not hasattr(self, 'table') or not self.table:
                return

            selected_rows = self.table.selectionModel().selectedRows()
            if not selected_rows:
                QMessageBox.information(self, "Thông báo", "Vui lòng chọn ít nhất một thư mục để tạo mô tả!")
                return

            # Hiển thị dialog xác nhận
            reply = QMessageBox.question(
                self, "Xác nhận AI", 
                f"Bạn có muốn sử dụng AI để tạo mô tả cho {len(selected_rows)} thư mục được chọn?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )

            if reply == QMessageBox.StandardButton.Yes:
                # Placeholder - sẽ tích hợp API AI sau này
                QMessageBox.information(
                    self, "Chức năng AI", 
                    "Chức năng AI tạo mô tả đang được phát triển.\n"
                    "Hiện tại cột mô tả đã được để trống để chuẩn bị cho tích hợp AI."
                )

        except Exception as e:
            self.logger.error(f"Lỗi AI generate: {str(e)}")
            QMessageBox.critical(self, "Lỗi", f"Không thể tạo mô tả AI: {str(e)}")

    def export_csv(self):
        """Export dữ liệu ra CSV"""
        try:
            if self.table.rowCount() == 0:
                QMessageBox.information(self, "Thông báo", "Không có dữ liệu để export!")
                return

            file_path, _ = QFileDialog.getSaveFileName(
                self, "Export CSV", "folder_scans.csv", "CSV files (*.csv)"
            )

            if file_path:
                import csv

                with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.writer(csvfile)

                    # Headers
                    headers = [
                        "ID", "Tiêu đề gốc", "Đường dẫn", "Số ảnh",
                        "Mô tả", "Trạng thái", "Tiêu đề mới", "Ngày tạo"
                    ]
                    writer.writerow(headers)

                    # Data
                    for row in range(self.table.rowCount()):
                        row_data = []
                        for col in range(self.table.columnCount()):
                            item = self.table.item(row, col)
                            row_data.append(item.text() if item else "")
                        writer.writerow(row_data)

                QMessageBox.information(self, "Thành công", f"Đã export dữ liệu ra: {file_path}")

        except Exception as e:
            self.logger.error(f"Lỗi export CSV: {str(e)}")
            QMessageBox.critical(self, "Lỗi", f"Không thể export CSV: {str(e)}")

    def save_scan_results(self):
        """Lưu kết quả quét hiện tại với tên để quản lý"""
        try:
            from datetime import datetime
            import json
            from PyQt6.QtWidgets import QInputDialog

            # Dialog nhập tên cho bộ kết quả quét
            name, ok = QInputDialog.getText(
                self, 
                "Lưu kết quả quét", 
                "Nhập tên cho bộ kết quả quét:",
                text=f"Scan_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            )

            if not ok or not name.strip():
                return

            if not self.db_manager:
                QMessageBox.warning(self, "Lỗi", "Database manager chưa khởi tạo!")
                return

            # Lấy tất cả folder scans hiện tại
            folders = self.db_manager.get_all_folder_scans()
            if not folders:
                QMessageBox.information(self, "Thông báo", "Không có dữ liệu để lưu!")
                return

            # Tạo saved scan record
            scan_data = {
                'name': name.strip(),
                'description': f"Scan kết quả với {len(folders)} thư mục",
                'folder_count': len(folders),
                'created_at': datetime.now(),
                'data': json.dumps(folders, ensure_ascii=False, default=str)
            }

            self.db_manager.create_saved_scan(scan_data)
            QMessageBox.information(self, "Thành công", f"Đã lưu kết quả quét: {name}")

        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Lỗi lưu kết quả: {str(e)}")

    def load_saved_results(self):
        """Load kết quả quét đã lưu"""
        try:
            if not self.db_manager:
                QMessageBox.warning(self, "Lỗi", "Database manager chưa khởi tạo!")
                return

            saved_scans = self.db_manager.get_all_saved_scans()
            if not saved_scans:
                QMessageBox.information(self, "Thông báo", "Không có kết quả quét đã lưu!")
                return

            # Dialog chọn kết quả đã lưu
            dialog = QDialog(self)
            dialog.setWindowTitle("Load kết quả đã lưu")
            dialog.setModal(True)
            dialog.resize(600, 400)

            layout = QVBoxLayout(dialog)

            # Table hiển thị saved scans
            table = QTableWidget()
            table.setColumnCount(4)
            table.setHorizontalHeaderLabels(["Tên", "Mô tả", "Số thư mục", "Ngày tạo"])
            table.setRowCount(len(saved_scans))
            table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)

            for i, scan in enumerate(saved_scans):
                table.setItem(i, 0, QTableWidgetItem(scan.get('name', '')))
                table.setItem(i, 1, QTableWidgetItem(scan.get('description', '')))
                table.setItem(i, 2, QTableWidgetItem(str(scan.get('folder_count', 0))))
                table.setItem(i, 3, QTableWidgetItem(str(scan.get('created_at', ''))))
                table.item(i, 0).setData(Qt.ItemDataRole.UserRole, scan.get('id'))

            table.resizeColumnsToContents()
            layout.addWidget(table)

            # Buttons
            button_layout = QHBoxLayout()
            load_btn = QPushButton("Load")
            delete_btn = QPushButton("Xóa")
            cancel_btn = QPushButton("Hủy")

            button_layout.addWidget(load_btn)
            button_layout.addWidget(delete_btn)
            button_layout.addStretch()
            button_layout.addWidget(cancel_btn)
            layout.addLayout(button_layout)

            # Event handlers
            def load_selected():
                if table.currentRow() >= 0:
                    scan_id = table.item(table.currentRow(), 0).data(Qt.ItemDataRole.UserRole)
                    self.load_scan_data(scan_id)
                    dialog.accept()
                else:
                    QMessageBox.warning(dialog, "Lỗi", "Vui lòng chọn kết quả để load!")

            def delete_selected():
                if table.currentRow() >= 0:
                    scan_name = table.item(table.currentRow(), 0).text()
                    scan_id = table.item(table.currentRow(), 0).data(Qt.ItemDataRole.UserRole)

                    reply = QMessageBox.question(
                        dialog, "Xác nhận", 
                        f"Bạn có chắc muốn xóa kết quả '{scan_name}'?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                    )

                    if reply == QMessageBox.StandardButton.Yes:
                        self.db_manager.delete_saved_scan(scan_id)
                        table.removeRow(table.currentRow())
                        QMessageBox.information(dialog, "Thành công", "Đã xóa kết quả!")
                else:
                    QMessageBox.warning(dialog, "Lỗi", "Vui lòng chọn kết quả để xóa!")

            load_btn.clicked.connect(load_selected)
            delete_btn.clicked.connect(delete_selected)
            cancel_btn.clicked.connect(dialog.reject)

            dialog.exec()

        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Lỗi load kết quả: {str(e)}")

    def load_scan_data(self, scan_id):
        """Load dữ liệu từ saved scan"""
        try:
            import json

            saved_scan = self.db_manager.get_saved_scan_by_id(scan_id)
            if not saved_scan:
                QMessageBox.warning(self, "Lỗi", "Không tìm thấy dữ liệu!")
                return

            # Parse JSON data
            folder_data = json.loads(saved_scan.get('data', '[]'))

            # Clear current table và load dữ liệu mới
            self.populate_table(folder_data)
            self.update_stats(folder_data)

            # Disable save button vì đây là dữ liệu đã lưu
            if hasattr(self, 'save_scan_btn'):
                self.save_scan_btn.setEnabled(False)

            QMessageBox.information(
                self, "Thành công", 
                f"Đã load kết quả: {saved_scan.get('name', '')}"
            )

        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Lỗi load dữ liệu: {str(e)}")

    def upload_to_woocommerce(self):
        """Đăng các thư mục đã chọn lên WooCommerce"""
        try:
            # Lấy các folder được chọn
            selected_rows = self.table.selectionModel().selectedRows()
            if not selected_rows:
                QMessageBox.information(self, "Thông báo", "Vui lòng chọn ít nhất một thư mục để đăng!")
                return

            # Lấy dữ liệu các folder được chọn
            selected_folders = []
            for selected_row in selected_rows:
                row = selected_row.row()
                folder_id = self.table.item(row, 0).text()

                if folder_id and self.db_manager:
                    folder_data = self.db_manager.get_folder_scan_by_id(int(folder_id))
                    if folder_data:
                        selected_folders.append(folder_data)

            if not selected_folders:
                QMessageBox.warning(self, "Lỗi", "Không thể lấy thông tin các thư mục được chọn!")
                return

            # Kiểm tra có sites không
            sites = self.db_manager.get_active_sites() if self.db_manager else []
            if not sites:
                QMessageBox.warning(self, "Lỗi", "Không có site WooCommerce nào hoạt động!\nVui lòng thêm site trong tab Quản lý Site.")
                return

            # Hỏi người dùng muốn upload đơn lẻ hay hàng loạt
            if len(selected_folders) > 1:
                reply = QMessageBox.question(
                    self, "Chọn chế độ upload",
                    f"Bạn đã chọn {len(selected_folders)} thư mục.\n"
                    "Bạn muốn upload như thế nào?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel,
                    QMessageBox.StandardButton.Yes
                )

                # Đặt text cho các nút
                yes_btn = QMessageBox.StandardButton.Yes
                no_btn = QMessageBox.StandardButton.No

                if reply == yes_btn:
                    # Bulk upload mode
                    from .product_upload_dialog import ProductUploadDialog
                    dialog = ProductUploadDialog(self, sites, self.db_manager, selected_folders)
                elif reply == no_btn:
                    # Single upload mode - chọn folder đầu tiên
                    from .product_upload_dialog import ProductUploadDialog
                    dialog = ProductUploadDialog(self, sites, self.db_manager)
                else:
                    return
            else:
                # Single folder upload
                from .product_upload_dialog import ProductUploadDialog
                dialog = ProductUploadDialog(self, sites, self.db_manager)

            if dialog.exec() == QDialog.DialogCode.Accepted:
                # Refresh data sau khi đăng
                self.load_data()
                QMessageBox.information(
                    self, "Thông báo", 
                    "Quá trình đăng sản phẩm đã hoàn thành!\nKiểm tra trong WooCommerce admin để xem kết quả."
                )

        except ImportError:
            QMessageBox.critical(self, "Lỗi", "Không thể import Product Upload Dialog!")
        except Exception as e:
            self.logger.error(f"Lỗi upload to WooCommerce: {str(e)}")
            QMessageBox.critical(self, "Lỗi", f"Không thể đăng lên WooCommerce: {str(e)}")

    def get_selected_folder(self):
        """Lấy thư mục được chọn"""
        current_row = self.table.currentRow()
        if current_row >= 0 and current_row < len(self.folders):
            return self.folders[current_row]
        return None

    def get_selected_folders(self):
        """Lấy danh sách các thư mục được chọn"""
        selected_folders = []
        for row in range(self.table.rowCount()):
            if self.table.item(row, 0) and self.table.item(row, 0).isSelected():
                if row < len(self.folders):
                    selected_folders.append(self.folders[row])

        # Nếu không có gì được chọn bằng selection, lấy folder hiện tại
        if not selected_folders:
            current_folder = self.get_selected_folder()
            if current_folder:
                selected_folders.append(current_folder)

        return selected_folders

    def open_ai_generate_dialog(self):
        """Mở dialog AI Generate để tạo nội dung AI cho các folders đã chọn"""
        selected_folders = self.get_selected_folders()

        if not selected_folders:
            QMessageBox.warning(self, "Cảnh báo", "Vui lòng chọn ít nhất một thư mục để tạo nội dung AI!")
            return

        try:
            from .ai_dialogs import AIGenerateDialog
            dialog = AIGenerateDialog(self, selected_folders)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                # Refresh data after AI generation
                self.load_data()
                self.status_message.emit("Đã hoàn thành tạo nội dung AI")
        except ImportError:
            QMessageBox.information(self, "Thông báo", 
                                  "Tính năng AI chưa được cài đặt.\n"
                                  "Vui lòng cấu hình API key trong phần ⚙️ Cấu hình AI")
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Không thể mở dialog AI Generate:\n{str(e)}")