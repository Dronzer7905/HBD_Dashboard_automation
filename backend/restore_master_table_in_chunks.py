import os
import sys
import time
from sqlalchemy import text
from dotenv import load_dotenv

# Ensure we are in backend context
backend_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(backend_dir)
load_dotenv(os.path.join(backend_dir, '.env'))

from app import app
from extensions import db

def main():
    print("=============================================================")
    print("🔄 SAFE RESTORE IN CHUNKS: MASTER_TABLE SNAPSHOT RESTORATION")
    print("=============================================================\n")

    with app.app_context():
        # Adjust PyMySQL connection read timeout dynamically to 300 seconds to be safe
        try:
            db.session.connection().connection.read_timeout = 300
        except Exception:
            pass

        # Prompt or accept backup table name from CLI
        if len(sys.argv) > 1:
            backup_table = sys.argv[1].strip()
        else:
            backup_table = input("Enter backup table name to restore from: ").strip()

        if not backup_table:
            print("❌ Error: No backup table name provided.")
            return

        # Verify backup table exists
        exists_query = text("""
            SELECT COUNT(*) 
            FROM information_schema.TABLES 
            WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :tname
        """)
        if db.session.execute(exists_query, {"tname": backup_table}).scalar() == 0:
            print(f"❌ Error: Backup table '{backup_table}' does not exist in the database.")
            return
        
        # Check if there are active rows in master_table missing from the backup
        print(f"Checking for any records in 'master_table' missing from '{backup_table}'...")
        try:
            check_sql = text(f"""
                SELECT COUNT(1) 
                FROM master_table m
                LEFT JOIN {backup_table} b ON m.global_business_id = b.global_business_id
                WHERE b.global_business_id IS NULL
            """)
            missing_count = db.session.execute(check_sql).scalar() or 0
            if missing_count > 0:
                print(f"⚠️ Warning: Found {missing_count:,} records in 'master_table' that are missing in backup!")
                confirm = input("Would you like to copy these missing records into the backup before restoring? (yes/no): ").strip().lower()
                if confirm in ('yes', 'y'):
                    print("Copying missing records to backup table...")
                    merge_sql = text(f"""
                        INSERT INTO {backup_table}
                        SELECT m.*
                        FROM master_table m
                        LEFT JOIN {backup_table} b ON m.global_business_id = b.global_business_id
                        WHERE b.global_business_id IS NULL
                    """)
                    db.session.execute(merge_sql)
                    db.session.commit()
                    print("✅ Backup table successfully updated with missing records.")
                else:
                    print("⚠️ Proceeding without saving active records. Those records will be deleted from master_table!")
        except Exception as check_err:
            print(f"⚠️ Warning: Could not perform safety checks (skipping): {check_err}")

        # 1. Get min and max ID to run chunked query
        print(f"\nAnalyzing snapshot '{backup_table}'...")
        limits_query = text(f"SELECT MIN(id), MAX(id), COUNT(*) FROM {backup_table}")
        res = db.session.execute(limits_query).fetchone()
        
        min_id, max_id, total_rows = res[0], res[1], res[2]
        
        if total_rows == 0 or min_id is None:
            print("❌ Error: The backup table appears to be empty.")
            return

        print(f"👉 Total Rows to Restore: {total_rows:,}")
        print(f"👉 Range of IDs:         {min_id:,} to {max_id:,}\n")

        # 2. Confirm truncate of the empty/dirty master_table
        confirm_trunc = input(f"Are you sure you want to TRUNCATE 'master_table' and restore from '{backup_table}'? (yes/no): ").strip().lower()
        if confirm_trunc not in ('yes', 'y'):
            print("❌ Restoration aborted by user.")
            return

        print("\nClearing target 'master_table' before restoring...")
        db.session.execute(text("TRUNCATE TABLE master_table;"))
        db.session.commit()
        print("✅ Target 'master_table' truncated.\n")

        # 3. Restore in chunks of 500,000
        chunk_size = 500000
        total_restored = 0
        t_start = time.time()

        for start_id in range(min_id, max_id + 1, chunk_size):
            end_id = start_id + chunk_size
            
            insert_query = text(f"""
                INSERT INTO master_table 
                SELECT * FROM {backup_table} 
                WHERE id >= :start AND id < :end
            """)
            
            try:
                r = db.session.execute(insert_query, {"start": start_id, "end": end_id})
                db.session.commit()
                total_restored += r.rowcount
                print(f"🔹 Synced chunk ID {start_id:,} to {end_id:,} | Restored: {total_restored:,} of {total_rows:,} rows...")
            except Exception as e:
                print(f"❌ Error restoring chunk {start_id} to {end_id}: {e}")
                db.session.rollback()
                return

        t_end = time.time()
        print(f"\n=============================================================")
        print(f"🎉 SUCCESS: Restoration Complete in {t_end - t_start:.2f} seconds!")
        print(f"Total Restored Rows: {total_restored:,}")
        print(f"=============================================================")

if __name__ == "__main__":
    main()
