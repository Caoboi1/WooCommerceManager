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

            # Kiểm tra điều kiện lọc site
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
        """Tạo danh mục hàng loạt"""
        try:
            # Disable buttons
            self.bulk_add_btn.setEnabled(False)
            self.add_btn.setEnabled(False)
            self.progress_bar.setVisible(True)
            self.progress_bar.setMaximum(len(categories))
            self.progress_bar.setValue(0)

            site = self.db.get_site_by_id(site_id)
            if not site:
                QMessageBox.warning(self, "Lỗi",
                                    "Không tìm thấy thông tin site")
                return

            # Khởi tạo API
            from .woocommerce_api import WooCommerceAPI
            api = WooCommerceAPI(site)

            created_categories = []
            parent_mapping = {}  # Mapping local index -> WC category ID
            errors = []

            # Tạo từng danh mục theo thứ tự
            for index, category_data in enumerate(categories):
                try:
                    self.status_label.setText(
                        f"Đang tạo: {category_data['name']}...")
                    self.progress_bar.setValue(index)
                    QApplication.processEvents()

                    # Chuẩn bị dữ liệu cho WooCommerce
                    wc_category_data = {
                        'name': category_data['name'],
                        'slug': category_data['slug'],
                        'description': category_data.get('description', ''),
                        'parent': 0  # Mặc định là parent
                    }

                    # Nếu có parent, tìm WC ID của parent
                    if category_data.get('parent_id') is not None:
                        parent_index = category_data['parent_id']
                        if parent_index in parent_mapping:
                            wc_category_data['parent'] = parent_mapping[
                                parent_index]

                    # Tạo trên WooCommerce
                    created_category = api.create_category(wc_category_data)

                    if created_category:
                        # Lưu mapping
                        parent_mapping[index] = created_category.get('id')

                        # Lưu vào database local
                        local_category_data = {
                            'site_id':
                            site_id,
                            'wc_category_id':
                            created_category.get('id'),
                            'name':
                            category_data['name'],
                            'slug':
                            category_data['slug'],
                            'description':
                            category_data.get('description', ''),
                            'parent_id':
                            wc_category_data['parent']
                            if wc_category_data['parent'] > 0 else None,
                            'count':
                            created_category.get('count', 0)
                        }

                        self.db.create_category(local_category_data)
                        created_categories.append(category_data['name'])

                        self.logger.info(
                            f"Đã tạo danh mục: {category_data['name']} (WC ID: {created_category.get('id')})"
                        )
                    else:
                        errors.append(
                            f"Không thể tạo danh mục '{category_data['name']}' trên site"
                        )

                except Exception as e:
                    error_msg = f"Lỗi tạo '{category_data['name']}': {str(e)}"
                    errors.append(error_msg)
                    self.logger.error(error_msg)

            # Hoàn thành
            self.progress_bar.setValue(len(categories))
            self.status_label.setText("Hoàn thành!")

            # Reload categories
            self.load_categories()

            # Hiển thị kết quả
            if created_categories:
                success_msg = f"✅ Đã tạo thành công {len(created_categories)} danh mục:\n"
                success_msg += "\n".join(
                    [f"• {name}" for name in created_categories])

                if errors:
                    success_msg += f"\n\n❌ Có {len(errors)} lỗi:\n"
                    success_msg += "\n".join(
                        [f"• {error}" for error in errors[:5]])
                    if len(errors) > 5:
                        success_msg += f"\n... và {len(errors) - 5} lỗi khác"

                QMessageBox.information(self, "Kết quả tạo danh mục",
                                        success_msg)
            else:
                error_msg = "❌ Không thể tạo danh mục nào!\n\n"
                error_msg += "\n".join([f"• {error}" for error in errors[:5]])
                if len(errors) > 5:
                    error_msg += f"\n... và {len(errors) - 5} lỗi khác"
                QMessageBox.critical(self, "Lỗi", error_msg)

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

        only_local_btn = msg_box.addButton("Chỉ xóa local",
                                           QMessageBox.ButtonRole.AcceptRole)
        retry_btn = msg_box.addButton("Thử lại",
                                      QMessageBox.ButtonRole.ResetRole)
        cancel_btn = msg_box.addButton("Hủy",
                                       QMessageBox.ButtonRole.RejectRole)

        msg_box.exec()
        clicked_btn = msg_box.clickedButton()

        if clicked_btn == only_local_btn:
            self.db.delete_category(category_id)
            return True
        elif clicked_btn == retry_btn:
            return self.delete_single_category(category_id,
                                               wc_category_id,
                                               category_name,
                                               show_dialogs=True)
        else:
            return False

    def show_deletion_results(self, successful_deletions: list,
                              failed_deletions: list):
        """Hiển thị kết quả xóa"""
        message = ""

        if successful_deletions:
            message += f"✅ Đã xóa thành công {len(successful_deletions)} categories:\n"
            message += "\n".join(
                [f"• {name}" for name in successful_deletions])

        if failed_deletions:
            if message:
                message += "\n\n"
            message += f"❌ Không thể xóa {len(failed_deletions)} categories:\n"
            message += "\n".join([f"• {name}" for name in failed_deletions])

        if not message:
            message = "Không có categories nào được xóa."

        # Chọn icon phù hợp
        if failed_deletions and not successful_deletions:
            icon = QMessageBox.Icon.Critical
            title = "Xóa thất bại"
        elif failed_deletions and successful_deletions:
            icon = QMessageBox.Icon.Warning
            title = "Xóa một phần"
        else:
            icon = QMessageBox.Icon.Information
            title = "Xóa thành công"

        msg_box = QMessageBox(self)
        msg_box.setIcon(icon)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        msg_box.exec()

    def delete_category_from_site(self, category_id: int, wc_category_id: int,
                                  category_name: str):
        """Xóa category từ site (để tương thích ngược)"""
        success = self.delete_single_category(category_id,
                                              wc_category_id,
                                              category_name,
                                              show_dialogs=True)
        if success:
            QMessageBox.information(
                self, "Thành công",
                f"Đã xóa category '{category_name}' thành công!")
            self.load_categories()

    def delete_category(self):
        """Xóa category đã chọn"""
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            return

        # Lấy thông tin tất cả categories được chọn
        categories_to_delete = []
        for selected_row in selected_rows:
            row = selected_row.row()
            item = self.table.item(row, 0)
            if item:
                category_data = item.data(Qt.ItemDataRole.UserRole)
                if category_data:
                    categories_to_delete.append({
                        'id':
                        category_data.get('id'),
                        'name':
                        category_data.get('name'),
                        'wc_id':
                        category_data.get('wc_category_id')
                    })

        if not categories_to_delete:
            return

        # Hiển thị dialog xác nhận
        if len(categories_to_delete) == 1:
            category_name = categories_to_delete[0]['name']
            message = f"Bạn có chắc muốn xóa category '{category_name}'?"
        else:
            category_names = [cat['name'] for cat in categories_to_delete]
            message = f"Bạn có chắc muốn xóa {len(categories_to_delete)} categories sau:\n\n"
            message += "\n".join([f"• {name}" for name in category_names])

        message += "\n\nLưu ý: Các category sẽ được xóa cả trên site và database local."

        reply = QMessageBox.question(
            self, "Xác nhận xóa", message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.Yes:
            self.delete_multiple_categories(categories_to_delete)

    def on_item_changed(self, item):
        """Xử lý khi một item trong table được chỉnh sửa"""
        try:
            # Ngăn dialog hiển thị khi đang khởi tạo
            if hasattr(self, 'is_initializing') and self.is_initializing:
                return

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
            new_value = item.text().strip()

            # Xác định field nào được chỉnh sửa
            field_mapping = {
                2: 'name',  # Tên danh mục
                3: 'slug',  # Slug
                4: 'description'  # Mô tả
            }

            # Tên hiển thị cho các trường
            field_display_names = {
                'name': 'tên danh mục',
                'slug': 'slug',
                'description': 'mô tả'
            }

            field_name = field_mapping.get(column)
            if not field_name:
                return

            # Kiểm tra xem có thay đổi thực sự không
            old_value = category_data.get(field_name, '')
            if new_value == old_value:
                return

            # Cập nhật category data
            updated_data = category_data.copy()
            updated_data[field_name] = new_value

            # Nếu category đã đồng bộ với WooCommerce, cập nhật trực tiếp
            if wc_category_id:
                field_display = field_display_names.get(field_name, field_name)
                reply = QMessageBox.question(
                    self, "Cập nhật trực tiếp",
                    f"Bạn có muốn cập nhật {field_display} lên WooCommerce ngay?\n\n"
                    f"Giá trị cũ: {old_value}\n"
                    f"Giá trị mới: {new_value}", QMessageBox.StandardButton.Yes
                    | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.Yes)

                if reply == QMessageBox.StandardButton.Yes:
                    # Cập nhật trực tiếp lên site
                    self.update_category_inline(category_id, updated_data,
                                                wc_category_id, field_name)
                else:
                    # Chỉ cập nhật local
                    self.db.update_category(category_id, updated_data)
                    # Cập nhật category_data trong item
                    id_item.setData(Qt.ItemDataRole.UserRole, updated_data)
            else:
                # Chỉ cập nhật local cho category chưa đồng bộ
                self.db.update_category(category_id, updated_data)
                # Cập nhật category_data trong item
                id_item.setData(Qt.ItemDataRole.UserRole, updated_data)

                # Hiển thị thông báo
                self.status_label.setText(
                    f"Đã cập nhật {field_name} trong database local")

        except Exception as e:
            self.logger.error(f"Lỗi cập nhật inline: {str(e)}")
            QMessageBox.critical(self, "Lỗi", f"Không thể cập nhật: {str(e)}")
            # Khôi phục giá trị cũ
            if 'old_value' in locals():
                item.setText(old_value)

    def update_category_inline(self, category_id: int, category_data: Dict,
                               wc_category_id: int, field_name: str):
        """Cập nhật category inline lên WooCommerce"""
        try:
            # Disable editing tạm thời
            self.table.setEnabled(False)
            self.status_label.setText(
                f"Đang cập nhật {field_name} lên WooCommerce...")

            # Lấy thông tin site
            site_id = category_data.get('site_id')
            site = self.db.get_site_by_id(site_id)
            if not site:
                raise Exception("Không tìm thấy thông tin site")

            # Khởi tạo API
            from .woocommerce_api import WooCommerceAPI
            api = WooCommerceAPI(site)

            # Chuẩn bị dữ liệu cập nhật
            wc_update_data = {field_name: category_data[field_name]}

            # Nếu cập nhật slug, cần validate
            if field_name == 'slug':
                import re
                slug = re.sub(r'[^a-zA-Z0-9\s-]', '',
                              category_data[field_name].lower())
                slug = re.sub(r'\s+', '-', slug.strip())
                wc_update_data['slug'] = slug
                category_data['slug'] = slug

            # Cập nhật lên WooCommerce
            result = api.update_category(wc_category_id, wc_update_data)

            if result:
                # Cập nhật database local
                self.db.update_category(category_id, category_data)

                # Cập nhật item data
                id_item = self.table.item(self.table.currentRow(), 0)
                if id_item:
                    id_item.setData(Qt.ItemDataRole.UserRole, category_data)

                self.status_label.setText(
                    f"✅ Đã cập nhật {field_name} thành công!")

                # Auto refresh sau 2 giây
                QTimer.singleShot(
                    2000, lambda: self.status_label.setText("Sẵn sàng"))
            else:
                raise Exception("Không nhận được response từ WooCommerce")

        except Exception as e:
            self.logger.error(f"Lỗi cập nhật inline lên site: {str(e)}")

            # Hỏi có muốn cập nhật local không
            reply = QMessageBox.question(
                self, "Cập nhật thất bại",
                f"Không thể cập nhật lên WooCommerce:\n{str(e)}\n\n"
                "Bạn có muốn lưu thay đổi trong database local không?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes)

            if reply == QMessageBox.StandardButton.Yes:
                self.db.update_category(category_id, category_data)
                self.status_label.setText(
                    "Đã lưu thay đổi trong database local")
            else:
                # Reload để khôi phục giá trị cũ
                self.load_categories()

        finally:
            # Re-enable editing
            self.table.setEnabled(True)

    def debug_category_mapping(self):
        """Debug category mapping để kiểm tra tình trạng đồng bộ"""
        try:
            site_id = self.site_combo.currentData()

            # Lấy debug report
            report = self.db.debug_category_mapping(site_id)

            if not report:
                QMessageBox.warning(self, "Lỗi",
                                    "Không thể lấy thông tin debug")
                return

            # Tạo message hiển thị
            message = f"📊 **CATEGORY MAPPING REPORT**\n\n"
            message += f"Tổng categories: {report.get('total_categories', 0)}\n"
            message += f"Có WC ID: {report.get('categories_with_wc_id', 0)}\n"
            message += f"Không có WC ID: {report.get('categories_without_wc_id', 0)}\n\n"

            message += "📋 **CHI TIẾT CATEGORIES:**\n"
            categories = report.get('categories', [])

            for cat in categories[:20]:  # Hiển thị 20 đầu tiên
                name = cat.get('name', 'N/A')
                wc_id = cat.get('wc_category_id', 'N/A')
                local_id = cat.get('id', 'N/A')
                site_name = cat.get('site_name', 'N/A')

                status = "✅" if wc_id and wc_id != 'N/A' else "❌"
                message += f"{status} {name} (Local:{local_id}, WC:{wc_id}) - {site_name}\n"

            if len(categories) > 20:
                message += f"\n... và {len(categories) - 20} categories khác"

            # Hiển thị trong dialog
            msg_box = QMessageBox(self)
            msg_box.setIcon(QMessageBox.Icon.Information)
            msg_box.setWindowTitle("Category Mapping Debug")
            msg_box.setText(message)
            msg_box.setDetailedText("\n".join([str(cat)
                                               for cat in categories]))
            msg_box.exec()

            # Log report
            self.logger.info(f"Category mapping report: {report}")

        except Exception as e:
            self.logger.error(f"Lỗi debug category mapping: {str(e)}")
            QMessageBox.critical(
                self, "Lỗi", f"Không thể debug category mapping:\n{str(e)}")