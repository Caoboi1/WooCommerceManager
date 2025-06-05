"""
Product Manager Tab - Quản lý sản phẩm từ các site WooCommerce
"""

import logging
import csv
import os
from typing import List, Optional
from datetime import datetime
import threading
import queue
import requests
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QLineEdit, QComboBox, QLabel, QGroupBox,
    QMessageBox, QFileDialog, QProgressDialog,
    QFormLayout, QSpinBox, QDoubleSpinBox, QTextEdit,
    QCheckBox, QSplitter, QAbstractItemView, QApplication,
    QDialog, QMenu
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread, pyqtSlot, QUrl, QThreadPool, QTimer
from PyQt6.QtGui import QFont, QPixmap, QColor, QPen, QPainter
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
from datetime import datetime
import csv
import requests

from .woocommerce_api import WooCommerceAPI
from .models import Product
from .dialogs import ProductDialog, SiteSelectionDialog, AnimatedProgressDialog


class ImageLoader(QThread):
    """Thread để tải ảnh từ URL với caching và tối ưu"""
    image_loaded = pyqtSignal(int, int, QPixmap)  # row, col, pixmap
    image_cache = {}  # Cache ảnh đã tải
    cache_access_count = {}  # Đếm số lần truy cập cache
    cache_limit = 300  # Tăng giới hạn cache

    def __init__(self, row, col, url):
        super().__init__()
        self.row = row
        self.col = col
        self.url = url

    def run(self):
        try:
            # Kiểm tra cache trước
            if self.url in ImageLoader.image_cache:
                # Cập nhật access count cho LRU
                ImageLoader.cache_access_count[
                    self.url] = ImageLoader.cache_access_count.get(
                        self.url, 0) + 1
                self.image_loaded.emit(self.row, self.col,
                                       ImageLoader.image_cache[self.url])
                return

            # Tối ưu request với headers và connection pooling
            headers = {
                'User-Agent':
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive'
            }

            response = requests.get(self.url,
                                    timeout=10,
                                    stream=True,
                                    headers=headers)
            if response.status_code == 200:
                # Tăng timeout và cải thiện việc tải ảnh
                content = b''
                content_length = int(response.headers.get('content-length', 0))

                # Kiểm tra kích thước trước khi tải
                if content_length > 3 * 1024 * 1024:  # 3MB limit
                    raise Exception("Image too large")

                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:  # Filter out keep-alive chunks
                        content += chunk
                        if len(content) > 3 * 1024 * 1024:  # 3MB limit
                            break

                # Validate minimum content size
                if len(content) < 100:  # Too small to be a valid image
                    raise Exception("Image content too small")

                # Validate image header (basic check)
                if not (content.startswith(b'\x89PNG') or  # PNG
                        content.startswith(b'\xff\xd8\xff') or  # JPEG
                        content.startswith(b'GIF8') or  # GIF
                        content.startswith(b'RIFF')):  # WebP
                    raise Exception("Invalid image format")

                pixmap = QPixmap()
                # Thử load với error handling tốt hơn
                success = False
                try:
                    success = pixmap.loadFromData(content)
                except Exception as load_error:
                    print(f"PyQt pixmap load error: {load_error}")
                    success = False

                if success and not pixmap.isNull():
                    # Scale ảnh với tối ưu chất lượng và error handling
                    try:
                        scaled_pixmap = pixmap.scaled(
                            70, 70, Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation)

                        # Kiểm tra scaled pixmap có hợp lệ không
                        if scaled_pixmap.isNull():
                            raise Exception("Failed to scale image")

                        # Quản lý cache size với LRU (Least Recently Used)
                        if len(ImageLoader.image_cache) >= self.cache_limit:
                            # Sắp xếp theo access count và xóa 30% ít được sử dụng nhất
                            sorted_cache = sorted(
                                ImageLoader.cache_access_count.items(),
                                key=lambda x: x[1])
                            keys_to_remove = [
                                item[0] for item in
                                sorted_cache[:int(self.cache_limit * 0.3)]
                            ]

                            for key in keys_to_remove:
                                if key in ImageLoader.image_cache:
                                    del ImageLoader.image_cache[key]
                                if key in ImageLoader.cache_access_count:
                                    del ImageLoader.cache_access_count[key]

                        # Lưu vào cache
                        ImageLoader.image_cache[self.url] = scaled_pixmap
                        ImageLoader.cache_access_count[self.url] = 1

                        self.image_loaded.emit(self.row, self.col,
                                               scaled_pixmap)
                        return  # Success, exit early

                    except Exception as scale_error:
                        print(f"Image scaling error: {scale_error}")
                        # Fall through to create placeholder
                else:
                    raise Exception("Failed to load pixmap from data")
        except Exception as e:
            # Log lỗi để debug
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed toload image from {self.url}: {str(e)}")

            # Tạo placeholder với icon lỗi
            placeholder = QPixmap(70, 70)
            placeholder.fill(Qt.GlobalColor.lightGray)

            # Thêm "X" để hiển thị lỗi
            from PyQt6.QtGui import QPainter, QPen, QColor
            painter = QPainter(placeholder)
            painter.setPen(QPen(QColor(255, 0, 0), 2))  # Red pen
            painter.drawLine(10, 10, 60, 60)
            painter.drawLine(60, 10, 10, 60)
            painter.end()

            self.image_loaded.emit(self.row, self.col, placeholder)

    @classmethod
    def cleanup_cache(cls):
        """Dọn dẹp cache khi quá giới hạn"""
        if len(cls.image_cache) >= cls.cache_limit:
            # Sắp xếp theo access count và xóa 30% ít được sử dụng nhất
            sorted_cache = sorted(
                cls.cache_access_count.items(),
                key=lambda x: x[1])
            keys_to_remove = [
                item[0] for item in
                sorted_cache[:int(cls.cache_limit * 0.3)]
            ]

            for key in keys_to_remove:
                if key in cls.image_cache:
                    del cls.image_cache[key]
                if key in cls.cache_access_count:
                    del cls.cache_access_count[key]

    @classmethod
    def save_persistent_cache(cls):
        """Lưu cache vào file (placeholder method)"""
        # Có thể implement lưu cache vào file nếu cần
        pass


class SyncProductsWorker(QThread):
    """Worker thread để đồng bộ sản phẩm từ các site"""
    progress_update = pyqtSignal(int, str)
    products_synced = pyqtSignal(list)
    error_occurred = pyqtSignal(str)

    def __init__(self, db_manager, sites=None):
        super().__init__()
        self.db_manager = db_manager
        self.sites = sites  # Danh sách sites để đồng bộ

    def get_product_view_count(self, product):
        """Lấy số lượt xem thực từ dữ liệu sản phẩm WooCommerce"""
        view_count = 0

        # Kiểm tra trong meta_data
        meta_data = product.get('meta_data', [])
        for meta in meta_data:
            key = meta.get('key', '')
            if key in ['_post_views_count', 'views', 'view_count', 'total_views']:
                try:
                    view_count = int(meta.get('value', 0))
                    if view_count > 0:
                        return view_count
                except (ValueError, TypeError):
                    continue

        # Fallback: ước tính từ rating_count
        rating_count = product.get('rating_count', 0)
        if rating_count > 0:
            # Ước tính 15-20 lượt xem cho mỗi đánh giá
            view_count = rating_count * 15

        return view_count

    def run(self):
        try:
            all_products = []
            # Sử dụng sites được truyền vào hoặc lấy tất cả sites active
            sites = self.sites if self.sites else self.db_manager.get_active_sites()

            for i, site in enumerate(sites):
                self.progress_update.emit(i * 100 // len(sites),
                                          f"Đang đồng bộ từ {site.name}...")

                api = WooCommerceAPI(site)
                products = api.get_all_products()

                for product in products:
                    # Lưu hoặc cập nhật sản phẩm trong database
                    product_data = {
                        'site_id':
                        site.id,
                        'wc_product_id':
                        product.get('id'),
                        'name':
                        product.get('name'),
                        'sku':
                        product.get('sku'),
                        'price':
                        float(product.get('price', 0)),
                        'regular_price':
                        float(product.get('regular_price', 0)),
                        'sale_price':
                        float(product.get('sale_price', 0))
                        if product.get('sale_price') else None,
                        'stock_quantity':
                        product.get('stock_quantity'),
                        'status':
                        product.get('status'),
                        'description':
                        product.get('description'),
                        'short_description':
                        product.get('short_description'),
                        'categories':
                        ','.join([
                            cat['name']
                            for cat in product.get('categories', [])
                        ]),
                        'tags':
                        ','.join(
                            [tag['name'] for tag in product.get('tags', [])]),
                        'images':
                        ','.join(
                            [img['src'] for img in product.get('images', [])]),
                        'view_count':
                        self.get_product_view_count(product),
                        'order_count':
                        int(product.get('total_sales', 0) or 0),
                        'last_sync':
                        datetime.now().isoformat()
                    }

                    # Kiểm tra xem sản phẩm đã tồn tại chưa
                    existing = self.db_manager.get_product_by_site_and_wc_id(
                        site.id, product.get('id'))
                    if existing:
                        self.db_manager.update_product(existing.id,
                                                       product_data)
                    else:
                        self.db_manager.create_product(product_data)

                    all_products.append(product_data)

            self.progress_update.emit(100, "Hoàn thành đồng bộ")
            self.products_synced.emit(all_products)

        except Exception as e:
            self.error_occurred.emit(str(e))


class ProductManagerTab(QWidget):
    """Tab quản lý sản phẩm"""

    # Signals
    status_message = pyqtSignal(str)
    progress_started = pyqtSignal()
    progress_finished = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.db_manager = None
        self.products = []
        self.sites = []
        self.image_loaders = []  # Để quản lý các image loader threads
        self.pending_image_loads = []  # Danh sách chờ tải ảnh
        self.image_queue_loader = None  # Image queue loader thread

        # Check if we're in minimal mode (Windows safe mode)
        self.minimal_mode = os.environ.get('WOOCOMMERCE_MINIMAL_MODE') == '1'

        # Initialize image loader only if not in minimal mode
        # if not self.minimal_mode: # This condition is removed based on the intention.
        #     self.image_loader = ImageLoader()
        #     self.setup_image_loader()
        # else:
        #     self.image_loader = None

        self.init_ui()
        # load_data() sẽ được gọi sau khi db_manager được gán

        # Thêm menu cache management
        self.add_cache_management()

    def init_ui(self):
        """Khởi tạo giao diện"""
        # Main layout without splitter
        main_layout = QVBoxLayout()
        self.setLayout(main_layout)

        # Product list panel
        left_layout = main_layout

        # Search and filter section
        filter_group = QGroupBox("Tìm kiếm và lọc")
        filter_layout = QFormLayout(filter_group)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText(
            "Tìm theo tên sản phẩm hoặc SKU...")
        self.search_edit.textChanged.connect(self.filter_products)
        filter_layout.addRow("Tìm kiếm:", self.search_edit)

        self.site_filter = QComboBox()
        self.site_filter.addItem("Tất cả sites")
        self.site_filter.currentTextChanged.connect(self.filter_products)
        filter_layout.addRow("Site:", self.site_filter)

        self.status_filter = QComboBox()
        self.status_filter.addItems(
            ["Tất cả trạng thái", "publish", "draft", "private"])
        self.status_filter.currentTextChanged.connect(self.filter_products)
        filter_layout.addRow("Trạng thái:", self.status_filter)

        self.category_filter = QComboBox()
        self.category_filter.addItem("Tất cả danh mục")
        self.category_filter.currentTextChanged.connect(self.filter_products)
        filter_layout.addRow("Danh mục:", self.category_filter)

        left_layout.addWidget(filter_group)

        # Buttons panel
        self.buttons_layout = QHBoxLayout()

        self.add_btn = QPushButton("➕ Thêm sản phẩm")
        self.add_btn.clicked.connect(self.add_product)
        self.buttons_layout.addWidget(self.add_btn)

        self.edit_btn = QPushButton("✏️ Sửa")
        self.edit_btn.clicked.connect(self.edit_product)
        self.edit_btn.setEnabled(False)
        self.buttons_layout.addWidget(self.edit_btn)

        self.delete_btn = QPushButton("🗑️ Xóa")
        self.delete_btn.clicked.connect(self.delete_selected_products)
        self.delete_btn.setEnabled(False)
        self.buttons_layout.addWidget(self.delete_btn)

        self.sync_btn = QPushButton("🔄 Đồng bộ sản phẩm")
        self.sync_btn.clicked.connect(self.sync_products)
        self.buttons_layout.addWidget(self.sync_btn)

        self.buttons_layout.addStretch()

        self.refresh_btn = QPushButton("🔄 Làm mới")
        self.refresh_btn.clicked.connect(self.refresh_data)
        self.buttons_layout.addWidget(self.refresh_btn)

        left_layout.addLayout(self.buttons_layout)

        # Product table
        self.table = QTableWidget()
        self.table.setColumnCount(12)
        self.table.setHorizontalHeaderLabels([
            "ID", "Ảnh", "Site", "Tên sản phẩm", "SKU", "Danh mục", "Giá ($)",
            "Kho", "Lượt xem", "Số đơn hàng", "Trạng thái", "Cập nhật"
        ])

        # Thiết lập table properties trước khi cấu hình header
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)  # Allow multi-selection
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)

        # Thiết lập kích thước cột với resize mode linh hoạt và an toàn
        self.setup_table_columns()

        # Connect selection change
        self.table.itemSelectionChanged.connect(self.on_selection_changed)

        left_layout.addWidget(self.table)

        # Statistics panel - di chuyển xuống cuối
        stats_group = QGroupBox("Thống kê sản phẩm")
        stats_group.setMaximumHeight(60)  # Giới hạn chiều cao
        stats_layout = QHBoxLayout(stats_group)
        stats_layout.setContentsMargins(10, 5, 10, 5)  # Giảm margins

        self.total_products_label = QLabel("Tổng: 0 sản phẩm")
        self.total_products_label.setFont(QFont("Arial", 8))  # Font nhỏ hơn
        self.total_products_label.setStyleSheet("color: #2E8B57; padding: 2px 8px; margin: 2px;")

        self.filtered_products_label = QLabel("Hiển thị: 0 sản phẩm")
        self.filtered_products_label.setFont(QFont("Arial", 8))
        self.filtered_products_label.setStyleSheet("color: #4682B4; padding: 2px 8px; margin: 2px;")

        self.sites_count_label = QLabel("Sites: 0")
        self.sites_count_label.setFont(QFont("Arial", 8))
        self.sites_count_label.setStyleSheet("color: #8A2BE2; padding: 2px 8px; margin: 2px;")

        stats_layout.addWidget(self.total_products_label)
        stats_layout.addWidget(self.filtered_products_label)
        stats_layout.addWidget(self.sites_count_label)
        stats_layout.addStretch()

        left_layout.addWidget(stats_group)

    def setup_table_columns(self):
        """Thiết lập responsive grid layout cho bảng sản phẩm"""
        header = self.table.horizontalHeader()

        # Thiết lập resize modes tối ưu cho từng cột
        resize_modes = [
            QHeaderView.ResizeMode.Fixed,             # ID - cố định
            QHeaderView.ResizeMode.Fixed,             # Ảnh - cố định
            QHeaderView.ResizeMode.ResizeToContents,  # Site - theo nội dung
            QHeaderView.ResizeMode.Stretch,           # Tên sản phẩm - co dãn chính
            QHeaderView.ResizeMode.ResizeToContents,  # SKU - theo nội dung
            QHeaderView.ResizeMode.Stretch,           # Danh mục - co dãn
            QHeaderView.ResizeMode.Fixed,             # Giá - cố định
            QHeaderView.ResizeMode.Fixed,             # Kho - cố định
            QHeaderView.ResizeMode.Fixed,             # Lượt xem - cố định
            QHeaderView.ResizeMode.Fixed,             # Số đơn hàng - cố định
            QHeaderView.ResizeMode.ResizeToContents,  # Trạng thái - theo nội dung
            QHeaderView.ResizeMode.Fixed              # Cập nhật - cố định
        ]

        # Áp dụng resize mode cho từng cột
        for col, mode in enumerate(resize_modes):
            if col < self.table.columnCount():
                header.setSectionResizeMode(col, mode)

        # Thiết lập width cố định cho các cột Fixed
        self.table.setColumnWidth(0, 50)   # ID
        self.table.setColumnWidth(1, 80)   # Ảnh
        self.table.setColumnWidth(6, 90)   # Giá
        self.table.setColumnWidth(7, 80)   # Kho
        self.table.setColumnWidth(8, 90)   # Lượt xem
        self.table.setColumnWidth(9, 100)  # Số đơn hàng
        self.table.setColumnWidth(11, 120) # Cập nhật

        # Cấu hình responsive header
        header.setStretchLastSection(False)
        header.setSectionsMovable(True)
        header.setSectionsClickable(True)
        header.setMinimumSectionSize(40)
        header.setDefaultSectionSize(120)

        # Context menu cho header để reset column sizes
        header.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        header.customContextMenuRequested.connect(self.show_header_context_menu)

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
        header = self.table.horizontalHeader()
        menu.exec(header.mapToGlobal(position))

    def reset_column_sizes(self):
        """Reset kích thước cột về mặc định"""
        try:
            self.setup_table_columns()
            self.status_message.emit("Đã reset kích thước cột về mặc định")
        except Exception as e:
            self.logger.error(f"Lỗi khi reset column sizes: {str(e)}")

    def auto_fit_columns(self):
        """Tự động điều chỉnh kích thước cột theo nội dung"""
        try:
            header = self.table.horizontalHeader()
            for col in range(self.table.columnCount()):
                # Chỉ auto-fit các cột có thể resize
                if header.sectionResizeMode(col) in [
                    QHeaderView.ResizeMode.Interactive,
                    QHeaderView.ResizeMode.ResizeToContents
                ]:
                    self.table.resizeColumnToContents(col)

            self.status_message.emit("Đã tự động điều chỉnh kích thước cột")
        except Exception as e:
            self.logger.error(f"Lỗi khi auto-fit columns: {str(e)}")

    def save_column_layout(self):
        """Lưu layout cột hiện tại"""
        try:
            column_widths = []
            for col in range(self.table.columnCount()):
                column_widths.append(self.table.columnWidth(col))

            # Lưu vào settings hoặc file (tạm thời lưu vào biến instance)
            self.saved_column_widths = column_widths
            self.status_message.emit("Đã lưu layout cột")
        except Exception as e:
            self.logger.error(f"Lỗi khi lưu column layout: {str(e)}")

    def load_column_layout(self):
        """Tải layout cột đã lưu"""
        try:
            if hasattr(self, 'saved_column_widths') and self.saved_column_widths:
                for col, width in enumerate(self.saved_column_widths):
                    if col < self.table.columnCount():
                        self.table.setColumnWidth(col, width)
                self.status_message.emit("Đã tải layout cột")
            else:
                self.status_message.emit("Chưa có layout nào được lưu")
        except Exception as e:
            self.logger.error(f"Lỗi khi tải column layout: {str(e)}")

    def load_data(self):
        """Tải dữ liệu sản phẩm và sites"""
        if not self.db_manager:
            return

        try:
            # Lưu trạng thái bộ lọc hiện tại
            current_site = self.site_filter.currentText()
            current_status = self.status_filter.currentText()
            current_category = self.category_filter.currentText()
            current_search = self.search_edit.text()

            # Load sites for filter
            self.sites = self.db_manager.get_all_sites()
            self.site_filter.clear()
            self.site_filter.addItem("Tất cả sites")
            for site in self.sites:
                self.site_filter.addItem(site.name)

            # Load products
            self.products = self.db_manager.get_all_products()

            # Load categories for filter
            self.load_categories_filter()

            # Khôi phục trạng thái bộ lọc
            self.restore_filter_state(current_site, current_status, current_category, current_search)

            self.pending_image_loads = []
            # Sử dụng filter_products thay vì update_table để duy trì bộ lọc
            self.filter_products()

            # Bắt đầu auto-loading ảnh sau khi update table
            self.start_auto_image_loading()
            self.status_message.emit(f"Đã tải {len(self.products)} sản phẩm")

        except Exception as e:
            self.logger.error(f"Lỗi khi tải dữ liệu: {str(e)}")
            QMessageBox.critical(self, "Lỗi",
                                 f"Không thể tải dữ liệu:\n{str(e)}")

    def start_auto_image_loading(self):
        """Bắt đầu tải ảnh tự động theo hàng đợi"""
        if self.pending_image_loads and not (
                self.image_queue_loader
                and self.image_queue_loader.isRunning()):
            # Sắp xếp theo thứ tự ưu tiên (dòng đầu tiên)
            self.pending_image_loads.sort(key=lambda x: x[0])

            self.image_queue_loader = ImageQueueLoader(
                self.pending_image_loads.copy())
            self.image_queue_loader.image_loaded.connect(
                self.on_queue_image_loaded)
            self.image_queue_loader.queue_progress.connect(
                self.on_queue_progress)
            self.image_queue_loader.finished.connect(self.on_queue_finished)

            self.image_queue_loader.start()
            self.pending_image_loads.clear()

    def on_queue_image_loaded(self, row, col, pixmap):
        """Xử lý ảnh từ queue đã load"""
        try:
            # Tìm label tương ứng trong table
            if row < self.table.rowCount() and col < self.table.columnCount():
                label = self.table.cellWidget(row, col)
                if label and hasattr(label, 'setPixmap'):
                    # Gọi hàm với đầy đủ tham số
                    url = getattr(label, 'image_url', 'unknown')
                    self.on_image_loaded(pixmap, url, row, col, label)
        except Exception as e:
            self.logger.error(f"Lỗi khi xử lý ảnh từ queue: {str(e)}")

    def on_queue_progress(self, current, total):
        """Hiển thị tiến độ loading ảnh"""
        if total > 0:
            self.status_message.emit(f"Đang tải ảnh {current}/{total}")

    def on_queue_finished(self):
        """Hoàn thành queue loading"""
        self.status_message.emit("Đã tải xong tất cả ảnh")
        # Lưu cache sau khi tải xong
        ImageLoader.save_persistent_cache()

    def load_categories_filter(self):
        """Tải danh sách danh mục cho filter"""
        categories = set()
        for product in self.products:
            if product.categories:
                cats = [cat.strip() for cat in product.categories.split(',')]
                categories.update(cats)

        self.category_filter.clear()
        self.category_filter.addItem("Tất cả danh mục")
        for category in sorted(categories):
            if category:
                self.category_filter.addItem(category)

    def restore_filter_state(self, site_text, status_text, category_text, search_text):
        """Khôi phục trạng thái bộ lọc sau khi load data"""
        try:
            # Khôi phục site filter
            site_index = self.site_filter.findText(site_text)
            if site_index >= 0:
                self.site_filter.setCurrentIndex(site_index)

            # Khôi phục status filter
            status_index = self.status_filter.findText(status_text)
            if status_index >= 0:
                self.status_filter.setCurrentIndex(status_index)

            # Khôi phục category filter
            category_index = self.category_filter.findText(category_text)
            if category_index >= 0:
                self.category_filter.setCurrentIndex(category_index)

            # Khôi phục search text
            self.search_edit.setText(search_text)

        except Exception as e:
            self.logger.error(f"Lỗi khi khôi phục filter state: {str(e)}")
            # Nếu có lỗi, để mặc định

    def update_table(self):
        """Cập nhật bảng sản phẩm"""
        filtered_products = self.get_filtered_products()
        
        # Xóa hoàn toàn table và tạo lại để tránh dữ liệu cũ
        self.table.clearContents()
        self.table.setRowCount(0)
        self.table.setRowCount(len(filtered_products))

        for row, product in enumerate(filtered_products):
            # ID - lưu trữ product object trong item để mapping chính xác
            id_item = QTableWidgetItem(str(product.id) if product.id else "")
            id_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            id_item.setData(Qt.ItemDataRole.UserRole, product)  # Lưu product object
            self.table.setItem(row, 0, id_item)

            # Product image - hiển thị ảnh thật với lazy loading tối ưu
            image_label = QLabel()
            image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            image_label.setScaledContents(True)
            image_label.setMinimumSize(70, 70)
            image_label.setMaximumSize(70, 70)
            image_label.setStyleSheet(
                "border: 1px solid #ddd; border-radius: 3px; background-color: #f8f9fa;"
            )

            if product.images and product.images.strip():
                image_urls = product.images.split(',')
                if image_urls and image_urls[0].strip():
                    image_url = image_urls[0].strip()
                    # Kiểm tra cache trước khi tải
                    if image_url in ImageLoader.image_cache:
                        # Cập nhật access count
                        ImageLoader.cache_access_count[
                            image_url] = ImageLoader.cache_access_count.get(
                                image_url, 0) + 1
                        image_label.setPixmap(
                            ImageLoader.image_cache[image_url])
                    else:
                        # Load ảnh cho tất cả các dòng với ưu tiên
                        # if row < 20:  # Load ngay lập tức cho 20 dòng đầu
                        #     self.load_product_image(row, 1, image_url, image_label)
                        # else:
                        #     # Hiển thị icon placeholder với click để load
                        #     image_label.setText("🖼️")
                        #     image_label.setToolTip(f"Click để tải ảnh\nURL: {image_url[:50]}...")
                        #     image_label.mousePressEvent = lambda e, r=row, c=1, url=image_url, label=image_label: self.load_product_image(r, c, url, label)
                        #     image_label.setCursor(Qt.CursorShape.PointingHandCursor)
                        self.pending_image_loads.append(
                            (row, 1, image_url, image_label))
                else:
                    image_label.setText("📷")
                    image_label.setToolTip("Không có URL ảnh")
            else:
                image_label.setText("📷")
                image_label.setToolTip("Sản phẩm chưa có ảnh")

            self.table.setCellWidget(row, 1, image_label)
            self.table.setRowHeight(row, 75)

            # Site name
            site_name = ""
            for site in self.sites:
                if site.id == product.site_id:
                    site_name = site.name
                    break
            site_item = QTableWidgetItem(site_name)
            self.table.setItem(row, 2, site_item)

            # Product name
            name_item = QTableWidgetItem(product.name or "")
            name_item.setFont(QFont("Arial", 10, QFont.Weight.Bold))
            self.table.setItem(row, 3, name_item)

            # SKU
            sku_item = QTableWidgetItem(product.sku or "")
            self.table.setItem(row, 4, sku_item)

            # Categories - hiển thị đầy đủ với tooltip
            categories_text = product.categories or ""
            if len(categories_text) > 50:
                display_text = categories_text[:47] + "..."
            else:
                display_text = categories_text
            category_item = QTableWidgetItem(display_text)
            category_item.setToolTip(
                f"Danh mục: {product.categories or 'Chưa phân loại'}")
            self.table.setItem(row, 5, category_item)

            # Price với định dạng USD
            if product.price:
                if product.sale_price and product.sale_price > 0:
                    price_text = f"${product.sale_price:,.2f}"
                    if product.regular_price and product.regular_price > product.sale_price:
                        price_text += f" (was ${product.regular_price:,.2f})"
                else:
                    price_text = f"${product.price:,.2f}"
            else:
                price_text = "$0.00"
            price_item = QTableWidgetItem(price_text)
            price_item.setTextAlignment(Qt.AlignmentFlag.AlignRight)
            self.table.setItem(row, 6, price_item)

            # Stock với trạng thái dựa trên stock_status và stock_quantity từ WooCommerce
            stock_status = getattr(product, 'stock_status', 'instock')

            if stock_status == 'outofstock':
                stock_text = "❌ Out of Stock"
            elif stock_status == 'onbackorder':
                stock_text = "⏳ On Backorder"
            elif stock_status == 'instock':
                if product.stock_quantity is not None and product.stock_quantity >= 0:
                    stock_text = f"✅ In Stock ({product.stock_quantity})"
                else:
                    stock_text = "✅ In Stock"
            else:
                stock_text = "❓ Unknown"
            stock_item = QTableWidgetItem(stock_text)
            stock_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 7, stock_item)

            # Lượt xem
            view_count = getattr(product, 'view_count', 0) or 0
            view_item = QTableWidgetItem(f"{view_count:,}")
            view_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 8, view_item)

            # Số đơn hàng
            order_count = getattr(product, 'order_count', 0) or 0
            order_item = QTableWidgetItem(f"{order_count:,}")
            order_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 9, order_item)

            # Status
            status_text = "✅ Published" if product.status == "publish" else "📝 Draft" if product.status == "draft" else product.status
            status_item = QTableWidgetItem(status_text)
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 10, status_item)

            # Last sync
            sync_text = product.last_sync.split(
                'T')[0] if product.last_sync else "Chưa đồng bộ"
            sync_item = QTableWidgetItem(sync_text)
            sync_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, 11, sync_item)

    def get_filtered_products(self):
        """Lấy danh sách sản phẩm đã lọc"""
        filtered = self.products

        # Filter by search text
        search_text = self.search_edit.text().lower()
        if search_text:
            filtered = [
                p for p in filtered
                if search_text in (p.name or "").lower() or search_text in (
                    p.sku or "").lower()
            ]

        # Filter by site
        site_name = self.site_filter.currentText()
        if site_name != "Tất cả sites":
            site_id = None
            for site in self.sites:
                if site.name == site_name:
                    site_id = site.id
                    break
            if site_id:
                filtered = [p for p in filtered if p.site_id == site_id]

        # Filter by status
        status = self.status_filter.currentText()
        if status != "Tất cả trạng thái":
            filtered = [p for p in filtered if p.status == status]

        # Filter by category
        category = self.category_filter.currentText()
        if category != "Tất cả danh mục":
            filtered = [
                p for p in filtered
                if p.categories and category in p.categories.split(',')
            ]

        return filtered

    def filter_products(self):
        """Lọc sản phẩm theo các tiêu chí"""
        self.pending_image_loads = []
        self.update_table()
        self.update_statistics()

        # Sau khi filter xong, start auto loading
        self.start_auto_image_loading()

    def apply_filters(self):
        """Áp dụng lại bộ lọc hiện tại (alias cho filter_products)"""
        self.filter_products()

    def update_statistics(self):
        """Cập nhật thống kê sản phẩm"""
        # Tổng số sản phẩm
        total_products = len(self.products)
        self.total_products_label.setText(f"Tổng: {total_products} sản phẩm")

        # Số sản phẩm hiển thị sau khi filter
        filtered_products = self.get_filtered_products()
        self.filtered_products_label.setText(f"Hiển thị: {len(filtered_products)} sản phẩm")

        # Tính tổng lượt xem và số đơn hàng
        total_views = sum(getattr(p, 'view_count', 0) or 0 for p in self.products)
        total_orders = sum(getattr(p, 'order_count', 0) or 0 for p in self.products)

        # Số sites
        self.sites_count_label.setText(f"Sites: {len(self.sites)} | Lượt xem: {total_views:,} | Đơn hàng: {total_orders:,}")

    def on_selection_changed(self):
        """Xử lý khi thay đổi lựa chọn trong bảng"""
        selected_rows = self.get_selected_rows()
        has_selection = len(selected_rows) > 0
        has_multiple_selection = len(selected_rows) > 1

        self.edit_btn.setEnabled(has_selection and not has_multiple_selection)  # Chỉ cho phép edit 1 sản phẩm
        self.delete_btn.setEnabled(has_selection)  # Enable khi có ít nhất 1 sản phẩm được chọn
        
        # Cập nhật text của nút xóa theo số lượng được chọn
        if has_multiple_selection:
            self.delete_btn.setText(f"🗑️ Xóa ({len(selected_rows)} sản phẩm)")
        elif has_selection:
            self.delete_btn.setText("🗑️ Xóa")
        else:
            self.delete_btn.setText("🗑️ Xóa")

    def add_product(self):
        """Thêm sản phẩm mới"""
        if not self.sites:
            QMessageBox.warning(self, "Cảnh báo", "Vui lòng thêm ít nhất một site trước khi thêm sản phẩm!")
            return

        try:
            dialog = ProductDialog(self, self.sites)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                product_data = dialog.get_product_data()

                # Thêm vào database
                product_id = self.db_manager.create_product(product_data)

                if product_id:
                    self.status_message.emit("Đã thêm sản phẩm thành công")
                    self.apply_filters()
                else:
                    QMessageBox.critical(self, "Lỗi", "Không thể thêm sản phẩm")

        except Exception as e:
            self.logger.error(f"Lỗi khi thêm sản phẩm: {str(e)}")
            QMessageBox.critical(self, "Lỗi", f"Không thể thêm sản phẩm:\n{str(e)}")

    def edit_product(self):
        """Sửa sản phẩm được chọn"""
        current_row = self.table.currentRow()
        if current_row < 0:
            return

        try:
            filtered_products = self.get_filtered_products()
            if current_row >= len(filtered_products):
                return

            product = filtered_products[current_row]

            dialog = ProductDialog(self, self.sites, product)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                product_data = dialog.get_product_data()

                # Cập nhật trong database
                success = self.db_manager.update_product(product.id, product_data)

                if success:
                    self.status_message.emit("Đã cập nhật sản phẩm thành công")
                    self.apply_filters()
                else:
                    QMessageBox.critical(self, "Lỗi", "Không thể cập nhật sản phẩm")

        except Exception as e:
            self.logger.error(f"Lỗi khi sửa sản phẩm: {str(e)}")
            QMessageBox.critical(self, "Lỗi", f"Không thể sửa sản phẩm:\n{str(e)}")

    def delete_selected_products(self):
        """Xóa các sản phẩm được chọn"""
        selected_rows = self.get_selected_rows()
        if not selected_rows:
            QMessageBox.warning(self, "Cảnh báo", "Vui lòng chọn ít nhất một sản phẩm để xóa!")
            return

        try:
            # Lấy danh sách products được chọn
            selected_products = []
            for row in selected_rows:
                id_item = self.table.item(row, 0)
                if id_item:
                    product = id_item.data(Qt.ItemDataRole.UserRole)
                    if product:
                        selected_products.append(product)

            if not selected_products:
                QMessageBox.warning(self, "Cảnh báo", "Không tìm thấy sản phẩm hợp lệ để xóa!")
                return

            # Xác nhận xóa
            if len(selected_products) == 1:
                confirm_message = f"Bạn có chắc chắn muốn xóa sản phẩm '{selected_products[0].name}'?"
            else:
                confirm_message = f"Bạn có chắc chắn muốn xóa {len(selected_products)} sản phẩm được chọn?"

            reply = QMessageBox.question(
                self, "Xác nhận xóa",
                confirm_message,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )

            if reply != QMessageBox.StandardButton.Yes:
                return

            # Hiển thị progress bar cho việc xóa nhiều sản phẩm
            self.progress_started.emit()
            self.status_message.emit(f"Đang xóa {len(selected_products)} sản phẩm...")

            deleted_count = 0
            failed_count = 0
            failed_products = []

            for i, product in enumerate(selected_products):
                try:
                    # Cập nhật progress
                    progress_percent = int((i + 1) / len(selected_products) * 100)
                    self.status_message.emit(f"Đang xóa sản phẩm {i+1}/{len(selected_products)}: {product.name}")

                    # Xóa trên site WooCommerce trước
                    site_deleted = True
                    if product.wc_product_id and product.site_id:
                        try:
                            site = self.db_manager.get_site_by_id(product.site_id)
                            if site:
                                api = WooCommerceAPI(site)
                                site_deleted = api.delete_product(product.wc_product_id)
                                if not site_deleted:
                                    self.logger.warning(f"Không thể xóa sản phẩm {product.name} trên site {site.name}")
                        except Exception as e:
                            self.logger.error(f"Lỗi khi xóa sản phẩm {product.name} trên site: {str(e)}")
                            site_deleted = False

                    # Xóa trong database (luôn thực hiện để dọn dẹp local data)
                    db_success = self.db_manager.delete_product(product.id)
                    
                    if db_success:
                        deleted_count += 1
                        self.logger.info(f"Đã xóa sản phẩm: {product.name}")
                    else:
                        failed_count += 1
                        failed_products.append(product.name)
                        self.logger.error(f"Không thể xóa sản phẩm khỏi database: {product.name}")

                except Exception as e:
                    failed_count += 1
                    failed_products.append(product.name)
                    self.logger.error(f"Lỗi khi xóa sản phẩm {product.name}: {str(e)}")

            # Hiển thị kết quả
            if deleted_count > 0:
                self.apply_filters()

            result_message = f"Đã xóa {deleted_count} sản phẩm thành công"
            if failed_count > 0:
                result_message += f", {failed_count} sản phẩm thất bại"
                if failed_products:
                    failed_list = '\n'.join(failed_products[:5])  # Hiển thị tối đa 5 sản phẩm lỗi
                    if len(failed_products) > 5:
                        failed_list += f"\n... và {len(failed_products) - 5} sản phẩm khác"
                    
                    QMessageBox.warning(
                        self, "Có lỗi xảy ra",
                        f"{result_message}\n\nCác sản phẩm không thể xóa:\n{failed_list}"
                    )
                else:
                    QMessageBox.warning(self, "Có lỗi xảy ra", result_message)
            else:
                QMessageBox.information(self, "Thành công", result_message)

            self.status_message.emit(result_message)

        except Exception as e:
            self.logger.error(f"Lỗi khi xóa sản phẩm: {str(e)}")
            QMessageBox.critical(self, "Lỗi", f"Không thể xóa sản phẩm:\n{str(e)}")
        finally:
            self.progress_finished.emit()

    def get_selected_rows(self):
        """Lấy danh sách các dòng được chọn"""
        selected_rows = set()
        selected_items = self.table.selectedItems()
        
        for item in selected_items:
            selected_rows.add(item.row())
        
        return sorted(list(selected_rows))

    def sync_products(self):
        """Đồng bộ sản phẩm từ site được chọn hoặc tất cả sites"""
        if not self.sites:
            QMessageBox.warning(self, "Cảnh báo", "Không có site nào để đồng bộ!")
            return

        try:
            # Lấy site được chọn từ filter
            selected_site_name = self.site_filter.currentText()
            selected_sites = []
            
            if selected_site_name == "Tất cả sites":
                # Nếu chọn "Tất cả sites" thì đồng bộ tất cả
                selected_sites = [site for site in self.sites if site.is_active]
                if not selected_sites:
                    QMessageBox.warning(self, "Cảnh báo", "Không có site nào được kích hoạt để đồng bộ!")
                    return
                sync_message = f"Đang đồng bộ từ {len(selected_sites)} sites..."
            else:
                # Chỉ đồng bộ site được chọn
                for site in self.sites:
                    if site.name == selected_site_name:
                        if not site.is_active:
                            QMessageBox.warning(self, "Cảnh báo", f"Site '{site.name}' không được kích hoạt!")
                            return
                        selected_sites = [site]
                        break
                
                if not selected_sites:
                    QMessageBox.warning(self, "Cảnh báo", "Không tìm thấy site được chọn!")
                    return
                    
                sync_message = f"Đang đồng bộ từ site '{selected_site_name}'..."

            self.progress_started.emit()
            self.status_message.emit(sync_message)

            # Tạo worker thread để đồng bộ với danh sách sites được chọn
            self.sync_worker = SyncProductsWorker(self.db_manager, selected_sites)
            self.sync_worker.progress_update.connect(self.on_sync_progress)
            self.sync_worker.products_synced.connect(self.on_products_synced)
            self.sync_worker.error_occurred.connect(self.on_sync_error)
            self.sync_worker.finished.connect(self.on_sync_finished)
            self.sync_worker.start()

        except Exception as e:
            self.logger.error(f"Lỗi khi bắt đầu đồng bộ: {str(e)}")
            QMessageBox.critical(self, "Lỗi", f"Không thể bắt đầu đồng bộ:\n{str(e)}")
            self.progress_finished.emit()

    def on_sync_finished(self):
        """Xử lý khi sync hoàn thành"""
        self.progress_finished.emit()
        # Load lại dữ liệu để đảm bảo hiển thị cập nhật
        QTimer.singleShot(500, self.load_data)

    def on_sync_progress(self, percent, message):
        """Xử lý tiến độ đồng bộ"""
        self.status_message.emit(f"{message} ({percent}%)")

    def on_products_synced(self, products):
        """Xử lý khi đồng bộ hoàn thành"""
        self.status_message.emit(f"Đã đồng bộ {len(products)} sản phẩm thành công")
        # Load lại dữ liệu và duy trì bộ lọc hiện tại
        self.load_data()

    def on_sync_error(self, error):
        """Xử lý lỗi đồng bộ"""
        self.logger.error(f"Lỗi đồng bộ: {error}")
        QMessageBox.critical(self, "Lỗi đồng bộ", f"Không thể đồng bộ sản phẩm:\n{error}")

    

    def refresh_data(self):
        """Làm mới dữ liệu với duy trì bộ lọc"""
        try:
            self.load_data()
            self.status_message.emit("Đã làm mới dữ liệu")
        except Exception as e:
            self.logger.error(f"Lỗi khi làm mới dữ liệu: {str(e)}")
            QMessageBox.critical(self, "Lỗi", f"Không thể làm mới dữ liệu:\n{str(e)}")

    def add_cache_management(self):
        """Thêm chức năng quản lý cache ảnh"""
        # Placeholder cho cache management
        pass

    def load_product_image(self, row, col, url, label):
        """Load ảnh sản phẩm"""
        try:
            # Tạo image loader thread
            loader = ImageLoader(row, col, url)
            loader.image_loaded.connect(lambda r, c, pixmap: self.on_image_loaded(pixmap, url, r, c, label))
            loader.start()

            # Thêm vào danh sách để quản lý
            self.image_loaders.append(loader)

        except Exception as e:
            self.logger.error(f"Lỗi khi load ảnh: {str(e)}")

    def on_image_loaded(self, pixmap, url, row, col, label):
        """Xử lý khi ảnh đã được load"""
        try:
            if label and hasattr(label, 'setPixmap'):
                label.setPixmap(pixmap)
                label.setToolTip(f"Ảnh: {url}")
        except Exception as e:
            self.logger.error(f"Lỗi khi hiển thị ảnh: {str(e)}")

    def export_csv(self):
        """Export sản phẩm ra CSV"""
        try:
            from PyQt6.QtWidgets import QFileDialog

            file_path, _ = QFileDialog.getSaveFileName(
                self, "Xuất file CSV", "products.csv", "CSV Files (*.csv)"
            )

            if file_path:
                import csv

                with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.writer(csvfile)

                    # Header
                    writer.writerow([
                        'ID', 'Site', 'Tên sản phẩm', 'SKU', 'Danh mục', 
                        'Giá', 'Giá sale', 'Kho', 'Trạng thái', 'Mô tả'
                    ])

                    # Data
                    for product in self.get_filtered_products():
                        site_name = ""
                        for site in self.sites:
                            if site.id == product.site_id:
                                site_name = site.name
                                break

                        writer.writerow([
                            product.id, site_name, product.name, product.sku,
                            product.categories, product.price, product.sale_price,
                            product.stock_quantity, product.status, product.description
                        ])

                self.status_message.emit(f"Đã xuất {len(self.get_filtered_products())} sản phẩm ra {file_path}")

        except Exception as e:
            self.logger.error(f"Lỗi khi xuất CSV: {str(e)}")
            QMessageBox.critical(self, "Lỗi", f"Không thể xuất CSV:\n{str(e)}")

    def import_csv(self):
        """Import sản phẩm từ CSV"""
        try:
            from PyQt6.QtWidgets import QFileDialog

            file_path, _ = QFileDialog.getOpenFileName(
                self, "Chọn file CSV", "", "CSV Files (*.csv)"
            )

            if file_path:
                import csv

                with open(file_path, 'r', encoding='utf-8') as csvfile:
                    reader = csv.DictReader(csvfile)

                    imported_count = 0
                    for row in reader:
                        try:
                            # Tìm site_id từ tên site
                            site_id = None
                            for site in self.sites:
                                if site.name == row.get('Site', ''):
                                    site_id = site.id
                                    break

                            if not site_id:
                                continue

                            product_data = {
                                'site_id': site_id,
                                'name': row.get('Tên sản phẩm', ''),
                                'sku': row.get('SKU', ''),
                                'categories': row.get('Danh mục', ''),
                                'price': float(row.get('Giá', 0) or 0),
                                'sale_price': float(row.get('Giá sale', 0) or 0) if row.get('Giá sale') else None,
                                'stock_quantity': int(row.get('Kho', 0) or 0),
                                'status': row.get('Trạng thái', 'draft'),
                                'description': row.get('Mô tả', '')
                            }

                            self.db_manager.create_product(product_data)
                            imported_count += 1

                        except Exception as e:
                            self.logger.warning(f"Lỗi khi import dòng: {str(e)}")
                            continue

                self.status_message.emit(f"Đã import {imported_count} sản phẩm thành công")
                self.refresh_data()

        except Exception as e:
            self.logger.error(f"Lỗi khi import CSV: {str(e)}")
            QMessageBox.critical(self, "Lỗi", f"Không thể import CSV:\n{str(e)}")


class ImageQueueLoader(QThread):
    """Thread để load ảnh theo hàng đợi"""
    image_loaded = pyqtSignal(int, int, QPixmap)
    queue_progress = pyqtSignal(int, int)

    def __init__(self, image_queue):
        super().__init__()
        self.image_queue = image_queue

    def run(self):
        """Chạy queue loading"""
        total = len(self.image_queue)

        for i, (row, col, url, label) in enumerate(self.image_queue):
            try:
                # Load ảnh
                loader = ImageLoader(row, col, url)
                loader.run()  # Chạy đồng bộ

                # Emit progress
                self.queue_progress.emit(i + 1, total)

            except Exception as e:
                print(f"Error loading image: {e}")
                continue


class DataManagerTab(QWidget):
    """Tab quản lý data"""

    # Signals
    data_loaded = pyqtSignal()
    status_message = pyqtSignal(str)
    products_loaded = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.db_manager = None
        self.sites = []
        self.products = []
        self.init_ui()

    def init_ui(self):
        """Khởi tạo giao diện"""
        layout = QVBoxLayout(self)

        # Site filter section
        site_group = QGroupBox("Lọc theo Site")
        site_layout = QHBoxLayout(site_group)

        self.site_filter = QComboBox()
        self.site_filter.addItem("Tất cả")
        self.site_filter.currentIndexChanged.connect(self.load_products)  # Changed signal
        site_layout.addWidget(self.site_filter)
        layout.addWidget(site_group)

        # Status filter section
        status_group = QGroupBox("Lọc theo Trạng thái")
        status_layout = QHBoxLayout(status_group)

        self.status_filter = QComboBox()
        self.status_filter.addItem("Tất cả")
        self.status_filter.addItem("publish")
        self.status_filter.addItem("draft")
        self.status_filter.addItem("private")
        self.status_filter.currentIndexChanged.connect(self.load_products)
        status_layout.addWidget(self.status_filter)
        layout.addWidget(status_group)

        # Search section
        search_group = QGroupBox("Tìm kiếm")
        search_layout = QHBoxLayout(search_group)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Tìm theo tên hoặc SKU...")
        self.search_input.textChanged.connect(self.load_products)
        search_layout.addWidget(self.search_input)
        layout.addWidget(search_group)

        # Product table
        self.product_table = QTableWidget()
        self.product_table.setColumnCount(4)
        self.product_table.setHorizontalHeaderLabels([
            "Tên", "Mô tả", "Số thư mục", "Ngày tạo"
        ])

        # Thiết lập responsive grid layout cho bảng
        header = self.product_table.horizontalHeader()

        # Thiết lập resize modes tối ưu cho từng cột
        resize_modes = [
            QHeaderView.ResizeMode.Stretch,           # Tên - co dãn chính
            QHeaderView.ResizeMode.Stretch,           # Mô tả - co dãn
            QHeaderView.ResizeMode.Fixed,             # Số thư mục - cố định
            QHeaderView.ResizeMode.Fixed              # Ngày tạo - cố định
        ]

        # Áp dụng resize mode cho từng cột
        for col, mode in enumerate(resize_modes):
            if col < self.product_table.columnCount():
                header.setSectionResizeMode(col, mode)

        # Thiết lập width cố định cho các cột Fixed
        self.product_table.setColumnWidth(2, 100)   # Số thư mục
        self.product_table.setColumnWidth(3, 150)   # Ngày tạo

        # Cấu hình responsive header với khả năng kéo thả
        header.setStretchLastSection(False)
        header.setSectionsMovable(True)           # Cho phép kéo thả di chuyển cột
        header.setSectionsClickable(True)         # Cho phép click để sort
        header.setMinimumSectionSize(40)
        header.setDefaultSectionSize(120)

        # Configure table
        self.product_table.setAlternatingRowColors(True)
        self.product_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.product_table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)  # Allow multi-selection
        self.product_table.setSortingEnabled(True)
        self.product_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.product_table.customContextMenuRequested.connect(self.show_context_menu)

        layout.addWidget(self.product_table)

        # Product count label
        self.product_count_label = QLabel("Tổng: 0 sản phẩm")
        layout.addWidget(self.product_count_label)

        self.setLayout(layout)

    def set_db_manager(self, db_manager):
        """Set database manager"""
        self.db_manager = db_manager
        self.load_sites()
        self.load_products()

    def load_sites(self):
        """Load sites"""
        try:
            self.sites = self.db_manager.get_all_sites()
            self.site_filter.clear()
            self.site_filter.addItem("Tất cả")
            for site in self.sites:
                self.site_filter.addItem(site.name, site.id)
        except Exception as e:
            self.logger.error(f"Lỗi load sites: {str(e)}")
            QMessageBox.critical(self, "Lỗi", f"Không thể load sites:\n{str(e)}")

    def load_products(self):
        """Load sản phẩm vào bảng với format giống data manager"""
        try:
            # Get filtered products
            site_id = self.site_filter.currentData() if self.site_filter.currentText() != "Tất cả" else None
            status = self.status_filter.currentText() if self.status_filter.currentText() != "Tất cả" else None
            search_text = self.search_input.text().strip()

            # Filter products
            filtered_products = []
            for product in self.products:
                # Site filter
                if site_id and product.get('site_id') != site_id:
                    continue

                # Status filter
                if status and product.get('status') != status:
                    continue

                # Search filter
                if search_text:
                    searchable_text = f"{product.get('name', '')} {product.get('sku', '')}".lower()
                    if search_text.lower() not in searchable_text:
                        continue

                filtered_products.append(product)

            # Update product count
            self.product_count_label.setText(f"Tổng: {len(filtered_products)} sản phẩm")

            # Populate table
            self.product_table.setRowCount(len(filtered_products))

            for row, product in enumerate(filtered_products):
                # Tên sản phẩm
                product_name = product.get('name', '')
                name_item = QTableWidgetItem(product_name)
                if not self.minimal_mode:
                    name_item.setData(Qt.ItemDataRole.UserRole, product)  # Store product data
                self.product_table.setItem(row, 0, name_item)

                # Mô tả (tạo từ thông tin sản phẩm)
                site_name = ""
                for site in self.sites:
                    if site.id == product.get('site_id'):
                        site_name = site.name
                        break

                categories = product.get('categories', [])
                category_names = [cat.get('name', '') for cat in categories]
                category_text = ', '.join(category_names[:2])  # Giới hạn 2 category đầu
                if len(category_names) > 2:
                    category_text += "..."

                description = f"Sản phẩm {product.get('status', 'draft')}"
                if category_text:
                    description += f" - {category_text}"
                if site_name:
                    description += f" - {site_name}"

                self.product_table.setItem(row, 1, QTableWidgetItem(description))

                # Số thư mục (tương đương image_count, sử dụng số lượng images)
                images = product.get('images', [])
                image_count = len(images)
                self.product_table.setItem(row, 2, QTableWidgetItem(str(image_count)))

                # Ngày tạo
                date_created = product.get('date_created', '')
                if date_created:
                    try:
                        from datetime import datetime
                        if isinstance(date_created, str):
                            dt = datetime.fromisoformat(date_created.replace('Z', '+00:00'))
                            formatted_date = dt.strftime('%Y-%m-%d %H:%M')
                        else:
                            formatted_date = str(date_created)
                    except:
                        formatted_date = str(date_created)
                else:
                    formatted_date = ""

                self.product_table.setItem(row, 3, QTableWidgetItem(formatted_date))

            # Resize columns to content
            self.product_table.resizeColumnsToContents()

        except Exception as e:
            self.logger.error(f"Lỗi load products: {str(e)}")
            QMessageBox.critical(self, "Lỗi", f"Không thể load sản phẩm:\n{str(e)}")

    def show_context_menu(self, position):
        """Hiển thị context menu"""
        menu = QMenu(self)

        # Edit action
        edit_action = menu.addAction("Sửa")
        edit_action.triggered.connect(self.edit_selected_product)

        # Delete action
        delete_action = menu.addAction("Xóa")
        delete_action.triggered.connect(self.delete_selected_product)

        menu.exec(self.product_table.mapToGlobal(position))

    def edit_selected_product(self):
        """Sửa sản phẩm được chọn"""
        selected_row = self.product_table.currentRow()
        if selected_row >= 0:
            product = self.get_product_at_row(selected_row)
            if product:
                self.edit_product(product)

    def delete_selected_product(self):
        """Xóa sản phẩm được chọn"""
        selected_row = self.product_table.currentRow()
        if selected_row >= 0:
            product = self.get_product_at_row(selected_row)
            if product:
                self.delete_product(product)

    def get_product_at_row(self, row):
        """Lấy sản phẩm tại dòng"""
        item = self.product_table.item(row, 0)
        if item:
            return item.data(Qt.ItemDataRole.UserRole)
        return None

    def add_product(self):
        """Thêm sản phẩm"""
        if not self.sites:
            QMessageBox.warning(self, "Cảnh báo", "Vui lòng thêm ít nhất một site trước khi thêm sản phẩm!")
            return

        try:
            dialog = ProductDialog(self, self.sites)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                product_data = dialog.get_product_data()

                # Thêm vào database
                product_id = self.db_manager.create_product(product_data)

                if product_id:
                    self.status_message.emit("Đã thêm sản phẩm thành công")
                    self.load_products()
                else:
                    QMessageBox.critical(self, "Lỗi", "Không thể thêm sản phẩm")

        except Exception as e:
            self.logger.error(f"Lỗi khi thêm sản phẩm: {str(e)}")
            QMessageBox.critical(self, "Lỗi", f"Không thể thêm sản phẩm:\n{str(e)}")

    def edit_product(self, product):
        """Sửa sản phẩm"""
        try:
            dialog = ProductDialog(self, self.sites, product)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                product_data = dialog.get_product_data()

                # Cập nhật trong database
                success = self.db_manager.update_product(product.id, product_data)

                if success:
                    self.status_message.emit("Đã cập nhật sản phẩm thành công")
                    self.load_products()
                else:
                    QMessageBox.critical(self, "Lỗi", "Không thể cập nhật sản phẩm")

        except Exception as e:
            self.logger.error(f"Lỗi khi sửa sản phẩm: {str(e)}")
            QMessageBox.critical(self, "Lỗi", f"Không thể sửa sản phẩm:\n{str(e)}")

    def delete_product(self, product):
        """Xóa sản phẩm"""
        try:
            reply = QMessageBox.question(
                self, "Xác nhận xóa",
                f"Bạn có chắc chắn muốn xóa sản phẩm '{product.name}'?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )

            if reply == QMessageBox.StandardButton.Yes:
                success = self.db_manager.delete_product(product.id)

                if success:
                    self.status_message.emit("Đã xóa sản phẩm thành công")
                    self.load_products()
                else:
                    QMessageBox.critical(self, "Lỗi", "Không thể xóa sản phẩm")

        except Exception as e:
            self.logger.error(f"Lỗi khi xóa sản phẩm: {str(e)}")
            QMessageBox.critical(self, "Lỗi", f"Không thể xóa sản phẩm:\n{str(e)}")