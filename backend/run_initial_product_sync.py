from app import app
from services.sync_to_product_master import sync_platform_to_master

if __name__ == "__main__":
    print("[SYNC] Starting initial migration of all scraped product data to product_master...")
    with app.app_context():
        # List of all e-commerce platforms to sync
        platforms = ['Zepto', 'Blinkit', 'DMart', 'BigBasket', 'Amazon', 'Flipkart', 'IndiaMART', 'JioMart']
        for p in platforms:
            try:
                sync_platform_to_master(p)
            except Exception as e:
                print(f"[ERROR] Failed syncing {p}: {e}")
    print("[SYNC] Complete migration of all product sources finished successfully!")
