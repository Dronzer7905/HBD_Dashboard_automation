import os
import sys
from dotenv import load_dotenv

# Ensure we are in backend dir context
backend_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(backend_dir)
os.chdir(backend_dir)

load_dotenv('.env')

from app import app
from extensions import db
from sqlalchemy import text

def main():
    print("=============================================================")
    print("[LOCATION] AUTO-POPULATING LOCATION MASTER INDIA FROM MASTER TABLE")
    print("=============================================================\n")

    with app.app_context():
        # 1. Fetch unique (city, area) from master_table not in Location_Master_India
        unmatched_query = text("""
            SELECT DISTINCT m.city, m.area 
            FROM master_table m
            LEFT JOIN Location_Master_India l 
              ON l.city_name = m.city AND l.area_name = m.area
            WHERE m.city IS NOT NULL 
              AND m.area IS NOT NULL
              AND l.id IS NULL
        """)
        print("Fetching unmatched city/area combinations from master_table...")
        unmatched_pairs = db.session.execute(unmatched_query).fetchall()
        print(f"Found {len(unmatched_pairs):,} unique unmatched combinations.\n")

        if not unmatched_pairs:
            print("No unmatched locations found. Location_Master_India is fully populated.")
            return

        # 2. Fetch existing city-to-state mappings from Location_Master_India to use as reference
        print("Caching existing city-to-state mappings from Location_Master_India...")
        city_ref_query = text("""
            SELECT DISTINCT city_name, state_full_name, state_short_code, country_name 
            FROM Location_Master_India 
            WHERE city_name IS NOT NULL AND state_full_name IS NOT NULL
        """)
        city_refs = db.session.execute(city_ref_query).fetchall()
        
        city_map = {}
        for r in city_refs:
            city_map[r[0].lower().strip()] = {
                "state_full_name": r[1],
                "state_short_code": r[2],
                "country_name": r[3] or "India"
            }
        print(f"Cached state reference for {len(city_map):,} unique cities.\n")

        # Dictionary of fallback mappings for common Indian cities
        fallback_cities = {
            "jodhpur": {"state_full_name": "Rajasthan", "state_short_code": "RJ", "country_name": "India"},
            "lucknow": {"state_full_name": "Uttar Pradesh", "state_short_code": "UP", "country_name": "India"},
            "gurgaon": {"state_full_name": "Haryana", "state_short_code": "HR", "country_name": "India"},
            "coimbatore": {"state_full_name": "Tamil Nadu", "state_short_code": "TN", "country_name": "India"},
            "nagpur": {"state_full_name": "Maharashtra", "state_short_code": "MH", "country_name": "India"},
            "thane": {"state_full_name": "Maharashtra", "state_short_code": "MH", "country_name": "India"},
            "pune": {"state_full_name": "Maharashtra", "state_short_code": "MH", "country_name": "India"},
            "bangalore": {"state_full_name": "Karnataka", "state_short_code": "KA", "country_name": "India"},
            "dhanbad": {"state_full_name": "Jharkhand", "state_short_code": "JH", "country_name": "India"},
            "bhopal": {"state_full_name": "Madhya Pradesh", "state_short_code": "MP", "country_name": "India"},
            "jhansi": {"state_full_name": "Uttar Pradesh", "state_short_code": "UP", "country_name": "India"},
            "kanpur": {"state_full_name": "Uttar Pradesh", "state_short_code": "UP", "country_name": "India"},
            "guwahati": {"state_full_name": "Assam", "state_short_code": "AS", "country_name": "India"},
            "jamshedpur": {"state_full_name": "Jharkhand", "state_short_code": "JH", "country_name": "India"},
            "amritsar": {"state_full_name": "Punjab", "state_short_code": "PB", "country_name": "India"},
            "ahmedabad": {"state_full_name": "Gujarat", "state_short_code": "GJ", "country_name": "India"},
            "varanasi": {"state_full_name": "Uttar Pradesh", "state_short_code": "UP", "country_name": "India"}
        }

        # 3. Process and insert the new locations
        inserted_count = 0
        skipped_count = 0
        batch_size = 500
        
        insert_query = text("""
            INSERT INTO Location_Master_India (area_name, city_name, state_full_name, state_short_code, country_name) 
            VALUES (:area, :city, :state, :state_short, :country)
        """)

        for i, pair in enumerate(unmatched_pairs):
            city_name = pair[0]
            area_name = pair[1]
            city_key = city_name.lower().strip()

            # Clean area name a bit (remove trailing city/state substrings if present, e.g. ", Ahmedabad")
            clean_area = area_name.split(",")[0].strip()

            # Skip obviously messy building numbers/addresses if they are too long or contain symbols that don't belong in area names
            if len(clean_area) > 100 or "floor" in clean_area.lower() or "road" in clean_area.lower() or "street" in clean_area.lower():
                skipped_count += 1
                continue

            state_info = city_map.get(city_key) or fallback_cities.get(city_key)
            if state_info:
                try:
                    db.session.execute(insert_query, {
                        "area": clean_area,
                        "city": city_name.strip(),
                        "state": state_info["state_full_name"],
                        "state_short": state_info["state_short_code"],
                        "country": state_info["country_name"]
                    })
                    inserted_count += 1
                    
                    if inserted_count % batch_size == 0:
                        db.session.commit()
                        print(f"Inserted {inserted_count:,} location records...")
                except Exception as e:
                    print(f"Error inserting {clean_area}, {city_name}: {e}")
                    db.session.rollback()
            else:
                skipped_count += 1

        db.session.commit()
        print(f"\n=============================================================")
        print(f"SUCCESS: Auto-population completed!")
        print(f"Total New Locations Added: {inserted_count:,}")
        print(f"Total Rows Skipped (Messy addresses/unknown states): {skipped_count:,}")
        print("=============================================================")

if __name__ == "__main__":
    main()
