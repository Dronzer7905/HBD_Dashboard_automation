import sys
sys.path.append(r'C:\\Desktop\\HBD_Dashboard_automation\\backend')

from database.session import SessionLocal
from sqlalchemy import text

def main():
    with SessionLocal() as db:
        print("Resetting tracking columns...")
        db.execute(text("UPDATE item_data SET assigned_tier = NULL, cleaning_status = NULL"))
        
        print("Updating Tier 1...")
        db.execute(text("""
            UPDATE item_data 
            SET assigned_tier = 'tier1_master_clean', cleaning_status = 'PROCESSED'
            WHERE ID IN (
                SELECT raw_source_id FROM tier1_master_clean WHERE raw_source_table = 'item_data'
            )
        """))
        
        print("Updating Tier 2...")
        db.execute(text("""
            UPDATE item_data 
            SET assigned_tier = 'tier2_missing_contact', cleaning_status = 'PROCESSED'
            WHERE ID IN (
                SELECT raw_source_id FROM tier2_missing_contact WHERE raw_source_table = 'item_data'
            )
        """))
        
        print("Updating Tier 3...")
        db.execute(text("""
            UPDATE item_data 
            SET assigned_tier = 'tier3_missing_location', cleaning_status = 'PROCESSED'
            WHERE ID IN (
                SELECT raw_source_id FROM tier3_missing_location WHERE raw_source_table = 'item_data'
            )
        """))
        
        print("Updating Tier 4...")
        db.execute(text("""
            UPDATE item_data 
            SET assigned_tier = 'tier4_partial_fragments', cleaning_status = 'PROCESSED'
            WHERE ID IN (
                SELECT raw_source_id FROM tier4_partial_fragments WHERE raw_source_table = 'item_data'
            )
        """))
        
        print("Updating Tier 5...")
        db.execute(text("""
            UPDATE item_data 
            SET assigned_tier = 'tier5_linked_duplicates', cleaning_status = 'PROCESSED'
            WHERE ID IN (
                SELECT raw_source_id FROM tier5_linked_duplicates WHERE raw_source_table = 'item_data'
            )
        """))
        
        db.commit()
        print("Updates completed and committed.")
        print("-" * 40)
        
        print("Verification Queries:")
        print("-" * 40)
        
        print("SELECT assigned_tier, COUNT(*) FROM item_data GROUP BY assigned_tier;")
        results = db.execute(text("SELECT assigned_tier, COUNT(*) FROM item_data GROUP BY assigned_tier")).fetchall()
        for row in results:
            print(f"{row[0]}: {row[1]}")
            
        print("-" * 40)
        print("SELECT cleaning_status, COUNT(*) FROM item_data GROUP BY cleaning_status;")
        results = db.execute(text("SELECT cleaning_status, COUNT(*) FROM item_data GROUP BY cleaning_status")).fetchall()
        for row in results:
            print(f"{row[0]}: {row[1]}")
            
        print("-" * 40)
        print("SELECT COUNT(*) FROM item_data WHERE assigned_tier IS NULL;")
        null_count = db.execute(text("SELECT COUNT(*) FROM item_data WHERE assigned_tier IS NULL")).scalar()
        print(f"NULL count: {null_count}")

if __name__ == '__main__':
    main()
