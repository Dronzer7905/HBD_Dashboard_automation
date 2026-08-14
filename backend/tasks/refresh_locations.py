import logging
from celery_app import celery
from database.session import get_db_session
from sqlalchemy import text
import sys
import os

@celery.task(name='tasks.refresh_locations.sync_new_locations')
def sync_new_locations():
    """
    Celery task to automatically sync new locations from Location_Master_India 
    to location_master and process new address components from master_table.
    This task is idempotent and safe to run periodically.
    """
    logging.info("Starting automatic location synchronization task...")
    
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if backend_dir not in sys.path:
        sys.path.append(backend_dir)
        
    try:
        from migrate_locations_full import main as run_migration
        from parse_addresses_to_hierarchy import main as run_address_parser
        
        logging.info("Step 1: Running migrate_locations_full...")
        run_migration()
        
        logging.info("Step 2: Running parse_addresses_to_hierarchy...")
        run_address_parser()
        
        logging.info("✅ Location synchronization task completed successfully.")
        return "Success"
    except Exception as e:
        logging.error(f"❌ Failed to sync locations automatically: {e}")
        return str(e)
