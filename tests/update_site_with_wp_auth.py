
#!/usr/bin/env python3
"""
Script cập nhật WordPress Authentication từ thông tin trong UI
"""

import sys
import os
sys.path.append('.')

def update_wordpress_auth_from_ui():
    """Cập nhật WordPress auth với thông tin từ UI"""
    try:
        from app.database import DatabaseManager
        
        db = DatabaseManager()
        sites = db.get_active_sites()
        
        if not sites:
            print("❌ Không có site hoạt động")
            return False
        
        # Lấy site Vogue Pony
        vogue_pony_site = None
        for site in sites:
            if 'voguepony' in site.url.lower():
                vogue_pony_site = site
                break
        
        if not vogue_pony_site:
            print("❌ Không tìm thấy site Vogue Pony")
            return False
        
        print(f"🌐 Cập nhật site: {vogue_pony_site.name}")
        print(f"   URL: {vogue_pony_site.url}")
        
        # Thông tin WordPress từ UI
        wp_username = "admin@voguepony"
        wp_app_password = input("Nhập Application Password từ UI (đã hiển thị): ")
        
        if not wp_app_password:
            print("❌ Application Password không được để trống")
            return False
        
        # Cập nhật database với thông tin đầy đủ
        site_data = {
            'name': vogue_pony_site.name,
            'url': vogue_pony_site.url,
            'consumer_key': vogue_pony_site.consumer_key,
            'consumer_secret': vogue_pony_site.consumer_secret,
            'wp_username': wp_username,
            'wp_app_password': wp_app_password,
            'is_active': vogue_pony_site.is_active,
            'notes': vogue_pony_site.notes
        }
        
        db.update_site(vogue_pony_site.id, site_data)
        
        print("\n✅ Cập nhật WordPress authentication thành công!")
        print(f"   WordPress Username: {wp_username}")
        print(f"   App Password: {'*' * len(wp_app_password)}")
        
        return True
        
    except Exception as e:
        print(f"❌ Lỗi cập nhật: {str(e)}")
        return False

if __name__ == "__main__":
    print("🔧 Cập nhật WordPress Authentication cho Vogue Pony")
    print("=" * 60)
    update_wordpress_auth_from_ui()
