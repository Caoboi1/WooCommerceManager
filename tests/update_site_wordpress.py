#!/usr/bin/env python3
"""
Script để cập nhật thông tin WordPress authentication cho site Vogue Pony
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import DatabaseManager

def update_vogue_pony_site():
    """Cập nhật thông tin WordPress cho site Vogue Pony"""
    db = DatabaseManager()
    
    # Lấy thông tin site Vogue Pony (ID = 1)
    site = db.get_site(1)
    if not site:
        print("Không tìm thấy site Vogue Pony")
        return
    
    print(f"Đang cập nhật site: {site.name}")
    
    # Cập nhật thông tin WordPress authentication
    site_data = {
        'name': site.name,
        'url': site.url,
        'consumer_key': site.consumer_key,
        'consumer_secret': site.consumer_secret,
        'wp_username': 'adminvoguepony',
        'wp_app_password': '0mU5 OmH8 exmd vNkJ VYS9 g7zp',
        'is_active': site.is_active,
        'notes': site.notes
    }
    
    # Cập nhật database
    db.update_site(1, site_data)
    
    print("✅ Đã cập nhật thông tin WordPress authentication thành công!")
    print(f"WordPress Username: {site_data['wp_username']}")
    print(f"Application Password: {site_data['wp_app_password']}")

if __name__ == "__main__":
    update_vogue_pony_site()