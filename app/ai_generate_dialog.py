# Applying the requested changes to add image renaming functionality with conflict resolution.
"""
AI Generate Dialog - Dialog xử lý tạo nội dung AI cho nhiều folders với đa luồng
"""

import os
import json
from typing import List, Dict, Any
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QProgressBar, QTextEdit, QGroupBox,
    QMessageBox, QHeaderView, QAbstractItemView, QSplitter,
    QSpinBox, QFormLayout, QCheckBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QThreadPool, QRunnable, QObject, QMutex, QMutexLocker
from PyQt6.QtGui import QFont

from .gemini_service import GeminiService


class AIGenerateSignals(QObject):
    """Signals cho AI Generation worker"""
    progress_updated = pyqtSignal(int, int, str)  # current, total, current_folder
    folder_completed = pyqtSignal(str, dict)  # folder_path, result
    folder_failed = pyqtSignal(str, str)  # folder_path, error
    quota_exceeded = pyqtSignal()  # Signal khi hết quota API


class AIGenerateWorker(QRunnable):
    """Worker runnable để xử lý AI generation cho một folder"""

    def __init__(self, folder: Dict, config: Dict, signals: AIGenerateSignals, mutex: QMutex):
        super().__init__()
        self.folder = folder
        self.config = config
        self.signals = signals
        self.mutex = mutex
        self._is_cancelled = False

    def run(self):
        """Chạy AI generation cho một folder"""
        if self._is_cancelled:
            return

        try:
            folder_path = self.folder['path']
            folder_name = os.path.basename(folder_path)

            # Tạo service Gemini với nhiều API keys
            api_keys = self.config.get('api_keys', [])
            if not api_keys and self.config.get('api_key'):  # Backward compatibility
                api_keys = [self.config.get('api_key')]

            service = GeminiService(api_keys=api_keys)

            # Log API keys status
            status = service.get_api_keys_status()
            print(f"DEBUG - Using {status['total_keys']} API keys, current: {status['current_key_preview']}")

            # Generate title
            title_prompt = self.config.get('title_prompt', '').format(
                folder_name=folder_name,
                folder_path=folder_path
            )

            # Generate description  
            description_prompt = self.config.get('description_prompt', '').format(
                folder_name=folder_name,
                folder_path=folder_path
            )

            # Tìm ảnh đầu tiên trong thư mục
            first_image = service.find_first_image(folder_path)
            if not first_image:
                self.signals.folder_failed.emit(folder_path, "Không tìm thấy ảnh trong thư mục")
                return

            # Encode ảnh
            image_base64 = service.encode_image_to_base64(first_image)
            if not image_base64:
                self.signals.folder_failed.emit(folder_path, "Không thể đọc ảnh")
                return

            # Call API để tạo nội dung
            title_result = service._generate_text_with_image(image_base64, first_image, title_prompt)

            # Kiểm tra lỗi API quota
            if title_result is None:
                # Có thể là lỗi quota, thử lần nữa với description
                description_result = service._generate_text_with_image(image_base64, first_image, description_prompt)
                if description_result is None:
                    # Cả 2 đều thất bại, có thể hết quota
                    self.signals.folder_failed.emit(folder_path, "API_QUOTA_EXCEEDED")
                    return
            else:
                description_result = service._generate_text_with_image(image_base64, first_image, description_prompt)

            if not self._is_cancelled:
                # Tạo fallback description tốt hơn
                fallback_description = self._create_fallback_description(folder_name, first_image)

                result = {
                    'title': title_result.strip() if title_result else folder_name,
                    'description': description_result.strip() if description_result else fallback_description,
                    'image_used': first_image
                }

                self.signals.folder_completed.emit(folder_path, result)

        except Exception as e:
            if not self._is_cancelled:
                error_msg = f"AI Generation failed: {str(e)}"
                print(f"DEBUG - Folder: {folder_path}")
                print(f"DEBUG - Error: {error_msg}")
                print(f"DEBUG - Title result: {title_result if 'title_result' in locals() else 'Not generated'}")
                print(f"DEBUG - Description result: {description_result if 'description_result' in locals() else 'Not generated'}")
                self.signals.folder_failed.emit(folder_path, error_msg)

    def cancel(self):
        """Hủy worker"""
        self._is_cancelled = True

    def _create_fallback_description(self, folder_name: str, image_path: str) -> str:
        """Tạo mô tả fallback khi AI generation thất bại"""
        try:
            # Phân tích folder name để tạo mô tả tốt hơn
            parts = folder_name.replace('-', ' ').replace('_', ' ').split()

            # Tìm team name (thường ở đầu)
            team = parts[0] if parts else "Team"

            # Tìm product type
            product_type = "Hawaiian Shirt"
            for part in parts:
                if any(keyword in part.lower() for keyword in ['shirt', 'jersey', 'hoodie', 'cap', 'hat']):
                    product_type = part.title()
                    break

            # Tạo mô tả cơ bản
            description = f"Show your {team} pride with this stylish {product_type}. "
            description += f"Perfect for game day, casual wear, or showing team support. "
            description += f"Features high-quality materials and authentic team styling. "
            description += f"Great gift for {team} fans of all ages!"

            return description

        except Exception:
            return f"High-quality {folder_name.replace('-', ' ')} - Perfect for fans and collectors"


class AIGenerateManager(QThread):
    """Manager thread để quản lý các worker threads"""

    progress_updated = pyqtSignal(int, int, str)  # current, total, current_folder
    folder_completed = pyqtSignal(str, dict)  # folder_path, result
    folder_failed = pyqtSignal(str, str)  # folder_path, error
    quota_exceeded = pyqtSignal()  # Signal khi hết quota API
    finished = pyqtSignal()

    def __init__(self, folders: List[Dict], config: Dict, max_threads: int = 3):
        super().__init__()
        self.folders = folders
        self.config = config
        self.max_threads = max_threads
        self._is_cancelled = False
        self.completed_count = 0
        self.total_count = len(folders)
        self.mutex = QMutex()

        # Thread pool
        self.thread_pool = QThreadPool()
        self.thread_pool.setMaxThreadCount(max_threads)

        # Signals
        self.signals = AIGenerateSignals()
        self.signals.folder_completed.connect(self.on_folder_completed)
        self.signals.folder_failed.connect(self.on_folder_failed)
        self.signals.quota_exceeded.connect(self.on_quota_exceeded)

        # Quota tracking
        self.quota_exceeded_count = 0

    def run(self):
        """Chạy AI generation với đa luồng"""
        try:
            # Submit all workers to thread pool
            for folder in self.folders:
                if self._is_cancelled:
                    break

                worker = AIGenerateWorker(folder, self.config, self.signals, self.mutex)
                self.thread_pool.start(worker)

            # Wait for all threads to complete
            self.thread_pool.waitForDone()

            if not self._is_cancelled:
                self.finished.emit()

        except Exception as e:
            self.folder_failed.emit("", f"Lỗi manager: {str(e)}")
            self.finished.emit()

    def on_folder_completed(self, folder_path: str, result: dict):
        """Xử lý khi hoàn thành một folder"""
        with QMutexLocker(self.mutex):
            self.completed_count += 1

        folder_name = os.path.basename(folder_path)
        self.progress_updated.emit(
            self.completed_count, 
            self.total_count, 
            f"Hoàn thành: {folder_name}"
        )
        self.folder_completed.emit(folder_path, result)

    def on_folder_failed(self, folder_path: str, error: str):
        """Xử lý khi lỗi một folder"""
        with QMutexLocker(self.mutex):
            self.completed_count += 1

            # Kiểm tra nếu là lỗi quota
            if error == "API_QUOTA_EXCEEDED":
                self.quota_exceeded_count += 1
                if self.quota_exceeded_count >= 3:  # Nếu có 3 lỗi quota liên tiếp
                    self.quota_exceeded.emit()
                    return

        folder_name = os.path.basename(folder_path)
        self.progress_updated.emit(
            self.completed_count, 
            self.total_count, 
            f"Lỗi: {folder_name}"
        )
        self.folder_failed.emit(folder_path, error)

    def on_quota_exceeded(self):
        """Xử lý khi hết quota API"""
        self.quota_exceeded.emit()

    def cancel(self):
        """Hủy tất cả xử lý"""
        self._is_cancelled = True
        self.thread_pool.clear()
        self.thread_pool.waitForDone(3000)


class AIGenerateDialog(QDialog):
    """Dialog xử lý AI generation với đa luồng"""

    def __init__(self, parent=None, folders: List[Dict] = None):
        super().__init__(parent)
        self.folders = folders or []
        self.results = {}  # folder_path -> result
        self.manager = None
        self.config = {}

        self.init_ui()
        self.load_config()
        self.populate_folders()

    def init_ui(self):
        """Khởi tạo giao diện"""
        self.setWindowTitle("🤖 AI Generate Content (Multi-threaded)")
        self.setModal(True)
        self.resize(900, 700)

        layout = QVBoxLayout(self)

        # Header info và cấu hình
        header_group = QGroupBox("Cấu hình xử lý")
        header_layout = QFormLayout(header_group)

        # Thông tin
        self.info_label = QLabel(f"Tạo nội dung AI cho {len(self.folders)} thư mục")
        self.info_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        header_layout.addRow("Thông tin:", self.info_label)

        # Số luồng
        thread_layout = QHBoxLayout()
        self.thread_spin = QSpinBox()
        self.thread_spin.setRange(1, 10)
        self.thread_spin.setValue(3)
        self.thread_spin.setToolTip("Số luồng xử lý đồng thời (1-10)")
        thread_layout.addWidget(self.thread_spin)

        thread_layout.addWidget(QLabel("luồng đồng thời"))
        thread_layout.addStretch()

        header_layout.addRow("Đa luồng:", thread_layout)

        # Auto apply results
        self.auto_apply_check = QCheckBox("Tự động áp dụng kết quả")
        self.auto_apply_check.setChecked(True)
        self.auto_apply_check.setToolTip("Tự động áp dụng kết quả thành công vào database")
        header_layout.addRow("Tự động:", self.auto_apply_check)

        layout.addWidget(header_group)

        # Progress
        progress_layout = QHBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        progress_layout.addWidget(self.progress_bar)

        self.status_label = QLabel("Sẵn sàng")
        progress_layout.addWidget(self.status_label)

        layout.addLayout(progress_layout)

        # Splitter
        splitter = QSplitter(Qt.Orientation.Vertical)

        # Table group
        table_group = QGroupBox("Danh sách thư mục và kết quả")
        table_layout = QVBoxLayout(table_group)

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels([
            "Thư mục", "Trạng thái", "Tiêu đề mới", "Mô tả mới", "Lỗi"
        ])

        # Set column widths
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)

        self.table.setColumnWidth(0, 200)
        self.table.setColumnWidth(1, 100)
        self.table.setColumnWidth(4, 200)

        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.selectionModel().selectionChanged.connect(self.on_selection_changed)

        table_layout.addWidget(self.table)

        # Table buttons
        table_buttons = QHBoxLayout()

        self.start_btn = QPushButton("🚀 Bắt đầu AI Generate")
        self.start_btn.clicked.connect(self.start_generation)
        table_buttons.addWidget(self.start_btn)

        self.cancel_btn = QPushButton("⏹️ Hủy")
        self.cancel_btn.clicked.connect(self.cancel_generation)
        self.cancel_btn.setEnabled(False)
        table_buttons.addWidget(self.cancel_btn)

        table_buttons.addStretch()

        self.retry_failed_btn = QPushButton("🔄 Thử lại lỗi")
        self.retry_failed_btn.clicked.connect(self.retry_failed)
        self.retry_failed_btn.setEnabled(False)
        table_buttons.addWidget(self.retry_failed_btn)

        self.continue_btn = QPushButton("▶️ Tiếp tục")
        self.continue_btn.clicked.connect(self.continue_generation)
        self.continue_btn.setEnabled(False)
        self.continue_btn.setVisible(False)
        table_buttons.addWidget(self.continue_btn)

        self.apply_btn = QPushButton("✅ Áp dụng kết quả")
        self.apply_btn.clicked.connect(self.apply_results)
        self.apply_btn.setEnabled(False)
        table_buttons.addWidget(self.apply_btn)

        table_layout.addLayout(table_buttons)

        splitter.addWidget(table_group)

        # Detail panel
        detail_group = QGroupBox("Chi tiết")
        detail_layout = QVBoxLayout(detail_group)

        self.detail_text = QTextEdit()
        self.detail_text.setMaximumHeight(150)
        self.detail_text.setReadOnly(True)
        detail_layout.addWidget(self.detail_text)

        splitter.addWidget(detail_group)

        # Set splitter sizes
        splitter.setSizes([500, 150])
        layout.addWidget(splitter)

        # Bottom buttons
        button_layout = QHBoxLayout()

        self.config_btn = QPushButton("⚙️ Cấu hình AI")
        self.config_btn.clicked.connect(self.open_ai_config)
        button_layout.addWidget(self.config_btn)

        button_layout.addStretch()

        self.close_btn = QPushButton("❌ Đóng")
        self.close_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.close_btn)

        layout.addLayout(button_layout)

    def load_config(self):
        """Load cấu hình AI"""
        try:
            config_file = "ai_config.json"
            if os.path.exists(config_file):
                with open(config_file, 'r', encoding='utf-8') as f:
                    self.config = json.load(f)

            # Kiểm tra API keys
            api_keys = self.config.get('api_keys', [])
            if not api_keys and self.config.get('api_key'):  # Backward compatibility
                api_keys = [self.config.get('api_key')]

            if not api_keys:
                QMessageBox.warning(
                    self, "Cảnh báo", 
                    "Chưa cấu hình API key!\nVui lòng vào 'Cấu hình AI' để thiết lập."
                )
                self.start_btn.setEnabled(False)
            else:
                # Update info label với số lượng API keys
                self.info_label.setText(f"Tạo nội dung AI cho {len(self.folders)} thư mục ({len(api_keys)} API keys)")

        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Không thể load cấu hình AI: {str(e)}")
            self.start_btn.setEnabled(False)

    def populate_folders(self):
        """Điền danh sách folders vào table"""
        self.table.setRowCount(len(self.folders))

        for i, folder in enumerate(self.folders):
            folder_name = folder.get('original_title', os.path.basename(folder.get('path', '')))

            # Tên thư mục
            self.table.setItem(i, 0, QTableWidgetItem(folder_name))

            # Trạng thái
            status_item = QTableWidgetItem("⏳ Chờ")
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(i, 1, status_item)

            # Tiêu đề mới
            self.table.setItem(i, 2, QTableWidgetItem(""))

            # Mô tả mới
            self.table.setItem(i, 3, QTableWidgetItem(""))

            # Lỗi
            self.table.setItem(i, 4, QTableWidgetItem(""))

    def start_generation(self):
        """Bắt đầu tạo nội dung AI với đa luồng"""
        if not self.config.get('api_key'):
            QMessageBox.warning(self, "Cảnh báo", "Chưa cấu hình API key!")
            return

        # Reset results
        self.results = {}

        # Reset table
        for i in range(self.table.rowCount()):
            self.table.item(i, 1).setText("⏳ Chờ")
            self.table.item(i, 2).setText("")
            self.table.item(i, 3).setText("")
            self.table.item(i, 4).setText("")

        # UI changes
        self.start_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.apply_btn.setEnabled(False)
        self.retry_failed_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, len(self.folders))
        self.progress_bar.setValue(0)

        # Get thread count
        max_threads = self.thread_spin.value()

        self.status_label.setText(f"Đang khởi tạo {max_threads} luồng xử lý...")

        # Start manager
        self.manager = AIGenerateManager(self.folders, self.config, max_threads)
        self.manager.progress_updated.connect(self.on_progress_updated)
        self.manager.folder_completed.connect(self.on_folder_completed)
        self.manager.folder_failed.connect(self.on_folder_failed)
        self.manager.quota_exceeded.connect(self.on_quota_exceeded)
        self.manager.finished.connect(self.on_generation_finished)
        self.manager.start()

    def cancel_generation(self):
        """Hủy tạo nội dung"""
        if self.manager:
            self.status_label.setText("Đang hủy...")
            self.manager.cancel()
            self.manager.wait(5000)  # Wait 5 seconds

        self.on_generation_finished()

    def on_progress_updated(self, current: int, total: int, message: str):
        """Cập nhật tiến độ"""
        self.progress_bar.setValue(current)
        self.status_label.setText(f"{message} ({current}/{total})")

    def on_folder_completed(self, folder_path: str, result: dict):
        """Xử lý khi hoàn thành một folder"""
        # Tìm row trong table
        for i in range(self.table.rowCount()):
            folder = self.folders[i]
            if folder['path'] == folder_path:
                self.table.item(i, 1).setText("✅ Hoàn thành")
                self.table.item(i, 2).setText(result.get('title', '')[:100])
                self.table.item(i, 3).setText(result.get('description', '')[:100])
                break

        # Lưu kết quả
        self.results[folder_path] = result

        # Auto apply nếu được bật
        if self.auto_apply_check.isChecked():
            self.auto_apply_single_result(folder_path, result)

    def on_folder_failed(self, folder_path: str, error: str):
        """Xử lý khi lỗi một folder"""
        # Tìm row trong table
        for i in range(self.table.rowCount()):
            folder = self.folders[i]
            if folder['path'] == folder_path:
                if error == "API_QUOTA_EXCEEDED":
                    self.table.item(i, 1).setText("⏸️ Dừng")
                    self.table.item(i, 4).setText("Hết lượt API")
                else:
                    self.table.item(i, 1).setText("❌ Lỗi")
                    self.table.item(i, 4).setText(error[:100])
                break

    def on_quota_exceeded(self):
        """Xử lý khi hết quota API"""
        # Dừng generation
        if self.manager:
            self.manager.cancel()

        # Hiển thị thông báo
        reply = QMessageBox.question(
            self, 
            "🚫 Hết lượt API",
            "API key hiện tại đã hết lượt sử dụng!\n\n"
            "Bạn có muốn:\n"
            "• Đổi API key và tiếp tục?\n"
            "• Dừng lại và áp dụng kết quả hiện có?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )

        if reply == QMessageBox.StandardButton.Yes:
            # Mở dialog cấu hình API
            self.open_ai_config_for_continue()
        else:
            # Kết thúc và cho phép áp dụng kết quả
            self.on_generation_finished()

    def open_ai_config_for_continue(self):
        """Mở dialog cấu hình AI để đổi API key và tiếp tục"""
        try:
            from .ai_config_dialog import AIConfigDialog

            dialog = AIConfigDialog(self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                # Load lại config
                self.load_config()

                # Hiển thị nút tiếp tục
                self.continue_btn.setEnabled(True)
                self.continue_btn.setVisible(True)
                self.status_label.setText("Đã cập nhật API key. Click 'Tiếp tục' để chạy tiếp!")

                QMessageBox.information(
                    self, "Thành công", 
                    "Đã cập nhật API key!\nClick 'Tiếp tục' để chạy với các folder chưa hoàn thành."
                )
            else:
                # User hủy, kết thúc generation
                self.on_generation_finished()

        except ImportError:
            QMessageBox.critical(self, "Lỗi", "Không thể import AI Config Dialog!")
            self.on_generation_finished()
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Không thể mở cấu hình AI: {str(e)}")
            self.on_generation_finished()

    def continue_generation(self):
        """Tiếp tục generation với API key mới"""
        if not self.config.get('api_key'):
            QMessageBox.warning(self, "Cảnh báo", "Vẫn chưa có API key hợp lệ!")
            return

        # Tìm các folder chưa hoàn thành
        pending_folders = []
        for i in range(self.table.rowCount()):
            status = self.table.item(i, 1).text()
            if status in ["⏳ Chờ", "⏸️ Dừng", "❌ Lỗi"]:
                pending_folders.append(self.folders[i])
                # Reset trạng thái
                self.table.item(i, 1).setText("⏳ Chờ")
                self.table.item(i, 4).setText("")

        if not pending_folders:
            QMessageBox.information(self, "Thông báo", "Tất cả folder đã được xử lý!")
            return

        # Ẩn nút tiếp tục
        self.continue_btn.setEnabled(False)
        self.continue_btn.setVisible(False)

        # Bắt đầu lại với các folder chưa hoàn thành
        original_folders = self.folders
        self.folders = pending_folders

        # Reset progress
        completed_count = len(original_folders) - len(pending_folders)
        self.progress_bar.setRange(0, len(original_folders))
        self.progress_bar.setValue(completed_count)

        self.start_generation()

        # Khôi phục danh sách folder gốc
        self.folders = original_folders

    def on_generation_finished(self):
        """Hoàn thành tạo nội dung"""
        # UI changes
        self.start_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.progress_bar.setVisible(False)
        self.continue_btn.setEnabled(False)
        self.continue_btn.setVisible(False)

        # Check results
        success_count = len(self.results)
        total_count = len(self.folders)
        failed_count = total_count - success_count

        # Count pending (chưa xử lý)
        pending_count = 0
        for i in range(self.table.rowCount()):
            status = self.table.item(i, 1).text()
            if status in ["⏳ Chờ", "⏸️ Dừng"]:
                pending_count += 1

        if success_count > 0:
            self.apply_btn.setEnabled(True)

        if failed_count > 0 or pending_count > 0:
            self.retry_failed_btn.setEnabled(True)

        status_msg = f"Hoàn thành: {success_count} thành công"
        if failed_count > 0:
            status_msg += f", {failed_count} lỗi"
        if pending_count > 0:
            status_msg += f", {pending_count} chưa xử lý"

        self.status_label.setText(status_msg)

        # Cleanup
        if self.manager:
            self.manager.deleteLater()
            self.manager = None

    def retry_failed(self):
        """Thử lại các folder bị lỗi"""
        failed_folders = []

        for i in range(self.table.rowCount()):
            if self.table.item(i, 1).text() == "❌ Lỗi":
                failed_folders.append(self.folders[i])

        if not failed_folders:
            QMessageBox.information(self, "Thông báo", "Không có folder nào bị lỗi để thử lại!")
            return

        # Temporarily replace folders with failed ones
        original_folders = self.folders
        self.folders = failed_folders
        self.start_generation()
        self.folders = original_folders

    def auto_apply_single_result(self, folder_path: str, result: dict):
        """Tự động áp dụng kết quả cho một folder"""
        try:
            # Tìm folder ID
            folder_id = None
            for folder in self.folders:
                if folder['path'] == folder_path:
                    folder_id = folder.get('id')
                    break

            if folder_id and hasattr(self.parent(), 'db_manager'):
                # Cập nhật database với tiêu đề và mô tả mới
                update_data = {
                    'new_title': result.get('title', ''),
                    'description': result.get('description', '')
                }
                self.parent().db_manager.update_folder_scan(folder_id, update_data)

                # Đổi tên file ảnh theo tiêu đề mới
                self.rename_images_in_folder(folder_path, result.get('title', ''))

        except Exception as e:
            print(f"Lỗi auto apply: {e}")
            import traceback
            traceback.print_exc()

    def rename_images_in_folder(self, folder_path: str, new_title: str):
        """Đổi tên các file ảnh trong folder theo tiêu đề mới"""
        if not new_title or not new_title.strip():
            print(f"WARNING - Empty title for folder: {folder_path}")
            return False

        try:
            if not os.path.exists(folder_path):
                print(f"ERROR - Folder không tồn tại: {folder_path}")
                return False

            new_title = self.sanitize_filename(new_title.strip())  # Làm sạch tiêu đề
            if not new_title:
                print(f"WARNING - Title không hợp lệ sau khi sanitize: {folder_path}")
                return False

            images = [f for f in os.listdir(folder_path) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp'))]

            if not images:
                print(f"WARNING - Không tìm thấy ảnh trong folder: {folder_path}")
                return False

            print(f"INFO - Đang đổi tên {len(images)} ảnh trong folder: {folder_path}")
            print(f"INFO - Tiêu đề mới: {new_title}")

            renamed_count = 0
            for index, image in enumerate(images):
                try:
                    image_path = os.path.join(folder_path, image)
                    name, ext = os.path.splitext(image)

                    # Thêm số thứ tự vào tên file để tránh xung đột
                    if index == 0:
                        new_name = f"{new_title}{ext}"
                    else:
                        new_name = f"{new_title}_{index + 1:02d}{ext}"

                    new_path = os.path.join(folder_path, new_name)

                    # Kiểm tra nếu file đích đã tồn tại
                    counter = 1
                    while os.path.exists(new_path):
                        if index == 0:
                            new_name = f"{new_title}_{counter:02d}{ext}"
                        else:
                            new_name = f"{new_title}_{index + counter:02d}{ext}"
                        new_path = os.path.join(folder_path, new_name)
                        counter += 1

                    # Thực hiện đổi tên
                    os.rename(image_path, new_path)
                    print(f"SUCCESS - Đã đổi tên: {image} -> {new_name}")
                    renamed_count += 1

                except Exception as e:
                    print(f"ERROR - Lỗi đổi tên ảnh {image}: {e}")
                    continue

            print(f"INFO - Hoàn thành đổi tên {renamed_count}/{len(images)} ảnh trong folder: {folder_path}")
            return renamed_count > 0

        except Exception as e:
            print(f"ERROR - Lỗi đổi tên ảnh trong folder {folder_path}: {e}")
            import traceback
            traceback.print_exc()
            return False

    def sanitize_filename(self, filename: str) -> str:
        """Làm sạch filename để đảm bảo tính hợp lệ"""
        if not filename:
            return ""

        # Loại bỏ khoảng trắng đầu cuối
        filename = filename.strip()

        # Thay thế các ký tự không hợp lệ
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')

        # Thay thế nhiều khoảng trắng liên tiếp bằng một dấu gạch dưới
        import re
        filename = re.sub(r'\s+', '_', filename)

        # Loại bỏ dấu gạch dưới liên tiếp
        filename = re.sub(r'_+', '_', filename)

        # Loại bỏ dấu gạch dưới ở đầu và cuối
        filename = filename.strip('_')

        # Giới hạn độ dài filename
        max_length = 200
        if len(filename) > max_length:
            filename = filename[:max_length].rstrip('_')

        return filename

    def apply_results(self):
        """Áp dụng tất cả kết quả"""
        if not self.results:
            QMessageBox.information(self, "Thông báo", "Không có kết quả để áp dụng!")
            return

        try:
            for folder_id, result in self.results.items():
                if result and result.get('status') == 'success':
                    # Cập nhật vào database
                    self.db_manager.update_folder_ai_content(folder_id, {
                        'title': result.get('title', ''),
                        'description': result.get('description', '')
                    })

            QMessageBox.information(self, "Thành công", "Đã áp dụng tất cả kết quả thành công!")
            
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Không thể áp dụng kết quả: {str(e)}")

    def get_results(self):
        """Lấy kết quả AI đã tạo"""
        return self.results

    def on_selection_changed(self):
        """Xử lý khi thay đổi selection trong table"""
        try:
            selected_rows = self.table.selectionModel().selectedRows()
            if selected_rows:
                row = selected_rows[0].row()
                folder_path = self.table.item(row, 0).text()
                
                # Hiển thị thông tin chi tiết nếu có
                if folder_path in self.results:
                    result = self.results[folder_path]
                    if result and 'description' in result:
                        self.details_text.setPlainText(result['description'])
                    else:
                        self.details_text.setPlainText("Chưa có kết quả AI")
                else:
                    self.details_text.setPlainText("Chờ xử lý...")
            else:
                self.details_text.setPlainText("")
                
        except Exception as e:
            # Không cần hiển thị lỗi cho người dùng, chỉ log
            pass

    def open_ai_config(self):
        """Mở dialog cấu hình AI"""
        try:
            from .ai_config_dialog import AIConfigDialog
            
            dialog = AIConfigDialog(self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                # Reload config sau khi user thay đổi
                config = dialog.get_config()
                if config:
                    QMessageBox.information(self, "Thành công", "Đã cập nhật cấu hình AI!")
                    
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Không thể mở cấu hình AI: {str(e)}")