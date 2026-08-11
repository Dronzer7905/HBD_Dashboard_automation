import os
import sys
from dotenv import load_dotenv
from sqlalchemy import text

backend_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(backend_dir)
load_dotenv(os.path.join(backend_dir, '.env'))

from app import app
from extensions import db

def debug():
    print("=============================================================")
    print("🔍 DEEP DEBUGGING LOCATION MIGRATION PHASE 3 (AREAS)")
    print("=============================================================\n")

    with app.app_context():
        with db.engine.connect() as conn:
            # 1. Check raw table counts
            total_raw = conn.execute(text("SELECT COUNT(*) FROM Location_Master_India")).scalar()
            print(f"👉 Total rows in Location_Master_India: {total_raw:,}")
            
            non_null_areas = conn.execute(text("SELECT COUNT(*) FROM Location_Master_India WHERE area_name IS NOT NULL AND area_name != ''")).scalar()
            print(f"👉 Total rows with non-empty area_name: {non_null_areas:,}")
            
            # 2. Check if parent cities and states exist in location_master
            states_count = conn.execute(text("SELECT COUNT(*) FROM location_master WHERE location_level = 2")).scalar()
            cities_count = conn.execute(text("SELECT COUNT(*) FROM location_master WHERE location_level = 3")).scalar()
            areas_count = conn.execute(text("SELECT COUNT(*) FROM location_master WHERE location_level = 4")).scalar()
            print(f"👉 Existing location_master - States: {states_count}, Cities: {cities_count}, Areas: {areas_count}")
            
            # 3. Test Phase 3 query directly without joins
            print("\nExecuting simplified raw areas query...")
            q = text("""
                SELECT DISTINCT 
                    state_full_name AS sname, 
                    city_name AS cname, 
                    area_name AS aname
                FROM Location_Master_India
                WHERE state_full_name IS NOT NULL AND city_name IS NOT NULL AND area_name IS NOT NULL AND area_name != ''
                LIMIT 5
            """)
            rows = conn.execute(q).fetchall()
            print(f"👉 Simplified query (limit 5) returned: {len(rows)} rows.")
            for r in rows:
                print(f"  - State: '{r.sname}', City: '{r.cname}', Area: '{r.aname}'")

            # 4. Run Phase 3 count with join
            print("\nExecuting full Phase 3 join query count...")
            join_q = text("""
                SELECT COUNT(DISTINCT l.state_full_name, l.city_name, l.area_name)
                FROM Location_Master_India l
                LEFT JOIN (
                    SELECT city, area, MAX(pincode) as pincode
                    FROM master_table
                    WHERE pincode IS NOT NULL AND pincode != ''
                    GROUP BY city, area
                ) m ON l.city_name = m.city AND l.area_name = m.area
                WHERE l.state_full_name IS NOT NULL AND l.city_name IS NOT NULL AND l.area_name IS NOT NULL AND l.area_name != ''
            """)
            join_count = conn.execute(join_q).scalar() or 0
            print(f"👉 Full Phase 3 query returned: {join_count:,} rows.")

            # 5. Trace the first 10 rows of the Phase 3 loop to see where it gets skipped
            print("\nTracing first 10 rows of Phase 3 loop...")
            trace_q = text("""
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
                LIMIT 10
            """)
            trace_rows = conn.execute(trace_q).fetchall()
            
            # Load state and city caches exactly like the migration script does
            state_cache = {}
            states = conn.execute(text("SELECT id, name FROM location_master WHERE location_level = 2")).fetchall()
            for row in states:
                state_cache[row.name.strip().lower()] = row.id
                
            # Add state variations to cache (from location_aliases)
            aliases = conn.execute(text("""
                SELECT la.alias, la.location_id 
                FROM location_aliases la
                JOIN location_master lm ON la.location_id = lm.id
                WHERE lm.location_level = 2
            """)).fetchall()
            for row in aliases:
                state_cache[row.alias.strip().lower()] = row.location_id
                
            city_cache = {}
            cities = conn.execute(text("SELECT id, parent_id, name FROM location_master WHERE location_level = 3")).fetchall()
            for row in cities:
                city_cache[(row.parent_id, row.name.strip().lower())] = row.id
                
            print(f"Loaded {len(state_cache)} states/aliases and {len(city_cache)} cities for debug trace.")
            
            for idx, r in enumerate(trace_rows, 1):
                sname = r.sname.strip()
                cname = r.cname.strip()
                aname = r.aname.strip()
                
                s_id = state_cache.get(sname.lower())
                c_id = city_cache.get((s_id, cname.lower())) if s_id else None
                
                print(f"Row {idx}:")
                print(f"  Input State: '{sname}' -> cache key: '{sname.lower()}' -> s_id: {s_id}")
                print(f"  Input City:  '{cname}' -> cache key: ({s_id}, '{cname.lower()}') -> c_id: {c_id}")
                print(f"  Input Area:  '{aname}'")

if __name__ == "__main__":
    debug()
