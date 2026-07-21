import logging
from sqlalchemy import text
from extensions import db

logger = logging.getLogger("ListingMasterSync")

def sync_listing_source_to_master(source_name: str):
    """
    Consolidates raw directory listings into master_table using
    high-performance SQL statements.
    """
    logger.info(f"🔄 Starting listing master sync for {source_name}...")
    
    # 1. AskLaila (columns: id, name, number1, number2, category, subcategory, email, url, ratings, address, pincode, area, city, state, country)
    if source_name == 'asklaila':
        sql = """
            INSERT INTO master_table (
                business_name, primary_phone, secondary_phone, email, address, 
                area, city, state, pincode, business_category, business_subcategory, 
                website_url, ratings, source, cleaning_status, created_at
            )
            SELECT 
                name AS business_name,
                number1 AS primary_phone,
                number2 AS secondary_phone,
                email,
                address,
                area,
                city,
                state,
                pincode,
                category AS business_category,
                subcategory AS business_subcategory,
                url AS website_url,
                ratings,
                'asklaila' AS source,
                'PENDING' AS cleaning_status,
                NOW()
            FROM asklaila
            WHERE name IS NOT NULL AND (number1 IS NOT NULL OR address IS NOT NULL);
        """
        res = db.session.execute(text(sql))
        db.session.commit()
        logger.info(f"✅ Successfully synced AskLaila to master_table. Rows inserted: {res.rowcount}")

    # 2. JustDial (columns: company, category, city, area, address, pin, email, virtualnumber, whatsapp, number1, number2, number3, latitude, longitude, rating, reviews, website)
    elif source_name == 'justdial':
        sql = """
            INSERT INTO master_table (
                business_name, primary_phone, secondary_phone, other_phones, virtual_phone, whatsapp_phone, email, address, 
                area, city, pincode, business_category, website_url, ratings, latitude, longitude, source, cleaning_status, created_at
            )
            SELECT 
                company AS business_name,
                number1 AS primary_phone,
                number2 AS secondary_phone,
                number3 AS other_phones,
                virtualnumber AS virtual_phone,
                whatsapp AS whatsapp_phone,
                email,
                address,
                area,
                city,
                pin AS pincode,
                category AS business_category,
                website AS website_url,
                rating AS ratings,
                latitude,
                longitude,
                'justdial' AS source,
                'PENDING' AS cleaning_status,
                NOW()
            FROM justdial
            WHERE company IS NOT NULL AND (number1 IS NOT NULL OR address IS NOT NULL);
        """
        res = db.session.execute(text(sql))
        db.session.commit()
        logger.info(f"✅ Successfully synced JustDial to master_table. Rows inserted: {res.rowcount}")

    # 3. Pinda (columns: id, name, url, address, number, category, country, city)
    elif source_name == 'pinda':
        max_id = db.session.execute(text("SELECT MAX(id) FROM pinda")).scalar() or 0
        batch_size = 100000
        logger.info(f"📦 Pinda has max_id={max_id}. Syncing in chunks of {batch_size}...")
        total_synced = 0
        for start_id in range(0, max_id + 1, batch_size):
            end_id = start_id + batch_size
            sql = f"""
                INSERT INTO master_table (
                    business_name, primary_phone, address, city, country,
                    business_category, website_url, source, cleaning_status, created_at
                )
                SELECT 
                    name AS business_name,
                    number AS primary_phone,
                    address,
                    city,
                    country,
                    category AS business_category,
                    url AS website_url,
                    'pinda' AS source,
                    'PENDING' AS cleaning_status,
                    NOW()
                FROM pinda
                WHERE id >= {start_id} AND id < {end_id} AND name IS NOT NULL;
            """
            r = db.session.execute(text(sql))
            db.session.commit()
            total_synced += r.rowcount
        logger.info(f"✅ Successfully synced Pinda to master_table. Total rows inserted: {total_synced}")

    # 4. HeyPlaces (columns: id, name, address, number, website, category, city)
    elif source_name == 'heyplaces':
        sql = """
            INSERT INTO master_table (
                business_name, primary_phone, address, city, 
                business_category, website_url, source, cleaning_status, created_at
            )
            SELECT 
                name AS business_name,
                number AS primary_phone,
                address,
                city,
                category AS business_category,
                website AS website_url,
                'heyplaces' AS source,
                'PENDING' AS cleaning_status,
                NOW()
            FROM heyplaces
            WHERE name IS NOT NULL;
        """
        res = db.session.execute(text(sql))
        db.session.commit()
        logger.info(f"✅ Successfully synced HeyPlaces to master_table. Rows inserted: {res.rowcount}")

    # 5. SchoolGIS (columns: name, pincode, latitude, longitude, subcategory, city, state, country, category)
    elif source_name == 'schoolgis':
        sql = """
            INSERT INTO master_table (
                business_name, pincode, latitude, longitude, city, state, country,
                business_category, business_subcategory, source, cleaning_status, created_at
            )
            SELECT 
                name AS business_name,
                pincode,
                latitude,
                longitude,
                city,
                state,
                country,
                category AS business_category,
                subcategory AS business_subcategory,
                'schoolgis' AS source,
                'PENDING' AS cleaning_status,
                NOW()
            FROM schoolgis
            WHERE name IS NOT NULL;
        """
        res = db.session.execute(text(sql))
        db.session.commit()
        logger.info(f"✅ Successfully synced SchoolGIS to master_table. Rows inserted: {res.rowcount}")

    # 6. CollegeDunia (columns: name, address, area, avg_fees, rating, number, website, country, subcategory, category, course_details, duration, email, requirement)
    elif source_name == 'college_dunia':
        sql = """
            INSERT INTO master_table (
                business_name, primary_phone, email, address, area, country,
                business_category, business_subcategory, website_url, ratings, avg_fees, course_details, duration, requirement,
                source, cleaning_status, created_at
            )
            SELECT 
                name AS business_name,
                number AS primary_phone,
                email,
                address,
                area,
                country,
                category AS business_category,
                subcategory AS business_subcategory,
                website AS website_url,
                rating AS ratings,
                avg_fees,
                course_details,
                duration,
                requirement,
                'college_dunia' AS source,
                'PENDING' AS cleaning_status,
                NOW()
            FROM college_dunia
            WHERE name IS NOT NULL;
        """
        res = db.session.execute(text(sql))
        db.session.commit()
        logger.info(f"✅ Successfully synced CollegeDunia to master_table. Rows inserted: {res.rowcount}")

    # 7. Shiksha (columns: name, address, area, latitude, longitude, admission_requirement, courses, avg_fees, avg_salary, rating, number, website, email, category, country)
    elif source_name == 'shiksha':
        sql = """
            INSERT INTO master_table (
                business_name, primary_phone, email, address, area, country, latitude, longitude,
                business_category, website_url, ratings, avg_fees, avg_salary, courses, admission_req_list,
                source, cleaning_status, created_at
            )
            SELECT 
                name AS business_name,
                number AS primary_phone,
                email,
                address,
                area,
                country,
                latitude,
                longitude,
                category AS business_category,
                website AS website_url,
                rating AS ratings,
                avg_fees,
                avg_salary,
                courses,
                admission_requirement AS admission_req_list,
                'shiksha' AS source,
                'PENDING' AS cleaning_status,
                NOW()
            FROM shiksha
            WHERE name IS NOT NULL;
        """
        res = db.session.execute(text(sql))
        db.session.commit()
        logger.info(f"✅ Successfully synced Shiksha to master_table. Rows inserted: {res.rowcount}")

    # 8. Nearbuy
    elif source_name == 'nearbuy':
        sql = """
            INSERT INTO master_table (
                business_name, primary_phone, address, city, country, latitude, longitude, ratings,
                source, cleaning_status, created_at
            )
            SELECT 
                name AS business_name,
                number AS primary_phone,
                address,
                city,
                country,
                latitude,
                longitude,
                rating AS ratings,
                'nearbuy' AS source,
                'PENDING' AS cleaning_status,
                NOW()
            FROM nearbuy
            WHERE name IS NOT NULL;
        """
        res = db.session.execute(text(sql))
        db.session.commit()
        logger.info(f"✅ Successfully synced Nearbuy to master_table. Rows inserted: {res.rowcount}")

    # 9. YellowPages
    elif source_name == 'yellow_pages':
        sql = """
            INSERT INTO master_table (
                business_name, primary_phone, email, address, area, city, state, pincode, country,
                business_category, source, cleaning_status, created_at
            )
            SELECT 
                name AS business_name,
                number AS primary_phone,
                email,
                address,
                area,
                city,
                state,
                pincode,
                country,
                category AS business_category,
                'yellow_pages' AS source,
                'PENDING' AS cleaning_status,
                NOW()
            FROM yellow_pages
            WHERE name IS NOT NULL;
        """
        res = db.session.execute(text(sql))
        db.session.commit()
        logger.info(f"✅ Successfully synced YellowPages to master_table. Rows inserted: {res.rowcount}")

    # 10. FreeListing
    elif source_name == 'freelisting':
        sql = """
            INSERT INTO master_table (
                business_name, primary_phone, address, description, business_category, business_subcategory, subcategory_2,
                website_url, source, cleaning_status, created_at
            )
            SELECT 
                name AS business_name,
                number AS primary_phone,
                address,
                description,
                category AS business_category,
                subcategory AS business_subcategory,
                subcategory_1 AS subcategory_2,
                url AS website_url,
                'freelisting' AS source,
                'PENDING' AS cleaning_status,
                NOW()
            FROM freelisting
            WHERE name IS NOT NULL;
        """
        res = db.session.execute(text(sql))
        db.session.commit()
        logger.info(f"✅ Successfully synced FreeListing to master_table. Rows inserted: {res.rowcount}")
