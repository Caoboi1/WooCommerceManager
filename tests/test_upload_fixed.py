#!/usr/bin/env python3
"""
Test upload sau khi sửa lỗi validation
"""

import sys
import os
sys.path.append('.')

def test_upload_after_fixes():
    """Test upload với dữ liệu đã được validate"""
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
        
        # Test với dữ liệu đã được validate tốt
        product_data = {
            'name': 'Hawaiian Shirt - Test Upload Fixed',
            'type': 'simple',
            'status': 'publish',
            'description': 'High quality Hawaiian shirt with tropical patterns',
            'short_description': 'Hawaiian shirt for summer',
            'regular_price': '29.99',
            'manage_stock': False,
            'stock_status': 'instock'
        }
        
        print("Đang test upload với dữ liệu đã validate...")
        result = api.create_product(product_data)
        
        if result and result.get('id'):
            print(f"Upload thành công!")
            print(f"ID: {result.get('id')}")
            print(f"Tên: {result.get('name')}")
            print(f"Status: {result.get('status')}")
            print(f"Stock: {result.get('stock_status')}")
            print(f"Link: {result.get('permalink')}")
            return True
        else:
            print("Upload thất bại")
            return False
            
    except Exception as e:
        print(f"Lỗi: {str(e)}")
        return False

def main():
    print("Test upload sau khi sửa lỗi")
    print("=" * 30)
    
    success = test_upload_after_fixes()
    
    print("=" * 30)
    if success:
        print("Chức năng upload đã hoạt động bình thường")
    else:
        print("Vẫn còn lỗi cần khắc phục")

if __name__ == "__main__":
    main()