# Auto-Load Category Feature Documentation

## Overview
The auto-load category feature automatically populates the category field in the WooCommerce upload form based on data from the folder scanner, eliminating manual category selection.

## Implementation Details

### Key Components
1. **Enhanced set_folder_category() method** in `app/product_upload_dialog.py`
2. **Dual matching strategy** for category selection
3. **Detailed logging** for debugging and monitoring

### How It Works

#### 1. Category Matching Process
```python
def set_folder_category(self, folder_data):
    # Step 1: Try matching by category_id
    category_id = folder_data.get('category_id')
    if category_id and self.db_manager:
        category = self.db_manager.get_category_by_id(category_id)
        if category:
            wc_category_id = category.get('wc_category_id')
            # Match in combo box by WooCommerce ID
    
    # Step 2: Fallback to name-based matching
    category_name = folder_data.get('category_name')
    if category_name:
        # Search combo box items by name similarity
```

#### 2. Integration Points
- **Folder Scanner**: Provides category_id and category_name data
- **Database**: Stores category mapping between local and WooCommerce IDs
- **Upload Dialog**: Automatically sets category when folder is selected

#### 3. Data Flow
```
Folder Scanner → Database (category_id, category_name)
       ↓
Upload Dialog → set_folder_category()
       ↓
Category Combo Box (auto-selected)
```

## User Experience

### Before Auto-Load
1. User selects folder from scanner
2. Product info auto-fills
3. **User manually selects category** from dropdown
4. User uploads product

### After Auto-Load
1. User selects folder from scanner
2. Product info auto-fills
3. **Category automatically selected** based on folder data
4. User uploads product

## Technical Benefits

### 1. Error Reduction
- Eliminates manual category selection mistakes
- Ensures consistency between folder data and upload form

### 2. Workflow Efficiency
- Reduces upload time by automating category selection
- Streamlines bulk upload operations

### 3. Data Integrity
- Maintains connection between folder scanner and upload process
- Preserves category mappings across application sessions

## Database Schema Requirements

### Categories Table
```sql
categories (
    id INTEGER PRIMARY KEY,
    site_id INTEGER,
    wc_category_id INTEGER,  -- WooCommerce category ID
    name TEXT,
    slug TEXT,
    description TEXT
)
```

### Folder Scans Table
```sql
folder_scans (
    id INTEGER PRIMARY KEY,
    category_id INTEGER,     -- Links to categories.id
    category_name TEXT,      -- Fallback name matching
    data_name TEXT,
    path TEXT,
    -- other fields
)
```

## Configuration

### Logging
The feature includes comprehensive logging for debugging:
```python
self.logger.info(f"Đã set category: {category.get('name', '')} (ID: {wc_category_id})")
self.logger.info(f"Đã set category theo tên: {category_name}")
self.logger.info(f"Không tìm thấy category phù hợp. Category ID: {category_id}, Name: {category_name}")
```

### Error Handling
- Safe fallback to manual selection if auto-load fails
- Graceful handling of missing category data
- No application crashes on category lookup errors

## Future Enhancements

1. **Category Suggestion**: AI-powered category recommendations
2. **Bulk Category Assignment**: Mass update categories for multiple folders
3. **Category Validation**: Real-time validation against WooCommerce API
4. **Category Creation**: Auto-create missing categories on WooCommerce site

## Troubleshooting

### Common Issues
1. **Category not auto-selected**: Check folder_scans.category_id mapping
2. **Wrong category selected**: Verify categories.wc_category_id accuracy
3. **No categories available**: Sync categories from WooCommerce site first

### Debug Steps
1. Check application logs for category selection messages
2. Verify database category mappings
3. Test folder scanner category assignment
4. Validate WooCommerce API category sync