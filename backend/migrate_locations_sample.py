import os
import sys
import uuid
import re
from sqlalchemy import text
from dotenv import load_dotenv

# Ensure we are in backend context
backend_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(backend_dir)
load_dotenv(os.path.join(backend_dir, '.env'))

from app import app
from extensions import db

# Support UTF-8 output on Windows terminals to prevent charmap encoding errors
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

def create_slug(name):
    # Convert to lowercase, replace special chars and spaces with dashes
    slug = name.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_-]+", "-", slug)
    return slug

def ensure_tables_exist(conn):
    print("Checking if location tables exist...")
    
    # 1. location_master (Updated with 7 levels and composite parent_id + slug unique key)
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

def insert_node(conn, name, parent_id, level, loc_type, postal_code=None, alternate=None):
    slug = create_slug(name)
    slug = slug[:255]

    # Check if node already exists by parent_id and name
    existing = conn.execute(text("""
        SELECT id FROM location_master 
        WHERE name = :name AND parent_id <=> :parent_id AND location_type = :loc_type
    """), {"name": name, "parent_id": parent_id, "loc_type": loc_type}).scalar()

    if existing:
        return existing

    node_uuid = str(uuid.uuid4())
    
    try:
        res = conn.execute(text("""
            INSERT INTO location_master 
            (uuid, parent_id, location_level, location_type, name, slug, postal_code, alternate_name)
            VALUES (:uuid, :parent_id, :level, :type, :name, :slug, :pcode, :alt)
        """), {
            "uuid": node_uuid,
            "parent_id": parent_id,
            "level": level,
            "type": loc_type,
            "name": name,
            "slug": slug,
            "pcode": postal_code,
            "alt": alternate
        })
        conn.commit()
        return conn.execute(text("SELECT LAST_INSERT_ID()")).scalar()
    except Exception as e:
        # Resolve parent_id + slug unique key collision by appending a short UUID segment
        slug = f"{slug}-{node_uuid[:8]}"
        res = conn.execute(text("""
            INSERT INTO location_master 
            (uuid, parent_id, location_level, location_type, name, slug, postal_code, alternate_name)
            VALUES (:uuid, :parent_id, :level, :type, :name, :slug, :pcode, :alt)
        """), {
            "uuid": node_uuid,
            "parent_id": parent_id,
            "level": level,
            "type": loc_type,
            "name": name,
            "slug": slug,
            "pcode": postal_code,
            "alt": alternate
        })
        conn.commit()
        return conn.execute(text("SELECT LAST_INSERT_ID()")).scalar()

def main():
    print("=============================================================")
    print("🌍 SAMPLE HIERARCHICAL LOCATION MIGRATION & TESTING")
    print("=============================================================\n")

    with app.app_context():
        engine = db.engine
        
        with engine.connect() as conn:
            # Ensure target tables exist
            ensure_tables_exist(conn)
            
            # Ask if Location_Master_India has data
            has_source = conn.execute(text("SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'Location_Master_India'")).scalar() > 0
            if not has_source:
                print("❌ Error: 'Location_Master_India' table does not exist. Cannot fetch sample data.")
                return

            print("Fetching sample records from Location_Master_India...")
            # Fetch a sample of 30 rows of distinct locations
            sample_query = text("""
                SELECT state, city, area, pincode 
                FROM Location_Master_India 
                WHERE state IS NOT NULL AND city IS NOT NULL AND area IS NOT NULL
                LIMIT 30
            """)
            rows = conn.execute(sample_query).fetchall()

            if not rows:
                print("⚠️ Warning: No rows found in Location_Master_India. Seeding dummy sample instead...")
                # Mock sample data
                rows = [
                    ("Gujarat", "Ahmedabad", "Navrangpura", "380009"),
                    ("Gujarat", "Ahmedabad", "Vastrapur", "380015"),
                    ("Gujarat", "Ahmedabad", "C G Road", "380009"),
                    ("Maharashtra", "Mumbai", "Andheri West", "400053"),
                    ("Maharashtra", "Mumbai", "Bandra West", "400050"),
                    ("Delhi", "New Delhi", "Connaught Place", "110001")
                ]

            print(f"Loaded {len(rows)} sample records. Beginning tree structuring...\n")
            
            # Begin tree generation
            # Step 1: Create Country (India) level 1
            country_id = insert_node(conn, "India", None, 1, "Country")
            print(f"🌐 Root Country Created: India (ID: {country_id})")

            for state_name, city_name, area_name, pincode in rows:
                # Step 2: State (level 2)
                state_id = insert_node(conn, state_name.strip(), country_id, 2, "State")

                # Step 3: City (level 3)
                city_id = insert_node(conn, city_name.strip(), state_id, 3, "City")

                # Step 4: Area (level 4)
                area_id = insert_node(conn, area_name.strip(), city_id, 4, "Area", postal_code=pincode)

                # Step 5: Add Postal Code mapping if available
                if pincode:
                    pcode_clean = str(pincode).strip()
                    try:
                        conn.execute(text("""
                            INSERT IGNORE INTO location_postal_codes (location_id, postal_code, area_name)
                            VALUES (:loc_id, :pcode, :area)
                        """), {"loc_id": area_id, "pcode": pcode_clean, "area": area_name.strip()})
                        conn.commit()
                    except Exception:
                        pass
            
            print("🎉 Sample data processed and structured!\n")

            # Print Visual Representation of Tree
            print("-------------------------------------------------------------")
            print("🌳 STRUCTURED LOCATION MASTER TREE REPRESENTATION:")
            print("-------------------------------------------------------------")
            
            # Print Country
            print(f"└── [Country] India")
            
            # Fetch states
            states = conn.execute(text("SELECT id, name FROM location_master WHERE parent_id = :pid AND location_type = 'State'"), {"pid": country_id}).fetchall()
            for s_idx, state in enumerate(states):
                s_branch = "├──" if s_idx < len(states) - 1 else "└──"
                print(f"    {s_branch} [State] {state.name}")
                
                # Fetch cities
                cities = conn.execute(text("SELECT id, name FROM location_master WHERE parent_id = :pid AND location_type = 'City'"), {"pid": state.id}).fetchall()
                for c_idx, city in enumerate(cities):
                    c_branch = "├──" if c_idx < len(cities) - 1 else "└──"
                    indent = "    │   " if s_idx < len(states) - 1 else "        "
                    print(f"{indent}{c_branch} [City] {city.name}")
                    
                    # Fetch areas (limit 5 for clean output)
                    areas = conn.execute(text("SELECT name, postal_code FROM location_master WHERE parent_id = :pid AND location_type = 'Area' LIMIT 5"), {"pid": city.id}).fetchall()
                    for a_idx, area in enumerate(areas):
                        a_branch = "├──" if a_idx < len(areas) - 1 else "└──"
                        indent_area = indent + ("│   " if c_idx < len(cities) - 1 else "    ")
                        pcode_str = f" ({area.postal_code})" if area.postal_code else ""
                        print(f"{indent_area}{a_branch} [Area] {area.name}{pcode_str}")
            
            print("\n=============================================================")
            print("Migration validation complete. Tables exist and structure is verified.")
            print("=============================================================")

if __name__ == "__main__":
    main()
