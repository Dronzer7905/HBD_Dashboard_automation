import os
import hashlib
from datetime import datetime
from sqlalchemy import create_engine, text
from urllib.parse import quote_plus
from dotenv import load_dotenv

# Import normalizer
import sys
sys.path.insert(0, os.getcwd())
from model.normalizer import UniversalNormalizer

load_dotenv()
db_pass = os.getenv('DB_PASSWORD_PLAIN') or os.getenv('DB_PASSWORD') or ''
DATABASE_URI = f"mysql+pymysql://{os.getenv('DB_USER')}:{quote_plus(db_pass)}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT', '3306')}/{os.getenv('DB_NAME')}"
engine = create_engine(DATABASE_URI)

def safe_str(val, default=""):
    if val is None: return default
    try:
        s = str(val).strip()
        return default if s.lower() in ('nan', 'none', 'nat', '') else s
    except Exception: return default

def safe_int(val, default=0):
    try:
        if val is None: return default
        s = str(val).strip()
        if s.lower() in ('', 'nan', 'none', 'nat'): return default
        import re
        m = re.search(r'\d+', s)
        return int(m.group()) if m else default
    except Exception: return default

def safe_float(val, default=0.0):
    try:
        if val is None: return default
        s = str(val).strip()
        if s.lower() in ('', 'nan', 'none', 'nat'): return default
        import re
        m = re.search(r'[-+]?\d*\.?\d+', s)
        return float(m.group()) if m else default
    except Exception: return default

def validate_row(row):
    mandatory_fields = ["name", "address", "phone_number", "city", "state", "category"]
    missing = [f for f in mandatory_fields if not row.get(f) or str(row.get(f)).strip() == ""]
    is_structured = len(missing) == 0
    
    invalid_fields = []
    raw_phone = safe_str(row.get('phone_number', ''))
    clean_phone = UniversalNormalizer.normalize_phone(raw_phone)
    if clean_phone and not (8 <= len(clean_phone) <= 18):
        invalid_fields.append("phone_number")
    elif not clean_phone and "phone_number" not in missing:
        missing.append("phone_number")

    if UniversalNormalizer.is_numerical_address(row.get('address')):
        invalid_fields.append("address")
        
    is_valid = len(invalid_fields) == 0 and is_structured
    return is_structured, is_valid, missing, invalid_fields

def process_missing_rows():
    batch_size = 10000
    with engine.connect() as conn:
        print("Checking table counts to verify no rows are missing...")
        raw_count = conn.execute(text("SELECT COUNT(id) FROM raw_google_map_drive_data")).scalar()
        clean_count = conn.execute(text("SELECT COUNT(raw_id) FROM raw_clean_google_map_data")).scalar()
        
        print(f" -> Total rows in raw table:   {raw_count}")
        print(f" -> Total rows in clean table: {clean_count}")
        
        if raw_count == clean_count:
            print(" -> SUCCESS: The row counts match perfectly. No rows are missing!")
            return
        
        diff = abs(raw_count - clean_count)
        print(f" -> NOTICE: There is a difference of {diff} rows between the tables.")

        print("\nLoading missing IDs from database (covering index scan)...")
        sql_missing_ids = text("""
            SELECT r.id 
            FROM raw_google_map_drive_data r 
            LEFT JOIN raw_clean_google_map_data c ON r.id = c.raw_id 
            WHERE c.raw_id IS NULL
        """)
        missing_ids = [row[0] for row in conn.execute(sql_missing_ids).fetchall()]
        print(f" -> Found {len(missing_ids)} missing IDs to process.")

        if not missing_ids:
            print("Sync complete. No missing rows found.")
            return

        for start_idx in range(0, len(missing_ids), batch_size):
            batch_ids = missing_ids[start_idx:start_idx + batch_size]
            
            # Fetch data for this specific batch of IDs
            sql_batch = text("""
                SELECT id, name, address, website, phone_number, 
                       reviews_count, reviews_average, category, subcategory, 
                       city, state, area, added_time AS created_at
                FROM raw_google_map_drive_data
                WHERE id IN :ids
            """)
            rows = conn.execute(sql_batch, {"ids": tuple(batch_ids)}).fetchall()
            if not rows:
                continue
                
            print(f"Processing batch of {len(rows)} rows...")
            
            # 1. Pre-process the rows to compute signature hashes in bulk
            batch_hashes = []
            row_signatures = []
            for r in rows:
                row_dict = r._asdict() if hasattr(r, '_asdict') else r._mapping
                norm_row = UniversalNormalizer.normalize_row_full(dict(row_dict))
                norm_row['id'] = row_dict['id']
                
                # String safety
                for key in ['name', 'address', 'website', 'phone_number', 'category', 'subcategory', 'city', 'state', 'area']:
                    norm_row[key] = safe_str(norm_row.get(key))
                
                # Sig Hash
                sig_str = f"{norm_row['phone_number']}|{norm_row['name'].lower()}|{norm_row['address'].lower()}|{norm_row['city'].lower()}"
                sig_hash = hashlib.md5(sig_str.encode()).hexdigest()
                batch_hashes.append(sig_hash)
                row_signatures.append((sig_hash, norm_row, row_dict))

            # 2. Check for duplicates in clean table in one single bulk request
            existing_hashes = set()
            if batch_hashes:
                sql_dup = text("SELECT signature_hash FROM raw_clean_google_map_data WHERE signature_hash IN :hashes")
                res_dup = conn.execute(sql_dup, {"hashes": tuple(batch_hashes)}).fetchall()
                existing_hashes = set(h[0] for h in res_dup)

            # 3. Process the rows using bulk-cached duplicates check
            clean_batch = []
            master_batch = []
            seen_in_batch = set()
            
            for sig_hash, norm_row, row_dict in row_signatures:
                is_structured, is_valid, missing, invalid = validate_row(norm_row)
                
                is_duplicate = (sig_hash in existing_hashes) or (sig_hash in seen_in_batch)
                seen_in_batch.add(sig_hash)
                
                status = "VALID"
                if not is_structured: status = "MISSING"
                elif is_duplicate: status = "DUPLICATE"
                elif not is_valid: status = "INVALID"
                
                # Create a guaranteed unique name for the clean table log to bypass MySQL case/space collation differences
                clean_name = f"{norm_row['name']} (Record #{norm_row['id']})"
                
                created_at = row_dict.get('created_at') or datetime.now()
                
                if status == "DUPLICATE":
                    clean_batch.append({
                        "raw_id": norm_row['id'], "sig_hash": sig_hash, "name": clean_name, "address": None,
                        "website": None, "phone": norm_row['phone_number'], 
                        "reviews": 0, "avg": 0.00,
                        "cat": None, "sub": None, "city": None,
                        "state": None, "area": None, "created": created_at,
                        "val_status": "DUPLICATE", 
                        "clean_status": "DUPLICATE_FOUND", 
                        "missing": None, 
                        "invalid": None, 
                        "duplicate_reason": "Exact match detected via signature hash", 
                        "processed_at": datetime.now()
                    })
                else:
                    clean_batch.append({
                        "raw_id": norm_row['id'], "sig_hash": sig_hash, "name": clean_name, "address": norm_row['address'],
                        "website": norm_row['website'], "phone": norm_row['phone_number'], 
                        "reviews": safe_int(norm_row.get('reviews_count', 0)),
                        "avg": safe_float(norm_row.get('reviews_average', 0.00)),
                        "cat": norm_row['category'], "sub": norm_row['subcategory'], "city": norm_row['city'],
                        "state": norm_row['state'], "area": norm_row['area'], "created": created_at,
                        "val_status": status, 
                        "clean_status": "CLEANED" if status == "VALID" else "FAILED_VALIDATION", 
                        "missing": ",".join(missing) if missing else None, 
                        "invalid": ",".join(invalid) if invalid else None, 
                        "duplicate_reason": None, 
                        "processed_at": datetime.now()
                    })
                
                if status == "VALID":
                    master_batch.append({
                        "name": norm_row['name'], "address": norm_row['address'], "website": norm_row['website'],
                        "phone_number": norm_row['phone_number'], "reviews_count": safe_int(norm_row.get('reviews_count', 0)),
                        "reviews_avg": safe_float(norm_row.get('reviews_average', 0.00)), "category": norm_row['category'],
                        "subcategory": norm_row['subcategory'], "city": norm_row['city'], "state": norm_row['state'],
                        "area": norm_row['area'], "created_at": created_at
                    })

            # Insert batches
            if clean_batch:
                print(f"Inserting {len(clean_batch)} rows into clean table...")
                with engine.begin() as trans_conn:
                    trans_conn.execute(text("""
                        INSERT IGNORE INTO raw_clean_google_map_data 
                        (raw_id, signature_hash, name, address, website, phone_number, reviews_count, reviews_avg,
                            category, subcategory, city, state, area, created_at,
                            validation_status, cleaning_status, missing_fields, invalid_format_fields, duplicate_reason, processed_at)
                        VALUES (:raw_id, :sig_hash, :name, :address, :website, :phone, :reviews, :avg, :cat, :sub, :city, :state, :area, :created,
                                :val_status, :clean_status, :missing, :invalid, :duplicate_reason, :processed_at)
                    """), clean_batch)
                    
                    if master_batch:
                        print(f"Inserting {len(master_batch)} rows into master table...")
                        trans_conn.execute(text("""
                            INSERT IGNORE INTO g_map_master_table 
                            (name, address, website, phone_number, reviews_count, reviews_avg, category, subcategory, city, state, area, created_at)
                            VALUES (:name, :address, :website, :phone_number, :reviews_count, :reviews_avg, :category, :subcategory, :city, :state, :area, :created_at)
                        """), master_batch)
            print("Batch Done!")

if __name__ == "__main__":
    process_missing_rows()
