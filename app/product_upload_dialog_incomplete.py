"""
Product Upload Dialog - Dialog để upload sản phẩm lên WooCommerce (Fixed Version)
"""

import logging
import os
from datetime import datetime
from typing import List, Dict, Optional
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QLineEdit, QTextEdit, QComboBox, QSpinBox,
    QDoubleSpinBox, QCheckBox, QGroupBox, QFormLayout,
    QProgressBar, QMessageBox, QFileDialog, QListWidget,
    QListWidgetItem, QSplitter, QScrollArea, QWidget,
    QGridLayout, QFrame, QTableWidget, QTableWidgetItem
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread, QTimer, QUrl
from PyQt6.QtGui import QPixmap, QFont, QColor, QDesktopServices

# Sử dụng PyQt6 để xử lý ảnh thay vì PIL
PIL_AVAILABLE = False
try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

from .woocommerce_api import WooCommerceAPI
from .models import Site


class BulkUploadWorker(QThread):
    """Worker thread để upload hàng loạt"""
    progress_update = pyqtSignal(int, int, str)  # current, total, message
    product_uploaded = pyqtSignal(int, dict, str)  # row, result, log_message
    upload_complete = pyqtSignal(int, int)  # success_count, total_count
    error_occurred = pyqtSignal(str)
    log_update = pyqtSignal(int, str, str)  # row, status, message

    def __init__(self, folders, config, db_manager):
        super().__init__()
        self.folders = folders or []  # Ensure never None
        self.config = config or {}    # Ensure never None
        self.db_manager = db_manager
        self.success_count = 0
        self.logger = logging.getLogger(__name__ + ".BulkUploadWorker")

    def run(self):
        """Upload từng sản phẩm với hỗ trợ đa luồng"""
        try:
            from .woocommerce_api import WooCommerceAPI
            import time
            from concurrent.futures import ThreadPoolExecutor, as_completed

            # Validate inputs với chi tiết hơn
            if not self.config:
                self.logger.error("Upload config is empty - Config chưa được khởi tạo")
                self.error_occurred.emit("Lỗi: Config upload chưa được khởi tạo")
                return
                
            if not isinstance(self.config, dict):
                self.logger.error(f"Upload config is not a dict: {type(self.config)}")
                self.error_occurred.emit("Lỗi: Config không hợp lệ")
                return
                
            if not self.config.get('site'):
                self.logger.error("No site configured for upload - Missing 'site' in config")
                self.error_occurred.emit("Lỗi: Chưa chọn site để đăng")
                return
                
            if not self.folders:
                self.logger.error("No folders to upload - folders list is empty")
                self.error_occurred.emit("Lỗi: Không có folder nào để upload")
                return
            
            # Log config để debug
            self.logger.info(f"BulkUploadWorker initialized with config keys: {list(self.config.keys())}")
            self.logger.info(f"Processing {len(self.folders)} folders")

            api = WooCommerceAPI(self.config['site'])
            total_folders = len(self.folders)
            
            # Check if threading is enabled
            threading_enabled = self.config.get('threading_enabled', False)
            max_threads = self.config.get('max_threads', 1)
            batch_size = self.config.get('batch_size', 5)
            thread_delay = self.config.get('thread_delay', 0)

            if threading_enabled and max_threads > 1:
                self.logger.info(f"Threading enabled: {max_threads} threads, batch size: {batch_size}")
                self.upload_with_threading(api, total_folders, max_threads, batch_size, thread_delay)
            else:
                self.logger.info("Sequential upload mode")
                self.upload_sequential(api, total_folders)

        except Exception as e:
            self.logger.error(f"Bulk upload error: {str(e)}")
            self.error_occurred.emit(f"Lỗi upload hàng loạt: {str(e)}")

        finally:
            # Ensure cleanup happens even on exceptions
            try:
                self.folders = []
                self.config = {}
                self.db_manager = None
                import gc
                gc.collect()
            except:
                pass

    def upload_with_threading(self, api, total_folders, max_threads, batch_size, thread_delay):
        """Upload với đa luồng sử dụng queue"""
        try:
            from concurrent.futures import ThreadPoolExecutor, as_completed
            from queue import Queue
            import threading
            import time
            
            # Tạo queue chứa các folder cần upload
            folder_queue = Queue()
            self.processed_count = 0
            self.queue_lock = threading.Lock()
            
            # Đánh dấu tất cả folders là "pending" với null checks
            valid_folders = []
            for i, folder in enumerate(self.folders or []):
                if folder is None:
                    self.logger.warning(f"Folder at index {i} is None, skipping")
                    continue
                    
                if not isinstance(folder, dict):
                    self.logger.warning(f"Folder at index {i} is not a dict: {type(folder)}, skipping")
                    continue
                    
                folder['_upload_status'] = 'pending'
                folder['_queue_index'] = i
                folder_queue.put((i, folder))
                valid_folders.append(folder)
            
            if not valid_folders:
                self.logger.error("No valid folders to process")
                self.error_occurred.emit("Lỗi: Không có folder hợp lệ để xử lý")
                return
            
            self.logger.info(f"Threading upload: {max_threads} threads processing {len(valid_folders)} valid folders")
            
            def worker_thread(thread_id):
                """Worker thread để xử lý upload"""
                worker_success_count = 0
                
                while True:
                    try:
                        # Lấy folder từ queue
                        try:
                            queue_index, folder = folder_queue.get(timeout=1)
                        except:
                            break  # Queue rỗng, thoát
                        
                        # Validate folder data
                        if folder is None or not isinstance(folder, dict):
                            self.logger.error(f"Thread {thread_id}: Invalid folder at index {queue_index}")
                            folder_queue.task_done()
                            continue
                        
                        # Đánh dấu đang xử lý
                        folder['_upload_status'] = 'processing'
                        
                        with self.queue_lock:
                            self.processed_count += 1
                            current_progress = self.processed_count
                        
                        # Hiển thị progress với safe get
                        folder_name = folder.get('data_name', 'Unknown')
                        self.progress_update.emit(
                            current_progress, 
                            total_folders, 
                            f"Thread {thread_id}: {folder_name}"
                        )
                        
                        # Upload folder
                        try:
                            success = self.upload_single_folder(api, folder, queue_index)
                            if success:
                                folder['_upload_status'] = 'completed'
                                worker_success_count += 1
                                with self.queue_lock:
                                    self.success_count += 1
                            else:
                                folder['_upload_status'] = 'failed'
                        except Exception as e:
                            folder['_upload_status'] = 'failed'
                            self.logger.error(f"Thread {thread_id} upload error for folder '{folder_name}': {str(e)}")
                        
                        # Đánh dấu hoàn thành task
                        folder_queue.task_done()
                        
                        # Delay giữa các upload trong cùng thread
                        if self.config and self.config.get('upload_delay', 0) > 0:
                            time.sleep(self.config['upload_delay'])
                            
                    except Exception as e:
                        self.logger.error(f"Thread {thread_id} worker error: {str(e)}")
                        try:
                            folder_queue.task_done()
                        except:
                            pass
                        break
                
                self.logger.info(f"Thread {thread_id} completed: {worker_success_count} successful uploads")
                return worker_success_count
            
            # Khởi tạo threads
            with ThreadPoolExecutor(max_workers=max_threads) as executor:
                futures = []
                
                # Tạo worker threads với delay
                for thread_id in range(max_threads):
                    future = executor.submit(worker_thread, thread_id + 1)
                    futures.append(future)
                    
                    # Delay giữa việc khởi động threads
                    if thread_delay > 0 and thread_id < max_threads - 1:
                        time.sleep(thread_delay)
                
                # Chờ tất cả threads hoàn thành
                total_thread_success = 0
                for future in as_completed(futures):
                    try:
                        thread_success = future.result()
                        total_thread_success += thread_success
                    except Exception as e:
                        self.logger.error(f"Thread execution error: {str(e)}")
            
            # Chờ queue hoàn thành
            folder_queue.join()
            
            self.logger.info(f"Threading upload completed: {self.success_count}/{total_folders} successful")
            self.upload_complete.emit(self.success_count, total_folders)
            
        except Exception as e:
            self.logger.error(f"Threading upload error: {str(e)}")
            self.error_occurred.emit(f"Lỗi upload đa luồng: {str(e)}")

    def upload_sequential(self, api, total_folders):
        """Upload tuần tự (không đa luồng)"""
        import time
        
        if not self.folders:
            self.logger.error("Folders list is empty in sequential upload")
            self.error_occurred.emit("Lỗi: Danh sách folder trống")
            return
            
        for i, folder in enumerate(self.folders):
            try:
                if folder is None:
                    self.logger.warning(f"Folder at index {i} is None, skipping")
                    continue
                    
                self.progress_update.emit(i, total_folders, f"Đang xử lý: {folder.get('data_name', 'Unknown')}")
                
                success = self.upload_single_folder(api, folder, i)
                if success:
                    self.success_count += 1

                # Delay between uploads
                if i < total_folders - 1:  # No delay after last item
                    upload_delay = self.config.get('upload_delay', 0) if self.config else 0
                    if upload_delay > 0:
                        time.sleep(upload_delay)

            except Exception as e:
                error_msg = f"Lỗi: {str(e)}"
                self.logger.error(f"Error uploading folder {folder.get('data_name', 'Unknown') if folder else 'None'}: {str(e)}")
                self.log_update.emit(i, "error", error_msg)
                # Tạo dict rỗng thay vì None để tránh lỗi signal
                empty_result = {}
                self.product_uploaded.emit(i, empty_result, error_msg)
                continue

        self.upload_complete.emit(self.success_count, total_folders)

    def upload_single_folder(self, api, folder, index):
        """Upload một folder duy nhất"""
        try:
            import time
            import hashlib
            from datetime import datetime
            
            # Validate inputs với chi tiết hơn
            if folder is None:
                raise Exception("Folder data is None")
            
            if not isinstance(folder, dict):
                raise Exception(f"Folder data is not a dict: {type(folder)}")
            
            if api is None:
                raise Exception("API object is None")
            
            # Validate config trước khi sử dụng
            if not self.config:
                raise Exception("Upload config is empty - Config chưa được khởi tạo")
            
            # Kiểm tra các field bắt buộc trong config
            required_config_fields = ['site', 'status', 'regular_price', 'stock_status']
            for field in required_config_fields:
                if field not in self.config:
                    raise Exception(f"Missing required config field: {field}")
            
            # Upload images first
            uploaded_images = []
            folder_path = folder.get('path', '')
            product_name = folder.get('new_title', '') or folder.get('data_name', 'Untitled Product')

            # Đổi tên ảnh theo tiêu đề mới trước khi upload
            if os.path.exists(folder_path) and product_name:
                try:
                    self.rename_images_in_folder(folder_path, product_name)
                except Exception as e:
                    self.logger.warning(f"Không thể đổi tên ảnh: {str(e)}")

            if os.path.exists(folder_path):
                image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'}
                image_files = []

                for file in os.listdir(folder_path):
                    if any(file.lower().endswith(ext) for ext in image_extensions):
                        image_files.append(os.path.join(folder_path, file))

                # Upload images với title và description theo yêu cầu
                for img_idx, img_path in enumerate(image_files[:5]):  # Limit to 5 images
                    try:
                        # Resize ảnh trước khi upload (mặc định 1200x1200)
                        resized_img_path = self.resize_image_if_needed(img_path, max_size=(1200, 1200))
                        
                        # Sử dụng tên sản phẩm làm title cho ảnh (Caption)
                        image_title = product_name
                        
                        # Sử dụng tên sản phẩm làm Alternative Text
                        image_alt = product_name
                        
                        # Sử dụng mô tả sản phẩm làm Description
                        product_description = folder.get('description', '')
                        if not product_description:
                            product_description = f"Premium quality {product_name}. Perfect for any occasion."

                        result = api.upload_media(
                            resized_img_path, 
                            image_title,
                            image_alt,
                            product_description  # Thêm description
                        )
                        if result:
                            uploaded_images.append(result)
                            self.log_update.emit(index, "info", f"Đã upload ảnh {img_idx + 1}/{min(len(image_files), 5)}")
                        
                        # Clean up resized image nếu khác với ảnh gốc
                        if resized_img_path != img_path and os.path.exists(resized_img_path):
                            try:
                                os.remove(resized_img_path)
                            except:
                                pass

                    except Exception as e:
                        self.logger.error(f"Lỗi upload ảnh {img_path}: {str(e)}")
                        self.log_update.emit(index, "warning", f"Lỗi upload ảnh: {str(e)}")

            # Prepare product data
            now = datetime.now()
            
            # Get category info
            category_ids = []
            try:
                if folder.get('category_id') and self.db_manager:
                    category = self.db_manager.get_category_by_id(folder['category_id'])
                    if category and category.get('wc_category_id'):
                        category_ids = [category['wc_category_id']]
                        
                # Fallback to config category
                if not category_ids and self.config.get('category_id'):
                    category_ids = [self.config['category_id']]
                    
                # Final fallback
                if not category_ids:
                    category_ids = [1]  # Uncategorized
                    
            except Exception as e:
                self.logger.warning(f"Lỗi lấy category: {str(e)}")
                category_ids = [1]

            # Create product data
            product_data = {
                'name': product_name,
                'type': 'simple',
                'regular_price': str(self.config.get('regular_price', '0')),
                'status': self.config.get('status', 'draft'),
                'categories': [{'id': cat_id} for cat_id in category_ids],
                'stock_status': self.config.get('stock_status', 'instock'),
                'manage_stock': self.config.get('manage_stock', False),
                'description': folder.get('description', f'Premium quality {product_name}. Perfect for any occasion.'),
                'short_description': folder.get('short_description', f'Premium {product_name}'),
            }

            # Add sale price if configured
            if self.config.get('sale_price') and float(self.config['sale_price']) > 0:
                product_data['sale_price'] = str(self.config['sale_price'])

            # Add stock quantity if manage_stock is enabled
            if product_data.get('manage_stock'):
                product_data['stock_quantity'] = self.config.get('stock_quantity', 10)

            # Add images
            if uploaded_images:
                product_data['images'] = [{'id': img['id']} for img in uploaded_images]

            # Add tags nếu có
            if folder.get('tags'):
                tags = [tag.strip() for tag in folder['tags'].split(',') if tag.strip()]
                product_data['tags'] = [{'name': tag} for tag in tags]

            # Upload product
            self.log_update.emit(index, "info", "Đang tạo sản phẩm...")
            
            product_result = api.create_product(product_data)
            
            if product_result:
                # Success
                result_data = {
                    'id': product_result.get('id'),
                    'name': product_result.get('name'),
                    'permalink': product_result.get('permalink'),
                    'status': product_result.get('status'),
                    'categories': product_result.get('categories', []),
                    'images': product_result.get('images', []),
                    'price': product_result.get('price'),
                    'product_url': product_result.get('permalink', ''),
                    'created_at': now.isoformat()
                }
                
                success_msg = f"Đã tạo sản phẩm: {product_name} (ID: {product_result.get('id')})"
                self.log_update.emit(index, "success", success_msg)
                self.product_uploaded.emit(index, result_data, success_msg)
                
                # Update folder trong database nếu có
                if self.db_manager and folder.get('id'):
                    try:
                        update_data = {
                            'wc_product_id': product_result.get('id'),
                            'upload_status': 'uploaded',
                            'upload_date': now.isoformat(),
                            'product_url': product_result.get('permalink', ''),
                            'site_id': self.config.get('site').id if self.config.get('site') else None
                        }
                        self.db_manager.update_folder_upload_info(folder['id'], update_data)
                    except Exception as e:
                        self.logger.warning(f"Không thể update folder info: {str(e)}")
                
                return True
            else:
                # Failure
                error_msg = "Không thể tạo sản phẩm - API trả về null"
                self.log_update.emit(index, "error", error_msg)
                empty_result = {}
                self.product_uploaded.emit(index, empty_result, error_msg)
                return False

        except Exception as e:
            error_msg = f"Lỗi upload: {str(e)}"
            self.logger.error(f"Error uploading folder: {str(e)}")
            self.log_update.emit(index, "error", error_msg)
            empty_result = {}
            self.product_uploaded.emit(index, empty_result, error_msg)
            return False

    def resize_image_if_needed(self, image_path: str, max_size: tuple = (1200, 1200)) -> str:
        """Resize ảnh nếu quá lớn và trả về đường dẫn ảnh đã resize"""
        try:
            if PIL_AVAILABLE:
                with Image.open(image_path) as img:
                    original_size = img.size
                    
                    # Kiểm tra xem có cần resize không
                    if original_size[0] <= max_size[0] and original_size[1] <= max_size[1]:
                        self.logger.info(f"Ảnh {os.path.basename(image_path)} không cần resize: {original_size}")
                        return image_path
                    
                    # Tính toán kích thước mới giữ tỷ lệ
                    ratio = min(max_size[0] / original_size[0], max_size[1] / original_size[1])
                    new_size = (int(original_size[0] * ratio), int(original_size[1] * ratio))
                    
                    # Resize ảnh
                    resized_img = img.resize(new_size, Image.Resampling.LANCZOS)
                    
                    # Tạo tên file mới cho ảnh đã resize
                    name, ext = os.path.splitext(image_path)
                    resized_path = f"{name}_resized{ext}"
                    
                    # Lưu ảnh đã resize với chất lượng tối ưu
                    if ext.lower() in ['.jpg', '.jpeg']:
                        resized_img.save(resized_path, 'JPEG', quality=85, optimize=True)
                    elif ext.lower() == '.png':
                        resized_img.save(resized_path, 'PNG', optimize=True)
                    elif ext.lower() == '.webp':
                        resized_img.save(resized_path, 'WEBP', quality=85, optimize=True)
                    else:
                        resized_img.save(resized_path, optimize=True)
                    
                    self.logger.info(f"Đã resize ảnh {os.path.basename(image_path)}: {original_size} → {new_size}")
                    return resized_path
            else:
                # Sử dụng PyQt6 thay thế
                pixmap = QPixmap(image_path)
                if pixmap.isNull():
                    self.logger.warning(f"Không thể load ảnh: {image_path}")
                    return image_path
                    
                original_size = (pixmap.width(), pixmap.height())
                
                # Kiểm tra xem có cần resize không
                if original_size[0] <= max_size[0] and original_size[1] <= max_size[1]:
                    self.logger.info(f"Ảnh {os.path.basename(image_path)} không cần resize: {original_size}")
                    return image_path
                
                # Resize bằng PyQt6
                scaled_pixmap = pixmap.scaled(max_size[0], max_size[1], Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                
                # Tạo tên file mới cho ảnh đã resize
                name, ext = os.path.splitext(image_path)
                resized_path = f"{name}_resized{ext}"
                
                # Lưu ảnh đã resize
                scaled_pixmap.save(resized_path, quality=85)
                
                new_size = (scaled_pixmap.width(), scaled_pixmap.height())
                self.logger.info(f"Đã resize ảnh {os.path.basename(image_path)}: {original_size} → {new_size}")
                return resized_path
                
        except Exception as e:
            self.logger.error(f"Lỗi resize ảnh {image_path}: {str(e)}")
            return image_path  # Trả về ảnh gốc nếu resize thất bại

    def rename_images_in_folder(self, folder_path: str, new_title: str):
        """Đổi tên các file ảnh trong folder theo tiêu đề mới"""
        try:
            if not os.path.exists(folder_path) or not new_title:
                return
            
            # Làm sạch tên file
            clean_title = self.sanitize_filename(new_title)
            
            image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'}
            image_files = []
            
            # Lấy danh sách file ảnh
            for file in os.listdir(folder_path):
                if any(file.lower().endswith(ext) for ext in image_extensions):
                    image_files.append(file)
            
            # Sắp xếp theo tên để đảm bảo thứ tự nhất quán
            image_files.sort()
            
            # Đổi tên từng file
            for i, old_filename in enumerate(image_files):
                old_path = os.path.join(folder_path, old_filename)
                
                # Lấy extension
                _, ext = os.path.splitext(old_filename)
                
                # Tạo tên mới
                if len(image_files) == 1:
                    new_filename = f"{clean_title}{ext}"
                else:
                    new_filename = f"{clean_title}_{i+1:02d}{ext}"
                
                new_path = os.path.join(folder_path, new_filename)
                
                # Đổi tên nếu tên mới khác tên cũ
                if old_path != new_path and not os.path.exists(new_path):
                    try:
                        os.rename(old_path, new_path)
                        self.logger.info(f"Đã đổi tên: {old_filename} → {new_filename}")
                    except Exception as e:
                        self.logger.warning(f"Không thể đổi tên {old_filename}: {str(e)}")
                        
        except Exception as e:
            self.logger.error(f"Lỗi đổi tên ảnh trong folder {folder_path}: {str(e)}")

    def sanitize_filename(self, filename: str) -> str:
        """Làm sạch filename để đảm bảo tính hợp lệ"""
        import re
        
        # Loại bỏ các ký tự không hợp lệ
        filename = re.sub(r'[<>:"/\\|?*]', '', filename)
        
        # Thay thế khoảng trắng bằng dấu gạch ngang
        filename = re.sub(r'\s+', '-', filename)
        
        # Loại bỏ dấu gạch ngang ở đầu và cuối
        filename = filename.strip('-')
        
        # Giới hạn độ dài
        if len(filename) > 100:
            filename = filename[:100]
        
        return filename


# Dummy classes to maintain interface compatibility
class ImageUploadWorker(QThread):
    """Placeholder class for compatibility"""
    pass


class ProductUploadDialog(QDialog):
    """Placeholder class for compatibility"""
    product_uploaded = pyqtSignal(dict)  # Signal phát ra khi sản phẩm được upload thành công
    
    def __init__(self, parent=None, sites=None, db_manager=None, selected_folders=None):
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)
        self.sites = sites or []
        self.db_manager = db_manager
        self.selected_folders = selected_folders or []
        
        # ... existing code ...
        
    def on_product_uploaded(self, product_data):
        """Phát signal khi sản phẩm được upload thành công"""
        try:
            self.product_uploaded.emit(product_data)
        except Exception as e:
            self.logger.error(f"Error emitting product_uploaded signal: {str(e)}")