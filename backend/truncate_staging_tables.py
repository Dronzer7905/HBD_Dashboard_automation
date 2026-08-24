import os
import sys
import argparse
from dotenv import load_dotenv

# Ensure we are in backend dir context
backend_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(backend_dir)
os.chdir(backend_dir)

load_dotenv('.env')

from app import app
from extensions import db
from sqlalchemy import text

# List of staging/raw tables that can be safely truncated
STAGING_TABLES = [
    "asklaila",
    "google_map_scrape",
    "justdial",
    "magicpin",
    "heyplaces",
    "pinda",
    "nearbuy",
    "schoolgis",
    "shiksha",
    "yellow_pages",
    "raw_google_map_drive_data",
    "atm",
    "college_dunia",
    "freelisting",
    "post_office",
    "vivo"
]

def main():
    parser = argparse.ArgumentParser(description="Safely truncate raw staging tables after master integration.")
    parser.add_argument("--confirm", action="store_true", help="Actually execute the TRUNCATE queries. Default is dry-run.")
    args = parser.parse_args()

    print("=============================================================")
    print("[CLEANUP] RAW STAGING TABLES CLEANUP UTILITY")
    print(f"Mode: {'EXECUTE (TRUNCATE)' if args.confirm else 'DRY-RUN (REPORT ONLY)'}")
    print("=============================================================\n")

    with app.app_context():
        total_space_saved_approx = 0
        for table in STAGING_TABLES:
            try:
                # Get current row count
                count = db.session.execute(text(f"SELECT COUNT(*) FROM `{table}`")).scalar()
                
                # Check approximate table size from information_schema to show space savings
                db_name = os.getenv('LIVE_DB_NAME') or os.getenv('DB_NAME')
                size_res = db.session.execute(text("""
                    SELECT (data_length + index_length) / 1024 / 1024 AS size_mb 
                    FROM information_schema.tables 
                    WHERE table_schema = :db AND table_name = :tbl
                """), {"db": db_name, "tbl": table}).fetchone()
                
                size_mb = round(size_res[0], 2) if size_res and size_res[0] else 0.0
                total_space_saved_approx += size_mb

                print(f"[TABLE] {table:<30} | Rows: {count:>10,} | Size: {size_mb:>8.2f} MB")
                
                if args.confirm:
                    if count > 0:
                        db.session.execute(text(f"TRUNCATE TABLE `{table}`"))
                        db.session.commit()
                        print(f"   ↳ [SUCCESS] Successfully truncated `{table}` (0 rows now).")
                    else:
                        print("   ↳ [SKIPPED] Table is already empty. Skipped.")
            except Exception as e:
                print(f"   ↳ [ERROR] Error checking/truncating table `{table}`: {e}")
                db.session.rollback()

        print("\n=============================================================")
        print(f"Estimated Disk Space to Recover: {total_space_saved_approx:.2f} MB")
        if not args.confirm:
            print("\n* To actually execute this truncation on the server, run:")
            print("   python truncate_staging_tables.py --confirm")
        print("=============================================================")

if __name__ == "__main__":
    main()
