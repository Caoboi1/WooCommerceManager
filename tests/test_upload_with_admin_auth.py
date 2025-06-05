
#!/usr/bin/env python3
"""
Test upload ảnh sử dụng WordPress admin authentication
"""

import sys
import os
sys.path.append('.')

def test_upload_with_admin_auth():
    """Test upload ảnh với admin authentication"""
    try:
        from app.database import DatabaseManager
        from app.woocommerce_api import WooCommerceAPI
        
        db = DatabaseManager()
        sites = db.get_active_sites()
        
        if not sites:
            print("❌ Không có site hoạt động")
            return False
            
        # Tìm site Vogue Pony
        site = None
        for s in sites:
            if 'voguepony' in s.url.lower():
                site = s
                break
        
        if not site:
            print("❌ Không tìm thấy site Vogue Pony")
            return False
            
        print(f"🌐 Site: {site.name}")
        print(f"📍 URL: {site.url}")
        
        # Kiểm tra WordPress auth
        wp_username = getattr(site, 'wp_username', '')
        wp_app_password = getattr(site, 'wp_app_password', '')
        
        if not wp_username or not wp_app_password:
            print("❌ Thiếu WordPress authentication!")
            print("💡 Chạy script update_site_with_wp_auth.py để cập nhật")
            return False
        
        print(f"✅ WordPress Username: {wp_username}")
        print(f"✅ App Password: {'*' * len(wp_app_password)}")
        
        api = WooCommerceAPI(site)
        
        # Test với ảnh Hawaiian shirt
        test_image_path = "./test_product_folder/Short Sleeve Button Up Tropical Hawaiian Shirt.jpg"
        
        if not os.path.exists(test_image_path):
            print(f"❌ File ảnh test không tồn tại: {test_image_path}")
            return False
        
        print(f"📷 Testing upload ảnh: {os.path.basename(test_image_path)}")
        
        # Đọc file ảnh
        with open(test_image_path, 'rb') as f:
            image_data = f.read()
        
        # Chuẩn bị media data
        media_data = {
            'title': 'Hawaiian Shirt Admin Test',
            'alt_text': 'Tropical Hawaiian Shirt uploaded by admin',
            'caption': 'Test upload using WordPress admin authentication',
            'filename': os.path.basename(test_image_path),
            'data': image_data,
            'mime_type': 'image/jpeg'
        }
        
        print("⬆️  Đang upload ảnh lên WordPress Media Library...")
        
        # Upload ảnh
        uploaded_media = api.upload_media(media_data)
        
        if uploaded_media and uploaded_media.get('id'):
            print(f"✅ Upload ảnh thành công!")
            print(f"   Media ID: {uploaded_media.get('id')}")
            print(f"   URL: {uploaded_media.get('source_url')}")
            print(f"   Title: {uploaded_media.get('title', {}).get('rendered', '')}")
            
            # Tạo sản phẩm với ảnh
            product_data = {
                'name': 'Hawaiian Shirt - Admin Upload Test',
                'type': 'simple',
                'status': 'draft',
                'description': 'Hawaiian shirt uploaded using WordPress admin authentication',
                'short_description': 'Test product with admin uploaded image',
                'regular_price': '29.99',
                'manage_stock': False,
                'stock_status': 'instock',
                'images': [{
                    'id': uploaded_media.get('id'),
                    'src': uploaded_media.get('source_url'),
                    'name': os.path.basename(test_image_path),
                    'alt': 'Hawaiian Shirt Admin Test'
                }]
            }
            
            print("🛍️  Đang tạo sản phẩm với ảnh...")
            created_product = api.create_product(product_data)
            
            if created_product and created_product.get('id'):
                print(f"✅ Tạo sản phẩm thành công!")
                print(f"   Product ID: {created_product.get('id')}")
                print(f"   Product Name: {created_product.get('name')}")
                print(f"   Status: {created_product.get('status')}")
                print(f"   Images: {len(created_product.get('images', []))}")
                
                if created_product.get('images'):
                    for idx, img in enumerate(created_product.get('images')):
                        print(f"   Image {idx+1}: {img.get('src')}")
                
                return True
            else:
                print("❌ Tạo sản phẩm thất bại")
                return False
        else:
            print("❌ Upload ảnh thất bại")
            return False
            
    except Exception as e:
        print(f"❌ Lỗi: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("🧪 Test Upload Ảnh với WordPress Admin Authentication")
    print("=" * 60)
    
    success = test_upload_with_admin_auth()
    
    print("=" * 60)
    if success:
        print("🎊 Test THÀNH CÔNG!")
        print("   - Upload ảnh lên WordPress Media Library ✅")
        print("   - Tạo sản phẩm với ảnh ✅")
        print("   - Sử dụng WordPress admin authentication ✅")
    else:
        print("⚠️  Test THẤT BẠI")
        print("\n💡 Gợi ý:")
        print("   1. Chạy update_site_with_wp_auth.py để cập nhật auth")
        print("   2. Kiểm tra WordPress username/password có đúng không")
        print("   3. Kiểm tra file ảnh test có tồn tại không")

if __name__ == "__main__":
    main()
