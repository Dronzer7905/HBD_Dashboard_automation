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

        backup_table = "master_table_backup_20260729_133150"
        
        # 1. Get min and max ID to run chunked query
        print(f"Analyzing snapshot '{backup_table}'...")
        limits_query = text(f"SELECT MIN(id), MAX(id), COUNT(*) FROM {backup_table}")
        res = db.session.execute(limits_query).fetchone()
        
        min_id, max_id, total_rows = res[0], res[1], res[2]
        
        if total_rows == 0 or min_id is None:
            print("❌ Error: The backup table appears to be empty.")
            return

        print(f"👉 Total Rows to Restore: {total_rows:,}")
        print(f"👉 Range of IDs:         {min_id:,} to {max_id:,}\n")

        # 2. Confirm truncate of the empty/dirty master_table
        print("Clearing target 'master_table' before restoring...")
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
