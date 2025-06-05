
#!/usr/bin/env python3
"""
Script cập nhật WordPress App Password cho site
"""

import sys
import os
sys.path.append('.')

def update_wordpress_password():
    """Cập nhật WordPress App Password"""
    try:
        from app.database import DatabaseManager
        
        db = DatabaseManager()
        sites = db.get_active_sites()
        
        if not sites:
            print("❌ Không có site hoạt động")
            return False
        
        # Hiển thị danh sách sites
        print("📋 Danh sách sites:")
        for i, site in enumerate(sites):
            print(f"   {i+1}. {site.name} - {site.url}")
        
        # Chọn site để cập nhật
        choice = input("\nChọn site cần cập nhật (số thứ tự): ")
        try:
            site_index = int(choice) - 1
            if site_index < 0 or site_index >= len(sites):
                print("❌ Lựa chọn không hợp lệ")
                return False
        except ValueError:
            print("❌ Vui lòng nhập số")
            return False
        
        site = sites[site_index]
        print(f"\n🌐 Cập nhật site: {site.name}")
        
        # Nhập thông tin WordPress
        print("\n📝 Nhập thông tin WordPress:")
        wp_username = input("WordPress Username (admin username): ")
        if not wp_username:
            print("❌ Username không được để trống")
            return False
        
        print("\n🔑 WordPress App Password:")
        print("   1. Đăng nhập WordPress Admin")
        print("   2. Vào Users → Your Profile")
        print("   3. Scroll xuống 'Application Passwords'")
        print("   4. Tạo new password với tên 'WooCommerce Manager'")
        print("   5. Copy password (dạng: xxxx xxxx xxxx xxxx)")
        
        wp_app_password = input("Paste App Password: ")
        if not wp_app_password:
            print("❌ App Password không được để trống")
            return False
        
        # Cập nhật database
        site_data = {
            'name': site.name,
            'url': site.url,
            'consumer_key': site.consumer_key,
            'consumer_secret': site.consumer_secret,
            'wp_username': wp_username,
            'wp_app_password': wp_app_password,
            'is_active': site.is_active,
            'notes': site.notes
        }
        
        db.update_site(site.id, site_data)
        
        print("\n✅ Cập nhật WordPress authentication thành công!")
        print(f"   WordPress Username: {wp_username}")
        print(f"   App Password: {'*' * len(wp_app_password)}")
        
        return True
        
    except Exception as e:
        print(f"❌ Lỗi cập nhật: {str(e)}")
        return False

if __name__ == "__main__":
    print("🔧 Cập nhật WordPress App Password")
    print("=" * 50)
    update_wordpress_password()
