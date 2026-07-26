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
    "atm",
    "college_dunia",
    "freelisting",
    "post_office"
]

def main():
    print("=============================================================")
    print("[VERIFY] STAGING SYNCHRONIZATION AUDIT REPORT")
    print("Checking if raw rows are fully processed and moved to tiers...")
    print("=============================================================\n")

    with app.app_context():
        for table in STAGING_TABLES:
            try:
                # 1. Get raw row count
                total_raw = db.session.execute(text(f"SELECT COUNT(*) FROM `{table}`")).scalar() or 0
                if total_raw == 0:
                    print(f"[OK] {table:<25} | Rows: 0 (Already empty or clean)")
                    continue
                
                # 2. Count rows not mapped in any of the active tiers
                unmapped_query = text(f"""
                    SELECT COUNT(*) 
                    FROM `{table}` 
                    WHERE id NOT IN (
                        SELECT raw_source_id FROM tier1_master_clean WHERE raw_source_table = :tbl AND raw_source_id IS NOT NULL
                        UNION ALL
                        SELECT raw_source_id FROM tier2_missing_contact WHERE raw_source_table = :tbl AND raw_source_id IS NOT NULL
                        UNION ALL
                        SELECT raw_source_id FROM tier3_missing_location WHERE raw_source_table = :tbl AND raw_source_id IS NOT NULL
                        UNION ALL
                        SELECT raw_source_id FROM tier4_partial_fragments WHERE raw_source_table = :tbl AND raw_source_id IS NOT NULL
                        UNION ALL
                        SELECT raw_source_id FROM tier5_linked_duplicates WHERE raw_source_table = :tbl AND raw_source_id IS NOT NULL
                    )
                """)
                unmapped_count = db.session.execute(unmapped_query, {"tbl": table}).scalar() or 0
                
                if unmapped_count == 0:
                    print(f"[OK] {table:<25} | Total: {total_raw:>9,} | Unsynced: {unmapped_count:>9,} (100% Synced - SAFE to truncate!)")
                else:
                    percent_synced = round(((total_raw - unmapped_count) / total_raw) * 100, 2)
                    print(f"[WARN] {table:<25} | Total: {total_raw:>9,} | Unsynced: {unmapped_count:>9,} ({percent_synced}% Synced - NOT safe to truncate!)")
            except Exception as e:
                print(f"[ERROR] {table:<25} | Error running audit: {e}")

if __name__ == "__main__":
    main()
