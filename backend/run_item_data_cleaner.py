import json
from app import app
from database.session import SessionLocal
from sqlalchemy import text
from services.dynamic_cleaning_service import clean_and_route_batch

db = SessionLocal()

limit = 5000

# Fetch 5000 rows from item_data where cleaning_status IS NULL or 'PENDING'
query = text("""
    SELECT ID, name, phone_no_1, email, address, city, state, pincode
    FROM item_data
    WHERE cleaning_status IS NULL OR cleaning_status = 'PENDING'
    LIMIT :limit
""")

rows = db.execute(query, {"limit": limit}).fetchall()

print(f"Fetched {len(rows)} rows from item_data to clean.")

records = []
for r in rows:
    records.append({
        "id": r[0],
        "name": str(r[1]) if r[1] is not None else "",
        "phone": str(r[2]) if r[2] is not None else "",
        "email": str(r[3]) if r[3] is not None else "",
        "address": str(r[4]) if r[4] is not None else "",
        "city": str(r[5]) if r[5] is not None else "",
        "state": str(r[6]) if r[6] is not None else "",
        "pincode": str(r[7]) if r[7] is not None else ""
    })

if records:
    with app.app_context():
        processed_count = clean_and_route_batch('item_data', records)
    print(f"SUCCESSFULLY PROCESSED {processed_count} ROWS.")
else:
    print("No pending rows found to process.")

# Now check tier tables for item_data entries
print("\n--- TIER SUMMARY FOR item_data ---")
for t in ['tier1_master_clean', 'tier2_missing_contact', 'tier3_missing_location', 'tier4_partial_fragments', 'tier5_linked_duplicates']:
    cnt = db.execute(text(f"SELECT COUNT(*) FROM {t} WHERE raw_source_table = 'item_data'")).scalar()
    print(f"{t}: {cnt} rows")

# Check sample entries in tier4_partial_fragments for item_data
malformed_t4 = db.execute(text("""
    SELECT id, raw_source_id, business_name, quality_score, fragment_data
    FROM tier4_partial_fragments
    WHERE raw_source_table = 'item_data'
    LIMIT 5
""")).fetchall()

print("\nSample entries in tier4_partial_fragments for item_data:")
for row in malformed_t4:
    print(row)

# Re-run check on tier tables for specific malformed bank IDs
ids_to_check = [1212601, 1212610, 1212670, 1213101, 1213476]
print("\nRe-checking specific malformed Bank IDs in tier tables:")
for tid in ids_to_check:
    found_any = False
    for table in ['tier1_master_clean', 'tier2_missing_contact', 'tier3_missing_location', 'tier4_partial_fragments', 'tier5_linked_duplicates']:
        res = db.execute(text(f"SELECT COUNT(*) FROM {table} WHERE raw_source_table = 'item_data' AND raw_source_id = :id"), {"id": tid}).scalar()
        if res and res > 0:
            print(f"ID {tid} found in {table}")
            found_any = True
    if not found_any:
        print(f"ID {tid} NOT found in any tier table (not in this batch of 5000)")

db.close()
