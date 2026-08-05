"""
🚀 Phase 2 Address Parser & Location Master Extractor
🔍 Scans addresses in master_table, extracts Building (7), Street (6), and Locality (5) via regex, 
   and links them hierarchically under their respective parent Area (4) node in location_master.
"""
import os
import sys
import uuid
import re
from sqlalchemy import text

sys.path.append(os.path.dirname(__file__))
from app import app, db

# Enable UTF-8 console output for Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

def create_slug(text_val):
    val = str(text_val).lower().strip()
    val = re.sub(r"[^\w\s-]", "", val)
    val = re.sub(r"[-\s]+", "-", val)
    return val

def parse_address_components(address_str):
    """
    Uses high-precision regex suffix markers to isolate Building, Street, and Locality.
    """
    if not address_str or len(address_str.strip()) < 5:
        return None, None, None

    # Clean address string
    addr = " " + address_str.strip() + " "

    # Suffix regex rules (matching typical Indian address patterns)
    building_rx = r"\b([A-Za-z0-9\s']+(?:apts?|apartments?|plaza|towers?|chambers?|house|enclave|residency|heights|building|complex|society))\b"
    street_rx = r"\b([A-Za-z0-9\s']+(?:road|rd|street|marg|lane|ln|gali|bypass|path|flyover))\b"
    locality_rx = r"\b([A-Za-z0-9\s']+(?:sector|phase|block|nagar|extension|ext|layout|zone|colony))\b"

    building_match = re.search(building_rx, addr, re.IGNORECASE)
    street_match = re.search(street_rx, addr, re.IGNORECASE)
    locality_match = re.search(locality_rx, addr, re.IGNORECASE)

    building = building_match.group(0).strip() if building_match else None
    street = street_match.group(0).strip() if street_match else None
    locality = locality_match.group(0).strip() if locality_match else None

    return building, street, locality

def get_or_insert_node(conn, name, parent_id, level, loc_type):
    """Checks cache or database and inserts node, returning its ID."""
    existing = conn.execute(text("""
        SELECT id FROM location_master 
        WHERE name = :name AND parent_id <=> :parent_id AND location_type = :loc_type
    """), {"name": name, "parent_id": parent_id, "loc_type": loc_type}).scalar()

    if existing:
        return existing

    node_uuid = str(uuid.uuid4())
    slug = create_slug(name)
    slug = slug[:255]

    try:
        conn.execute(text("""
            INSERT INTO location_master (uuid, parent_id, location_level, location_type, name, slug)
            VALUES (:uuid, :parent_id, :level, :type, :name, :slug)
        """), {
            "uuid": node_uuid,
            "parent_id": parent_id,
            "level": level,
            "type": loc_type,
            "name": name,
            "slug": slug
        })
        conn.commit()
        return conn.execute(text("SELECT LAST_INSERT_ID()")).scalar()
    except Exception:
        # Handle unique constraint collisions by appending short UUID suffix
        slug = f"{slug}-{node_uuid[:8]}"
        conn.execute(text("""
            INSERT INTO location_master (uuid, parent_id, location_level, location_type, name, slug)
            VALUES (:uuid, :parent_id, :level, :type, :name, :slug)
        """), {
            "uuid": node_uuid,
            "parent_id": parent_id,
            "level": level,
            "type": loc_type,
            "name": name,
            "slug": slug
        })
        conn.commit()
        return conn.execute(text("SELECT LAST_INSERT_ID()")).scalar()

def main():
    print("=============================================================")
    print("🔍 RUNNING ADDRESS HIERARCHY EXTRACTOR (PHASE 2)")
    print("=============================================================\n")

    with app.app_context():
        engine = db.engine
        
        with engine.connect() as conn:
            # 1. Cache Level 4 (Area) nodes to avoid nested queries
            print("Caching active Area nodes from location_master...")
            area_cache = {}  # (city_name.lower(), area_name.lower()) -> Area Node ID
            
            areas = conn.execute(text("""
                SELECT a.id AS area_id, a.name AS area_name, c.name AS city_name 
                FROM location_master a
                JOIN location_master c ON a.parent_id = c.id
                WHERE a.location_level = 4 AND c.location_level = 3
            """)).fetchall()
            
            for row in areas:
                key = (row.city_name.strip().lower(), row.area_name.strip().lower())
                area_cache[key] = row.area_id
            print(f"Cached {len(area_cache):,} Area nodes.\n")

            # 2. Query master_table records with addresses
            print("Fetching address listings from master_table...")
            records = conn.execute(text("""
                SELECT id, business_name, address, city, area 
                FROM master_table 
                WHERE address IS NOT NULL AND address != ''
                AND city IS NOT NULL AND city != ''
                AND area IS NOT NULL AND area != ''
                LIMIT 50000 -- Limit batch size for safety
            """)).fetchall()

            if not records:
                print("No addresses found in master_table to process.")
                return

            print(f"Found {len(records):,} records. Processing & extracting deep location levels...\n")
            
            building_count = 0
            street_count = 0
            locality_count = 0
            
            for idx, row in enumerate(records):
                city_key = row.city.strip().lower()
                area_key = row.area.strip().lower()
                
                # Check if we have the parent Area node ID
                parent_area_id = area_cache.get((city_key, area_key))
                if not parent_area_id:
                    continue  # Area not in location_master yet, skip
                
                # Extract components
                building, street, locality = parse_address_components(row.address)
                
                # Insert Building (Level 7)
                if building:
                    get_or_insert_node(conn, building, parent_area_id, 7, "Building")
                    building_count += 1
                    
                # Insert Street (Level 6)
                if street:
                    get_or_insert_node(conn, street, parent_area_id, 6, "Street")
                    street_count += 1
                    
                # Insert Locality (Level 5)
                if locality:
                    get_or_insert_node(conn, locality, parent_area_id, 5, "Locality")
                    locality_count += 1

                if (idx + 1) % 5000 == 0:
                    print(f"Processed {idx + 1}/{len(records)} listings...")

            print("\n=============================================================")
            print("🎉 EXTRACTION COMPLETE SUMMARY:")
            print(f"🏢 Buildings Extracted & Registered (Level 7): {building_count:,}")
            print(f"🛣️ Streets Extracted & Registered (Level 6):   {street_count:,}")
            print(f"🏡 Localities Extracted & Registered (Level 5): {locality_count:,}")
            print("=============================================================")

if __name__ == "__main__":
    main()