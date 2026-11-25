import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

def build_master_sync_workbook():
    wb = openpyxl.Workbook()
    # Remove default sheet
    wb.remove(wb.active)

    # Styling Palettes
    DARK_NAVY = "1B365D"
    SLATE_BLUE = "2C3E50"
    TEAL_HEADER = "0E6251"
    ACCENT_BLUE = "2980B9"
    ACCENT_PURPLE = "6C3483"
    ALERT_RED = "922B21"
    SUCCESS_GREEN = "1E8449"
    LIGHT_GRAY_FILL = "F8F9FA"
    ZEBRA_FILL = "F2F4F4"
    WHITE = "FFFFFF"
    BORDER_COLOR = "BDC3C7"

    font_title = Font(name="Calibri", size=16, bold=True, color=DARK_NAVY)
    font_subtitle = Font(name="Calibri", size=11, italic=True, color="566573")
    font_section = Font(name="Calibri", size=13, bold=True, color=SLATE_BLUE)
    font_tbl_header = Font(name="Calibri", size=11, bold=True, color=WHITE)
    font_body = Font(name="Calibri", size=10, bold=False, color="212F3D")
    font_body_bold = Font(name="Calibri", size=10, bold=True, color="212F3D")
    font_code = Font(name="Consolas", size=9.5, bold=False, color="1B4F72")

    fill_navy = PatternFill(start_color=DARK_NAVY, end_color=DARK_NAVY, fill_type="solid")
    fill_slate = PatternFill(start_color=SLATE_BLUE, end_color=SLATE_BLUE, fill_type="solid")
    fill_teal = PatternFill(start_color=TEAL_HEADER, end_color=TEAL_HEADER, fill_type="solid")
    fill_purple = PatternFill(start_color=ACCENT_PURPLE, end_color=ACCENT_PURPLE, fill_type="solid")
    fill_accent_blue = PatternFill(start_color=ACCENT_BLUE, end_color=ACCENT_BLUE, fill_type="solid")
    fill_light_gray = PatternFill(start_color=LIGHT_GRAY_FILL, end_color=LIGHT_GRAY_FILL, fill_type="solid")
    fill_zebra = PatternFill(start_color=ZEBRA_FILL, end_color=ZEBRA_FILL, fill_type="solid")
    fill_yellow = PatternFill(start_color="FCF3CF", end_color="FCF3CF", fill_type="solid")
    fill_green_light = PatternFill(start_color="D4EFDF", end_color="D4EFDF", fill_type="solid")
    fill_red_light = PatternFill(start_color="FADBD8", end_color="FADBD8", fill_type="solid")

    thin_border = Border(
        left=Side(style='thin', color=BORDER_COLOR),
        right=Side(style='thin', color=BORDER_COLOR),
        top=Side(style='thin', color=BORDER_COLOR),
        bottom=Side(style='thin', color=BORDER_COLOR)
    )

    def style_header_row(ws, row_idx, fill_obj):
        for col_idx in range(1, ws.max_column + 1):
            cell = ws.cell(row=row_idx, column=col_idx)
            cell.font = font_tbl_header
            cell.fill = fill_obj
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            cell.border = thin_border
        ws.row_dimensions[row_idx].height = 28

    def auto_fit_columns(ws, max_cols=None):
        num_cols = max_cols or ws.max_column
        for col in range(1, num_cols + 1):
            col_letter = get_column_letter(col)
            max_len = 0
            for row in range(1, ws.max_row + 1):
                val = ws.cell(row=row, column=col).value
                if val:
                    val_str = str(val)
                    if "\n" in val_str:
                        lines = val_str.split("\n")
                        line_max = max(len(l) for l in lines)
                        if line_max > max_len:
                            max_len = line_max
                    else:
                        if len(val_str) > max_len:
                            max_len = len(val_str)
            ws.column_dimensions[col_letter].width = min(max(max_len + 4, 12), 65)

    # =========================================================================
    # TAB 1: EXECUTIVE OVERVIEW & SIGN-OFF
    # =========================================================================
    ws1 = wb.create_sheet(title="Executive Overview & Sign-Off")
    ws1.views.sheetView[0].showGridLines = True

    ws1.cell(row=1, column=1, value="CityHangaround Production Data Sync & Multi-Platform Product Master").font = font_title
    ws1.cell(row=2, column=1, value="Unified Enterprise Specification: Directory, 8-Marketplace Products, Categories, and Sync Architecture").font = font_subtitle

    overview_sections = [
        ("1. EXECUTIVE SCOPE & PURPOSE", 
         "This master document provides the complete technical and operational crosswalk between the HBD Automation System and CityHangaround's production database.\n"
         "It covers: (1) Local Business Directory (460k+ listings), (2) Geography Hierarchy (India Master), (3) Master Categories & Taxonomies,\n"
         "(4) The P1 Business-Product Bridge, and (5) Complete 8-Marketplace E-Commerce Catalog (Amazon, Flipkart, Zepto, Blinkit, DMart, BigBasket, IndiaMART, JioMart)."),
        
        ("2. STRICT GOVERNANCE & ZERO-WRITE POLICY",
         "CRITICAL SAFETY MANDATE: No write, update, alter, or ETL job will touch the live CityHangaround database until this plan receives formal management review.\n"
         "All development and verification will proceed in dry-run/simulation mode. No tables will be modified or dropped without prior explicit authorization."),
        
        ("3. THE 3-TIER PRODUCT ARCHITECTURE",
         "Our system operates a sophisticated 3-tier product engine:\n"
         "• Tier 1 (Raw Scrapers): Dedicated ingestion tables for 8 major platforms (Amazon 1.6M+, Flipkart, Zepto, Blinkit, DMart, BigBasket, IndiaMART, JioMart).\n"
         "• Tier 2 (Consolidated Master): High-speed UPSERT consolidation into 'product_master', with automated cleaning, deduplication, and quarantine of invalid items.\n"
         "• Tier 3 (Taxonomy & Association): Mapped to 'product_category_master' and linked to local business categories via 'business_product_category_mappings'."),
        
        ("4. CITYHANGAROUND DUAL-PRODUCT CONSUMPTION",
         "CityHangaround natively supports products in two distinct operational models:\n"
         "• Model A: Affiliate / Marketplace Products ('affiliate_products' table) — Receives our 8-marketplace catalog (ASIN/SKU, prices, ratings, affiliate URLs, badges).\n"
         "• Model B: Merchant Store Inventory ('page_products' & 'product_catalogue' tables) — Links products to specific local business pages with city/area context.\n"
         "• Model C: Master Directory Catalog ('catalog_items' & 'catalog_products') — Canonical global product catalog templates."),
        
        ("5. ID RESOLUTION & INTEGRITY GUARANTEES",
         "• Natural Compound Key Resolution: Cities, categories, and areas are resolved via in-memory lookup maps [(lower(name), parent_id) -> destination_id].\n"
         "• Zero ID Overwrites: Source auto-increment IDs are NEVER forced onto CityHangaround target tables to prevent fatal primary key collisions.\n"
         "• Idempotent Business Upsert: CityHangaround's 'pages.db_primary_id' stores our source listing ID, allowing clean 'ON CONFLICT DO UPDATE' operations.\n"
         "• Idempotent Product Upsert: 'affiliate_products' utilizes unique compound key (source, source_product_id) for safe re-syncing.")
    ]

    curr_row = 4
    for title, desc in overview_sections:
        ws1.cell(row=curr_row, column=1, value=title).font = font_section
        curr_row += 1
        cell = ws1.cell(row=curr_row, column=1, value=desc)
        cell.font = font_body
        cell.alignment = Alignment(wrap_text=True)
        ws1.merge_cells(start_row=curr_row, start_column=1, end_row=curr_row, end_column=6)
        ws1.row_dimensions[curr_row].height = 55
        curr_row += 2

    # Sign-off box
    ws1.cell(row=curr_row, column=1, value="FORMAL MANAGEMENT REVIEW & APPROVAL SIGN-OFF").font = font_section
    curr_row += 1
    headers_signoff = ["Role / Stakeholder", "Designation", "Sign-Off Status", "Signature / Timestamp", "Conditions / Notes"]
    for c_idx, h in enumerate(headers_signoff, 1):
        ws1.cell(row=curr_row, column=c_idx, value=h)
    style_header_row(ws1, curr_row, fill_navy)
    curr_row += 1

    signoff_rows = [
        ("Technical Lead / Author", "Engineering Lead (HBD Automation)", "COMPLETED & SUBMITTED", "Automated Architecture Plan", "Ready for technical review"),
        ("Database Administrator (DBA)", "Production Infrastructure Lead", "PENDING REVIEW", "[ Pending Verification ]", "Verify index impact & buffer pool allocation"),
        ("Engineering Manager / Project Manager", "Product & Operations Manager", "PENDING APPROVAL", "[ Signature Required ]", "Final authorization to execute sync script"),
        ("CityHangaround Platform Owner", "External System Stakeholder", "PENDING REVIEW", "[ Stakeholder Acknowledged ]", "Review affiliate_products & bridge ingestion")
    ]
    for r in signoff_rows:
        for c_idx, val in enumerate(r, 1):
            cell = ws1.cell(row=curr_row, column=c_idx, value=val)
            cell.font = font_body_bold if c_idx in [1, 3] else font_body
            cell.border = thin_border
            if val == "COMPLETED & SUBMITTED":
                cell.fill = fill_green_light
            elif "PENDING" in val:
                cell.fill = fill_yellow
        ws1.row_dimensions[curr_row].height = 24
        curr_row += 1

    auto_fit_columns(ws1, 6)

    # =========================================================================
    # TAB 2: TABLE CROSSWALK REGISTRY
    # =========================================================================
    ws2 = wb.create_sheet(title="Table Crosswalk Registry")
    ws2.views.sheetView[0].showGridLines = True

    ws2.cell(row=1, column=1, value="Comprehensive Enterprise Table Crosswalk Registry").font = font_title
    ws2.cell(row=2, column=1, value="Mapping All 22 Source Tables to CityHangaround Production Entities").font = font_subtitle

    headers_reg = [
        "Sync Seq", "Functional Domain", "Source Table (HBD System)", "Source Scope & Est Volume",
        "Target Table (CityHangaround)", "Target Scope / Est Volume", "Relationship & Strategy",
        "Key Dependency", "Operational Notes"
    ]
    for c_idx, h in enumerate(headers_reg, 1):
        ws2.cell(row=4, column=c_idx, value=h)
    style_header_row(ws2, 4, fill_slate)

    registry_data = [
        (1, "Geography", "Location_Master_India", "4,000+ Verified Cities", "countries", "250 Countries", "Master Cache Lookup", "None", "Cache country_id (India = 101)"),
        (2, "Geography", "Location_Master_India", "36 States & UTs", "states", "36 Indian States", "Master Cache / Lookup", "countries", "Lookup state_id by ISO code or state name"),
        (3, "Geography", "Location_Master_India", "Distinct Cities", "cities", "28,368 Active Cities", "Lookup or Safe Insert", "states", "Match (lower(city), state_id); auto-create missing"),
        (4, "Geography", "Location_Master_India", "Pincode/Area dataset", "areas", "562,173 Areas", "Lookup / Child Insert", "cities", "Match (lower(area), city_id); auto-create if missing"),
        (5, "Taxonomy", "master_categories", "800+ Standard Business Cats", "categories", "47,752 Categories", "Hierarchical Upsert", "None", "Tree sync: Parent categories first, then child subcats"),
        (6, "Taxonomy", "product_category_master", "23k+ E-Comm Taxonomies", "page_product_categories", "23,876 E-Comm Categories", "Direct 1:1 Schema Upsert", "None", "Exact match: category_key, category_path, level"),
        (7, "Bridge (P1)", "business_product_category_mappings", "Reviewed Cross-Taxonomy Map", "page_category_product_category", "0 Rows (Ready for Ingestion)", "Direct Bridge Insert", "categories, page_product_categories", "P1 Goal: Activates product discovery on business categories"),
        (8, "Directory", "master_table / listing_master", "460k+ Scraped Businesses", "pages", "461,994 Businesses", "Idempotent Upsert", "cities, categories", "Key bridge: pages.db_primary_id = master_table.id"),
        (9, "Directory", "master_table (Category tags)", "Business-Category Links", "page_category", "943,539 Links", "Pivot Table Upsert", "pages, categories", "Many-to-many relationship: (page_id, category_id)"),
        (10, "Directory", "master_table (Raw Timings)", "Parsed Opening Schedules", "page_hours", "Child Rows (Days 1-7)", "Child Replace/Insert", "pages", "Normalized schedule: day, open_time, close_time"),
        (11, "Products (Raw)", "amazon_products", "1.6M+ Scraped SKUs", "product_master (Consolidated)", "Consolidated E-Comm Hub", "Chunked SQL Batch Sync", "None", "Consolidation step: ASIN, title, brand, price, bullets"),
        (12, "Products (Raw)", "flipkart_products_new", "200k+ Flipkart Products", "product_master (Consolidated)", "Consolidated E-Comm Hub", "Direct SQL Upsert", "None", "Consolidation step: product_id, brand, mrp, discount"),
        (13, "Products (Raw)", "zepto / blinkit / dmart", "Quick Commerce Grocery SKUs", "product_master (Consolidated)", "Consolidated E-Comm Hub", "Direct SQL Upsert", "None", "Consolidation step: Grocery items, unit quantity, MRP"),
        (14, "Products (Raw)", "bigbasket / indiamart / jiomart", "B2B & Hyperlocal Catalog", "product_master (Consolidated)", "Consolidated E-Comm Hub", "Direct SQL Upsert", "None", "Consolidation step: SKU IDs, manufacturer, specs"),
        (15, "Products (Clean)", "uncleaned_product_master_table", "Quarantined Products", "Local Quarantine Log", "Audit / Manual Review", "Quality Filter Gate", "product_master", "Items failing price, ASIN or category rules quarantined"),
        (16, "Products (Sync)", "product_master (Cleaned)", "Verified Multi-Marketplace Catalog", "affiliate_products", "Live Multi-Vendor Feed", "Chunked Stream Upsert", "page_product_categories", "Direct feed: (source, source_product_id) unique index"),
        (17, "Products (Store)", "product_master (Store Inventory)", "Merchant Store Products", "page_products / product_catalogue", "Merchant Store Products", "Child Ingestion", "pages, cities, areas", "In-store catalog attached to verified physical pages"),
        (18, "Directory", "master_table (Custom specs)", "Dynamic Business Attributes", "page_attributes / page_attribute_values", "Dynamic Specification Store", "Key-Value Upsert", "pages, categories", "WiFi, AC, Parking, Payment modes")
    ]

    for row_idx, r_data in enumerate(registry_data, 5):
        for col_idx, val in enumerate(r_data, 1):
            cell = ws2.cell(row=row_idx, column=col_idx, value=val)
            cell.font = font_body_bold if col_idx in [1, 2, 3, 5] else font_body
            cell.border = thin_border
            if row_idx % 2 == 0:
                cell.fill = fill_zebra
        ws2.row_dimensions[row_idx].height = 24

    auto_fit_columns(ws2)

    # =========================================================================
    # TAB 3: PRODUCT MASTER & MARKETPLACES (ALL 8 PLATFORMS)
    # =========================================================================
    ws3 = wb.create_sheet(title="Product Master & Marketplaces")
    ws3.views.sheetView[0].showGridLines = True

    ws3.cell(row=1, column=1, value="Multi-Marketplace Scraped Product Architecture").font = font_title
    ws3.cell(row=2, column=1, value="Detailed Platform Analysis: 8 Scraper Tables, Consolidation Engine, and Cleaning Pipeline").font = font_subtitle

    ws3.cell(row=4, column=1, value="1. SOURCE PLATFORM INGESTION MATRIX (8 MARKETPLACES)").font = font_section

    headers_pforms = [
        "Platform", "Source Table Name", "Primary Identifier", "Key Product Columns Available",
        "Category / Hierarchy Columns", "Price & Offer Fields", "Rich Media & Variant Data", "Volume / Characteristics"
    ]
    for c_idx, h in enumerate(headers_pforms, 1):
        ws3.cell(row=5, column=c_idx, value=h)
    style_header_row(ws3, 5, fill_purple)

    pforms_data = [
        ("Amazon", "amazon_products", "ASIN (Unique String)", "Product_name, Brand, Seller, Manufacturer_Name, description", "category, subcategory, sub_sub_category, category_sub_sub_sub", "price, rating, Number_of_ratings", "Image_URLs, size_options, colour, About_the_items_bullet, JSON details", "1.6M+ items; Massive depth; Chunked sync (100k batches)"),
        ("Flipkart", "flipkart_products_new", "product_id (Unique String)", "product_name, brand, spec_bullets", "main_category, subcategory, leaf_category", "price, mrp, discount, rating, reviews", "image_url, product_url", "200k+ electronics, fashion & FMCG items"),
        ("Zepto", "zepto", "sku_id (Unique String)", "product_name, product_description, quantity", "main_category, subcategory", "mrp, selling_price, rating, review", "product_url, image_url", "Quick-commerce grocery; Rapid price/stock volatility"),
        ("Blinkit", "blinkit", "product_id (BigInteger)", "product_name, brand, quantity, availability", "category, sub_category, category_id", "price, mrp, discount", "image_url, product_url", "Hyperlocal grocery catalog; 10-minute delivery inventory"),
        ("DMart", "dmart_products", "ASIN (String)", "Product_name, Brand, quantity, availability", "category, category_id (FK dmart_categories)", "price, listPrice", "Image_URLs, link", "FMCG, household grocery; High MRP discount margin"),
        ("BigBasket", "bigbasket", "sku_id (String) / id", "product_name, brand, type, description", "category, sub_category", "sale_price, market_price, rating", "product_url", "Comprehensive grocery and staples database"),
        ("IndiaMART", "indiamart_products", "asin (String)", "product_name, manufacturer, location, description", "category_name, sub_category_name", "price_numeric, Price, stars, reviews", "productUrl, imgUrl, badges", "B2B wholesale, industrial equipment & bulk suppliers"),
        ("JioMart", "jiomart_products", "sku_id (String)", "product_name, brand, quantity, size", "category_id (FK jiomart_categories)", "price, mrp", "image_url, product_url", "Retail grocery & electronics catalog")
    ]

    curr_row = 6
    for r in pforms_data:
        for c_idx, val in enumerate(r, 1):
            cell = ws3.cell(row=curr_row, column=c_idx, value=val)
            cell.font = font_body_bold if c_idx in [1, 2, 3] else font_body
            cell.border = thin_border
            if curr_row % 2 == 1:
                cell.fill = fill_zebra
        ws3.row_dimensions[curr_row].height = 26
        curr_row += 1

    curr_row += 1
    ws3.cell(row=curr_row, column=1, value="2. CONSOLIDATION ENGINE & PIPELINE (sync_to_product_master.py)").font = font_section
    curr_row += 1

    headers_cons = [
        "Consolidated Column (product_master)", "Target Data Type", "Amazon Mapping", "Flipkart Mapping",
        "Zepto / Blinkit Mapping", "DMart / BigBasket Mapping", "IndiaMART / JioMart Mapping"
    ]
    for c_idx, h in enumerate(headers_cons, 1):
        ws3.cell(row=curr_row, column=c_idx, value=h)
    style_header_row(ws3, curr_row, fill_teal)
    curr_row += 1

    cons_mappings = [
        ("marketplace_name", "VARCHAR(100)", "'Amazon'", "'Flipkart'", "'Zepto' / 'Blinkit'", "'DMart' / 'BigBasket'", "'IndiaMART' / 'JioMart'"),
        ("asin", "VARCHAR(100)", "ASIN", "product_id", "sku_id / product_id", "ASIN / sku_id", "asin / sku_id"),
        ("product_name", "TEXT", "Product_name", "product_name", "product_name", "Product_name / product", "product_name"),
        ("brand", "VARCHAR(255)", "Brand (or first word of title)", "brand", "SUBSTRING_INDEX(product_name, ' ', 1)", "Brand / brand", "manufacturer / brand"),
        ("price", "DECIMAL(12,2)", "CAST(price AS DECIMAL)", "price", "selling_price / price", "price / sale_price", "price_numeric / price"),
        ("list_price (MRP)", "DECIMAL(12,2)", "listPrice", "mrp", "mrp", "listPrice / market_price", "mrp"),
        ("discount", "VARCHAR(50)", "Computed: ((MRP-Price)/MRP)%", "discount", "Computed: ((mrp-price)/mrp)%", "Computed discount", "Computed discount"),
        ("stars", "FLOAT", "rating", "rating", "rating / NULL", "NULL / rating", "stars / NULL"),
        ("reviews", "INTEGER", "Number_of_ratings", "Cleaned numeric reviews", "review / NULL", "NULL / NULL", "reviews / NULL"),
        ("is_best_seller", "VARCHAR(50)", "isBestSeller", "NULL", "NULL", "NULL", "badges (contains best seller)"),
        ("bought_in_last_month", "INTEGER", "boughtInLastMonth", "NULL", "NULL", "NULL", "NULL"),
        ("availability", "VARCHAR(50)", "'In Stock'", "'In Stock'", "'In Stock'", "IF(availability=1, 'In Stock', 'Out of Stock')", "'In Stock'"),
        ("category_name", "VARCHAR(255)", "category", "main_category", "main_category / category", "category", "category_name"),
        ("sub_category_name", "VARCHAR(255)", "subcategory", "subcategory", "subcategory / sub_category", "NULL / sub_category", "sub_category_name"),
        ("img_url", "TEXT", "Image_URLs", "image_url", "image_url", "Image_URLs / NULL", "imgUrl / image_url"),
        ("product_url", "TEXT", "link", "product_url", "product_url", "link / product_url", "productUrl / product_url"),
        ("description", "TEXT", "description", "spec_bullets", "product_description", "NULL / description", "description"),
        ("cleaning_status", "VARCHAR(50)", "'PENDING'", "'PENDING'", "'PENDING'", "'PENDING'", "'PENDING'")
    ]

    for r in cons_mappings:
        for c_idx, val in enumerate(r, 1):
            cell = ws3.cell(row=curr_row, column=c_idx, value=val)
            cell.font = font_code if c_idx in [1, 2] else font_body
            cell.border = thin_border
            if curr_row % 2 == 1:
                cell.fill = fill_zebra
        ws3.row_dimensions[curr_row].height = 22
        curr_row += 1

    curr_row += 1
    ws3.cell(row=curr_row, column=1, value="3. QUALITY FILTERING, DEDUPLICATION & QUARANTINE RULES (data_cleaning_service.py)").font = font_section
    curr_row += 1

    headers_clean = ["Rule ID", "Quality Dimension", "Validation Check", "Failure Action", "Quarantine Destination", "Business Impact"]
    for c_idx, h in enumerate(headers_clean, 1):
        ws3.cell(row=curr_row, column=c_idx, value=h)
    style_header_row(ws3, curr_row, fill_slate)
    curr_row += 1

    clean_rules = [
        ("PRD-01", "Identifier Integrity", "asin / SKU MUST NOT be null or empty", "Quarantine Record", "uncleaned_product_master_table", "Prevents unidentifiable orphaned products"),
        ("PRD-02", "Price Validity", "price MUST be > 0 and price <= list_price (if MRP exists)", "Flag Anomaly / Quarantine", "uncleaned_product_master_table", "Prevents display of Rs. 0 or impossible negative discounts"),
        ("PRD-03", "Title Length", "product_name length MUST be between 3 and 1000 characters", "Trim / Reject if too short", "uncleaned_product_master_table", "Eliminates broken scraper titles and scrape errors"),
        ("PRD-04", "Category Verification", "category_name MUST match product_category_master", "Mark UNMATCHED_CATEGORY", "unmatched_data_review", "Ensures products map to valid CityHangaround taxonomies"),
        ("PRD-05", "Deduplication", "Exact match on (marketplace_name, asin)", "UPSERT: Update latest price/stock", "duplicate_records_review", "Ensures prices stay fresh without duplicating product records"),
        ("PRD-06", "Image URL Validation", "img_url must start with http/https and have valid extension", "Fallback placeholder image", "None (Auto-remediated)", "Prevents broken image icons on frontend cards")
    ]

    for r in clean_rules:
        for c_idx, val in enumerate(r, 1):
            cell = ws3.cell(row=curr_row, column=c_idx, value=val)
            cell.font = font_body_bold if c_idx in [1, 2] else font_body
            cell.border = thin_border
            if c_idx == 4 and "Quarantine" in val:
                cell.fill = fill_red_light
            elif c_idx == 4 and "UPSERT" in val:
                cell.fill = fill_green_light
        ws3.row_dimensions[curr_row].height = 22
        curr_row += 1

    auto_fit_columns(ws3)

    # =========================================================================
    # TAB 4: AFFILIATE & CATALOG SYNC MAP (To CityHangaround)
    # =========================================================================
    ws4 = wb.create_sheet(title="Affiliate & Catalog Sync Map")
    ws4.views.sheetView[0].showGridLines = True

    ws4.cell(row=1, column=1, value="CityHangaround Affiliate & Catalog Ingestion Specification").font = font_title
    ws4.cell(row=2, column=1, value="Direct Mapping from Consolidated product_master to 'affiliate_products' and Master Catalog").font = font_subtitle

    headers_aff = [
        "Target Column (affiliate_products)", "Target Data Type", "Nullable / Constraints",
        "Source Field (product_master / Scraper)", "Transformation & Business Logic", "Default / Fallback Value"
    ]
    for c_idx, h in enumerate(headers_aff, 1):
        ws4.cell(row=4, column=c_idx, value=h)
    style_header_row(ws4, 4, fill_navy)

    aff_mappings = [
        ("id", "BIGINT", "PRIMARY KEY NOT NULL", "Destination Auto-Increment", "PostgreSQL Identity sequence (never overwrite with source ID)", "AUTO_INCREMENT"),
        ("catalog_product_id", "BIGINT", "NOT NULL", "catalog_products.id", "Optional link to master catalog item; defaults to 0 if standalone", "0"),
        ("source", "VARCHAR(100)", "NOT NULL", "product_master.marketplace_name", "Direct copy: 'Amazon', 'Flipkart', 'Zepto', 'Blinkit', 'DMart', etc.", "Mandatory"),
        ("source_product_id", "VARCHAR(100)", "NOT NULL", "product_master.asin", "Direct copy: ASIN, SKU ID, or platform product identifier", "Mandatory"),
        ("affiliate_url", "TEXT", "NOT NULL", "product_master.product_url", "Marketplace product link or transformed affiliate tracking URL", "Mandatory"),
        ("mrp", "NUMERIC(10,2)", "NULLABLE", "product_master.list_price", "Parsed numeric MRP. NULL if not provided by source platform", "NULL"),
        ("offer_price", "NUMERIC(10,2)", "NULLABLE", "product_master.price", "Parsed numeric active selling price / deal price", "NULL"),
        ("currency", "CHARACTER(3)", "DEFAULT 'INR'", "Static / Config", "Standard Indian Rupee", "'INR'"),
        ("availability", "VARCHAR(30)", "NULLABLE", "product_master.availability", "Normalized availability: 'In Stock', 'Out of Stock', 'Available'", "'In Stock'"),
        ("average_rating", "NUMERIC(2,1)", "NULLABLE", "product_master.stars", "Numeric product rating between 1.0 and 5.0", "NULL"),
        ("total_reviews", "INTEGER", "NULLABLE", "product_master.reviews", "Total customer review count (sanitized integer)", "0"),
        ("commission_type", "VARCHAR(20)", "NULLABLE", "Affiliate Config", "Commission structure: 'percentage' or 'flat'", "NULL"),
        ("commission_value", "NUMERIC(10,2)", "NULLABLE", "Affiliate Config", "Agreed affiliate payout rate", "NULL"),
        ("click_count", "INTEGER", "DEFAULT 0 NOT NULL", "System Counter", "Initializes to 0 clicks", "0"),
        ("conversion_count", "INTEGER", "DEFAULT 0 NOT NULL", "System Counter", "Initializes to 0 conversions", "0"),
        ("last_synced_at", "TIMESTAMPTZ", "NULLABLE", "ETL Engine", "Timestamp of successful sync execution", "CURRENT_TIMESTAMP"),
        ("status", "VARCHAR(20)", "DEFAULT 'Active' NOT NULL", "product_master.cleaning_status", "Active if CLEANED; Inactive if QUARANTINED", "'Active'"),
        ("product_name", "TEXT", "NULLABLE", "product_master.product_name", "Cleaned product title without excess whitespace", "Mandatory"),
        ("brand", "VARCHAR(255)", "NULLABLE", "product_master.brand", "Extracted or mapped manufacturer brand", "NULL"),
        ("discount", "VARCHAR(50)", "NULLABLE", "product_master.discount", "Discount text (e.g., '25% OFF' or parsed percentage)", "NULL"),
        ("rating_count", "INTEGER", "NULLABLE", "product_master.reviews", "Customer rating count (maps to reviews)", "NULL"),
        ("is_prime", "BOOLEAN", "NULLABLE", "amazon_products.About_the_items_bullet", "True if Amazon Prime badge detected", "FALSE"),
        ("is_best_seller", "BOOLEAN", "NULLABLE", "product_master.is_best_seller", "Boolean cast: True if is_best_seller == 'true' or BestSeller", "FALSE"),
        ("bought_in_last_month", "INTEGER", "NULLABLE", "product_master.bought_in_last_month", "Social proof sales velocity counter", "0"),
        ("delivery_message", "TEXT", "NULLABLE", "Scraper metadata", "Delivery SLA (e.g. 'Get it by Tomorrow', 'In 10 mins')", "NULL"),
        ("deal_type", "VARCHAR(255)", "NULLABLE", "Scraper metadata", "Promotional deal badge (e.g. 'Deal of the Day', 'Limited Time')", "NULL"),
        ("coupon", "VARCHAR(255)", "NULLABLE", "Scraper metadata", "On-page coupon code or discount voucher text", "NULL"),
        ("description", "TEXT", "NULLABLE", "product_master.description", "Full product specs, HTML bullets or text description", "NULL"),
        ("manufacturer", "VARCHAR(255)", "NULLABLE", "amazon_products.Manufacturer_Name", "Manufacturer enterprise name (from Amazon/IndiaMART)", "NULL"),
        ("seller", "VARCHAR(255)", "NULLABLE", "amazon_products.Seller", "Marketplace merchant / seller entity", "NULL"),
        ("variants", "TEXT", "NULLABLE", "amazon_products (size_options, colour)", "JSON string or formatted text of available sizes and colors", "NULL"),
        ("badges", "TEXT", "NULLABLE", "indiamart_products.badges", "Verification badges (e.g. 'Verified Exporter', 'TrustSEAL')", "NULL"),
        ("category_name", "VARCHAR(255)", "NOT NULL", "product_master.category_name", "L1 Category name", "Mandatory"),
        ("sub_category_name", "VARCHAR(255)", "NULLABLE", "product_master.sub_category_name", "L2 Subcategory name", "NULL"),
        ("img_url", "TEXT", "NULLABLE", "product_master.img_url", "High-res primary thumbnail image URL", "NULL"),
        ("product_category_id", "BIGINT", "NOT NULL", "Resolved from page_product_categories.id", "CRITICAL FK: Resolved via (category_key, marketplace_name) lookup", "Resolved ID"),
        ("category_key", "VARCHAR(255)", "NULLABLE", "product_category_master.category_key", "Normalized category key slug for fast indexing", "NULL"),
        ("sub_category_key", "VARCHAR(255)", "NULLABLE", "product_category_master.category_key (L2)", "Subcategory slug key", "NULL"),
        ("cleaning_status", "VARCHAR(50)", "NULLABLE", "product_master.cleaning_status", "'CLEANED', 'VERIFIED'", "'CLEANED'"),
        ("product_service_id", "BIGINT", "NULLABLE", "product_catalogue.id", "Optional link if tied to a directory service listing", "NULL")
    ]

    for row_idx, r_data in enumerate(aff_mappings, 5):
        for col_idx, val in enumerate(r_data, 1):
            cell = ws4.cell(row=row_idx, column=col_idx, value=val)
            cell.font = font_code if col_idx in [1, 2] else font_body
            cell.border = thin_border
            if col_idx == 1 and "id" == val:
                cell.fill = fill_yellow
            elif col_idx == 1 and "product_category_id" == val:
                cell.fill = fill_green_light
            elif row_idx % 2 == 0:
                cell.fill = fill_zebra
        ws4.row_dimensions[row_idx].height = 22

    auto_fit_columns(ws4)

    # =========================================================================
    # TAB 5: GEOGRAPHY & LOCATION MAP
    # =========================================================================
    ws5 = wb.create_sheet(title="Geography & Location Map")
    ws5.views.sheetView[0].showGridLines = True

    ws5.cell(row=1, column=1, value="Geography & Administrative Hierarchy Mapping").font = font_title
    ws5.cell(row=2, column=1, value="Resolving 4,000+ Indian Cities & 560k+ Areas into CityHangaround without ID Overwrites").font = font_subtitle

    headers_geo = [
        "Entity Level", "Source Column (Location_Master_India)", "Target Table",
        "Target Column", "Matching / Lookup Strategy", "ID Resolution Logic", "Collision Prevention"
    ]
    for c_idx, h in enumerate(headers_geo, 1):
        ws5.cell(row=4, column=c_idx, value=h)
    style_header_row(ws5, 4, fill_slate)

    geo_data = [
        ("Country", "country_name ('India')", "countries", "name / iso2 ('IN')", "Exact match on country code / name", "Cache countries.id (India = 101)", "Read-only lookup. Never insert/update country."),
        ("State", "state_full_name", "states", "name", "Case-insensitive name match", "Cache (lower(state_name)) -> state_id", "Pre-populated 36 Indian states. Read-only lookup."),
        ("State Code", "state_short_code (e.g. 'GJ', 'MH')", "states", "iso2 / state_code", "Exact match on 2-letter ISO state code", "Fallback match if state_full_name differs", "Guarantees state accuracy even with naming variations."),
        ("City", "city_name (e.g. 'Ahmedabad')", "cities", "name", "Natural Compound Key: (LOWER(city_name), state_id)", "Lookup in memory; if found use existing city_id", "Prevents duplicate city records in existing 28,368 cities."),
        ("City (Missing)", "city_name (New scraped city)", "cities", "name, slug, state_id, country_id", "INSERT INTO cities (...) RETURNING id", "New auto-increment id allocated by PostgreSQL", "Zero collision: DB sequence creates unique ID."),
        ("Area / Ward", "area_name (e.g. 'Navrangpura')", "areas", "name", "Natural Compound Key: (LOWER(area_name), city_id)", "Lookup in memory; if found use area_id", "CityHangaround has 562,173 areas; reuse existing."),
        ("Area (Missing)", "area_name (New area)", "areas", "name, slug, city_id, status", "INSERT INTO areas (...) RETURNING id", "New auto-increment id allocated by PostgreSQL", "Attached to correct parent city_id."),
        ("Pincode", "pincode (6-digit postal code)", "areas / pages", "postal_code", "Stored on area or directly on business listing", "Regex validation: ^[1-9][0-9]{5}$", "Invalid pincodes stripped to prevent data corruption.")
    ]

    for row_idx, r_data in enumerate(geo_data, 5):
        for col_idx, val in enumerate(r_data, 1):
            cell = ws5.cell(row=row_idx, column=col_idx, value=val)
            cell.font = font_body_bold if col_idx in [1, 3] else font_body
            cell.border = thin_border
            if row_idx % 2 == 0:
                cell.fill = fill_zebra
        ws5.row_dimensions[row_idx].height = 24

    auto_fit_columns(ws5)

    # =========================================================================
    # TAB 6: BUSINESS LISTINGS (PAGES) MAP
    # =========================================================================
    ws6 = wb.create_sheet(title="Business Listings (Pages) Map")
    ws6.views.sheetView[0].showGridLines = True

    ws6.cell(row=1, column=1, value="Local Business Listings (pages) Detailed Field Mapping").font = font_title
    ws6.cell(row=2, column=1, value="37 Column Crosswalk from master_table / listing_master to CityHangaround 'pages'").font = font_subtitle

    headers_pages = [
        "CityHangaround Column", "Data Type", "Constraints", "Source Column (HBD System)",
        "Transformation & Formatting Logic", "Default / Fallback Rule"
    ]
    for c_idx, h in enumerate(headers_pages, 1):
        ws6.cell(row=4, column=c_idx, value=h)
    style_header_row(ws6, 4, fill_navy)

    pages_columns = [
        ("id", "BIGINT", "PRIMARY KEY NOT NULL", "Destination Auto-Increment", "PostgreSQL Identity sequence (NEVER overwritten with source ID)", "AUTO_INCREMENT"),
        ("db_primary_id", "BIGINT", "UNIQUE INDEX", "master_table.id", "CRITICAL KEY: Stores our source integer ID. Enables idempotent sync", "Mandatory (Source ID)"),
        ("title", "VARCHAR(255)", "NOT NULL", "master_table.business_name", "Cleaned business title, trimmed of extra whitespace and emojis", "Mandatory"),
        ("slug", "VARCHAR(255)", "NOT NULL", "master_table.business_name", "URL slug: slugify(business_name) + '-' + db_primary_id for uniqueness", "Generated unique slug"),
        ("phone", "VARCHAR(50)", "NULLABLE", "master_table.primary_phone", "Cleaned 10-digit Indian mobile or landline (+91 prefix optional)", "NULL if invalid"),
        ("secondary_phone", "VARCHAR(50)", "NULLABLE", "master_table.secondary_phone", "Validated secondary phone number", "NULL"),
        ("email", "VARCHAR(255)", "NULLABLE", "master_table.email", "Validated email format regex: [^@]+@[^@]+\\.[^@]+", "NULL if invalid"),
        ("website", "VARCHAR(500)", "NULLABLE", "master_table.website", "Validated HTTP/HTTPS URL", "NULL if invalid"),
        ("address", "TEXT", "NULLABLE", "master_table.address", "Full address string", "NULL"),
        ("country_id", "BIGINT", "NOT NULL", "Resolved Country ID", "Resolved ID for India (101)", "101"),
        ("state_id", "BIGINT", "NOT NULL", "Resolved State ID", "Resolved from states table via state_name / state_code lookup", "Resolved state_id"),
        ("city_id", "BIGINT", "NOT NULL", "Resolved City ID", "Resolved from cities table via (lower(city), state_id) lookup", "Resolved city_id"),
        ("area_id", "BIGINT", "NULLABLE", "Resolved Area ID", "Resolved from areas table via (lower(area), city_id) lookup", "NULL if unmatched"),
        ("postal_code", "VARCHAR(20)", "NULLABLE", "master_table.pincode", "Validated 6-digit Indian pincode", "NULL"),
        ("latitude", "NUMERIC(10,8)", "NULLABLE", "master_table.latitude", "Valid coordinate: -90.0 <= lat <= 90.0", "NULL"),
        ("longitude", "NUMERIC(11,8)", "NULLABLE", "master_table.longitude", "Valid coordinate: -180.0 <= lon <= 180.0", "NULL"),
        ("description", "TEXT", "NULLABLE", "master_table.description", "Business description text", "NULL"),
        ("short_description", "VARCHAR(500)", "NULLABLE", "master_table.description", "First 300 characters of description", "NULL"),
        ("thumbnail_image", "TEXT", "NULLABLE", "master_table.image_url", "Primary storefront or logo image URL", "Default placeholder image"),
        ("gallery", "JSONB", "NULLABLE", "master_table.gallery_urls", "JSON array of additional photo URLs: [\"url1\", \"url2\"]", "'[]'::jsonb"),
        ("working_hours", "TEXT", "NULLABLE", "master_table.opening_hours", "Raw schedule text (e.g., 'Mon-Sat: 10:00 AM - 08:00 PM')", "NULL"),
        ("rating", "NUMERIC(2,1)", "DEFAULT 0", "master_table.rating", "Validated numeric rating (0.0 to 5.0)", "0.0"),
        ("reviews_count", "INTEGER", "DEFAULT 0", "master_table.review_count", "Sanitized integer count of customer reviews", "0"),
        ("is_claimed", "BOOLEAN", "DEFAULT false", "Static false", "All imported directory listings start unclaimed", "false"),
        ("is_verified", "BOOLEAN", "DEFAULT false", "Data Quality Engine", "Set to true if business has verified phone + address + location", "false"),
        ("is_active", "BOOLEAN", "DEFAULT true", "Status Flag", "Active and searchable on directory", "true"),
        ("status", "VARCHAR(20)", "DEFAULT 'Active'", "Status Flag", "'Active'", "'Active'"),
        ("created_at", "TIMESTAMPTZ", "DEFAULT NOW()", "master_table.created_at", "Source record creation timestamp", "CURRENT_TIMESTAMP"),
        ("updated_at", "TIMESTAMPTZ", "DEFAULT NOW()", "ETL Engine", "Last sync execution timestamp", "CURRENT_TIMESTAMP")
    ]

    for row_idx, r_data in enumerate(pages_columns, 5):
        for col_idx, val in enumerate(r_data, 1):
            cell = ws6.cell(row=row_idx, column=col_idx, value=val)
            cell.font = font_code if col_idx in [1, 2] else font_body
            cell.border = thin_border
            if col_idx == 1 and val == "db_primary_id":
                cell.fill = fill_yellow
            elif col_idx == 1 and "city_id" in val:
                cell.fill = fill_green_light
            elif row_idx % 2 == 0:
                cell.fill = fill_zebra
        ws6.row_dimensions[row_idx].height = 22

    auto_fit_columns(ws6)

    # =========================================================================
    # TAB 7: CATEGORY TAXONOMIES MAP
    # =========================================================================
    ws7 = wb.create_sheet(title="Category Taxonomies Map")
    ws7.views.sheetView[0].showGridLines = True

    ws7.cell(row=1, column=1, value="Taxonomy Crosswalk: Business & Product Categories").font = font_title
    ws7.cell(row=2, column=1, value="Hierarchical Alignment of master_categories and product_category_master").font = font_subtitle

    ws7.cell(row=4, column=1, value="1. BUSINESS CATEGORY TAXONOMY (master_categories -> categories)").font = font_section

    headers_bcat = [
        "Target Column (categories)", "Data Type", "Constraints",
        "Source Column (master_categories)", "Transformation & Tree Construction Logic", "Notes"
    ]
    for c_idx, h in enumerate(headers_bcat, 1):
        ws7.cell(row=5, column=c_idx, value=h)
    style_header_row(ws7, 5, fill_slate)

    bcat_data = [
        ("id", "BIGINT", "PRIMARY KEY NOT NULL", "Destination Auto-Increment", "PostgreSQL sequence (Never overwrite with source ID)", "Destination primary key"),
        ("name", "VARCHAR(150)", "NOT NULL", "master_categories.name", "Category name (trimmed, standardized casing)", "Match on LOWER(name) to reuse existing"),
        ("slug", "VARCHAR(150)", "NOT NULL", "master_categories.name", "URL slug: slugify(name)", "Unique indexing"),
        ("parent_id", "BIGINT", "NULLABLE FK", "Resolved parent_id", "Resolved ID of parent category in destination tree", "Level 1 has parent_id = NULL"),
        ("display_order", "INTEGER", "DEFAULT 0", "master_categories.level", "Display priority sorting", "Root categories ordered first"),
        ("status", "VARCHAR(20)", "DEFAULT 'Active'", "master_categories.is_active", "Map boolean: True -> 'Active', False -> 'Inactive'", "'Active'"),
        ("created_at", "TIMESTAMPTZ", "DEFAULT NOW()", "Audit Timestamp", "Creation timestamp", "CURRENT_TIMESTAMP")
    ]

    curr_row = 6
    for r in bcat_data:
        for c_idx, val in enumerate(r, 1):
            cell = ws7.cell(row=curr_row, column=c_idx, value=val)
            cell.font = font_code if c_idx in [1, 2] else font_body
            cell.border = thin_border
            if curr_row % 2 == 1:
                cell.fill = fill_zebra
        ws7.row_dimensions[curr_row].height = 22
        curr_row += 1

    curr_row += 1
    ws7.cell(row=curr_row, column=1, value="2. PRODUCT CATEGORY TAXONOMY (product_category_master -> page_product_categories)").font = font_section
    curr_row += 1

    headers_pcat = [
        "Target Column (page_product_categories)", "Data Type", "Constraints",
        "Source Column (product_category_master)", "Transformation & Tree Construction Logic", "Notes"
    ]
    for c_idx, h in enumerate(headers_pcat, 1):
        ws7.cell(row=curr_row, column=c_idx, value=h)
    style_header_row(ws7, curr_row, fill_teal)
    curr_row += 1

    pcat_data = [
        ("id", "BIGINT", "PRIMARY KEY NOT NULL", "Destination Auto-Increment", "PostgreSQL sequence", "Destination primary key"),
        ("name", "VARCHAR(150)", "NOT NULL", "product_category_master.category_name", "Primary product category name", "1:1 Schema Match"),
        ("slug", "VARCHAR(150)", "NOT NULL", "product_category_master.category_name", "slugify(category_name)", "URL friendly slug"),
        ("marketplace_name", "VARCHAR(100)", "NULLABLE", "product_category_master.marketplace_name", "Origin platform: 'Amazon', 'Flipkart', 'Blinkit', etc.", "Identifies taxonomy owner"),
        ("subcategory_name", "VARCHAR(255)", "NULLABLE", "product_category_master.subcategory_name", "Level 2 subcategory name", "1:1 Schema Match"),
        ("child_category_name", "VARCHAR(255)", "NULLABLE", "product_category_master.child_category_name", "Level 3 leaf category name", "1:1 Schema Match"),
        ("category_level", "INTEGER", "DEFAULT 1 NOT NULL", "product_category_master.category_level", "Numeric hierarchy depth (1, 2, or 3)", "1:1 Schema Match"),
        ("category_path", "TEXT", "NOT NULL", "product_category_master.category_path", "Full breadcrumb (e.g. 'Electronics > Audio > Headphones')", "1:1 Schema Match"),
        ("category_key", "VARCHAR(255)", "NOT NULL", "product_category_master.category_key", "Unique machine key: slugify(path)", "CRITICAL KEY FOR AFFILIATE SYNC"),
        ("status", "VARCHAR(20)", "DEFAULT 'Active' NOT NULL", "Static 'Active'", "All validated categories set to Active", "'Active'")
    ]

    for r in pcat_data:
        for c_idx, val in enumerate(r, 1):
            cell = ws7.cell(row=curr_row, column=c_idx, value=val)
            cell.font = font_code if c_idx in [1, 2] else font_body
            cell.border = thin_border
            if c_idx == 1 and val == "category_key":
                cell.fill = fill_yellow
            elif curr_row % 2 == 1:
                cell.fill = fill_zebra
        ws7.row_dimensions[curr_row].height = 22
        curr_row += 1

    auto_fit_columns(ws7)

    # =========================================================================
    # TAB 8: BUSINESS-PRODUCT BRIDGE (P1)
    # =========================================================================
    ws8 = wb.create_sheet(title="Business-Product Bridge (P1)")
    ws8.views.sheetView[0].showGridLines = True

    ws8.cell(row=1, column=1, value="P1 Priority Deliverable: Business-to-Product Bridge").font = font_title
    ws8.cell(row=2, column=1, value="Activating CityHangaround's Empty 'page_category_product_category' Table").font = font_subtitle

    ws8.cell(row=4, column=1, value="1. ARCHITECTURAL OVERVIEW & BUSINESS VALUE").font = font_section
    bridge_overview = (
        "CURRENT STATUS IN PRODUCTION: The table 'page_category_product_category' in CityHangaround currently contains 0 ROWS.\n"
        "THE GOAL: When users search for a local business category (e.g., 'Pet Shop' or 'Pharmacy'), CityHangaround needs to know which e-commerce\n"
        "products (e.g., 'Dog Food' or 'First Aid Supplies') are relevant to display.\n"
        "OUR ASSET: The HBD Automation team has already reviewed and approved mappings in 'category_mapping.business_product_category_mappings'.\n"
        "This sheet defines the exact ETL pipeline to activate this cross-selling bridge table in production."
    )
    ws8.cell(row=5, column=1, value=bridge_overview).font = font_body
    ws8.cell(row=5, column=1).alignment = Alignment(wrap_text=True)
    ws8.merge_cells(start_row=5, start_column=1, end_row=5, end_column=7)
    ws8.row_dimensions[5].height = 65

    ws8.cell(row=7, column=1, value="2. COLUMN CROSSWALK SPECIFICATION").font = font_section

    headers_bridge = [
        "Target Column (page_category_product_category)", "Target Data Type", "Constraints",
        "Source Column (business_product_category_mappings)", "ID Translation Logic", "Validation Rule"
    ]
    for c_idx, h in enumerate(headers_bridge, 1):
        ws8.cell(row=8, column=c_idx, value=h)
    style_header_row(ws8, 8, fill_purple)

    bridge_cols = [
        ("id", "BIGINT", "PRIMARY KEY NOT NULL", "Destination Sequence", "PostgreSQL sequence (Never copy source ID)", "AUTO_INCREMENT"),
        ("page_category_id", "BIGINT", "NOT NULL FK", "business_subcategory_id (or business_category_id)", "Resolve: Map source category ID -> CityHangaround categories.id", "Must exist in CityHangaround 'categories'"),
        ("product_category_id", "BIGINT", "NOT NULL FK", "product_category_id", "Resolve: Map source product category ID -> page_product_categories.id", "Must exist in 'page_product_categories'"),
        ("sort_order", "INTEGER", "DEFAULT 0 NOT NULL", "Derived from mapping priority", "Order of product relevance on business category page", "Default 0"),
        ("created_at", "TIMESTAMP", "NULLABLE", "business_product_category_mappings.created_at", "Source creation timestamp", "CURRENT_TIMESTAMP"),
        ("updated_at", "TIMESTAMP", "NULLABLE", "Audit Timestamp", "ETL ingestion timestamp", "CURRENT_TIMESTAMP")
    ]

    curr_row = 9
    for r in bridge_cols:
        for c_idx, val in enumerate(r, 1):
            cell = ws8.cell(row=curr_row, column=c_idx, value=val)
            cell.font = font_code if c_idx in [1, 2] else font_body
            cell.border = thin_border
            if c_idx == 1 and "id" in val and val != "id":
                cell.fill = fill_green_light
            elif curr_row % 2 == 1:
                cell.fill = fill_zebra
        ws8.row_dimensions[curr_row].height = 24
        curr_row += 1

    auto_fit_columns(ws8)

    # =========================================================================
    # TAB 9: MERCHANT PRODUCTS & STORE SPECS
    # =========================================================================
    ws9 = wb.create_sheet(title="Merchant Products & Store Specs")
    ws9.views.sheetView[0].showGridLines = True

    ws9.cell(row=1, column=1, value="Merchant In-Store Products, Operating Hours & Dynamic Attributes").font = font_title
    ws9.cell(row=2, column=1, value="Mapping Local Store Catalog (page_products), Schedules (page_hours), and Custom Attributes").font = font_subtitle

    ws9.cell(row=4, column=1, value="1. MERCHANT IN-STORE PRODUCT CATALOG (page_products & product_catalogue)").font = font_section

    headers_mprod = [
        "Target Column (page_products)", "Data Type", "Constraints",
        "Source Field (Store Inventory)", "Transformation & Business Rule", "Default Value"
    ]
    for c_idx, h in enumerate(headers_mprod, 1):
        ws9.cell(row=5, column=c_idx, value=h)
    style_header_row(ws9, 5, fill_navy)

    mprod_data = [
        ("id", "BIGINT", "PRIMARY KEY NOT NULL", "Destination Sequence", "PostgreSQL Identity sequence", "AUTO_INCREMENT"),
        ("page_id", "BIGINT", "NOT NULL FK", "pages.id", "CRITICAL FK: Resolved CityHangaround business listing ID", "Mandatory FK"),
        ("category_id", "BIGINT", "NULLABLE FK", "categories.id", "Product category within the store", "Resolved category_id"),
        ("type", "VARCHAR(20)", "DEFAULT 'Product' NOT NULL", "Static 'Product'", "'Product' or 'Service'", "'Product'"),
        ("title", "VARCHAR(255)", "NOT NULL", "Product Title", "Store item name", "Mandatory"),
        ("slug", "VARCHAR(255)", "NOT NULL", "Product Title", "slugify(title) + '-' + page_id", "Unique slug"),
        ("thumbnail_image", "TEXT", "NOT NULL", "Image URL", "Store item photo URL", "Placeholder image"),
        ("mrp", "NUMERIC(10,2)", "NOT NULL", "MRP", "Maximum retail price", "0.00"),
        ("offer_price", "NUMERIC(10,2)", "NOT NULL", "Selling Price", "Actual in-store price", "0.00"),
        ("brand", "VARCHAR(150)", "NULLABLE", "Brand Name", "Manufacturer / brand", "NULL"),
        ("city_id", "BIGINT", "NOT NULL FK", "pages.city_id", "Inherited from parent business page", "Inherited from page"),
        ("area_id", "BIGINT", "NOT NULL FK", "pages.area_id", "Inherited from parent business page", "Inherited from page"),
        ("status", "VARCHAR(20)", "DEFAULT 'Active' NOT NULL", "Inventory Status", "'Active' if in stock, else 'Inactive'", "'Active'"),
        ("catalog_item_id", "BIGINT", "NULLABLE FK", "catalog_items.id", "Optional link to universal master item", "NULL")
    ]

    curr_row = 6
    for r in mprod_data:
        for c_idx, val in enumerate(r, 1):
            cell = ws9.cell(row=curr_row, column=c_idx, value=val)
            cell.font = font_code if c_idx in [1, 2] else font_body
            cell.border = thin_border
            if c_idx == 1 and val in ["page_id", "city_id"]:
                cell.fill = fill_green_light
            elif curr_row % 2 == 1:
                cell.fill = fill_zebra
        ws9.row_dimensions[curr_row].height = 22
        curr_row += 1

    curr_row += 1
    ws9.cell(row=curr_row, column=1, value="2. BUSINESS OPERATING HOURS SCHEDULE (page_hours)").font = font_section
    curr_row += 1

    headers_hours = ["Target Column (page_hours)", "Data Type", "Constraints", "Source Logic", "Transformation Rule", "Default Value"]
    for c_idx, h in enumerate(headers_hours, 1):
        ws9.cell(row=curr_row, column=c_idx, value=h)
    style_header_row(ws9, curr_row, fill_slate)
    curr_row += 1

    hours_data = [
        ("id", "BIGINT", "PRIMARY KEY NOT NULL", "Destination Sequence", "PostgreSQL sequence", "AUTO_INCREMENT"),
        ("page_id", "BIGINT", "NOT NULL FK", "pages.id", "CRITICAL FK: Parent business page ID", "Mandatory FK"),
        ("day", "SMALLINT", "NOT NULL (1-7)", "Day of Week", "1 = Monday, 2 = Tuesday, ..., 7 = Sunday", "1 to 7"),
        ("open_time", "TIME", "NULLABLE", "Parsed Opening Time", "Extracted 24-hr time: HH:MM:SS (e.g., '10:00:00')", "NULL if closed"),
        ("close_time", "TIME", "NULLABLE", "Parsed Closing Time", "Extracted 24-hr time: HH:MM:SS (e.g., '20:00:00')", "NULL if closed"),
        ("is_closed", "BOOLEAN", "DEFAULT false NOT NULL", "Parsed Schedule", "True if marked 'Closed', 'Sunday Closed', etc.", "false")
    ]

    for r in hours_data:
        for c_idx, val in enumerate(r, 1):
            cell = ws9.cell(row=curr_row, column=c_idx, value=val)
            cell.font = font_code if c_idx in [1, 2] else font_body
            cell.border = thin_border
            if curr_row % 2 == 1:
                cell.fill = fill_zebra
        ws9.row_dimensions[curr_row].height = 22
        curr_row += 1

    auto_fit_columns(ws9)

    # =========================================================================
    # TAB 10: SYNC ENGINE & OPERATIONS PLAN
    # =========================================================================
    ws10 = wb.create_sheet(title="Sync Engine & Operations Plan")
    ws10.views.sheetView[0].showGridLines = True

    ws10.cell(row=1, column=1, value="End-to-End ETL Synchronization & Operational Rollout Plan").font = font_title
    ws10.cell(row=2, column=1, value="Phase-by-Phase Technical Procedure for Safe Production Data Sync").font = font_subtitle

    headers_ops = [
        "Phase", "Stage Name", "Target Table(s)", "Pre-Flight Checks & Actions",
        "Rollback / Safety Mechanism", "Success Criteria & Metrics"
    ]
    for c_idx, h in enumerate(headers_ops, 1):
        ws10.cell(row=4, column=c_idx, value=h)
    style_header_row(ws10, 4, fill_navy)

    ops_data = [
        ("Phase 1", "Environment & Permission Verification", "All target tables", "Run read-only check on CityHangaround schema. Verify PostgreSQL user permissions (SELECT, INSERT, UPDATE). Check pg_stat_activity to ensure zero blocking locks.", "Abort immediately if write permissions or schema drift detected.", "100% table presence confirmed; Zero schema drift."),
        ("Phase 2", "In-Memory Master Caching", "countries, states, cities, areas", "Pre-load existing 28k cities and 560k areas into memory hash-map: (lower(name), parent_id) -> id. Verify RAM footprint (< 250MB).", "Engine aborts if memory exceeds limit or DB query times out.", "Zero lookup query overhead during streaming sync."),
        ("Phase 3", "Category & Taxonomy Ingestion", "categories, page_product_categories", "Sync root categories (level 1) first, then child subcategories. Validate slug uniqueness. Ensure parent_id correctly matches newly inserted parent IDs.", "Transaction rollback per category tree block if foreign key breaks.", "All 800+ business categories and 23k+ e-comm categories synced."),
        ("Phase 4", "Business-Product Bridge Activation (P1)", "page_category_product_category", "Transform 'business_product_category_mappings' into destination bridge rows using cached category_id and product_category_id.", "Atomic transaction: rollback on FK mismatch.", "Table populated from 0 rows; Product discovery enabled."),
        ("Phase 5", "Business Directory Sync (Pages)", "pages, page_category, page_hours", "Stream business listings in batches of 500 rows. Use 'ON CONFLICT (db_primary_id) DO UPDATE'. Immediately propagate page_category and page_hours.", "Batch-level savepoints; Failed records routed to Dead Letter Queue (DLQ).", "460k+ businesses synced with 100% idempotent updates."),
        ("Phase 6", "Marketplace Consolidation & Cleaning", "product_master, uncleaned_product_master_table", "Execute 'sync_to_product_master.py' across all 8 scraper platforms. Run 'data_cleaning_service.py' to quarantine invalid prices and missing SKUs.", "Quarantine table isolates anomalies without stopping pipeline.", "Consolidated product catalog cleaned and ready for affiliate feed."),
        ("Phase 7", "Affiliate Products Sync (Streaming)", "affiliate_products", "Stream verified products from product_master in 50,000-row chunks. Resolve product_category_id via category_key. Upsert using (source, source_product_id).", "Chunked transactions; Checkpoint tracking per 50k batch.", "Multi-million affiliate catalog populated with zero downtime."),
        ("Phase 8", "Post-Sync Audit & Reconciliation", "All tables", "Run reconciliation script comparing source row counts vs. target row counts. Check index health (REINDEX if needed). Run ANALYZE on PostgreSQL.", "Full audit report exported to management. No rollbacks needed.", "Manager sign-off completed; Production verification PASS.")
    ]

    for row_idx, r_data in enumerate(ops_data, 5):
        for col_idx, val in enumerate(r_data, 1):
            cell = ws10.cell(row=row_idx, column=col_idx, value=val)
            cell.font = font_body_bold if col_idx in [1, 2] else font_body
            cell.border = thin_border
            if col_idx == 1 and val in ["Phase 4", "Phase 7"]:
                cell.fill = fill_green_light
            elif row_idx % 2 == 0:
                cell.fill = fill_zebra
        ws10.row_dimensions[row_idx].height = 36

    auto_fit_columns(ws10)

    # Save workbook
    output_filename = "CityHangaround_Production_Data_Sync_and_Mapping_Master.xlsx"
    wb.save(output_filename)
    print(f"Successfully generated expanded 10-sheet master workbook: {output_filename}")

if __name__ == "__main__":
    build_master_sync_workbook()
