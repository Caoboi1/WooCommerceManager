#!/usr/bin/env python3
"""
Test upload sản phẩm có kèm ảnh
"""

import sys
import os
import glob
sys.path.append('.')

def find_images_in_folder(folder_path):
    """Tìm ảnh trong folder"""
    if not os.path.exists(folder_path):
        return []
    
    image_extensions = ['*.jpg', '*.jpeg', '*.png', '*.gif', '*.webp']
    images = []
    
    for ext in image_extensions:
        images.extend(glob.glob(os.path.join(folder_path, ext)))
        images.extend(glob.glob(os.path.join(folder_path, ext.upper())))
    
    return images[:5]  # Chỉ lấy 5 ảnh đầu

def upload_images_to_wc(api, images, product_name):
    """Upload ảnh lên WooCommerce"""
    uploaded_images = []
    
    for i, image_path in enumerate(images):
        try:
            print(f"  Đang upload ảnh {i+1}/{len(images)}: {os.path.basename(image_path)}")
            
            # Chuẩn bị dữ liệu media
            with open(image_path, 'rb') as f:
                image_data = f.read()
            
            filename = os.path.basename(image_path)
            media_data = {
                'title': f"{product_name} - Image {i+1}",
                'alt_text': f"{product_name}",
                'caption': f"{product_name}",
                'filename': filename,
                'data': image_data
            }
            
            # Upload lên WordPress Media Library
            media_result = api.upload_media(media_data)
            
            if media_result and media_result.get('id'):
                uploaded_images.append({
                    'id': media_result.get('id'),
                    'src': media_result.get('source_url', ''),
                    'name': filename,
                    'alt': f"{product_name}"
                })
                print(f"    ✅ Upload thành công ID: {media_result.get('id')}")
            else:
                print(f"    ❌ Upload thất bại")
                
        except Exception as e:
            print(f"    ❌ Lỗi upload {filename}: {str(e)}")
    
    return uploaded_images

def test_upload_product_with_images():
    """Test upload sản phẩm có ảnh"""
    try:
        from app.database import DatabaseManager
        from app.woocommerce_api import WooCommerceAPI
        
        db = DatabaseManager()
        folders = db.get_all_folder_scans()
        sites = db.get_active_sites()
        
        if not folders or not sites:
            print("Cần có folder và site")
            return False
            
        folder = folders[0]
        site = sites[0]
        
        folder_path = folder.get('path')
        product_name = folder.get('data_name', 'Test Product')
        
        print(f"Sản phẩm: {product_name}")
        print(f"Folder: {folder_path}")
        print(f"Site: {site.name}")
        
        # Tìm ảnh trong folder
        images = find_images_in_folder(folder_path)
        print(f"Tìm thấy {len(images)} ảnh")
        
        if not images:
            print("❌ Không có ảnh để upload")
            return False
            
        api = WooCommerceAPI(site)
        
        # Upload ảnh
        print("Đang upload ảnh...")
        uploaded_images = upload_images_to_wc(api, images, product_name)
        
        if not uploaded_images:
            print("❌ Không upload được ảnh nào")
            return False
        
        # Tạo sản phẩm với ảnh
        product_data = {
            'name': f"{product_name} (With Images)",
            'type': 'simple',
            'status': 'publish',
            'description': folder.get('description', f'Hawaiian shirt {product_name}'),
            'short_description': f'Stylish {product_name}',
            'regular_price': '30.00',
            'sale_price': '25.00',
            'categories': [{'id': 1}],
            'images': uploaded_images,
            'manage_stock': False,
            'stock_status': 'instock'
        }
        
        print("Đang tạo sản phẩm với ảnh...")
        result = api.create_product(product_data)
        
        if result and result.get('id'):
            print(f"✅ Tạo sản phẩm thành công!")
            print(f"ID: {result.get('id')}")
            print(f"Link: {result.get('permalink')}")
            print(f"Ảnh: {len(result.get('images', []))} ảnh")
            return True
        else:
            print("❌ Không thể tạo sản phẩm")
            return False
            
    except Exception as e:
        print(f"❌ Lỗi: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("Test upload sản phẩm có ảnh")
    print("=" * 40)
    
    success = test_upload_product_with_images()
    
    print("=" * 40)
    if success:
        print("Sản phẩm có ảnh đã được tạo thành công!")
    else:
        print("Có lỗi khi upload sản phẩm có ảnh")

if __name__ == "__main__":
    main()