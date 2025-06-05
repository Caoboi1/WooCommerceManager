#!/usr/bin/env python3
"""
Test upload sản phẩm với WordPress authentication
"""

import sys
import os
sys.path.append('.')

def test_upload_with_wordpress_auth():
    """Test upload sản phẩm sử dụng WordPress authentication"""
    try:
        from app.database import DatabaseManager
        from app.woocommerce_api import WooCommerceAPI
        
        db = DatabaseManager()
        sites = db.get_active_sites()
        
        if not sites:
            print("Không có site hoạt động")
            return False
            
        site = sites[0]
        print(f"Site: {site.name}")
        print(f"URL: {site.url}")
        print(f"Consumer Key: {site.consumer_key[:10]}...")
        
        # Kiểm tra WordPress auth
        wp_username = getattr(site, 'wp_username', '')
        wp_app_password = getattr(site, 'wp_app_password', '')
        
        print(f"WordPress Username: {wp_username}")
        print(f"WordPress App Password: {'*' * len(wp_app_password) if wp_app_password else 'Không có'}")
        
        if not wp_username or not wp_app_password:
            print("Thiếu thông tin WordPress authentication")
            print("Cần có wp_username và wp_app_password để upload ảnh")
            return False
        
        api = WooCommerceAPI(site)
        
        # Test folder có ảnh
        folder_path = "./test_product_folder"
        
        if not os.path.exists(folder_path):
            print("Folder test không tồn tại")
            return False
            
        # Tìm file ảnh
        image_files = []
        for file in os.listdir(folder_path):
            if file.lower().endswith(('.jpg', '.jpeg', '.png', '.gif')):
                image_files.append(file)
                
        print(f"Tìm thấy {len(image_files)} ảnh: {image_files}")
        
        if not image_files:
            print("Không có ảnh để test")
            return False
        
        # Upload ảnh đầu tiên
        image_file = image_files[0]
        image_path = os.path.join(folder_path, image_file)
        
        print(f"Đang upload ảnh: {image_file}")
        
        # Upload qua WordPress Media API sử dụng upload_media
        with open(image_path, 'rb') as f:
            import base64
            file_content = f.read()
            file_base64 = base64.b64encode(file_content).decode('utf-8')
            
        media_data = {
            'title': image_file.split('.')[0],
            'source_url': f'data:image/jpeg;base64,{file_base64}',
            'mime_type': 'image/jpeg'
        }
        
        uploaded_media = api.upload_media(media_data)
        
        if uploaded_media:
            print(f"Upload ảnh thành công!")
            print(f"Media ID: {uploaded_media.get('id')}")
            print(f"URL: {uploaded_media.get('source_url')}")
            
            # Tạo sản phẩm với ảnh
            product_data = {
                'name': 'Hawaiian Shirt with WordPress Auth',
                'type': 'simple',
                'status': 'publish',
                'description': 'Tropical Hawaiian shirt uploaded with WordPress authentication',
                'short_description': 'Hawaiian shirt with real image',
                'regular_price': '39.99',
                'manage_stock': False,
                'stock_status': 'instock',
                'images': [{
                    'id': uploaded_media.get('id'),
                    'src': uploaded_media.get('source_url'),
                    'name': image_file,
                    'alt': image_file.split('.')[0]
                }]
            }
            
            print("Đang tạo sản phẩm với ảnh...")
            result = api.create_product(product_data)
            
            if result and result.get('id'):
                print(f"Tạo sản phẩm thành công!")
                print(f"ID: {result.get('id')}")
                print(f"Tên: {result.get('name')}")
                print(f"Status: {result.get('status')}")
                print(f"Stock: {result.get('stock_status')}")
                print(f"Số ảnh: {len(result.get('images', []))}")
                print(f"Link: {result.get('permalink')}")
                
                # Hiển thị thông tin ảnh
                for idx, img in enumerate(result.get('images', [])):
                    print(f"  Ảnh {idx+1}: {img.get('src')}")
                    
                return True
            else:
                print("Tạo sản phẩm thất bại")
                return False
        else:
            print("Upload ảnh thất bại")
            return False
            
    except Exception as e:
        print(f"Lỗi: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("Test upload sản phẩm với WordPress authentication")
    print("=" * 50)
    
    success = test_upload_with_wordpress_auth()
    
    print("=" * 50)
    if success:
        print("Upload sản phẩm có ảnh thành công!")
    else:
        print("Upload thất bại")

if __name__ == "__main__":
    main()