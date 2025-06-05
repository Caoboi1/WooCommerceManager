"""
Bulk Category Dialog - Dialog để tạo nhiều danh mục theo cấu trúc cây
"""

import logging
from typing import List, Dict, Optional, Tuple
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *


class CategoryTreeWidget(QTreeWidget):
    """Tree widget tùy chỉnh cho danh mục"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderLabels(["Tên danh mục", "Slug", "Mô tả"])
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)

    def add_category_item(self, name: str, parent_item=None) -> QTreeWidgetItem:
        """Thêm item danh mục vào tree"""
        item = QTreeWidgetItem()
        item.setText(0, name)

        # Auto generate slug
        slug = self.generate_slug(name)
        item.setText(1, slug)
        item.setText(2, "")  # Mô tả trống

        # Thiết lập flags để có thể edit
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)

        if parent_item:
            parent_item.addChild(item)
        else:
            self.addTopLevelItem(item)

        return item

    def generate_slug(self, name: str) -> str:
        """Tạo slug từ tên"""
        import re
        slug = name.lower().replace(' ', '-')
        slug = re.sub(r'[^a-z0-9\-]', '', slug)
        slug = re.sub(r'-+', '-', slug).strip('-')
        return slug

    def get_tree_data(self) -> List[Dict]:
        """Lấy dữ liệu cây dưới dạng list"""
        result = []

        def process_item(item, parent_id=None):
            data = {
                'name': item.text(0),
                'slug': item.text(1),
                'description': item.text(2),
                'parent_id': parent_id,
                'children': []
            }

            # Xử lý children
            for i in range(item.childCount()):
                child = item.child(i)
                child_data = process_item(child, len(result))
                data['children'].append(child_data)

            result.append(data)
            return data

        # Xử lý top level items
        for i in range(self.topLevelItemCount()):
            item = self.topLevelItem(i)
            process_item(item)

        return result


class BulkCategoryDialog(QDialog):
    """Dialog để tạo nhiều danh mục theo cấu trúc cây"""

    def __init__(self, parent=None, sites=None):
        super().__init__(parent)
        self.sites = sites or []
        self.logger = logging.getLogger(__name__)
        self.init_ui()

    def init_ui(self):
        """Khởi tạo giao diện"""
        self.setWindowTitle("Tạo danh mục sản phẩm theo cấu trúc cây")
        self.setModal(True)
        self.resize(800, 600)

        layout = QVBoxLayout(self)

        # Header info
        info_label = QLabel(
            "Tạo danh mục chính và các danh mục con trực tiếp. "
            "Công cụ này sẽ giúp bạn tạo nhanh cấu trúc danh mục nhiều cấp."
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #666; padding: 10px; background: #f0f0f0; border-radius: 5px;")
        layout.addWidget(info_label)

        # Site selection
        site_layout = QHBoxLayout()
        site_layout.addWidget(QLabel("Site:"))

        self.site_combo = QComboBox()
        for site in self.sites:
            self.site_combo.addItem(site.name, site.id)
        site_layout.addWidget(self.site_combo)
        site_layout.addStretch()
        layout.addLayout(site_layout)

        # Main content in splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left side - Input panel
        input_panel = self.create_input_panel()
        splitter.addWidget(input_panel)

        # Right side - Tree preview
        preview_panel = self.create_preview_panel()
        splitter.addWidget(preview_panel)

        splitter.setSizes([400, 400])
        layout.addWidget(splitter)

        # Buttons
        buttons_layout = QHBoxLayout()

        self.create_btn = QPushButton("🌳 Tạo tất cả danh mục")
        self.create_btn.clicked.connect(self.create_categories)
        self.create_btn.setStyleSheet("font-weight: bold; background: #4CAF50; color: white; padding: 8px;")
        buttons_layout.addWidget(self.create_btn)

        self.cancel_btn = QPushButton("❌ Hủy")
        self.cancel_btn.clicked.connect(self.reject)
        buttons_layout.addWidget(self.cancel_btn)

        layout.addLayout(buttons_layout)

    def create_input_panel(self) -> QWidget:
        """Tạo panel nhập liệu"""
        panel = QGroupBox("Nhập cấu trúc danh mục")
        layout = QVBoxLayout(panel)

        # Instructions
        instructions = QLabel(
            "Cách nhập:\n"
            "• Tên danh mục chính\n"
            "  - Tên danh mục con (thụt lề 2 spaces)\n"
            "    - Tên danh mục con cấp 2 (thụt lề 4 spaces)\n"
            "• Tên danh mục chính khác\n\n"
            "Ví dụ:\n"
            "Thời trang\n"
            "  Áo\n"
            "    Áo sơ mi\n"
            "    Áo thun\n"
            "  Quần\n"
            "    Quần jean\n"
            "Điện tử\n"
            "  Điện thoại\n"
            "  Laptop"
        )
        instructions.setStyleSheet("font-family: monospace; background: #f8f8f8; padding: 10px; border-radius: 5px;")
        layout.addWidget(instructions)

        # Text input
        self.text_input = QPlainTextEdit()
        self.text_input.setPlaceholderText("Nhập cấu trúc danh mục theo format trên...")
        self.text_input.textChanged.connect(self.update_preview)
        layout.addWidget(self.text_input)

        # Quick add buttons
        quick_layout = QHBoxLayout()

        sample_btn = QPushButton("📝 Mẫu thời trang")
        sample_btn.clicked.connect(self.add_fashion_sample)
        quick_layout.addWidget(sample_btn)

        tech_btn = QPushButton("📱 Mẫu công nghệ")
        tech_btn.clicked.connect(self.add_tech_sample)
        quick_layout.addWidget(tech_btn)

        clear_btn = QPushButton("🗑️ Xóa tất cả")
        clear_btn.clicked.connect(self.text_input.clear)
        quick_layout.addWidget(clear_btn)

        layout.addLayout(quick_layout)

        return panel

    def create_preview_panel(self) -> QWidget:
        """Tạo panel xem trước"""
        panel = QGroupBox("Xem trước cấu trúc")
        layout = QVBoxLayout(panel)

        # Tree widget
        self.tree_widget = CategoryTreeWidget()
        layout.addWidget(self.tree_widget)

        # Context menu cho tree
        self.tree_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree_widget.customContextMenuRequested.connect(self.show_tree_context_menu)

        # Add buttons
        tree_buttons = QHBoxLayout()

        add_parent_btn = QPushButton("➕ Thêm danh mục chính")
        add_parent_btn.clicked.connect(self.add_parent_category)
        tree_buttons.addWidget(add_parent_btn)

        add_child_btn = QPushButton("➕ Thêm danh mục con")
        add_child_btn.clicked.connect(self.add_child_category)
        tree_buttons.addWidget(add_child_btn)

        remove_btn = QPushButton("➖ Xóa")
        remove_btn.clicked.connect(self.remove_selected)
        tree_buttons.addWidget(remove_btn)

        layout.addLayout(tree_buttons)

        return panel

    def add_fashion_sample(self):
        """Thêm mẫu thời trang"""
        sample = """Thời trang
  Áo
    Áo sơ mi
    Áo thun
    Áo khoác
  Quần
    Quần jean
    Quần kaki
    Quần short
  Phụ kiện
    Túi xách
    Giày dép
    Trang sức"""
        self.text_input.setPlainText(sample)

    def add_tech_sample(self):
        """Thêm mẫu công nghệ"""
        sample = """Điện tử
  Điện thoại
    iPhone
    Samsung
    Xiaomi
  Laptop
    Gaming
    Văn phòng
    Ultrabook
  Phụ kiện
    Tai nghe
    Sạc dự phòng
    Ốp lưng"""
        self.text_input.setPlainText(sample)

    def update_preview(self):
        """Cập nhật xem trước từ text input"""
        self.tree_widget.clear()
        text = self.text_input.toPlainText()

        if not text.strip():
            return

        lines = text.split('\n')
        stack = []  # Stack để theo dõi parent items

        for line in lines:
            if not line.strip():
                continue

            # Đếm số spaces để xác định level
            level = len(line) - len(line.lstrip())
            name = line.strip()

            if not name:
                continue

            # Điều chỉnh stack theo level
            while len(stack) > level // 2:
                stack.pop()

            # Tạo item
            parent_item = stack[-1] if stack else None
            item = self.tree_widget.add_category_item(name, parent_item)

            # Thêm vào stack
            stack.append(item)

        # Expand all
        self.tree_widget.expandAll()

    def show_tree_context_menu(self, position):
        """Hiển thị context menu cho tree"""
        item = self.tree_widget.itemAt(position)

        menu = QMenu()

        if item:
            edit_action = menu.addAction("✏️ Sửa")
            edit_action.triggered.connect(lambda: self.tree_widget.editItem(item))

            add_child_action = menu.addAction("➕ Thêm con")
            add_child_action.triggered.connect(lambda: self.add_child_to_item(item))

            menu.addSeparator()

            remove_action = menu.addAction("🗑️ Xóa")
            remove_action.triggered.connect(lambda: self.remove_item(item))
        else:
            add_action = menu.addAction("➕ Thêm danh mục chính")
            add_action.triggered.connect(self.add_parent_category)

        menu.exec(self.tree_widget.mapToGlobal(position))

    def add_parent_category(self):
        """Thêm danh mục chính"""
        name, ok = QInputDialog.getText(self, "Thêm danh mục chính", "Tên danh mục:")
        if ok and name.strip():
            item = self.tree_widget.add_category_item(name.strip())
            self.tree_widget.setCurrentItem(item)

    def add_child_category(self):
        """Thêm danh mục con cho item được chọn"""
        current_item = self.tree_widget.currentItem()
        if not current_item:
            QMessageBox.warning(self, "Cảnh báo", "Vui lòng chọn danh mục cha trước")
            return

        self.add_child_to_item(current_item)

    def add_child_to_item(self, parent_item):
        """Thêm con cho item cụ thể"""
        name, ok = QInputDialog.getText(self, "Thêm danh mục con", "Tên danh mục con:")
        if ok and name.strip():
            item = self.tree_widget.add_category_item(name.strip(), parent_item)
            parent_item.setExpanded(True)
            self.tree_widget.setCurrentItem(item)

    def remove_selected(self):
        """Xóa items được chọn"""
        selected_items = self.tree_widget.selectedItems()
        if not selected_items:
            return

        reply = QMessageBox.question(
            self, 
            "Xác nhận xóa",
            f"Bạn có chắc muốn xóa {len(selected_items)} danh mục đã chọn?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            for item in selected_items:
                self.remove_item(item)

    def remove_item(self, item):
        """Xóa một item"""
        parent = item.parent()
        if parent:
            parent.removeChild(item)
        else:
            index = self.tree_widget.indexOfTopLevelItem(item)
            self.tree_widget.takeTopLevelItem(index)

    def validate_data(self) -> bool:
        """Kiểm tra dữ liệu hợp lệ"""
        if self.site_combo.currentData() is None:
            QMessageBox.warning(self, "Lỗi", "Vui lòng chọn site")
            return False

        if self.tree_widget.topLevelItemCount() == 0:
            QMessageBox.warning(self, "Lỗi", "Vui lòng thêm ít nhất một danh mục")
            return False

        return True

    def get_categories_data(self) -> Tuple[int, List[Dict]]:
        """Lấy dữ liệu danh mục để tạo"""
        site_id = self.site_combo.currentData()
        categories = []

        def process_item(item, parent_id=None, level=0):
            # Tạo data cho item hiện tại
            category_data = {
                'site_id': site_id,
                'name': item.text(0).strip(),
                'slug': item.text(1).strip(),
                'description': item.text(2).strip(),
                'parent_id': parent_id,
                'level': level
            }
            categories.append(category_data)
            current_index = len(categories) - 1

            # Xử lý children
            for i in range(item.childCount()):
                child = item.child(i)
                process_item(child, current_index, level + 1)

        # Xử lý tất cả top level items
        for i in range(self.tree_widget.topLevelItemCount()):
            item = self.tree_widget.topLevelItem(i)
            process_item(item)

        return site_id, categories

    def create_categories(self):
        """Tạo tất cả danh mục"""
        if not self.validate_data():
            return

        site_id, categories = self.get_categories_data()

        # Hiển thị dialog xác nhận
        total_categories = len(categories)
        reply = QMessageBox.question(
            self,
            "Xác nhận tạo danh mục",
            f"Bạn có muốn tạo {total_categories} danh mục trên site không?\n\n"
            "Quá trình này có thể mất vài phút để hoàn thành.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )

        if reply == QMessageBox.StandardButton.Yes:
            # Emit signal với dữ liệu để parent xử lý
            self.accept_with_data(site_id, categories)

    def accept_with_data(self, site_id: int, categories: List[Dict]):
        """Accept dialog và truyền dữ liệu"""
        self.result_data = (site_id, categories)
        self.accept()

    def get_result_data(self):
        """Lấy dữ liệu kết quả"""
        return getattr(self, 'result_data', None)

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
            if hasattr(self, 'load_categories'):
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