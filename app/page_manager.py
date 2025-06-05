"""
Page Manager Tab - Quản lý trang từ các site WooCommerce/WordPress

COMPONENT OVERVIEW:
------------------
Tab quản lý pages từ các site WordPress/WooCommerce.
Cho phép xem, thêm, sửa, xóa và đồng bộ pages từ các sites.

FEATURES:
---------
- Đồng bộ pages từ WordPress REST API
- CRUD operations cho pages
- Tìm kiếm và lọc pages
- Hiển thị thông tin chi tiết pages
- Export/Import pages

API ENDPOINTS:
--------------
- /wp-json/wp/v2/pages: Lấy danh sách pages
- /wp-json/wp/v2/pages/{id}: CRUD operations cho page cụ thể

DATABASE SCHEMA:
---------------
pages table:
- id: Primary key
- site_id: Foreign key to sites table
- wp_page_id: WordPress page ID
- title: Page title
- content: Page content
- excerpt: Page excerpt
- status: Page status (publish, draft, private)
- slug: Page slug
- parent_id: Parent page ID
- menu_order: Menu order
- featured_media: Featured media ID
- author: Author ID
- last_sync: Last sync timestamp
- created_at, updated_at: Timestamps
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QMessageBox, QHeaderView, QComboBox, QLineEdit,
    QLabel, QGroupBox, QSplitter, QTextEdit, QProgressBar,
    QFrame, QApplication, QDialog, QSpinBox, QScrollArea
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QIcon

from app.models import Site
from app.database import DatabaseManager 
from app.woocommerce_api import WooCommerceAPI
from app.page_dialog import PageDialog
from app.dialogs import AnimatedProgressDialog


class PageSyncWorker(QThread):
    """Worker thread để đồng bộ pages"""

    progress_updated = pyqtSignal(int, str)  # progress value, status message
    finished = pyqtSignal(bool, str)  # success, message
    page_synced = pyqtSignal(dict)  # page data

    def __init__(self, site: Site, specific_page_id: int = None):
        super().__init__()
        self.site = site
        self.specific_page_id = specific_page_id  # ID của trang cụ thể cần sync
        self.db = DatabaseManager()
        self.logger = logging.getLogger(__name__)

    def run(self):
        """Thực hiện đồng bộ pages"""
        try:
            self.progress_updated.emit(10, f"Kết nối đến {self.site.name}...")

            # Tạo API client
            api = WooCommerceAPI(self.site)

            self.progress_updated.emit(20, "Kiểm tra kết nối...")

            # Test connection
            success, message = api.test_connection()
            if not success:
                self.finished.emit(False, f"Không thể kết nối đến site: {message}")
                return

            if self.specific_page_id:
                # Đồng bộ trang cụ thể
                self.progress_updated.emit(30, f"Lấy thông tin page ID {self.specific_page_id}...")

                # Lấy trang cụ thể từ WordPress
                page = api.get_page_by_id(self.specific_page_id)

                if not page:
                    self.finished.emit(False, f"Không thể lấy dữ liệu page ID {self.specific_page_id} từ WordPress")
                    return

                self.progress_updated.emit(70, "Cập nhật thông tin page...")

                # Cập nhật trang cụ thể trong database
                self.update_single_page_in_db(page)

                self.progress_updated.emit(100, "Hoàn thành!")
                self.finished.emit(True, f"Đã đồng bộ page '{page.get('title', {}).get('rendered', 'N/A')}' thành công")

            else:
                self.progress_updated.emit(40, "Lấy danh sách pages...")

                # Lấy pages từ WordPress API
                pages = api.get_pages()
                if not pages:
                    self.finished.emit(False, "Không lấy được pages từ API")
                    return

                self.progress_updated.emit(60, f"Đồng bộ {len(pages)} pages...")

                # Lưu vào database
                if self.site.id is not None:
                    self.db.save_pages_from_api(self.site.id, pages)

                self.progress_updated.emit(80, "Cập nhật thông tin...")

                # Emit từng page để cập nhật UI
                for page_data in pages:
                    self.page_synced.emit(page_data)

                self.progress_updated.emit(100, "Hoàn thành!")
                self.finished.emit(True, f"Đã đồng bộ {len(pages)} pages thành công")

        except Exception as e:
            self.logger.error(f"Lỗi đồng bộ pages: {str(e)}")
            self.finished.emit(False, f"Lỗi đồng bộ pages: {str(e)}")

    def update_single_page_in_db(self, page: Dict):
        """Cập nhật một trang cụ thể trong database"""
        try:
            title = page.get('title', '')
            if isinstance(title, dict):
                title = title.get('rendered', '')

            content = page.get('content', '')
            if isinstance(content, dict):
                content = content.get('rendered', '')

            excerpt = page.get('excerpt', '')
            if isinstance(excerpt, dict):
                excerpt = excerpt.get('rendered', '')

            # Kiểm tra xem page đã tồn tại trong database chưa
            with self.db.get_connection() as conn:
                existing_page = conn.execute("""
                    SELECT id FROM pages 
                    WHERE site_id = ? AND wp_page_id = ?
                """, (self.site.id, page.get('id', 0))).fetchone()

                if existing_page:
                    # Cập nhật page có sẵn
                    conn.execute("""
                        UPDATE pages 
                        SET title = ?, slug = ?, content = ?, excerpt = ?, status = ?,
                            parent_id = ?, menu_order = ?, featured_media = ?, author = ?,
                            last_sync = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE site_id = ? AND wp_page_id = ?
                    """, (
                        title,
                        page.get('slug', ''),
                        content,
                        excerpt,
                        page.get('status', 'publish'),
                        page.get('parent', 0),
                        page.get('menu_order', 0),
                        page.get('featured_media', 0),
                        page.get('author', 0),
                        datetime.now().isoformat(),
                        self.site.id,
                        page.get('id', 0)
                    ))
                else:
                    # Tạo page mới
                    conn.execute("""
                        INSERT INTO pages 
                        (site_id, wp_page_id, title, slug, content, excerpt, status, 
                         parent_id, menu_order, featured_media, author, last_sync, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """, (
                        self.site.id,
                        page.get('id', 0),
                        title,
                        page.get('slug', ''),
                        content,
                        excerpt,
                        page.get('status', 'publish'),
                        page.get('parent', 0),
                        page.get('menu_order', 0),
                        page.get('featured_media', 0),
                        page.get('author', 0),
                        datetime.now().isoformat()
                    ))

                conn.commit()
                self.logger.info(f"Updated page '{title}' in database")

        except Exception as e:
            self.logger.error(f"Error updating single page in database: {str(e)}")
            raise


class PageManagerTab(QWidget):
    """Tab quản lý pages"""

    def __init__(self):
        super().__init__()
        self.db = DatabaseManager()
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)  # Giảm debug logging
        self.sync_worker = None
        self.progress_dialog = None

        self.init_ui()
        self.load_sites()
        self.load_pages()

    def init_ui(self):
        """Khởi tạo giao diện"""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)

        # Header với controls
        header_layout = QHBoxLayout()

        # Site selection
        site_label = QLabel("Site:")
        site_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        header_layout.addWidget(site_label)

        self.site_combo = QComboBox()
        self.site_combo.setMinimumWidth(200)
        # Sử dụng currentIndexChanged thay vì currentTextChanged để lấy đúng data
        self.site_combo.currentIndexChanged.connect(self.filter_pages)
        header_layout.addWidget(self.site_combo)

        header_layout.addSpacing(20)

        # Search
        search_label = QLabel("Tìm kiếm:")
        search_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        header_layout.addWidget(search_label)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Nhập tên page hoặc slug...")
        self.search_edit.setMinimumWidth(250)
        self.search_edit.textChanged.connect(self.filter_pages)
        header_layout.addWidget(self.search_edit)

        header_layout.addStretch()

        # Buttons
        self.sync_all_btn = QPushButton("🔄 Đồng bộ trang")
        self.sync_all_btn.clicked.connect(self.sync_all_pages)
        self.sync_all_btn.setToolTip("Đồng bộ trang từ site được chọn")
        header_layout.addWidget(self.sync_all_btn)

        self.sync_selected_btn = QPushButton("🔄 Đồng bộ Trang chọn")
        self.sync_selected_btn.clicked.connect(self.sync_selected_page)
        self.sync_selected_btn.setEnabled(False)
        header_layout.addWidget(self.sync_selected_btn)

        self.add_btn = QPushButton("➕ Thêm Page")
        self.add_btn.clicked.connect(self.add_page)
        header_layout.addWidget(self.add_btn)

        self.edit_btn = QPushButton("✏️ Sửa")
        self.edit_btn.clicked.connect(self.edit_page)
        self.edit_btn.setEnabled(False)
        header_layout.addWidget(self.edit_btn)

        self.delete_btn = QPushButton("🗑️ Xóa")
        self.delete_btn.clicked.connect(self.delete_page)
        self.delete_btn.setEnabled(False)
        header_layout.addWidget(self.delete_btn)

        layout.addLayout(header_layout)

        # Splitter cho table và details
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Pages table
        self.pages_table = QTableWidget()
        # Configure table columns
        columns = ["ID", "Site", "Tiêu đề", "Slug", "Trạng thái", "Tác giả", "Ngày tạo", "Ngày sửa"]
        self.pages_table.setColumnCount(len(columns))
        self.pages_table.setHorizontalHeaderLabels(columns)

        # Cấu hình responsive grid layout cho pages
        header = self.pages_table.horizontalHeader()

        # Thiết lập resize modes tối ưu cho từng cột
        resize_modes = [
            QHeaderView.ResizeMode.Fixed,             # ID - cố định
            QHeaderView.ResizeMode.ResizeToContents,  # Site - theo nội dung  
            QHeaderView.ResizeMode.Stretch,           # Tiêu đề - co dãn chính
            QHeaderView.ResizeMode.Stretch,           # Slug - co dãn
            QHeaderView.ResizeMode.Fixed,             # Trạng thái - cố định
            QHeaderView.ResizeMode.ResizeToContents,  # Tác giả - theo nội dung
            QHeaderView.ResizeMode.Fixed,             # Ngày tạo - cố định
            QHeaderView.ResizeMode.Fixed              # Ngày sửa - cố định
        ]

        # Áp dụng resize mode cho từng cột
        for col, mode in enumerate(resize_modes):
            if col < len(columns):
                header.setSectionResizeMode(col, mode)

        # Thiết lập width cố định cho các cột Fixed
        self.pages_table.setColumnWidth(0, 50)   # ID
        self.pages_table.setColumnWidth(4, 90)   # Trạng thái
        self.pages_table.setColumnWidth(6, 110)  # Ngày tạo
        self.pages_table.setColumnWidth(7, 110)  # Ngày sửa

        # Cấu hình responsive header
        header.setStretchLastSection(False)
        header.setSectionsMovable(True)
        header.setSectionsClickable(True)
        header.setMinimumSectionSize(40)
        header.setDefaultSectionSize(120)
        self.pages_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.pages_table.setAlternatingRowColors(True)
        self.pages_table.selectionModel().selectionChanged.connect(self.on_selection_changed)

        splitter.addWidget(self.pages_table)

        # Page details panel
        details_group = QGroupBox("Chi tiết Page") 
        details_layout = QVBoxLayout(details_group)

        self.details_text = QTextEdit()
        self.details_text.setReadOnly(True)
        details_layout.addWidget(self.details_text)

        splitter.addWidget(details_group)

        # Điều chỉnh tỷ lệ phân chia 
        splitter.setSizes([600, 400])  # Tăng kích thước phần details

        # Thêm style cho details_group
        details_group.setStyleSheet("""
            QGroupBox {
                border: 2px solid #c0c0c0;
                border-radius: 4px;
                margin-top: 1ex;
                padding: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)

        # Thêm QScrollArea để có thể scroll khi nội dung dài
        scroll = QScrollArea()
        scroll.setWidget(details_group)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        splitter.addWidget(scroll)

        layout.addWidget(splitter)

        # Stats panel - compact version
        stats_group = QGroupBox("Thống kê")
        stats_group.setMaximumHeight(60)  # Giới hạn chiều cao
        stats_layout = QHBoxLayout(stats_group)
        stats_layout.setContentsMargins(10, 5, 10, 5)  # Giảm margins

        self.total_label = QLabel("Tổng: 0")
        self.published_label = QLabel("Đã xuất bản: 0")
        self.draft_label = QLabel("Nháp: 0")
        self.private_label = QLabel("Riêng tư: 0")

        for label in [self.total_label, self.published_label, self.draft_label, self.private_label]:
            label.setFont(QFont("Arial", 8))  # Font nhỏ hơn
            label.setStyleSheet("color: #555; padding: 2px 8px; margin: 2px;")  # Style compact
            stats_layout.addWidget(label)

        stats_layout.addStretch()
        layout.addWidget(stats_group)

    def load_sites(self):
        """Load danh sách sites"""
        try:
            self.site_combo.clear()
            self.site_combo.addItem("Tất cả sites", None)

            sites = self.db.get_all_sites()
            for site in sites:
                self.site_combo.addItem(site.name, site.id)
                self.logger.debug(f"Added site to combo: {site.name} (ID: {site.id})")

        except Exception as e:
            self.logger.error(f"Lỗi load sites: {str(e)}")

    def load_pages(self):
        """Load danh sách pages"""
        try:
            pages = self.db.get_all_pages()
            self.display_pages(pages)
            self.update_stats(pages)

        except Exception as e:
            self.logger.error(f"Lỗi load pages: {str(e)}")

    def display_pages(self, pages: List[Dict]):
        """Hiển thị pages trong table"""
        try:
            self.pages_table.setRowCount(len(pages))

            for row, page in enumerate(pages):
                # ID
                self.pages_table.setItem(row, 0, QTableWidgetItem(str(page.get('id', ''))))

                # Site name
                site_name = page.get('site_name', '')
                self.pages_table.setItem(row, 1, QTableWidgetItem(str(site_name)))

                # Title
                title = page.get('title', '')
                if isinstance(title, dict):
                    title = title.get('rendered', '')
                self.pages_table.setItem(row, 2, QTableWidgetItem(str(title)))

                # Slug
                self.pages_table.setItem(row, 3, QTableWidgetItem(str(page.get('slug', ''))))

                # Status
                status = page.get('status', '')
                status_text = {
                    'publish': 'Đã xuất bản',
                    'draft': 'Nháp',
                    'private': 'Riêng tư',
                    'pending': 'Chờ duyệt'
                }.get(status, status)
                self.pages_table.setItem(row, 4, QTableWidgetItem(status_text))

                # Author
                author = str(page.get('author', ''))
                self.pages_table.setItem(row, 5, QTableWidgetItem(author))

                # Created date
                created = page.get('created_at', '')
                if created:
                    try:
                        if 'T' in created:
                            dt = datetime.fromisoformat(created.replace('Z', '+00:00'))
                            created = dt.strftime('%d/%m/%Y %H:%M')
                    except:
                        pass
                self.pages_table.setItem(row, 6, QTableWidgetItem(str(created)))

                # Updated date
                updated = page.get('updated_at', page.get('modified', ''))
                if updated:
                    try:
                        if 'T' in updated:
                            dt = datetime.fromisoformat(updated.replace('Z', '+00:00'))
                            updated = dt.strftime('%d/%m/%Y %H:%M')
                    except:
                        pass
                self.pages_table.setItem(row, 7, QTableWidgetItem(str(updated)))

                # Store full page data in first cell
                item = self.pages_table.item(row, 0)
                if item:
                    item.setData(Qt.ItemDataRole.UserRole, page)

        except Exception as e:
            self.logger.error(f"Lỗi hiển thị pages: {str(e)}")

    def filter_pages(self):
        """Lọc pages theo site và search"""
        try:
            site_id = self.site_combo.currentData()
            site_text = self.site_combo.currentText()
            search_term = self.search_edit.text().lower()

            # Debug logging
            self.logger.debug(f"Filtering pages - Site ID: {site_id}, Site Text: {site_text}, Search: {search_term}")

            # Kiểm tra điều kiện lọc site - chỉ lọc khi chọn site cụ thể
            if site_id and site_id != 0 and site_text != "Tất cả sites":  
                pages = self.db.get_pages_by_site(site_id)
                self.logger.debug(f"Found {len(pages)} pages for site_id {site_id}")
            else:
                pages = self.db.get_all_pages()
                self.logger.debug(f"Found {len(pages)} total pages")

            # Debug: Log first few pages to check data
            if pages:
                for i, page in enumerate(pages[:3]):
                    self.logger.debug(f"Page {i}: site_id={page.get('site_id')}, site_name={page.get('site_name')}, title={page.get('title')}")

            # Filter by search term
            if search_term:
                filtered_pages = []
                for page in pages:
                    title = page.get('title', '')
                    if isinstance(title, dict):
                        title = title.get('rendered', '')

                    if (search_term in str(title).lower() or 
                        search_term in str(page.get('slug', '')).lower()):
                        filtered_pages.append(page)
                pages = filtered_pages

            self.display_pages(pages)
            self.update_stats(pages)

        except Exception as e:
            self.logger.error(f"Lỗi filter pages: {str(e)}")

    def update_stats(self, pages: List[Dict]):
        """Cập nhật thống kê"""
        try:
            total = len(pages)
            published = sum(1 for p in pages if p.get('status') == 'publish')
            draft = sum(1 for p in pages if p.get('status') == 'draft')
            private = sum(1 for p in pages if p.get('status') == 'private')

            self.total_label.setText(f"Tổng: {total}")
            self.published_label.setText(f"Đã xuất bản: {published}")
            self.draft_label.setText(f"Nháp: {draft}")
            self.private_label.setText(f"Riêng tư: {private}")

        except Exception as e:
            self.logger.error(f"Lỗi update stats: {str(e)}")

    def on_selection_changed(self):
        """Xử lý khi selection thay đổi"""
        try:
            selected_rows = self.pages_table.selectionModel().selectedRows()
            has_selection = len(selected_rows) > 0

            self.edit_btn.setEnabled(has_selection)
            self.delete_btn.setEnabled(has_selection)
            self.sync_selected_btn.setEnabled(has_selection)

            if has_selection:
                row = selected_rows[0].row()
                item = self.pages_table.item(row, 0)
                if item:
                    page_data = item.data(Qt.ItemDataRole.UserRole)
                    if page_data:
                        self.show_page_details(page_data)
            else:
                self.details_text.clear()

        except Exception as e:
            self.logger.error(f"Lỗi selection changed: {str(e)}")

    def show_page_details(self, page: Dict):
        """Hiển thị chi tiết page"""
        try:
            title = page.get('title', '')
            if isinstance(title, dict):
                title = title.get('rendered', '')

            content = page.get('content', '')
            if isinstance(content, dict):
                content = content.get('rendered', '')

            excerpt = page.get('excerpt', '')
            if isinstance(excerpt, dict):
                excerpt = excerpt.get('rendered', '')

            details = f"""
        <div style="padding: 10px;">
            <h2 style="color: #2c3e50;">{title}</h2>
            <div style="margin: 10px 0; padding: 10px; background: #f8f9fa; border-radius: 4px;">
                <p><b>ID:</b> {page.get('id', 'N/A')}</p>
                <p><b>Slug:</b> {page.get('slug', 'N/A')}</p>
                <p><b>Trạng thái:</b> {page.get('status', 'N/A')}</p>
                <p><b>Thứ tự menu:</b> {page.get('menu_order', 0)}</p>
                <p><b>Tác giả:</b> {page.get('author', 'N/A')}</p>
                <p><b>Page cha:</b> {page.get('parent', 'Không có')}</p>
                <p><b>Cập nhật:</b> {page.get('updated_at', 'N/A')}</p>
            </div>
            <div style="margin-top: 20px;">
                <h3 style="color: #2c3e50;">Mô tả ngắn:</h3>
                <div style="padding: 10px; background: #fff; border: 1px solid #eee;">
                    {excerpt}
                </div>
            </div>
            <div style="margin-top: 20px;">
                <h3 style="color: #2c3e50;">Nội dung:</h3>
                <div style="padding: 10px; background: #fff; border: 1px solid #eee;">
                    {content[:500] + '...' if len(str(content)) > 500 else content}
                </div>
            </div>
        </div>
        """

            self.details_text.setHtml(details)

        except Exception as e:
            self.logger.error(f"Lỗi show page details: {str(e)}")

    def sync_all_pages(self):
        """Đồng bộ trang từ site được chọn"""
        try:
            # Lấy site được chọn
            site_id = self.site_combo.currentData()
            
            if not site_id:
                QMessageBox.warning(self, "Cảnh báo", 
                                    "Vui lòng chọn một site cụ thể để đồng bộ trang.\n\n"
                                    "Không thể đồng bộ khi chọn 'Tất cả sites'.")
                return

            site_obj = self.db.get_site_by_id(site_id)
            if not site_obj:
                QMessageBox.warning(self, "Lỗi", "Không tìm thấy thông tin site!")
                return

            # Hiển thị xác nhận
            reply = QMessageBox.question(
                self, "Xác nhận đồng bộ",
                f"Bạn có muốn đồng bộ trang từ site '{site_obj.name}' không?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self.start_sync_all(site_obj)

        except Exception as e:
            self.logger.error(f"Lỗi sync pages: {str(e)}")
            QMessageBox.critical(self, "Lỗi", f"Lỗi đồng bộ pages: {str(e)}")

    def start_sync_all(self, site: Site):
        """Bắt đầu đồng bộ tất cả pages"""
        try:
            # Tạo progress dialog
            self.progress_dialog = AnimatedProgressDialog("Đồng bộ Pages", self)
            self.progress_dialog.start_progress()
            self.progress_dialog.show()

            # Tạo worker thread
            self.sync_worker = PageSyncWorker(site)
            self.sync_worker.progress_updated.connect(self.on_sync_progress)
            self.sync_worker.finished.connect(self.on_sync_finished)
            self.sync_worker.page_synced.connect(self.on_page_synced)

            # Disable sync button
            self.sync_all_btn.setEnabled(False)
            self.sync_selected_btn.setEnabled(False)

            # Bắt đầu sync
            self.sync_worker.start()

        except Exception as e:
            self.logger.error(f"Lỗi start sync: {str(e)}")

    def on_sync_progress(self, value: int, status: str):
        """Cập nhật tiến độ sync"""
        if self.progress_dialog:
            self.progress_dialog.set_progress(value)
            self.progress_dialog.set_status(status)

    def on_sync_finished(self, success: bool, message: str):
        """Xử lý khi sync hoàn thành"""
        try:
            # Ẩn progress dialog
            if self.progress_dialog:
                self.progress_dialog.finish_progress(success, message)
                QTimer.singleShot(2000, self.progress_dialog.close)

            # Enable sync button
            self.sync_all_btn.setEnabled(True)
            # Chỉ enable sync_selected_btn nếu có selection
            selected_rows = self.pages_table.selectionModel().selectedRows()
            self.sync_selected_btn.setEnabled(len(selected_rows) > 0)

            # Hiển thị kết quả
            if success:
                QMessageBox.information(self, "Thành công", message)
                # Áp dụng lại bộ lọc thay vì load tất cả
                self.filter_pages()  
            else:
                QMessageBox.critical(self, "Lỗi", message)

            # Cleanup worker
            if self.sync_worker:
                self.sync_worker.deleteLater()
                self.sync_worker = None

        except Exception as e:
            self.logger.error(f"Lỗi sync finished: {str(e)}")

    def on_page_synced(self, page_data: Dict):
        """Xử lý khi một page được sync"""
        # Có thể cập nhật UI real-time nếu cần
        pass

    def sync_selected_page(self):
        """Đồng bộ trang được chọn từ WordPress"""
        try:
            selected_rows = self.pages_table.selectionModel().selectedRows()
            if not selected_rows:
                return

            row = selected_rows[0].row()
            item = self.pages_table.item(row, 0)
            if not item:
                return

            page_data = item.data(Qt.ItemDataRole.UserRole)
            if not page_data:
                return

            wp_page_id = page_data.get('wp_page_id')
            if not wp_page_id:
                QMessageBox.warning(self, "Cảnh báo", "Page này chưa có WordPress ID để đồng bộ")
                return

            # Lấy site được chọn
            site_id = self.site_combo.currentData()
            if not site_id:
                QMessageBox.warning(self, "Cảnh báo", "Vui lòng chọn một site để đồng bộ")
                return

            site = self.db.get_site_by_id(site_id)
            if not site:
                QMessageBox.warning(self, "Cảnh báo", "Không tìm thấy thông tin site")
                return

            self.start_sync_selected_page(site, wp_page_id, page_data.get('title', ''))

        except Exception as e:
            self.logger.error(f"Error syncing selected page: {str(e)}")
            QMessageBox.critical(self, "Lỗi", f"Không thể đồng bộ trang: {str(e)}")

    def start_sync_selected_page(self, site: Site, wp_page_id: int, page_title: str):
        """Bắt đầu đồng bộ trang được chọn"""
        try:
            # Tạo progress dialog
            self.progress_dialog = AnimatedProgressDialog("Đồng bộ Pages", self)
            self.progress_dialog.start_progress()
            self.progress_dialog.show()

            if self.sync_worker and self.sync_worker.isRunning():
                QMessageBox.warning(self, "Cảnh báo", "Đang có tiến trình đồng bộ khác")
                return

            # Disable buttons
            self.sync_all_btn.setEnabled(False)
            self.sync_selected_btn.setEnabled(False)

            # Tạo worker thread với specific page ID
            self.sync_worker = PageSyncWorker(site, specific_page_id=wp_page_id)
            self.sync_worker.progress_updated.connect(self.on_sync_progress)
            self.sync_worker.finished.connect(self.on_sync_finished)
            self.sync_worker.page_synced.connect(self.on_page_synced)

            # Bắt đầu sync
            self.sync_worker.start()

        except Exception as e:
            self.logger.error(f"Lỗi start sync selected page: {str(e)}")

    def add_page(self):
        """Thêm page mới"""
        try:
            sites = self.db.get_active_sites()
            if not sites:
                QMessageBox.warning(self, "Cảnh báo", "Không có site nào hoạt động")
                return

            pages = self.db.get_all_pages()

            dialog = PageDialog(self, sites=sites, pages=pages)
            dialog.page_saved.connect(self.on_page_saved)
            dialog.exec()

        except Exception as e:
            self.logger.error(f"Lỗi thêm page: {str(e)}")
            QMessageBox.critical(self, "Lỗi", f"Không thể thêm trang: {str(e)}")

    def on_page_saved(self, page_data: Dict):
        """Xử lý khi page được lưu từ dialog"""
        try:
            # Tạo page trên WordPress trước
            site_id = page_data['site_id']
            site = self.db.get_site_by_id(site_id)

            if not site:
                QMessageBox.warning(self, "Cảnh báo", "Không tìm thấy thông tin site")
                return

            # Chuẩn bị data cho WordPress API
            wp_page_data = {
                'title': page_data['title'],
                'content': page_data['content'],
                'excerpt': page_data['excerpt'],
                'status': page_data['status'],
                'slug': page_data['slug'],
                'parent': page_data.get('parent_id', 0),
                'menu_order': page_data.get('menu_order', 0)
            }

            # Tạo page trên WordPress
            api = WooCommerceAPI(site)
            created_page = api.create_page(wp_page_data)

            if created_page:
                # Lưu vào database local
                page_data['wp_page_id'] = created_page.get('id')
                self.db.create_page(page_data)

                QMessageBox.information(self, "Thành công", "Đã tạo trang thành công!")
                self.load_pages()
            else:
                QMessageBox.warning(self, "Cảnh báo", "Không thể tạo trang trên WordPress")

        except Exception as e:
            self.logger.error(f"Lỗi lưu page: {str(e)}")
            QMessageBox.critical(self, "Lỗi", f"Không thể lưu trang: {str(e)}")

    def edit_page(self):
        """Sửa page đã chọn"""
        try:
            selected_rows = self.pages_table.selectionModel().selectedRows()
            if not selected_rows:
                return

            row = selected_rows[0].row()
            item = self.pages_table.item(row, 0)
            if not item:
                return

            page_data = item.data(Qt.ItemDataRole.UserRole)
            if not page_data:
                return

            sites = self.db.get_active_sites()
            pages = self.db.get_all_pages()

            dialog = PageDialog(self, sites=sites, page=page_data, pages=pages)
            dialog.page_saved.connect(self.on_page_updated)
            dialog.exec()

        except Exception as e:
            self.logger.error(f"Lỗi sửa page: {str(e)}")
            QMessageBox.critical(self, "Lỗi", f"Không thể sửa trang: {str(e)}")

    def on_page_updated(self, page_data: Dict):
        """Xử lý khi page được cập nhật"""
        pass

    def delete_page(self):
        """Xóa page đã chọn"""
        try:
            selected_rows = self.pages_table.selectionModel().selectedRows()
            if not selected_rows:
                return

            row = selected_rows[0].row()
            item = self.pages_table.item(row, 0)
            if not item:
                return

            page_data = item.data(Qt.ItemDataRole.UserRole)
            if not page_data:
                return

            page_title = page_data.get('title', '')
            if isinstance(page_title, dict):
                page_title = page_title.get('rendered', '')

            reply = QMessageBox.question(
                self, 
                "Xác nhận xóa",
                f"Bạn có chắc chắn muốn xóa trang '{page_title}'?\n\n"
                "Lưu ý: Trang sẽ bị xóa cả trên WordPress và database local.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )

            if reply == QMessageBox.StandardButton.Yes:
                # Xóa page từ WordPress nếu có wp_page_id
                wp_page_id = page_data.get('wp_page_id')
                site_id = page_data.get('site_id')
                
                if wp_page_id and site_id:
                    site = self.db.get_site_by_id(site_id)
                    if site:
                        try:
                            api = WooCommerceAPI(site)
                            api.delete_page(wp_page_id)
                        except Exception as e:
                            self.logger.warning(f"Không thể xóa page từ WordPress: {str(e)}")

                # Xóa từ database local
                page_id = page_data.get('id')
                if page_id:
                    self.db.delete_page(page_id)

                QMessageBox.information(self, "Thành công", "Đã xóa trang thành công!")
                self.load_pages()

        except Exception as e:
            self.logger.error(f"Lỗi xóa page: {str(e)}")
            QMessageBox.critical(self, "Lỗi", f"Không thể xóa trang: {str(e)}")


import logging

class PageManager:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        # Định dạng logger để hiển thị đẹp hơn
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s\n%(message)s\n'
        )
        
        # Thêm handler để hiển thị log ra console
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)
        
        # Set log level
        self.logger.setLevel(logging.DEBUG)

    def filter_pages(self, site_id=None, search_text=''):
        self.logger.debug(
            f"Filtering pages:\n"
            f"Site ID: {site_id}\n"
            f"Search text: {search_text}"
        )
        # ...existing code...

    def add_site_to_combo(self, site_name, site_id):
        self.logger.debug(
            f"Added site to combo:\n"
            f"Site: {site_name}\n" 
            f"ID: {site_id}"
        )
        # ...existing code...