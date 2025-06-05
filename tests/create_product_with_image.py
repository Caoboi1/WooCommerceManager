#!/usr/bin/env python3
"""
Tạo sản phẩm có ảnh thực tế
"""

import sys
import os
sys.path.append('.')

def create_sample_image():
    """Tạo ảnh SVG mẫu"""
    svg_content = '''<?xml version="1.0" encoding="UTF-8"?>
<svg width="600" height="600" xmlns="http://www.w3.org/2000/svg">
  <!-- Background -->
  <rect width="600" height="600" fill="#87CEEB"/>
  
  <!-- Shirt outline -->
  <path d="M150 200 L150 180 L200 160 L400 160 L450 180 L450 200 L480 220 L480 500 L450 520 L150 520 L120 500 L120 220 Z" 
        fill="#FFE4B5" stroke="#D2691E" stroke-width="3"/>
  
  <!-- Collar -->
  <path d="M200 160 L250 140 L350 140 L400 160 L350 180 L250 180 Z" 
        fill="#FFFFFF" stroke="#D2691E" stroke-width="2"/>
  
  <!-- Hawaiian patterns -->
  <circle cx="220" cy="250" r="25" fill="#FF6347" opacity="0.7"/>
  <circle cx="380" cy="280" r="20" fill="#32CD32" opacity="0.7"/>
  <circle cx="300" cy="320" r="30" fill="#FFD700" opacity="0.7"/>
  <circle cx="250" cy="380" r="18" fill="#FF69B4" opacity="0.7"/>
  <circle cx="350" cy="420" r="22" fill="#00CED1" opacity="0.7"/>
  
  <!-- Palm leaves -->
  <path d="M180 300 Q200 280 220 300 Q200 320 180 300" fill="#228B22" opacity="0.6"/>
  <path d="M420 350 Q400 330 380 350 Q400 370 420 350" fill="#228B22" opacity="0.6"/>
  
  <!-- Text -->
  <text x="300" y="580" text-anchor="middle" font-family="Arial" font-size="24" font-weight="bold" fill="#D2691E">
    Hawaiian Shirt
  </text>
</svg>'''
    
    # Tạo thư mục nếu chưa có
    os.makedirs("test_product_folder", exist_ok=True)
    
    # Lưu file SVG
    image_path = "test_product_folder/hawaiian_shirt.svg"
    with open(image_path, "w") as f:
        f.write(svg_content)
    
    return os.path.abspath(image_path)

def upload_product_with_real_image():
    """Upload sản phẩm có ảnh thực tế"""
    try:
        from app.database import DatabaseManager
        from app.woocommerce_api import WooCommerceAPI
        
        # Tạo ảnh mẫu
        image_path = create_sample_image()
        print(f"Đã tạo ảnh mẫu: {image_path}")
        
        db = DatabaseManager()
        sites = db.get_active_sites()
        
        if not sites:
            print("Không có site hoạt động")
            return False
            
        site = sites[0]
        api = WooCommerceAPI(site)
        
        # Upload ảnh lên WordPress Media Library
        print("Đang upload ảnh lên WordPress...")
        
        with open(image_path, 'rb') as f:
            image_data = f.read()
        
        media_data = {
            'title': 'Hawaiian Shirt Product Image',
            'alt_text': 'Tropical Hawaiian Shirt',
            'caption': 'Beautiful Hawaiian shirt with tropical patterns',
            'filename': 'hawaiian_shirt.svg',
            'data': image_data
        }
        
        media_result = api.upload_media(media_data)
        
        if not media_result or not media_result.get('id'):
            print("Không thể upload ảnh lên WordPress")
            return False
            
        print(f"Upload ảnh thành công - Media ID: {media_result.get('id')}")
        
        # Tạo sản phẩm với ảnh
        product_data = {
            'name': 'Hawaiian Tropical Shirt - Premium Quality',
            'type': 'simple',
            'status': 'publish',
            'description': '''
<h3>Premium Hawaiian Tropical Shirt</h3>
<p>Experience the vibrant spirit of the tropics with our premium Hawaiian shirt featuring:</p>
<ul>
<li>Authentic tropical patterns</li>
<li>Comfortable short sleeve design</li>
<li>High-quality fabric</li>
<li>Perfect for summer and vacation</li>
<li>Available in multiple sizes</li>
</ul>
<p>Made with care for those who appreciate quality and style.</p>
            ''',
            'short_description': 'Premium Hawaiian shirt with authentic tropical patterns. Perfect for summer and vacation wear.',
            'regular_price': '45.00',
            'sale_price': '35.00',
            'categories': [{'id': 1}],
            'images': [{
                'id': media_result.get('id'),
                'src': media_result.get('source_url', ''),
                'name': 'hawaiian_shirt.svg',
                'alt': 'Hawaiian Tropical Shirt'
            }],
            'manage_stock': True,
            'stock_quantity': 50,
            'stock_status': 'instock',
            'weight': '0.3',
            'dimensions': {
                'length': '30',
                'width': '20',
                'height': '2'
            }
        }
        
        print("Đang tạo sản phẩm có ảnh...")
        result = api.create_product(product_data)
        
        if result and result.get('id'):
            print("Tạo sản phẩm có ảnh thành công!")
            print(f"Product ID: {result.get('id')}")
            print(f"Tên: {result.get('name')}")
            print(f"Link: {result.get('permalink')}")
            print(f"Số ảnh: {len(result.get('images', []))}")
            
            # Hiển thị thông tin ảnh
            images = result.get('images', [])
            if images:
                print("Ảnh sản phẩm:")
                for i, img in enumerate(images):
                    print(f"  {i+1}. {img.get('src', 'N/A')}")
            
            return True
        else:
            print("Không thể tạo sản phẩm")
            return False
            
    except Exception as e:
        print(f"Lỗi: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("Tạo sản phẩm có ảnh thực tế")
    print("=" * 40)
    
    success = upload_product_with_real_image()
    
    print("=" * 40)
    if success:
        print("Sản phẩm có ảnh đã được tạo thành công!")
        print("Kiểm tra trên:")
        print("- Trang sản phẩm trên website")
        print("- Admin WooCommerce")
    else:
        print("Có lỗi khi tạo sản phẩm có ảnh")

if __name__ == "__main__":
    main()