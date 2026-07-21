from services.csv_uploaders_listing.upload_heyplaces import upload_heyplaces_data
from services.sync_to_listing_master import sync_listing_source_to_master
from celery_app import celery
import os

@celery.task(bind=True,autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={'max_retries': 3,'countdown': 5},retry_jitter=True,acks_late=True)
def process_heyplaces_task(self,file_paths):
    if not file_paths:
        raise ValueError("No file provided")
    result = upload_heyplaces_data(file_paths)

    try:
        sync_listing_source_to_master('heyplaces')
    except Exception as sync_err:
        print(f"[AUTO-SYNC ERROR] Failed syncing heyplaces to master_table: {sync_err}")

    for path in file_paths:
        try:
            if os.path.exists(path):
                os.remove(path)
        except PermissionError:
            pass
    return result