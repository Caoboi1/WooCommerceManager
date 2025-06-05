"""
Site Manager Tab - Quản lý các site WooCommerce

COMPONENT OVERVIEW:
------------------
Tab quản lý thông tin các site WooCommerce. Cho phép thêm, sửa, xóa, test kết nối
và import/export danh sách sites.

FEATURES:
---------
- CRUD operations cho WooCommerce sites
- Test kết nối API với threading
- Import/Export CSV format
- Real-time validation
- Detail view panel
- Search và filter functionality

UI COMPONENTS:
--------------
- QTableWidget: Hiển thị danh sách sites
- QPushButton: Actions (Add, Edit, Delete, Test, Refresh)
- QGroupBox: Detail panel hiển thị thông tin site được chọn
- QFormLayout: Form layout cho detail view
- QLineEdit, QTextEdit: Input fields

THREADING:
----------
- TestConnectionWorker: Background thread để test API connection
- Tránh blocking UI khi test kết nối API

DATABASE OPERATIONS:
-------------------
- get_all_sites(): Lấy tất cả sites từ database
- create_site(): Tạo site mới
- update_site(): Cập nhật thông tin site
- delete_site(): Xóa site khỏi database

SIGNALS:
--------
- status_message(str): Gửi thông báo lên main window
- progress_started(): Bắt đầu progress indicator
- progress_finished(): Kết thúc progress indicator
"""

import logging
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
    QTableWidget, QTableWidgetItem, QHeaderView,
    QGroupBox, QFormLayout, QLineEdit, QTextEdit,
    QMessageBox, QFileDialog, QInputDialog, QCheckBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread, pyqtSlot
from PyQt6.QtGui import QFont

from .woocommerce_api import WooCommerceAPI
from .models import Site
from .dialogs import SiteDialog
import csv

class TestConnectionWorker(QThread):
    """Worker thread để test kết nối API"""
    result_ready = pyqtSignal(bool, str)

    def __init__(self, site):
        super().__init__()
        self.site = site

    def run(self):
        try:
            api = WooCommerceAPI(self.site)
            success, message = api.test_connection()
            self.result_ready.emit(success, message)
        except Exception as e:
            self.result_ready.emit(False, str(e))

class SiteManagerTab(QWidget):
    """Tab quản lý các site WooCommerce"""

    # Signals
    status_message = pyqtSignal(str)
    progress_started = pyqtSignal()
    progress_finished = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.db_manager = None
        self.sites = []

        self.init_ui()
        # Load sites sẽ được gọi sau khi db_manager được set

    def set_db_manager(self, db_manager):
        """Set database manager và load dữ liệu"""
        self.db_manager = db_manager
        self.load_sites()

    def init_ui(self):
        """Khởi tạo giao diện"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        # Tiêu đề
        title_label = QWidget()
        title_layout = QHBoxLayout(title_label)
        title_layout.setContentsMargins(0, 0, 0, 0)

        # Buttons panel
        buttons_layout = QHBoxLayout()

        self.add_btn = QPushButton("➕ Thêm Site")
        self.add_btn.clicked.connect(self.add_site)
        buttons_layout.addWidget(self.add_btn)

        self.edit_btn = QPushButton("✏️ Sửa")
        self.edit_btn.clicked.connect(self.edit_site)
        self.edit_btn.setEnabled(False)
        buttons_layout.addWidget(self.edit_btn)

        self.delete_btn = QPushButton("🗑️ Xóa")
        self.delete_btn.clicked.connect(self.delete_site)
        self.delete_btn.setEnabled(False)
        buttons_layout.addWidget(self.delete_btn)

        self.test_btn = QPushButton("🔌 Test Kết nối")
        self.test_btn.clicked.connect(self.test_connection)
        self.test_btn.setEnabled(False)
        buttons_layout.addWidget(self.test_btn)

        buttons_layout.addStretch()

        self.refresh_btn = QPushButton("🔄 Làm mới")
        self.refresh_btn.clicked.connect(self.refresh_data)
        buttons_layout.addWidget(self.refresh_btn)

        layout.addLayout(buttons_layout)

        # Table widget
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "ID", "Tên Site", "URL", "Consumer Key", "Status", "Ghi chú"
        ])

        # Configure table columns với responsive sizing
        header = self.table.horizontalHeader()
        
        # Thiết lập resize mode cho từng cột để tối ưu co dãn
        resize_modes = [
            QHeaderView.ResizeMode.Fixed,        # ID - cố định
            QHeaderView.ResizeMode.Stretch,      # Tên Site - co dãn chính
            QHeaderView.ResizeMode.Stretch,      # URL - co dãn chính  
            QHeaderView.ResizeMode.ResizeToContents,  # Consumer Key - theo nội dung
            QHeaderView.ResizeMode.Fixed,        # Status - cố định
            QHeaderView.ResizeMode.Stretch       # Ghi chú - co dãn
        ]
        
        # Áp dụng resize mode cho từng cột
        for col, mode in enumerate(resize_modes):
            if col < self.table.columnCount():
                header.setSectionResizeMode(col, mode)

        # Thiết lập kích thước cố định cho các cột Fixed
        self.table.setColumnWidth(0, 60)   # ID
        self.table.setColumnWidth(4, 100)  # Status

        # Cấu hình header responsive
        header.setStretchLastSection(True)
        header.setSectionsMovable(True)
        header.setSectionsClickable(True)
        header.setMinimumSectionSize(50)
        header.setDefaultSectionSize(150)

        # Thiết lập table properties
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)

        # Connect selection change
        self.table.itemSelectionChanged.connect(self.on_selection_changed)

        layout.addWidget(self.table)

        # Site details group
        details_group = QGroupBox("Thông tin chi tiết Site")
        details_layout = QFormLayout(details_group)

        self.name_edit = QLineEdit()
        self.name_edit.setReadOnly(True)
        details_layout.addRow("Tên Site:", self.name_edit)

        self.url_edit = QLineEdit()
        self.url_edit.setReadOnly(True)
        details_layout.addRow("URL:", self.url_edit)

        self.key_edit = QLineEdit()
        self.key_edit.setReadOnly(True)
        details_layout.addRow("Consumer Key:", self.key_edit)

        self.secret_edit = QLineEdit()
        self.secret_edit.setReadOnly(True)
        self.secret_edit.setEchoMode(QLineEdit.EchoMode.Password)
        details_layout.addRow("Consumer Secret:", self.secret_edit)

        self.notes_edit = QTextEdit()
        self.notes_edit.setReadOnly(True)
        self.notes_edit.setMaximumHeight(60)
        details_layout.addRow("Ghi chú:", self.notes_edit)

        layout.addWidget(details_group)

    def load_sites(self):
        """Tải danh sách sites từ database"""
        try:
            self.sites = self.db_manager.get_all_sites()
            self.update_table()
            self.status_message.emit(f"Đã tải {len(self.sites)} site(s)")
        except Exception as e:
            self.logger.error(f"Lỗi khi tải sites: {str(e)}")
            QMessageBox.critical(self, "Lỗi", f"Không thể tải danh sách sites:\n{str(e)}")

    def update_table(self):
        """Cập nhật bảng hiển thị"""
        self.table.setRowCount(len(self.sites))

        for row, site in enumerate(self.sites):
            # ID
            id_item = QTableWidgetItem(str(site.id) if site.id else "")
            id_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 0, id_item)

            # Tên Site
            name_item = QTableWidgetItem(site.name or "")
            name_item.setFont(QFont("Arial", 10, QFont.Weight.Bold))
            self.table.setItem(row, 1, name_item)

            # URL
            url_item = QTableWidgetItem(site.url or "")
            self.table.setItem(row, 2, url_item)

            # Consumer Key (hiển thị một phần)
            key_display = site.consumer_key[:8] + "..." if site.consumer_key and len(site.consumer_key) > 8 else site.consumer_key
            key_item = QTableWidgetItem(key_display or "")
            self.table.setItem(row, 3, key_item)

            # Status
            status_item = QTableWidgetItem("✅ Hoạt động" if site.is_active else "❌ Không hoạt động")
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 4, status_item)

            # Ghi chú
            notes_item = QTableWidgetItem(site.notes or "")
            self.table.setItem(row, 5, notes_item)

    def on_selection_changed(self):
        """Xử lý khi chọn site khác"""
        current_row = self.table.currentRow()
        has_selection = current_row >= 0

        # Enable/disable buttons
        self.edit_btn.setEnabled(has_selection)
        self.delete_btn.setEnabled(has_selection)
        self.test_btn.setEnabled(has_selection)

        if has_selection and current_row < len(self.sites):
            site = self.sites[current_row]
            self.show_site_details(site)
        else:
            self.clear_site_details()

    def show_site_details(self, site):
        """Hiển thị thông tin chi tiết site"""
        self.name_edit.setText(site.name or "")
        self.url_edit.setText(site.url or "")
        self.key_edit.setText(site.consumer_key or "")
        self.secret_edit.setText(site.consumer_secret or "")
        self.notes_edit.setPlainText(site.notes or "")

    def clear_site_details(self):
        """Xóa thông tin chi tiết"""
        self.name_edit.clear()
        self.url_edit.clear()
        self.key_edit.clear()
        self.secret_edit.clear()
        self.notes_edit.clear()

    def add_site(self):
        """Thêm site mới"""
        dialog = SiteDialog(self)
        if dialog.exec() == SiteDialog.DialogCode.Accepted:
            site_data = dialog.get_site_data()
            try:
                site_id = self.db_manager.create_site(site_data)
                self.status_message.emit("Đã thêm site mới thành công")
                self.load_sites()
            except Exception as e:
                self.logger.error(f"Lỗi khi thêm site: {str(e)}")
                QMessageBox.critical(self, "Lỗi", f"Không thể thêm site:\n{str(e)}")

    def edit_site(self):
        """Sửa site được chọn"""
        current_row = self.table.currentRow()
        if current_row < 0 or current_row >= len(self.sites):
            return

        site = self.sites[current_row]
        dialog = SiteDialog(self, site)
        if dialog.exec() == SiteDialog.DialogCode.Accepted:
            site_data = dialog.get_site_data()
            try:
                self.db_manager.update_site(site.id, site_data)
                self.status_message.emit("Đã cập nhật site thành công")
                self.load_sites()
            except Exception as e:
                self.logger.error(f"Lỗi khi cập nhật site: {str(e)}")
                QMessageBox.critical(self, "Lỗi", f"Không thể cập nhật site:\n{str(e)}")

    def delete_site(self):
        """Xóa site được chọn"""
        current_row = self.table.currentRow()
        if current_row < 0 or current_row >= len(self.sites):
            return

        site = self.sites[current_row]
        reply = QMessageBox.question(
            self, "Xác nhận xóa",
            f"Bạn có chắc chắn muốn xóa site '{site.name}'?\n"
            "Hành động này không thể hoàn tác.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                self.db_manager.delete_site(site.id)
                self.status_message.emit("Đã xóa site thành công")
                self.load_sites()
            except Exception as e:
                self.logger.error(f"Lỗi khi xóa site: {str(e)}")
                QMessageBox.critical(self, "Lỗi", f"Không thể xóa site:\n{str(e)}")

    def test_connection(self):
        """Test kết nối với site được chọn"""
        current_row = self.table.currentRow()
        if current_row < 0 or current_row >= len(self.sites):
            return

        site = self.sites[current_row]

        # Disable button và hiển thị progress
        self.test_btn.setEnabled(False)
        self.test_btn.setText("🔌 Đang test...")
        self.progress_started.emit()
        self.status_message.emit(f"Đang test kết nối tới {site.name}...")

        # Tạo worker thread
        self.worker = TestConnectionWorker(site)
        self.worker.result_ready.connect(self.on_test_result)
        self.worker.start()

    @pyqtSlot(bool, str)
    def on_test_result(self, success, message):
        """Xử lý kết quả test kết nối"""
        self.progress_finished.emit()
        self.test_btn.setEnabled(True)
        self.test_btn.setText("🔌 Test Kết nối")

        if success:
            QMessageBox.information(self, "Kết nối thành công", 
                                  f"✅ Kết nối thành công!\n\n{message}")
            self.status_message.emit("Kết nối thành công")
        else:
            QMessageBox.warning(self, "Kết nối thất bại", 
                              f"❌ Kết nối thất bại!\n\n{message}")
            self.status_message.emit("Kết nối thất bại")

    def refresh_data(self):
        """Làm mới dữ liệu"""
        self.load_sites()

    def export_csv(self):
        """Export danh sách sites ra CSV"""
        if not self.sites:
            QMessageBox.information(self, "Thông báo", "Không có dữ liệu để export")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Sites", "sites.csv", "CSV Files (*.csv)"
        )

        if file_path:
            try:
                with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(['Tên Site', 'URL', 'Consumer Key', 'Consumer Secret', 'Hoạt động', 'Ghi chú'])

                    for site in self.sites:
                        writer.writerow([
                            site.name,
                            site.url,
                            site.consumer_key,
                            site.consumer_secret,
                            'Có' if site.is_active else 'Không',
                            site.notes
                        ])

                QMessageBox.information(self, "Thành công", f"Đã export {len(self.sites)} site(s) ra file {file_path}")
                self.status_message.emit(f"Đã export {len(self.sites)} site(s)")

            except Exception as e:
                self.logger.error(f"Lỗi khi export CSV: {str(e)}")
                QMessageBox.critical(self, "Lỗi", f"Không thể export file:\n{str(e)}")

    def import_csv(self):
        """Import sites từ CSV"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Import Sites", "", "CSV Files (*.csv)"
        )

        if file_path:
            try:
                imported_count = 0
                with open(file_path, 'r', encoding='utf-8') as csvfile:
                    reader = csv.DictReader(csvfile)

                    for row in reader:
                        site_data = {
                            'name': row.get('Tên Site', ''),
                            'url': row.get('URL', ''),
                            'consumer_key': row.get('Consumer Key', ''),
                            'consumer_secret': row.get('Consumer Secret', ''),
                            'is_active': row.get('Hoạt động', '').lower() in ['có', 'yes', 'true', '1'],
                            'notes': row.get('Ghi chú', '')
                        }

                        if site_data['name'] and site_data['url']:
                            self.db_manager.create_site(site_data)
                            imported_count += 1

                self.load_sites()
                QMessageBox.information(self, "Thành công", f"Đã import {imported_count} site(s)")
                self.status_message.emit(f"Đã import {imported_count} site(s)")

            except Exception as e:
                self.logger.error(f"Lỗi khi import CSV: {str(e)}")
                QMessageBox.critical(self, "Lỗi", f"Không thể import file:\n{str(e)}")