
#!/usr/bin/env python3
"""
Script kiểm tra WordPress authentication cho upload ảnh
"""

import sys
import os
sys.path.append('.')

def check_wordpress_auth():
    """Kiểm tra WordPress authentication trong database"""
    try:
        from app.database import DatabaseManager
        
        db = DatabaseManager()
        sites = db.get_active_sites()
        
        if not sites:
            print("❌ Không có site hoạt động")
            return False
            
        for site in sites:
            print(f"\n🌐 Site: {site.name}")
            print(f"   URL: {site.url}")
            print(f"   Consumer Key: {site.consumer_key[:10]}...")
            
            # Kiểm tra WordPress auth
            wp_username = getattr(site, 'wp_username', '')
            wp_app_password = getattr(site, 'wp_app_password', '')
            
            print(f"   WordPress Username: {wp_username}")
            
            if wp_app_password:
                print(f"   WordPress App Password: {'*' * len(wp_app_password)} (có)")
            else:
                print("   WordPress App Password: ❌ THIẾU")
                print("   ⚠️  Cần tạo WordPress App Password để upload ảnh!")
                
        return True
        
    except Exception as e:
        print(f"❌ Lỗi kiểm tra: {str(e)}")
        return False

if __name__ == "__main__":
    print("🔍 Kiểm tra WordPress Authentication")
    print("=" * 50)
    check_wordpress_auth()
