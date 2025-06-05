#!/usr/bin/env python3
"""
Script để khắc phục lỗi PIL trong product_upload_dialog.py
"""

import os
import re

def fix_pil_errors():
    """Khắc phục lỗi PIL trong product_upload_dialog.py"""
    file_path = "app/product_upload_dialog.py"
    
    if not os.path.exists(file_path):
        print(f"File {file_path} không tồn tại")
        return False
    
    # Đọc nội dung file
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Thay thế các phần sử dụng PIL
    fixes = [
        # Fix 1: Thay thế Image.open trong resize_image_if_needed (lần 1)
        (
            r'            with Image\.open\(image_path\) as img:\s*\n\s*original_size = img\.size',
            '''            if PIL_AVAILABLE:
                with Image.open(image_path) as img:
                    original_size = img.size
            else:
                # Sử dụng PyQt6 thay thế
                pixmap = QPixmap(image_path)
                if pixmap.isNull():
                    return image_path
                original_size = (pixmap.width(), pixmap.height())'''
        ),
        
        # Fix 2: Thay thế phần resize với PIL
        (
            r'                # Resize ảnh\s*\n\s*resized_img = img\.resize\(new_size, Image\.Resampling\.LANCZOS\)',
            '''                # Resize ảnh
                if PIL_AVAILABLE:
                    resized_img = img.resize(new_size, Image.Resampling.LANCZOS)
                else:
                    # Resize bằng PyQt6
                    scaled_pixmap = pixmap.scaled(new_size[0], new_size[1], Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)'''
        ),
        
        # Fix 3: Thay thế phần save image
        (
            r'                # Lưu ảnh đã resize với chất lượng tối ưu\s*\n\s*if ext\.lower\(\) in \[\'\.jpg\', \'\.jpeg\'\]:\s*\n\s*resized_img\.save\(resized_path, \'JPEG\', quality=85, optimize=True\)\s*\n\s*elif ext\.lower\(\) == \'\.png\':\s*\n\s*resized_img\.save\(resized_path, \'PNG\', optimize=True\)\s*\n\s*elif ext\.lower\(\) == \'\.webp\':\s*\n\s*resized_img\.save\(resized_path, \'WEBP\', quality=85, optimize=True\)\s*\n\s*else:\s*\n\s*resized_img\.save\(resized_path, optimize=True\)',
            '''                # Lưu ảnh đã resize với chất lượng tối ưu
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
                    scaled_pixmap.save(resized_path, quality=85)'''
        ),
        
        # Fix 4: Khắc phục lỗi config upload - thêm validation
        (
            r'            # Validate inputs với chi tiết hơn\s*\n\s*if self\.config is None:\s*\n\s*raise Exception\("Upload config is None - BulkUploadWorker không nhận được config"\)',
            '''            # Validate inputs với chi tiết hơn
            if self.config is None:
                self.logger.error("Upload config is None - Config chưa được khởi tạo")
                self.error_occurred.emit("Lỗi: Config upload chưa được khởi tạo")
                return'''
        ),
        
        # Fix 5: Khắc phục lỗi emit signal với None
        (
            r'                self\.product_uploaded\.emit\(i, None, error_msg\)',
            '''                # Tạo dict rỗng thay vì None để tránh lỗi signal
                empty_result = {}
                self.product_uploaded.emit(i, empty_result, error_msg)'''
        )
    ]
    
    # Áp dụng các fixes
    for pattern, replacement in fixes:
        content = re.sub(pattern, replacement, content, flags=re.MULTILINE | re.DOTALL)
    
    # Ghi lại file
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("✅ Đã khắc phục lỗi PIL và config upload")
    return True

if __name__ == "__main__":
    fix_pil_errors()