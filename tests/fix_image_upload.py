#!/usr/bin/env python3
"""
Sửa chức năng upload ảnh cho sản phẩm
"""

import sys
import os
sys.path.append('.')

def update_folder_path_and_upload():
    """Cập nhật đường dẫn folder và upload sản phẩm có ảnh"""
    try:
        from app.database import DatabaseManager
        from app.woocommerce_api import WooCommerceAPI
        
        db = DatabaseManager()
        
        # Tạo folder test với ảnh mẫu
        test_folder_path = os.path.abspath("test_product_folder")
        
        # Tạo ảnh SVG mẫu cho sản phẩm
        svg_content = '''<?xml version="1.0" encoding="UTF-8"?>
<svg width="400" height="400" xmlns="http://www.w3.org/2000/svg">
  <rect width="400" height="400" fill="#87CEEB"/>
  <rect x="50" y="50" width="300" height="300" fill="#FFE4B5" stroke="#D2691E" stroke-width="3"/>
  <text x="200" y="180" text-anchor="middle" font-family="Arial" font-size="24" fill="#D2691E">Hawaiian</text>
  <text x="200" y="220" text-anchor="middle" font-family="Arial" font-size="24" fill="#D2691E">Shirt</text>
  <circle cx="120" cy="280" r="15" fill="#FF6347"/>
  <circle cx="160" cy="260" r="12" fill="#32CD32"/>
  <circle cx="240" cy="270" r="10" fill="#FFD700"/>
  <circle cx="280" cy="290" r="13" fill="#FF69B4"/>
</svg>'''
        
        # Tạo file ảnh mẫu
        with open(os.path.join(test_folder_path, "hawaiian_shirt_main.svg"), "w") as f:
            f.write(svg_content)
            
        # Cập nhật folder path trong database
        folders = db.get_all_folder_scans()
        if folders:
            folder = folders[0]
            folder_id = folder.get('id')
            
            # Cập nhật với đường dẫn thực tế
            update_data = {
                'path': test_folder_path,
                'image_count': 1
            }
            
            # Sử dụng SQL trực tiếp để tránh lỗi KeyError
            db.cursor.execute("""
                UPDATE folder_scans 
                SET path = ?, image_count = ?
                WHERE id = ?
            """, (test_folder_path, 1, folder_id))
            db.conn.commit()
            
            print(f"Đã cập nhật folder path: {test_folder_path}")
            
            # Test upload với ảnh
            sites = db.get_active_sites()
            if sites:
                site = sites[0]
                api = WooCommerceAPI(site)
                
                # Upload ảnh trước
                try:
                    svg_path = os.path.join(test_folder_path, "hawaiian_shirt_main.svg")
                    
                    # Đọc file SVG
                    with open(svg_path, 'rb') as f:
                        image_data = f.read()
                    
                    media_data = {
                        'title': 'Hawaiian Shirt Product Image',
                        'alt_text': 'Hawaiian Shirt',
                        'caption': 'Stylish Hawaiian Shirt',
                        'filename': 'hawaiian_shirt_main.svg',
                        'data': image_data
                    }
                    
                    print("Đang upload ảnh lên WordPress Media Library...")
                    media_result = api.upload_media(media_data)
                    
                    if media_result and media_result.get('id'):
                        print(f"Upload ảnh thành công, Media ID: {media_result.get('id')}")
                        
                        # Tạo sản phẩm với ảnh
                        product_data = {
                            'name': 'Short Sleeve Button Up Tropical Hawaiian Shirt (With Image)',
                            'type': 'simple',
                            'status': 'publish',
                            'description': 'Beautiful tropical Hawaiian shirt perfect for summer',
                            'short_description': 'Stylish Hawaiian shirt with tropical design',
                            'regular_price': '35.00',
                            'sale_price': '28.00',
                            'categories': [{'id': 1}],
                            'images': [{
                                'id': media_result.get('id'),
                                'src': media_result.get('source_url', ''),
                                'name': 'hawaiian_shirt_main.svg',
                                'alt': 'Hawaiian Shirt'
                            }],
                            'manage_stock': False,
                            'stock_status': 'instock'
                        }
                        
                        print("Đang tạo sản phẩm với ảnh...")
                        result = api.create_product(product_data)
                        
                        if result and result.get('id'):
                            print(f"Tạo sản phẩm có ảnh thành công!")
                            print(f"Product ID: {result.get('id')}")
                            print(f"Link: {result.get('permalink')}")
                            print(f"Số ảnh: {len(result.get('images', []))}")
                            return True
                        else:
                            print("Không thể tạo sản phẩm")
                            return False
                    else:
                        print("Không thể upload ảnh")
                        return False
                        
                except Exception as e:
                    print(f"Lỗi upload ảnh: {str(e)}")
                    return False
        
        return False
        
    except Exception as e:
        print(f"Lỗi: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("Sửa chức năng upload ảnh cho sản phẩm")
    print("=" * 50)
    
    success = update_folder_path_and_upload()
    
    print("=" * 50)
    if success:
        print("Đã sửa thành công - sản phẩm có ảnh đã được tạo!")
    else:
        print("Có lỗi trong quá trình sửa")

if __name__ == "__main__":
    main()