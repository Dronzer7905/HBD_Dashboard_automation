import logging
from sqlalchemy import text
from extensions import db

logger = logging.getLogger("ProductMasterSync")

def sync_platform_to_master(platform_name: str):
    """
    Consolidates raw platform scraper data directly into product_master 
    using high-performance database-level UPSERT statements.
    """
    logger.info(f"🔄 Starting product master sync for {platform_name}...")
    
    # 1. Special chunked processing for Amazon to prevent read timeouts on 1.6M rows
    if platform_name == 'Amazon':
        try:
            max_id = db.session.execute(text("SELECT MAX(id) FROM amazon_products")).scalar() or 0
            batch_size = 100000
            logger.info(f"📦 Amazon has max_id={max_id}. Processing in chunks of {batch_size}...")
            
            for start_id in range(0, max_id + 1, batch_size):
                end_id = start_id + batch_size
                query = f"""
                    INSERT INTO product_master (
                        marketplace_name, asin, product_name, brand, price, list_price, 
                        stars, reviews, is_best_seller, bought_in_last_month, availability, 
                        category_name, img_url, product_url, cleaning_status, created_at, updated_at
                    )
                    SELECT 
                        'Amazon' AS marketplace_name,
                        asin,
                        title AS product_name,
                        SUBSTRING_INDEX(title, ' ', 1) AS brand,
                        price,
                        listPrice AS list_price,
                        stars,
                        reviews,
                        isBestSeller AS is_best_seller,
                        boughtInLastMonth AS bought_in_last_month,
                        'In Stock' AS availability,
                        categoryName AS category_name,
                        imgUrl AS img_url,
                        productUrl AS product_url,
                        'PENDING' AS cleaning_status,
                        NOW(), NOW()
                    FROM amazon_products
                    WHERE id >= {start_id} AND id < {end_id}
                    ON DUPLICATE KEY UPDATE
                        product_name = VALUES(product_name),
                        price = VALUES(price),
                        list_price = VALUES(list_price),
                        stars = VALUES(stars),
                        reviews = VALUES(reviews),
                        is_best_seller = VALUES(is_best_seller),
                        bought_in_last_month = VALUES(bought_in_last_month),
                        category_name = VALUES(category_name),
                        img_url = VALUES(img_url),
                        product_url = VALUES(product_url),
                        updated_at = NOW();
                """
                db.session.execute(text(query))
                db.session.commit()
                logger.info(f"  - Completed chunk {start_id} to {end_id}")
                
            logger.info("✅ Successfully synced Amazon in chunks to product_master.")
            return True
        except Exception as e:
            db.session.rollback()
            logger.error(f"🔥 Database sync failed for Amazon: {e}")
            return False

    # 2. SQL queries for other platforms (which complete in under 5 seconds)
    queries = {
        'Zepto': """
            INSERT INTO product_master (
                marketplace_name, asin, product_name, brand, price, list_price, 
                stars, reviews, availability, category_name, sub_category_name, 
                img_url, product_url, description, cleaning_status, created_at, updated_at
            )
            SELECT 
                'Zepto' AS marketplace_name,
                sku_id AS asin,
                product_name,
                SUBSTRING_INDEX(product_name, ' ', 1) AS brand,
                selling_price AS price,
                mrp AS list_price,
                rating AS stars,
                review AS reviews,
                'In Stock' AS availability,
                main_category AS category_name,
                subcategory AS sub_category_name,
                image_url AS img_url,
                product_url,
                product_description AS description,
                'PENDING' AS cleaning_status,
                NOW(), NOW()
            FROM zepto
            ON DUPLICATE KEY UPDATE
                product_name = VALUES(product_name),
                price = VALUES(price),
                list_price = VALUES(list_price),
                stars = VALUES(stars),
                reviews = VALUES(reviews),
                img_url = VALUES(img_url),
                product_url = VALUES(product_url),
                description = VALUES(description),
                updated_at = NOW();
        """,
        'Blinkit': """
            INSERT INTO product_master (
                marketplace_name, asin, product_name, brand, price, list_price, 
                stars, reviews, availability, category_name, img_url, 
                product_url, cleaning_status, created_at, updated_at
            )
            SELECT 
                'Blinkit' AS marketplace_name,
                product_id AS asin,
                product_name,
                brand,
                price,
                mrp AS list_price,
                NULL AS stars,
                NULL AS reviews,
                'In Stock' AS availability,
                category AS category_name,
                image_url AS img_url,
                product_url,
                'PENDING' AS cleaning_status,
                NOW(), NOW()
            FROM blinkit
            ON DUPLICATE KEY UPDATE
                product_name = VALUES(product_name),
                price = VALUES(price),
                list_price = VALUES(list_price),
                img_url = VALUES(img_url),
                product_url = VALUES(product_url),
                updated_at = NOW();
        """,
        'DMart': """
            INSERT INTO product_master (
                marketplace_name, asin, product_name, brand, price, list_price, 
                availability, category_name, img_url, product_url, 
                cleaning_status, created_at, updated_at
            )
            SELECT 
                'DMart' AS marketplace_name,
                ASIN AS asin,
                Product_name,
                Brand,
                price,
                listPrice AS list_price,
                IF(availability = 1, 'In Stock', 'Out of Stock') AS availability,
                category AS category_name,
                Image_URLs AS img_url,
                link AS product_url,
                'PENDING' AS cleaning_status,
                NOW(), NOW()
            FROM dmart_products
            ON DUPLICATE KEY UPDATE
                product_name = VALUES(product_name),
                price = VALUES(price),
                list_price = VALUES(list_price),
                availability = VALUES(availability),
                img_url = VALUES(img_url),
                product_url = VALUES(product_url),
                updated_at = NOW();
        """,
        'BigBasket': """
            INSERT INTO product_master (
                marketplace_name, asin, product_name, brand, price, list_price, 
                stars, reviews, availability, category_name, 
                img_url, product_url, cleaning_status, created_at, updated_at
            )
            SELECT 
                'BigBasket' AS marketplace_name,
                CAST(sku_id AS CHAR) AS asin,
                product_name,
                SUBSTRING_INDEX(product_name, ' ', 1) AS brand,
                selling_price AS price,
                mrp AS list_price,
                rating AS stars,
                review AS reviews,
                'In Stock' AS availability,
                main_category AS category_name,
                NULL AS img_url,
                product_url,
                'PENDING' AS cleaning_status,
                NOW(), NOW()
            FROM bigbasket
            ON DUPLICATE KEY UPDATE
                product_name = VALUES(product_name),
                price = VALUES(price),
                list_price = VALUES(list_price),
                stars = VALUES(stars),
                reviews = VALUES(reviews),
                product_url = VALUES(product_url),
                updated_at = NOW();
        """,
        'Flipkart': """
            INSERT INTO product_master (
                marketplace_name, asin, product_name, brand, price, list_price, 
                discount, stars, reviews, availability, category_name, sub_category_name, 
                img_url, product_url, cleaning_status, created_at, updated_at
            )
            SELECT 
                'Flipkart' AS marketplace_name,
                product_id AS asin,
                product_name,
                brand,
                price,
                mrp AS list_price,
                discount,
                rating AS stars,
                CAST(NULLIF(REGEXP_REPLACE(reviews, '[^0-9]', ''), '') AS SIGNED) AS reviews,
                'In Stock' AS availability,
                main_category AS category_name,
                subcategory AS sub_category_name,
                image_url AS img_url,
                product_url,
                'PENDING' AS cleaning_status,
                NOW(), NOW()
            FROM flipkart_products_new
            ON DUPLICATE KEY UPDATE
                product_name = VALUES(product_name),
                brand = VALUES(brand),
                price = VALUES(price),
                list_price = VALUES(list_price),
                discount = VALUES(discount),
                stars = VALUES(stars),
                reviews = VALUES(reviews),
                img_url = VALUES(img_url),
                product_url = VALUES(product_url),
                updated_at = NOW();
        """,
        'IndiaMART': """
            INSERT INTO product_master (
                marketplace_name, asin, product_name, price, stars, 
                description, category_name, sub_category_name, cleaning_status, created_at, updated_at
            )
            SELECT 
                'IndiaMART' AS marketplace_name,
                asin,
                product_name,
                CAST(NULLIF(REGEXP_SUBSTR(Price, '[0-9]+(\\\\.[0-9]+)?'), '') AS DECIMAL(12,2)) AS price,
                stars,
                description,
                category_name,
                sub_category_name,
                'PENDING' AS cleaning_status,
                NOW(), NOW()
            FROM indiamart_products
            ON DUPLICATE KEY UPDATE
                product_name = VALUES(product_name),
                price = VALUES(price),
                stars = VALUES(stars),
                description = VALUES(description),
                category_name = VALUES(category_name),
                sub_category_name = VALUES(sub_category_name),
                updated_at = NOW();
        """,
        'JioMart': """
            INSERT INTO product_master (
                marketplace_name, asin, product_name, brand, price, list_price, 
                availability, img_url, product_url, cleaning_status, created_at, updated_at
            )
            SELECT 
                'JioMart' AS marketplace_name,
                sku_id AS asin,
                product_name,
                brand,
                price,
                mrp AS list_price,
                'In Stock' AS availability,
                image_url AS img_url,
                product_url,
                'PENDING' AS cleaning_status,
                NOW(), NOW()
            FROM jiomart_products
            ON DUPLICATE KEY UPDATE
                product_name = VALUES(product_name),
                brand = VALUES(brand),
                price = VALUES(price),
                list_price = VALUES(list_price),
                img_url = VALUES(img_url),
                product_url = VALUES(product_url),
                updated_at = NOW();
        """
    }

    if platform_name not in queries:
        logger.error(f"❌ Unknown platform for sync: {platform_name}")
        return False

    try:
        # Run the direct database transfer query
        result = db.session.execute(text(queries[platform_name]))
        db.session.commit()
        logger.info(f"✅ Successfully synced {platform_name} to product_master. Rows modified: {result.rowcount}")
        return True
    except Exception as e:
        db.session.rollback()
        logger.error(f"🔥 Database sync failed for {platform_name}: {e}")
        return False
