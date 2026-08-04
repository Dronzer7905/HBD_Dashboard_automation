import time
from app import app
from database.session import SessionLocal
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from services.dynamic_cleaning_service import clean_and_route_batch

db = SessionLocal()
total_processed = 0
batch_num = 0
BATCH_SIZE = 1000

with app.app_context():
    while True:
        try:
            query = text(f"SELECT ID, name, phone_no_1, phone_no_2, phone_no_3, whatsapp_no, email, address, city, state, pincode FROM item_data WHERE cleaning_status IS NULL OR cleaning_status = 'PENDING' LIMIT {BATCH_SIZE}")
            rows = db.execute(query).fetchall()
            if not rows:
                break
            records = [{
                'id': r[0],
                'name': str(r[1] or ''),
                'phone': str(r[2] or ''),
                'phone_no_2': str(r[3] or ''),
                'phone_no_3': str(r[4] or ''),
                'whatsapp_no': str(r[5] or ''),
                'email': str(r[6] or ''),
                'address': str(r[7] or ''),
                'city': str(r[8] or ''),
                'state': str(r[9] or ''),
                'pincode': str(r[10] or '')
            } for r in rows]
        except Exception as e:
            print(f"Error fetching rows: {e}. Reconnecting...", flush=True)
            db.close()
            time.sleep(5)
            db = SessionLocal()
            continue

        retries = 0
        success = False
        while retries < 3 and not success:
            try:
                result = clean_and_route_batch('item_data', records)
                total_processed += result
                batch_num += 1
                success = True
                
                if batch_num % 20 == 0:
                    print(f"Batch {batch_num}: processed {result} rows in this batch, total so far: {total_processed}", flush=True)
                
                time.sleep(0.2)
            except OperationalError as e:
                retries += 1
                print(f"OperationalError during batch {batch_num + 1} (attempt {retries}/3): {e}. Rolling back and retrying in 5 seconds...", flush=True)
                db.rollback()
                time.sleep(5)
                # Ensure the local db session is also reset if needed
                db.close()
                db = SessionLocal()
            except Exception as e:
                print(f"Non-Operational error during batch {batch_num + 1}: {e}. Skipping batch...", flush=True)
                db.rollback()
                db.close()
                db = SessionLocal()
                break
                
        if not success and retries >= 3:
            print(f"Batch {batch_num + 1} failed after 3 OperationalError retries. Moving on...", flush=True)
            
        # VERY IMPORTANT: Commit the local read session to end the transaction.
        # Otherwise, MySQL's REPEATABLE READ isolation level will cause the next SELECT
        # to see the same 'PENDING' rows over and over again, creating an infinite loop.
        db.commit()

print(f"DONE. Total processed: {total_processed}")
db.close()
