from services.csv_uploaders_product.upload_dmart import upload_dmart_data
from celery_app import celery
import os

@celery.task(bind=True,autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={'max_retries': 3,'countdown': 5},retry_jitter=True,acks_late=True)
def process_dmart_task(self,file_paths):
    if not file_paths:
        raise ValueError("No file provided")
    result = upload_dmart_data(file_paths)

    for path in file_paths:
        try:
            if os.path.exists(path):
                os.remove(path)
        except PermissionError:
            pass

    # Automatically trigger category sync & auto-mapping for DMart in background
    try:
        from services.category_sync_service import auto_sync_platform
        auto_sync_platform('DMart')
    except Exception as e:
        print(f"[CategoryAutoSync] Error running sync for DMart: {e}")

    # Consolidate new DMart products directly into product_master table
    try:
        from services.sync_to_product_master import sync_platform_to_master
        sync_platform_to_master('DMart')
    except Exception as e:
        print(f"[ProductMasterSync] Error running master sync for DMart: {e}")

    return result