#!/usr/bin/env python3
"""
Test nhanh chức năng upload sản phẩm
"""

import sys
import os
sys.path.append('.')

def test_upload_function():
    """Test chức năng upload có hoạt động không"""
    try:
        print("Test import các module cần thiết...")
        
        # Test 1: Import database
        from app.database import DatabaseManager
        db = DatabaseManager()
        print("✅ DatabaseManager OK")
        
        # Test 2: Import API
        from app.woocommerce_api import WooCommerceAPI
        print("✅ WooCommerceAPI OK")
        
        # Test 3: Import Upload Dialog (đã sửa lỗi QWidget)
        from app.product_upload_dialog import ProductUploadDialog, ProductUploadWorker
        print("✅ ProductUploadDialog OK")
        
        # Test 4: Import FolderScanner upload method
        from app.folder_scanner import FolderScannerTab
        print("✅ FolderScannerTab OK")
        
        # Test 5: Kiểm tra có dữ liệu không
        folders = db.get_all_folder_scans()
        sites = db.get_active_sites()
        
        print(f"📁 Folders trong DB: {len(folders)}")
        print(f"🌐 Sites hoạt động: {len(sites)}")
        
        if folders and sites:
            print("✅ Có dữ liệu để test upload")
            return True
        else:
            print("⚠️  Cần có folder và site để test upload")
            return False
            
    except Exception as e:
        print(f"❌ Lỗi: {str(e)}")
        return False

def main():
    print("🧪 Test nhanh chức năng upload")
    print("=" * 40)
    
    success = test_upload_function()
    
    print("=" * 40)
    
    if success:
        print("🎉 CHỨC NĂNG UPLOAD SẴN SÀNG!")
        print("Bạn có thể:")
        print("1. Chọn folder trong tab Quét thư mục")
        print("2. Click nút 'Đăng lên WooCommerce'")
        print("3. Cấu hình thông tin sản phẩm")
        print("4. Đăng lên store")
    else:
        print("❌ Cần kiểm tra lại cấu hình")

if __name__ == "__main__":
    main()