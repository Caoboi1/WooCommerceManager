"""
Product Upload Dialog - Dialog để upload sản phẩm lên WooCommerce
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
        self.folders = folders
        self.config = config
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
            if self.config is None:
                self.logger.error("Upload config is None - Config chưa được khởi tạo")
                self.error_occurred.emit("Lỗi: Config upload chưa được khởi tạo")
                return
                
            if not isinstance(self.config, dict):
                raise Exception(f"Upload config is not a dict: {type(self.config)}")
                
            if not self.config.get('site'):
                raise Exception("No site configured for upload - Missing 'site' in config")
                
            if not self.folders:
                raise Exception("No folders to upload - folders list is empty")
            
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
                self.logger.info(f"🔧 Threading enabled: {max_threads} threads, batch size: {batch_size}")
                self.upload_with_threading(api, total_folders, max_threads, batch_size, thread_delay)
            else:
                self.logger.info("📤 Sequential upload mode")
                self.upload_sequential(api, total_folders)

        except Exception as e:
            self.logger.error(f"Bulk upload error: {str(e)}")
            self.error_occurred.emit(f"Lỗi upload hàng loạt: {str(e)}")

        finally:
            # Ensure cleanup happens even on exceptions
            try:
                self.folders = None
                self.config = None
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
            if self.folders is None:
                self.logger.error("Folders list is None")
                self.error_occurred.emit("Lỗi: Danh sách folder không hợp lệ")
                return
            
            for i, folder in enumerate(self.folders):
                if folder is None:
                    self.logger.warning(f"Folder at index {i} is None, skipping")
                    continue
                    
                if not isinstance(folder, dict):
                    self.logger.warning(f"Folder at index {i} is not a dict: {type(folder)}, skipping")
                    continue
                    
                folder['_upload_status'] = 'pending'
                folder['_queue_index'] = i
                folder_queue.put((i, folder))
            
            self.logger.info(f"🔧 Threading upload: {max_threads} threads processing {folder_queue.qsize()} valid folders")
            
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
                        if folder is None:
                            self.logger.error(f"Thread {thread_id}: Folder is None at index {queue_index}")
                            folder_queue.task_done()
                            continue
                            
                        if not isinstance(folder, dict):
                            self.logger.error(f"Thread {thread_id}: Folder is not dict at index {queue_index}: {type(folder)}")
                            folder_queue.task_done()
                            continue
                        
                        # Đánh dấu đang xử lý
                        folder['_upload_status'] = 'processing'
                        
                        with self.queue_lock:
                            self.processed_count += 1
                            current_progress = self.processed_count
                        
                        # Hiển thị progress với safe get
                        folder_name = folder.get('data_name', 'Unknown') if folder else 'Invalid'
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
                        # Ensure task is marked done even on error
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
            
            self.logger.info(f"✅ Threading upload completed: {self.success_count}/{total_folders} successful")
            self.upload_complete.emit(self.success_count, total_folders)
            
        except Exception as e:
            self.logger.error(f"Threading upload error: {str(e)}")
            self.error_occurred.emit(f"Lỗi upload đa luồng: {str(e)}")

    def upload_sequential(self, api, total_folders):
        """Upload tuần tự (không đa luồng)"""
        import time
        
        if self.folders is None:
            self.logger.error("Folders list is None in sequential upload")
            self.error_occurred.emit("Lỗi: Danh sách folder không hợp lệ")
            return
            
        for i, folder in enumerate(self.folders or []):
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
                    time.sleep(self.config['upload_delay'])

            except Exception as e:
                error_msg = f"❌ Lỗi: {str(e)}"
                self.logger.error(f"Error uploading folder {folder.get('data_name')}: {str(e)}")
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
            if self.config is None:
                raise Exception("Upload config is None - Config chưa được khởi tạo")
            
            # Kiểm tra các field bắt buộc trong config
            required_config_fields = ['site', 'status', 'regular_price', 'stock_status']
            for field in required_config_fields:
                if field not in self.config:
                    raise Exception(f"Missing required config field: {field}")
            
            # Upload images first
            uploaded_images = []
            folder_path = folder.get('path', '') if folder else ''
            product_name = (folder.get('new_title', '') or folder.get('data_name', 'Untitled Product')) if folder else 'Untitled Product'

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
                            # Sử dụng dữ liệu đã được format chuẩn từ API
                            uploaded_images.append(result)
                            
                        # Cleanup file resize nếu có
                        self.cleanup_single_resized_image(img_path, resized_img_path)
                        
                    except Exception as e:
                        self.logger.error(f"Error uploading image {img_path}: {str(e)}")
                        # Cleanup ngay cả khi có lỗi
                        self.cleanup_single_resized_image(img_path, resized_img_path)
                        continue

            # Tạo SKU chỉ dùng số
            hash_input = f"{product_name}{folder.get('id', '')}{int(time.time())}"
            hash_object = hashlib.md5(hash_input.encode())
            sku = str(int(hash_object.hexdigest()[:8], 16))

            # Determine stock settings with null checks
            if self.config is None:
                raise Exception("Upload config is None")
                
            manage_stock = self.config.get('manage_stock', True)
            stock_status = self.config.get('stock_status', 'instock')
            stock_quantity = self.config.get('stock_quantity', 100)

            # Auto-adjust status based on quantity if managing stock
            if manage_stock:
                if stock_quantity > 0:
                    stock_status = 'instock'
                else:
                    stock_status = 'outofstock'

            # Tự động lấy danh mục từ dữ liệu folder
            category_id = self.get_folder_category_id(folder)
            if not category_id:
                category_id = self.config.get('category_id', 1)

            product_data = {
                'name': product_name,
                'sku': sku,
                'type': 'simple',
                'status': self.config['status'],
                'description': folder.get('description', f'Premium quality {product_name}'),
                'regular_price': str(self.config['regular_price']),
                'manage_stock': manage_stock,
                'stock_status': stock_status,
                'categories': [{'id': category_id}]
            }

            # Only add stock_quantity if managing stock
            if manage_stock:
                product_data['stock_quantity'] = stock_quantity

            if self.config.get('sale_price'):
                product_data['sale_price'] = str(self.config['sale_price'])

            if uploaded_images:
                product_data['images'] = uploaded_images

            # Create product với log chi tiết
            self.log_update.emit(index, "uploading", "📤 Đang tạo sản phẩm...")
            result = api.create_product(product_data)

            if result and result.get('id'):
                product_id = result.get('id')
                product_url = f"{api.base_url}/wp-admin/post.php?post={product_id}&action=edit"

                # Log thành công
                log_msg = f"✅ Upload thành công! ID: {product_id}, Ảnh: {len(uploaded_images)}"
                self.log_update.emit(index, "success", log_msg)

                # Attach images to product to remove (Unattached) status
                if uploaded_images and api.wp_username and api.wp_app_password:
                    self.log_update.emit(index, "processing", "🔗 Đang attach ảnh...")
                    attached_count = 0
                    for img_idx, image in enumerate(uploaded_images):
                        media_id = image.get('id')
                        if media_id and isinstance(product_id, int):
                            try:
                                # Attach ảnh vào sản phẩm
                                success = api.attach_media_to_post(media_id, product_id)
                                if success:
                                    attached_count += 1
                                    self.logger.info(f"Successfully attached media {media_id} to product {product_id}")
                                else:
                                    self.logger.warning(f"Failed to attach media {media_id} to product {product_id}")
                            except Exception as e:
                                self.logger.warning(f"Could not attach image {media_id} to product {product_id}: {str(e)}")

                    # Update log với kết quả attach
                    if attached_count > 0:
                        self.log_update.emit(index, "success", f"✅ Hoàn thành! {attached_count}/{len(uploaded_images)} ảnh attached")

                    # Thêm delay để đảm bảo attachment được xử lý
                    time.sleep(1)

                # Update database - đánh dấá đã hoàn thành để tránh upload lại
                if self.db_manager and folder and folder.get('id'):
                    try:
                        if result is None:
                            raise Exception("API result is None")
                            
                        update_data = {
                            'status': 'completed',
                            'wc_product_id': result.get('id') if result else None,
                            'uploaded_at': datetime.now().isoformat(),
                            'upload_success': 1,  # SQLite boolean = 1
                            'error_message': None,
                            'product_url': product_url  # Lưu URL để truy cập sau
                        }

                        # Sử dụng method update_folder_scan với try-catch
                        try:
                            success = self.db_manager.update_folder_scan(folder.get('id'), update_data)
                            if success:
                                self.logger.info(f"✅ Updated folder {folder.get('id')} status to completed with product ID {result.get('id')}")

                                # Cập nhật saved_scans data nếu folder này là part của batch
                                self.update_saved_scans_after_upload(folder.get('id'), update_data)

                            else:
                                self.logger.error(f"❌ Failed to update folder {folder.get('id')} in database")
                        except Exception as update_error:
                            # Fallback: chỉ update status và wc_product_id
                            self.logger.warning(f"Full update failed, trying minimal update: {str(update_error)}")
                            minimal_data = {
                                'status': 'completed',
                                'wc_product_id': result.get('id'),
                                'product_url': product_url
                            }
                            self.db_manager.update_folder_scan(folder.get('id'), minimal_data)

                    except Exception as db_error:
                        self.logger.error(f"❌ Database update error for folder {folder.get('id')}: {str(db_error)}")

                # Emit với thông tin chi tiết
                result_with_url = dict(result)
                result_with_url['product_url'] = product_url
                self.product_uploaded.emit(index, result_with_url, log_msg)

                return True

            else:
                raise Exception("Không thể tạo sản phẩm trên WooCommerce")

        except Exception as e:
            error_msg = f"❌ Lỗi: {str(e)}"
            self.logger.error(f"Error uploading folder {folder.get('data_name')}: {str(e)}")
            self.log_update.emit(index, "error", error_msg)

            # Update database với trạng thái lỗi
            if self.db_manager and folder.get('id'):
                try:
                    error_data = {
                        'status': 'error',
                        'upload_success': 0,  # SQLite boolean = 0
                        'error_message': str(e),
                        'uploaded_at': datetime.now().isoformat()
                    }
                    # Chỉ update các field cần thiết để tránh lỗi column
                    try:
                        self.db_manager.update_folder_scan(folder.get('id'), error_data)
                        self.logger.info(f"Updated folder {folder.get('id')} status to error")
                    except Exception as update_error:
                        # Fallback: chỉ update status
                        self.logger.warning(f"Full error update failed, trying minimal: {str(update_error)}")
                        minimal_error = {'status': 'error', 'error_message': str(e)}
                        self.db_manager.update_folder_scan(folder.get('id'), minimal_error)
                except Exception as db_error:
                    self.logger.error(f"Database error update failed: {str(db_error)}")

            self.product_uploaded.emit(index, None, error_msg)
            return False

            

        except Exception as e:
            self.logger.error(f"Bulk upload error: {str(e)}")
            self.error_occurred.emit(f"Lỗi upload hàng loạt: {str(e)}")

        finally:
            # Ensure cleanup happens even on exceptions
            try:
                self.folders = None
                self.config = None
                self.db_manager = None
                import gc
                gc.collect()
            except:
                pass

    def rename_images_in_folder(self, folder_path: str, new_title: str):
        """Đổi tên các file ảnh trong folder theo tiêu đề mới"""
        if not new_title or not new_title.strip():
            self.logger.warning(f"Empty title for folder: {folder_path}")
            return False

        try:
            if not os.path.exists(folder_path):
                self.logger.error(f"Folder không tồn tại: {folder_path}")
                return False

            new_title = self.sanitize_filename(new_title.strip())

            if not new_title:
                self.logger.warning(f"Title không hợp lệ sau khi sanitize: {folder_path}")
                return False

            images = [f for f in os.listdir(folder_path) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp'))]

            if not images:
                self.logger.warning(f"Không tìm thấy ảnh trong folder: {folder_path}")
                return False

            self.logger.info(f"Đang đổi tên {len(images)} ảnh trong folder: {folder_path}")
            self.logger.info(f"Tiêu đề mới: {new_title}")

            renamed_count = 0
            for index, image in enumerate(images):
                try:
                    image_path = os.path.join(folder_path, image)
                    name, ext = os.path.splitext(image)

                    # Tạo tên file mới với số thứ tự
                    if index == 0:
                        new_name = f"{new_title}{ext}"
                    else:
                        new_name = f"{new_title}_{index + 1:02d}{ext}"

                    new_path = os.path.join(folder_path, new_name)

                    # Xử lý xung đột tên file
                    counter = 1
                    original_new_path = new_path
                    while os.path.exists(new_path) and new_path != image_path:
                        name_part, ext_part = os.path.splitext(os.path.basename(original_new_path))
                        if index == 0:
                            new_name = f"{name_part}_alt_{counter}{ext_part}"
                        else:
                            new_name = f"{name_part}_alt_{counter}{ext_part}"
                        new_path = os.path.join(folder_path, new_name)
                        counter += 1

                        if counter > 100:
                            self.logger.error(f"Không thể tìm tên file unique cho {image}")
                            break

                    # Chỉ đổi tên nếu tên file khác với tên hiện tại
                    if new_path != image_path and counter <= 100:
                        if os.path.exists(new_path):
                            self.logger.warning(f"File đích vẫn tồn tại, bỏ qua: {new_name}")
                            continue

                        os.rename(image_path, new_path)
                        self.logger.info(f"Đã đổi tên: {image} -> {new_name}")
                        renamed_count += 1
                    else:
                        self.logger.info(f"Bỏ qua file: {image}")

                except Exception as e:
                    self.logger.error(f"Lỗi đổi tên file {image}: {str(e)}")
                    continue

            self.logger.info(f"Đã đổi tên thành công {renamed_count}/{len(images)} ảnh")
            return renamed_count > 0

        except Exception as e:
            self.logger.error(f"Lỗi đổi tên ảnh trong folder {folder_path}: {str(e)}")
            return False

    def cleanup_single_resized_image(self, original_path: str, resized_path: str):
        """Xóa một file ảnh đã resize"""
        try:
            if resized_path != original_path and os.path.exists(resized_path):
                os.remove(resized_path)
                self.logger.info(f"Đã xóa file resize: {os.path.basename(resized_path)}")
        except Exception as e:
            self.logger.warning(f"Không thể xóa file resize {resized_path}: {str(e)}")

    def get_folder_category_id(self, folder):
        """Lấy category ID từ dữ liệu folder"""
        try:
            # Thử lấy category_id từ folder data
            category_id = folder.get('category_id')
            if category_id and self.db_manager:
                # Lấy thông tin category từ database
                category = self.db_manager.get_category_by_id(category_id)
                if category:
                    wc_category_id = category.get('wc_category_id')
                    if wc_category_id:
                        self.logger.info(f"Đã tìm thấy WC category ID {wc_category_id} cho folder {folder.get('data_name', '')}")
                        return wc_category_id

            # Nếu không tìm thấy theo ID, thử tìm theo tên
            category_name = folder.get('category_name')
            if category_name and self.db_manager:
                categories = self.db_manager.get_all_categories()
                for cat in categories:
                    if cat.get('name', '').lower() == category_name.lower():
                        wc_id = cat.get('wc_category_id')
                        if wc_id:
                            self.logger.info(f"Đã tìm thấy WC category ID {wc_id} theo tên '{category_name}' cho folder {folder.get('data_name', '')}")
                            return wc_id

            # Log để debug
            self.logger.info(f"Không tìm thấy category phù hợp cho folder {folder.get('data_name', '')}. Category ID: {category_id}, Name: {category_name}")
            return None

        except Exception as e:
            self.logger.error(f"Lỗi lấy folder category: {str(e)}")
            return None

    def resize_image_if_needed(self, image_path: str, max_size: tuple = (1200, 1200)) -> str:
        """Resize ảnh nếu quá lớn và trả về đường dẫn ảnh đã resize"""
        try:
            if PIL_AVAILABLE:
                with Image.open(image_path) as img:
                    original_size = img.size
            else:
                # Sử dụng PyQt6 thay thế
                pixmap = QPixmap(image_path)
                if pixmap.isNull():
                    return image_path
                original_size = (pixmap.width(), pixmap.height())
                
                # Kiểm tra xem có cần resize không
                if original_size[0] <= max_size[0] and original_size[1] <= max_size[1]:
                    self.logger.info(f"Ảnh {os.path.basename(image_path)} không cần resize: {original_size}")
                    return image_path
                
                # Tính toán kích thước mới giữ tỷ lệ
                ratio = min(max_size[0] / original_size[0], max_size[1] / original_size[1])
                new_size = (int(original_size[0] * ratio), int(original_size[1] * ratio))
                
                # Resize ảnh
                if PIL_AVAILABLE:
                    resized_img = img.resize(new_size, Image.Resampling.LANCZOS)
                else:
                    # Resize bằng PyQt6
                    scaled_pixmap = pixmap.scaled(new_size[0], new_size[1], Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                
                # Tạo tên file mới cho ảnh đã resize
                name, ext = os.path.splitext(image_path)
                resized_path = f"{name}_resized{ext}"
                
                # Lưu ảnh đã resize với chất lượng tối ưu
                if PIL_AVAILABLE:
                    if ext.lower() in ['.jpg', '.jpeg']:
                        resized_img.save(resized_path, 'JPEG', quality=85, optimize=True)
                    elif ext.lower() == '.png':
                        resized_img.save(resized_path, 'PNG', optimize=True)
                    elif ext.lower() == '.webp':
                        resized_img.save(resized_path, 'WEBP', quality=85, optimize=True)
                    else:
                        resized_img.save(resized_path, optimize=True)
                else:
                    # Lưu bằng PyQt6
                    scaled_pixmap.save(resized_path, quality=85)
                
                self.logger.info(f"Đã resize ảnh {os.path.basename(image_path)}: {original_size} → {new_size}")
                return resized_path
                
        except Exception as e:
            self.logger.error(f"Lỗi resize ảnh {image_path}: {str(e)}")
            return image_path  # Trả về ảnh gốc nếu resize thất bại

    def sanitize_filename(self, filename: str) -> str:
        """Làm sạch tên file để tránh ký tự không hợp lệ"""
        import re

        if not filename:
            return ""

        # Loại bỏ các ký tự không hợp lệ cho tên file
        sanitized = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '', filename)

        # Thay thế khoảng trắng liên tiếp bằng dấu gạch dưới
        sanitized = re.sub(r'\s+', '_', sanitized)

        # Loại bỏ dấu chấm ở đầu và cuối
        sanitized = sanitized.strip('.')

        # Giới hạn độ dài tên file
        if len(sanitized) > 100:
            sanitized = sanitized[:100]

        # Loại bỏ ký tự cuối nếu là dấu gạch dưới
        sanitized = sanitized.rstrip('_')

        return sanitized if sanitized else "product"

    def update_saved_scans_after_upload(self, folder_id, update_data):
        """Cập nhật dữ liệu saved_scans sau khi upload thành công"""
        # This function should update the saved_scans list in ProductUploadDialog
        # to reflect the new state of the uploaded folder.
        #
        # It's crucial to ensure the UI is updated correctly.
        try:
            if not folder_id or not update_data:
                self.logger.warning("Không có ID folder hoặc dữ liệu update")
                return

            # Find the corresponding folder in self.folders
            for folder in self.folders:
                if folder.get('id') == folder_id:
                    # Update the folder data in place
                    folder.update(update_data)
                    self.logger.info(f"Đã cập nhật folder {folder_id} trong self.folders")
                    return

            self.logger.warning(f"Không tìm thấy folder {folder_id} trong self.folders")

        except Exception as e:
            self.logger.error(f"Lỗi cập nhật saved_scans data: {str(e)}")

class ImageUploadWorker(QThread):
    """Worker thread để upload ảnh"""
    progress_update = pyqtSignal(int, str)
    image_uploaded = pyqtSignal(dict)
    upload_complete = pyqtSignal(list)
    error_occurred = pyqtSignal(str)

    def __init__(self, api, image_paths, product_name, product_description=None):
        super().__init__()
        self.api = api
        self.image_paths = image_paths
        self.product_name = product_name
        self.product_description = product_description
        self.uploaded_images = []
        self.logger = logging.getLogger(__name__ + ".ImageUploadWorker")

    def resize_image_if_needed(self, image_path: str, max_size: tuple = (1200, 1200)) -> str:
        """Resize ảnh nếu quá lớn và trả về đường dẫn ảnh đã resize"""
        try:
            if PIL_AVAILABLE:
                with Image.open(image_path) as img:
                    original_size = img.size
            else:
                # Sử dụng PyQt6 thay thế
                pixmap = QPixmap(image_path)
                if pixmap.isNull():
                    return image_path
                original_size = (pixmap.width(), pixmap.height())
                
                # Kiểm tra xem có cần resize không
                if original_size[0] <= max_size[0] and original_size[1] <= max_size[1]:
                    self.logger.info(f"Ảnh {os.path.basename(image_path)} không cần resize: {original_size}")
                    return image_path
                
                # Tính toán kích thước mới giữ tỷ lệ
                ratio = min(max_size[0] / original_size[0], max_size[1] / original_size[1])
                new_size = (int(original_size[0] * ratio), int(original_size[1] * ratio))
                
                # Resize ảnh
                if PIL_AVAILABLE:
                    resized_img = img.resize(new_size, Image.Resampling.LANCZOS)
                else:
                    # Resize bằng PyQt6
                    scaled_pixmap = pixmap.scaled(new_size[0], new_size[1], Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                
                # Tạo tên file mới cho ảnh đã resize
                name, ext = os.path.splitext(image_path)
                resized_path = f"{name}_resized{ext}"
                
                # Lưu ảnh đã resize với chất lượng tối ưu
                if PIL_AVAILABLE:
                    if ext.lower() in ['.jpg', '.jpeg']:
                        resized_img.save(resized_path, 'JPEG', quality=85, optimize=True)
                    elif ext.lower() == '.png':
                        resized_img.save(resized_path, 'PNG', optimize=True)
                    elif ext.lower() == '.webp':
                        resized_img.save(resized_path, 'WEBP', quality=85, optimize=True)
                    else:
                        resized_img.save(resized_path, optimize=True)
                else:
                    # Lưu bằng PyQt6
                    scaled_pixmap.save(resized_path, quality=85)
                
                self.logger.info(f"Đã resize ảnh {os.path.basename(image_path)}: {original_size} → {new_size}")
                return resized_path
                
        except Exception as e:
            self.logger.error(f"Lỗi resize ảnh {image_path}: {str(e)}")
            return image_path  # Trả về ảnh gốc nếu resize thất bại

    def run(self):
        """Upload ảnh lên WordPress Media Library"""
        try:
            total_images = len(self.image_paths)

            for i, image_path in enumerate(self.image_paths):
                try:
                    self.progress_update.emit(
                        int((i / total_images) * 100),
                        f"Đang upload ảnh {i+1}/{total_images}: {os.path.basename(image_path)}"
                    )

                    # Resize ảnh trước khi upload (mặc định 1200x1200)
                    resized_img_path = self.resize_image_if_needed(image_path, max_size=(1200, 1200))
                    
                    filename = os.path.basename(resized_img_path)
                    # Sử dụng tên sản phẩm làm title (Caption)
                    title = self.product_name
                    
                    # Sử dụng tên sản phẩm làm Alternative Text
                    alt_text = self.product_name
                    
                    # Sử dụng mô tả sản phẩm làm Description
                    description = ""
                    if hasattr(self, 'product_description') and self.product_description:
                        description = self.product_description
                    else:
                        description = f"Premium quality {self.product_name}. Perfect for any occasion."

                    # Upload lên WordPress với đầy đủ metadata
                    result = self.api.upload_media(resized_img_path, title, alt_text, description)

                    if result and result.get('id'):
                        # Sử dụng dữ liệu trả về từ API đã được format chuẩn
                        uploaded_image = result
                        self.uploaded_images.append(uploaded_image)
                        self.image_uploaded.emit(uploaded_image)
                    else:
                        self.error_occurred.emit(f"Không thể upload ảnh: {filename}")

                except Exception as e:
                    self.error_occurred.emit(f"Lỗi upload {os.path.basename(image_path)}: {str(e)}")
                    continue

            self.progress_update.emit(100, f"Đã upload {len(self.uploaded_images)}/{total_images} ảnh")
            self.upload_complete.emit(self.uploaded_images)
            
            # Cleanup các file ảnh đã resize
            self.cleanup_resized_images()

        except Exception as e:
            self.error_occurred.emit(f"Lỗi upload ảnh: {str(e)}")
            # Cleanup ngay cả khi có lỗi
            self.cleanup_resized_images()

    def cleanup_resized_images(self):
        """Xóa các file ảnh đã resize để tiết kiệm dung lượng"""
        try:
            for image_path in self.image_paths:
                name, ext = os.path.splitext(image_path)
                resized_path = f"{name}_resized{ext}"
                if os.path.exists(resized_path) and resized_path != image_path:
                    try:
                        os.remove(resized_path)
                        self.logger.info(f"Đã xóa file resize: {os.path.basename(resized_path)}")
                    except Exception as e:
                        self.logger.warning(f"Không thể xóa file resize {resized_path}: {str(e)}")
        except Exception as e:
            self.logger.error(f"Lỗi cleanup resized images: {str(e)}")


class ProductUploadDialog(QDialog):
    """Dialog để upload sản phẩm lên WooCommerce"""

    product_uploaded = pyqtSignal(dict)

    def __init__(self, parent=None, sites=None, db_manager=None, selected_folders=None):
        super().__init__(parent)
        self.sites = sites or []
        self.db_manager = db_manager
        self.logger = logging.getLogger(__name__)
        self.folder_scans = []
        self.selected_folder = None
        self.selected_folders = selected_folders or []  # Support for bulk upload
        self.uploaded_images = []
        self.image_upload_worker = None
        self.bulk_upload_worker = None
        self.categories = []  # Store categories list
        self.saved_bulk_config = None  # Lưu cấu hình đã thiết lập

        if self.selected_folders:
            self.setWindowTitle("Cấu hình đăng")
            self.resize(1400, 1050)  # Tăng chiều cao
            self.setMinimumSize(1200, 950)  # Tăng min height
        else:
            self.setWindowTitle("Đăng sản phẩm lên WooCommerce")
            self.resize(1300, 1000)  # Tăng chiều cao
            self.setMinimumSize(1100, 900)  # Tăng min height

        # Maximize window để tận dụng toàn bộ màn hình
        self.showMaximized()

        self.init_ui()

        # Load data với error handling để tránh crash app
        try:
            self.load_folder_scans()
        except Exception as e:
            self.logger.error(f"Failed to load folder scans: {str(e)}")

        try:
            self.load_categories()
        except Exception as e:
            self.logger.error(f"Failed to load categories: {str(e)}")

        # Load cấu hình đã lưu nếu có (cho bulk mode)
        if self.selected_folders:
            try:
                self.load_saved_bulk_config()
            except Exception as e:
                self.logger.error(f"Failed to load saved bulk config: {str(e)}")

    def init_ui(self):
        """Khởi tạo giao diện"""
        layout = QVBoxLayout()
        self.setLayout(layout)

        if self.selected_folders:
            # Bulk upload mode
            self.init_bulk_ui(layout)
        else:
            # Single upload mode
            self.init_single_ui(layout)

    def init_single_ui(self, layout):
        """Giao diện upload đơn lẻ"""
        # Splitter chính với margins tối thiểu
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setContentsMargins(5, 5, 5, 5)
        splitter.setHandleWidth(8)
        layout.addWidget(splitter)

        # Panel trái - Danh sách folder scans
        left_panel = self.create_folder_panel()
        splitter.addWidget(left_panel)

        # Panel phải - Thông tin sản phẩm
        right_panel = self.create_product_panel()
        splitter.addWidget(right_panel)

        # Set tỷ lệ panels tối ưu cho màn hình lớn
        splitter.setSizes([400, 900])
        splitter.setStretchFactor(0, 0)  # Folder panel cố định
        splitter.setStretchFactor(1, 1)  # Product panel mở rộng theo cửa sổ

        # Buttons
        self.create_single_buttons(layout)

    def init_bulk_ui(self, layout):
        """Giao diện upload hàng loạt"""
        # Header info
        info_layout = QHBoxLayout()
        info_label = QLabel(f"📦 Đăng {len(self.selected_folders)} sản phẩm hàng loạt")
        info_label.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        info_layout.addWidget(info_label)
        info_layout.addStretch()
        layout.addLayout(info_layout)

        # Create horizontal layout for settings panels
        settings_layout = QHBoxLayout()
        
        # Bulk settings panel (left)
        bulk_panel = self.create_bulk_settings_panel()
        settings_layout.addWidget(bulk_panel)

        # Threading config panel (right)
        threading_panel = self.create_threading_config_panel()
        settings_layout.addWidget(threading_panel)
        
        layout.addLayout(settings_layout)

        # Preview panel
        preview_panel = self.create_bulk_preview_panel()
        layout.addWidget(preview_panel)

        # Bulk upload buttons
        self.create_bulk_buttons(layout)

    def create_single_buttons(self, layout):
        """Tạo buttons cho upload đơn lẻ"""
        button_layout = QHBoxLayout()

        self.upload_btn = QPushButton("🚀 Đăng sản phẩm")
        self.upload_btn.clicked.connect(self.upload_product)
        self.upload_btn.setEnabled(False)

        button_layout.addWidget(self.upload_btn)

        button_layout.addStretch()

        cancel_btn = QPushButton("Hủy")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        layout.addLayout(button_layout)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("")
        layout.addWidget(self.status_label)

    def populate_folder_list(self):
        """Điền danh sách folder vào list widget"""
        try:
            # Chỉ populate nếu đang ở single mode và có folder_list
            if not hasattr(self, 'folder_list') or self.selected_folders:
                return

            self.folder_list.clear()

            for folder in self.folder_scans:
                folder_name = folder.get('data_name') or folder.get('original_title', 'Unknown')
                image_count = folder.get('image_count', 0)

                item_text = f"{folder_name} ({image_count} ảnh)"
                item = QListWidgetItem(item_text)
                item.setData(Qt.ItemDataRole.UserRole, folder)
                self.folder_list.addItem(item)

        except Exception as e:
            self.logger.error(f"Lỗi populate folder list: {str(e)}")

    def create_folder_panel(self):
        """Tạo panel danh sách folder scans"""
        widget = QWidget()
        widget.setMaximumWidth(450)  # Giới hạn width để panel phải có nhiều không gian hơn
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Header
        header_label = QLabel("📁 Danh sách thư mục đã quét")
        header_label.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        header_label.setMinimumHeight(35)
        header_label.setStyleSheet("background-color: #f0f0f0; padding: 8px; border-radius: 4px;")
        header_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header_label)

        # List widget với size policy mở rộng
        self.folder_list = QListWidget()
        self.folder_list.itemClicked.connect(self.on_folder_selected)
        from PyQt6.QtWidgets import QSizePolicy
        self.folder_list.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.folder_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #ccc;
                border-radius: 4px;
                background-color: white;
                alternate-background-color: #f9f9f9;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #eee;
            }
            QListWidget::item:selected {
                background-color: #0078d4;
                color: white;
            }
        """)
        layout.addWidget(self.folder_list)

        # Refresh button
        refresh_btn = QPushButton("🔄 Làm mới")
        refresh_btn.setMinimumHeight(40)
        refresh_btn.setStyleSheet("""
            QPushButton {
                font-weight: bold;
                padding: 8px 16px;
                border-radius: 6px;
            }
        """)
        refresh_btn.clicked.connect(self.load_folder_scans)
        layout.addWidget(refresh_btn)

        return widget

    def create_product_panel(self):
        """Tạo panel thông tin sản phẩm"""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        # Site selection với grid layout
        site_group = QGroupBox("🌐 Cấu hình site và danh mục")
        site_group.setStyleSheet("QGroupBox { font-weight: bold; padding-top: 15px; }")
        site_layout = QGridLayout(site_group)
        site_layout.setVerticalSpacing(10)
        site_layout.setHorizontalSpacing(15)

        # Row 1: Site
        site_layout.addWidget(QLabel("Site:"), 0, 0)
        self.site_combo = QComboBox()
        self.site_combo.setMinimumHeight(35)
        self.site_combo.currentIndexChanged.connect(self.on_site_changed)
        for site in self.sites:
            self.site_combo.addItem(site.name, site.id)
        site_layout.addWidget(self.site_combo, 0, 1)

        # Row 2: Category
        site_layout.addWidget(QLabel("Danh mục:"), 1, 0)
        self.category_combo = QComboBox()
        self.category_combo.setMinimumHeight(35)
        self.category_combo.addItem("Chọn danh mục...", None)
        site_layout.addWidget(self.category_combo, 1, 1)

        layout.addWidget(site_group)

        # Product info với grid layout 2 cột
        product_group = QGroupBox("📦 Thông tin sản phẩm")
        product_group.setStyleSheet("QGroupBox { font-weight: bold; padding-top: 15px; }")
        product_layout = QGridLayout(product_group)
        product_layout.setVerticalSpacing(10)
        product_layout.setHorizontalSpacing(15)

        # Row 1: Tên sản phẩm (span 2 columns)
        product_layout.addWidget(QLabel("Tên sản phẩm:"), 0, 0)
        self.name_edit = QLineEdit()
        self.name_edit.setMinimumHeight(35)
        product_layout.addWidget(self.name_edit, 0, 1, 1, 2)  # span 2 columns

        # Row 2: SKU và Status
        product_layout.addWidget(QLabel("SKU:"), 1, 0)
        self.sku_edit = QLineEdit()
        self.sku_edit.setMinimumHeight(35)
        product_layout.addWidget(self.sku_edit, 1, 1)

        product_layout.addWidget(QLabel("Trạng thái:"), 1, 2)
        self.status_combo = QComboBox()
        self.status_combo.setMinimumHeight(35)
        self.status_combo.addItems(["publish", "draft", "private"])
        product_layout.addWidget(self.status_combo, 1, 3)

        # Row 3: Giá gốc và Giá sale
        product_layout.addWidget(QLabel("Giá gốc ($):"), 2, 0)
        self.regular_price_spin = QDoubleSpinBox()
        self.regular_price_spin.setMinimumHeight(35)
        self.regular_price_spin.setRange(0, 999999)
        self.regular_price_spin.setDecimals(2)
        self.regular_price_spin.setValue(25.00)
        product_layout.addWidget(self.regular_price_spin, 2, 1)

        product_layout.addWidget(QLabel("Giá sale ($):"), 2, 2)
        self.sale_price_spin = QDoubleSpinBox()
        self.sale_price_spin.setMinimumHeight(35)
        self.sale_price_spin.setRange(0, 999999)
        self.sale_price_spin.setDecimals(2)
        product_layout.addWidget(self.sale_price_spin, 2, 3)

        # Row 4: Số lượng và quản lý kho
        product_layout.addWidget(QLabel("Số lượng:"), 3, 0)
        self.stock_spin = QSpinBox()
        self.stock_spin.setMinimumHeight(35)
        self.stock_spin.setRange(0, 999999)
        self.stock_spin.setValue(100)
        product_layout.addWidget(self.stock_spin, 3, 1)

        # Checkbox để quản lý kho - ẩn và tắt mặc định
        self.manage_stock_cb = QCheckBox("Quản lý kho hàng")
        self.manage_stock_cb.setChecked(False)  # Tắt mặc định
        self.manage_stock_cb.setVisible(False)  # Ẩn checkbox

        # Stock status
        product_layout.addWidget(QLabel("Tình trạng:"), 3, 3)
        self.stock_status_combo = QComboBox()
        self.stock_status_combo.setMinimumHeight(35)
        self.stock_status_combo.addItems(["instock", "outofstock", "onbackorder"])
        self.stock_status_combo.setCurrentText("instock")
        product_layout.addWidget(self.stock_status_combo, 3, 4)

        layout.addWidget(product_group)

        # Description - chỉ mô tả chi tiết, mở rộng full width
        desc_group = QGroupBox("📝 Mô tả sản phẩm")
        desc_group.setStyleSheet("QGroupBox { font-weight: bold; padding-top: 15px; }")
        desc_layout = QVBoxLayout(desc_group)
        desc_layout.setSpacing(10)

        # Chỉ mô tả chi tiết - mở rộng full width và tăng chiều cao
        desc_layout.addWidget(QLabel("Mô tả chi tiết:"))
        self.desc_edit = QTextEdit()
        self.desc_edit.setMinimumHeight(200)  # Tăng chiều cao
        self.desc_edit.setMaximumHeight(300)  # Tăng max height
        self.desc_edit.setPlaceholderText("Mô tả chi tiết về sản phẩm...")
        desc_layout.addWidget(self.desc_edit)

        # Tạo short_desc_edit ẩn để tương thích với code hiện tại
        self.short_desc_edit = QTextEdit()
        self.short_desc_edit.setVisible(False)

        layout.addWidget(desc_group)

        # Images section với layout tối ưu
        images_group = QGroupBox("🖼️ Quản lý hình ảnh")
        images_group.setStyleSheet("QGroupBox { font-weight: bold; padding-top: 15px; }")
        images_layout = QVBoxLayout(images_group)
        images_layout.setSpacing(10)

        # Images list với style
        self.images_list = QListWidget()
        self.images_list.setMinimumHeight(180)
        self.images_list.setMaximumHeight(220)
        self.images_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #ccc;
                border-radius: 4px;
                background-color: white;
            }
            QListWidget::item {
                padding: 6px;
                border-bottom: 1px solid #eee;
            }
            QListWidget::item:selected {
                background-color: #0078d4;
                color: white;
            }
        """)
        images_layout.addWidget(self.images_list)

        # Buttons layout
        images_btn_layout = QHBoxLayout()
        images_btn_layout.setSpacing(10)

        self.add_images_btn = QPushButton("➕ Thêm ảnh")
        self.add_images_btn.setMinimumHeight(40)
        self.add_images_btn.setStyleSheet("font-weight: bold; padding: 8px 16px;")
        self.add_images_btn.clicked.connect(self.add_images)
        images_btn_layout.addWidget(self.add_images_btn)

        self.remove_image_btn = QPushButton("🗑️ Xóa ảnh")
        self.remove_image_btn.setMinimumHeight(40)
        self.remove_image_btn.setStyleSheet("font-weight: bold; padding: 8px 16px;")
        self.remove_image_btn.clicked.connect(self.remove_image)
        images_btn_layout.addWidget(self.remove_image_btn)

        images_btn_layout.addStretch()

        images_layout.addLayout(images_btn_layout)

        layout.addWidget(images_group)

        # Add stretch to fill remaining space
        layout.addStretch()

        scroll.setWidget(widget)
        scroll.setWidgetResizable(True)
        scroll.setMinimumWidth(400)
        return scroll

    def load_folder_scans(self):
        """Load danh sách folder scans từ database"""
        if not self.db_manager:
            return

        try:
            self.folder_scans = self.db_manager.get_all_folder_scans()

            # Chỉ populate folder_list nếu đang ở single mode
            if hasattr(self, 'folder_list') and not self.selected_folders:
                self.folder_list.clear()

                for folder in self.folder_scans:
                    item_text = f"{folder.get('data_name', 'Unknown')}\n📁 {folder.get('path', 'No path')}"
                    if folder.get('image_count', 0) > 0:
                        item_text += f"\n🖼️ {folder.get('image_count')} ảnh"

                    item = QListWidgetItem(item_text)
                    item.setData(Qt.ItemDataRole.UserRole, folder)
                    self.folder_list.addItem(item)

        except Exception as e:
            self.logger.error(f"Lỗi load folder scans: {str(e)}")

    def on_folder_selected(self, item):
        """Xử lý khi chọn folder"""
        folder_data = item.data(Qt.ItemDataRole.UserRole)
        if folder_data:
            self.selected_folder = folder_data
            self.populate_product_info(folder_data)
            self.load_folder_images(folder_data.get('path', ''))
            self.set_folder_category(folder_data)
            self.upload_btn.setEnabled(True)

    def populate_product_info(self, folder_data):
        """Điền thông tin sản phẩm từ folder data"""
        # Tên sản phẩm - ưu tiên new_title, fallback về data_name
        product_name = folder_data.get('new_title', '') or folder_data.get('data_name', 'Untitled Product')
        self.name_edit.setText(product_name)

        # SKU chỉ dùng số (hash của tên sản phẩm)
        import hashlib
        import time

        # Tạo SKU số từ hash của product name + timestamp
        hash_input = f"{product_name}{int(time.time())}"
        hash_object = hashlib.md5(hash_input.encode())
        sku = str(int(hash_object.hexdigest()[:8], 16))  # Lấy 8 ký tự đầu và convert sang số
        self.sku_edit.setText(sku)

        # Mô tả
        description = folder_data.get('description', '')
        if not description:
            description = f"Premium quality {product_name}. Perfect for any occasion."
        self.desc_edit.setText(description)

        # Mô tả ngắn - bỏ qua vì đã ẩn
        # self.short_desc_edit.setText("")  # Bỏ mô tả ngắn

    def set_folder_category(self, folder_data):
        """Set category từ dữ liệu folder"""
        try:
            # Thử lấy category_id từ folder data
            category_id = folder_data.get('category_id')
            category_name = folder_data.get('category_name')

            if category_id and self.db_manager:
                # Lấy thông tin category từ database
                category = self.db_manager.get_category_by_id(category_id)
                if category:
                    wc_category_id = category.get('wc_category_id')
                    if wc_category_id:
                        # Tìm và set trong combo box theo WC ID
                        for i in range(self.category_combo.count()):
                            if self.category_combo.itemData(i) == wc_category_id:
                                self.category_combo.setCurrentIndex(i)
                                self.logger.info(f"Đã set category: {category.get('name', '')} (ID: {wc_category_id})")
                                return

            # Nếu không tìm thấy theo ID, thử tìm theo tên
            if category_name:
                for i in range(self.category_combo.count()):
                    combo_text = self.category_combo.itemText(i)
                    if category_name.lower() in combo_text.lower():
                        self.category_combo.setCurrentIndex(i)
                        self.logger.info(f"Đã set category theo tên: {category_name}")
                        return

            # Log để debug
            self.logger.info(f"Không tìm thấy category phù hợp. Category ID: {category_id}, Name: {category_name}")

        except Exception as e:
            self.logger.error(f"Lỗi set folder category: {str(e)}")

    def load_folder_images(self, folder_path):
        """Load ảnh từ folder"""
        self.images_list.clear()

        if not os.path.exists(folder_path):
            return

        try:
            image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'}
            image_files = []

            for file in os.listdir(folder_path):
                if any(file.lower().endswith(ext) for ext in image_extensions):
                    image_files.append(os.path.join(folder_path, file))

            for image_path in sorted(image_files):
                item = QListWidgetItem(f"🖼️ {os.path.basename(image_path)}")
                item.setData(Qt.ItemDataRole.UserRole, image_path)
                self.images_list.addItem(item)

        except Exception as e:
            self.logger.error(f"Lỗi load ảnh từ folder: {str(e)}")

    def add_images(self):
        """Thêm ảnh từ file dialog"""
        files, _ = QFileDialog.getOpenFileNames(
            self, "Chọn ảnh",
            "",
            "Image Files (*.png *.jpg *.jpeg *.gif *.bmp *.webp)"
        )

        for file_path in files:
            item = QListWidgetItem(f"🖼️ {os.path.basename(file_path)}")
            item.setData(Qt.ItemDataRole.UserRole, file_path)
            self.images_list.addItem(item)

    def remove_image(self):
        """Xóa ảnh được chọn"""
        current_row = self.images_list.currentRow()
        if current_row >= 0:
            self.images_list.takeItem(current_row)

    def get_image_paths(self):
        """Lấy danh sách đường dẫn ảnh"""
        image_paths = []
        for i in range(self.images_list.count()):
            item = self.images_list.item(i)
            image_path = item.data(Qt.ItemDataRole.UserRole)
            if image_path and os.path.exists(image_path):
                image_paths.append(image_path)
        return image_paths

    def upload_product(self):
        """Upload sản phẩm lên WooCommerce"""
        if not self.validate_input():
            return

        try:
            # Disable upload button
            self.upload_btn.setEnabled(False)
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)

            # Get selected site
            site_id = self.site_combo.currentData()
            selected_site = None
            for site in self.sites:
                if site.id == site_id:
                    selected_site = site
                    break

            if not selected_site:
                raise Exception("Không tìm thấy site được chọn")

            api = WooCommerceAPI(selected_site)

            # Get image paths
            image_paths = self.get_image_paths()
            product_name = self.name_edit.text()

            if image_paths:
                # Upload ảnh trước
                self.status_label.setText("Đang upload ảnh...")
                product_description = self.desc_edit.toPlainText()
                self.image_upload_worker = ImageUploadWorker(api, image_paths, product_name, product_description)
                self.image_upload_worker.progress_update.connect(self.on_upload_progress)
                self.image_upload_worker.image_uploaded.connect(self.on_image_uploaded)
                self.image_upload_worker.upload_complete.connect(self.on_images_uploaded)
                self.image_upload_worker.error_occurred.connect(self.on_upload_error)
                self.image_upload_worker.start()
            else:
                # Tạo sản phẩm không có ảnh
                self.create_product_without_images(api)

        except Exception as e:
            self.logger.error(f"Lỗi upload sản phẩm: {str(e)}")
            QMessageBox.critical(self, "Lỗi", f"Không thể upload sản phẩm:\n{str(e)}")
            self.reset_upload_state()

    def validate_input(self):
        """Validate input trước khi upload"""
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "Cảnh báo", "Vui lòng nhập tên sản phẩm!")
            return False

        if self.site_combo.currentData() is None:
            QMessageBox.warning(self, "Cảnh báo", "Vui lòng chọn site!")
            return False

        return True

    def on_upload_progress(self, percent, message):
        """Cập nhật tiến độ upload"""
        self.progress_bar.setValue(percent)
        self.status_label.setText(message)

    def on_image_uploaded(self, image_data):
        """Xử lý khi một ảnh được upload"""
        self.uploaded_images.append(image_data)

    def on_images_uploaded(self, uploaded_images):
        """Xử lý khi tất cả ảnh đã upload"""
        self.uploaded_images = uploaded_images
        self.status_label.setText("Đang tạo sản phẩm...")

        # Tạo sản phẩm với ảnh
        site_id = self.site_combo.currentData()
        selected_site = None
        for site in self.sites:
            if site.id == site_id:
                selected_site = site
                break

        if selected_site:
            api = WooCommerceAPI(selected_site)
            self.create_product_with_images(api, uploaded_images)
        else:
            self.on_upload_error("Không tìm thấy site được chọn")

    def create_product_with_images(self, api, uploaded_images):
        """Tạo sản phẩm có ảnh"""
        try:
            product_data = self.get_product_data()

            # Thêm ảnh vào product data
            product_data['images'] = uploaded_images

            result = api.create_product(product_data)

            if result and result.get('id'):
                self.progress_bar.setValue(100)
                self.status_label.setText("Đăng sản phẩm thành công!")

                QMessageBox.information(
                    self, "Thành công",
                    f"Đã đăng sản phẩm '{result.get('name')}' lên {api.site.name}!\n"
                    f"Product ID: {result.get('id')}\n"
                    f"Số ảnh: {len(uploaded_images)}"
                )

                self.product_uploaded.emit(result)
                self.accept()
            else:
                raise Exception("Không thể tạo sản phẩm trên WooCommerce")

        except Exception as e:
            self.on_upload_error(f"Lỗi tạo sản phẩm: {str(e)}")

    def create_product_without_images(self, api):
        """Tạo sản phẩm không có ảnh"""
        try:
            self.status_label.setText("Đang tạo sản phẩm...")
            product_data = self.get_product_data()

            result = api.create_product(product_data)

            if result and result.get('id'):
                self.progress_bar.setValue(100)
                self.status_label.setText("Đăng sản phẩm thành công!")

                QMessageBox.information(
                    self, "Thành công",
                    f"Đã đăng sản phẩm '{result.get('name')}' lên {api.site.name}!\n"
                    f"Product ID: {result.get('id')}\n"
                    f"Lưu ý: Sản phẩm chưa có ảnh"
                )

                self.product_uploaded.emit(result)
                self.accept()
            else:
                raise Exception("Không thể tạo sản phẩm trên WooCommerce")

        except Exception as e:
            self.on_upload_error(f"Lỗi tạo sản phẩm: {str(e)}")

    def get_product_data(self):
        """Lấy dữ liệu sản phẩm từ form"""
        # Get selected category
        selected_category_id = self.category_combo.currentData()
        categories = []
        if selected_category_id:
            categories = [{'id': selected_category_id}]
        else:
            categories = [{'id': 1}]  # Default category if none selected

        # Tắt quản lý kho mặc định
        manage_stock = False  # Luôn tắt quản lý kho
        stock_status = 'instock'  # Mặc định luôn có hàng

        product_data = {
            'name': self.name_edit.text().strip(),
            'sku': self.sku_edit.text().strip(),
            'type': 'simple',
            'status': self.status_combo.currentText(),
            'description': self.desc_edit.toPlainText(),
            'regular_price': str(self.regular_price_spin.value()),
            'sale_price': str(self.sale_price_spin.value()) if self.sale_price_spin.value() > 0 else '',
            'manage_stock': manage_stock,
            'stock_status': stock_status,
            'categories': categories
        }

        # Only add stock_quantity if managing stock
        if manage_stock:
            product_data['stock_quantity'] = self.stock_spin.value()

        return product_data

    def on_upload_error(self, error_message):
        """Xử lý lỗi upload"""
        self.logger.error(f"Upload error: {error_message}")
        QMessageBox.critical(self, "Lỗi upload", error_message)
        self.reset_upload_state()

    def reset_upload_state(self):
        """Reset trạng thái upload"""
        if hasattr(self, 'upload_btn'):
            self.upload_btn.setEnabled(True)
        if hasattr(self, 'bulk_upload_btn'):
            self.bulk_upload_btn.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.status_label.setText("")
        self.uploaded_images = []

    def load_categories(self):
        """Load danh sách categories từ database"""
        if not self.db_manager:
            return

        try:
            # Load tất cả categories
            self.categories = self.db_manager.get_all_categories()
            self.update_category_combo()

        except Exception as e:
            self.logger.error(f"Lỗi load categories: {str(e)}")

    def update_category_combo(self):
        """Cập nhật category combobox dựa trên site được chọn"""
        if not hasattr(self, 'category_combo'):
            return

        # Clear current items (keep default item)
        self.category_combo.clear()
        self.category_combo.addItem("Chọn danh mục...", None)

        # Get current selected site
        site_id = self.site_combo.currentData()
        if not site_id:
            return

        # Filter categories by site
        site_categories = [cat for cat in self.categories if cat.get('site_id') == site_id]

        # Group categories by parent
        parent_categories = [cat for cat in site_categories if not cat.get('parent_id') or cat.get('parent_id') == 0]
        child_categories = [cat for cat in site_categories if cat.get('parent_id') and cat.get('parent_id') != 0]

        # Add parent categories first
        for cat in sorted(parent_categories, key=lambda x: x.get('name', '')):
            wc_id = cat.get('wc_category_id')
            if wc_id:  # Only show synced categories
                self.category_combo.addItem(f"📁 {cat.get('name', '')}", wc_id)

                # Add child categories under parent
                children = [c for c in child_categories if c.get('parent_id') == cat.get('id')]
                for child in sorted(children, key=lambda x: x.get('name', '')):
                    child_wc_id = child.get('wc_category_id')
                    if child_wc_id:
                        self.category_combo.addItem(f"  └── {child.get('name', '')}", child_wc_id)

        # Update bulk category combo if exists
        if hasattr(self, 'bulk_category_combo'):
            self.bulk_category_combo.clear()
            self.bulk_category_combo.addItem("Chọn danh mục...", None)

            # Copy items from main category combo
            for i in range(1, self.category_combo.count()):  # Skip default item
                text = self.category_combo.itemText(i)
                data = self.category_combo.itemData(i)
                self.bulk_category_combo.addItem(text, data)

    def on_site_changed(self):
        """Xử lý khi thay đổi site"""
        self.update_category_combo()

    def on_bulk_site_changed(self):
        """Xử lý khi thay đổi site trong bulk mode"""
        if not hasattr(self, 'bulk_category_combo'):
            return

        # Clear current items
        self.bulk_category_combo.clear()
        self.bulk_category_combo.addItem("Chọn danh mục...", None)

        # Get current selected site
        site_id = self.bulk_site_combo.currentData()
        if not site_id or not self.categories:
            return

        # Filter categories by site
        site_categories = [cat for cat in self.categories if cat.get('site_id') == site_id]

        # Group categories by parent
        parent_categories = [cat for cat in site_categories if not cat.get('parent_id') or cat.get('parent_id') == 0]
        child_categories = [cat for cat in site_categories if cat.get('parent_id') and cat.get('parent_id') != 0]

        # Add parent categories first
        for cat in sorted(parent_categories, key=lambda x: x.get('name', '')):
            wc_id = cat.get('wc_category_id')
            if wc_id:  # Only show synced categories
                self.bulk_category_combo.addItem(f"📁 {cat.get('name', '')}", wc_id)

                # Add child categories under parent
                children = [c for c in child_categories if c.get('parent_id') == cat.get('id')]
                for child in sorted(children, key=lambda x: x.get('name', '')):
                    child_wc_id = child.get('wc_category_id')
                    if child_wc_id:
                        self.bulk_category_combo.addItem(f"  └── {child.get('name', '')}", child_wc_id)

    def on_threading_toggled(self, checked):
        """Xử lý khi bật/tắt chế độ đa luồng"""
        try:
            # Enable/disable threading controls
            self.max_threads.setEnabled(checked)
            self.thread_delay.setEnabled(checked)
            self.threading_warning.setVisible(checked)
            self.threading_info.setVisible(checked)
            
            # Adjust upload delay based on threading mode
            if checked:
                # Reduce delay when using threading
                if self.upload_delay.value() > 2:
                    self.upload_delay.setValue(1)
                self.upload_delay.setMaximum(10)  # Lower max for threading mode
                self.upload_delay.setToolTip("Thời gian chờ giữa các upload trong cùng thread")
            else:
                # Restore normal delay range
                self.upload_delay.setMaximum(60)
                if self.upload_delay.value() < 3:
                    self.upload_delay.setValue(3)
                self.upload_delay.setToolTip("Thời gian chờ giữa các upload đơn lẻ")
                
            self.logger.info(f"Threading mode {'enabled' if checked else 'disabled'}")
            
        except Exception as e:
            self.logger.error(f"Error toggling threading: {str(e)}")

    def create_bulk_settings_panel(self):
        """Tạo panel cài đặt cho upload hàng loạt"""
        group = QGroupBox("⚙️ Cài đặt hàng loạt")
        group.setStyleSheet("QGroupBox { font-weight: bold; padding-top: 15px; }")
        layout = QFormLayout(group)
        layout.setSpacing(10)
        layout.setContentsMargins(15, 20, 15, 15)

        # Site selection
        self.bulk_site_combo = QComboBox()
        self.bulk_site_combo.setMinimumHeight(35)
        self.bulk_site_combo.currentIndexChanged.connect(self.on_bulk_site_changed)
        for site in self.sites:
            self.bulk_site_combo.addItem(site.name, site.id)
        layout.addRow("Site:", self.bulk_site_combo)

        # Category selection for bulk upload
        self.bulk_category_combo = QComboBox()
        self.bulk_category_combo.setMinimumHeight(35)
        self.bulk_category_combo.addItem("Chọn danh mục...", None)
        layout.addRow("Danh mục:", self.bulk_category_combo)

        # Load categories first, then populate combo
        self.load_categories()
        if self.sites:
            self.on_bulk_site_changed()

        # Common settings
        self.bulk_status_combo = QComboBox()
        self.bulk_status_combo.setMinimumHeight(35)
        self.bulk_status_combo.addItems(["publish", "draft", "private"])
        self.bulk_status_combo.setCurrentText("publish")  # Set default
        layout.addRow("Trạng thái:", self.bulk_status_combo)

        self.bulk_regular_price = QDoubleSpinBox()
        self.bulk_regular_price.setMinimumHeight(35)
        self.bulk_regular_price.setRange(0, 999999)
        self.bulk_regular_price.setDecimals(2)
        self.bulk_regular_price.setValue(25.00)
        layout.addRow("Giá gốc ($):", self.bulk_regular_price)

        self.bulk_sale_price = QDoubleSpinBox()
        self.bulk_sale_price.setMinimumHeight(35)
        self.bulk_sale_price.setRange(0, 999999)
        self.bulk_sale_price.setDecimals(2)
        layout.addRow("Giá sale ($):", self.bulk_sale_price)

        self.bulk_stock = QSpinBox()
        self.bulk_stock.setMinimumHeight(35)
        self.bulk_stock.setRange(0, 999999)
        self.bulk_stock.setValue(100)
        layout.addRow("Số lượng:", self.bulk_stock)

        # Stock management for bulk - Tắt mặc định như single upload
        self.bulk_manage_stock = QCheckBox("Quản lý kho hàng")
        self.bulk_manage_stock.setChecked(False)  # Tắt mặc định
        layout.addRow("", self.bulk_manage_stock)

        self.bulk_stock_status = QComboBox()
        self.bulk_stock_status.setMinimumHeight(35)
        self.bulk_stock_status.addItems(["instock", "outofstock", "onbackorder"])
        self.bulk_stock_status.setCurrentText("instock")
        layout.addRow("Tình trạng kho:", self.bulk_stock_status)

        # Delay between uploads
        self.upload_delay = QSpinBox()
        self.upload_delay.setMinimumHeight(35)
        self.upload_delay.setRange(1, 60)
        self.upload_delay.setValue(3)
        self.upload_delay.setSuffix(" giây")
        layout.addRow("Thời gian chờ giữa các upload:", self.upload_delay)

        return group

    def create_threading_config_panel(self):
        """Tạo panel cấu hình đa luồng riêng biệt"""
        group = QGroupBox("🔧 Cấu hình đa luồng")
        group.setStyleSheet("QGroupBox { font-weight: bold; padding-top: 15px; }")
        layout = QFormLayout(group)
        layout.setSpacing(10)
        layout.setContentsMargins(15, 20, 15, 15)
        
        # Enable multi-threading
        self.enable_threading = QCheckBox("Bật upload đa luồng")
        self.enable_threading.setChecked(False)  # Default disabled for safety
        self.enable_threading.toggled.connect(self.on_threading_toggled)
        layout.addRow("", self.enable_threading)
        
        # Max concurrent uploads
        self.max_threads = QSpinBox()
        self.max_threads.setMinimumHeight(35)
        self.max_threads.setRange(1, 10)
        self.max_threads.setValue(3)
        self.max_threads.setSuffix(" luồng")
        self.max_threads.setEnabled(False)  # Disabled by default
        layout.addRow("Số luồng tối đa:", self.max_threads)
        
        # Info label thay cho batch size
        self.threading_info = QLabel("Các luồng sẽ tự động lấy sản phẩm tiếp theo khi hoàn thành")
        self.threading_info.setStyleSheet("color: #666; font-size: 10px; font-style: italic;")
        self.threading_info.setVisible(False)
        layout.addRow("", self.threading_info)
        
        # Thread delay
        self.thread_delay = QSpinBox()
        self.thread_delay.setMinimumHeight(35)
        self.thread_delay.setRange(0, 30)
        self.thread_delay.setValue(1)
        self.thread_delay.setSuffix(" giây")
        self.thread_delay.setEnabled(False)  # Disabled by default
        layout.addRow("Thời gian chờ giữa các luồng:", self.thread_delay)
        
        # Warning label
        self.threading_warning = QLabel("⚠️ Chế độ đa luồng có thể gây quá tải server. Sử dụng cẩn thận!")
        self.threading_warning.setStyleSheet("color: #ff6b35; font-size: 9px; font-style: italic;")
        self.threading_warning.setVisible(False)
        layout.addRow("", self.threading_warning)

        return group

    def create_bulk_preview_panel(self):
        """Tạo panel preview cho bulk upload"""
        group = QGroupBox("📋 Danh sách sản phẩm sẽ đăng")
        group.setStyleSheet("QGroupBox { font-weight: bold; padding-top: 15px; }")
        layout = QVBoxLayout(group)
        layout.setContentsMargins(12, 12, 12, 12)

        # Table preview với responsive design
        from PyQt6.QtWidgets import QTableWidget, QTableWidgetItem, QSizePolicy, QHeaderView

        self.bulk_table = QTableWidget()
        self.bulk_table.setColumnCount(9)
        self.bulk_table.setHorizontalHeaderLabels([
            "Tên sản phẩm", "Đường dẫn", "Số ảnh", "SKU", "Danh mục", "Mô tả", "Site đăng", "Trạng thái", "Chi tiết/Link"
        ])

        # Set table properties for full window utilization
        self.bulk_table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # Advanced column sizing for better space utilization
        header = self.bulk_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)           # Tên sản phẩm - stretch
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)  # Đường dẫn - content
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)             # Số ảnh - fixed
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)  # SKU - content
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)  # Danh mục - content
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)           # Mô tả - stretch
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)  # Site đăng - content
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.ResizeToContents)  # Trạng thái - content
        header.setSectionResizeMode(8, QHeaderView.ResizeMode.Stretch)           # Chi tiết/Link - stretch

        # Set fixed column widths for specific columns
        self.bulk_table.setColumnWidth(2, 80)   # Số ảnh column

        # Table styling
        self.bulk_table.setAlternatingRowColors(True)
        self.bulk_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.bulk_table.setStyleSheet("""
            QTableWidget {
                gridline-color: #e0e0e0;
                background-color: white;
                border: 1px solid #ccc;
                border-radius: 4px;
            }
            QTableWidget::item {
                padding: 8px;
                border-bottom: 1px solid #f0f0f0;
            }
            QHeaderView::section {
                background-color: #f8f9fa;
                padding: 10px;
                border: 1px solid #dee2e6;
                font-weight: bold;
            }
        """)

        # Populate preview table
        self.populate_bulk_preview()

        # Kết nối click handler
        self.bulk_table.itemClicked.connect(self.on_bulk_table_clicked)

        layout.addWidget(self.bulk_table)
        return group

    def populate_bulk_preview(self):
        """Điền preview table cho bulk upload"""
        from PyQt6.QtWidgets import QTableWidgetItem

        if not hasattr(self, 'bulk_table'):
            return

        self.bulk_table.setRowCount(len(self.selected_folders))

        for row, folder in enumerate(self.selected_folders):
            try:
                # Product name - ưu tiên new_title
                name = folder.get('new_title', '') or folder.get('data_name', folder.get('original_title', 'Untitled'))
                self.bulk_table.setItem(row, 0, QTableWidgetItem(str(name)))

                # Path
                path = folder.get('path', '')
                self.bulk_table.setItem(row, 1, QTableWidgetItem(str(path)))

                # Image count
                count = str(folder.get('image_count', 0))
                self.bulk_table.setItem(row, 2, QTableWidgetItem(count))

                # SKU chỉ dùng số
                import hashlib
                hash_input = f"{name}{folder.get('id', '')}"
                hash_object = hashlib.md5(hash_input.encode())
                sku = str(int(hash_object.hexdigest()[:8], 16))
                self.bulk_table.setItem(row, 3, QTableWidgetItem(sku))

                # Category - hiển thị tên danh mục từ folder data
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
                
                self.bulk_table.setItem(row, 4, QTableWidgetItem(str(category_name)))

                # Description
                desc = folder.get('description', '')
                if not desc:
                    desc = f"Premium quality {name}"
                if len(desc) > 50:
                    desc = desc[:50] + "..."
                self.bulk_table.setItem(row, 5, QTableWidgetItem(str(desc)))

                # Site đăng - lấy từ bulk config hoặc folder data
                site_name = "Sẽ chọn"
                if hasattr(self, 'bulk_site_combo') and self.bulk_site_combo.currentText():
                    site_name = self.bulk_site_combo.currentText()
                elif folder.get('site_name'):
                    site_name = folder.get('site_name')
                self.bulk_table.setItem(row, 6, QTableWidgetItem(str(site_name)))

                # Status với màu sắc để dễ phân biệt
                status_item = QTableWidgetItem("⏳ Chờ upload")
                status_item.setBackground(QColor(255, 248, 220))  # Light yellow
                self.bulk_table.setItem(row, 7, status_item)
                
                # Chi tiết/Log column
                log_item = QTableWidgetItem("📋 Chưa bắt đầu")
                log_item.setBackground(QColor(248, 248, 248))  # Light gray
                self.bulk_table.setItem(row, 8, log_item)

            except Exception as e:
                self.logger.error(f"Error populating row {row}: {str(e)}")
                continue

        # Resize columns after populating
        try:
            self.bulk_table.resizeColumnsToContents()
        except Exception as e:
            self.logger.error(f"Error resizing columns: {str(e)}")

    def create_bulk_buttons(self, layout):
        """Tạo buttons cho bulk upload"""
        button_layout = QHBoxLayout()

        # Nút lưu cấu hình
        save_btn = QPushButton("💾 Lưu")
        save_btn.clicked.connect(self.save_bulk_config)
        save_btn.setStyleSheet("""
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
        button_layout.addWidget(save_btn)

        self.bulk_upload_btn = QPushButton("🚀 Đăng hàng loạt")
        self.bulk_upload_btn.clicked.connect(self.start_bulk_upload)
        button_layout.addWidget(self.bulk_upload_btn)

        button_layout.addStretch()

        cancel_btn = QPushButton("Hủy")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        layout.addLayout(button_layout)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("")
        layout.addWidget(self.status_label)

    def start_bulk_upload(self):
        """Bắt đầu upload hàng loạt"""
        if not self.validate_bulk_input():
            return

        try:
            # Get selected site
            site_id = self.bulk_site_combo.currentData()
            selected_site = None
            for site in self.sites:
                if site.id == site_id:
                    selected_site = site
                    break

            if not selected_site:
                raise Exception("Không tìm thấy site được chọn")

            # Prepare bulk upload config
            selected_category_id = self.bulk_category_combo.currentData()
            manage_stock = False  # Tắt quản lý kho như single upload
            stock_status = 'instock'  # Mặc định luôn có hàng

            # Kiểm tra nếu không có category được chọn trong combo
            if not selected_category_id:
                # Thử lấy từ folder đầu tiên
                first_folder = self.selected_folders[0] if self.selected_folders else {}
                folder_category_id = first_folder.get('category_id')
                if folder_category_id and self.db_manager:
                    try:
                        category = self.db_manager.get_category_by_id(folder_category_id)
                        if category:
                            selected_category_id = category.get('wc_category_id', 1)
                            self.logger.info(f"Sử dụng category từ folder data: {selected_category_id}")
                    except Exception as e:
                        self.logger.warning(f"Could not get category from folder: {str(e)}")

                # Fallback to default category
                if not selected_category_id:
                    selected_category_id = 1

            # Threading configuration
            threading_enabled = getattr(self, 'enable_threading', None) and self.enable_threading.isChecked()
            
            bulk_config = {
                'site': selected_site,
                'status': self.bulk_status_combo.currentText(),
                'regular_price': self.bulk_regular_price.value(),
                'sale_price': self.bulk_sale_price.value() if self.bulk_sale_price.value() > 0 else None,
                'stock_quantity': self.bulk_stock.value(),
                'manage_stock': manage_stock,
                'stock_status': stock_status,
                'upload_delay': self.upload_delay.value(),
                'category_id': selected_category_id,
                # Threading settings
                'threading_enabled': threading_enabled,
                'max_threads': self.max_threads.value() if threading_enabled else 1,
                'thread_delay': self.thread_delay.value() if threading_enabled else 0
            }

            # Disable button and show progress
            self.bulk_upload_btn.setEnabled(False)
            self.progress_bar.setVisible(True)
            self.progress_bar.setMaximum(len(self.selected_folders))
            self.progress_bar.setValue(0)

            # Start bulk upload worker
            self.bulk_upload_worker = BulkUploadWorker(
                self.selected_folders, 
                bulk_config, 
                self.db_manager
            )

            self.bulk_upload_worker.progress_update.connect(self.on_bulk_progress)
            self.bulk_upload_worker.product_uploaded.connect(self.on_bulk_product_uploaded)
            self.bulk_upload_worker.upload_complete.connect(self.on_bulk_complete)
            self.bulk_upload_worker.error_occurred.connect(self.on_bulk_error)
            self.bulk_upload_worker.log_update.connect(self.on_bulk_log_update)

            self.bulk_upload_worker.start()

        except Exception as e:
            self.logger.error(f"Lỗi bắt đầu bulk upload: {str(e)}")
            QMessageBox.critical(self, "Lỗi", f"Không thể bắt đầu upload hàng loạt:\n{str(e)}")
            self.reset_upload_state()

    def validate_bulk_input(self):
        """Validate input cho bulk upload"""
        if not self.selected_folders:
            QMessageBox.warning(self, "Cảnh báo", "Không có thư mục nào để upload!")
            return False

        if self.bulk_site_combo.currentData() is None:
            QMessageBox.warning(self, "Cảnh báo", "Vui lòng chọn site!")
            return False

        if hasattr(self, 'bulk_category_combo') and self.bulk_category_combo.currentData() is None:
            QMessageBox.warning(self, "Cảnh báo", "Vui lòng chọn danh mục!")
            return False

        return True

    def on_bulk_progress(self, current, total, message):
        """Cập nhật tiến độ bulk upload"""
        self.progress_bar.setValue(current)
        self.status_label.setText(f"{message} ({current}/{total})")

    def on_bulk_product_uploaded(self, row, result, log_message):
        """Xử lý khi một sản phẩm được upload thành công"""
        if result and result.get('id'):
            # Cập nhật trạng thái
            status_item = QTableWidgetItem("✅ Thành công")
            status_item.setBackground(QColor(220, 255, 220))  # Light green
            self.bulk_table.setItem(row, 7, status_item)

            # Tạo link sản phẩm clickable
            product_url = result.get('product_url', '')
            if product_url:
                link_item = QTableWidgetItem(f"🔗 Xem sản phẩm (ID: {result.get('id')})")
                link_item.setForeground(QColor(0, 102, 204))  # Blue color
                link_item.setData(Qt.ItemDataRole.UserRole, product_url)
                self.bulk_table.setItem(row, 8, link_item)
            else:
                self.bulk_table.setItem(row, 8, QTableWidgetItem(log_message))
        else:
            status_item = QTableWidgetItem("❌ Thất bại")
            status_item.setBackground(QColor(255, 220, 220))  # Light red
            self.bulk_table.setItem(row, 7, status_item)
            self.bulk_table.setItem(row, 8, QTableWidgetItem(log_message or "❌ Upload thất bại"))

    def on_bulk_log_update(self, row, status, message):
        """Cập nhật log chi tiết cho từng row"""
        try:
            # Cập nhật cột log
            log_item = QTableWidgetItem(message)

            # Màu sắc dựa trên status
            if status == "uploading":
                log_item.setBackground(QColor(255, 248, 220))  # Light yellow
            elif status == "processing":
                log_item.setBackground(QColor(220, 240, 255))  # Light blue
            elif status == "success":
                log_item.setBackground(QColor(220, 255, 220))  # Light green
            elif status == "error":
                log_item.setBackground(QColor(255, 220, 220))  # Light red

            self.bulk_table.setItem(row, 8, log_item)

        except Exception as e:
            self.logger.error(f"Error updating log for row {row}: {str(e)}")

    def on_bulk_table_clicked(self, item):
        """Xử lý click vào bảng để mở link"""
        try:
            if item.column() == 8:  # Cột Chi tiết/Link
                url = item.data(Qt.ItemDataRole.UserRole)
                if url:
                    QDesktopServices.openUrl(QUrl(url))
        except Exception as e:
            self.logger.error(f"Error opening URL: {str(e)}")

    def on_bulk_complete(self, success_count, total_count):
        """Xử lý khi hoàn thành bulk upload với safe cleanup"""
        try:
            # Update UI safely
            self.progress_bar.setValue(total_count)
            self.status_label.setText(f"Hoàn thành! {success_count}/{total_count} sản phẩm đã đăng thành công")

            # Safe worker cleanup to prevent memory corruption crash
            if hasattr(self, 'bulk_upload_worker') and self.bulk_upload_worker:
                try:
                    # Disconnect signals before cleanup
                    self.bulk_upload_worker.progress_update.disconnect()
                    self.bulk_upload_worker.product_uploaded.disconnect()
                    self.bulk_upload_worker.upload_complete.disconnect()
                    self.bulk_upload_worker.error_occurred.disconnect()
                except:
                    pass  # Ignore disconnect errors

                # Wait for thread to finish properly
                if self.bulk_upload_worker.isRunning():
                    self.bulk_upload_worker.wait(5000)  # Wait max 5 seconds

                # Clean reference
                self.bulk_upload_worker = None

            # Force garbage collection to prevent memory leaks
            import gc
            gc.collect()

        except Exception as e:
            self.logger.error(f"Error in bulk completion handler: {str(e)}")

        finally:
            # Always reset upload state
            self.reset_upload_state()

        # Emit signal để parent refresh data
        try:
            if hasattr(self.parent(), 'refresh_data'):
                self.parent().refresh_data()
            elif hasattr(self.parent(), 'load_data'):
                self.parent().load_data()
        except Exception as e:
            self.logger.warning(f"Could not refresh parent data: {str(e)}")

        QMessageBox.information(
            self, "Hoàn thành",
            f"Đã đăng {success_count}/{total_count} sản phẩm thành công!\n\n"
            f"Trạng thái đã được cập nhật trong database."
        )

        # Emit signal để thông báo upload hoàn thành
        self.product_uploaded.emit({
            'success_count': success_count,
            'total_count': total_count,
            'type': 'bulk_complete'
        })

        if success_count > 0:
            self.accept()

    def on_bulk_error(self, error_message):
        """Xử lý lỗi bulk upload"""
        self.logger.error(f"Bulk upload error: {error_message}")
        QMessageBox.critical(self, "Lỗi upload hàng loạt", error_message)
        self.reset_upload_state()

    def save_bulk_config(self):
        """Lưu cấu hình bulk upload"""
        try:
            # Validate input
            if not self.validate_bulk_input():
                return

            # Prepare config data to save to database or apply to selected folders
            threading_enabled = getattr(self, 'enable_threading', None) and self.enable_threading.isChecked()
            
            config = {
                'site_id': self.bulk_site_combo.currentData(),
                'site_name': self.bulk_site_combo.currentText(),
                'category_id': self.bulk_category_combo.currentData(),
                'category_name': self.bulk_category_combo.currentText(),
                'status': self.bulk_status_combo.currentText(),
                'regular_price': self.bulk_regular_price.value(),
                'sale_price': self.bulk_sale_price.value(),
                'stock_quantity': self.bulk_stock.value(),
                'manage_stock': self.bulk_manage_stock.isChecked(),
                'stock_status': self.bulk_stock_status.currentText(),
                'upload_delay': self.upload_delay.value(),
                # Threading configuration
                'threading_enabled': threading_enabled,
                'max_threads': self.max_threads.value() if threading_enabled else 1,
                'thread_delay': self.thread_delay.value() if threading_enabled else 0
            }

            # Lưu cấu hình vào biến instance để giữ trạng thái
            self.saved_bulk_config = config

            # Apply config to selected folders in database
            if self.db_manager and self.selected_folders:
                updated_count = 0
                for folder in self.selected_folders:
                    folder_id = folder.get('id')
                    if folder_id:
                        update_data = {
                            'site_id': config['site_id'],
                            'category_id': config['category_id'],
                            'regular_price': config['regular_price'],
                            'sale_price': config['sale_price'],
                            'stock_quantity': config['stock_quantity'],
                            'upload_status': 'configured'
                        }
                        try:
                            self.db_manager.update_folder_scan(folder_id, update_data)
                            # Update folder data in memory
                            folder.update(update_data)
                            updated_count += 1
                        except Exception as e:
                            self.logger.error(f"Failed to update folder {folder_id}: {str(e)}")

                self.logger.info(f"Updated {updated_count}/{len(self.selected_folders)} folders with bulk config")

            # Reload categories to ensure fresh data
            try:
                self.load_categories()
                self.on_bulk_site_changed()  # Refresh category combo
            except Exception as e:
                self.logger.error(f"Error reloading categories: {str(e)}")

            # Update the preview table with new config
            try:
                if hasattr(self, 'bulk_table') and hasattr(self, 'populate_bulk_preview'):
                    self.populate_bulk_preview()
            except Exception as e:
                self.logger.error(f"Error updating bulk preview: {str(e)}")

            # Show success message
            QMessageBox.information(
                self, "Thành công", 
                f"Đã lưu cấu hình cho {len(self.selected_folders)} sản phẩm\n"
                f"Site: {config['site_name']}\n"
                f"Danh mục: {config['category_name']}"
            )

            self.status_label.setText("Cấu hình đã được lưu thành công!")

        except Exception as e:
            self.logger.error(f"Error saving bulk config: {str(e)}")
            QMessageBox.critical(self, "Lỗi", f"Không thể lưu cấu hình: {str(e)}")

    def load_saved_bulk_config(self):
        """Load cấu hình đã lưu vào form"""
        try:
            if not hasattr(self, 'saved_bulk_config') or not self.saved_bulk_config:
                # Thử load từ folder đầu tiên nếu có cấu hình
                if self.selected_folders:
                    first_folder = self.selected_folders[0]
                    if first_folder.get('site_id') and first_folder.get('category_id'):
                        self.load_config_from_folder(first_folder)
                return

            config = self.saved_bulk_config

            # Set site
            site_id = config.get('site_id')
            if site_id:
                for i in range(self.bulk_site_combo.count()):
                    if self.bulk_site_combo.itemData(i) == site_id:
                        self.bulk_site_combo.setCurrentIndex(i)
                        break

            # Refresh categories for selected site
            self.on_bulk_site_changed()

            # Set category
            category_id = config.get('category_id')
            if category_id:
                for i in range(self.bulk_category_combo.count()):
                    if self.bulk_category_combo.itemData(i) == category_id:
                        self.bulk_category_combo.setCurrentIndex(i)
                        break

            # Set other fields
            self.bulk_status_combo.setCurrentText(config.get('status', 'publish'))
            self.bulk_regular_price.setValue(config.get('regular_price', 25.0))
            self.bulk_sale_price.setValue(config.get('sale_price', 0.0))
            self.bulk_stock.setValue(config.get('stock_quantity', 100))
            self.bulk_manage_stock.setChecked(config.get('manage_stock', False))
            self.bulk_stock_status.setCurrentText(config.get('stock_status', 'instock'))
            self.upload_delay.setValue(config.get('upload_delay', 3))
            
            # Load threading configuration
            if hasattr(self, 'enable_threading'):
                threading_enabled = config.get('threading_enabled', False)
                self.enable_threading.setChecked(threading_enabled)
                self.max_threads.setValue(config.get('max_threads', 3))
                self.thread_delay.setValue(config.get('thread_delay', 1))
                # Trigger the toggle handler to update UI state
                self.on_threading_toggled(threading_enabled)

            self.logger.info("Đã load cấu hình đã lưu thành công")

        except Exception as e:
            self.logger.error(f"Error loading saved bulk config: {str(e)}")

    def load_config_from_folder(self, folder):
        """Load cấu hình từ folder data"""
        try:
            # Set site
            site_id = folder.get('site_id')
            if site_id:
                for i in range(self.bulk_site_combo.count()):
                    if self.bulk_site_combo.itemData(i) == site_id:
                        self.bulk_site_combo.setCurrentIndex(i)
                        break

            # Refresh categories
            self.on_bulk_site_changed()

            # Set category
            category_id = folder.get('category_id')
            if category_id and self.db_manager:
                try:
                    category = self.db_manager.get_category_by_id(category_id)
                    if category:
                        wc_category_id = category.get('wc_category_id')
                        if wc_category_id:
                            for i in range(self.bulk_category_combo.count()):
                                if self.bulk_category_combo.itemData(i) == wc_category_id:
                                    self.bulk_category_combo.setCurrentIndex(i)
                                    break
                except Exception as e:
                    self.logger.error(f"Error setting category from folder: {str(e)}")

            # Set prices if available
            if folder.get('regular_price'):
                self.bulk_regular_price.setValue(float(folder.get('regular_price', 25.0)))
            if folder.get('sale_price'):
                self.bulk_sale_price.setValue(float(folder.get('sale_price', 0.0)))
            if folder.get('stock_quantity'):
                self.bulk_stock.setValue(int(folder.get('stock_quantity', 100)))

            self.logger.info("Đã load cấu hình từ folder data")

        except Exception as e:
            self.logger.error(f"Error loading config from folder: {str(e)}")

    def get_upload_config(self):
        """Lấy cấu hình upload hiện tại"""
        try:
            return {
                'configured': True,
                'site_id': self.site_combo.currentData(),
                'category_id': self.category_combo.currentData() if hasattr(self, 'category_combo') else None,
                'status': self.status_combo.currentText() if hasattr(self, 'status_combo') else 'draft',
                'image_gallery': getattr(self, 'gallery_check', True),
                'auto_description': getattr(self, 'auto_desc_check', True),
                'price': getattr(self, 'price_input', 0),
                'delay': getattr(self, 'delay_spin', 3)
            }
        except Exception as e:
            self.logger.error(f"Error getting upload config: {str(e)}")
            return {'configured': False}

    def closeEvent(self, event):
        """Override close event to cleanup workers"""
        try:
            if hasattr(self, 'upload_worker') and self.upload_worker:
                self.upload_worker.stop()
                self.upload_worker.wait()
        except Exception as e:
            self.logger.error(f"Error during close: {str(e)}")
        finally:
            event.accept()