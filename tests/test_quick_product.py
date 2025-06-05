#!/usr/bin/env python3
"""
Test nhanh tạo sản phẩm publish + instock
"""

import sys
import os
sys.path.append('.')

def quick_product_test():
    """Test nhanh tạo sản phẩm"""
    try:
        from app.database import DatabaseManager
        from app.woocommerce_api import WooCommerceAPI
        
        db = DatabaseManager()
        sites = db.get_active_sites()
        
        if not sites:
            print("Không có site")
            return False
            
        site = sites[0]
        api = WooCommerceAPI(site)
        
        # Sản phẩm đơn giản
        product_data = {
            'name': 'Hawaiian Shirt - Quick Test',
            'type': 'simple',
            'status': 'publish',
            'description': 'Beautiful Hawaiian shirt for summer',
            'regular_price': '35.00',
            'manage_stock': False,
            'stock_status': 'instock'
        }
        
        print("Tạo sản phẩm...")
        result = api.create_product(product_data)
        
        if result and result.get('id'):
            print(f"Thành công! ID: {result.get('id')}")
            print(f"Status: {result.get('status')}")
            print(f"Stock: {result.get('stock_status')}")
            print(f"Link: {result.get('permalink')}")
            return True
        else:
            print("Thất bại")
            return False
            
    except Exception as e:
        print(f"Lỗi: {str(e)}")
        return False

if __name__ == "__main__":
    print("Test nhanh sản phẩm")
    print("=" * 30)
    success = quick_product_test()
    print("=" * 30)
    if success:
        print("HOÀN THÀNH - Sản phẩm đã publish và instock")
    else:
        print("Có lỗi")