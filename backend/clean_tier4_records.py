import sys
import time
import re
sys.path.append(r'C:\Desktop\HBD_Dashboard_automation\backend')

from database.session import SessionLocal
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

BATCH_SIZE = 5000

def main():
    db = SessionLocal()
    
    # 1. Add column if it doesn't exist
    try:
        db.execute(text("ALTER TABLE item_data ADD COLUMN data_quality VARCHAR(30) NULL"))
        db.commit()
        print("Added data_quality column.")
    except Exception as e:
        db.rollback()
        print(f"Column data_quality might already exist (skipping creation).")
    
    total_unusable = 0
    total_recoverable = 0
    batch_num = 0
    
    print("Starting Tier 4 cleaning...")
    
    while True:
        try:
            # Fetch batch where data_quality is NULL to allow resuming
            query = text(f"SELECT ID, name FROM item_data WHERE assigned_tier = 'tier4_partial_fragments' AND data_quality IS NULL LIMIT {BATCH_SIZE}")
            rows = db.execute(query).fetchall()
            
            if not rows:
                break
                
            updates = []
            for row in rows:
                row_id = row[0]
                name = str(row[1] or '').strip()
                
                # Check if empty or has no alphabetic characters
                if not name or re.match(r'^[^a-zA-Z]*$', name):
                    quality = 'unusable'
                    total_unusable += 1
                else:
                    quality = 'incomplete_recoverable'
                    total_recoverable += 1
                    
                updates.append({'q': quality, 'id': row_id})
                
        except Exception as e:
            print(f"Error fetching rows: {e}. Reconnecting...", flush=True)
            db.close()
            time.sleep(5)
            db = SessionLocal()
            continue
            
        # Update batch with retry
        retries = 0
        success = False
        while retries < 3 and not success:
            try:
                update_query = text("UPDATE item_data SET data_quality = :q WHERE ID = :id")
                db.execute(update_query, updates)
                db.commit()
                batch_num += 1
                success = True
                
                if batch_num % 20 == 0:
                    print(f"Batch {batch_num}: Processed {batch_num * BATCH_SIZE} rows. Unusable: {total_unusable}, Recoverable: {total_recoverable}", flush=True)
                    
            except OperationalError as e:
                retries += 1
                print(f"OperationalError during batch {batch_num + 1} (attempt {retries}/3): {e}. Rolling back and retrying...", flush=True)
                db.rollback()
                time.sleep(5)
                db.close()
                db = SessionLocal()
            except Exception as e:
                print(f"Non-Operational error during batch {batch_num + 1}: {e}. Skipping batch...", flush=True)
                db.rollback()
                db.close()
                db = SessionLocal()
                break
                
        if not success and retries >= 3:
            print(f"Batch {batch_num + 1} failed after 3 OperationalError retries.", flush=True)
            # Break to avoid infinite loop if we can't update these rows
            break
            
    print("-" * 40)
    print(f"DONE. Final Summary:")
    print(f"Total unusable: {total_unusable}")
    print(f"Total incomplete_recoverable: {total_recoverable}")
    
    db.close()

if __name__ == '__main__':
    main()
