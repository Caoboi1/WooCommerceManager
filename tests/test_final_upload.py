#!/usr/bin/env python3
"""
Test cuối cùng - đăng sản phẩm với status publish và stock instock
"""

import sys
import os
sys.path.append('.')

def test_final_product_upload():
    """Test đăng sản phẩm với cấu hình cuối cùng"""
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
        
        # Tạo sản phẩm với cấu hình đầy đủ
        product_data = {
            'name': 'Hawaiian Shirt - Final Test (Publish + InStock)',
            'type': 'simple',
            'status': 'publish',  # Trạng thái publish
            'description': '''
<h3>Premium Hawaiian Shirt</h3>
<p>Beautiful tropical Hawaiian shirt perfect for:</p>
<ul>
<li>Summer vacation</li>
<li>Beach parties</li>
<li>Casual wear</li>
<li>Gift giving</li>
</ul>
<p>High quality fabric with authentic Hawaiian patterns.</p>
            ''',
            'short_description': 'Premium Hawaiian shirt with tropical patterns - perfect for summer',
            'regular_price': '39.99',
            'sale_price': '29.99',
            'sku': 'HAWAIIAN-FINAL-001',
            'manage_stock': False,  # Không quản lý stock quantity
            'stock_status': 'instock',  # Trạng thái instock
            'categories': [{'id': 1}],
            'weight': '0.5',
            'dimensions': {
                'length': '28',
                'width': '22', 
                'height': '3'
            },
            'attributes': [
                {
                    'name': 'Material',
                    'options': ['Cotton Blend'],
                    'visible': True
                },
                {
                    'name': 'Pattern',
                    'options': ['Tropical Hawaiian'],
                    'visible': True
                }
            ]
        }
        
        print("Đang tạo sản phẩm với status=publish và stock_status=instock...")
        result = api.create_product(product_data)
        
        if result and result.get('id'):
            print("Tạo sản phẩm thành công!")
            print(f"Product ID: {result.get('id')}")
            print(f"Tên: {result.get('name')}")
            print(f"Status: {result.get('status')}")
            print(f"Stock Status: {result.get('stock_status')}")
            print(f"Manage Stock: {result.get('manage_stock')}")
            print(f"Regular Price: ${result.get('regular_price')}")
            print(f"Sale Price: ${result.get('sale_price')}")
            print(f"Link: {result.get('permalink')}")
            
            # Kiểm tra các thuộc tính quan trọng
            if result.get('status') == 'publish':
                print("✅ Status: Published (hiển thị trên website)")
            else:
                print(f"⚠️ Status: {result.get('status')}")
                
            if result.get('stock_status') == 'instock':
                print("✅ Stock: In Stock (có thể mua)")
            else:
                print(f"⚠️ Stock: {result.get('stock_status')}")
            
            return True
        else:
            print("Không thể tạo sản phẩm")
            return False
            
    except Exception as e:
        print(f"Lỗi: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def check_existing_products():
    """Kiểm tra sản phẩm hiện có trên site"""
    try:
        from app.database import DatabaseManager
        from app.woocommerce_api import WooCommerceAPI
        
        db = DatabaseManager()
        sites = db.get_active_sites()
        
        if not sites:
            return False
            
        site = sites[0]
        api = WooCommerceAPI(site)
        
        print(f"Kiểm tra sản phẩm trên {site.name}...")
        
        # Lấy 5 sản phẩm mới nhất
        products = api.get_products(per_page=5)
        
        if products:
            print(f"Tìm thấy {len(products)} sản phẩm:")
            for product in products:
                status = product.get('status', 'unknown')
                stock = product.get('stock_status', 'unknown')
                price = product.get('regular_price', '0')
                print(f"- {product.get('name')} (Status: {status}, Stock: {stock}, Price: ${price})")
        else:
            print("Không có sản phẩm nào")
            
        return True
        
    except Exception as e:
        print(f"Lỗi kiểm tra: {str(e)}")
        return False

def main():
    print("Test cuối cùng - Upload sản phẩm với publish + instock")
    print("=" * 60)
    
    print("1. Kiểm tra sản phẩm hiện tại...")
    check_existing_products()
    
    print("\n" + "-" * 40)
    
    print("2. Tạo sản phẩm mới với cấu hình hoàn chỉnh...")
    success = test_final_product_upload()
    
    print("\n" + "=" * 60)
    
    if success:
        print("HOÀN THÀNH!")
        print("Sản phẩm đã được tạo với:")
        print("- Status: publish (hiển thị trên website)")
        print("- Stock: instock (có thể mua)")
        print("- Giá bán và sale price")
        print("- Mô tả đầy đủ")
    else:
        print("Có lỗi trong quá trình tạo sản phẩm")

if __name__ == "__main__":
    main()