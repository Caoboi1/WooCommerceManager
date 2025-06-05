#!/usr/bin/env python3
"""
Test tạo sản phẩm không có ảnh - workaround cho lỗi upload ảnh
"""

import sys
import os
sys.path.append('.')

def test_create_product_without_images():
    """Test tạo sản phẩm không có ảnh"""
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
        
        # Tạo sản phẩm từ thông tin folder
        folder_info = {
            'name': 'Short Sleeve Button Up Tropical Hawaiian Shirt',
            'description': 'High-quality tropical Hawaiian shirt perfect for summer vacation, beach parties, and casual outings. Features vibrant colors and comfortable fit.',
            'price': '45.99',
            'category_id': None  # Không có category
        }
        
        product_data = {
            'name': folder_info['name'],
            'type': 'simple',
            'status': 'publish',
            'description': folder_info['description'],
            'short_description': folder_info['description'][:100] + '...' if len(folder_info['description']) > 100 else folder_info['description'],
            'regular_price': folder_info['price'],
            'manage_stock': False,
            'stock_status': 'instock'
            # Không có images để tránh lỗi upload
        }
        
        print("Đang tạo sản phẩm không có ảnh...")
        print(f"Tên: {product_data['name']}")
        print(f"Giá: ${product_data['regular_price']}")
        print(f"Mô tả: {product_data['description'][:50]}...")
        
        result = api.create_product(product_data)
        
        if result and result.get('id'):
            print(f"Tạo sản phẩm thành công!")
            print(f"ID: {result.get('id')}")
            print(f"Tên: {result.get('name')}")
            print(f"Status: {result.get('status')}")
            print(f"Stock: {result.get('stock_status')}")
            print(f"Giá: ${result.get('regular_price')}")
            print(f"Link: {result.get('permalink')}")
            print("\nLưu ý: Sản phẩm được tạo không có ảnh")
            print("Bạn có thể thêm ảnh sau thông qua WordPress Admin hoặc ứng dụng")
            return True
        else:
            print("Tạo sản phẩm thất bại")
            return False
            
    except Exception as e:
        print(f"Lỗi: {str(e)}")
        return False

def main():
    print("Test tạo sản phẩm không có ảnh")
    print("=" * 40)
    
    success = test_create_product_without_images()
    
    print("=" * 40)
    if success:
        print("Sản phẩm đã được tạo thành công!")
        print("Chức năng tạo sản phẩm hoạt động bình thường")
    else:
        print("Tạo sản phẩm thất bại")

if __name__ == "__main__":
    main()