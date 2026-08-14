"""
🧹 Utility Script to Truncate Hierarchical Location Tables
This cleans up duplicated States, Cities, and Areas from the location_master tree so you can run the corrected migration with a fresh slate.
"""
import os
import sys
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Load environment
backend_dir = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(backend_dir, '.env'))

db_host = os.getenv('DB_HOST', 'localhost')
db_user = os.getenv('DB_USER', 'root').strip()
db_password = os.getenv('DB_PASSWORD', '')
db_name = os.getenv('DB_NAME', 'default')
db_port = int(os.getenv('DB_PORT', '3306'))

url = f"mysql+pymysql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
engine = create_engine(url)

print("=============================================================")
print("🧹 TRUNCATING HIERARCHICAL LOCATION TABLES")
print("=============================================================")
print(f"Connecting to database: {db_name} on {db_host}...")

try:
    with engine.connect() as conn:
        print("\nDisabling foreign key checks...")
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 0;"))
        conn.commit()
        
        print("Truncating `location_postal_codes`...")
        conn.execute(text("TRUNCATE TABLE location_postal_codes;"))
        conn.commit()
        
        print("Truncating `location_aliases`...")
        conn.execute(text("TRUNCATE TABLE location_aliases;"))
        conn.commit()
        
        print("Truncating `location_master`...")
        conn.execute(text("TRUNCATE TABLE location_master;"))
        conn.commit()
        
        print("Re-enabling foreign key checks...")
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 1;"))
        conn.commit()
        
        print("\n✅ All hierarchical location tables truncated successfully!")
        print("You can now run `python migrate_locations_full.py` to rebuild a clean tree.")
        
except Exception as e:
    print(f"\n❌ Error during truncation: {e}")
    sys.exit(1)
