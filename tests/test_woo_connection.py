#!/usr/bin/env python3
"""
Test kết nối thực tế với WooCommerce API
"""

import sys
import os
sys.path.append('.')

def test_woo_api_connection():
    """Test kết nối với WooCommerce API"""
    try:
        print("Đang khởi tạo database manager...")
        from app.database import DatabaseManager
        db = DatabaseManager()
        
        print("Đang lấy site để test...")
        sites = db.get_active_sites()
        
        if not sites:
            print("❌ Không có site hoạt động!")
            return False
            
        test_site = sites[0]
        print(f"🌐 Test kết nối với site: {test_site.name}")
        print(f"   URL: {test_site.url}")
        
        print("Đang khởi tạo WooCommerce API...")
        from app.woocommerce_api import WooCommerceAPI
        
        api = WooCommerceAPI(test_site)
        
        print("Đang test kết nối...")
        # Test connection trả về tuple (success, message)
        success, message = api.test_connection()
        
        if success:
            print(f"✅ Kết nối WooCommerce API thành công!")
            print(f"   {message}")
            
            # Test lấy danh sách sản phẩm
            print("Đang test lấy danh sách sản phẩm...")
            products = api.get_products(per_page=5)
            
            if products:
                print(f"✅ Lấy được {len(products)} sản phẩm từ store")
                for product in products[:2]:  # Hiển thị 2 sản phẩm đầu
                    print(f"   - {product.get('name', 'N/A')} (ID: {product.get('id')})")
            else:
                print("ℹ️  Store chưa có sản phẩm nào")
                
            return True
        else:
            print(f"❌ Lỗi kết nối: {message}")
            return False
            
    except Exception as e:
        print(f"❌ Lỗi test kết nối: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_create_sample_product():
    """Test tạo sản phẩm mẫu"""
    try:
        from app.database import DatabaseManager
        from app.woocommerce_api import WooCommerceAPI
        
        db = DatabaseManager()
        sites = db.get_active_sites()
        test_site = sites[0]
        
        api = WooCommerceAPI(test_site)
        
        # Sản phẩm mẫu đơn giản để test
        sample_product = {
            'name': 'Test Product - Sample Hawaiian Shirt',
            'type': 'simple',
            'status': 'draft',  # Tạo draft để không ảnh hưởng store
            'description': 'This is a test product created by WooCommerce Product Manager',
            'short_description': 'Test Hawaiian shirt',
            'regular_price': '25.00',
            'categories': [{'id': 1}],  # Category mặc định
            'images': []
        }
        
        print("Đang test tạo sản phẩm mẫu...")
        result = api.create_product(sample_product)
        
        if result and result.get('id'):
            product_id = result.get('id')
            print(f"✅ Tạo sản phẩm test thành công! ID: {product_id}")
            print(f"   Tên: {result.get('name')}")
            print(f"   Status: {result.get('status')}")
            
            # Xóa sản phẩm test ngay sau khi tạo
            print("Đang xóa sản phẩm test...")
            delete_result = api.delete_product(product_id)
            if delete_result:
                print("✅ Đã xóa sản phẩm test")
            
            return True
        else:
            print("❌ Không thể tạo sản phẩm test")
            return False
            
    except Exception as e:
        print(f"❌ Lỗi test tạo sản phẩm: {str(e)}")
        return False

def main():
    """Main test function"""
    print("🧪 Test kết nối WooCommerce API")
    print("=" * 50)
    
    # Test 1: Kết nối cơ bản
    print("1. Test kết nối cơ bản...")
    connection_ok = test_woo_api_connection()
    
    if not connection_ok:
        print("\n❌ Kết nối thất bại - Không thể tiếp tục test")
        return False
    
    print("\n" + "-" * 30)
    
    # Test 2: Tạo/xóa sản phẩm
    print("2. Test tạo/xóa sản phẩm...")
    create_ok = test_create_sample_product()
    
    print("\n" + "=" * 50)
    
    if connection_ok and create_ok:
        print("🎉 TẤT CẢ TEST PASS - Sẵn sàng đăng sản phẩm thực tế!")
    else:
        print("⚠️  Một số test thất bại - Cần kiểm tra lại cấu hình")

if __name__ == "__main__":
    main()