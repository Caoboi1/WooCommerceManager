#!/usr/bin/env python3
"""
Test upload sản phẩm với ảnh thực tế từ folder test
"""

import sys
import os
sys.path.append('.')

def test_upload_product_with_real_image():
    """Test upload sản phẩm có ảnh thực tế"""
    try:
        from app.database import DatabaseManager
        from app.woocommerce_api import WooCommerceAPI
        
        db = DatabaseManager()
        sites = db.get_active_sites()
        
        if not sites:
            print("Không có site hoạt động")
            return False
            
        site = sites[0]
        api = WooCommerceAPI(site)
        
        # Test với folder có ảnh thực tế
        folder_path = "./test_product_folder"
        
        if not os.path.exists(folder_path):
            print("Folder test không tồn tại")
            return False
            
        # Tìm file ảnh trong folder
        image_files = []
        for file in os.listdir(folder_path):
            if file.lower().endswith(('.jpg', '.jpeg', '.png', '.gif')):
                image_files.append(file)
                
        print(f"Tìm thấy {len(image_files)} ảnh: {image_files}")
        
        # Upload ảnh lên WordPress Media Library
        uploaded_images = []
        for image_file in image_files:
            image_path = os.path.join(folder_path, image_file)
            
            print(f"Đang upload ảnh: {image_file}")
            
            # Upload ảnh lên WordPress
            with open(image_path, 'rb') as f:
                files = {'file': (image_file, f, 'image/jpeg')}
                headers = {
                    'Authorization': f'Basic {api._get_auth_header()}',
                }
                
                try:
                    import requests
                    response = requests.post(
                        f"{api.base_url}/wp-json/wp/v2/media",
                        files=files,
                        headers=headers,
                        timeout=30
                    )
                    
                    if response.status_code == 201:
                        media_data = response.json()
                        uploaded_images.append({
                            'id': media_data.get('id'),
                            'src': media_data.get('source_url'),
                            'name': image_file,
                            'alt': image_file.split('.')[0]
                        })
                        print(f"Upload ảnh thành công: {media_data.get('source_url')}")
                    else:
                        print(f"Upload ảnh thất bại: {response.status_code} - {response.text}")
                        
                except Exception as e:
                    print(f"Lỗi upload ảnh: {str(e)}")
        
        # Tạo sản phẩm với ảnh
        product_data = {
            'name': 'Hawaiian Shirt with Real Images',
            'type': 'simple',
            'status': 'publish',
            'description': 'Tropical Hawaiian shirt with authentic product images',
            'short_description': 'Hawaiian shirt for summer with real photos',
            'regular_price': '35.99',
            'manage_stock': False,
            'stock_status': 'instock',
            'images': uploaded_images
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
            
    except Exception as e:
        print(f"Lỗi: {str(e)}")
        return False

def main():
    print("Test upload sản phẩm với ảnh thực tế")
    print("=" * 40)
    
    success = test_upload_product_with_real_image()
    
    print("=" * 40)
    if success:
        print("Upload sản phẩm có ảnh thành công!")
    else:
        print("Upload thất bại")

if __name__ == "__main__":
    main()