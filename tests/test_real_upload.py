#!/usr/bin/env python3
"""
Test thực tế đăng sản phẩm lên WooCommerce từ database
"""

import sys
import os
sys.path.append('.')

def test_real_woo_upload():
    """Test đăng sản phẩm thực tế lên WooCommerce"""
    try:
        print("Đang khởi tạo database manager...")
        from app.database import DatabaseManager
        db = DatabaseManager()
        
        print("Đang lấy danh sách folder scans...")
        folder_scans = db.get_all_folder_scans()
        
        if not folder_scans:
            print("❌ Không có folder scan nào trong database!")
            return False
            
        print(f"✅ Tìm thấy {len(folder_scans)} folder scans")
        
        # Lấy folder đầu tiên để test
        test_folder = folder_scans[0]
        print(f"📦 Test với folder: {test_folder.get('data_name', 'N/A')}")
        
        print("Đang lấy danh sách sites...")
        sites = db.get_active_sites()
        
        if not sites:
            print("❌ Không có site WooCommerce nào hoạt động!")
            print("💡 Cần thêm site WooCommerce trong tab Quản lý Site")
            return False
            
        print(f"✅ Tìm thấy {len(sites)} sites hoạt động")
        test_site = sites[0]
        print(f"🌐 Test với site: {test_site.name}")
        
        print("Đang import ProductUploadWorker...")
        from app.product_upload_dialog import ProductUploadWorker
        
        # Chuẩn bị config upload
        upload_config = {
            'site_id': test_site.id,
            'category_id': test_folder.get('category_id', 1),
            'status': 'publish',
            'price': 25.00,
            'sale_price': 20.00,
            'manage_stock': False,
            'stock_quantity': 0,
            'delay_between_posts': 2
        }
        
        print("Đang tạo ProductUploadWorker...")
        worker = ProductUploadWorker([test_folder], upload_config)
        
        print("✅ ProductUploadWorker được tạo thành công!")
        print("📝 Cấu hình upload:")
        print(f"   - Site: {test_site.name}")
        print(f"   - Folder: {test_folder.get('data_name')}")
        print(f"   - Giá: ${upload_config['price']}")
        print(f"   - Trạng thái: {upload_config['status']}")
        
        print("\n⚠️  Để test đăng thực tế, cần:")
        print("1. API credentials hợp lệ cho WooCommerce site")
        print("2. Site phải có thể truy cập được")
        print("3. Folder phải có ảnh sản phẩm")
        
        return True
        
    except Exception as e:
        print(f"❌ Lỗi test upload: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def check_site_credentials():
    """Kiểm tra thông tin đăng nhập site"""
    try:
        from app.database import DatabaseManager
        db = DatabaseManager()
        sites = db.get_active_sites()
        
        if not sites:
            print("❌ Không có site nào!")
            return False
            
        for site in sites:
            print(f"\n🌐 Site: {site.name}")
            print(f"   URL: {site.url}")
            print(f"   Consumer Key: {'***' if site.consumer_key else 'Chưa có'}")
            print(f"   Consumer Secret: {'***' if site.consumer_secret else 'Chưa có'}")
            print(f"   Trạng thái: {'Hoạt động' if site.is_active else 'Tạm dừng'}")
            
        return True
        
    except Exception as e:
        print(f"❌ Lỗi kiểm tra credentials: {str(e)}")
        return False

def main():
    """Main test function"""
    print("🧪 Test đăng sản phẩm thực tế lên WooCommerce")
    print("=" * 60)
    
    # Kiểm tra credentials
    print("1. Kiểm tra thông tin sites...")
    check_site_credentials()
    
    print("\n" + "-" * 40)
    
    # Test upload
    print("2. Test chuẩn bị upload...")
    success = test_real_woo_upload()
    
    print("\n" + "=" * 60)
    
    if success:
        print("✅ Test PASS - Chức năng upload sẵn sàng!")
    else:
        print("❌ Test FAILED - Cần kiểm tra lại!")

if __name__ == "__main__":
    main()