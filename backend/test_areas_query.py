import os
import sys
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Load backend .env
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
print("🔍 DIAGNOSING SOURCE SCHEMA AND AREA COUNTS")
print("=============================================================\n")

try:
    with engine.connect() as conn:
        # 1. Show columns of Location_Master_India
        print("1. Columns in Location_Master_India:")
        cols_res = conn.execute(text("SHOW COLUMNS FROM Location_Master_India")).fetchall()
        for c in cols_res:
            print(f"   - {c[0]} ({c[1]})")
        print("")
        
        # 2. Count total rows
        total_rows = conn.execute(text("SELECT COUNT(*) FROM Location_Master_India")).scalar()
        print(f"2. Total rows in Location_Master_India: {total_rows:,}")
        
        # 3. Check counts of non-null and non-empty columns
        print("\n3. Column Population Counts:")
        for col in ['state', 'city', 'area', 'state_full_name', 'city_name', 'area_name']:
            col_exists = any(c[0].lower() == col.lower() for c in cols_res)
            if col_exists:
                cnt = conn.execute(text(f"SELECT COUNT(*) FROM Location_Master_India WHERE `{col}` IS NOT NULL AND `{col}` != ''")).scalar()
                print(f"   - `{col}` is populated in: {cnt:,} rows")
            else:
                print(f"   - `{col}` does NOT exist in table")
                
        # 4. Check location_master counts
        print("\n4. Counts in location_master:")
        for lvl, name in [(1, 'Country'), (2, 'State'), (3, 'City'), (4, 'Area')]:
            cnt = conn.execute(text("SELECT COUNT(*) FROM location_master WHERE location_level = :lvl"), {"lvl": lvl}).scalar()
            print(f"   - Level {lvl} ({name}): {cnt:,} nodes")
            
except Exception as e:
    print(f"❌ Error during diagnostics: {e}")
