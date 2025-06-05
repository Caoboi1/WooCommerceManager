
#!/usr/bin/env python3
"""
Test script đăng sản phẩm hoàn chỉnh lên WooCommerce với upload ảnh
"""

import sys
import os
sys.path.append('.')

def test_complete_product_upload():
    """Test đăng sản phẩm hoàn chỉnh có ảnh"""
    try:
        from app.database import DatabaseManager
        from app.woocommerce_api import WooCommerceAPI
        
        print("🚀 Test đăng sản phẩm hoàn chỉnh lên WooCommerce")
        print("=" * 60)
        
        # Khởi tạo database
        db = DatabaseManager()
        sites = db.get_active_sites()
        
        if not sites:
            print("❌ Không có site hoạt động")
            return False
            
        site = sites[0]
        api = WooCommerceAPI(site)
        
        print(f"🌐 Site: {site.name}")
        print(f"📍 URL: {site.url}")
        
        # Test folder có ảnh
        test_folder = "./test_product_folder"
        
        if not os.path.exists(test_folder):
            print(f"❌ Folder test không tồn tại: {test_folder}")
            return False
        
        # Tìm ảnh trong folder
        image_files = []
        for file in os.listdir(test_folder):
            if file.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.bmp')):
                image_files.append(os.path.join(test_folder, file))
        
        print(f"📷 Tìm thấy {len(image_files)} ảnh: {[os.path.basename(f) for f in image_files]}")
        
        if not image_files:
            print("❌ Không có ảnh để test")
            return False
        
        # Upload ảnh lên WordPress Media Library
        print("\n⬆️  Đang upload ảnh lên WordPress...")
        uploaded_images = []
        
        for i, image_path in enumerate(image_files):
            print(f"   Đang upload ảnh {i+1}/{len(image_files)}: {os.path.basename(image_path)}")
            
            try:
                with open(image_path, 'rb') as f:
                    image_data = f.read()
                
                filename = os.path.basename(image_path)
                media_data = {
                    'title': f'Hawaiian Shirt Test - Image {i+1}',
                    'alt_text': 'Hawaiian Shirt Product Image',
                    'caption': 'Test product image upload',
                    'filename': filename,
                    'data': image_data,
                    'file_path': image_path
                }
                
                result = api.upload_media(media_data)
                
                if result and result.get('id'):
                    uploaded_images.append({
                        'id': result.get('id'),
                        'src': result.get('source_url', ''),
                        'name': filename,
                        'alt': 'Hawaiian Shirt Product Image'
                    })
                    print(f"      ✅ Upload thành công - Media ID: {result.get('id')}")
                else:
                    print(f"      ❌ Upload thất bại cho {filename}")
                    
            except Exception as e:
                print(f"      ❌ Lỗi upload {filename}: {str(e)}")
                continue
        
        print(f"\n📊 Kết quả upload ảnh: {len(uploaded_images)}/{len(image_files)} thành công")
        
        if not uploaded_images:
            print("❌ Không upload được ảnh nào")
            return False
        
        # Tạo sản phẩm với ảnh
        print("\n🛍️  Đang tạo sản phẩm với ảnh...")
        
        product_data = {
            'name': 'Hawaiian Tropical Shirt - Complete Test',
            'sku': 'hawaiian-shirt-complete-test',
            'type': 'simple',
            'status': 'publish',
            'description': '''
<h3>Premium Hawaiian Tropical Shirt</h3>
<p>Sản phẩm test đăng hoàn chỉnh với ảnh thực tế từ WooCommerce Product Manager.</p>
<ul>
<li>Chất liệu cao cấp</li>
<li>Họa tiết Hawaii chính gốc</li>
<li>Thoáng mát và thoải mái</li>
<li>Phù hợp cho mùa hè và du lịch</li>
</ul>
            ''',
            'short_description': 'Hawaiian shirt với họa tiết nhiệt đới chính gốc. Test upload hoàn chỉnh từ WooCommerce Product Manager.',
            'regular_price': '45.99',
            'sale_price': '35.99',
            'manage_stock': True,
            'stock_quantity': 50,
            'stock_status': 'instock',
            'categories': [{'id': 1}],
            'images': uploaded_images,
            'weight': '0.3',
            'dimensions': {
                'length': '30',
                'width': '25',
                'height': '2'
            }
        }
        
        result = api.create_product(product_data)
        
        if result and result.get('id'):
            print("🎉 Đăng sản phẩm thành công!")
            print(f"   📦 Product ID: {result.get('id')}")
            print(f"   📝 Tên: {result.get('name')}")
            print(f"   🔗 Link: {result.get('permalink')}")
            print(f"   💰 Giá: ${result.get('regular_price')} (Sale: ${result.get('sale_price')})")
            print(f"   📊 Trạng thái: {result.get('status')}")
            print(f"   🖼️  Số ảnh: {len(result.get('images', []))}")
            
            # Hiển thị thông tin ảnh
            if result.get('images'):
                print("\n📷 Ảnh sản phẩm:")
                for i, img in enumerate(result.get('images', [])):
                    print(f"   {i+1}. {img.get('src', 'N/A')}")
            
            return True
        else:
            print("❌ Không thể tạo sản phẩm")
            return False
            
    except Exception as e:
        print(f"❌ Lỗi test: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_folder_scan_upload():
    """Test upload từ folder scan data"""
    try:
        from app.database import DatabaseManager
        from app.woocommerce_api import WooCommerceAPI
        
        print("\n" + "=" * 60)
        print("🗂️  Test upload từ folder scan data")
        print("=" * 60)
        
        db = DatabaseManager()
        folder_scans = db.get_all_folder_scans()
        
        if not folder_scans:
            print("❌ Không có folder scan data")
            return False
        
        # Lấy folder scan đầu tiên
        folder_data = folder_scans[0]
        print(f"📁 Folder: {folder_data.get('data_name', 'Unknown')}")
        print(f"📍 Path: {folder_data.get('path', 'No path')}")
        print(f"🖼️  Số ảnh: {folder_data.get('image_count', 0)}")
        
        sites = db.get_active_sites()
        if not sites:
            print("❌ Không có site hoạt động")
            return False
            
        site = sites[0]
        api = WooCommerceAPI(site)
        
        # Lấy ảnh từ folder
        folder_path = folder_data.get('path', '')
        if not os.path.exists(folder_path):
            print(f"❌ Folder không tồn tại: {folder_path}")
            return False
        
        image_files = []
        for file in os.listdir(folder_path):
            if file.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.bmp')):
                image_files.append(os.path.join(folder_path, file))
        
        print(f"📷 Tìm thấy {len(image_files)} ảnh trong folder scan")
        
        if image_files:
            # Upload một vài ảnh đầu (tối đa 3)
            upload_images = image_files[:3]
            uploaded_images = []
            
            print(f"\n⬆️  Upload {len(upload_images)} ảnh đầu...")
            
            for i, image_path in enumerate(upload_images):
                try:
                    with open(image_path, 'rb') as f:
                        image_data = f.read()
                    
                    filename = os.path.basename(image_path)
                    media_data = {
                        'title': f'{folder_data.get("data_name", "Product")} - Image {i+1}',
                        'alt_text': folder_data.get('data_name', 'Product'),
                        'filename': filename,
                        'data': image_data
                    }
                    
                    result = api.upload_media(media_data)
                    
                    if result and result.get('id'):
                        uploaded_images.append({
                            'id': result.get('id'),
                            'src': result.get('source_url', ''),
                            'name': filename,
                            'alt': folder_data.get('data_name', 'Product')
                        })
                        print(f"   ✅ {filename} - Media ID: {result.get('id')}")
                    
                except Exception as e:
                    print(f"   ❌ Lỗi upload {filename}: {str(e)}")
                    continue
        
        # Tạo sản phẩm từ folder scan data
        product_name = folder_data.get('data_name', 'Product from Folder Scan')
        sku = product_name.replace(' ', '-').replace('_', '-').lower()
        sku = ''.join(c for c in sku if c.isalnum() or c == '-')
        
        product_data = {
            'name': f"{product_name} - From Folder Scan",
            'sku': f"{sku}-folder-scan",
            'type': 'simple',
            'status': 'publish',
            'description': folder_data.get('description', f'Product created from folder scan: {product_name}'),
            'short_description': f'Auto-generated product from folder scan data.',
            'regular_price': '29.99',
            'sale_price': '24.99',
            'manage_stock': True,
            'stock_quantity': 100,
            'stock_status': 'instock',
            'categories': [{'id': 1}]
        }
        
        if uploaded_images:
            product_data['images'] = uploaded_images
        
        print(f"\n🛍️  Tạo sản phẩm từ folder scan: {product_name}")
        result = api.create_product(product_data)
        
        if result and result.get('id'):
            print("🎉 Tạo sản phẩm từ folder scan thành công!")
            print(f"   📦 Product ID: {result.get('id')}")
            print(f"   📝 Tên: {result.get('name')}")
            print(f"   🖼️  Số ảnh: {len(result.get('images', []))}")
            return True
        else:
            print("❌ Không thể tạo sản phẩm từ folder scan")
            return False
            
    except Exception as e:
        print(f"❌ Lỗi test folder scan: {str(e)}")
        return False

def main():
    """Main test function"""
    print("🧪 WooCommerce Product Upload Complete Test")
    print("Kiểm tra tính năng đăng sản phẩm hoàn chỉnh với upload ảnh")
    
    # Test 1: Upload sản phẩm hoàn chỉnh
    success1 = test_complete_product_upload()
    
    # Test 2: Upload từ folder scan data
    success2 = test_folder_scan_upload()
    
    print("\n" + "=" * 60)
    print("📊 KẾT QUẢ TEST")
    print("=" * 60)
    
    if success1:
        print("✅ Test upload sản phẩm hoàn chỉnh: THÀNH CÔNG")
    else:
        print("❌ Test upload sản phẩm hoàn chỉnh: THẤT BẠI")
    
    if success2:
        print("✅ Test upload từ folder scan: THÀNH CÔNG")
    else:
        print("❌ Test upload từ folder scan: THẤT BẠI")
    
    if success1 or success2:
        print("\n🎊 Chức năng đăng sản phẩm hoạt động tốt!")
        print("Có thể sử dụng trong ứng dụng chính.")
    else:
        print("\n⚠️  Cần kiểm tra lại cấu hình và kết nối.")

if __name__ == "__main__":
    main()
