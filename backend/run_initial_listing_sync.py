import os
import sys

sys.path.append(os.path.dirname(__file__))

from app import app
from services.sync_to_listing_master import sync_listing_source_to_master

if __name__ == "__main__":
    print("[SYNC] Starting initial consolidation of all raw directory listings into master_table...")
    with app.app_context():
        sources = ['asklaila', 'justdial', 'pinda', 'heyplaces', 'schoolgis', 'college_dunia', 'shiksha', 'nearbuy', 'yellow_pages', 'freelisting']
        for s in sources:
            try:
                sync_listing_source_to_master(s)
            except Exception as e:
                print(f"[ERROR] Failed syncing {s}: {e}")
    print("[SYNC] Complete consolidation of all directory listing sources finished successfully!")
