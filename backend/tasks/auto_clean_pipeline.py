import os
import sys
import uuid
import logging
from celery_app import celery
from sqlalchemy import text

# Ensure backend dir is in sys.path
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.append(backend_dir)

logger = logging.getLogger("AutoCleanPipeline")

@celery.task(name='tasks.auto_clean_pipeline.auto_clean_master_table')
def auto_clean_master_table():
    """
    Celery task to run the full listings data cleaning pipeline on master_table.
    Applies the geographical, categoric, and standard validation rules.
    """
    logger.info("Starting automated cleaning task for master_table...")
    try:
        from app import app
        from extensions import db
        from services.data_cleaning_service import run_cleaning_async
        from model.data_cleaning_log import DataCleaningLog
        
        with app.app_context():
            run_id = f"auto_{uuid.uuid4().hex[:8]}"
            log_entry = DataCleaningLog(
                run_id=run_id,
                run_type="apply",
                status="running",
                table_name="master_table"
            )
            db.session.add(log_entry)
            db.session.commit()
            
            run_cleaning_async(run_id, "master_table", "apply", app.app_context())
            
        logger.info(f"✅ Automated cleaning task for master_table completed (Run ID: {run_id}).")
        return f"Success: {run_id}"
    except Exception as e:
        logger.error(f"❌ Automated cleaning task for master_table failed: {e}")
        return str(e)


@celery.task(name='tasks.auto_clean_pipeline.auto_clean_product_master')
def auto_clean_product_master():
    """
    Celery task to run the full product data cleaning pipeline on product_master.
    """
    logger.info("Starting automated cleaning task for product_master...")
    try:
        from app import app
        from extensions import db
        from services.data_cleaning_service import run_cleaning_async
        from model.data_cleaning_log import DataCleaningLog
        
        with app.app_context():
            run_id = f"auto_{uuid.uuid4().hex[:8]}"
            log_entry = DataCleaningLog(
                run_id=run_id,
                run_type="apply",
                status="running",
                table_name="product_master"
            )
            db.session.add(log_entry)
            db.session.commit()
            
            run_cleaning_async(run_id, "product_master", "apply", app.app_context())
            
        logger.info(f"✅ Automated cleaning task for product_master completed (Run ID: {run_id}).")
        return f"Success: {run_id}"
    except Exception as e:
        logger.error(f"❌ Automated cleaning task for product_master failed: {e}")
        return str(e)


@celery.task(name='tasks.auto_clean_pipeline.auto_route_item_tiers')
def auto_route_item_tiers():
    """
    Celery task to fetch pending raw records from item_data and route them 
    to the appropriate clean or malformed tiers (tier1_master_clean through tier5_linked_duplicates).
    """
    logger.info("Starting automated tier routing task for item_data...")
    try:
        from app import app
        from extensions import db
        from services.dynamic_cleaning_service import clean_and_route_batch
        
        with app.app_context():
            query = text("""
                SELECT ID, name, phone_no_1, email, address, city, state, pincode
                FROM item_data
                WHERE cleaning_status IS NULL OR cleaning_status = 'PENDING'
                LIMIT 5000
            """)
            rows = db.session.execute(query).fetchall()
            
            if not rows:
                logger.info("No pending rows found in item_data to process.")
                return "No rows to process"
                
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
                
            logger.info(f"Loaded {len(records)} pending rows from item_data. Processing routing...")
            processed_count = clean_and_route_batch('item_data', records)
            
        logger.info(f"✅ Automated tier routing completed. Processed {processed_count} rows.")
        return f"Processed {processed_count} rows"
    except Exception as e:
        logger.error(f"❌ Automated tier routing task failed: {e}")
        return str(e)
