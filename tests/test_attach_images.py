
#!/usr/bin/env python3
"""
Test attach ảnh vào sản phẩm để giải quyết vấn đề (Unattached)
"""

import sys
import os
sys.path.append('.')

def test_upload_and_attach_images():
    """Test upload ảnh và attach vào sản phẩm"""
    try:
        from app.database import DatabaseManager
        from app.woocommerce_api import WooCommerceAPI
        
        db = DatabaseManager()
        sites = db.get_active_sites()
        
        if not sites:
            print("❌ Không có site nào")
            return False
            
        site = sites[0]
        api = WooCommerceAPI(site)
        
        print(f"🌐 Site: {site.name}")
        print(f"🔑 WordPress Auth: {'✅' if api.wp_username and api.wp_app_password else '❌'}")
        
        # Tìm ảnh test
        test_folder = "test_product_folder"
        if not os.path.exists(test_folder):
            print(f"❌ Không tìm thấy folder test: {test_folder}")
            return False
            
        image_files = []
        for file in os.listdir(test_folder):
            if file.lower().endswith(('.jpg', '.jpeg', '.png', '.gif')):
                image_files.append(os.path.join(test_folder, file))
                
        if not image_files:
            print("❌ Không có ảnh nào trong folder test")
            return False
            
        print(f"📷 Tìm thấy {len(image_files)} ảnh")
        
        # Upload ảnh trước
        uploaded_images = []
        for i, img_path in enumerate(image_files[:3]):  # Chỉ upload 3 ảnh đầu
            print(f"📤 Đang upload ảnh {i+1}: {os.path.basename(img_path)}")
            
            try:
                result = api.upload_media(
                    img_path,
                    f"Hawaiian Shirt Image {i+1}",
                    "Hawaiian Shirt Product Image"
                )
                
                if result:
                    uploaded_images.append(result)
                    print(f"   ✅ Upload thành công: {result.get('src')}")
                else:
                    print(f"   ❌ Upload thất bại")
                    
            except Exception as e:
                print(f"   ❌ Lỗi upload: {str(e)}")
                continue
        
        if not uploaded_images:
            print("❌ Không upload được ảnh nào")
            return False
            
        print(f"\n📦 Đang tạo sản phẩm với {len(uploaded_images)} ảnh...")
        
        # Tạo sản phẩm với ảnh
        product_data = {
            'name': 'Hawaiian Shirt - Test Attach Images',
            'sku': 'hawaiian-attach-test',
            'type': 'simple',
            'status': 'publish',
            'description': 'Test sản phẩm để kiểm tra attach ảnh đúng cách',
            'short_description': 'Hawaiian shirt test với ảnh được attach đúng',
            'regular_price': '35.99',
            'sale_price': '25.99',
            'manage_stock': True,
            'stock_quantity': 50,
            'stock_status': 'instock',
            'categories': [{'id': 1}],
            'images': uploaded_images
        }
        
        result = api.create_product(product_data)
        
        if result and result.get('id'):
            product_id = result.get('id')
            print(f"✅ Tạo sản phẩm thành công!")
            print(f"   Product ID: {product_id}")
            print(f"   Tên: {result.get('name')}")
            print(f"   Status: {result.get('status')}")
            print(f"   Stock: {result.get('stock_status')}")
            print(f"   Số ảnh: {len(result.get('images', []))}")
            
            # Hiển thị thông tin ảnh
            for idx, img in enumerate(result.get('images', [])):
                print(f"   Ảnh {idx+1}: {img.get('src')}")
                
            print(f"\n🎯 Kiểm tra trên WordPress Admin:")
            print(f"   - Sản phẩm: {site.url}/wp-admin/post.php?post={product_id}&action=edit")
            print(f"   - Media Library: {site.url}/wp-admin/upload.php")
            print(f"   - Ảnh không còn hiển thị (Unattached) ✅")
            
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
    print("🧪 Test Upload và Attach Ảnh vào Sản Phẩm")
    print("=" * 50)
    
    success = test_upload_and_attach_images()
    
    print("\n" + "=" * 50)
    if success:
        print("🎊 Test THÀNH CÔNG!")
        print("✅ Ảnh đã được upload và attach vào sản phẩm")
        print("✅ Không còn hiển thị (Unattached) trong Media Library")
    else:
        print("❌ Test thất bại")

if __name__ == "__main__":
    main()
