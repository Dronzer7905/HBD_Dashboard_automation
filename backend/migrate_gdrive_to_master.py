import logging
import os
import sys
from sqlalchemy import text

sys.path.append(os.path.dirname(__file__))

from app import app
from extensions import db

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("GDriveMigrator")

def migrate_existing_gmap_data():
    logger.info("🔄 Starting one-time migration from g_map_master_table to master_table...")
    
    # Check if g_map_master_table exists
    with app.app_context():
        with db.engine.connect() as conn:
            check_table = conn.execute(text(
                "SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'g_map_master_table'"
            )).scalar()
            
            if check_table == 0:
                logger.error("❌ Table g_map_master_table does not exist in the database! Migration aborted.")
                return

            row_count = conn.execute(text("SELECT COUNT(*) FROM g_map_master_table")).scalar()
            logger.info(f"📊 Found {row_count:,} rows in g_map_master_table to migrate.")
            
            if row_count == 0:
                logger.info("✅ No rows to migrate. Finished!")
                return
            
            # Migration Query
            sql = """
                INSERT IGNORE INTO master_table (
                    global_business_id, business_name, address, website_url, primary_phone, 
                    reviews, ratings, business_category, business_subcategory, city, state, area, 
                    source, cleaning_status, created_at
                )
                SELECT 
                    (1200000000 + id) AS global_business_id,
                    name AS business_name,
                    address,
                    website AS website_url,
                    phone_number AS primary_phone,
                    reviews_count AS reviews,
                    reviews_avg AS ratings,
                    category AS business_category,
                    subcategory AS business_subcategory,
                    city,
                    IFNULL(state, 'Unknown') AS state,
                    area,
                    'Google Maps' AS source,
                    'PENDING' AS cleaning_status,
                    IFNULL(created_at, NOW()) AS created_at
                FROM g_map_master_table;
            """
            
            trans = conn.begin()
            try:
                res = conn.execute(text(sql))
                trans.commit()
                logger.info(f"✅ Migration successful! {res.rowcount:,} rows merged into master_table under source='Google Maps'.")
            except Exception as e:
                trans.rollback()
                logger.error(f"❌ Migration failed: {e}")
                raise e

if __name__ == "__main__":
    migrate_existing_gmap_data()
