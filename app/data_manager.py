"""
Data Manager Tab - Quản lý và tối ưu dữ liệu folder scans
"""

import os
import logging
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QComboBox, QTextEdit, QDialog, QProgressDialog,
    QGroupBox, QSplitter, QMessageBox, QFileDialog, QInputDialog,
    QTabWidget, QFormLayout, QSpinBox, QCheckBox, QHeaderView, QLineEdit,
    QProgressBar, QAbstractItemView
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QColor

from app.database import DatabaseManager


class DataCleanupWorker(QThread):
    """Worker thread cho cleanup data"""

    progress_update = pyqtSignal(int, str)
    finished = pyqtSignal(bool, str, dict)

    def __init__(self, db_manager: DatabaseManager, cleanup_options: Dict[str, bool]):
        super().__init__()
        self.db_manager = db_manager
        self.cleanup_options = cleanup_options
        self.results = {}

    def run(self):
        """Chạy cleanup"""
        try:
            total_steps = sum(1 for option in self.cleanup_options.values() if option)
            current_step = 0

            # Cleanup orphaned folders
            if self.cleanup_options.get('orphaned_folders', False):
                current_step += 1
                self.progress_update.emit(
                    int((current_step / total_steps) * 100),
                    "Đang dọn dẹp folder scans không còn tồn tại..."
                )
                deleted_count = self.db_manager.cleanup_orphaned_folder_scans()
                self.results['orphaned_deleted'] = deleted_count

            # Find and optionally merge duplicates
            if self.cleanup_options.get('duplicate_folders', False):
                current_step += 1
                self.progress_update.emit(
                    int((current_step / total_steps) * 100),
                    "Đang tìm và xử lý folder scans trùng lặp..."
                )
                duplicates = self.db_manager.get_duplicate_folder_scans()
                self.results['duplicates_found'] = len(duplicates)

                # Auto-merge duplicates
                merged_count = 0
                for dup in duplicates:
                    if len(dup['ids']) > 1:
                        keep_id = min(dup['ids'])  # Giữ lại ID nhỏ nhất
                        merge_ids = [id for id in dup['ids'] if id != keep_id]
                        if self.db_manager.merge_duplicate_folder_scans(keep_id, merge_ids):
                            merged_count += 1

                self.results['duplicates_merged'] = merged_count

            # Fix missing data_names
            if self.cleanup_options.get('missing_data_names', False):
                current_step += 1
                self.progress_update.emit(
                    int((current_step / total_steps) * 100),
                    "Đang sửa data_name trống..."
                )
                folders = self.db_manager.get_all_folder_scans()
                fixed_count = 0

                for folder in folders:
                    if not folder.get('data_name') or folder.get('data_name', '').strip() == '':
                        original_title = folder.get('original_title', '')
                        if original_title and folder.get('id'):
                            success = self.db_manager.update_folder_scan(
                                folder.get('id'), 
                                {'data_name': original_title}
                            )
                            if success:
                                fixed_count += 1

                self.results['data_names_fixed'] = fixed_count

            # Optimize database
            if self.cleanup_options.get('optimize_db', False):
                current_step += 1
                self.progress_update.emit(
                    int((current_step / total_steps) * 100),
                    "Đang tối ưu database..."
                )
                self.db_manager.optimize_folder_scans_table()
                self.results['db_optimized'] = True

            self.progress_update.emit(100, "Hoàn thành cleanup!")
            self.finished.emit(True, "Cleanup hoàn thành thành công!", self.results)

        except Exception as e:
            self.finished.emit(False, f"Lỗi cleanup: {str(e)}", {})


class DataManagerTab(QWidget):
    """Tab quản lý data"""

    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(__name__)

        try:
            from app.database import DatabaseManager
            self.db_manager = DatabaseManager()
            self.cleanup_worker = None

            self.init_ui()
            self.load_summary()

        except Exception as e:
            self.logger.error(f"Error initializing DataManagerTab: {str(e)}")
            layout = QVBoxLayout(self)
            error_label = QLabel(f"Lỗi khởi tạo: {str(e)}")
            layout.addWidget(error_label)

    def init_ui(self):
        """Khởi tạo giao diện"""
        # Xóa layout cũ nếu có
        if self.layout():
            old_layout = self.layout()
            # Xóa tất cả widgets từ layout cũ
            while old_layout.count():
                item = old_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            # Xóa layout cũ
            old_layout.deleteLater()

        # Tạo layout mới
        layout = QVBoxLayout()
        self.setLayout(layout)

        # Thêm các widgets vào layout mới
        # Header
        header_layout = QHBoxLayout()

        title_label = QLabel("📊 Quản lý Data Folder Scans")
        title_label.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        header_layout.addWidget(title_label)

        layout.addLayout(header_layout)

        # Tab widget
        self.tab_widget = QTabWidget()

        # Overview tab
        self.overview_tab = self.create_overview_tab()
        self.tab_widget.addTab(self.overview_tab, "📊 Tổng quan")

        # Cleanup tab
        self.cleanup_tab = self.create_cleanup_tab()
        self.tab_widget.addTab(self.cleanup_tab, "🧹 Dọn dẹp")

        # Export/Import tab
        self.export_tab = self.create_export_tab()
        self.tab_widget.addTab(self.export_tab, "📤 Xuất/Nhập")

        # Upload tab
        self.upload_tab = self.create_upload_tab()
        self.tab_widget.addTab(self.upload_tab, "⬆️ Dữ liệu đăng")

        layout.addWidget(self.tab_widget)

    def create_overview_tab(self) -> QWidget:
        """Tạo tab tổng quan"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Summary stats
        stats_group = QGroupBox("📈 Thống kê tổng quan")
        stats_layout = QFormLayout(stats_group)

        self.total_folders_label = QLabel("0")
        stats_layout.addRow("Tổng số folder:", self.total_folders_label)

        self.total_images_label = QLabel("0")
        stats_layout.addRow("Tổng số ảnh:", self.total_images_label)

        self.pending_folders_label = QLabel("0")
        stats_layout.addRow("Folder chờ xử lý:", self.pending_folders_label)

        self.completed_folders_label = QLabel("0")
        stats_layout.addRow("Folder hoàn thành:", self.completed_folders_label)

        layout.addWidget(stats_group)

        # Detailed data table
        data_group = QGroupBox("📋 Chi tiết dữ liệu quét thư mục")
        data_layout = QVBoxLayout(data_group)

        # Filter controls
        filter_layout = QHBoxLayout()

        # Batch filter
        filter_layout.addWidget(QLabel("Chọn batch:"))
        self.filter_batch_combo = QComboBox()
        self.filter_batch_combo.addItem("Tất cả dữ liệu", None)
        # Disconnect any existing connections to prevent duplicates
        try:
            self.filter_batch_combo.currentTextChanged.disconnect()
        except:
            pass
        self.filter_batch_combo.currentTextChanged.connect(self.load_detailed_data)
        filter_layout.addWidget(self.filter_batch_combo)

        filter_layout.addWidget(QLabel("Lọc theo site:"))
        self.filter_site_combo = QComboBox()
        try:
            self.filter_site_combo.currentTextChanged.disconnect()
        except:
            pass
        self.filter_site_combo.currentTextChanged.connect(self.load_detailed_data)
        filter_layout.addWidget(self.filter_site_combo)

        filter_layout.addWidget(QLabel("Trạng thái:"))
        self.filter_status_combo = QComboBox()
        self.filter_status_combo.addItems(["Tất cả", "pending", "completed", "uploaded"])
        try:
            self.filter_status_combo.currentTextChanged.disconnect()
        except:
            pass
        self.filter_status_combo.currentTextChanged.connect(self.load_detailed_data)
        filter_layout.addWidget(self.filter_status_combo)

        filter_layout.addStretch()

        # Refresh button kept in filter_layout
        refresh_btn = QPushButton("🔄 Làm mới")
        refresh_btn.clicked.connect(self.load_detailed_data)
        filter_layout.addWidget(refresh_btn)

        data_layout.addLayout(filter_layout)

        # Data table với cấu trúc cột tối ưu
        self.data_table = QTableWidget()
        self.data_table.setColumnCount(7)
        self.data_table.setHorizontalHeaderLabels([
            "Tên sản phẩm", "Số ảnh", "Site", "Danh mục", "Trạng thái", "Ngày tạo", "Thao tác"
        ])

        # Thiết lập responsive grid layout cho bảng
        header = self.data_table.horizontalHeader()

        # Thay thế đoạn code cũ với resize modes mới
        resize_modes = [
            QHeaderView.ResizeMode.Interactive,     # Tên sản phẩm - co dãn 
            QHeaderView.ResizeMode.Fixed,           # Số ảnh - cố định
            QHeaderView.ResizeMode.ResizeToContents,# Site - theo nội dung  
            QHeaderView.ResizeMode.ResizeToContents,# Danh mục - theo nội dung
            QHeaderView.ResizeMode.Fixed,           # Trạng thái - cố định 
            QHeaderView.ResizeMode.Fixed,           # Ngày tạo - cố định
            QHeaderView.ResizeMode.Fixed            # Thao tác - cố định
        ]

        # Áp dụng resize mode cho từng cột
        for col, mode in enumerate(resize_modes):
            header.setSectionResizeMode(col, mode)

        # Thiết lập width cố định cho các cột Fixed
        self.data_table.setColumnWidth(1, 80)    # Số ảnh
        self.data_table.setColumnWidth(4, 100)   # Trạng thái
        self.data_table.setColumnWidth(5, 130)   # Ngày tạo
        self.data_table.setColumnWidth(6, 120)   # Thao tác

        # Cấu hình responsive header với khả năng kéo thả
        header.setStretchLastSection(False)
        header.setSectionsMovable(True)           # Cho phép kéo thả di chuyển cột
        header.setSectionsClickable(True)         # Cho phép click để sort
        header.setMinimumSectionSize(40)
        header.setDefaultSectionSize(120)

        # Context menu cho header để reset column sizes
        header.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        header.customContextMenuRequested.connect(self.show_header_context_menu)

        self.data_table.setAlternatingRowColors(True)
        self.data_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.data_table.setSortingEnabled(True)
        self.data_table.itemSelectionChanged.connect(self.on_data_selection_changed)

        data_layout.addWidget(self.data_table)

        # Data action buttons với nhiều tính năng hơn
        data_buttons_layout = QHBoxLayout()

        # Nhóm buttons chính
        main_buttons_group = QHBoxLayout()

        # Tìm kiếm nhanh
        search_layout = QHBoxLayout()
        search_label = QLabel("🔍 Tìm kiếm:")
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Nhập tên sản phẩm, site, hoặc danh mục...")
        try:
            self.search_input.textChanged.disconnect()
        except:
            pass
        self.search_input.textChanged.connect(self.on_search_changed)
        search_layout.addWidget(search_label)
        search_layout.addWidget(self.search_input)
        main_buttons_group.addLayout(search_layout)

        main_buttons_group.addStretch()

        # Buttons hành động
        action_buttons_layout = QHBoxLayout()

        self.edit_data_btn = QPushButton("✏️ Chỉnh sửa")
        self.edit_data_btn.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; font-weight: bold; padding: 8px 16px; border-radius: 4px; }")

        self.view_details_btn = QPushButton("👁️ Xem chi tiết")
        self.view_details_btn.setStyleSheet("QPushButton { background-color: #2196F3; color: white; font-weight: bold; padding: 8px 16px; border-radius: 4px; }")

        self.bulk_edit_btn = QPushButton("📝 Sửa hàng loạt")
        self.bulk_edit_btn.setStyleSheet("QPushButton { background-color: #FF9800; color: white; font-weight: bold; padding: 8px 16px; border-radius: 4px; }")

        self.delete_data_btn = QPushButton("🗑️ Xóa")
        self.delete_data_btn.setStyleSheet("QPushButton { background-color: #f44336; color: white; font-weight: bold; padding: 8px 16px; border-radius: 4px; }")

        self.export_selected_btn = QPushButton("📤 Xuất dữ liệu")
        self.export_selected_btn.setStyleSheet("QPushButton { background-color: #9C27B0; color: white; font-weight: bold; padding: 8px 16px; border-radius: 4px; }")

        action_buttons_layout.addWidget(self.edit_data_btn)
        action_buttons_layout.addWidget(self.view_details_btn)
        action_buttons_layout.addWidget(self.bulk_edit_btn)
        action_buttons_layout.addWidget(self.delete_data_btn)
        action_buttons_layout.addWidget(self.export_selected_btn)

        data_buttons_layout.addLayout(main_buttons_group)
        data_buttons_layout.addLayout(action_buttons_layout)

        # Connect button signals
        self.edit_data_btn.clicked.connect(self.edit_selected_data)
        self.view_details_btn.clicked.connect(self.view_data_details)
        self.bulk_edit_btn.clicked.connect(self.on_bulk_edit_selected)
        self.delete_data_btn.clicked.connect(self.delete_selected_data_batch)
        self.export_selected_btn.clicked.connect(self.on_export_selected_data)

        # Disable buttons initially
        self.edit_data_btn.setEnabled(False)
        self.view_details_btn.setEnabled(False)
        self.bulk_edit_btn.setEnabled(False)
        self.delete_data_btn.setEnabled(False)
        self.export_selected_btn.setEnabled(False)
        self.view_details_btn.setEnabled(False)
        data_buttons_layout.addWidget(self.view_details_btn)

        data_buttons_layout.addSpacing(20)

        self.load_saved_scans_btn = QPushButton("📦 Load từ Saved Scans")
        self.load_saved_scans_btn.clicked.connect(self.show_saved_scans_dialog)
        self.load_saved_scans_btn.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                font-weight: bold;
                padding: 8px 16px;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #218838;
            }
        """)
        data_buttons_layout.addWidget(self.load_saved_scans_btn)

        data_buttons_layout.addStretch()

        data_layout.addLayout(data_buttons_layout)

        layout.addWidget(data_group)

        return widget

    def create_cleanup_tab(self) -> QWidget:
        """Tạo tab dọn dẹp"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Cleanup options
        options_group = QGroupBox("🧹 Tùy chọn dọn dẹp")
        options_layout = QVBoxLayout(options_group)

        self.orphaned_check = QCheckBox("Xóa folder scans không còn tồn tại trên disk")
        self.orphaned_check.setChecked(True)
        options_layout.addWidget(self.orphaned_check)

        self.duplicate_check = QCheckBox("Gộp folder scans trùng lặp")
        self.duplicate_check.setChecked(True)
        options_layout.addWidget(self.duplicate_check)

        self.missing_names_check = QCheckBox("Sửa data_name trống")
        self.missing_names_check.setChecked(True)
        options_layout.addWidget(self.missing_names_check)

        self.optimize_check = QCheckBox("Tối ưu database")
        self.optimize_check.setChecked(False)
        options_layout.addWidget(self.optimize_check)

        layout.addWidget(options_group)

        # Cleanup actions
        actions_group = QGroupBox("⚡ Thao tác")
        actions_layout = QHBoxLayout(actions_group)

        self.cleanup_btn = QPushButton("🧹 Bắt đầu dọn dẹp")
        self.cleanup_btn.clicked.connect(self.start_cleanup)
        actions_layout.addWidget(self.cleanup_btn)

        self.preview_btn = QPushButton("👀 Xem trước")
        self.preview_btn.clicked.connect(self.preview_cleanup)
        actions_layout.addWidget(self.preview_btn)

        actions_layout.addStretch()

        layout.addWidget(actions_group)

        # Results
        self.cleanup_results = QTextEdit()
        self.cleanup_results.setMaximumHeight(200)
        self.cleanup_results.setPlainText("Chưa thực hiện cleanup nào...")
        layout.addWidget(self.cleanup_results)

        layout.addStretch()
        return widget

    def create_export_tab(self) -> QWidget:
        """Tạo tab xuất/nhập"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Export section
        export_group = QGroupBox("📤 Xuất dữ liệu")
        export_layout = QVBoxLayout(export_group)

        export_buttons = QHBoxLayout()

        self.export_json_btn = QPushButton("📄 Xuất JSON")
        self.export_json_btn.clicked.connect(self.export_to_json)
        export_buttons.addWidget(self.export_json_btn)

        self.export_csv_btn = QPushButton("📊 Xuất CSV")
        self.export_csv_btn.clicked.connect(self.export_to_csv)
        export_buttons.addWidget(self.export_csv_btn)

        export_buttons.addStretch()

        export_layout.addLayout(export_buttons)
        layout.addWidget(export_group)

        # Backup section
        backup_group = QGroupBox("💾 Sao lưu")
        backup_layout = QVBoxLayout(backup_group)

        backup_buttons = QHBoxLayout()

        self.backup_db_btn = QPushButton("💾 Sao lưu Database")
        self.backup_db_btn.clicked.connect(self.backup_database)
        backup_buttons.addWidget(self.backup_db_btn)

        self.restore_db_btn = QPushButton("📥 Khôi phục Database")
        self.restore_db_btn.clicked.connect(self.restore_database)
        backup_buttons.addWidget(self.restore_db_btn)

        backup_buttons.addStretch()

        backup_layout.addLayout(backup_buttons)
        layout.addWidget(backup_group)

        layout.addStretch()
        return widget

    def create_upload_tab(self) -> QWidget:
        """Tạo tab upload scheduler"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        # Control panel
        control_group = QGroupBox("🎛️ Điều khiển upload")
        control_group.setStyleSheet("QGroupBox { font-weight: bold; padding-top: 15px; }")
        control_layout = QHBoxLayout(control_group)

        # Batch selector
        control_layout.addWidget(QLabel("Chọn batch:"))
        self.upload_batch_combo = QComboBox()
        self.upload_batch_combo.setMinimumWidth(200)
        self.upload_batch_combo.addItem("Chọn từ bảng chi tiết", None)
        control_layout.addWidget(self.upload_batch_combo)

        # Load batch button
        self.load_batch_btn = QPushButton("📦 Load batch")
        self.load_batch_btn.clicked.connect(self.load_batch_upload_data)
        self.load_batch_btn.setEnabled(False)
        control_layout.addWidget(self.load_batch_btn)

        # Refresh upload data button
        self.refresh_upload_btn = QPushButton("🔄 Làm mới")
        self.refresh_upload_btn.clicked.connect(self.refresh_upload_data)
        self.refresh_upload_btn.setStyleSheet("""
            QPushButton {
                background-color: #17a2b8;
                color: white;
                font-weight: bold;
                padding: 8px 16px;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #138496;
            }
        """)
        control_layout.addWidget(self.refresh_upload_btn)



        # Config button
        self.config_upload_btn = QPushButton("⚙️ Thiết lập cấu hình đăng")
        self.config_upload_btn.clicked.connect(self.show_upload_config)
        self.config_upload_btn.setEnabled(False)
        self.config_upload_btn.setToolTip("Mở dialog cấu hình chi tiết cho việc đăng sản phẩm")
        control_layout.addWidget(self.config_upload_btn)

        # Di chuyển các nút điều khiển upload vào đây
        self.pause_upload_btn = QPushButton("⏸️ Tạm dừng")
        self.pause_upload_btn.clicked.connect(self.pause_upload)
        self.pause_upload_btn.setEnabled(False)
        self.pause_upload_btn.setStyleSheet("""
            QPushButton {
                background-color: #ffc107;
                color: black;
                font-weight: bold;
                padding: 8px 16px;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #e0a800;
            }
            QPushButton:disabled {
                background-color: #6c757d;
                color: #ffffff;
            }
        """)
        control_layout.addWidget(self.pause_upload_btn)

        self.resume_upload_btn = QPushButton("▶️ Tiếp tục")
        self.resume_upload_btn.clicked.connect(self.resume_upload)
        self.resume_upload_btn.setEnabled(False)
        self.resume_upload_btn.setVisible(False)
        self.resume_upload_btn.setStyleSheet("""
            QPushButton {
                background-color: #17a2b8;
                color: white;
                font-weight: bold;
                padding: 8px 16px;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #138496;
            }
            QPushButton:disabled {
                background-color: #6c757d;
                color: #ffffff;
            }
        """)
        control_layout.addWidget(self.resume_upload_btn)

        self.stop_upload_btn = QPushButton("⏹️ Dừng")
        self.stop_upload_btn.clicked.connect(self.stop_upload)
        self.stop_upload_btn.setEnabled(False)
        self.stop_upload_btn.setStyleSheet("""
            QPushButton {
                background-color: #dc3545;
                color: white;
                font-weight: bold;
                padding: 8px 16px;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #c82333;
            }
            QPushButton:disabled {
                background-color: #6c757d;
                color: #ffffff;
            }
        """)
        control_layout.addWidget(self.stop_upload_btn)

        control_layout.addStretch()

        # Delay setting
        control_layout.addWidget(QLabel("Thời gian chờ:"))
        self.upload_delay_spin = QSpinBox()
        self.upload_delay_spin.setRange(1, 60)
        self.upload_delay_spin.setValue(3)
        self.upload_delay_spin.setSuffix(" giây")
        control_layout.addWidget(self.upload_delay_spin)

        layout.addWidget(control_group)

        # Status and controls
        status_group = QGroupBox("📊 Trạng thái upload")
        status_group.setStyleSheet("QGroupBox { font-weight: bold; padding-top: 15px; }")
        status_layout = QVBoxLayout(status_group)

        # Progress info
        progress_info_layout = QHBoxLayout()

        self.upload_status_label = QLabel("Sẵn sàng upload")
        self.upload_status_label.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        progress_info_layout.addWidget(self.upload_status_label)

        progress_info_layout.addStretch()

        self.upload_progress_label = QLabel("0/0")
        self.upload_progress_label.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        progress_info_layout.addWidget(self.upload_progress_label)

        status_layout.addLayout(progress_info_layout)

        # Thêm label hiển thị thống kê chi tiết
        self.upload_stats_label = QLabel("Chọn batch để xem thống kê")
        self.upload_stats_label.setFont(QFont("Arial", 9))
        self.upload_stats_label.setStyleSheet("color: #666; padding: 5px;")
        self.upload_stats_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status_layout.addWidget(self.upload_stats_label)

        # Progress bar
        self.upload_progress_bar = QProgressBar()
        self.upload_progress_bar.setVisible(False)
        status_layout.addWidget(self.upload_progress_bar)

        # Control buttons
        control_buttons_layout = QHBoxLayout()

        self.start_upload_btn = QPushButton("🚀 Bắt đầu đăng hàng loạt")
        self.start_upload_btn.clicked.connect(self.start_upload_scheduler)
        self.start_upload_btn.setEnabled(False)
        self.start_upload_btn.setToolTip("Bắt đầu upload với cấu hình đã thiết lập")
        self.start_upload_btn.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                font-weight: bold;
                padding: 8px 16px;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #218838;
            }
            QPushButton:disabled {
                background-color: #6c757d;
                color: #ffffff;
            }
        """)
        control_buttons_layout.addWidget(self.start_upload_btn)  # Thêm dấu đóng ngoặc

        self.clear_queue_btn = QPushButton("🗑️ Xóa hàng đợi")
        self.clear_queue_btn.clicked.connect(self.clear_upload_queue)
        self.clear_queue_btn.setEnabled(False)
        control_buttons_layout.addWidget(self.clear_queue_btn)

        self.remove_selected_btn = QPushButton("➖ Xóa đã chọn")
        self.remove_selected_btn.clicked.connect(self.remove_selected_from_queue)
        self.remove_selected_btn.setEnabled(False)
        control_buttons_layout.addWidget(self.remove_selected_btn)

        # Refresh queue button
        self.refresh_queue_btn = QPushButton("🔄 Làm mới hàng đợi")
        self.refresh_queue_btn.clicked.connect(self.refresh_upload_queue)
        self.refresh_queue_btn.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                color: white;
                font-weight: bold;
                padding: 8px 16px;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #5a6268;
            }
        """)
        control_buttons_layout.addWidget(self.refresh_queue_btn)

        control_buttons_layout.addStretch()

        status_layout.addLayout(control_buttons_layout)

        layout.addWidget(status_group)

        # Upload queue table
        queue_group = QGroupBox("📋 Hàng đợi upload")
        queue_group.setStyleSheet("QGroupBox { font-weight: bold; padding-top: 15px; }")
        queue_layout = QVBoxLayout(queue_group)

        # Table
        self.upload_queue_table = QTableWidget()
        self.upload_queue_table.setColumnCount(9)
        self.upload_queue_table.setHorizontalHeaderLabels([
            "Tên sản phẩm", "Đường dẫn", "Số ảnh", "Danh mục", "Mô tả", "Site đăng", "Trạng thái", "Log", "Thời gian"
        ])

        # Table properties
        self.upload_queue_table.setAlternatingRowColors(True)
        self.upload_queue_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)

        # Header settings
        header = self.upload_queue_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)  # Tên sản phẩm
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)  # Đường dẫn
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)  # Số ảnh
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)  # Danh mục
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)  # Mô tả
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)  # Site đăng
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)  # Trạng thái
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.Stretch)  # Log
        header.setSectionResizeMode(8, QHeaderView.ResizeMode.ResizeToContents)  # Thời gian

        self.upload_queue_table.setColumnWidth(2, 80)  # Số ảnh

        # Connect selection changed signal
        self.upload_queue_table.itemSelectionChanged.connect(self.on_queue_selection_changed)

        queue_layout.addWidget(self.upload_queue_table)

        layout.addWidget(queue_group)

        # Initialize upload data
        self.upload_folders = []
        self.upload_config = {
            'configured': False,
            'default_site_id': None,
            'default_category_id': None,
            'default_status': 'draft',
            'image_gallery': True,
            'auto_description': True
        }

        return widget

    def load_summary(self):
        """Load thống kê tổng quan với sync database"""
        try:
            summary = self.db_manager.get_folder_scans_summary()

            # Update summary labels
            self.total_folders_label.setText(str(summary.get('total_folders', 0)))
            self.total_images_label.setText(str(summary.get('total_images', 0)))

            status_stats = summary.get('by_status', {})
            pending_count = status_stats.get('pending', 0)
            completed_count = status_stats.get('completed', 0)
            uploaded_count = status_stats.get('uploaded', 0)  # Thêm uploaded count
            
            # Hiển thị thống kê chi tiết hơn
            self.pending_folders_label.setText(f"{pending_count} (chờ xử lý)")
            
            # Tổng hợp completed + uploaded
            total_processed = completed_count + uploaded_count
            self.completed_folders_label.setText(f"{total_processed} (đã xử lý)")
            
            self.logger.info(f"📊 Summary refreshed - Pending: {pending_count}, Completed: {completed_count}, Uploaded: {uploaded_count}")

            # Load batch filter
            self.load_batch_filter()

            # Load upload batch selector
            self.load_upload_batch_selector()

            # Load sites for filter
            self.load_sites_filter()

            # Load detailed data với force refresh
            self.load_detailed_data()
            
            # Log để debug data consistency
            self.log_data_consistency_check()

        except Exception as e:
            self.logger.error(f"Error loading summary: {str(e)}")
            QMessageBox.critical(self, "Lỗi", f"Không thể load thống kê: {str(e)}")

    def log_data_consistency_check(self):
        """Log để kiểm tra tính nhất quán của dữ liệu"""
        try:
            # Kiểm tra consistency giữa folder_scans và saved_scans
            folder_scans = self.db_manager.get_all_folder_scans()
            saved_scans = self.db_manager.get_all_saved_scans()
            
            # Đếm status từ folder_scans table
            folder_status_count = {}
            for folder in folder_scans:
                status = folder.get('status', 'pending')
                folder_status_count[status] = folder_status_count.get(status, 0) + 1
            
            # Đếm status từ saved_scans data
            saved_status_count = {}
            for saved_scan in saved_scans:
                try:
                    import json
                    data_json = saved_scan.get('data', '[]')
                    if isinstance(data_json, str):
                        folders_data = json.loads(data_json)
                    else:
                        folders_data = data_json
                    
                    for folder in folders_data:
                        status = folder.get('status', 'pending')
                        saved_status_count[status] = saved_status_count.get(status, 0) + 1
                except:
                    continue
            
            self.logger.info(f"🔍 Consistency Check - Folder Scans: {folder_status_count}")
            self.logger.info(f"🔍 Consistency Check - Saved Scans: {saved_status_count}")
            
            # Cảnh báo nếu có sự khác biệt lớn
            folder_uploaded = folder_status_count.get('uploaded', 0)
            saved_uploaded = saved_status_count.get('uploaded', 0)
            if abs(folder_uploaded - saved_uploaded) > 0:
                self.logger.warning(f"⚠️ Data inconsistency detected - Folder uploaded: {folder_uploaded}, Saved uploaded: {saved_uploaded}")
                
        except Exception as e:
            self.logger.error(f"Error in consistency check: {str(e)}")

    def load_batch_filter(self):
        """Load saved scans cho batch filter dropdown"""
        try:
            self.filter_batch_combo.clear()
            self.filter_batch_combo.addItem("Tất cả dữ liệu", None)

            # Load saved scans
            saved_scans = self.db_manager.get_all_saved_scans()
            for scan in saved_scans:
                scan_name = scan.get('name', f"Scan {scan.get('id', '')}")
                folder_count = scan.get('folder_count', 0)
                display_name = f"📦 {scan_name} ({folder_count} folders)"
                self.filter_batch_combo.addItem(display_name, scan.get('id'))

        except Exception as e:
            self.logger.error(f"Error loading batch filter: {str(e)}")

    def load_upload_batch_selector(self):
        """Load saved scans cho upload batch selector"""
        try:
            if not hasattr(self, 'upload_batch_combo'):
                return

            self.upload_batch_combo.clear()
            self.upload_batch_combo.addItem("Chọn từ bảng chi tiết", None)

            # Load saved scans
            saved_scans = self.db_manager.get_all_saved_scans()
            for scan in saved_scans:
                scan_name = scan.get('name', f"Scan {scan.get('id', '')}")
                folder_count = scan.get('folder_count', 0)
                display_name = f"📦 {scan_name} ({folder_count} folders)"
                self.upload_batch_combo.addItem(display_name, scan.get('id'))

            # Connect signal để enable/disable load batch button
            self.upload_batch_combo.currentTextChanged.connect(self.on_upload_batch_changed)

        except Exception as e:
            self.logger.error(f"Error loading upload batch selector: {str(e)}")

    def on_upload_batch_changed(self):
        """Xử lý khi thay đổi batch selector"""
        try:
            batch_id = self.upload_batch_combo.currentData()
            self.load_batch_btn.setEnabled(batch_id is not None)

            # Hiển thị thống kê nhanh cho batch được chọn
            if batch_id and hasattr(self, 'upload_stats_label'):
                try:
                    saved_scans = self.db_manager.get_all_saved_scans()
                    selected_scan = None
                    for scan in saved_scans:
                        if scan.get('id') == batch_id:
                            selected_scan = scan
                            break

                    if selected_scan:
                        import json
                        data_json = selected_scan.get('data', '[]')
                        if isinstance(data_json, str):
                            folders_data = json.loads(data_json)
                        else:
                            folders_data = data_json

                        # Đếm theo trạng thái
                        pending_count = 0
                        completed_count = 0
                        uploaded_count = 0
                        error_count = 0

                        for folder in folders_data:
                            status = folder.get('status', 'pending')
                            if status == 'completed':
                                completed_count += 1
                            elif status == 'uploaded':
                                uploaded_count += 1
                            elif status == 'error':
                                error_count += 1
                            else:  # pending và các status khác
                                pending_count += 1

                        # Hiển thị thống kê rõ ràng
                        total_count = len(folders_data)
                        stats_text = f"📊 Tổng: {total_count} | ⏳ Chờ: {pending_count} | ✅ Hoàn thành: {completed_count}"
                        if uploaded_count > 0:
                            stats_text += f" | 🚀 Đã đăng: {uploaded_count}"
                        if error_count > 0:
                            stats_text += f" | ❌ Lỗi: {error_count}"

                        self.upload_stats_label.setText(stats_text)
                    else:
                        self.upload_stats_label.setText("Không tìm thấy batch")
                except Exception as e:
                    self.upload_stats_label.setText("Lỗi load thống kê")
                    self.logger.error(f"Error loading batch stats: {str(e)}")
            else:
                if hasattr(self, 'upload_stats_label'):
                    self.upload_stats_label.setText("Chọn batch để xem thống kê")

        except Exception as e:
            self.logger.error(f"Error handling batch change: {str(e)}")

    def is_folder_already_processed(self, folder_data):
        """Kiểm tra xem folder đã được xử lý (upload) thành công chưa - Updated logic"""
        try:
            folder_id = folder_data.get('id')
            
            # Luôn kiểm tra database trước (source of truth)
            if folder_id and self.db_manager:
                try:
                    db_folder = self.db_manager.get_folder_scan_by_id(folder_id)
                    if db_folder:
                        # Sync folder_data với database data
                        db_status = db_folder.get('status', 'pending')
                        db_upload_success = db_folder.get('upload_success', 0)
                        db_wc_product_id = db_folder.get('wc_product_id')
                        
                        # Cập nhật folder_data với thông tin mới nhất từ database
                        folder_data['status'] = db_status
                        folder_data['upload_success'] = db_upload_success
                        if db_wc_product_id:
                            folder_data['wc_product_id'] = db_wc_product_id
                        if db_folder.get('uploaded_at'):
                            folder_data['uploaded_at'] = db_folder.get('uploaded_at')
                        if db_folder.get('product_url'):
                            folder_data['product_url'] = db_folder.get('product_url')
                        
                        # Kiểm tra các điều kiện processed dựa trên database
                        if db_upload_success == 1:
                            self.logger.debug(f"Folder {folder_id} đã processed: upload_success = 1")
                            return True
                            
                        if db_wc_product_id and db_wc_product_id > 0:
                            self.logger.debug(f"Folder {folder_id} đã processed: có wc_product_id = {db_wc_product_id}")
                            return True
                            
                        if db_status in ['uploaded']:  # Chỉ 'uploaded' mới được coi là processed
                            self.logger.debug(f"Folder {folder_id} đã processed: status = {db_status}")
                            return True
                            
                        # Log status cho debug
                        self.logger.debug(f"Folder {folder_id} chưa processed: status={db_status}, upload_success={db_upload_success}, wc_product_id={db_wc_product_id}")
                        return False
                        
                except Exception as e:
                    self.logger.warning(f"Lỗi kiểm tra database cho folder {folder_id}: {str(e)}")
                    # Fallback to folder_data check nếu database lỗi
                    pass

            # Fallback: kiểm tra từ folder_data nếu không có database
            # Kiểm tra upload_success flag
            if folder_data.get('upload_success') == 1:
                self.logger.debug(f"Folder {folder_id} đã processed (fallback): upload_success = 1")
                return True

            # Kiểm tra có wc_product_id không
            wc_product_id = folder_data.get('wc_product_id')
            if wc_product_id and wc_product_id > 0:
                self.logger.debug(f"Folder {folder_id} đã processed (fallback): có wc_product_id = {wc_product_id}")
                return True

            # Kiểm tra status - chỉ 'uploaded' mới được coi là processed
            status = folder_data.get('status', 'pending')
            if status == 'uploaded':
                self.logger.debug(f"Folder {folder_id} đã processed (fallback): status = {status}")
                return True

            self.logger.debug(f"Folder {folder_id} chưa processed (fallback): status={status}, upload_success={folder_data.get('upload_success')}, wc_product_id={wc_product_id}")
            return False

        except Exception as e:
            self.logger.error(f"Lỗi kiểm tra folder processed: {str(e)}")
            return False

    def load_batch_upload_data(self):
        """Load toàn bộ dữ liệu từ batch được chọn vào hàng đợi upload (chỉ load trạng thái pending)"""
        try:
            batch_id = self.upload_batch_combo.currentData()
            if not batch_id:
                QMessageBox.warning(self, "Cảnh báo", "Vui lòng chọn một batch!")
                return

            # Tìm saved scan
            saved_scans = self.db_manager.get_all_saved_scans()
            selected_scan = None
            for scan in saved_scans:
                if scan.get('id') == batch_id:
                    selected_scan = scan
                    break

            if not selected_scan:
                QMessageBox.warning(self, "Lỗi", "Không tìm thấy batch được chọn!")
                return

            # Track batch ID được load
            self.current_loaded_batch_id = selected_scan.get('id')

            # Load folders từ saved scan
            import json

            data_json = selected_scan.get('data', '[]')
            if isinstance(data_json, str):
                folders_data = json.loads(data_json)
            else:
                folders_data = data_json

            # Clear existing upload queue
            self.upload_folders = []
            self.upload_queue_table.setRowCount(0)

            # Phân loại theo trạng thái
            pending_count = 0
            completed_count = 0
            uploaded_count = 0
            error_count = 0
            loaded_count = 0

            for folder_data in folders_data:
                status = folder_data.get('status', 'pending')

                # Đếm theo trạng thái
                if status == 'completed':
                    completed_count += 1
                elif status == 'uploaded':
                    uploaded_count += 1
                elif status == 'error':
                    error_count += 1
                else:
                    pending_count += 1

                # Chỉ load những folder có trạng thái 'pending' (chờ xử lý) và chưa được xử lý
                if status == 'pending' and not self.is_folder_already_processed(folder_data) and self.validate_folder_for_upload(folder_data):
                    self.upload_folders.append(folder_data)
                    self.add_folder_to_upload_queue(folder_data)
                    loaded_count += 1

            # Tạo thông báo chi tiết
            total_count = len(folders_data)
            actual_pending = len([f for f in folders_data if f.get('status', 'pending') == 'pending' and not self.is_folder_already_processed(f)])

            status_detail = f"📊 Thống kê batch '{selected_scan.get('name', '')}':\n"
            status_detail += f"• Tổng số: {total_count} sản phẩm\n"
            status_detail += f"• ⏳ Chờ xử lý thực tế: {actual_pending}\n"
            status_detail += f"• ⏳ Chờ xử lý (theo saved scan): {pending_count}\n"
            status_detail += f"• ✅ Hoàn thành: {completed_count}\n"
            if uploaded_count > 0:
                status_detail += f"• 🚀 Đã đăng: {uploaded_count}\n"
            if error_count > 0:
                status_detail += f"• ❌ Lỗi: {error_count}\n"
            status_detail += f"\n📥 Đã load {loaded_count}/{actual_pending} sản phẩm thực sự chờ xử lý vào hàng đợi"

            # Enable buttons based on loaded folders
            if loaded_count > 0:
                self.config_upload_btn.setEnabled(True)
                self.start_upload_btn.setEnabled(True)
                self.upload_status_label.setText(f"✅ Đã load {loaded_count} sản phẩm chờ xử lý từ batch vào hàng đợi")

                QMessageBox.information(
                    self, "Thành công", 
                    status_detail + "\n\n"
                    f"✅ Đã load {loaded_count} sản phẩm vào hàng đợi upload\n\n"
                    f"• Nhấn 'Thiết lập cấu hình đăng' để cấu hình chi tiết\n"
                    f"• Nhấn 'Bắt đầu đăng hàng loạt' để upload với cấu hình mặc định"
                )
            else:
                self.config_upload_btn.setEnabled(False)
                self.start_upload_btn.setEnabled(False)
                if pending_count == 0:
                    self.upload_status_label.setText(f"✅ Batch đã hoàn thành toàn bộ ({completed_count + uploaded_count}/{total_count})")

                    QMessageBox.information(
                        self, "Thông báo", 
                        status_detail + "\n\n"
                        "🎉 Batch này đã hoàn thành toàn bộ!\n"
                        "Tất cả sản phẩm đều đã được xử lý hoặc đăng thành công."
                    )
                else:
                    self.upload_status_label.setText(f"⚠️ Không load được sản phẩm nào từ {pending_count} sản phẩm chờ xử lý")

                    QMessageBox.warning(
                        self, "Cảnh báo", 
                        status_detail + "\n\n"
                        f"⚠️ Có {pending_count} sản phẩm chờ xử lý nhưng không thể load vào hàng đợi.\n"
                        "Có thể do:\n"
                        "• Đường dẫn folder không tồn tại\n"
                        "• Folder không có ảnh hợp lệ\n"
                        "• Thiếu tên sản phẩm\n\n"
                        "Vui lòng kiểm tra dữ liệu trong tab 'Tổng quan'."
                    )

        except Exception as e:
            self.logger.error(f"Lỗi load batch upload data: {str(e)}")
            QMessageBox.critical(self, "Lỗi", f"Không thể load dữ liệu batch: {str(e)}")

    def load_sites_filter(self):
        """Load sites cho filter dropdown"""
        try:
            self.filter_site_combo.clear()
            self.filter_site_combo.addItem("Tất cả sites", None)

            sites = self.db_manager.get_all_sites()
            for site in sites:
                self.filter_site_combo.addItem(site.name, site.id)

        except Exception as e:
            self.logger.error(f"Error loading sites filter: {str(e)}")

    def load_detailed_data(self):
        """Load dữ liệu chi tiết vào bảng - bao gồm cả saved scans và folder scans"""
        try:
            # Debouncing: tránh gọi liên tiếp trong thời gian ngắn
            if hasattr(self, '_load_timer'):
                self._load_timer.stop()

            self._load_timer = QTimer()
            self._load_timer.setSingleShot(True)
            self._load_timer.timeout.connect(self._do_load_detailed_data)
            self._load_timer.start(100)  # Delay 100ms

        except Exception as e:
            self.logger.error(f"Error in load_detailed_data: {str(e)}")

    def _do_load_detailed_data(self):
        """Thực hiện load dữ liệu chi tiết (debounced version)"""
        try:
            if not self.db_manager:
                self.logger.warning("Database manager not available")
                return

            # Lấy filter values
            batch_id = self.filter_batch_combo.currentData()
            site_id = self.filter_site_combo.currentData()
            status_filter = self.filter_status_combo.currentText()

            all_data = []

            if batch_id is None:
                # Hiển thị tất cả dữ liệu (saved scans + folder scans)
                # Lấy dữ liệu saved scans
                saved_scans = self.db_manager.get_all_saved_scans()

                # Lấy dữ liệu folder scans
                folder_scans = self.db_manager.get_all_folder_scans()

                self.logger.debug(f"Found {len(saved_scans)} saved scans and {len(folder_scans)} folder scans")

                # Thêm saved scans vào đầu danh sách
                for scan in saved_scans:
                    all_data.append({
                        'type': 'saved_scan',
                        'id': scan.get('id'),
                        'name': scan.get('name', ''),
                        'description': scan.get('description', ''),
                        'folder_count': scan.get('folder_count', 0),
                        'created_at': scan.get('created_at', ''),
                        'data': scan  # Lưu toàn bộ data
                    })

                # Thêm individual folder scans
                for folder in folder_scans:
                    # Apply filters cho folder scans
                    if site_id and folder.get('site_id') != site_id:
                        continue
                    if status_filter != "Tất cả" and folder.get('status') != status_filter:
                        continue

                    all_data.append({
                        'type': 'folder_scan',
                        'id': folder.get('id'),
                        'name': folder.get('data_name') or folder.get('original_title', ''),
                        'description': f"Folder với {folder.get('image_count', 0)} ảnh" + (f" - {folder.get('site_name')}" if folder.get('site_name') else ""),
                        'folder_count': folder.get('image_count', 0),
                        'created_at': folder.get('created_at', ''),
                        'data': folder  # Lưu toàn bộ data
                    })
            else:
                # Chỉ hiển thị dữ liệu của batch được chọn
                import json
                saved_scan = None
                saved_scans = self.db_manager.get_all_saved_scans()
                for scan in saved_scans:
                    if scan.get('id') == batch_id:
                        saved_scan = scan
                        break

                if saved_scan:
                    # Parse folder data từ saved scan
                    try:
                        data_json = saved_scan.get('data', '[]')
                        if isinstance(data_json, str):
                            folders_data = json.loads(data_json)
                        else:
                            folders_data = data_json

                        # Thêm từng folder từ batch vào all_data
                        for folder in folders_data:
                            # Apply filters cho folder scans
                            if site_id and folder.get('site_id') != site_id:
                                continue
                            if status_filter != "Tất cả" and folder.get('status') != status_filter:
                                continue

                            all_data.append({
                                'type': 'batch_folder',
                                'id': folder.get('id'),
                                'name': folder.get('data_name') or folder.get('original_title', ''),
                                'description': f"📦 Batch: {saved_scan.get('name', '')} - {folder.get('image_count', 0)} ảnh" + (f" - {folder.get('site_name', '')}" if folder.get('site_name') else ""),
                                'folder_count': folder.get('image_count', 0),
                                'created_at': folder.get('created_at', ''),
                                'data': folder  # Lưu toàn bộ data
                            })

                        self.logger.info(f"Loaded {len(all_data)} folders from batch: {saved_scan.get('name', '')}")
                    except Exception as e:
                        self.logger.error(f"Error parsing batch data: {str(e)}")
                else:
                    self.logger.warning(f"Batch with ID {batch_id} not found")

            # Populate table
            self.data_table.setRowCount(len(all_data))

            for row, item in enumerate(all_data):
                folder_data = item['data']

                # Tên sản phẩm (cột 0) - với icon để phân biệt loại
                name_text = item['name']
                if item['type'] == 'saved_scan':
                    name_text = f"📦 {name_text}"  # Icon cho saved scan
                elif item['type'] == 'batch_folder':
                    name_text = f"📦📁 {name_text}"  # Icon cho folder từ batch
                else:
                    name_text = f"📁 {name_text}"  # Icon cho folder scan

                name_item = QTableWidgetItem(name_text)
                name_item.setData(Qt.ItemDataRole.UserRole, item)  # Lưu toàn bộ data
                self.data_table.setItem(row, 0, name_item)

                # Số ảnh (cột 1)
                image_count = folder_data.get('image_count', 0) if item['type'] == 'folder_scan' else item.get('folder_count', 0)
                self.data_table.setItem(row, 1, QTableWidgetItem(str(image_count)))

                # Site (cột 2)
                site_name = ""
                if item['type'] == 'folder_scan' or item['type'] == 'batch_folder':
                    site_id = folder_data.get('site_id')
                    if site_id and self.db_manager:
                        try:
                            sites = self.db_manager.get_all_sites()
                            for site in sites:
                                if site.id == site_id:
                                    site_name = site.name
                                    break
                        except:
                            pass
                    if not site_name:
                        site_name = folder_data.get('site_name', 'Chưa chọn')
                    if item['type'] == 'batch_folder':
                        site_name = f"📦 {site_name}"  # Thêm icon batch
                elif item['type'] == 'saved_scan':
                    site_name = "Tổng hợp"
                self.data_table.setItem(row, 2, QTableWidgetItem(site_name))

                # Danh mục (cột 3)
                category_name = ""
                if item['type'] == 'folder_scan' or item['type'] == 'batch_folder':
                    category_id = folder_data.get('category_id')
                    if category_id and self.db_manager:
                        try:
                            category = self.db_manager.get_category_by_id(category_id)
                            if category:
                                category_name = category.get('name', 'Chưa có')
                        except:
                            pass
                    if not category_name:
                        category_name = folder_data.get('category_name', 'Chưa có')
                    if item['type'] == 'batch_folder':
                        category_name = f"📦 {category_name}"  # Thêm icon batch
                elif item['type'] == 'saved_scan':
                    category_name = "Tổng hợp"
                self.data_table.setItem(row, 3, QTableWidgetItem(category_name))

                # Trạng thái (cột 4)
                status_text = ""
                if item['type'] == 'folder_scan' or item['type'] == 'batch_folder':
                    status = folder_data.get('status', 'pending')
                    status_icons = {
                        'pending': '⏳ Chờ xử lý',
                        'completed': '✅ Hoàn thành',
                        'uploaded': '🚀 Đã đăng',
                        'failed': '❌ Thất bại'
                    }
                    status_text = status_icons.get(status, f"❓ {status}")
                    if item['type'] == 'batch_folder':
                        status_text = f"📦 {status_text}"  # Thêm icon batch
                elif item['type'] == 'saved_scan':
                    status_text = "📊 Saved Scan"

                status_item = QTableWidgetItem(status_text)
                # Thêm màu sắc cho trạng thái
                if 'pending' in status_text.lower():
                    status_item.setBackground(QColor(255, 248, 220))  # Vàng nhạt
                elif 'hoàn thành' in status_text.lower():
                    status_item.setBackground(QColor(220, 255, 220))  # Xanh nhạt
                elif 'đã đăng' in status_text.lower():
                    status_item.setBackground(QColor(220, 220, 255))  # Xanh dương nhạt
                elif 'thất bại' in status_text.lower():
                    status_item.setBackground(QColor(255, 220, 220))  # Đỏ nhạt
                self.data_table.setItem(row, 4, status_item)

                # Ngày tạo (cột 5)
                created_at = item['created_at']
                if created_at:
                    try:
                        from datetime import datetime
                        if isinstance(created_at, str):
                            dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                            formatted_date = dt.strftime('%Y-%m-%d %H:%M')
                        else:
                            formatted_date = str(created_at)
                    except:
                        formatted_date = str(created_at)
                else:
                    formatted_date = ""
                self.data_table.setItem(row, 5, QTableWidgetItem(formatted_date))

                # Thao tác (cột 6) - Buttons cho các hành động
                action_text = ""
                if item['type'] == 'folder_scan':
                    status = folder_data.get('status', 'pending')
                    if status == 'pending':
                        action_text = "🔧 Cấu hình"
                    elif status == 'completed':
                        action_text = "🚀 Có thể đăng"
                    elif status == 'uploaded':
                        action_text = "✅ Đã đăng"
                    else:
                        action_text = "⚙️ Xem chi tiết"
                else:
                    action_text = "📋 Load data"

                action_item = QTableWidgetItem(action_text)
                action_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.data_table.setItem(row, 6, action_item)

            # Resize columns to content
            self.data_table.resizeColumnsToContents()

        except Exception as e:
            self.logger.error(f"Error loading detailed data: {str(e)}")
            QMessageBox.critical(self, "Lỗi", f"Không thể load dữ liệu chi tiết: {str(e)}")

    def preview_cleanup(self):
        """Xem trước cleanup"""
        try:
            preview_text = "📋 XEM TRƯỚC CLEANUP:\n\n"

            if self.orphaned_check.isChecked():
                # Count orphaned folders
                folders = self.db_manager.get_all_folder_scans()
                orphaned_count = 0
                for folder in folders:
                    if not os.path.exists(folder.get('path', '')):
                        orphaned_count += 1
                preview_text += f"• Sẽ xóa {orphaned_count} folder scans không còn tồn tại\n"

            if self.duplicate_check.isChecked():
                duplicates = self.db_manager.get_duplicate_folder_scans()
                preview_text += f"• Sẽ gộp {len(duplicates)} nhóm folder scans trùng lặp\n"

            if self.missing_names_check.isChecked():
                folders = self.db_manager.get_all_folder_scans()
                missing_count = 0
                for folder in folders:
                    if not folder.get('data_name') or folder.get('data_name', '').strip() == '':
                        missing_count += 1
                preview_text += f"• Sẽ sửa {missing_count} data_name trống\n"

            if self.optimize_check.isChecked():
                preview_text += "• Sẽ tối ưu database\n"

            preview_text += "\n⚠️ Thao tác này không thể hoàn tác!"

            QMessageBox.information(self, "Xem trước Cleanup", preview_text)

        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Không thể xem trước: {str(e)}")

    def start_cleanup(self):
        """Bắt đầu cleanup"""
        try:
            # Xác nhận
            reply = QMessageBox.question(
                self, "Xác nhận", 
                "Bạn có chắc chắn muốn thực hiện cleanup?\nThao tác này không thể hoàn tác!",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )

            if reply != QMessageBox.StandardButton.Yes:
                return

            # Chuẩn bị options
            cleanup_options = {
                'orphaned_folders': self.orphaned_check.isChecked(),
                'duplicate_folders': self.duplicate_check.isChecked(),
                'missing_data_names': self.missing_names_check.isChecked(),
                'optimize_db': self.optimize_check.isChecked()
            }

            if not any(cleanup_options.values()):
                QMessageBox.information(self, "Thông báo", "Vui lòng chọn ít nhất một tùy chọn cleanup!")
                return

            # Progress dialog
            self.progress_dialog = QProgressDialog("Đang cleanup...", "Hủy", 0, 100, self)
            self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
            self.progress_dialog.setMinimumDuration(0)
            self.progress_dialog.show()

            # Worker thread
            self.cleanup_worker = DataCleanupWorker(self.db_manager, cleanup_options)
            self.cleanup_worker.progress_update.connect(self.on_cleanup_progress)
            self.cleanup_worker.finished.connect(self.on_cleanup_finished)

            self.cleanup_btn.setEnabled(False)
            self.cleanup_worker.start()

        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Không thể bắt đầu cleanup: {str(e)}")

    def on_cleanup_progress(self, percent, message):
        """Cập nhật tiến độ cleanup"""
        if self.progress_dialog:
            self.progress_dialog.setValue(percent)
            self.progress_dialog.setLabelText(message)

    def on_cleanup_finished(self, success, message, results):
        """Hoàn thành cleanup"""
        try:
            if self.progress_dialog:
                self.progress_dialog.close()
                self.progress_dialog = None

            self.cleanup_btn.setEnabled(True)

            if success:
                # Hiển thị kết quả
                result_text = f"✅ CLEANUP HOÀN THÀNH!\n\n"
                result_text += f"📊 KẾT QUẢ:\n"

                if 'orphaned_deleted' in results:
                    result_text += f"• Đã xóa {results['orphaned_deleted']} folder scans không còn tồn tại\n"

                if 'duplicates_found' in results:
                    result_text += f"• Tìm thấy {results['duplicates_found']} nhóm trùng lặp\n"
                    if 'duplicates_merged' in results:
                        result_text += f"• Đã gộp {results['duplicates_merged']} nhóm trùng lặp\n"

                if 'data_names_fixed' in results:
                    result_text += f"• Đã sửa {results['data_names_fixed']} data_name trống\n"

                if results.get('db_optimized'):
                    result_text += f"• Đã tối ưu database\n"

                result_text += f"\n🕒 Thời gian: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

                self.cleanup_results.setPlainText(result_text)

                # Reload summary
                self.load_summary()

                QMessageBox.information(self, "Thành công", message)
            else:
                QMessageBox.critical(self, "Lỗi", message)

        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Lỗi xử lý kết quả cleanup: {str(e)}")

    def export_to_json(self):
        """Xuất dữ liệu ra JSON"""
        try:
            file_path, _ = QFileDialog.getSaveFileName(
                self, "Xuất JSON", f"folder_scans_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                "JSON files (*.json)"
            )

            if file_path:
                exported_file = self.db_manager.export_folder_scans_to_json(file_path)
                QMessageBox.information(self, "Thành công", f"Đã xuất dữ liệu ra: {exported_file}")

        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Không thể xuất JSON: {str(e)}")

    def export_to_csv(self):
        """Xuất dữ liệu ra CSV"""
        try:
            file_path, _ = QFileDialog.getSaveFileName(
                self, "Xuất CSV", f"folder_scans_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                "CSV files (*.csv)"
            )

            if file_path:
                import csv
                folders = self.db_manager.get_all_folder_scans()

                with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
                    if folders:
                        fieldnames = folders[0].keys()
                        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                        writer.writeheader()
                        writer.writerows(folders)

                QMessageBox.information(self, "Thành công", f"Đã xuất {len(folders)} records ra: {file_path}")

        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Không thể xuất CSV: {str(e)}")

    def backup_database(self):
        """Sao lưu database"""
        try:
            import shutil

            file_path, _ = QFileDialog.getSaveFileName(
                self, "Sao lưu Database", 
                f"woocommerce_manager_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db",
                "Database files (*.db)"
            )

            if file_path:
                shutil.copy2(self.db_manager.db_path, file_path)
                QMessageBox.information(self, "Thành công", f"Đã sao lưu database ra: {file_path}")

        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Không thể sao lưu database: {str(e)}")

    def restore_database(self):
        """Khôi phục database"""
        try:
            file_path, _ = QFileDialog.getOpenFileName(
                self, "Khôi phục Database", "", "Database files (*.db)"
            )

            if file_path:
                reply = QMessageBox.question(
                    self, "Xác nhận", 
                    "Thao tác này sẽ ghi đè database hiện tại!\nBạn có chắc chắn?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No
                )

                if reply == QMessageBox.StandardButton.Yes:
                    import shutil
                    shutil.copy2(file_path, self.db_manager.db_path)
                    QMessageBox.information(self, "Thành công", "Đã khôi phục database thành công!")
                    self.load_summary()

        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Không thể khôi phục database: {str(e)}")

    def show_header_context_menu(self, position):
        """Hiển thị context menu cho header để reset kích thước cột"""
        from PyQt6.QtWidgets import QMenu
        menu = QMenu(self)

        # Reset column sizes
        reset_action = menu.addAction("🔄 Reset kích thước cột")
        reset_action.triggered.connect(self.reset_column_sizes)

        # Auto-fit columns
        autofit_action = menu.addAction("📏 Tự động điều chỉnh")
        autofit_action.triggered.connect(self.auto_fit_columns)

        # Save column layout
        save_layout_action = menu.addAction("💾 Lưu layout")
        save_layout_action.triggered.connect(self.save_column_layout)

        # Load column layout
        load_layout_action = menu.addAction("📂 Tải layout")
        load_layout_action.triggered.connect(self.load_column_layout)

        # Show menu
        header = self.data_table.horizontalHeader()
        menu.exec(header.mapToGlobal(position))

    def reset_column_sizes(self):
        """Reset kích thước cột về mặc định"""
        try:
            # Thiết lập lại resize modes
            header = self.data_table.horizontalHeader()
            resize_modes = [
                QHeaderView.ResizeMode.Stretch,           # Tên
                QHeaderView.ResizeMode.Stretch,           # Mô tả
                QHeaderView.ResizeMode.Fixed,             # Số thư mục
                QHeaderView.ResizeMode.Fixed              # Ngày tạo
            ]

            for col, mode in enumerate(resize_modes):
                if col < self.data_table.columnCount():
                    header.setSectionResizeMode(col, mode)

            # Reset width cho các cột Fixed
            self.data_table.setColumnWidth(2, 100)   # Số thư mục
            self.data_table.setColumnWidth(3, 150)   # Ngày tạo

            QMessageBox.information(self, "Thành công", "Đã reset kích thước cột về mặc định")

        except Exception as e:
            self.logger.error(f"Lỗi khi reset column sizes: {str(e)}")
            QMessageBox.critical(self, "Lỗi", f"Không thể reset kích thước cột: {str(e)}")

    def auto_fit_columns(self):
        """Tự động điều chỉnh kích thước cột theo nội dung"""
        try:
            header = self.data_table.horizontalHeader()
            for col in range(self.data_table.columnCount()):
                # Chỉ auto-fit các cột có thể resize
                if header.sectionResizeMode(col) in [
                    QHeaderView.ResizeMode.Interactive,
                    QHeaderView.ResizeMode.ResizeToContents
                ]:
                    self.data_table.resizeColumnToContents(col)

            QMessageBox.information(self, "Thành công", "Đã tự động điều chỉnh kích thước cột")

        except Exception as e:
            self.logger.error(f"Lỗi khi auto-fit columns: {str(e)}")
            QMessageBox.critical(self, "Lỗi", f"Không thể tự động điều chỉnh: {str(e)}")

    def save_column_layout(self):
        """Lưu layout cột hiện tại"""
        try:
            column_widths = []
            column_order = []

            header = self.data_table.horizontalHeader()

            # Lưu độ rộng cột
            for col in range(self.data_table.columnCount()):
                column_widths.append(self.data_table.columnWidth(col))

            # Lưu thứ tự cột (logical index)
            for visual_index in range(header.count()):
                logical_index = header.logicalIndex(visual_index)
                column_order.append(logical_index)

            # Lưu vào biến instance (có thể mở rộng để lưu vào file config)
            self.saved_column_widths = column_widths
            self.saved_column_order = column_order

            QMessageBox.information(self, "Thành công", "Đã lưu layout cột")

        except Exception as e:
            self.logger.error(f"Lỗi khi save column layout: {str(e)}")
            QMessageBox.critical(self, "Lỗi", f"Không thể lưu layout: {str(e)}")

    def load_column_layout(self):
        """Tải layout cột đã lưu"""
        try:
            if not hasattr(self, 'saved_column_widths') or not hasattr(self, 'saved_column_order'):
                QMessageBox.information(self, "Thông báo", "Chưa có layout nào được lưu!")
                return

            header = self.data_table.horizontalHeader()

            # Khôi phục thứ tự cột
            for visual_index, logical_index in enumerate(self.saved_column_order):
                if visual_index < header.count() and logical_index < header.count():
                    current_visual = header.visualIndex(logical_index)
                    if current_visual != visual_index:
                        header.moveSection(current_visual, visual_index)

            # Khôi phục độ rộng cột
            for col, width in enumerate(self.saved_column_widths):
                if col < self.data_table.columnCount():
                    self.data_table.setColumnWidth(col, width)

            QMessageBox.information(self, "Thành công", "Đã tải layout cột")

        except Exception as e:
            self.logger.error(f"Lỗi khi load column layout: {str(e)}")
            QMessageBox.critical(self, "Lỗi", f"Không thể tải layout: {str(e)}")

    def on_data_selection_changed(self):
        """Xử lý khi selection data table thay đổi"""
        has_selection = len(self.data_table.selectedItems()) > 0
        self.edit_data_btn.setEnabled(has_selection)
        self.delete_data_btn.setEnabled(has_selection)
        self.view_details_btn.setEnabled(has_selection)

    def get_selected_folder_data(self):
        """Lấy data được chọn (có thể là saved scan hoặc folder scan)"""
        current_row = self.data_table.currentRow()
        if current_row < 0:
            return None

        # Lấy data từ cột Tên (UserRole)
        name_item = self.data_table.item(current_row, 0)
        if name_item:
            selected_item = name_item.data(Qt.ItemDataRole.UserRole)
            return selected_item
        return None

    def edit_selected_data(self):
        """Chỉnh sửa data được chọn"""
        try:
            folder_data = self.get_selected_folder_data()
            if not folder_data:
                QMessageBox.warning(self, "Cảnh báo", "Vui lòng chọn một item để chỉnh sửa!")
                return

            # Tạo dialog chỉnh sửa
            dialog = DataEditDialog(self, folder_data)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                updated_data = dialog.get_updated_data()

                # Cập nhật vào database
                if self.db_manager.update_folder_scan(folder_data['id'], updated_data):
                    QMessageBox.information(self, "Thành công", "Đã cập nhật dữ liệu thành công!")
                    self.load_detailed_data()
                    self.load_summary()
                else:
                    QMessageBox.critical(self, "Lỗi", "Không thể cập nhật dữ liệu!")

        except Exception as e:
            self.logger.error(f"Lỗi khi chỉnh sửa data: {str(e)}")
            QMessageBox.critical(self, "Lỗi", f"Không thể chỉnh sửa data: {str(e)}")

    def delete_selected_data_batch(self):
        """Xóa data được chọn (hỗ trợ batch delete)"""
        try:
            # Lấy tất cả rows được chọn
            selected_rows = set()
            for item in self.data_table.selectedItems():
                selected_rows.add(item.row())

            if not selected_rows:
                QMessageBox.warning(self, "Cảnh báo", "Vui lòng chọn ít nhất một item để xóa!")
                return

            # Lấy danh sách folder_data để xóa
            folders_to_delete = []
            for row in selected_rows:
                try:
                    item = self.data_table.item(row, 0)
                    if item:
                        item_data = item.data(Qt.ItemDataRole.UserRole)
                        if item_data and item_data.get('type') == 'folder_scan':
                            folder_data = item_data.get('data', {})
                            if folder_data.get('id'):
                                folders_to_delete.append(folder_data)
                except Exception as e:
                    self.logger.warning(f"Lỗi lấy data row {row}: {str(e)}")
                    continue

            if not folders_to_delete:
                QMessageBox.warning(self, "Cảnh báo", "Không tìm thấy dữ liệu hợp lệ để xóa!")
                return

            # Xác nhận xóa
            count = len(folders_to_delete)
            if count == 1:
                data_name = folders_to_delete[0].get('data_name') or folders_to_delete[0].get('original_title', 'N/A')
                message = f"Bạn có chắc chắn muốn xóa data '{data_name}'?"
            else:
                message = f"Bạn có chắc chắn muốn xóa {count} items được chọn?"

            reply = QMessageBox.question(
                self, "Xác nhận xóa", 
                f"{message}\n\nThao tác này không thể hoàn tác!",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )

            if reply == QMessageBox.StandardButton.Yes:
                # Xóa từng folder
                deleted_count = 0
                failed_count = 0

                for folder_data in folders_to_delete:
                    try:
                        if self.db_manager.delete_folder_scan(folder_data['id']):
                            deleted_count += 1
                        else:
                            failed_count += 1
                    except Exception as e:
                        self.logger.error(f"Lỗi xóa folder {folder_data.get('id')}: {str(e)}")
                        failed_count += 1

                # Thông báo kết quả
                if deleted_count > 0:
                    if failed_count == 0:
                        QMessageBox.information(self, "Thành công", f"Đã xóa thành công {deleted_count} items!")
                    else:
                        QMessageBox.warning(self, "Một phần thành công", 
                                          f"Đã xóa {deleted_count} items, {failed_count} items thất bại!")

                    # Refresh data
                    self.load_detailed_data()
                    self.load_summary()
                else:
                    QMessageBox.critical(self, "Lỗi", "Không thể xóa bất kỳ dữ liệu nào!")

        except Exception as e:
            self.logger.error(f"Lỗi khi xóa data batch: {str(e)}")
            QMessageBox.critical(self, "Lỗi", f"Không thể xóa data: {str(e)}")

    def delete_selected_data(self):
        """Xóa data được chọn (legacy function for compatibility)"""
        self.delete_selected_data_batch()

    def view_data_details(self):
        """Xem chi tiết data được chọn"""
        try:
            selected_item = self.get_selected_folder_data()
            if not selected_item:
                QMessageBox.warning(self, "Cảnh báo", "Vui lòng chọn một item để xem chi tiết!")
                return

            # Lấy data thực tế để hiển thị
            display_data = selected_item.get('data', selected_item)

            dialog = DataDetailsDialog(self, display_data, selected_item.get('type', 'unknown'))
            dialog.exec()

        except Exception as e:
            self.logger.error(f"Lỗi khi xem chi tiết data: {str(e)}")
            QMessageBox.critical(self, "Lỗi", f"Không thể xem chi tiết data: {str(e)}")

    def load_folders_from_saved_scan(self, saved_scan_item):
        """Load các folders từ saved scan data"""
        try:
            import json

            saved_scan_data = saved_scan_item.get('data', {})
            data_json = saved_scan_data.get('data', '[]')

            # Parse JSON data
            if isinstance(data_json, str):
                folders_data = json.loads(data_json)
            else:
                folders_data = data_json

            loaded_count = 0
            for folder_data in folders_data:
                if self.validate_folder_for_upload(folder_data):
                    if folder_data not in self.upload_folders:
                        self.upload_folders.append(folder_data)
                        self.add_folder_to_upload_queue(folder_data)
                        loaded_count += 1

            self.logger.info(f"Loaded {loaded_count} folders from saved scan '{saved_scan_data.get('name', '')}'")

        except Exception as e:
            self.logger.error(f"Lỗi khi load folders từ saved scan: {str(e)}")
            QMessageBox.warning(self, "Lỗi", f"Không thể load dữ liệu từ saved scan: {str(e)}")

    def validate_folder_for_upload(self, folder):
        """Kiểm tra folder có hợp lệ để upload không"""
        try:
            # Kiểm tra trạng thái - chỉ cho phép 'pending'
            status = folder.get('status', 'pending')
            if status != 'pending':
                return False

            # Kiểm tra đường dẫn tồn tại
            folder_path = folder.get('path', '')
            if not folder_path or not os.path.exists(folder_path):
                return False

            # Kiểm tra có ảnh không
            image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'}
            has_images = False

            try:
                for file in os.listdir(folder_path):
                    if any(file.lower().endswith(ext) for ext in image_extensions):
                        has_images = True
                        break
            except (OSError, PermissionError):
                return False

            # Kiểm tra có tên sản phẩm không
            product_name = folder.get('new_title') or folder.get('data_name') or folder.get('original_title')
            if not product_name or not product_name.strip():
                return False

            return has_images

        except Exception as e:
            self.logger.error(f"Lỗi validate folder: {str(e)}")
            return False

    def add_folder_to_upload_queue(self, folder):
        """Thêm một folder vào hàng đợi upload table"""
        try:
            row_count = self.upload_queue_table.rowCount()
            self.upload_queue_table.insertRow(row_count)

            # Product name (column 0)
            data_name = folder.get('new_title') or folder.get('data_name') or folder.get('original_title', 'Untitled')
            name_item = QTableWidgetItem(data_name)
            name_item.setData(Qt.ItemDataRole.UserRole, folder)  # Store folder data
            self.upload_queue_table.setItem(row_count, 0, name_item)

            # Path (column 1) - rút gọn đường dẫn nếu quá dài
            path = folder.get('path', '')
            if len(path) > 50:
                path = "..." + path[-47:]
            self.upload_queue_table.setItem(row_count, 1, QTableWidgetItem(path))

            # Image count (column 2)
            image_count = str(folder.get('image_count', 0))
            self.upload_queue_table.setItem(row_count, 2, QTableWidgetItem(image_count))

            # Category (column 3) - lấy tên danh mục
            category_name = "Chưa có"
            category_id = folder.get('category_id')
            if category_id and self.db_manager:
                try:
                    category = self.db_manager.get_category_by_id(category_id)
                    if category:
                        category_name = category.get('name', 'Chưa có')
                except:
                    pass
            elif folder.get('category_name'):
                category_name = folder.get('category_name')
            self.upload_queue_table.setItem(row_count, 3, QTableWidgetItem(str(category_name)))

            # Description (column 4) - mô tả ngắn gọn
            description = folder.get('description', '')
            if not description:
                description = f"Premium quality {data_name}"
            if len(description) > 50:
                description = description[:50] + "..."
            self.upload_queue_table.setItem(row_count, 4, QTableWidgetItem(str(description)))

            # Site (column 5) - tên site đăng
            site_name = "Chưa chọn"
            site_id = folder.get('site_id')
            if site_id and self.db_manager:
                try:
                    sites = self.db_manager.get_all_sites()
                    for site in sites:
                        if site.id == site_id:
                            site_name = site.name
                            break
                except:
                    pass
            elif folder.get('site_name'):
                site_name = folder.get('site_name')
            self.upload_queue_table.setItem(row_count, 5, QTableWidgetItem(str(site_name)))

            # Status (column 6) - initial status với màu sắc
            status_item = QTableWidgetItem("⏳ Chờ đăng")
            status_item.setBackground(QColor(255, 248, 220))  # Light yellow
            self.upload_queue_table.setItem(row_count, 6, status_item)

        except Exception as e:
            self.logger.error(f"Lỗi khi thêm folder vào queue: {str(e)}")

    def on_queue_selection_changed(self):
        """Xử lý khi selection trong upload queue thay đổi"""
        try:
            has_selection = len(self.upload_queue_table.selectedItems()) > 0
            self.remove_selected_btn.setEnabled(has_selection and len(self.upload_folders) > 0)
        except Exception as e:
            self.logger.error(f"Lỗi queue selection changed: {str(e)}")

    def show_upload_config(self):
        """Hiển thị dialog cấu hình upload bằng ProductUploadDialog"""
        try:
            # Import ProductUploadDialog 
            from .product_upload_dialog import ProductUploadDialog

            dialog = ProductUploadDialog(
                parent=self,
                sites=self.db_manager.get_active_sites(),
                db_manager=self.db_manager,
                selected_folders=self.upload_folders
            )

            # Kết nối signal product_uploaded
            dialog.product_uploaded.connect(self.on_product_uploaded_from_dialog)

            if dialog.exec() == QDialog.DialogCode.Accepted:
                # Lưu cấu hình từ dialog
                if hasattr(dialog, 'saved_bulk_config') and dialog.saved_bulk_config:
                    self.save_upload_config(dialog.saved_bulk_config)
                elif hasattr(dialog, 'bulk_site_combo'):
                    # Tự động lưu cấu hình từ dialog controls
                    auto_config = {
                        'site_id': dialog.bulk_site_combo.currentData(),
                        'category_id': dialog.bulk_category_combo.currentData() if hasattr(dialog, 'bulk_category_combo') else None,
                        'status': dialog.bulk_status_combo.currentText() if hasattr(dialog, 'bulk_status_combo') else 'draft',
                        'price': dialog.bulk_regular_price.value() if hasattr(dialog, 'bulk_regular_price') else 25.0,
                        'delay': dialog.upload_delay.value() if hasattr(dialog, 'upload_delay') else 3
                    }
                    self.save_upload_config(auto_config)

                # Upload thành công, clear queue và refresh data
                self.upload_folders = []
                self.upload_queue_table.setRowCount(0)
                self.config_upload_btn.setEnabled(False)
                self.start_upload_btn.setEnabled(False)
                self.upload_status_label.setText("Upload hoàn thành, đã clear hàng đợi")

                # Refresh data trong bảng chi tiết
                self.load_detailed_data()
                self.load_summary()

                QMessageBox.information(
                    self, "Thành công", 
                    "Đã hoàn thành upload sản phẩm!\n"
                    "Dữ liệu đã được cập nhật trong database."
                )
            else:
                # User cancel hoặc có lỗi - vẫn lưu cấu hình nếu có
                if hasattr(dialog, 'saved_bulk_config') and dialog.saved_bulk_config:
                    self.save_upload_config(dialog.saved_bulk_config)
                self.upload_status_label.setText("Đã hủy upload, dữ liệu vẫn trong hàng đợi")

        except Exception as e:
            self.logger.error(f"Lỗi khi hiển thị dialog upload: {str(e)}")
            QMessageBox.critical(self, "Lỗi", f"Không thể hiển thị dialog upload: {str(e)}")

    def pause_upload(self):
        """Tạm dừng upload"""
        try:
            # Placeholder for pause functionality
            self.upload_status_label.setText("⏸️ Upload đã tạm dừng")
            self.pause_upload_btn.setEnabled(False)
            self.resume_upload_btn.setEnabled(True)
            self.resume_upload_btn.setVisible(True)
            self.logger.info("Upload paused")
        except Exception as e:
            self.logger.error(f"Error pausing upload: {str(e)}")

    def resume_upload(self):
        """Tiếp tục upload"""
        try:
            # Placeholder for resume functionality
            self.upload_status_label.setText("▶️ Upload đã tiếp tục")
            self.pause_upload_btn.setEnabled(True)
            self.resume_upload_btn.setEnabled(False)
            self.resume_upload_btn.setVisible(False)
            self.logger.info("Upload resumed")
        except Exception as e:
            self.logger.error(f"Error resuming upload: {str(e)}")

    def stop_upload(self):
        """Dừng upload"""
        try:
            reply = QMessageBox.question(
                self, "Xác nhận", 
                "Bạn có chắc chắn muốn dừng upload?\nTiến trình hiện tại sẽ bị hủy.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self.upload_status_label.setText("⏹️ Upload đã dừng")
                self.pause_upload_btn.setEnabled(False)
                self.resume_upload_btn.setEnabled(False)
                self.resume_upload_btn.setVisible(False)
                self.stop_upload_btn.setEnabled(False)
                self.start_upload_btn.setEnabled(True)
                self.logger.info("Upload stopped")
                
        except Exception as e:
            self.logger.error(f"Error stopping upload: {str(e)}")
            QMessageBox.critical(self, "Lỗi", f"Không thể dừng upload: {str(e)}")

    def on_product_uploaded_from_dialog(self, product_result):
        """Xử lý khi có sản phẩm được upload thành công từ dialog"""
        try:
            product_id = product_result.get('id')
            product_name = product_result.get('name', 'Unknown')

            self.logger.info(f"Sản phẩm được upload: {product_name} (ID: {product_id})")

            # Có thể thêm logic cập nhật trạng thái trong queue table ở đây

        except Exception as e:
            self.logger.error(f"Lỗi xử lý product uploaded signal: {str(e)}")

    def save_upload_config(self, config):
        """Lưu cấu hình upload"""
        try:
            # Mở rộng config để lưu thêm thông tin
            enhanced_config = {
                'configured': True,
                'site_id': config.get('site_id'),
                'category_id': config.get('category_id'), 
                'status': config.get('status', 'draft'),
                'price': config.get('price', 25.0),
                'delay': config.get('delay', 3),
                'image_gallery': config.get('image_gallery', True),
                'auto_description': config.get('auto_description', True),
                'last_updated': datetime.now().isoformat()
            }

            self.upload_config = enhanced_config
            self.logger.info("Đã lưu cấu hình upload thành công với thông tin mở rộng")

            # Update UI status
            if hasattr(self, 'upload_status_label'):
                self.upload_status_label.setText("Cấu hình đã được lưu - sẵn sàng upload tự động")

            return True
        except Exception as e:
            self.logger.error(f"Lỗi lưu cấu hình upload: {str(e)}")
            return False

    def show_saved_scans_dialog(self):
        """Hiển thị dialog để chọn và load saved scans"""
        try:
            saved_scans = self.db_manager.get_all_saved_scans()
            if not saved_scans:
                QMessageBox.information(self, "Thông báo", "Không có saved scans nào!\nVui lòng quét thư mục và lưu kết quả trước.")
                return

            # Tạo dialog chọn saved scan
            dialog = QDialog(self)
            dialog.setWindowTitle("📦 Chọn Saved Scan để Load")
            dialog.setModal(True)
            dialog.resize(800, 500)

            layout = QVBoxLayout(dialog)

            # Thông tin
            info_label = QLabel("Chọn một hoặc nhiều saved scans để load vào quản lý:")
            info_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
            layout.addWidget(info_label)

            # Table hiển thị saved scans
            table = QTableWidget()
            table.setColumnCount(5)
            table.setHorizontalHeaderLabels(["Chọn", "Tên", "Mô tả", "Số thư mục", "Ngày tạo"])
            table.setRowCount(len(saved_scans))
            table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)

            for i, scan in enumerate(saved_scans):
                # Checkbox
                checkbox = QCheckBox()
                table.setCellWidget(i, 0, checkbox)

                # Data
                table.setItem(i, 1, QTableWidgetItem(scan.get('name', '')))
                table.setItem(i, 2, QTableWidgetItem(scan.get('description', '')))
                table.setItem(i, 3, QTableWidgetItem(str(scan.get('folder_count', 0))))
                table.setItem(i, 4, QTableWidgetItem(str(scan.get('created_at', ''))))

                # Lưu data vào item
                table.item(i, 1).setData(Qt.ItemDataRole.UserRole, scan)

            table.resizeColumnsToContents()
            table.setColumnWidth(0, 60)  # Checkbox column
            layout.addWidget(table)

            # Buttons
            button_layout = QHBoxLayout()

            select_all_btn = QPushButton("☑️ Chọn tất cả")
            select_all_btn.clicked.connect(lambda: self.toggle_all_checkboxes(table, True))
            button_layout.addWidget(select_all_btn)

            deselect_all_btn = QPushButton("☐ Bỏ chọn tất cả")
            deselect_all_btn.clicked.connect(lambda: self.toggle_all_checkboxes(table, False))
            button_layout.addWidget(deselect_all_btn)

            button_layout.addStretch()

            load_btn = QPushButton("📋 Load đã chọn")
            load_btn.setStyleSheet("""
                QPushButton {
                    background-color: #007bff;
                    color: white;
                    font-weight: bold;
                    padding: 8px 16px;
                    border: none;
                    border-radius: 4px;
                }
                QPushButton:hover {
                    background-color: #0056b3;
                }
            """)
            load_btn.clicked.connect(lambda: self.load_selected_saved_scans(dialog, table))
            button_layout.addWidget(load_btn)

            cancel_btn = QPushButton("❌ Hủy")
            cancel_btn.clicked.connect(dialog.reject)
            button_layout.addWidget(cancel_btn)

            layout.addLayout(button_layout)

            dialog.exec()

        except Exception as e:
            self.logger.error(f"Lỗi hiển thị saved scans dialog: {str(e)}")
            QMessageBox.critical(self, "Lỗi", f"Không thể hiển thị saved scans: {str(e)}")

    def toggle_all_checkboxes(self, table, checked_state):
        """Toggle tất cả checkboxes trong table"""
        try:
            for row in range(table.rowCount()):
                checkbox = table.cellWidget(row, 0)
                if checkbox:
                    checkbox.setChecked(checked_state)
        except Exception as e:
            self.logger.error(f"Lỗi toggle checkboxes: {str(e)}")

    def load_selected_saved_scans(self, dialog, table):
        """Load các saved scans đã chọn"""
        try:
            import json
            selected_scans = []

            # Collect selected scans
            for row in range(table.rowCount()):
                checkbox = table.cellWidget(row, 0)
                if checkbox and checkbox.isChecked():
                    scan_data = table.item(row, 1).data(Qt.ItemDataRole.UserRole)
                    if scan_data:
                        selected_scans.append(scan_data)

            if not selected_scans:
                QMessageBox.warning(dialog, "Cảnh báo", "Vui lòng chọn ít nhất một saved scan!")
                return

            # Load folders từ selected scans
            total_loaded = 0
            for scan in selected_scans:
                try:
                    data_json = scan.get('data', '[]')
                    if isinstance(data_json, str):
                        folders_data = json.loads(data_json)
                    else:
                        folders_data = data_json

                    # Load từng folder vào database nếu chưa tồn tại
                    for folder_data in folders_data:
                        path = folder_data.get('path', '')
                        if path:
                            # Kiểm tra đã tồn tại chưa
                            existing = self.db_manager.get_folder_scan_by_path(path)
                            if not existing:
                                # Tạo mới
                                self.db_manager.create_folder_scan(folder_data)
                                total_loaded += 1
                            else:
                                # Cập nhật nếu cần thiết
                                self.db_manager.update_folder_scan(existing['id'], folder_data)

                except Exception as e:
                    self.logger.error(f"Lỗi load scan '{scan.get('name', '')}': {str(e)}")
                    continue

            # Refresh data
            self.load_detailed_data()
            self.load_summary()

            dialog.accept()

            QMessageBox.information(
                self, "Thành công", 
                f"Đã load {total_loaded} folder mới từ {len(selected_scans)} saved scans!\n"
                f"Dữ liệu đã được cập nhật trong bảng quản lý."
            )

        except Exception as e:
            self.logger.error(f"Lỗi load selected saved scans: {str(e)}")
            QMessageBox.critical(dialog, "Lỗi", f"Không thể load saved scans: {str(e)}")

    def start_upload_scheduler(self):
        """Bắt đầu upload với cấu hình đã thiết lập - tự động load và upload"""
        try:
            if not self.upload_folders:
                QMessageBox.warning(self, "Cảnh báo", "Không có folder nào để upload!")
                return

            # Kiểm tra có cấu hình default không
            if not self.upload_config.get('configured', False):
                # Hiển thị dialog cấu hình trước
                reply = QMessageBox.question(
                    self, "Cấu hình upload", 
                    "Chưa có cấu hình upload. Bạn có muốn thiết lập trước không?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.Yes
                )

                if reply == QMessageBox.StandardButton.Yes:
                    self.show_upload_config()
                    return
                else:
                    # Sử dụng cấu hình mặc định
                    self.auto_upload_with_default_config()

        except Exception as e:
            self.logger.error(f"Lỗi khi bắt đầu upload: {str(e)}")
            QMessageBox.critical(self, "Lỗi", f"Không thể bắt đầu upload: {str(e)}")

    def refresh_upload_data(self):
        """Làm mới dữ liệu upload"""
        try:
            self.logger.info("Refreshing upload data...")
            
            # Reload upload batch selector
            self.load_upload_batch_selector()
            
            # Refresh upload stats if batch is selected
            self.on_upload_batch_changed()
            
            # Refresh upload queue if there are folders loaded
            if hasattr(self, 'upload_folders') and self.upload_folders:
                self.refresh_upload_queue()
                
            # Update status
            self.upload_status_label.setText("🔄 Đã làm mới dữ liệu upload")
            
            self.logger.info("Upload data refreshed successfully")
            
        except Exception as e:
            self.logger.error(f"Error refreshing upload data: {str(e)}")
            QMessageBox.critical(self, "Lỗi", f"Không thể làm mới dữ liệu upload: {str(e)}")

    def refresh_upload_queue(self):
        """Làm mới hàng đợi upload"""
        try:
            if not hasattr(self, 'upload_folders') or not self.upload_folders:
                self.upload_status_label.setText("Không có dữ liệu trong hàng đợi để làm mới")
                return
                
            # Clear current table
            self.upload_queue_table.setRowCount(0)
            
            # Re-add all folders to queue with updated status
            valid_folders = []
            for folder in self.upload_folders:
                # Re-validate folder
                if self.validate_folder_for_upload(folder):
                    # Check if folder is already processed
                    if not self.is_folder_already_processed(folder):
                        self.add_folder_to_upload_queue(folder)
                        valid_folders.append(folder)
                        
            # Update folders list with only valid ones
            self.upload_folders = valid_folders
            
            # Update button states
            has_folders = len(self.upload_folders) > 0
            self.clear_queue_btn.setEnabled(has_folders)
            self.start_upload_btn.setEnabled(has_folders)
            self.config_upload_btn.setEnabled(has_folders)
            
            # Update status
            removed_count = len([f for f in self.upload_folders]) - len(valid_folders)
            if removed_count > 0:
                self.upload_status_label.setText(f"🔄 Đã làm mới hàng đợi - Loại bỏ {removed_count} sản phẩm đã xử lý")
            else:
                self.upload_status_label.setText(f"🔄 Đã làm mới hàng đợi - {len(valid_folders)} sản phẩm sẵn sàng")
                
        except Exception as e:
            self.logger.error(f"Error refreshing upload queue: {str(e)}")
            QMessageBox.critical(self, "Lỗi", f"Không thể làm mới hàng đợi: {str(e)}")

    def clear_upload_queue(self):
        """Xóa hàng đợi upload"""
        try:
            reply = QMessageBox.question(
                self, "Xác nhận", 
                "Bạn có chắc chắn muốn xóa toàn bộ hàng đợi upload?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self.upload_folders = []
                self.upload_queue_table.setRowCount(0)
                
                # Disable buttons
                self.clear_queue_btn.setEnabled(False)
                self.start_upload_btn.setEnabled(False)
                self.config_upload_btn.setEnabled(False)
                self.remove_selected_btn.setEnabled(False)
                
                # Update status
                self.upload_status_label.setText("Đã xóa hàng đợi upload")
                
        except Exception as e:
            self.logger.error(f"Error clearing upload queue: {str(e)}")
            QMessageBox.critical(self, "Lỗi", f"Không thể xóa hàng đợi: {str(e)}")

    def remove_selected_from_queue(self):
        """Xóa các items được chọn từ hàng đợi"""
        try:
            selected_rows = set()
            for item in self.upload_queue_table.selectedItems():
                selected_rows.add(item.row())
                
            if not selected_rows:
                QMessageBox.warning(self, "Cảnh báo", "Vui lòng chọn ít nhất một sản phẩm để xóa!")
                return
                
            # Remove from upload_folders list
            rows_to_remove = sorted(selected_rows, reverse=True)
            for row in rows_to_remove:
                if row < len(self.upload_folders):
                    self.upload_folders.pop(row)
                    
            # Refresh the queue table
            self.refresh_upload_queue()
            
        except Exception as e:
            self.logger.error(f"Error removing selected from queue: {str(e)}")
            QMessageBox.critical(self, "Lỗi", f"Không thể xóa items đã chọn: {str(e)}")

    def auto_upload_with_default_config(self):
        """Tự động upload với cấu hình mặc định"""
        try:
            # Lấy sites
            sites = self.db_manager.get_active_sites()
            if not sites:
                QMessageBox.warning(
                    self, "Cảnh báo", 
                    "Không có site WooCommerce nào hoạt động!\n"
                    "Vui lòng thêm và kích hoạt site trong tab 'Quản lý Site'."
                )
                return

            # Import ProductUploadDialog
            from .product_upload_dialog import ProductUploadDialog

            # Tạo dialog với auto_start=True
            dialog = ProductUploadDialog(
                parent=self, 
                sites=sites, 
                db_manager=self.db_manager, 
                selected_folders=self.upload_folders
            )

            # Áp dụng cấu hình hiện tại nếu có
            if self.upload_config.get('configured', False):
                self.apply_config_to_dialog(dialog)

            # Kết nối signal để theo dõi kết quả upload
            dialog.product_uploaded.connect(self.on_product_uploaded_from_dialog)

            # Tự động bắt đầu upload luôn
            QTimer.singleShot(500, lambda: self.auto_start_upload_in_dialog(dialog))

            # Hiển thị dialog
            result = dialog.exec()

            if result == QDialog.DialogCode.Accepted:
                # Upload thành công, clear queue và refresh data
                self.upload_folders = []
                self.upload_queue_table.setRowCount(0)
                self.config_upload_btn.setEnabled(False)
                self.start_upload_btn.setEnabled(False)
                self.upload_status_label.setText("Upload hoàn thành, đã clear hàng đợi")

                # Refresh data trong bảng chi tiết
                self.load_detailed_data()
                self.load_summary()

                QMessageBox.information(
                    self, "Thành công", 
                    "Đã hoàn thành upload sản phẩm!\n"
                    "Dữ liệu đã được cập nhật trong database."
                )
            else:
                # User cancel hoặc có lỗi
                self.upload_status_label.setText("Đã hủy upload, dữ liệu vẫn trong hàng đợi")

        except Exception as e:
            self.logger.error(f"Lỗi auto upload: {str(e)}")
            QMessageBox.critical(self, "Lỗi", f"Không thể auto upload: {str(e)}")

    def apply_config_to_dialog(self, dialog):
        """Áp dụng cấu hình hiện tại vào dialog"""
        try:
            config = self.upload_config

            # Thiết lập site
            site_id = config.get('site_id')
            if site_id and hasattr(dialog, 'bulk_site_combo'):
                for i in range(dialog.bulk_site_combo.count()):
                    if dialog.bulk_site_combo.itemData(i) == site_id:
                        dialog.bulk_site_combo.setCurrentIndex(i)
                        break

            # Thiết lập category
            category_id = config.get('category_id')
            if category_id and hasattr(dialog, 'bulk_category_combo'):
                # Update category combo theo site
                dialog.on_bulk_site_changed()
                for i in range(dialog.bulk_category_combo.count()):
                    if dialog.bulk_category_combo.itemData(i) == category_id:
                        dialog.bulk_category_combo.setCurrentIndex(i)
                        break

            #            # Thiết lập các thông số khác
            if hasattr(dialog, 'bulk_status_combo'):
                status = config.get('status', 'draft')
                index = dialog.bulk_status_combo.findText(status)
                if index >= 0:
                    dialog.bulk_status_combo.setCurrentIndex(index)

            if hasattr(dialog, 'bulk_regular_price'):
                price = config.get('price', 25.0)
                dialog.bulk_regular_price.setValue(price)

            if hasattr(dialog, 'upload_delay'):
                delay = config.get('delay', 3)
                dialog.upload_delay.setValue(delay)

            self.logger.info("Đã áp dụng cấu hình upload vào dialog")

        except Exception as e:
            self.logger.error(f"Lỗi apply config to dialog: {str(e)}")

    def auto_start_upload_in_dialog(self, dialog):
        """Tự động bắt đầu upload trong dialog"""
        try:
            if hasattr(dialog, 'start_bulk_upload'):
                # Tự động nhấn nút upload
                dialog.start_bulk_upload()
                self.logger.info("Đã tự động bắt đầu bulk upload")
            else:
                self.logger.warning("Dialog không có method start_bulk_upload")

        except Exception as e:
            self.logger.error(f"Lỗi auto start upload in dialog: {str(e)}")
            QMessageBox.critical(
                self, "Lỗi", 
                f"Không thể tự động bắt đầu upload:\n{str(e)}\n"
                "Vui lòng nhấn nút 'Đăng hàng loạt' trong dialog."
            )

    def pause_upload(self):
        """Tạm dừng upload"""
        try:
            if hasattr(self, 'upload_worker') and self.upload_worker:
                self.upload_worker.pause()
                self.pause_upload_btn.setEnabled(False)
                self.resume_upload_btn.setEnabled(True)
                self.resume_upload_btn.setVisible(True)
                self.upload_status_label.setText("Upload đã tạm dừng")

        except Exception as e:
            self.logger.error(f"Lỗi khi tạm dừng upload: {str(e)}")
            QMessageBox.critical(self, "Lỗi", f"Không thể tạm dừng upload: {str(e)}")

    def resume_upload(self):
        """Tiếp tục upload"""
        try:
            if hasattr(self, 'upload_worker') and self.upload_worker:
                self.upload_worker.resume()
                self.pause_upload_btn.setEnabled(True)
                self.resume_upload_btn.setEnabled(False)
                self.resume_upload_btn.setVisible(False)
                self.upload_status_label.setText("Đang tiếp tục upload...")

        except Exception as e:
            self.logger.error(f"Lỗi khi tiếp tục upload: {str(e)}")
            QMessageBox.critical(self, "Lỗi", f"Không thể tiếp tục upload: {str(e)}")

    def stop_upload(self):
        """Dừng upload hoàn toàn"""
        try:
            reply = QMessageBox.question(
                self, "Xác nhận", 
                "Bạn có chắc chắn muốn dừng upload?\nCác sản phẩm đã upload sẽ không bị ảnh hưởng.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )

            if reply == QMessageBox.StandardButton.Yes:
                if hasattr(self, 'upload_worker') and self.upload_worker:
                    self.upload_worker.stop()
                    self.upload_worker.wait()  # Wait for thread to finish

                self.on_upload_finished()
                self.upload_status_label.setText("Upload đã bị dừng")

        except Exception as e:
            self.logger.error(f"Lỗi khi dừng upload: {str(e)}")
            QMessageBox.critical(self, "Lỗi", f"Không thể dừng upload: {str(e)}")

    def clear_upload_queue(self):
        """Clear hàng đợi upload"""
        try:
            reply = QMessageBox.question(
                self, "Xác nhận", 
                "Bạn có chắc chắn muốn xóa toàn bộ hàng đợi upload?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )

            if reply == QMessageBox.StandardButton.Yes:
                self.upload_folders = []
                self.upload_queue_table.setRowCount(0)
                self.config_upload_btn.setEnabled(False)
                self.start_upload_btn.setEnabled(False)
                self.upload_status_label.setText("Đã xóa hàng đợi upload")

                QMessageBox.information(self, "Thành công", "Đã xóa toàn bộ hàng đợi upload")

        except Exception as e:
            self.logger.error(f"Lỗi khi clear upload queue: {str(e)}")
            QMessageBox.critical(self, "Lỗi", f"Không thể clear hàng đợi: {str(e)}")

    def remove_selected_from_queue(self):
        """Xóa item được chọn khỏi hàng đợi upload"""
        try:
            current_row = self.upload_queue_table.currentRow()
            if current_row < 0:
                QMessageBox.information(self, "Thông báo", "Vui lòng chọn một item để xóa!")
                return

            # Remove from upload_folders list
            if current_row < len(self.upload_folders):
                removed_folder = self.upload_folders.pop(current_row)
                folder_name = removed_folder.get('data_name', 'Unknown')

                # Remove from table
                self.upload_queue_table.removeRow(current_row)

                # Update buttons
                if not self.upload_folders:
                    self.config_upload_btn.setEnabled(False)
                    self.start_upload_btn.setEnabled(False)
                    self.upload_status_label.setText("Hàng đợi trống")
                else:
                    self.upload_status_label.setText(f"Còn {len(self.upload_folders)} item trong hàng đợi")

                QMessageBox.information(self, "Thành công", f"Đã xóa '{folder_name}' khỏi hàng đợi")

        except Exception as e:
            self.logger.error(f"Lỗi khi xóa item khỏi queue: {str(e)}")
            QMessageBox.critical(self, "Lỗi", f"Không thể xóa item: {str(e)}")

    def update_upload_status(self, folder, status):
        """Cập nhật trạng thái upload trong queue table"""
        try:
            # Find the row in the table for the given folder
            row = -1
            for i in range(self.upload_queue_table.rowCount()):
                item = self.upload_queue_table.item(i, 1)  # Path is in column 1
                if item and item.text() == folder.get('path'):
                    row = i
                    break

            if row >= 0:
                self.upload_queue_table.setItem(row, 6, QTableWidgetItem(status))  # Update status in column 6

        except Exception as e:
            self.logger.error(f"Lỗi khi cập nhật trạng thái upload: {str(e)}")

    def update_upload_progress(self, completed, total):
        """Cập nhật tiến độ upload"""
        try:
            percent = int((completed / total) * 100) if total > 0 else 0
            self.upload_progress_bar.setValue(percent)
            self.upload_progress_label.setText(f"{completed}/{total}")

        except Exception as e:
            self.logger.error(f"Lỗi khi cập nhật tiến độ upload: {str(e)}")

    def update_upload_log(self, folder, log):
        """Cập nhật log upload trong queue table"""
        try:
            # Find the row in the table for the given folder
            row = -1
            for i in range(self.upload_queue_table.rowCount()):
                item = self.upload_queue_table.item(i, 1)  # Path is in column 1
                if item and item.text() == folder.get('path'):
                    row = i
                    break

            if row >= 0:
                self.upload_queue_table.setItem(row, 7, QTableWidgetItem(log))  # Update log in column 7

        except Exception as e:
            self.logger.error(f"Lỗi khi cập nhật log upload: {str(e)}")

    def on_upload_finished(self):
        """Xử lý khi upload hoàn thành (hoặc dừng)"""
        try:
            # Re-enable controls
            self.load_selected_btn.setEnabled(True)
            self.config_upload_btn.setEnabled(True)
            self.start_upload_btn.setEnabled(True)

            # Reset control buttons
            if hasattr(self, 'pause_upload_btn'):
                self.pause_upload_btn.setEnabled(False)
            if hasattr(self, 'resume_upload_btn'):
                self.resume_upload_btn.setEnabled(False)
                self.resume_upload_btn.setVisible(False)
            if hasattr(self, 'stop_upload_btn'):
                self.stop_upload_btn.setEnabled(False)

            # Reset UI
            self.upload_status_label.setText("Upload hoàn thành")
            self.upload_progress_bar.setVisible(False)
            self.upload_progress_bar.setValue(0)

            if hasattr(self, 'upload_worker') and self.upload_worker:
                completed = getattr(self.upload_worker, 'completed_count', 0)
                total = len(self.upload_folders) if self.upload_folders else 0
                if total > 0:
                    QMessageBox.information(self, "Thông báo", f"Đã upload {completed}/{total} mục.")

            self.upload_worker = None  # Clear worker

        except Exception as e:
            self.logger.error(f"Lỗi khi upload hoàn thành: {str(e)}")
            QMessageBox.critical(self, "Lỗi", f"Lỗi trong quá trình upload: {str(e)}")

    def on_search_changed(self):
        """Xử lý khi thay đổi từ khóa tìm kiếm"""
        search_text = self.search_input.text().lower().strip()

        for row in range(self.data_table.rowCount()):
            show_row = True

            if search_text:
                # Tìm kiếm trong tất cả các cột
                row_text = ""
                for col in range(self.data_table.columnCount()):
                    item = self.data_table.item(row, col)
                    if item:
                        row_text += item.text().lower() + " "

                show_row = search_text in row_text

            self.data_table.setRowHidden(row, not show_row)

    def on_bulk_edit_selected(self):
        """Sửa hàng loạt dữ liệu được chọn"""
        selected_items = self.data_table.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Cảnh báo", "Vui lòng chọn ít nhất một dòng!")
            return

        # Import dialog sửa hàng loạt
        from .bulk_folder_edit_dialog import BulkFolderEditDialog

        dialog = BulkFolderEditDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            update_data = dialog.get_update_data()

            # Cập nhật cho tất cả folder được chọn
            updated_count = 0
            for row in range(self.data_table.rowCount()):
                if self.data_table.item(row, 0).isSelected():
                    item_data = self.data_table.item(row, 0).data(Qt.ItemDataRole.UserRole)
                    if item_data and item_data['type'] == 'folder_scan':
                        folder_id = item_data['id']
                        if self.db_manager.update_folder_scan(folder_id, update_data):
                            updated_count += 1

            QMessageBox.information(
                self, "Thành công", 
                f"Đã cập nhật {updated_count} folder thành công!"
            )
            self.load_detailed_data()

    def on_export_selected_data(self):
        """Xuất dữ liệu được chọn"""
        selected_rows = set()
        for item in self.data_table.selectedItems():
            selected_rows.add(item.row())

        if not selected_rows:
            QMessageBox.warning(self, "Cảnh báo", "Vui lòng chọn ít nhất một dòng!")
            return

        # Chọn file để lưu
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Xuất dữ liệu", "", 
            "JSON files (*.json);;CSV files (*.csv)"
        )

        if file_path:
            try:
                export_data = []
                for row in selected_rows:
                    item_data = self.data_table.item(row, 0).data(Qt.ItemDataRole.UserRole)
                    if item_data:
                        export_data.append(item_data['data'])

                if file_path.endswith('.json'):
                    import json
                    with open(file_path, 'w', encoding='utf-8') as f:
                        json.dump(export_data, f, ensure_ascii=False, indent=2)
                elif file_path.endswith('.csv'):
                    import csv
                    if export_data:
                        with open(file_path, 'w', newline='', encoding='utf-8') as f:
                            writer = csv.DictWriter(f, fieldnames=export_data[0].keys())
                            writer.writeheader()
                            writer.writerows(export_data)

                QMessageBox.information(
                    self, "Thành công", 
                    f"Đã xuất {len(export_data)} bản ghi ra {file_path}"
                )

            except Exception as e:
                QMessageBox.critical(self, "Lỗi", f"Lỗi xuất dữ liệu: {str(e)}")


class DataEditDialog(QDialog):
    """Dialog chỉnh sửa folder scan data"""

    def __init__(self, parent=None, folder_data=None):
        super().__init__(parent)
        self.folder_data = folder_data or {}
        self.init_ui()
        self.load_data()

    def init_ui(self):
        """Khởi tạo giao diện"""
        self.setWindowTitle("✏️ Chỉnh sửa Folder Scan Data")
        self.setModal(True)
        self.resize(500, 400)

        layout = QVBoxLayout(self)

        # Form fields
        form_group = QGroupBox("📝 Thông tin cần chỉnh sửa")
        form_layout = QFormLayout(form_group)

        self.data_name_edit = QLineEdit()
        form_layout.addRow("Tên data:", self.data_name_edit)

        self.original_title_edit = QLineEdit()
        form_layout.addRow("Tiêu đề gốc:", self.original_title_edit)

        self.path_edit = QLineEdit()
        form_layout.addRow("Đường dẫn:", self.path_edit)

        self.status_combo = QComboBox()
        self.status_combo.addItems(["pending", "completed", "uploaded", "error"])
        form_layout.addRow("Trạng thái:", self.status_combo)

        self.image_count_spin = QSpinBox()
        self.image_count_spin.setRange(0, 999999)
        form_layout.addRow("Số thư mục:", self.image_count_spin)

        self.notes_edit = QTextEdit()
        self.notes_edit.setMaximumHeight(100)
        form_layout.addRow("Ghi chú:", self.notes_edit)

        layout.addWidget(form_group)

        # Buttons
        buttons_layout = QHBoxLayout()

        self.save_btn = QPushButton("💾 Lưu")
        self.save_btn.clicked.connect(self.accept)
        buttons_layout.addWidget(self.save_btn)

        self.cancel_btn = QPushButton("❌ Hủy")
        self.cancel_btn.clicked.connect(self.reject)
        buttons_layout.addWidget(self.cancel_btn)

        layout.addLayout(buttons_layout)

    def load_data(self):
        """Load dữ liệu hiện tại vào form"""
        try:
            self.data_name_edit.setText(self.folder_data.get('data_name', ''))
            self.original_title_edit.setText(self.folder_data.get('original_title', ''))
            self.path_edit.setText(self.folder_data.get('path', ''))

            status = self.folder_data.get('status', 'pending')
            index = self.status_combo.findText(status)
            if index >= 0:
                self.status_combo.setCurrentIndex(index)

            self.image_count_spin.setValue(self.folder_data.get('image_count', 0))
            self.notes_edit.setPlainText(self.folder_data.get('notes', ''))

        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Không thể load dữ liệu: {str(e)}")

    def get_updated_data(self):
        """Lấy dữ liệu đã chỉnh sửa"""
        return {
            'data_name': self.data_name_edit.text().strip(),
            'original_title': self.original_title_edit.text().strip(),
            'path': self.path_edit.text().strip(),
            'status': self.status_combo.currentText(),
            'image_count': self.image_count_spin.value(),
            'notes': self.notes_edit.toPlainText().strip()
        }


class DataDetailsDialog(QDialog):
    """Dialog xem chi tiết data (saved scan hoặc folder scan)"""

    def __init__(self, parent=None, data=None, data_type="unknown"):
        super().__init__(parent)
        self.data = data or {}
        self.data_type = data_type
        self.init_ui()
        self.load_data()

    def init_ui(self):
        """Khởi tạo giao diện"""
        title = "👁️ Chi tiết Saved Scan" if self.data_type == 'saved_scan' else "👁️ Chi tiết Folder Scan"
        self.setWindowTitle(title)
        self.setModal(True)
        self.resize(700, 600)

        layout = QVBoxLayout(self)

        # Details display
        details_group = QGroupBox("📋 Thông tin chi tiết")
        details_layout = QVBoxLayout(details_group)

        self.details_text = QTextEdit()
        self.details_text.setReadOnly(True)
        details_layout.addWidget(self.details_text)

        layout.addWidget(details_group)

        # Buttons
        buttons_layout = QHBoxLayout()

        # Load button chỉ hiển thị cho saved scans
        if self.data_type == 'saved_scan':
            self.load_btn = QPushButton("📋 Load vào quản lý")
            self.load_btn.clicked.connect(self.load_saved_scan_data)
            buttons_layout.addWidget(self.load_btn)

        buttons_layout.addStretch()

        close_btn = QPushButton("❌ Đóng")
        close_btn.clicked.connect(self.accept)
        buttons_layout.addWidget(close_btn)

        layout.addLayout(buttons_layout)

    def load_data(self):
        """Load và hiển thị dữ liệu chi tiết"""
        try:
            if self.data_type == 'saved_scan':
                self.load_saved_scan_details()
            else:
                self.load_folder_scan_details()

        except Exception as e:
            self.details_text.setPlainText(f"Lỗi hiển thị chi tiết: {str(e)}")

    def load_saved_scan_details(self):
        """Hiển thị chi tiết saved scan"""
        try:
            import json

            details_html = "<h3>📦 Thông tin Saved Scan</h3>"
            details_html += "<table border='1' cellpadding='5' cellspacing='0' style='border-collapse: collapse; width: 100%;'>"

            # Basic info
            details_html += f"<tr><td style='font-weight: bold; background-color: #e3f2fd;'>Tên</td><td>{self.data.get('name', 'N/A')}</td></tr>"
            details_html += f"<tr><td style='font-weight: bold; background-color: #e3f2fd;'>Mô tả</td><td>{self.data.get('description', 'N/A')}</td></tr>"
            details_html += f"<tr><td style='font-weight: bold; background-color: #e3f2fd;'>Số lượng folder</td><td>{self.data.get('folder_count', 0)}</td></tr>"
            details_html += f"<tr><td style='font-weight: bold; background-color: #e3f2fd;'>Ngày tạo</td><td>{self.data.get('created_at', 'N/A')}</td></tr>"

            details_html += "</table>"

            # Folders data preview
            data_json = self.data.get('data', '[]')
            try:
                if isinstance(data_json, str):
                    folders_data = json.loads(data_json)
                else:
                    folders_data = data_json

                details_html += f"<h4>📁 Danh sách Folders ({len(folders_data)} items)</h4>"
                details_html += "<table border='1' cellpadding='3' cellspacing='0' style='border-collapse: collapse; width: 100%; font-size: 12px;'>"
                details_html += "<tr style='background-color: #f5f5f5;'><th>Tên</th><th>Đường dẫn</th><th>Số ảnh</th><th>Trạng thái</th></tr>"

                for i, folder in enumerate(folders_data[:10]):  # Hiển thị tối đa 10 folders
                    name = folder.get('data_name') or folder.get('original_title', 'N/A')
                    path = folder.get('path', 'N/A')
                    if len(path) > 50:
                        path = path[:50] + "..."
                    image_count = folder.get('image_count', 0)
                    status = folder.get('status', 'N/A')

                    details_html += f"<tr><td>{name}</td><td>{path}</td><td>{image_count}</td><td>{status}</td></tr>"

                if len(folders_data) > 10:
                    details_html += f"<tr><td colspan='4' style='text-align: center; font-style: italic;'>... và {len(folders_data) - 10} folders khác</td></tr>"

                details_html += "</table>"

            except Exception as e:
                details_html += f"<p style='color: red;'>Lỗi hiển thị folders data: {str(e)}</p>"

            self.details_text.setHtml(details_html)

        except Exception as e:
            self.details_text.setPlainText(f"Lỗi hiển thị saved scan: {str(e)}")

    def load_folder_scan_details(self):
        """Hiển thị chi tiết folder scan"""
        try:
            details_html = "<h3>📁 Thông tin Folder Scan</h3>"
            details_html += "<table border='1' cellpadding='5' cellspacing='0' style='border-collapse: collapse; width: 100%;'>"

            for key, value in self.data.items():
                if key in ['data', 'scan_results', 'metadata']:
                    # Format JSON data
                    if isinstance(value, (dict, list)):
                        import json
                        value = json.dumps(value, indent=2, ensure_ascii=False)

                details_html += f"<tr><td style='font-weight: bold; background-color: #f0f0f0;'>{key}</td><td>{value}</td></tr>"

            details_html += "</table>"
            self.details_text.setHtml(details_html)

        except Exception as e:
            self.details_text.setPlainText(f"Lỗi hiển thị folder scan: {str(e)}")

    def load_saved_scan_data(self):
        """Load saved scan data vào database"""
        try:
            # Implement logic để load saved scan data vào current folder scans
            QMessageBox.information(self, "Thông báo", "Chức năng load saved scan data sẽ được triển khai sau!")

        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Không thể load saved scan data: {str(e)}")