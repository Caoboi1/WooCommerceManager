"""
Category Manager - Tab quản lý danh mục sản phẩm
"""

import logging
from typing import List, Dict, Optional
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *

from .models import Site
from .database import DatabaseManager
from .woocommerce_api import WooCommerceAPI
from .category_dialog import CategoryDialog
from .bulk_category_dialog import BulkCategoryDialog


class CategorySyncWorker(QThread):
    """Worker thread để đồng bộ categories"""

    progress_updated = pyqtSignal(int, str)  # progress value, status message
    finished = pyqtSignal(bool, str)  # success, message
    category_synced = pyqtSignal(dict)  # category data

    def __init__(self, site: Site):
        super().__init__()
        self.site = site
        self.logger = logging.getLogger(__name__)

    def run(self):
        """Thực hiện đồng bộ categories"""
        try:
            self.progress_updated.emit(10, f"Kết nối đến {self.site.name}...")

            # Khởi tạo API
            api = WooCommerceAPI(self.site)

            self.progress_updated.emit(30, "Lấy danh sách categories...")

            # Lấy tất cả categories từ WooCommerce
            categories = api.get_categories()

            if not categories:
                self.finished.emit(
                    False, "Không thể lấy dữ liệu categories từ WooCommerce")
                return

            self.progress_updated.emit(
                50, f"Đồng bộ {len(categories)} categories...")

            # Lưu vào database
            db = DatabaseManager()
            db.save_categories_from_api(self.site.id, categories)

            self.progress_updated.emit(100, "Hoàn thành!")
            self.finished.emit(
                True, f"Đã đồng bộ {len(categories)} categories thành công")

        except Exception as e:
            self.logger.error(f"Lỗi sync categories: {str(e)}")
            self.finished.emit(False, f"Lỗi đồng bộ: {str(e)}")


class CategoryManagerTab(QWidget):
    """Tab quản lý danh mục sản phẩm"""

    def __init__(self):
        super().__init__()
        self.db = DatabaseManager()
        self.logger = logging.getLogger(__name__)
        self.sync_worker = None
        self.is_initializing = True  # Flag để ngăn dialog khi khởi tạo

        self.init_ui()
        self.load_sites()
        self.load_categories()

        # Hoàn thành khởi tạo và kết nối signal
        self.is_initializing = False
        self.table.itemChanged.connect(self.on_item_changed)

    def init_ui(self):
        """Khởi tạo giao diện"""
        layout = QVBoxLayout(self)
        layout.setSpacing(5)  # Giảm spacing từ 10 xuống 5
        layout.setContentsMargins(5, 5, 5, 5)  # Giảm margins từ 10 xuống 5

        # Header với controls
        header_layout = QHBoxLayout()

        # Site selection
        site_label = QLabel("Site:")
        site_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        header_layout.addWidget(site_label)

        self.site_combo = QComboBox()
        self.site_combo.setMinimumWidth(200)
        self.site_combo.currentTextChanged.connect(self.filter_categories)
        header_layout.addWidget(self.site_combo)

        header_layout.addSpacing(20)

        # Search
        search_label = QLabel("Tìm kiếm:")
        search_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        header_layout.addWidget(search_label)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Nhập tên danh mục hoặc slug...")
        self.search_edit.setMinimumWidth(250)
        self.search_edit.textChanged.connect(self.filter_categories)
        header_layout.addWidget(self.search_edit)

        header_layout.addStretch()

        # Buttons
        self.sync_btn = QPushButton("🔄 Đồng bộ danh mục")
        self.sync_btn.clicked.connect(self.sync_categories)
        self.sync_btn.setToolTip("Đồng bộ danh mục từ site được chọn")
        header_layout.addWidget(self.sync_btn)

        self.add_btn = QPushButton("➕ Thêm Danh mục")
        self.add_btn.clicked.connect(self.add_category)
        header_layout.addWidget(self.add_btn)

        self.bulk_add_btn = QPushButton("🌳 Tạo cấu trúc cây")
        self.bulk_add_btn.clicked.connect(self.bulk_add_categories)
        header_layout.addWidget(self.bulk_add_btn)

        self.edit_btn = QPushButton("✏️ Sửa")
        self.edit_btn.clicked.connect(self.edit_category)
        self.edit_btn.setEnabled(False)
        header_layout.addWidget(self.edit_btn)

        self.delete_btn = QPushButton("🗑️ Xóa")
        self.delete_btn.clicked.connect(self.delete_category)
        self.delete_btn.setEnabled(False)
        header_layout.addWidget(self.delete_btn)

        self.debug_btn = QPushButton("🔍 Debug Mapping")
        self.debug_btn.clicked.connect(self.debug_category_mapping)
        header_layout.addWidget(self.debug_btn)

        layout.addLayout(header_layout)

        # Splitter cho table và details
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Table với hiển thị thụt lề cho cấu trúc cha-con
        self.table = QTableWidget()
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)

        # Categories table
        self.table = QTableWidget()
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels([
            "ID", "Site", "Tên danh mục", "Slug", "Mô tả", "Ảnh",
            "Số sản phẩm", "Parent", "WC ID"
        ])

        # Cấu hình responsive grid layout cho categories
        header = self.table.horizontalHeader()
        if header:
            # Thiết lập resize modes tối ưu cho từng cột
            header.setSectionResizeMode(
                0, QHeaderView.ResizeMode.Fixed)  # ID - cố định
            header.setSectionResizeMode(1,
                                        QHeaderView.ResizeMode.ResizeToContents
                                        )  # Site - theo nội dung
            header.setSectionResizeMode(
                2,
                QHeaderView.ResizeMode.Stretch)  # Tên danh mục - co dãn chính
            header.setSectionResizeMode(
                3, QHeaderView.ResizeMode.Stretch)  # Slug - co dãn
            header.setSectionResizeMode(
                4, QHeaderView.ResizeMode.Stretch)  # Mô tả - co dãn
            header.setSectionResizeMode(
                5, QHeaderView.ResizeMode.Fixed)  # Ảnh - cố định
            header.setSectionResizeMode(
                6, QHeaderView.ResizeMode.Fixed)  # Số sản phẩm - cố định
            header.setSectionResizeMode(7,
                                        QHeaderView.ResizeMode.ResizeToContents
                                        )  # Parent - theo nội dung
            header.setSectionResizeMode(
                8, QHeaderView.ResizeMode.Fixed)  # WC ID - cố định

            # Thiết lập width cố định cho các cột Fixed
            self.table.setColumnWidth(0, 50)  # ID
            self.table.setColumnWidth(5, 80)  # Ảnh
            self.table.setColumnWidth(6, 90)  # Số sản phẩm
            self.table.setColumnWidth(8, 80)  # WC ID

            # Cấu hình responsive header
            header.setStretchLastSection(False)
            header.setMinimumSectionSize(40)
            header.setDefaultSectionSize(120)

        self.table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.selectionModel().selectionChanged.connect(
            self.on_selection_changed)

        # Enable inline editing (kết nối signal sau khi khởi tạo xong)
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed)

        splitter.addWidget(self.table)

        # Category details panel
        details_group = QGroupBox("Chi tiết Danh mục")
        details_layout = QVBoxLayout(details_group)

        # Điều chỉnh QTextEdit để nó lấp đầy chiều cao của GroupBox
        self.details_text = QTextEdit()
        self.details_text.setReadOnly(True)
        # Bỏ các giới hạn chiều cao
        # self.details_text.setMaximumHeight(120)  
        # self.details_text.setMinimumHeight(80)   
        details_layout.addWidget(self.details_text)

        splitter.addWidget(details_group)
        # Điều chỉnh tỷ lệ chia giữa bảng và chi tiết (700:300 thay vì 700:200)
        splitter.setSizes([700, 300])

        layout.addWidget(splitter)

        # Stats panel - compact version
        stats_group = QGroupBox("Thống kê")
        stats_group.setMaximumHeight(60)  # Giới hạn chiều cao
        stats_layout = QHBoxLayout(stats_group)
        stats_layout.setContentsMargins(10, 5, 10, 5)  # Giảm margins

        self.total_label = QLabel("Tổng: 0")
        self.synced_label = QLabel("Đã đồng bộ: 0")
        self.parent_label = QLabel("Danh mục cha: 0")
        self.child_label = QLabel("Danh mục con: 0")

        for label in [
                self.total_label, self.synced_label, self.parent_label,
                self.child_label
        ]:
            label.setFont(QFont("Arial", 8))  # Font nhỏ hơn
            label.setStyleSheet(
                "color: #555; padding: 2px 8px; margin: 2px;")  # Style compact
            stats_layout.addWidget(label)

        stats_layout.addStretch()
        layout.addWidget(stats_group)

        # Progress bar and status (initially hidden) - compact version
        progress_widget = QWidget()
        progress_widget.setMaximumHeight(30)  # Giới hạn chiều cao
        progress_layout = QHBoxLayout(progress_widget)
        progress_layout.setContentsMargins(0, 0, 0, 0)  # Loại bỏ margins
        progress_layout.setSpacing(5)

        self.status_label = QLabel("Sẵn sàng")
        self.status_label.setFont(QFont("Arial", 8))  # Font nhỏ hơn
        self.status_label.setStyleSheet("color: #666; padding: 2px;")
        progress_layout.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setMaximumHeight(20)  # Giới hạn chiều cao progress bar
        progress_layout.addWidget(self.progress_bar)

        layout.addWidget(progress_widget)

        # Không thêm stretch để layout sát xuống dưới

    def load_sites(self):
        """Load danh sách sites"""
        try:
            sites = self.db.get_all_sites()
            self.site_combo.clear()
            self.site_combo.addItem("Tất cả sites", None)

            for site in sites:
                self.site_combo.addItem(site.name, site.id)

        except Exception as e:
            self.logger.error(f"Lỗi load sites: {str(e)}")

    def load_categories(self):
        """Load danh sách categories"""
        try:
            categories = self.db.get_all_categories()
            self.display_categories(categories)
            self.update_stats(categories)

        except Exception as e:
            self.logger.error(f"Lỗi load categories: {str(e)}")
            QMessageBox.critical(self, "Lỗi",
                                 f"Không thể tải categories: {str(e)}")

    def display_categories(self, categories: List[Dict]):
        """Hiển thị categories trong table với thụt lề theo cấu trúc cha-con"""
        try:
            # Tạm thời disconnect signal để tránh trigger dialog khi populate data
            try:
                self.table.itemChanged.disconnect()
            except:
                pass  # Signal có thể chưa được kết nối

            # Clear table trước
            self.table.setRowCount(0)
            # Tạo dict để lookup categories
            local_id_to_category = {}
            parent_children = {}
            root_categories = []

            # Build lookup dictionary - sử dụng wc_category_id thay vì local id
            for category in categories:
                local_id = category.get('id')
                wc_id = category.get('wc_category_id')
                if local_id:
                    local_id_to_category[local_id] = category
                if wc_id:
                    local_id_to_category[wc_id] = category

            # Phân loại categories thành root và children dựa trên parent_id
            for category in categories:
                parent_id = category.get('parent_id')

                if not parent_id or parent_id == 0:
                    root_categories.append(category)
                else:
                    # Kiểm tra parent có tồn tại trong danh sách không
                    if parent_id in local_id_to_category:
                        if parent_id not in parent_children:
                            parent_children[parent_id] = []
                        parent_children[parent_id].append(category)
                    else:
                        # Nếu không tìm thấy parent trong danh sách hiện tại, coi như root
                        root_categories.append(category)

            # Tạo danh sách categories theo thứ tự hiển thị với cấu trúc cây
            ordered_categories = []

            # Sắp xếp root categories theo tên
            root_categories.sort(key=lambda x: x.get('name', '').lower())

            def add_category_and_children(category,
                                          level=0,
                                          is_last_sibling=True,
                                          parent_prefixes=""):
                """Thêm category và children của nó vào danh sách ordered với tree structure"""
                ordered_categories.append(
                    (category, level, is_last_sibling, parent_prefixes))

                # Thêm children nếu có
                category_id = category.get('id')
                wc_id = category.get('wc_category_id')

                children = []
                if category_id and category_id in parent_children:
                    children = parent_children[category_id]
                elif wc_id and wc_id in parent_children:
                    children = parent_children[wc_id]

                if children:
                    children = sorted(children,
                                      key=lambda x: x.get('name', '').lower())

                    # Tạo prefix cho children
                    if level == 0:
                        new_parent_prefixes = ""
                    else:
                        if is_last_sibling:
                            new_parent_prefixes = parent_prefixes + "    "
                        else:
                            new_parent_prefixes = parent_prefixes + "│   "

                    for i, child in enumerate(children):
                        is_last_child = (i == len(children) - 1)
                        add_category_and_children(child, level + 1,
                                                  is_last_child,
                                                  new_parent_prefixes)

            # Xây dựng cấu trúc cây
            for i, root_category in enumerate(root_categories):
                is_last_root = (i == len(root_categories) - 1)
                add_category_and_children(root_category, 0, is_last_root, "")

            # Hiển thị trong table
            self.table.setRowCount(len(ordered_categories))

            for row, (category, level, is_last_sibling,
                      parent_prefixes) in enumerate(ordered_categories):
                # ID
                item = QTableWidgetItem(str(category.get('id', '')))
                item.setData(Qt.ItemDataRole.UserRole, category)
                self.table.setItem(row, 0, item)

                # Site name
                site_name = ""
                if category.get('site_id'):
                    site = self.db.get_site_by_id(category['site_id'])
                    if site:
                        site_name = site.name if hasattr(
                            site, 'name') else str(site.get('name', ''))
                self.table.setItem(row, 1, QTableWidgetItem(site_name))

                # Tên với tree structure như trong hình
                name = str(category.get('name', ''))
                if level > 0:
                    # Tạo tree structure với các ký tự box drawing
                    tree_prefix = parent_prefixes
                    if is_last_sibling:
                        tree_prefix += "└── "
                    else:
                        tree_prefix += "├── "
                    name = tree_prefix + name

                # Tạo font đậm cho parent categories (level 0)
                name_item = QTableWidgetItem(name)
                if level == 0:
                    font = name_item.font()
                    font.setBold(True)
                    name_item.setFont(font)
                    # Thêm icon folder cho categories cha
                    name_item.setText("📁 " + name)
                elif level == 1:
                    # Icon cho categories con cấp 1
                    if name.strip().endswith("├── " +
                                             category.get('name', '')):
                        name_item.setText(
                            name.replace("├── ",
                                         "├── 📂 ").replace("└── ", "└── 📂 "))
                    else:
                        name_item.setText(name)
                else:
                    # Icon cho categories con cấp 2+
                    if "├── " in name or "└── " in name:
                        name_item.setText(
                            name.replace("├── ",
                                         "├── 📄 ").replace("└── ", "└── 📄 "))
                    else:
                        name_item.setText(name)

                # Cho phép chỉnh sửa name nếu có WC ID (đã đồng bộ)
                if category.get('wc_category_id'):
                    name_item.setFlags(name_item.flags()
                                       | Qt.ItemFlag.ItemIsEditable)
                    name_item.setToolTip("Double-click để chỉnh sửa trực tiếp")
                else:
                    name_item.setFlags(name_item.flags()
                                       & ~Qt.ItemFlag.ItemIsEditable)
                    name_item.setToolTip(
                        "Category chưa đồng bộ - không thể chỉnh sửa trực tiếp"
                    )

                self.table.setItem(row, 2, name_item)

                # Slug
                slug_item = QTableWidgetItem(str(category.get('slug', '')))
                if category.get('wc_category_id'):
                    slug_item.setFlags(slug_item.flags()
                                       | Qt.ItemFlag.ItemIsEditable)
                    slug_item.setToolTip(
                        "Double-click để chỉnh sửa slug trực tiếp")
                else:
                    slug_item.setFlags(slug_item.flags()
                                       & ~Qt.ItemFlag.ItemIsEditable)
                    slug_item.setToolTip(
                        "Category chưa đồng bộ - không thể chỉnh sửa trực tiếp"
                    )
                self.table.setItem(row, 3, slug_item)

                # Mô tả (hiển thị đầy đủ hơn)
                description = str(category.get('description', ''))
                # Loại bỏ HTML tags nếu có
                import re
                clean_description = re.sub(r'<[^>]+>', '', description)
                clean_description = clean_description.strip()

                # Hiển thị tối đa 200 ký tự thay vì 100
                if len(clean_description) > 200:
                    display_description = clean_description[:197] + "..."
                else:
                    display_description = clean_description

                desc_item = QTableWidgetItem(display_description)
                desc_item.setToolTip(
                    clean_description)  # Full description in tooltip

                # Cho phép chỉnh sửa description
                if category.get('wc_category_id'):
                    desc_item.setFlags(desc_item.flags()
                                       | Qt.ItemFlag.ItemIsEditable)
                    desc_item.setToolTip(
                        clean_description +
                        "\n\nDouble-click để chỉnh sửa trực tiếp")
                else:
                    desc_item.setFlags(desc_item.flags()
                                       & ~Qt.ItemFlag.ItemIsEditable)
                    desc_item.setToolTip(
                        clean_description +
                        "\n\nCategory chưa đồng bộ - không thể chỉnh sửa trực tiếp"
                    )

                self.table.setItem(row, 4, desc_item)

                # Ảnh - hiển thị thumbnail nếu có
                image_item = QTableWidgetItem()
                image_url = category.get('image', '')
                if image_url:
                    # Tạo label để hiển thị ảnh
                    image_widget = QLabel()
                    image_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    image_widget.setFixedSize(70, 70)
                    image_widget.setStyleSheet(
                        "border: 1px solid #ddd; background: #f9f9f9;")

                    try:
                        # Load image từ URL hoặc file path
                        if image_url.startswith(('http://', 'https://')):
                            # TODO: Load image from URL (cần implement async loading)
                            image_widget.setText("🖼️")
                        else:
                            # Load local image
                            pixmap = QPixmap(image_url)
                            if not pixmap.isNull():
                                scaled_pixmap = pixmap.scaled(
                                    68, 68, Qt.AspectRatioMode.KeepAspectRatio,
                                    Qt.TransformationMode.SmoothTransformation)
                                image_widget.setPixmap(scaled_pixmap)
                            else:
                                image_widget.setText("❌")
                    except:
                        image_widget.setText("❌")

                    self.table.setCellWidget(row, 5, image_widget)
                    image_item.setToolTip(f"Ảnh: {image_url}")
                else:
                    image_item.setText("Không có")
                self.table.setItem(row, 5, image_item)

                # Số sản phẩm
                product_count = self.get_category_product_count(category)
                self.table.setItem(row, 6,
                                   QTableWidgetItem(str(product_count)))

                # Parent - hiển thị tên parent thay vì ID
                parent_name = ""
                parent_id = category.get('parent_id')
                if parent_id and parent_id in local_id_to_category:
                    parent_name = local_id_to_category[parent_id].get(
                        'name', '')
                self.table.setItem(row, 7, QTableWidgetItem(parent_name))

                # WC ID
                wc_id = category.get('wc_category_id', '')
                self.table.setItem(
                    row, 8, QTableWidgetItem(str(wc_id) if wc_id else ""))

        except Exception as e:
            self.logger.error(f"Lỗi hiển thị categories: {str(e)}")
            QMessageBox.critical(self, "Lỗi",
                                 f"Không thể hiển thị categories:\n{str(e)}")
        finally:
            # Reconnect signal sau khi populate xong data
            try:
                self.table.itemChanged.connect(self.on_item_changed)
            except:
                pass  # Signal có thể đã được kết nối rồi

    def create_category_tree_item(self, category: Dict):
        """Tạo tree item cho một category"""
        try:
            # Lấy thông tin site
            site_name = ""
            if category.get('site_id'):
                site = self.db.get_site_by_id(category['site_id'])
                if site:
                    site_name = site.name if hasattr(site, 'name') else str(
                        site.get('name', ''))

            # Lấy số lượng sản phẩm
            product_count = self.get_category_product_count(category)

            # Tạo item với các cột
            item = QTreeWidgetItem([
                str(category.get('name', '')),  # Tên danh mục
                str(category.get('slug', '')),  # Slug
                str(product_count),  # Số sản phẩm
                site_name,  # Site
                str(category.get('wc_category_id', '')),  # WC ID
                str(category.get('description', ''))[:100]  # Mô tả (rút gọn)
            ])

            # Lưu data vào item
            item.setData(0, Qt.ItemDataRole.UserRole, category)

            # Đặt icon cho danh mục cha
            if category.get('parent_id', 0) == 0:
                item.setIcon(
                    0,
                    self.style().standardIcon(
                        self.style().StandardPixmap.SP_DirIcon))
            else:
                item.setIcon(
                    0,
                    self.style().standardIcon(
                        self.style().StandardPixmap.SP_FileIcon))

            return item

        except Exception as e:
            self.logger.error(f"Lỗi tạo tree item: {str(e)}")
            return QTreeWidgetItem([str(category.get('name', 'Lỗi'))])

    def add_children_recursive(self, parent_item, parent_id, parent_children,
                               category_dict):
        """Thêm children cho parent item một cách đệ quy"""
        if parent_id in parent_children:
            for child_category in parent_children[parent_id]:
                child_item = self.create_category_tree_item(child_category)
                parent_item.addChild(child_item)

                # Đệ quy thêm children của children
                child_id = child_category.get('id')
                self.add_children_recursive(child_item, child_id,
                                            parent_children, category_dict)

    def get_category_product_count(self, category: Dict) -> int:
        """Lấy số lượng sản phẩm trong category"""
        try:
            # Ưu tiên lấy từ count field trong database
            if 'count' in category and category['count'] is not None:
                return int(category['count'])

            # Nếu không có, thử lấy từ database products
            category_id = category.get('id')
            if category_id and hasattr(self.db, 'get_products_by_category'):
                products = self.db.get_products_by_category(category_id)
                return len(products) if products else 0

            return 0

        except Exception as e:
            self.logger.error(f"Lỗi lấy product count: {str(e)}")
            return 0

    def filter_categories(self):
        """Lọc categories theo site và search"""
        try:
            site_id = self.site_combo.currentData()
            site_text = self.site_combo.currentText()
            search_term = self.search_edit.text().lower()

            # Debug logging
            self.logger.debug(f"Filtering categories - Site ID: {site_id}, Site Text: {site_text}, Search: {search_term}")

            # Kiểm tra điều kiện lọc site - chỉ lọc khi chọn site cụ thể
            if site_id and site_id != 0 and site_text != "Tất cả sites":  
                categories = self.db.get_categories_by_site(site_id)
                self.logger.debug(f"Found {len(categories)} categories for site_id {site_id}")
            else:
                categories = self.db.get_all_categories()
                self.logger.debug(f"Found {len(categories)} total categories")

            # Debug: Log first few categories to check data
            if categories:
                for i, category in enumerate(categories[:3]):
                    self.logger.debug(f"Category {i}: site_id={category.get('site_id')}, site_name={category.get('site_name')}, name={category.get('name')}")

            # Filter by search term
            if search_term:
                filtered_categories = []
                for category in categories:
                    name = category.get('name', '')
                    if isinstance(name, dict):
                        name = name.get('rendered', '')

                    if (search_term in str(name).lower() or 
                        search_term in str(category.get('slug', '')).lower()):
                        filtered_categories.append(category)
                categories = filtered_categories

            self.display_categories(categories)
            self.update_stats(categories)

        except Exception as e:
            self.logger.error(f"Lỗi filter categories: {str(e)}")

    def update_stats(self, categories: List[Dict]):
        """Cập nhật thống kê"""
        try:
            total = len(categories)
            synced = len(
                [cat for cat in categories if cat.get('wc_category_id')])
            parents = len([
                cat for cat in categories
                if not cat.get('parent_id') or cat.get('parent_id') == 0
            ])
            children = total - parents

            self.total_label.setText(f"Tổng: {total}")
            self.synced_label.setText(f"Đã đồng bộ: {synced}")
            self.parent_label.setText(f"Danh mục cha: {parents}")
            self.child_label.setText(f"Danh mục con: {children}")

        except Exception as e:
            self.logger.error(f"Lỗi update stats: {str(e)}")

    def on_selection_changed(self):
        """Xử lý khi selection thay đổi"""
        selected_rows = self.table.selectionModel().selectedRows()
        has_selection = len(selected_rows) > 0

        self.edit_btn.setEnabled(has_selection)
        self.delete_btn.setEnabled(has_selection)

        if has_selection:
            row = selected_rows[0].row()
            item = self.table.item(row, 0)
            if item:
                category_data = item.data(Qt.ItemDataRole.UserRole)
                if category_data:
                    self.show_category_details(category_data)
        else:
            self.details_text.clear()

    def show_category_details(self, category: Dict):
        """Hiển thị chi tiết category"""
        try:
            name = category.get('name', '')
            description = category.get('description', '')

            # Tìm parent name
            parent_name = "Không có"
            parent_id = category.get('parent_id')
            if parent_id and parent_id != 0:
                # Tìm parent trong danh sách categories
                all_categories = self.db.get_all_categories()
                for cat in all_categories:
                    if cat.get('id') == parent_id or cat.get(
                            'wc_category_id') == parent_id:
                        parent_name = cat.get('name', f'ID: {parent_id}')
                        break

            details = f"""
<h3>{name}</h3>
<p><b>ID:</b> {category.get('id', 'N/A')}</p>
<p><b>Slug:</b> {category.get('slug', 'N/A')}</p>
<p><b>Trạng thái:</b> {'Đã đồng bộ' if category.get('wc_category_id') else 'Chưa đồng bộ'}</p>
<p><b>Số sản phẩm:</b> {category.get('count', 0)}</p>
<p><b>Danh mục cha:</b> {parent_name}</p>
<p><b>WooCommerce ID:</b> {category.get('wc_category_id', 'Chưa đồng bộ')}</p>
<p><b>Cập nhật:</b> {category.get('updated_at', 'N/A')}</p>
<p><b>Mô tả:</b></p>
<p>{description[:300] + '...' if len(str(description)) > 300 else description}</p>
            """

            self.details_text.setHtml(details)

        except Exception as e:
            self.logger.error(f"Lỗi show category details: {str(e)}")

    def sync_categories(self):
        """Đồng bộ categories từ site được chọn"""
        # Lấy site được chọn
        site_id = self.site_combo.currentData()

        if not site_id:
            QMessageBox.warning(self, "Cảnh báo", 
                                "Vui lòng chọn một site cụ thể để đồng bộ danh mục.\n\n"
                                "Không thể đồng bộ khi chọn 'Tất cả sites'.")
            return

        site = self.db.get_site_by_id(site_id)
        if not site:
            QMessageBox.warning(self, "Cảnh báo",
                                "Không tìm thấy thông tin site")
            return

        # Hiển thị xác nhận
        reply = QMessageBox.question(
            self, "Xác nhận đồng bộ",
            f"Bạn có muốn đồng bộ danh mục từ site '{site.name}' không?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.start_sync(site)            
    def start_sync(self, site):
        """Bắt đầu đồng bộ categories"""
        if self.sync_worker and self.sync_worker.isRunning():
            QMessageBox.warning(self, "Cảnh báo",
                                "Đang có tiến trình đồng bộ khác")
            return

        # Disable buttons
        self.sync_btn.setEnabled(False)
        if hasattr(self, 'progress_bar'):
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
        if hasattr(self, 'status_label'):
            self.status_label.setText("Đang đồng bộ...")

        # Start worker
        self.sync_worker = CategorySyncWorker(site)
        self.sync_worker.progress_updated.connect(self.on_sync_progress)
        self.sync_worker.finished.connect(self.on_sync_finished)
        self.sync_worker.category_synced.connect(self.on_category_synced)
        self.sync_worker.start()

    def on_sync_progress(self, value: int, status: str):
        """Cập nhật tiến độ sync"""
        if hasattr(self, 'progress_bar'):
            self.progress_bar.setValue(value)
        if hasattr(self, 'status_label'):
            self.status_label.setText(status)

    def on_sync_finished(self, success: bool, message: str):
        """Xử lý khi sync hoàn thành"""
        self.sync_btn.setEnabled(True)
        if hasattr(self, 'progress_bar'):
            self.progress_bar.setVisible(False)
        if hasattr(self, 'status_label'):
            self.status_label.setText("Sẵn sàng")

        if success:
            QMessageBox.information(self, "Thành công", message)
            # Áp dụng lại bộ lọc thay vì load tất cả
            self.filter_categories()
        else:
            QMessageBox.critical(self, "Lỗi", message)

    def on_category_synced(self, category_data: Dict):
        """Xử lý khi một category được sync"""
        # Có thể cập nhật real-time nếu cần
        pass

    def create_category_on_site(self, category_data: Dict):
        """Tạo danh mục trực tiếp trên site và đồng bộ về"""
        try:
            # Disable buttons
            self.add_btn.setEnabled(False)
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            self.status_label.setText("Đang tạo danh mục trên site...")

            # Lấy thông tin site
            site_id = category_data.get('site_id')
            site = self.db.get_site_by_id(site_id)
            if not site:
                QMessageBox.warning(self, "Lỗi",
                                    "Không tìm thấy thông tin site")
                return

            # Khởi tạo API
            from .woocommerce_api import WooCommerceAPI
            api = WooCommerceAPI(site)

            self.progress_bar.setValue(30)
            self.status_label.setText("Chuẩn bị dữ liệu...")

            # Chuẩn bị dữ liệu cho WooCommerce API
            wc_category_data = {
                'name':
                category_data['name'],
                'slug':
                category_data['slug'],
                'description':
                category_data.get('description', ''),
                'parent':
                category_data.get('parent', 0)
                if category_data.get('parent') else 0,
                'display':
                category_data.get('display', 'default'),
                'menu_order':
                category_data.get('menu_order', 0)
            }

            # Thêm image nếu có
            if category_data.get('image'):
                wc_category_data['image'] = {'src': category_data['image']}

            self.progress_bar.setValue(50)
            self.status_label.setText("Tạo danh mục trên site...")

            # Tạo danh mục trên WooCommerce
            created_category = api.create_category(wc_category_data)

            self.progress_bar.setValue(80)
            self.status_label.setText("Lưu vào database...")

            if created_category:
                # Lưu vào database local với wc_category_id
                category_data['wc_category_id'] = created_category.get('id')
                self.db.create_category(category_data)

                self.progress_bar.setValue(100)
                self.status_label.setText("Hoàn thành!")

                # Reload categories
                self.load_categories()

                QMessageBox.information(
                    self, "Thành công",
                    f"Đã tạo danh mục '{category_data['name']}' trên site và đồng bộ về database!"
                )
            else:
                # Nếu tạo trên site thất bại, hỏi user có muốn lưu local không
                reply = QMessageBox.question(
                    self, "Lỗi tạo trên site",
                    f"Không thể tạo danh mục '{category_data['name']}' trên site.\n\n"
                    "Bạn có muốn lưu chỉ trong database local không?",
                    QMessageBox.StandardButton.Yes
                    | QMessageBox.StandardButton.No)

                if reply == QMessageBox.StandardButton.Yes:
                    # Xóa wc_category_id nếu có
                    category_data.pop('wc_category_id', None)
                    self.db.create_category(category_data)
                    self.load_categories()
                    QMessageBox.information(
                        self, "Thành công",
                        "Đã lưu danh mục vào database local!")

        except Exception as e:
            error_msg = str(e)
            self.logger.error(f"Lỗi tạo category: {error_msg}")

            # Kiểm tra loại lỗi để đưa ra thông báo phù hợp
            if "Consumer Key không có quyền" in error_msg or "insufficient_permission" in error_msg or "403" in error_msg:
                QMessageBox.warning(
                    self, "Lỗi quyền hạn", f"❌ {error_msg}\n\n"
                    "💡 Giải pháp:\n"
                    "1. Vào WooCommerce Admin → WooCommerce → Settings → Advanced → REST API\n"
                    "2. Chỉnh sửa Consumer Key hiện tại\n"
                    "3. Đảm bảo Permissions = 'Read/Write'\n"
                    "4. Hoặc tạo Consumer Key mới với quyền Read/Write\n\n"
                    "🔧 Lưu ý: Consumer Key chỉ có quyền 'Read' không thể tạo/sửa dữ liệu"
                )
            elif "401" in error_msg or "xác thực" in error_msg:
                QMessageBox.warning(
                    self, "Lỗi xác thực", f"❌ {error_msg}\n\n"
                    "💡 Kiểm tra lại:\n"
                    "1. Consumer Key và Consumer Secret có đúng không\n"
                    "2. URL site có chính xác không\n"
                    "3. WooCommerce REST API có được kích hoạt không")
            elif "500" in error_msg or "Internal Server Error" in error_msg:
                QMessageBox.critical(
                    self, "Lỗi Server",
                    f"❌ Lỗi server khi tạo category:\n{error_msg}\n\n"
                    "💡 Có thể do:\n"
                    "1. Category name đã tồn tại\n"
                    "2. Slug đã được sử dụng\n"
                    "3. Dữ liệu category không hợp lệ\n"
                    "4. Plugin WooCommerce có vấn đề\n"
                    "5. Database server quá tải\n\n"
                    "🔧 Thử lại:\n"
                    "- Đổi tên category khác\n"
                    "- Kiểm tra tên category có ký tự đặc biệt không\n"
                    "- Liên hệ admin website kiểm tra server")
            elif "đã tồn tại" in error_msg or "already exists" in error_msg:
                QMessageBox.warning(
                    self, "Category đã tồn tại", f"❌ {error_msg}\n\n"
                    "💡 Giải pháp:\n"
                    "1. Thay đổi tên category\n"
                    "2. Hoặc sử dụng category có sẵn")
            elif "không hợp lệ" in error_msg or "invalid" in error_msg.lower():
                QMessageBox.warning(
                    self, "Dữ liệu không hợp lệ", f"❌ {error_msg}\n\n"
                    "💡 Kiểm tra lại:\n"
                    "1. Tên category không để trống\n"
                    "2. Slug chỉ chứa chữ, số và dấu gạch ngang\n"
                    "3. Parent category có tồn tại không")
            else:
                QMessageBox.critical(self, "Lỗi",
                                     f"Không thể tạo danh mục:\n{error_msg}")
        finally:
            # Re-enable buttons và ẩn progress
            self.add_btn.setEnabled(True)
            self.progress_bar.setVisible(False)
            self.status_label.setText("Sẵn sàng")

    def update_category_on_site(self, category_id: int, category_data: Dict,
                                wc_category_id: int):
        """Cập nhật danh mục trực tiếp trên site và đồng bộ về"""
        try:
            # Disable buttons
            self.edit_btn.setEnabled(False)
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            self.status_label.setText("Đang cập nhật danh mục trên site...")

            # Lấy thông tin site
            site_id = category_data.get('site_id')
            site = self.db.get_site_by_id(site_id)
            if not site:
                QMessageBox.warning(self, "Lỗi",
                                    "Không tìm thấy thông tin site")
                return

            # Khởi tạo API
            from .woocommerce_api import WooCommerceAPI
            api = WooCommerceAPI(site)

            self.progress_bar.setValue(30)
            self.status_label.setText("Chuẩn bị dữ liệu...")

            # Chuẩn bị dữ liệu cho WooCommerce API
            wc_category_data = {
                'name':
                category_data['name'],
                'slug':
                category_data['slug'],
                'description':
                category_data.get('description', ''),
                'parent':
                category_data.get('parent_id', 0)
                if category_data.get('parent_id') else 0
            }

            # Thêm image nếu có
            if category_data.get('image'):
                wc_category_data['image'] = {'src': category_data['image']}

            self.progress_bar.setValue(50)
            self.status_label.setText("Cập nhật danh mục trên site...")

            # Cập nhật category trên WooCommerce
            result = api.update_category(wc_category_id, wc_category_data)

            if result:
                self.progress_bar.setValue(70)
                self.status_label.setText("Cập nhật database...")

                # Cập nhật dữ liệu từ response
                category_data['count'] = result.get('count', 0)

                # Cập nhật image URL từ response nếu có
                if result.get('image') and result['image'].get('src'):
                    category_data['image'] = result['image']['src']

                self.db.update_category(category_id, category_data)

                self.progress_bar.setValue(100)
                self.status_label.setText("Hoàn thành!")

                # Reload categories để hiển thị
                self.load_categories()

                QMessageBox.information(
                    self, "Thành công",
                    f"Đã cập nhật danh mục '{category_data['name']}' thành công!\n"
                    f"WooCommerce ID: {result.get('id')}")
            else:
                raise Exception("Không nhận được response từ WooCommerce API")

        except Exception as e:
            self.logger.error(f"Lỗi cập nhật category trên site: {str(e)}")
            QMessageBox.critical(
                self, "Lỗi",
                f"Không thể cập nhật danh mục trên site:\n{str(e)}\n\n"
                "Bạn có muốn cập nhật trong database local không?")

            # Hỏi có muốn cập nhật local không
            reply = QMessageBox.question(
                self, "Cập nhật database local?",
                "Cập nhật trên site thất bại. Bạn có muốn cập nhật danh mục trong database local không?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes)

            if reply == QMessageBox.StandardButton.Yes:
                try:
                    self.db.update_category(category_id, category_data)
                    self.load_categories()
                    QMessageBox.information(
                        self, "Thành công",
                        "Đã cập nhật danh mục trong database local!")
                except Exception as local_error:
                    QMessageBox.critical(
                        self, "Lỗi",
                        f"Không thể cập nhật database local: {str(local_error)}"
                    )

        finally:
            # Restore UI
            self.edit_btn.setEnabled(True)
            self.progress_bar.setVisible(False)
            self.status_label.setText("Sẵn sàng")

    def bulk_add_categories(self):
        """Tạo nhiều danh mục theo cấu trúc cây"""
        try:
            sites = self.db.get_active_sites()
            if not sites:
                QMessageBox.warning(self, "Cảnh báo",
                                    "Không có site nào hoạt động")
                return

            dialog = BulkCategoryDialog(self, sites=sites)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                result_data = dialog.get_result_data()
                if result_data:
                    site_id, categories = result_data
                    self.create_bulk_categories(site_id, categories)

        except Exception as e:
            self.logger.error(f"Lỗi tạo bulk categories: {str(e)}")
            QMessageBox.critical(
                self, "Lỗi", f"Không thể tạo danh mục hàng loạt:\n{str(e)}")

    def create_bulk_categories(self, site_id: int, categories: List[Dict]):
        """Tạo danh mục hàng loạt với tối ưu hóa duplicate detection"""
        try:
            # Disable buttons
            self.bulk_add_btn.setEnabled(False)
            self.add_btn.setEnabled(False)
            self.progress_bar.setVisible(True)
            self.progress_bar.setMaximum(len(categories))
            self.progress_bar.setValue(0)

            site = self.db.get_site_by_id(site_id)
            if not site:
                QMessageBox.warning(self, "Lỗi", "Không tìm thấy thông tin site")
                return

            # Khởi tạo API
            from .woocommerce_api import WooCommerceAPI
            api = WooCommerceAPI(site)

            # Lấy danh sách categories hiện có trên site
            self.status_label.setText("Đang lấy danh sách categories hiện có...")
            existing_categories = api.get_categories()

            # Tạo lookup table cho categories hiện có theo tên và slug
            existing_lookup = {}
            for cat in existing_categories:
                name = cat.get('name', '').lower().strip()
                slug = cat.get('slug', '').lower().strip()
                if name:
                    existing_lookup[name] = cat
                if slug and slug != name:
                    existing_lookup[slug] = cat

            self.logger.info(f"Tìm thấy {len(existing_categories)} categories hiện có trên site")

            created_categories = []
            updated_categories = []
            parent_mapping = {}  # Mapping local index -> WC category ID
            errors = []

            # Tạo từng danh mục theo thứ tự
            for index, category_data in enumerate(categories):
                try:
                    category_name = category_data['name']
                    category_slug = category_data['slug']

                    self.status_label.setText(f"Đang xử lý: {category_name}...")
                    self.progress_bar.setValue(index)
                    QApplication.processEvents()

                    # Kiểm tra xem category đã tồn tại chưa
                    existing_category = None
                    name_key = category_name.lower().strip()
                    slug_key = category_slug.lower().strip()

                    if name_key in existing_lookup:
                        existing_category = existing_lookup[name_key]
                        self.logger.info(f"Tìm thấy category '{category_name}' theo tên")
                    elif slug_key in existing_lookup:
                        existing_category = existing_lookup[slug_key]
                        self.logger.info(f"Tìm thấy category '{category_name}' theo slug")

                    if existing_category:
                        # Category đã tồn tại, sử dụng lại
                        wc_category_id = existing_category.get('id')
                        parent_mapping[index] = wc_category_id

                        # Cập nhật thông tin trong database local nếu chưa có
                        local_category = self.db.get_category_by_wc_id(site_id, wc_category_id)
                        if not local_category:
                            local_category_data = {
                                'site_id': site_id,
                                'wc_category_id': wc_category_id,
                                'name': existing_category.get('name', category_name),
                                'slug': existing_category.get('slug', category_slug),
                                'description': existing_category.get('description', ''),
                                'parent_id': existing_category.get('parent', 0) if existing_category.get('parent', 0) > 0 else None,
                                'count': existing_category.get('count', 0),
                                'image': existing_category.get('image', {}).get('src', '') if existing_category.get('image') else ''
                            }
                            self.db.create_category(local_category_data)

                        updated_categories.append(f"{category_name} (đã tồn tại - ID: {wc_category_id})")
                        self.logger.info(f"Sử dụng lại category '{category_name}' (WC ID: {wc_category_id})")
                        continue

                    # Category chưa tồn tại, tạo mới
                    wc_category_data = {
                        'name': category_name,
                        'slug': category_slug,
                        'description': category_data.get('description', ''),
                        'parent': 0  # Mặc định là root
                    }

                    # Xử lý parent category nếu có
                    if category_data.get('parent_id') is not None:
                        parent_index = category_data['parent_id']
                        if parent_index in parent_mapping:
                            wc_category_data['parent'] = parent_mapping[parent_index]
                            self.logger.info(f"Set parent cho '{category_name}': {parent_mapping[parent_index]}")

                    # Tạo category mới trên WooCommerce
                    self.logger.info(f"Tạo category mới: {category_name}")
                    created_category = api.create_category(wc_category_data)

                    if created_category:
                        wc_category_id = created_category.get('id')
                        parent_mapping[index] = wc_category_id

                        # Lưu vào database local
                        local_category_data = {
                            'site_id': site_id,
                            'wc_category_id': wc_category_id,
                            'name': category_name,
                            'slug': category_slug,
                            'description': category_data.get('description', ''),
                            'parent_id': wc_category_data['parent'] if wc_category_data['parent'] > 0 else None,
                            'count': created_category.get('count', 0),
                            'image': created_category.get('image', {}).get('src', '') if created_category.get('image') else ''
                        }

                        self.db.create_category(local_category_data)
                        created_categories.append(f"{category_name} (mới - ID: {wc_category_id})")

                        # Cập nhật lookup table
                        existing_lookup[category_name.lower().strip()] = created_category
                        existing_lookup[category_slug.lower().strip()] = created_category

                        self.logger.info(f"Đã tạo category mới: {category_name} (WC ID: {wc_category_id})")
                    else:
                        errors.append(f"Không thể tạo category '{category_name}' trên site")

                except Exception as e:
                    error_msg = f"Lỗi xử lý '{category_data.get('name', 'Unknown')}': {str(e)}"
                    errors.append(error_msg)
                    self.logger.error(error_msg)

            # Hoàn thành
            self.progress_bar.setValue(len(categories))
            self.status_label.setText("Hoàn thành!")

            # Reload categories để hiển thị cập nhật
            self.load_categories()

            # Hiển thị kết quả chi tiết
            self.show_bulk_creation_results(created_categories, updated_categories, errors)

        except Exception as e:
            self.logger.error(f"Lỗi tạo bulk categories: {str(e)}")
            QMessageBox.critical(
                self, "Lỗi nghiêm trọng",
                f"Không thể hoàn thành quá trình tạo danh mục:\n{str(e)}")
        finally:
            # Restore UI
            self.bulk_add_btn.setEnabled(True)
            self.add_btn.setEnabled(True)
            self.progress_bar.setVisible(False)
            self.status_label.setText("Sẵn sàng")

    def show_bulk_creation_results(self, created_categories: List[str], updated_categories: List[str], errors: List[str]):
        """Hiển thị kết quả tạo bulk categories"""
        try:
            total_processed = len(created_categories) + len(updated_categories)

            message = f"📊 **KẾT QUẢ TẠO DANH MỤC**\n\n"

            if created_categories:
                message += f"✅ **Đã tạo mới {len(created_categories)} danh mục:**\n"
                for cat in created_categories[:10]:  # Hiển thị tối đa 10
                    message += f"  • {cat}\n"
                if len(created_categories) > 10:
                    message += f"  ... và {len(created_categories) - 10} danh mục khác\n"
                message += "\n"

            if updated_categories:
                message += f"🔄 **Đã sử dụng lại {len(updated_categories)} danh mục có sẵn:**\n"
                for cat in updated_categories[:10]:  # Hiển thị tối đa 10
                    message += f"  • {cat}\n"
                if len(updated_categories) > 10:
                    message += f"  ... và {len(updated_categories) - 10} danh mục khác\n"
                message += "\n"

            if errors:
                message += f"❌ **Có {len(errors)} lỗi:**\n"
                for error in errors[:5]:  # Hiển thị tối đa 5 lỗi
                    message += f"  • {error}\n"
                if len(errors) > 5:
                    message += f"  ... và {len(errors) - 5} lỗi khác\n"

            if total_processed > 0:
                message += f"\n📈 **Tổng kết:** {total_processed}/{total_processed + len(errors)} danh mục được xử lý thành công"

            # Chọn icon và title phù hợp
            if errors and not total_processed:
                icon = QMessageBox.Icon.Critical
                title = "Tạo danh mục thất bại"
            elif errors and total_processed:
                icon = QMessageBox.Icon.Warning
                title = "Tạo danh mục hoàn thành (có lỗi)"
            else:
                icon = QMessageBox.Icon.Information
                title = "Tạo danh mục thành công"

            msg_box = QMessageBox(self)
            msg_box.setIcon(icon)
            msg_box.setWindowTitle(title)
            msg_box.setText(message)
            msg_box.exec()

        except Exception as e:
            self.logger.error(f"Lỗi hiển thị kết quả: {str(e)}")
            QMessageBox.information(
                self, "Hoàn thành", 
                f"Đã xử lý {len(created_categories)} danh mục mới và {len(updated_categories)} danh mục có sẵn")

    def add_category(self):
        """Thêm danh mục mới"""
        try:
            sites = self.db.get_active_sites()
            if not sites:
                QMessageBox.warning(self, "Cảnh báo",
                                    "Không có site nào hoạt động")
                return

            categories = self.db.get_all_categories()

            dialog = CategoryDialog(self, sites=sites, categories=categories)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                category_data = dialog.get_category_data()

                # Hiển thị dialog xác nhận
                reply = QMessageBox.question(
                    self, "Xác nhận tạo danh mục",
                    f"Bạn có muốn tạo danh mục '{category_data['name']}' trực tiếp lên site không?\n\n"
                    "Chọn 'Yes' để tạo lên site và đồng bộ về\n"
                    "Chọn 'No' để chỉ tạo trong database local",
                    QMessageBox.StandardButton.Yes
                    | QMessageBox.StandardButton.No
                    | QMessageBox.StandardButton.Cancel,
                    QMessageBox.StandardButton.Yes)

                if reply == QMessageBox.StandardButton.Cancel:
                    return
                elif reply == QMessageBox.StandardButton.Yes:
                    # Tạo trên site và đồng bộ về
                    self.create_category_on_site(category_data)
                else:
                    # Chỉ tạo trong database local
                    self.db.create_category(category_data)
                    self.load_categories()
                    QMessageBox.information(
                        self, "Thành công",
                        "Đã thêm danh mục vào database local!")

        except Exception as e:
            error_msg = str(e)
            self.logger.error(f"Lỗi tạo category: {error_msg}")

            # Kiểm tra loại lỗi để đưa ra thông báo phù hợp
            if "Consumer Key không có quyền" in error_msg or "insufficient_permission" in error_msg or "403" in error_msg:
                QMessageBox.warning(
                    self, "Lỗi quyền hạn", f"❌ {error_msg}\n\n"
                    "💡 Giải pháp:\n"
                    "1. Vào WooCommerce Admin → WooCommerce → Settings → Advanced → REST API\n"
                    "2. Chỉnh sửa Consumer Key hiện tại\n"
                    "3. Đảm bảo Permissions = 'Read/Write'\n"
                    "4. Hoặc tạo Consumer Key mới với quyền Read/Write\n\n"
                    "🔧 Lưu ý: Consumer Key chỉ có quyền 'Read' không thể tạo/sửa dữ liệu"
                )
            elif "401" in error_msg or "xác thực" in error_msg:
                QMessageBox.warning(
                    self, "Lỗi xác thực", f"❌ {error_msg}\n\n"
                    "💡 Kiểm tra lại:\n"
                    "1. Consumer Key và Consumer Secret có đúng không\n"
                    "2. URL site có chính xác không\n"
                    "3. WooCommerce REST API có được kích hoạt không")
            else:
                QMessageBox.critical(self, "Lỗi",
                                     f"Không thể tạo danh mục:\n{error_msg}")
        finally:
            # Re-enable buttons và ẩn progress
            self.add_btn.setEnabled(True)
            self.progress_bar.setVisible(False)
            self.status_label.setText("Sẵn sàng")

    def edit_category(self):
        """Sửa danh mục đã chọn"""
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            return

        row = selected_rows[0].row()
        item = self.table.item(row, 0)
        if not item:
            return

        category_data = item.data(Qt.ItemDataRole.UserRole)
        if not category_data:
            return

        try:
            sites = self.db.get_active_sites()
            categories = self.db.get_all_categories()
            category_id = category_data.get('id')

            dialog = CategoryDialog(self,
                                    sites=sites,
                                    category=category_data,
                                    categories=categories)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                updated_data = dialog.get_category_data()

                # Kiểm tra xem category có WC ID không
                wc_category_id = category_data.get('wc_category_id')

                if wc_category_id:
                    # Hiển thị dialog xác nhận
                    reply = QMessageBox.question(
                        self, "Xác nhận cập nhật danh mục",
                        f"Danh mục này đã được đồng bộ với WooCommerce (ID: {wc_category_id}).\n\n"
                        "Bạn có muốn cập nhật trên site không?\n\n"
                        "Chọn 'Yes' để cập nhật trên site và đồng bộ về\n"
                        "Chọn 'No' để chỉ cập nhật trong database local",
                        QMessageBox.StandardButton.Yes
                        | QMessageBox.StandardButton.No
                        | QMessageBox.StandardButton.Cancel,
                        QMessageBox.StandardButton.Yes)

                    if reply == QMessageBox.StandardButton.Cancel:
                        return
                    elif reply == QMessageBox.StandardButton.Yes:
                        # Cập nhật trên site
                        self.update_category_on_site(category_id, updated_data,
                                                     wc_category_id)
                        return

                # Chỉ cập nhật trong database local
                self.db.update_category(category_id, updated_data)
                self.load_categories()
                QMessageBox.information(
                    self, "Thành công",
                    "Đã cập nhật danh mục trong database local!")

        except Exception as e:
            self.logger.error(f"Lỗi sửa category: {str(e)}")
            QMessageBox.critical(self, "Lỗi",
                                 f"Không thể cập nhật danh mục: {str(e)}")

    def delete_multiple_categories(self, categories_to_delete: list):
        """Xóa nhiều categories cùng lúc"""
        total_categories = len(categories_to_delete)

        # Tạo progress dialog
        progress = QProgressDialog("Đang xóa categories...", "Hủy", 0,
                                   total_categories, self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setAutoReset(False)
        progress.setAutoClose(False)

        successful_deletions = []
        failed_deletions = []

        for i, category_info in enumerate(categories_to_delete):
            if progress.wasCanceled():
                break

            progress.setValue(i)
            progress.setLabelText(f"Đang xóa '{category_info['name']}'...")
            QApplication.processEvents()

            try:
                success = self.delete_single_category(category_info['id'],
                                                      category_info['wc_id'],
                                                      category_info['name'],
                                                      show_dialogs=False)

                if success:
                    successful_deletions.append(category_info['name'])
                else:
                    failed_deletions.append(category_info['name'])

            except Exception as e:
                self.logger.error(
                    f"Lỗi xóa category {category_info['name']}: {str(e)}")
                failed_deletions.append(category_info['name'])

        progress.setValue(total_categories)
        progress.close()

        # Reload categories
        self.load_categories()

        # Hiển thị kết quả
        self.show_deletion_results(successful_deletions, failed_deletions)

    def delete_single_category(self,
                               category_id: int,
                               wc_category_id: int,
                               category_name: str,
                               show_dialogs: bool = True) -> bool:
        """Xóa một category đơn lẻ"""
        try:
            # Lấy site info
            category = self.db.get_category_by_id(category_id)
            if not category:
                return False

            # category là dict, nên sử dụng ['site_id'] thay vì .site_id
            site_id = category.get('site_id')
            if not site_id:
                if show_dialogs:
                    QMessageBox.warning(
                        self, "Cảnh báo",
                        "Không tìm thấy site_id cho category này")
                return False

            site = self.db.get_site_by_id(site_id)
            if not site:
                if show_dialogs:
                    QMessageBox.warning(self, "Cảnh báo",
                                        "Không tìm thấy thông tin site")
                return False

            # Khởi tạo API
            api = WooCommerceAPI(site)

            # Xóa từ WooCommerce
            success = api.delete_category(wc_category_id, force=True)

            if success:
                # Xóa từ database local
                self.db.delete_category(category_id)
                return True
            else:
                # Nếu không hiển thị dialog, chỉ xóa local
                if not show_dialogs:
                    self.db.delete_category(category_id)
                    return True
                else:
                    return self.handle_delete_failure(category_id,
                                                      wc_category_id,
                                                      category_name)

        except Exception as e:
            self.logger.error(f"Lỗi xóa category từ site: {str(e)}")
            if show_dialogs:
                QMessageBox.critical(self, "Lỗi",
                                     f"Lỗi xóa category: {str(e)}")
            return False

    def handle_delete_failure(self, category_id: int, wc_category_id: int,
                              category_name: str) -> bool:
        """Xử lý khi xóa thất bại"""
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Icon.Question)
        msg_box.setWindowTitle("Lỗi xóa từ site")
        msg_box.setText(
            f"Không thể xóa category '{category_name}' từ site.\n\nBạn muốn:")

        only_local_btn = msg_box.addButton("Chỉ xóa local", QMessageBox.ButtonRole.AcceptRole)
        cancel_btn = msg_box.addButton("Hủy", QMessageBox.ButtonRole.RejectRole)
        
        msg_box.exec()
        
        if msg_box.clickedButton() == only_local_btn:
            try:
                self.db.delete_category(category_id)
                return True
            except Exception as e:
                self.logger.error(f"Lỗi xóa category từ database local: {str(e)}")
                return False
        
        return False

    def show_deletion_results(self, successful_deletions: list, failed_deletions: list):
        """Hiển thị kết quả xóa categories"""
        try:
            message = "📊 **KẾT QUẢ XÓA CATEGORIES**\n\n"
            
            if successful_deletions:
                message += f"✅ **Đã xóa thành công {len(successful_deletions)} categories:**\n"
                for cat in successful_deletions[:10]:
                    message += f"  • {cat}\n"
                if len(successful_deletions) > 10:
                    message += f"  ... và {len(successful_deletions) - 10} categories khác\n"
                message += "\n"
            
            if failed_deletions:
                message += f"❌ **Xóa thất bại {len(failed_deletions)} categories:**\n"
                for cat in failed_deletions[:5]:
                    message += f"  • {cat}\n"
                if len(failed_deletions) > 5:
                    message += f"  ... và {len(failed_deletions) - 5} categories khác\n"
            
            # Chọn icon và title phù hợp
            if failed_deletions and not successful_deletions:
                icon = QMessageBox.Icon.Critical
                title = "Xóa categories thất bại"
            elif failed_deletions and successful_deletions:
                icon = QMessageBox.Icon.Warning
                title = "Xóa categories hoàn thành (có lỗi)"
            else:
                icon = QMessageBox.Icon.Information
                title = "Xóa categories thành công"
            
            msg_box = QMessageBox(self)
            msg_box.setIcon(icon)
            msg_box.setWindowTitle(title)
            msg_box.setText(message)
            msg_box.exec()
            
        except Exception as e:
            self.logger.error(f"Lỗi hiển thị kết quả xóa: {str(e)}")
            QMessageBox.information(
                self, "Hoàn thành", 
                f"Đã xóa {len(successful_deletions)} categories thành công")

    def delete_category(self):
        """Xóa danh mục đã chọn (có thể xóa nhiều)"""
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.warning(self, "Cảnh báo", "Vui lòng chọn ít nhất một danh mục để xóa")
            return

        # Lấy thông tin các categories cần xóa
        categories_to_delete = []
        for row in selected_rows:
            item = self.table.item(row.row(), 0)
            if item:
                category_data = item.data(Qt.ItemDataRole.UserRole)
                if category_data:
                    categories_to_delete.append({
                        'id': category_data.get('id'),
                        'wc_id': category_data.get('wc_category_id'),
                        'name': category_data.get('name', 'Không rõ')
                    })

        if not categories_to_delete:
            QMessageBox.warning(self, "Cảnh báo", "Không tìm thấy dữ liệu category để xóa")
            return

        # Xác nhận xóa
        category_names = [cat['name'] for cat in categories_to_delete]
        if len(categories_to_delete) == 1:
            message = f"Bạn có chắc muốn xóa danh mục '{category_names[0]}'?"
        else:
            message = f"Bạn có chắc muốn xóa {len(categories_to_delete)} danh mục đã chọn?\n\n"
            message += "Danh sách:\n"
            for name in category_names[:5]:  # Hiển thị tối đa 5 tên
                message += f"• {name}\n"
            if len(category_names) > 5:
                message += f"... và {len(category_names) - 5} danh mục khác"

        message += "\n\n⚠️ Lưu ý: Thao tác này sẽ:\n"
        message += "1. Xóa danh mục từ site WooCommerce (nếu đã đồng bộ)\n"
        message += "2. Xóa danh mục khỏi database local\n"
        message += "3. KHÔNG thể hoàn tác!\n\n"
        message += "Bạn có muốn tiếp tục?"

        reply = QMessageBox.question(
            self, 
            "Xác nhận xóa danh mục",
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            if len(categories_to_delete) == 1:
                # Xóa một category
                cat_info = categories_to_delete[0]
                success = self.delete_single_category(
                    cat_info['id'], 
                    cat_info['wc_id'], 
                    cat_info['name'],
                    show_dialogs=True
                )
                if success:
                    self.load_categories()
                    QMessageBox.information(self, "Thành công", f"Đã xóa danh mục '{cat_info['name']}' thành công!")
            else:
                # Xóa nhiều categories
                self.delete_multiple_categories(categories_to_delete)

    def on_item_changed(self, item):
        """Xử lý khi user chỉnh sửa trực tiếp trong table"""
        if self.is_initializing:
            return  # Không xử lý khi đang khởi tạo
        
        try:
            row = item.row()
            column = item.column()
            
            # Lấy category data từ row đầu tiên
            id_item = self.table.item(row, 0)
            if not id_item:
                return
                
            category_data = id_item.data(Qt.ItemDataRole.UserRole)
            if not category_data:
                return
            
            category_id = category_data.get('id')
            wc_category_id = category_data.get('wc_category_id')
            
            if not wc_category_id:
                QMessageBox.warning(
                    self, "Không thể chỉnh sửa",
                    "Category này chưa được đồng bộ với WooCommerce.\n"
                    "Vui lòng sử dụng nút 'Sửa' để chỉnh sửa."
                )
                return
            
            # Xác định field được chỉnh sửa
            field_name = None
            new_value = item.text()
            
            if column == 2:  # Tên danh mục
                field_name = 'name'
                # Loại bỏ prefix tree structure và icon
                clean_name = new_value
                if new_value.startswith('📁 '):
                    clean_name = new_value[2:].strip()
                elif '├── 📂 ' in new_value:
                    clean_name = new_value.split('├── 📂 ')[-1].strip()
                elif '└── 📂 ' in new_value:
                    clean_name = new_value.split('└── 📂 ')[-1].strip()
                elif '├── 📄 ' in new_value:
                    clean_name = new_value.split('├── 📄 ')[-1].strip()
                elif '└── 📄 ' in new_value:
                    clean_name = new_value.split('└── 📄 ')[-1].strip()
                elif '├── ' in new_value:
                    clean_name = new_value.split('├── ')[-1].strip()
                elif '└── ' in new_value:
                    clean_name = new_value.split('└── ')[-1].strip()
                
                new_value = clean_name
                
            elif column == 3:  # Slug
                field_name = 'slug'
            elif column == 4:  # Description
                field_name = 'description'
            else:
                return  # Không hỗ trợ chỉnh sửa cột khác
            
            if not field_name or not new_value.strip():
                QMessageBox.warning(self, "Lỗi", "Giá trị không được để trống")
                return
            
            # Cập nhật database local
            updated_data = category_data.copy()
            updated_data[field_name] = new_value.strip()
            
            # Hiển thị xác nhận
            reply = QMessageBox.question(
                self, "Xác nhận cập nhật",
                f"Bạn có muốn cập nhật {field_name} của danh mục '{category_data.get('name')}' "
                f"từ '{category_data.get(field_name, '')}' thành '{new_value.strip()}'?\n\n"
                "Thay đổi sẽ được đồng bộ lên WooCommerce.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                # Cập nhật lên site và database
                self.update_category_on_site(category_id, updated_data, wc_category_id)
            else:
                # Restore giá trị cũ
                if column == 2:
                    # Restore với tree structure
                    original_display = self.table.item(row, column).text()
                    self.load_categories()  # Reload để restore tree structure
                else:
                    item.setText(str(category_data.get(field_name, '')))
                    
        except Exception as e:
            self.logger.error(f"Lỗi khi chỉnh sửa trực tiếp: {str(e)}")
            QMessageBox.critical(self, "Lỗi", f"Không thể cập nhật: {str(e)}")
            # Reload để restore về trạng thái ban đầu
            self.load_categories()

    def debug_category_mapping(self):
        """Debug category parent-child mapping"""
        try:
            categories = self.db.get_all_categories()
            
            debug_info = []
            debug_info.append("🔍 DEBUG CATEGORY MAPPING")
            debug_info.append("=" * 50)
            
            # Group by site
            sites = {}
            for cat in categories:
                site_id = cat.get('site_id', 'unknown')
                if site_id not in sites:
                    sites[site_id] = []
                sites[site_id].append(cat)
            
            for site_id, site_cats in sites.items():
                site = self.db.get_site_by_id(site_id) if site_id != 'unknown' else None
                site_name = site.name if site else f"Site ID: {site_id}"
                
                debug_info.append(f"\n📍 SITE: {site_name}")
                debug_info.append("-" * 30)
                
                # Phân loại parent và children
                parents = [cat for cat in site_cats if not cat.get('parent_id') or cat.get('parent_id') == 0]
                children = [cat for cat in site_cats if cat.get('parent_id') and cat.get('parent_id') != 0]
                
                debug_info.append(f"👨‍👩‍👧‍👦 Parent categories: {len(parents)}")
                for parent in parents:
                    debug_info.append(f"  • {parent.get('name')} (ID: {parent.get('id')}, WC: {parent.get('wc_category_id')})")
                
                debug_info.append(f"\n👶 Child categories: {len(children)}")
                for child in children:
                    parent_id = child.get('parent_id')
                    parent_name = "Unknown"
                    
                    # Tìm parent name
                    for parent in parents:
                        if parent.get('id') == parent_id or parent.get('wc_category_id') == parent_id:
                            parent_name = parent.get('name')
                            break
                    
                    debug_info.append(f"  • {child.get('name')} → Parent: {parent_name} (Parent ID: {parent_id})")
                
                # Kiểm tra orphans
                orphans = []
                for child in children:
                    parent_id = child.get('parent_id')
                    found_parent = False
                    
                    for parent in site_cats:
                        if parent.get('id') == parent_id or parent.get('wc_category_id') == parent_id:
                            found_parent = True
                            break
                    
                    if not found_parent:
                        orphans.append(child)
                
                if orphans:
                    debug_info.append(f"\n⚠️ Orphaned categories: {len(orphans)}")
                    for orphan in orphans:
                        debug_info.append(f"  • {orphan.get('name')} (Parent ID: {orphan.get('parent_id')} not found)")
            
            # Hiển thị debug info
            debug_text = "\n".join(debug_info)
            
            # Tạo dialog hiển thị debug info
            dialog = QDialog(self)
            dialog.setWindowTitle("Debug Category Mapping")
            dialog.setMinimumSize(800, 600)
            
            layout = QVBoxLayout(dialog)
            
            text_edit = QPlainTextEdit()
            text_edit.setPlainText(debug_text)
            text_edit.setReadOnly(True)
            text_edit.setFont(QFont("Courier", 10))
            layout.addWidget(text_edit)
            
            button_layout = QHBoxLayout()
            
            copy_btn = QPushButton("📋 Copy to Clipboard")
            copy_btn.clicked.connect(lambda: QApplication.clipboard().setText(debug_text))
            button_layout.addWidget(copy_btn)
            
            close_btn = QPushButton("Đóng")
            close_btn.clicked.connect(dialog.accept)
            button_layout.addWidget(close_btn)
            
            layout.addLayout(button_layout)
            
            dialog.exec()
            
        except Exception as e:
            self.logger.error(f"Lỗi debug category mapping: {str(e)}")
            QMessageBox.critical(self, "Lỗi", f"Không thể debug category mapping: {str(e)}")