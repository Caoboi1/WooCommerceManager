
#!/usr/bin/env python3
"""
Test upload ảnh sản phẩm với WordPress authentication
"""

import sys
import os
import base64
sys.path.append('.')

def test_wordpress_media_upload():
    """Test upload ảnh lên WordPress Media Library"""
    try:
        from app.database import DatabaseManager
        from app.woocommerce_api import WooCommerceAPI
        
        db = DatabaseManager()
        sites = db.get_active_sites()
        
        if not sites:
            print("❌ Không có site hoạt động")
            return False
            
        site = sites[0]
        print(f"🌐 Site: {site.name}")
        
        # Kiểm tra WordPress auth
        wp_username = getattr(site, 'wp_username', '')
        wp_app_password = getattr(site, 'wp_app_password', '')
        
        if not wp_username or not wp_app_password:
            print("❌ Thiếu WordPress authentication!")
            print("💡 Chạy script update_wp_password.py để cập nhật")
            return False
        
        print(f"✅ WordPress Username: {wp_username}")
        print(f"✅ App Password: {'*' * len(wp_app_password)}")
        
        api = WooCommerceAPI(site)
        
        # Test folder ảnh
        folder_path = "./test_product_folder"
        if not os.path.exists(folder_path):
            print("❌ Folder test không tồn tại")
            return False
        
        # Tìm file ảnh
        image_files = []
        for file in os.listdir(folder_path):
            if file.lower().endswith(('.jpg', '.jpeg', '.png', '.gif')):
                image_files.append(file)
        
        if not image_files:
            print("❌ Không có ảnh trong folder test")
            return False
        
        print(f"📸 Tìm thấy {len(image_files)} ảnh")
        
        # Upload ảnh đầu tiên
        image_file = image_files[0]
        image_path = os.path.join(folder_path, image_file)
        
        print(f"🔄 Đang upload: {image_file}")
        
        # Đọc file và chuyển thành base64
        with open(image_path, 'rb') as f:
            image_data = f.read()
            image_base64 = base64.b64encode(image_data).decode('utf-8')
        
        # Chuẩn bị data cho WordPress Media API
        media_data = {
            'title': image_file.split('.')[0],
            'source_url': f'data:image/jpeg;base64,{image_base64}',
            'mime_type': 'image/jpeg'
        }
        
        # Upload lên WordPress
        uploaded_media = api.upload_media(media_data)
        
        if uploaded_media:
            print(f"✅ Upload thành công!")
            print(f"   Media ID: {uploaded_media.get('id')}")
            print(f"   URL: {uploaded_media.get('source_url')}")
            print(f"   Title: {uploaded_media.get('title', {}).get('rendered', '')}")
            
            # Test tạo sản phẩm với ảnh
            product_data = {
                'name': 'Test Product with Image',
                'type': 'simple',
                'status': 'draft',
                'description': 'Test product created with image upload',
                'regular_price': '25.00',
                'images': [{
                    'id': uploaded_media.get('id'),
                    'src': uploaded_media.get('source_url'),
                    'name': image_file,
                    'alt': 'Test product image'
                }]
            }
            
            print("\n🔄 Đang tạo sản phẩm với ảnh...")
            product = api.create_product(product_data)
            
            if product:
                print(f"✅ Tạo sản phẩm thành công!")
                print(f"   Product ID: {product.get('id')}")
                print(f"   Name: {product.get('name')}")
                print(f"   Images: {len(product.get('images', []))}")
                
                # Xóa sản phẩm test
                print("\n🗑️  Đang xóa sản phẩm test...")
                api.delete_product(product.get('id'), force=True)
                print("✅ Đã xóa sản phẩm test")
                
            return True
        else:
            print("❌ Upload ảnh thất bại")
            return False
            
    except Exception as e:
        print(f"❌ Lỗi test: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🧪 Test Upload Ảnh với WordPress Authentication")
    print("=" * 60)
    
    success = test_wordpress_media_upload()
    
    print("\n" + "=" * 60)
    if success:
        print("🎉 Upload ảnh hoạt động bình thường!")
    else:
        print("⚠️  Cần kiểm tra lại cấu hình WordPress authentication")
