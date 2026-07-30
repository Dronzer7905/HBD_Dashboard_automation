import sys
sys.path.append(r'C:\Desktop\HBD_Dashboard_automation\backend')
from database.session import SessionLocal
from sqlalchemy import text

def main():
    db = SessionLocal()
    
    print("Applying new unusable conditions to incomplete_recoverable rows...")
    
    # Condition 1: contains "@"
    # Condition 2: ends with double quote or single quote
    update_sql = text("""
        UPDATE item_data 
        SET data_quality = 'unusable' 
        WHERE assigned_tier = 'tier4_partial_fragments' 
          AND data_quality = 'incomplete_recoverable' 
          AND (name LIKE '%@%' OR name LIKE '%"' OR name LIKE "%'");
    """)
    
    # We have to be careful with escaping the single quote in Python string.
    # The above uses a triple-quoted string, so `%"` and `%'` should be passed to MySQL properly.
    
    result = db.execute(update_sql)
    db.commit()
    
    print(f"Updated {result.rowcount} rows to 'unusable'.")
    
    unusable = db.execute(text("SELECT COUNT(*) FROM item_data WHERE assigned_tier = 'tier4_partial_fragments' AND data_quality = 'unusable'")).scalar()
    recoverable = db.execute(text("SELECT COUNT(*) FROM item_data WHERE assigned_tier = 'tier4_partial_fragments' AND data_quality = 'incomplete_recoverable'")).scalar()
    
    print("-" * 40)
    print("Updated Final Summary:")
    print(f"Total unusable: {unusable}")
    print(f"Total incomplete_recoverable: {recoverable}")
    
    db.close()

if __name__ == '__main__':
    main()
