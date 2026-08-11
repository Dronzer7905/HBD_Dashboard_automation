"""
🚀 High-Performance Hierarchical Location Migration Script
🌎 Migrates the entire Location_Master_India database into the structured 3-table tree schema in seconds.
⚡ Uses optimized 3-phase memory mapping to avoid database query roundtrips.
"""
import os
import sys
import uuid
import re
from datetime import datetime
from sqlalchemy import text

sys.path.append(os.path.dirname(__file__))
from app import app, db

# Support UTF-8 output on Windows terminals to prevent charmap encoding errors
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

STATE_STANDARD_MAP = {
    "mh": "Maharashtra", "maharashtra": "Maharashtra", "maharastra": "Maharashtra",
    "gj": "Gujarat", "gujarat": "Gujarat",
    "dl": "Delhi", "delhi": "Delhi", "new delhi": "Delhi", "nct of delhi": "Delhi",
    "ka": "Karnataka", "karnataka": "Karnataka",
    "tn": "Tamil Nadu", "tamil nadu": "Tamil Nadu", "tamilnadu": "Tamil Nadu",
    "ap": "Andhra Pradesh", "andhra pradesh": "Andhra Pradesh",
    "tg": "Telangana", "telangana": "Telangana", "ts": "Telangana", "ts-telangana": "Telangana",
    "up": "Uttar Pradesh", "uttar pradesh": "Uttar Pradesh",
    "mp": "Madhya Pradesh", "madhya pradesh": "Madhya Pradesh",
    "wb": "West Bengal", "west bengal": "West Bengal",
    "hr": "Haryana", "haryana": "Haryana",
    "pb": "Punjab", "punjab": "Punjab",
    "rj": "Rajasthan", "rajasthan": "Rajasthan",
    "or": "Odisha", "odisha": "Odisha", "orissa": "Odisha",
    "kl": "Kerala", "kerala": "Kerala",
    "br": "Bihar", "bihar": "Bihar",
    "jh": "Jharkhand", "jharkhand": "Jharkhand",
    "ct": "Chhattisgarh", "chhattisgarh": "Chhattisgarh", "chattisgarh": "Chhattisgarh",
    "as": "Assam", "assam": "Assam",
    "jk": "Jammu & Kashmir", "jammu & kashmir": "Jammu & Kashmir", "jammu and kashmir": "Jammu & Kashmir",
    "ut": "Uttarakhand", "uttarakhand": "Uttarakhand", "uttaranchal": "Uttarakhand",
    "hp": "Himachal Pradesh", "himachal pradesh": "Himachal Pradesh",
    "tr": "Tripura", "tripura": "Tripura",
    "ml": "Meghalaya", "meghalaya": "Meghalaya",
    "mn": "Manipur", "manipur": "Manipur",
    "nl": "Nagaland", "nagaland": "Nagaland",
    "goa": "Goa", "ga": "Goa",
    "ar": "Arunachal Pradesh", "arunachal pradesh": "Arunachal Pradesh",
    "mz": "Mizoram", "mizoram": "Mizoram",
    "sk": "Sikkim", "sikkim": "Sikkim",
    "py": "Puducherry", "puducherry": "Puducherry", "pondicherry": "Puducherry",
    "ch": "Chandigarh", "chandigarh": "Chandigarh",
    "an": "Andaman & Nicobar", "andaman & nicobar": "Andaman & Nicobar", "andaman and nicobar": "Andaman & Nicobar", "andaman and nicobar islands": "Andaman & Nicobar",
    "dn": "Dadra & Nagar Haveli and Daman & Diu", "daman & diu": "Dadra & Nagar Haveli and Daman & Diu", "daman and diu": "Dadra & Nagar Haveli and Daman & Diu", "dadra & nagar haveli": "Dadra & Nagar Haveli and Daman & Diu",
    "ld": "Lakshadweep", "lakshadweep": "Lakshadweep",
    "la": "Ladakh", "ladakh": "Ladakh"
}

def create_slug(text_val):
    """Converts a name string to an alphanumeric URL-safe slug."""
    val = str(text_val).lower().strip()
    val = re.sub(r"[^\w\s-]", "", val)
    val = re.sub(r"[-\s]+", "-", val)
    return val

def ensure_tables_exist(conn):
    print("Checking if hierarchical location tables exist...")
    
    # 1. location_master (Supports 7 levels and composite parent_id + slug unique key)
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS location_master (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            uuid VARCHAR(36) NOT NULL,
            parent_id BIGINT DEFAULT NULL,
            location_level TINYINT NOT NULL COMMENT '1=Country, 2=State, 3=City, 4=Area, 5=Locality, 6=Street, 7=Building',
            location_type VARCHAR(30) NOT NULL,
            name VARCHAR(255) NOT NULL,
            short_name VARCHAR(100) DEFAULT NULL,
            slug VARCHAR(255) NOT NULL,
            code VARCHAR(50) DEFAULT NULL,
            alternate_name VARCHAR(255) DEFAULT NULL,
            description TEXT DEFAULT NULL,
            latitude DECIMAL(10,7) DEFAULT NULL,
            longitude DECIMAL(10,7) DEFAULT NULL,
            timezone VARCHAR(100) DEFAULT 'Asia/Kolkata',
            postal_code VARCHAR(20) DEFAULT NULL,
            materialized_path VARCHAR(255) DEFAULT NULL,
            status VARCHAR(20) DEFAULT 'Active',
            city_rank INT DEFAULT NULL,
            metadata JSON DEFAULT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (parent_id) REFERENCES location_master(id) ON DELETE SET NULL,
            UNIQUE KEY uq_parent_slug (parent_id, slug),
            UNIQUE KEY uq_uuid (uuid),
            INDEX idx_parent_type (parent_id, location_type),
            INDEX idx_postal_code (postal_code)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
    """))

    # 2. location_aliases
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS location_aliases (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            location_id BIGINT NOT NULL,
            alias VARCHAR(255) NOT NULL,
            alias_type VARCHAR(30) DEFAULT 'Local',
            language_id BIGINT DEFAULT NULL,
            is_primary BOOLEAN DEFAULT FALSE,
            search_weight SMALLINT DEFAULT 100,
            status VARCHAR(20) DEFAULT 'Active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (location_id) REFERENCES location_master(id) ON DELETE CASCADE,
            UNIQUE KEY uq_loc_alias (location_id, alias),
            INDEX idx_alias_search (alias)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
    """))

    # 3. location_postal_codes
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS location_postal_codes (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            location_id BIGINT NOT NULL,
            postal_code VARCHAR(20) NOT NULL,
            area_name VARCHAR(255) DEFAULT NULL,
            is_primary BOOLEAN DEFAULT TRUE,
            delivery_available BOOLEAN DEFAULT TRUE,
            status VARCHAR(20) DEFAULT 'Active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (location_id) REFERENCES location_master(id) ON DELETE CASCADE,
            UNIQUE KEY uq_loc_postal (location_id, postal_code),
            INDEX idx_postal_code (postal_code)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
    """))
    print("✅ Hierarchical location tables verified/created successfully.")

def build_cache(conn):
    """Loads all existing hierarchical records into RAM to skip duplicate queries."""
    print("Caching existing locations from location_master...")
    state_cache = {}  # name.lower() -> id
    city_cache = {}   # (parent_state_id, name.lower()) -> id
    area_cache = {}   # (parent_city_id, name.lower()) -> id
    
    # Load States
    states = conn.execute(text("SELECT id, name FROM location_master WHERE location_level = 2")).fetchall()
    for row in states:
        state_cache[row.name.strip().lower()] = row.id
        
    # Load Cities
    cities = conn.execute(text("SELECT id, parent_id, name FROM location_master WHERE location_level = 3")).fetchall()
    for row in cities:
        city_cache[(row.parent_id, row.name.strip().lower())] = row.id
        
    # Load Areas
    areas = conn.execute(text("SELECT id, parent_id, name FROM location_master WHERE location_level = 4")).fetchall()
    for row in areas:
        area_cache[(row.parent_id, row.name.strip().lower())] = row.id
        
    print(f"Cached {len(state_cache)} States, {len(city_cache)} Cities, and {len(area_cache)} Areas.")
    return state_cache, city_cache, area_cache

def main():
    print("=============================================================")
    print("🚀 RUNNING FULL HIERARCHICAL LOCATION MIGRATION")
    print("=============================================================\n")

    with app.app_context():
        engine = db.engine
        
        with engine.connect() as conn:
            ensure_tables_exist(conn)
            
            # Verify source table exists
            has_source = conn.execute(text("SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'Location_Master_India'")).scalar() > 0
            if not has_source:
                print("❌ Error: 'Location_Master_India' table does not exist. Migration aborted.")
                return
                
            # Build memory caches
            state_cache, city_cache, area_cache = build_cache(conn)
            
            # 1. Create or Get Country Node (India)
            country_id = conn.execute(text("SELECT id FROM location_master WHERE location_level = 1 AND name = 'India'")).scalar()
            if not country_id:
                print("Inserting Country Node (India)...")
                conn.execute(text("""
                    INSERT INTO location_master (uuid, parent_id, location_level, location_type, name, slug)
                    VALUES (:uuid, NULL, 1, 'Country', 'India', 'india')
                """), {"uuid": str(uuid.uuid4())})
                conn.commit()
                country_id = conn.execute(text("SELECT LAST_INSERT_ID()")).scalar()
            print(f"🌐 Country Root Node ID: {country_id}")

            # -----------------------------------------------------------------
            # PHASE 1: Migrate Unique States (Standardized & Aliased)
            # -----------------------------------------------------------------
            print("\n🔄 Phase 1: Migrating unique states...")
            raw_states = conn.execute(text("SELECT DISTINCT BINARY state_full_name AS sname FROM Location_Master_India WHERE state_full_name IS NOT NULL AND state_full_name != ''")).fetchall()
            state_aliases_to_insert = []
            
            for r in raw_states:
                raw_name = r.sname.strip()
                raw_skey = raw_name.lower()
                
                # Clean and Standardize Name
                standard_name = STATE_STANDARD_MAP.get(raw_skey, raw_name)
                skey = standard_name.lower()
                
                if skey not in state_cache:
                    node_uuid = str(uuid.uuid4())
                    slug = create_slug(standard_name)
                    try:
                        conn.execute(text("""
                            INSERT INTO location_master (uuid, parent_id, location_level, location_type, name, slug)
                            VALUES (:uuid, :pid, 2, 'State', :name, :slug)
                        """), {"uuid": node_uuid, "pid": country_id, "name": standard_name, "slug": slug})
                        conn.commit()
                        state_id = conn.execute(text("SELECT LAST_INSERT_ID()")).scalar()
                    except Exception:
                        # Append unique slug suffix in case of collision
                        slug = f"{slug}-{node_uuid[:8]}"
                        conn.execute(text("""
                            INSERT INTO location_master (uuid, parent_id, location_level, location_type, name, slug)
                            VALUES (:uuid, :pid, 2, 'State', :name, :slug)
                        """), {"uuid": node_uuid, "pid": country_id, "name": standard_name, "slug": slug})
                        conn.commit()
                        state_id = conn.execute(text("SELECT LAST_INSERT_ID()")).scalar()
                    
                    state_cache[skey] = state_id
                
                # Fetch standard state ID to map this raw spelling variation
                state_id = state_cache[skey]
                state_cache[raw_skey] = state_id # Map raw key to standard ID in cache
                
                # Store alias if spelling is different from the standardized name
                if raw_skey != skey:
                    state_aliases_to_insert.append((state_id, raw_name))
            
            # Batch insert state spelling aliases into location_aliases
            if state_aliases_to_insert:
                print(f"Populating state spelling aliases (Total: {len(state_aliases_to_insert)})...")
                alias_batch = [{"loc_id": s_id, "alias": name} for s_id, name in state_aliases_to_insert]
                conn.execute(text("""
                    INSERT IGNORE INTO location_aliases (location_id, alias, alias_type, is_primary)
                    VALUES (:loc_id, :alias, 'Spell Variation', FALSE)
                """), alias_batch)
                conn.commit()
                
            print(f"✅ State Migration Complete. Total cached states (including variations): {len(state_cache)}")

            # -----------------------------------------------------------------
            # PHASE 2: Migrate Unique Cities
            # -----------------------------------------------------------------
            print("\n🔄 Phase 2: Migrating unique cities...")
            
            # Load City Ranks
            print("Caching city ranks from Top_cities_rank...")
            city_ranks = {} # (state_name.lower(), city_name.lower()) -> city_rank
            try:
                ranks = conn.execute(text("SELECT LOWER(state_name) as sname, LOWER(city_name) as cname, city_rank FROM Top_cities_rank")).fetchall()
                for row in ranks:
                    city_ranks[(row.sname.strip(), row.cname.strip())] = row.city_rank
                print(f"Cached {len(city_ranks)} city ranks.")
            except Exception as e:
                print(f"⚠️ Warning: Could not read Top_cities_rank table. City ranks will not be populated: {e}")

            raw_cities = conn.execute(text("""
                SELECT DISTINCT BINARY state_full_name AS sname, BINARY city_name AS cname 
                FROM Location_Master_India 
                WHERE state_full_name IS NOT NULL AND city_name IS NOT NULL AND city_name != ''
            """)).fetchall()
            
            cities_to_insert = []
            for r in raw_cities:
                sname = r.sname.strip()
                cname = r.cname.strip()
                s_id = state_cache.get(sname.lower())
                if s_id and (s_id, cname.lower()) not in city_cache:
                    # Look up city_rank
                    rank = city_ranks.get((sname.lower(), cname.lower()))
                    cities_to_insert.append((s_id, cname, rank))
            
            if cities_to_insert:
                print(f"Found {len(cities_to_insert):,} new cities to insert. Inserting in batches of 2000...")
                batch = []
                for idx, (s_id, cname, rank) in enumerate(cities_to_insert):
                    node_uuid = str(uuid.uuid4())
                    slug = create_slug(cname)
                    batch.append({
                        "uuid": node_uuid,
                        "parent_id": s_id,
                        "name": cname,
                        "slug": slug,
                        "city_rank": rank
                    })
                    
                    if len(batch) >= 2000 or idx == len(cities_to_insert) - 1:
                        # Insert batch
                        conn.execute(text("""
                            INSERT IGNORE INTO location_master (uuid, parent_id, location_level, location_type, name, slug, city_rank)
                            VALUES (:uuid, :parent_id, 3, 'City', :name, :slug, :city_rank)
                        """), batch)
                        conn.commit()
                        batch = []
                
                # Re-fetch new cities to populate cache mapping
                new_cities = conn.execute(text("SELECT id, parent_id, name FROM location_master WHERE location_level = 3")).fetchall()
                for row in new_cities:
                    city_cache[(row.parent_id, row.name.strip().lower())] = row.id
            print(f"✅ City Migration Complete. Total cached cities: {len(city_cache)}")

            # -----------------------------------------------------------------
            # PHASE 3: Migrate Unique Areas & Postal Codes
            # -----------------------------------------------------------------
            print("\n🔄 Phase 3: Migrating unique areas and postal codes...")
            
            # Detect available columns in Location_Master_India dynamically to ensure compatibility
            cols_res = conn.execute(text("SHOW COLUMNS FROM Location_Master_India")).fetchall()
            available_cols = {r[0].lower() for r in cols_res}
            print(f"Detected columns in Location_Master_India: {', '.join(available_cols)}")
            
            use_legacy = False
            if 'area' in available_cols and 'city' in available_cols and 'state' in available_cols:
                # If area_name column is missing or empty, fall back to legacy columns
                if 'area_name' in available_cols:
                    area_name_count = conn.execute(text("SELECT COUNT(*) FROM Location_Master_India WHERE area_name IS NOT NULL AND area_name != ''")).scalar() or 0
                    if area_name_count == 0:
                        print("Warning: 'area_name' column is empty! Falling back to legacy columns 'state', 'city', 'area'...")
                        use_legacy = True
                else:
                    print("'area_name' column is missing. Falling back to legacy columns 'state', 'city', 'area'...")
                    use_legacy = True
            
            if use_legacy:
                print("Running unique areas extraction using legacy columns (state, city, area)...")
                raw_areas_q = """
                    SELECT DISTINCT 
                        l.state AS sname, 
                        l.city AS cname, 
                        l.area AS aname,
                        m.pincode AS pincode
                    FROM Location_Master_India l
                    LEFT JOIN (
                        SELECT city, area, MAX(pincode) as pincode
                        FROM master_table
                        WHERE pincode IS NOT NULL AND pincode != ''
                        GROUP BY city, area
                    ) m ON l.city = m.city AND l.area = m.area
                    WHERE l.state IS NOT NULL AND l.city IS NOT NULL AND l.area IS NOT NULL AND l.area != ''
                """
            else:
                print("Running unique areas extraction using active columns (state_full_name, city_name, area_name)...")
                raw_areas_q = """
                    SELECT DISTINCT 
                        l.state_full_name AS sname, 
                        l.city_name AS cname, 
                        l.area_name AS aname,
                        m.pincode AS pincode
                    FROM Location_Master_India l
                    LEFT JOIN (
                        SELECT city, area, MAX(pincode) as pincode
                        FROM master_table
                        WHERE pincode IS NOT NULL AND pincode != ''
                        GROUP BY city, area
                    ) m ON l.city_name = m.city AND l.area_name = m.area
                    WHERE l.state_full_name IS NOT NULL AND l.city_name IS NOT NULL AND l.area_name IS NOT NULL AND l.area_name != ''
                """
                
            raw_areas = conn.execute(text(raw_areas_q)).fetchall()
            
            areas_to_insert = []
            for r in raw_areas:
                sname = r.sname.strip()
                cname = r.cname.strip()
                aname = r.aname.strip()
                pcode = str(r.pincode).strip() if r.pincode else None
                
                s_id = state_cache.get(sname.lower())
                if s_id:
                    c_id = city_cache.get((s_id, cname.lower()))
                    if c_id and (c_id, aname.lower()) not in area_cache:
                        areas_to_insert.append((c_id, aname, pcode))
                        
            if areas_to_insert:
                print(f"Found {len(areas_to_insert):,} new areas to insert. Processing in batches of 5000...")
                batch = []
                for idx, (c_id, aname, pcode) in enumerate(areas_to_insert):
                    node_uuid = str(uuid.uuid4())
                    slug = create_slug(aname)
                    batch.append({
                        "uuid": node_uuid,
                        "parent_id": c_id,
                        "name": aname,
                        "slug": slug,
                        "pcode": pcode
                    })
                    
                    if len(batch) >= 5000 or idx == len(areas_to_insert) - 1:
                        conn.execute(text("""
                            INSERT IGNORE INTO location_master (uuid, parent_id, location_level, location_type, name, slug, postal_code)
                            VALUES (:uuid, :parent_id, 4, 'Area', :name, :slug, :pcode)
                        """), batch)
                        conn.commit()
                        batch = []
                        
                # Re-fetch new areas to populate cache mapping
                new_areas = conn.execute(text("SELECT id, parent_id, name, postal_code FROM location_master WHERE location_level = 4")).fetchall()
                for row in new_areas:
                    area_cache[(row.parent_id, row.name.strip().lower())] = row.id
                    
                # Batch insert PIN codes into location_postal_codes table
                print("Populating location_postal_codes bridge table...")
                postal_batch = []
                for row in new_areas:
                    if row.postal_code:
                        postal_batch.append({
                            "loc_id": row.id,
                            "pcode": str(row.postal_code).strip(),
                            "aname": row.name
                        })
                        if len(postal_batch) >= 5000:
                            conn.execute(text("""
                                INSERT IGNORE INTO location_postal_codes (location_id, postal_code, area_name)
                                VALUES (:loc_id, :pcode, :aname)
                            """), postal_batch)
                            conn.commit()
                            postal_batch = []
                    conn.commit()
            
            print(f"✅ Area & Postal Code Migration Complete. Total cached areas: {len(area_cache)}")

            # -----------------------------------------------------------------
            # PHASE 4: Populate State Short Code Aliases
            # -----------------------------------------------------------------
            print("\n🔄 Phase 4: Populating location_aliases with state short codes...")
            
            # Use appropriate state column based on legacy fallback detection in Phase 3
            state_col = "state" if use_legacy else "state_full_name"
            
            alias_sql = text(f"""
                INSERT IGNORE INTO location_aliases (location_id, alias, alias_type, is_primary)
                SELECT DISTINCT lm.id, TRIM(lmi.state_short_code), 'Short Code', TRUE
                FROM location_master lm
                JOIN Location_Master_India lmi ON LOWER(lm.name) = LOWER(lmi.{state_col})
                WHERE lm.location_level = 2 
                  AND lmi.state_short_code IS NOT NULL 
                  AND TRIM(lmi.state_short_code) != ''
            """)
            r_alias = conn.execute(alias_sql)
            conn.commit()
            print(f"✅ State short code aliases populated: {r_alias.rowcount} rows inserted.")
            
            print("\n=============================================================")
            print("🎉 FULL LOCATION HIERARCHY MIGRATION COMPLETED SUCCESSFULLY!")
            print("=============================================================")

if __name__ == "__main__":
    main()
