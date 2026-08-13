import os
import sys
from dotenv import load_dotenv
from sqlalchemy import text

backend_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(backend_dir)
load_dotenv(os.path.join(backend_dir, '.env'))

from app import app
from extensions import db

def main():
    print("=============================================================")
    print("🔍 CHECKING DATABASE GEOGRAPHY SCHEMAS & COUNTS")
    print("=============================================================\n")

    with app.app_context():
        with db.engine.connect() as conn:
            # 1. Row counts in location_master
            print("1. Table Row Counts in location_master:")
            for lvl, name in [(1, 'Country'), (2, 'State'), (3, 'City'), (4, 'Area'), (5, 'Locality'), (6, 'Street'), (7, 'Building')]:
                cnt = conn.execute(text("SELECT COUNT(*) FROM location_master WHERE location_level = :lvl"), {"lvl": lvl}).scalar()
                print(f"   Level {lvl} ({name}): {cnt:,} nodes")
            
            postal_cnt = conn.execute(text("SELECT COUNT(*) FROM location_postal_codes")).scalar() or 0
            alias_cnt = conn.execute(text("SELECT COUNT(*) FROM location_aliases")).scalar() or 0
            print(f"   location_postal_codes: {postal_cnt:,} rows")
            print(f"   location_aliases:      {alias_cnt:,} rows\n")

            # 2. Check structure of location_master city records
            print("2. Sample City records from location_master:")
            cities = conn.execute(text("SELECT id, parent_id, name, slug FROM location_master WHERE location_level = 3 LIMIT 5")).fetchall()
            for c in cities:
                print(f"   ID: {c.id}, Parent ID (State): {c.parent_id}, Name: '{c.name}', Slug: '{c.slug}'")
            print("")

            # 3. Cache structures for analysis
            state_cache = {}
            states = conn.execute(text("SELECT id, name FROM location_master WHERE location_level = 2")).fetchall()
            for row in states:
                state_cache[row.name.strip().lower()] = row.id
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

            # 4. Read sample records from Location_Master_India and show lookup results
            print("3. Trace lookup process for sample areas:")
            cols_res = conn.execute(text("SHOW COLUMNS FROM Location_Master_India")).fetchall()
            available_cols = {r[0].lower() for r in cols_res}
            
            use_legacy = 'area' in available_cols and 'city' in available_cols and 'state' in available_cols
            if use_legacy:
                q = text("""
                    SELECT DISTINCT state AS sname, city AS cname, area AS aname 
                    FROM Location_Master_India 
                    WHERE state IS NOT NULL AND city IS NOT NULL AND area IS NOT NULL AND area != ''
                    LIMIT 5
                """)
            else:
                q = text("""
                    SELECT DISTINCT state_full_name AS sname, city_name AS cname, area_name AS aname 
                    FROM Location_Master_India 
                    WHERE state_full_name IS NOT NULL AND city_name IS NOT NULL AND area_name IS NOT NULL AND area_name != ''
                    LIMIT 5
                """)
            
            rows = conn.execute(q).fetchall()
            for idx, r in enumerate(rows, 1):
                sname = r.sname.strip()
                cname = r.cname.strip()
                aname = r.aname.strip()
                
                s_id = state_cache.get(sname.lower())
                c_id = city_cache.get((s_id, cname.lower())) if s_id else None
                
                print(f"   Record {idx}: State='{sname}', City='{cname}', Area='{aname}'")
                print(f"     -> Lower State Key: '{sname.lower()}' -> State ID found: {s_id}")
                if s_id:
                    print(f"     -> City Cache Key: ({s_id}, '{cname.lower()}') -> City ID found: {c_id}")
                else:
                    print(f"     -> City Lookup skipped because State ID is None")

if __name__ == "__main__":
    main()
