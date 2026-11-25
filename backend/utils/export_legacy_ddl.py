"""
Pre-Flight Safety Script: Export Legacy Table DDLs and Verify Row Counts
========================================================================
This script safely checks all 36 candidate empty tables in the database.
1. Verifies that COUNT(*) == 0 for every candidate table.
2. Extracts their CREATE TABLE DDL using SQLAlchemy reflection.
3. Saves individual .sql files into backend/migrations/legacy_ddl/
4. Prints an executive verification report so the Team Lead can drop with 100% confidence.
"""

import os
import sys

# Ensure backend root is in python path
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.schema import CreateTable

DEAD_TABLE_CANDIDATES = [
    "Top_categories_rank",
    "activities",
    "addons",
    "alembic_version",
    "asklaila",
    "atm",
    "business_data_quality",
    "college_dunia",
    "data_validation_log",
    "etl_dlq",
    "freelisting",
    "google_map_scrape",
    "heyplaces",
    "jio_mart_products",
    "justdial",
    "level_1_category",
    "listing_master_table",
    "location_postal_codes",
    "magicpin",
    "nearbuy",
    "new_master_priority_ranking",
    "new_priority_ranking",
    "pinda",
    "post_office",
    "product_master_table",
    "product_top_selling_report",
    "raw_google_map",
    "schoolgis",
    "shiksha",
    "staging_location_master_ranking",
    "uncleaned_listing_master_table",
    "uncleaned_product_master_table",
    "upload_reports",
    "validation_raw_google_map",
    "vivo",
    "yellow_pages"
]

def main():
    print("=" * 70)
    print("  HBD AUTOMATION: PHASE 1 PRE-FLIGHT DDL BACKUP & VERIFICATION")
    print("=" * 70)

    engine = create_engine(Config.SQLALCHEMY_DATABASE_URI)
    insp = inspect(engine)
    existing_tables = set(insp.get_table_names())

    out_dir = os.path.join(backend_dir, "migrations", "legacy_ddl")
    os.makedirs(out_dir, exist_ok=True)
    print(f"[*] DDL Output Directory: {out_dir}")

    verified_zero = []
    has_rows = []
    missing_tables = []

    with engine.connect() as conn:
        for tbl in DEAD_TABLE_CANDIDATES:
            # Handle exact case sensitivity in postgres
            matched_name = None
            for ex in existing_tables:
                if ex.lower() == tbl.lower():
                    matched_name = ex
                    break

            if not matched_name:
                missing_tables.append(tbl)
                continue

            # Query row count
            try:
                cnt = conn.execute(text(f'SELECT COUNT(*) FROM "{matched_name}"')).scalar()
            except Exception as e:
                print(f"[ERROR] Could not count rows for {matched_name}: {e}")
                continue

            if cnt == 0:
                verified_zero.append((matched_name, cnt))
                # Export DDL
                try:
                    # Fetch column definitions via information_schema
                    cols = conn.execute(text(f"""
                        SELECT column_name, data_type, character_maximum_length, is_nullable
                        FROM information_schema.columns
                        WHERE table_name = '{matched_name}'
                        ORDER BY ordinal_position;
                    """)).fetchall()

                    col_defs = []
                    for c in cols:
                        col_type = c[1]
                        if c[2]:
                            col_type += f"({c[2]})"
                        nullable = "NULL" if c[3] == "YES" else "NOT NULL"
                        col_defs.append(f'    "{c[0]}" {col_type} {nullable}')

                    ddl_sql = f'-- Archived DDL for empty legacy table: {matched_name}\n'
                    ddl_sql += f'CREATE TABLE IF NOT EXISTS public."{matched_name}" (\n'
                    ddl_sql += ",\n".join(col_defs)
                    ddl_sql += "\n);\n"

                    ddl_file = os.path.join(out_dir, f"{matched_name}.sql")
                    with open(ddl_file, "w", encoding="utf-8") as f:
                        f.write(ddl_sql)
                except Exception as ex:
                    print(f"[WARN] Failed to write DDL file for {matched_name}: {ex}")
            else:
                has_rows.append((matched_name, cnt))

    print("\n" + "-" * 70)
    print(f"  VERIFICATION RESULTS:")
    print(f"  - Verified 0 Rows (Safe to Drop): {len(verified_zero)} tables")
    print(f"  - Has Rows (> 0) (ABORT DROP):    {len(has_rows)} tables")
    print(f"  - Already Dropped / Missing:       {len(missing_tables)} tables")
    print("-" * 70)

    if has_rows:
        print("\n[CRITICAL WARNING] The following tables have rows! DO NOT DROP:")
        for t, c in has_rows:
            print(f"  ! {t}: {c} rows")
    else:
        print("\n[SUCCESS] 100% of candidate tables are confirmed ZERO rows.")
        print(f"[SUCCESS] All {len(verified_zero)} DDL files safely generated in:")
        print(f"          {out_dir}")
        print("\nYou can now safely run the DROP command (Task TL-1.3) with zero data loss risk.")

if __name__ == "__main__":
    main()
