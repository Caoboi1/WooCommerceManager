#!/usr/bin/env python3
"""
Debug script to test page filtering logic
"""
import sqlite3
import sys
import os

# Add app to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from database import DatabaseManager

def debug_filtering():
    """Debug filtering logic"""
    print("=== Debug Page Filtering ===")
    
    # Initialize database
    db = DatabaseManager()
    
    # Get all sites
    print("\n1. Sites in database:")
    sites = db.get_all_sites()
    for site in sites:
        print(f"   ID: {site.id}, Name: {site.name}")
    
    # Get all pages
    print("\n2. All pages:")
    all_pages = db.get_all_pages()
    print(f"   Total pages: {len(all_pages)}")
    
    # Count pages by site
    site_counts = {}
    for page in all_pages:
        site_id = page.get('site_id')
        site_name = page.get('site_name', 'Unknown')
        if site_id not in site_counts:
            site_counts[site_id] = {'name': site_name, 'count': 0}
        site_counts[site_id]['count'] += 1
    
    print("\n3. Pages by site:")
    for site_id, info in site_counts.items():
        print(f"   Site ID {site_id} ({info['name']}): {info['count']} pages")
    
    # Test filtering for each site
    print("\n4. Testing filtering:")
    for site in sites:
        filtered_pages = db.get_pages_by_site(site.id)
        print(f"   Site '{site.name}' (ID: {site.id}): {len(filtered_pages)} pages")
        if filtered_pages:
            print(f"      First 3 pages:")
            for i, page in enumerate(filtered_pages[:3]):
                title = page.get('title', 'No title')
                if isinstance(title, dict):
                    title = title.get('rendered', 'No title')
                print(f"        {i+1}. {title} (site_id: {page.get('site_id')})")
    
    # Test the actual filtering logic from PageManagerTab
    print("\n5. Simulating PageManagerTab filtering:")
    
    # Test filter with site_id = 2 (Threadroar.com)
    test_site_id = 2
    print(f"\n   Testing filter with site_id = {test_site_id}")
    
    if test_site_id and test_site_id != 0:
        pages = db.get_pages_by_site(test_site_id)
        print(f"   Found {len(pages)} pages for site_id {test_site_id}")
    else:
        pages = db.get_all_pages()
        print(f"   Found {len(pages)} total pages")
    
    if pages:
        print("   First 5 pages:")
        for i, page in enumerate(pages[:5]):
            title = page.get('title', 'No title')
            if isinstance(title, dict):
                title = title.get('rendered', 'No title')
            print(f"     {i+1}. Site: {page.get('site_name')} | Title: {title}")

if __name__ == "__main__":
    debug_filtering()