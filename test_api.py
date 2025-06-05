
#!/usr/bin/env python3
"""
Test script để kiểm tra API WooCommerce
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.woocommerce_api import WooCommerceAPI
from app.models import Site
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def test_api():
    # Tạo site object với credentials bạn cung cấp
    site = Site(
        name="Vogue Pony",
        url="https://voguepony.com",
        consumer_key="ck_d961ea5f91c37e781026a6f59cacfaf4921dc486",
        consumer_secret="cs_8642539dafcbb6ca0220af0dd35b435844f67c32",
        is_active=True
    )
    
    print(f"Testing API connection to: {site.url}")
    print(f"Consumer Key: {site.consumer_key}")
    print("-" * 50)
    
    api = WooCommerceAPI(site)
    
    # 1. Test connection
    print("1. Testing connection...")
    success, message = api.test_connection()
    print(f"Connection result: {success}")
    print(f"Message: {message}")
    print()
    
    if not success:
        print("❌ Kết nối thất bại! Kiểm tra lại credentials và URL.")
        return
    
    # 2. Get existing categories
    print("2. Getting existing categories...")
    try:
        categories = api.get_categories()
        print(f"Found {len(categories)} categories:")
        for cat in categories[:5]:  # Show first 5
            print(f"  - ID: {cat.get('id')}, Name: {cat.get('name')}, Parent: {cat.get('parent')}")
        print()
    except Exception as e:
        print(f"Error getting categories: {e}")
        return
    
    # 3. Test creating a category
    print("3. Testing category creation...")
    test_category = {
        "name": "Test Category API",
        "slug": "test-category-api", 
        "description": "Test category created via API",
        "parent": 0
    }
    
    try:
        result = api.create_category(test_category)
        if result:
            print(f"✅ Category created successfully!")
            print(f"  - ID: {result.get('id')}")
            print(f"  - Name: {result.get('name')}")
            print(f"  - Slug: {result.get('slug')}")
            print(f"  - Link: {result.get('_links', {}).get('self', [{}])[0].get('href', 'N/A')}")
            
            # Try to delete the test category
            print("4. Cleaning up test category...")
            delete_success = api.delete_category(result.get('id'), force=True)
            print(f"Delete result: {delete_success}")
        else:
            print("❌ Category creation failed - no result returned")
    except Exception as e:
        print(f"❌ Error creating category: {e}")

if __name__ == "__main__":
    test_api()
