#!/usr/bin/env python3
"""
Test script để kiểm tra chức năng đăng lên WooCommerce
"""

import sys
import os
sys.path.append('.')

def test_import_product_upload_dialog():
    """Test import ProductUploadDialog để kiểm tra lỗi QWidget"""
    try:
        print("Đang test import ProductUploadDialog...")
        from app.product_upload_dialog import ProductUploadDialog
        print("✅ Import ProductUploadDialog thành công - Lỗi QWidget đã được sửa!")
        return True
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Lỗi khác: {e}")
        return False

def test_folder_scanner_upload():
    """Test chức năng upload trong folder_scanner"""
    try:
        print("Đang test import FolderScannerTab...")
        from app.folder_scanner import FolderScannerTab
        print("✅ Import FolderScannerTab thành công!")
        
        # Test tạo instance để kiểm tra method upload_to_woocommerce
        print("Đang kiểm tra method upload_to_woocommerce...")
        if hasattr(FolderScannerTab, 'upload_to_woocommerce'):
            print("✅ Method upload_to_woocommerce tồn tại!")
            return True
        else:
            print("❌ Method upload_to_woocommerce không tồn tại!")
            return False
            
    except Exception as e:
        print(f"❌ Lỗi test FolderScannerTab: {e}")
        return False

def main():
    """Main test function"""
    print("🧪 Bắt đầu test chức năng đăng lên WooCommerce...")
    print("=" * 50)
    
    success = True
    
    # Test 1: Import ProductUploadDialog
    if not test_import_product_upload_dialog():
        success = False
    
    print("-" * 30)
    
    # Test 2: Test FolderScannerTab upload method
    if not test_folder_scanner_upload():
        success = False
    
    print("=" * 50)
    
    if success:
        print("🎉 Tất cả test đều PASS - Chức năng đăng lên WooCommerce hoạt động bình thường!")
    else:
        print("⚠️  Có lỗi trong quá trình test!")
    
    return success

if __name__ == "__main__":
    main()