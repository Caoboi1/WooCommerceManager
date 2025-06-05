
#!/usr/bin/env python3
"""
Test script để kiểm tra upload ảnh với cải tiến mới
"""

import sys
import os
sys.path.append('.')

def test_image_upload_with_improvements():
    """Test upload ảnh với cải tiến mới"""
    try:
        from app.database import DatabaseManager
        from app.woocommerce_api import WooCommerceAPI
        
        db = DatabaseManager()
        sites = db.get_active_sites()
        
        if not sites:
            print("❌ Không có site hoạt động")
            return False
            
        site = sites[0]
        api = WooCommerceAPI(site)
        
        print(f"🌐 Testing với site: {site.name}")
        
        # Test với ảnh có sẵn
        test_image_path = "./test_product_folder/Short Sleeve Button Up Tropical Hawaiian Shirt.jpg"
        
        if not os.path.exists(test_image_path):
            print(f"❌ File ảnh test không tồn tại: {test_image_path}")
            return False
        
        print(f"📷 Testing upload ảnh: {os.path.basename(test_image_path)}")
        
        # Đọc file ảnh
        with open(test_image_path, 'rb') as f:
            image_data = f.read()
        
        # Chuẩn bị media data với cải tiến mới
        media_data = {
            'file_path': test_image_path,
            'filename': os.path.basename(test_image_path),
            'title': 'Hawaiian Shirt Test Image',
            'alt_text': 'Hawaiian shirt product image',
            'caption': 'Test upload for Hawaiian shirt',
            'data': image_data,
            'mime_type': 'image/jpeg'
        }
        
        print("⬆️  Đang upload ảnh lên WordPress Media Library...")
        uploaded_media = api.upload_media(media_data)
        
        if uploaded_media and uploaded_media.get('id'):
            print(f"✅ Upload ảnh thành công!")
            print(f"   Media ID: {uploaded_media.get('id')}")
            print(f"   URL: {uploaded_media.get('source_url', 'N/A')}")
            
            # Tạo sản phẩm với ảnh vừa upload
            product_data = {
                'name': 'Hawaiian Shirt - Test Upload Fix',
                'type': 'simple',
                'status': 'publish',
                'description': 'Test product with uploaded image',
                'short_description': 'Hawaiian shirt with real uploaded image',
                'regular_price': '35.99',
                'sale_price': '29.99',
                'manage_stock': False,
                'stock_status': 'instock',
                'images': [{
                    'id': uploaded_media.get('id'),
                    'src': uploaded_media.get('source_url'),
                    'name': uploaded_media.get('title', ''),
                    'alt': uploaded_media.get('alt_text', '')
                }]
            }
            
            print("🛍️  Đang tạo sản phẩm với ảnh...")
            created_product = api.create_product(product_data)
            
            if created_product and created_product.get('id'):
                print(f"🎉 Tạo sản phẩm thành công!")
                print(f"   Product ID: {created_product.get('id')}")
                print(f"   Product Name: {created_product.get('name')}")
                print(f"   Product URL: {created_product.get('permalink')}")
                print(f"   Images: {len(created_product.get('images', []))} ảnh")
                
                # Hiển thị thông tin ảnh
                for i, img in enumerate(created_product.get('images', [])):
                    print(f"     Ảnh {i+1}: {img.get('src', 'N/A')}")
                
                return True
            else:
                print("❌ Không thể tạo sản phẩm")
                return False
        else:
            print("❌ Upload ảnh thất bại")
            return False
            
    except Exception as e:
        print(f"❌ Lỗi: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("🧪 Test Upload Ảnh với Cải tiến Mới")
    print("=" * 50)
    
    success = test_image_upload_with_improvements()
    
    print("=" * 50)
    if success:
        print("🎊 Test THÀNH CÔNG - Upload ảnh và tạo sản phẩm hoạt động tốt!")
    else:
        print("⚠️  Test THẤT BẠI - Cần kiểm tra lại cấu hình")
        print("\n💡 Gợi ý:")
        print("   1. Kiểm tra Consumer Key/Secret có quyền upload")
        print("   2. Kiểm tra WordPress authentication (nếu có)")
        print("   3. Kiểm tra file ảnh có tồn tại không")
        print("   4. Kiểm tra kết nối mạng")

if __name__ == "__main__":
    main()
