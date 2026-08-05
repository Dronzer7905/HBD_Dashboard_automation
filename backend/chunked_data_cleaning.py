import os
import sys
import time
import argparse
from dotenv import load_dotenv

import pymysql
from pymysql.cursors import DictCursor

def load_db_connection():
    """Securely load DB connections purely via environment variables."""
    # Load .env variables
    load_dotenv('.env')
    
    db_host = os.getenv("DB_HOST")
    db_port = int(os.getenv("DB_PORT", 3306))
    db_user = os.getenv("DB_USER")
    db_password = os.getenv("DB_PASSWORD")
    db_name = os.getenv("DB_NAME")
    
    if not all([db_host, db_user, db_name]):
        print("❌ Error: Missing required .env variables for DB connection.")
        sys.exit(1)
        
    return pymysql.connect(
        host=db_host,
        port=db_port,
        user=db_user,
        password=db_password,
        database=db_name,
        cursorclass=DictCursor,
        autocommit=False  # We will manually commit after each chunk if applying
    )

def main():
    parser = argparse.ArgumentParser(description="Chunk-wise Data Cleaning Script for master_table")
    parser.add_argument("--apply", action="store_true", 
                        help="Apply changes to the database. By default, it runs in dry-run mode.")
    parser.add_argument("--chunk-size", type=int, default=5000,
                        help="Number of rows to process per batch (default: 5000).")
    parser.add_argument("--delay", type=float, default=0.5,
                        help="Delay in seconds between chunks to prevent server overload (default: 0.5s).")
    args = parser.parse_args()

    run_type = "APPLY" if args.apply else "DRY-RUN"
    chunk_size = args.chunk_size
    delay = args.delay
    
    print(f"============================================================")
    print(f"STARTING DATA CLEANING RUN")
    print(f"Target Table: master_table")
    print(f"Run Mode:     {run_type}")
    print(f"Chunk Size:   {chunk_size}")
    print(f"============================================================")

    try:
        conn = load_db_connection()
    except Exception as e:
        print(f"❌ Failed to connect to database: {e}")
        sys.exit(1)
    
    # Metrics
    total_rows_checked = 0
    standardized_rows = 0
    duplicates_found = 0
    
    last_id = 0
    processed_duplicate_keys = set()
    
    try:
        with conn.cursor() as cursor:
            while True:
                # 1. Fetch chunk using cursor-based pagination
                cursor.execute("""
                    SELECT id, business_name, primary_phone, email, address, city, state, pincode 
                    FROM master_table 
                    WHERE id > %s 
                    ORDER BY id ASC 
                    LIMIT %s
                """, (last_id, chunk_size))
                
                rows = cursor.fetchall()
                if not rows:
                    break
                
                chunk_len = len(rows)
                total_rows_checked += chunk_len
                
                # Progress logging
                start_row = total_rows_checked - chunk_len + 1
                print(f"[INFO] Processed chunk: Rows {start_row:,} to {total_rows_checked:,} (last_id: {last_id})")
                
                batch_updates = []
                
                for row in rows:
                    row_id = row['id']
                    last_id = row_id  # Update last_id for the next chunk's pagination
                    
                    b_name = row['business_name']
                    phone = row['primary_phone']
                    address = row['address']
                    
                    # 2. Standardization / Cleaning Logic
                    # Trim spaces and handle empty strings
                    clean_b_name = b_name.strip() if b_name else None
                    clean_phone = phone.strip() if phone else None
                    clean_addr = address.strip() if address else None
                    
                    is_standardized = False
                    if clean_b_name != b_name or clean_phone != phone or clean_addr != address:
                        is_standardized = True
                        standardized_rows += 1
                        batch_updates.append({
                            'id': row_id,
                            'business_name': clean_b_name,
                            'primary_phone': clean_phone,
                            'address': clean_addr
                        })
                        
                    # 3. Duplication Check
                    # Create a composite key to check for duplicates
                    dupe_key = f"{clean_b_name or ''}_{clean_phone or ''}_{clean_addr or ''}".lower().replace(' ', '')
                    if dupe_key and (clean_b_name or clean_phone or clean_addr):
                        if dupe_key in processed_duplicate_keys:
                            duplicates_found += 1
                        else:
                            processed_duplicate_keys.add(dupe_key)
                
                # 4. Apply Database Changes (if not dry run)
                if args.apply and batch_updates:
                    update_sql = """
                        UPDATE master_table 
                        SET business_name = %(business_name)s, 
                            primary_phone = %(primary_phone)s, 
                            address = %(address)s 
                        WHERE id = %(id)s
                    """
                    cursor.executemany(update_sql, batch_updates)
                    conn.commit()
                
                # 5. Delay to prevent server overload
                time.sleep(delay)
                
    except Exception as e:
        print(f"\n❌ Pipeline run failed with error: {e}")
        if args.apply:
            conn.rollback()
    finally:
        conn.close()

    # Final Summary Log (Preserved format)
    print(f"\n=================== RUN RESULTS SUMMARY ===================")
    print(f"Status:             COMPLETED ({run_type})")
    print(f"Total Rows Checked: {total_rows_checked:,}")
    print(f"Standardized Rows:  {standardized_rows:,}")
    print(f"Duplicates Found:   {duplicates_found:,}")
    print(f"============================================================")

if __name__ == "__main__":
    main()
