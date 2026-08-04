from database.session import SessionLocal
from sqlalchemy import text

db = SessionLocal()

columns_query = db.execute(text("SHOW COLUMNS FROM item_data")).fetchall()
col_names = [col[0].lower() for col in columns_query]

added_cols = []
if 'cleaning_status' not in col_names:
    db.execute(text("ALTER TABLE item_data ADD COLUMN cleaning_status VARCHAR(50) DEFAULT 'PENDING'"))
    added_cols.append('cleaning_status')
if 'assigned_tier' not in col_names:
    db.execute(text("ALTER TABLE item_data ADD COLUMN assigned_tier VARCHAR(100) DEFAULT NULL"))
    added_cols.append('assigned_tier')
if 'quality_score' not in col_names:
    db.execute(text("ALTER TABLE item_data ADD COLUMN quality_score INT DEFAULT NULL"))
    added_cols.append('quality_score')

db.commit()
print("PREPARE TABLE OUTPUT:", f"Added columns: {added_cols if added_cols else 'None (Already fit)'}")

cols_after = [col[0] for col in db.execute(text("SHOW COLUMNS FROM item_data")).fetchall()]
print("Columns in item_data now:", cols_after)
db.close()
