#!/usr/bin/env python3
"""
Test đăng sản phẩm thực tế lên WooCommerce
"""

import sys
import os
sys.path.append('.')

def test_real_product_upload():
    """Test đăng sản phẩm thực tế"""
    try:
        print("Khởi tạo database và API...")
        from app.database import DatabaseManager
        from app.woocommerce_api import WooCommerceAPI
        
        db = DatabaseManager()
        
        # Lấy folder và site
        folders = db.get_all_folder_scans()
        sites = db.get_active_sites()
        
        if not folders or not sites:
            print("Cần có folder và site để test")
            return False
            
        test_folder = folders[0]
        test_site = sites[0]
        
        print(f"Đăng sản phẩm: {test_folder.get('data_name')}")
        print(f"Lên site: {test_site.name}")
        
        api = WooCommerceAPI(test_site)
        
        # Tạo sản phẩm đơn giản
        product_data = {
            'name': test_folder.get('data_name', 'Test Product'),
            'type': 'simple',
            'status': 'publish',
            'description': test_folder.get('description', 'Test product description'),
            'short_description': 'Test Hawaiian shirt from WooCommerce Product Manager',
            'regular_price': '25.00',
            'sale_price': '20.00',
            'categories': [{'id': 1}],  # Default category
            'manage_stock': False,
            'stock_status': 'instock'
        }
        
        print("Đang tạo sản phẩm trên WooCommerce...")
        result = api.create_product(product_data)
        
        if result and result.get('id'):
            product_id = result.get('id')
            product_name = result.get('name')
            product_status = result.get('status')
            permalink = result.get('permalink')
            
            print(f"Tạo sản phẩm thành công!")
            print(f"ID: {product_id}")
            print(f"Tên: {product_name}")
            print(f"Trạng thái: {product_status}")
            print(f"Link: {permalink}")
            
            # Cập nhật database
            update_data = {
                'status': 'completed',
                'wc_product_id': product_id
            }
            db.update_folder_scan(test_folder.get('id'), update_data)
            print("Đã cập nhật database")
            
            return True
        else:
            print("Không thể tạo sản phẩm")
            print(f"Response: {result}")
            return False
            
    except Exception as e:
        print(f"Lỗi: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def check_products_on_site():
    """Kiểm tra sản phẩm trên site"""
    try:
        from app.database import DatabaseManager
        from app.woocommerce_api import WooCommerceAPI
        
        db = DatabaseManager()
        sites = db.get_active_sites()
        
        if not sites:
            print("Không có site nào")
            return False
            
        test_site = sites[0]
        api = WooCommerceAPI(test_site)
        
        print(f"Kiểm tra sản phẩm trên {test_site.name}...")
        
        # Lấy 10 sản phẩm mới nhất
        products = api.get_products(per_page=10, orderby='date', order='desc')
        
        if products:
            print(f"Tìm thấy {len(products)} sản phẩm:")
            for product in products:
                print(f"- {product.get('name')} (ID: {product.get('id')}, Status: {product.get('status')})")
        else:
            print("Không có sản phẩm nào trên site")
            
        return True
        
    except Exception as e:
        print(f"Lỗi kiểm tra: {str(e)}")
        return False

def main():
    print("Test đăng sản phẩm thực tế lên WooCommerce")
    print("=" * 50)
    
    print("1. Kiểm tra sản phẩm hiện tại trên site...")
    check_products_on_site()
    
    print("\n" + "-" * 30)
    
    print("2. Đăng sản phẩm mới...")
    success = test_real_product_upload()
    
    if success:
        print("\n" + "-" * 30)
        print("3. Kiểm tra lại sản phẩm trên site...")
        check_products_on_site()
    
    print("\n" + "=" * 50)
    
    if success:
        print("Đăng sản phẩm thành công! Kiểm tra trên site:")
        print("https://voguepony.com/wp-admin/edit.php?post_type=product")
    else:
        print("Có lỗi khi đăng sản phẩm")

if __name__ == "__main__":
    main()