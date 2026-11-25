"""
Sync Product Categories across All Platforms (High-Performance Bulk Version)
==========================================================================
Synchronizes DMart, Flipkart, JioMart, and Zepto categories from their respective
staging tables into public.product_category_master so that all 8 major platforms
(Amazon, BigBasket, Blinkit, DMart, Flipkart, IndiaMART, JioMart, Zepto) are
represented and queryable in product mapping.
"""

import logging
from sqlalchemy import text
from extensions import db

logger = logging.getLogger("PlatformCategorySync")

def reset_sequence():
    db.session.execute(text("""
        SELECT setval('product_category_master_id_seq', COALESCE((SELECT MAX(id) FROM product_category_master), 1));
    """))
    db.session.commit()

def sync_dmart_to_product_category_master():
    rows = db.session.execute(text("""
        SELECT category_id, category_name, parent_id, category_level, category_path 
        FROM dmart_categories 
        WHERE category_name IS NOT NULL AND category_name != ''
        ORDER BY category_level ASC, category_id ASC
    """)).fetchall()
    
    existing = set(db.session.execute(text("""
        SELECT category_path FROM product_category_master WHERE marketplace_name = 'DMart'
    """)).scalars().all())
    
    inserted = 0
    id_map = {}
    
    for r in rows:
        cid, name, pid, level, path = r[0], r[1].strip(), r[2], r[3] or 1, (r[4] or r[1]).strip()
        if path in existing:
            continue
            
        parent_id = id_map.get(pid, 0) if pid else 0
        parts = [p.strip() for p in path.split(' > ') if p.strip()]
        sub_name = parts[1] if len(parts) > 1 else ''
        child_name = parts[2] if len(parts) > 2 else ''
        
        res = db.session.execute(text("""
            INSERT INTO product_category_master 
            (marketplace_name, category_name, subcategory_name, child_category_name, parent_id, category_level, category_path, category_key)
            VALUES ('DMart', :name, :sub, :child, :pid, :level, :path, :key)
            RETURNING id
        """), {
            'name': name, 'sub': sub_name, 'child': child_name,
            'pid': parent_id, 'level': level, 'path': path, 'key': name.lower()
        })
        new_id = res.scalar()
        id_map[cid] = new_id
        existing.add(path)
        inserted += 1
        
    db.session.commit()
    return inserted


def sync_jiomart_to_product_category_master():
    rows = db.session.execute(text("""
        SELECT category_id, category_name, parent_id, category_level, category_path 
        FROM jiomart_categories 
        WHERE category_name IS NOT NULL AND category_name != ''
        ORDER BY category_level ASC, category_id ASC
    """)).fetchall()
    
    existing = set(db.session.execute(text("""
        SELECT category_path FROM product_category_master WHERE marketplace_name = 'JioMart'
    """)).scalars().all())
    
    inserted = 0
    id_map = {}
    
    for r in rows:
        cid, name, pid, level, path = r[0], r[1].strip(), r[2], (r[3] or 0) + 1, (r[4] or r[1]).strip()
        if path in existing:
            continue
            
        parent_id = id_map.get(pid, 0) if pid else 0
        parts = [p.strip() for p in path.split(' > ') if p.strip()]
        sub_name = parts[1] if len(parts) > 1 else ''
        child_name = parts[2] if len(parts) > 2 else ''
        
        res = db.session.execute(text("""
            INSERT INTO product_category_master 
            (marketplace_name, category_name, subcategory_name, child_category_name, parent_id, category_level, category_path, category_key)
            VALUES ('JioMart', :name, :sub, :child, :pid, :level, :path, :key)
            RETURNING id
        """), {
            'name': name, 'sub': sub_name, 'child': child_name,
            'pid': parent_id, 'level': level, 'path': path, 'key': name.lower()
        })
        new_id = res.scalar()
        id_map[cid] = new_id
        existing.add(path)
        inserted += 1
        
    db.session.commit()
    return inserted


def sync_flipkart_to_product_category_master():
    rows = db.session.execute(text("""
        SELECT category_id, category_name, parent_id, category_level, category_path 
        FROM flipkart_db_mapping 
        WHERE category_name IS NOT NULL AND category_name != ''
        ORDER BY category_level ASC, category_id ASC
    """)).fetchall()
    
    existing = set(db.session.execute(text("""
        SELECT category_path FROM product_category_master WHERE marketplace_name = 'Flipkart'
    """)).scalars().all())
    
    inserted = 0
    id_map = {}
    
    for r in rows:
        cid, name, pid, level, path = r[0], r[1].strip(), r[2], (r[3] or 0) + 1, (r[4] or r[1]).strip()
        if not path:
            path = name
        if path in existing:
            continue
            
        parent_id = id_map.get(pid, 0) if pid else 0
        parts = [p.strip() for p in path.split(' > ') if p.strip()]
        sub_name = parts[1] if len(parts) > 1 else ''
        child_name = parts[2] if len(parts) > 2 else ''
        
        res = db.session.execute(text("""
            INSERT INTO product_category_master 
            (marketplace_name, category_name, subcategory_name, child_category_name, parent_id, category_level, category_path, category_key)
            VALUES ('Flipkart', :name, :sub, :child, :pid, :level, :path, :key)
            RETURNING id
        """), {
            'name': name, 'sub': sub_name, 'child': child_name,
            'pid': parent_id, 'level': level, 'path': path, 'key': name.lower()
        })
        new_id = res.scalar()
        id_map[cid] = new_id
        existing.add(path)
        inserted += 1
        
    db.session.commit()
    return inserted


def sync_zepto_to_product_category_master():
    rows = db.session.execute(text("""
        SELECT category_id, category, parent_id, category_level, category_path 
        FROM zepto_db_mapping 
        WHERE category IS NOT NULL AND category != ''
        ORDER BY category_level ASC, category_id ASC
    """)).fetchall()
    
    existing = set(db.session.execute(text("""
        SELECT category_path FROM product_category_master WHERE marketplace_name = 'Zepto'
    """)).scalars().all())
    
    inserted = 0
    id_map = {}
    
    for r in rows:
        cid, name, pid, level, path = r[0], r[1].strip(), r[2], r[3] or 1, (r[4] or r[1]).strip()
        if path in existing:
            continue
            
        parent_id = id_map.get(pid, 0) if pid else 0
        parts = [p.strip() for p in path.split(' > ') if p.strip()]
        sub_name = parts[1] if len(parts) > 1 else ''
        child_name = parts[2] if len(parts) > 2 else ''
        
        res = db.session.execute(text("""
            INSERT INTO product_category_master 
            (marketplace_name, category_name, subcategory_name, child_category_name, parent_id, category_level, category_path, category_key)
            VALUES ('Zepto', :name, :sub, :child, :pid, :level, :path, :key)
            RETURNING id
        """), {
            'name': name, 'sub': sub_name, 'child': child_name,
            'pid': parent_id, 'level': level, 'path': path, 'key': name.lower()
        })
        new_id = res.scalar()
        id_map[cid] = new_id
        existing.add(path)
        inserted += 1
        
    db.session.commit()
    return inserted


def sync_all_missing_platforms():
    """Run synchronization for all missing product platforms."""
    reset_sequence()
    results = {
        'dmart_inserted': sync_dmart_to_product_category_master(),
        'jiomart_inserted': sync_jiomart_to_product_category_master(),
        'flipkart_inserted': sync_flipkart_to_product_category_master(),
        'zepto_inserted': sync_zepto_to_product_category_master(),
    }
    reset_sequence()
    return results

if __name__ == '__main__':
    import sys
    sys.path.insert(0, 'backend')
    from app import app
    with app.app_context():
        res = sync_all_missing_platforms()
        print("Sync results:", res)
