"""
The Data Enrichment team's own documentation, kept as data so the dashboard
can show it next to the LIVE database numbers.

Sources (all written by the team - nothing here is invented):
  * "Data enrichment tables" sheet   -> RAW_SOURCES / PRODUCT_SOURCES / EMPTY_GROUPS
  * 01 Final Data Enrichment Master Report          -> PROCESS_STEPS, PROCESS_KEY_POINTS
  * 02 Dynamic URL Extraction and CSV Enrichment     -> URL_* constants
  * 03 State match / Missing regions / Missing area /
       Location master data matching reports         -> LOCATION_DOCS
  * 04 Location Master Data Report                   -> LOCATION_RANK_DOC

"sheet_count" is the number written in the sheet. The dashboard always shows
the live row count from the database beside it; the sheet number is never
used as if it were live.

To update: edit the lists below (one dict per row of the sheet) and redeploy.
"""

import re


def _num(text):
    """'2,53,346' -> 253346 ; '1663951 lakh' -> 1663951 ; '' -> None"""
    digits = re.sub(r"[^\d]", "", str(text or ""))
    return int(digits) if digits else None


def _src(group, subgroup, table, detail, count_text, done_by, remarks, notes=(), candidates=()):
    return {
        "group": group, "subgroup": subgroup, "table": table, "candidates": [table, *candidates],
        "detail": detail, "sheet_count_text": count_text, "sheet_count": _num(count_text),
        "done_by": done_by, "sheet_remarks": remarks, "sheet_notes": list(notes),
    }


# ─── "Data enrichment tables" sheet - raw group ─────────────────────────────
RAW_SOURCES = [
    _src("raw", "school", "raw_schools",
         "Exhaustive UDISE+ government database of all Indian primary and secondary schools with detailed "
         "administrative hierarchies (village, block, district).",
         "1663951 lakh", "Prachi",
         "Lacks exact Lat/Long coordinates; mapping this to our database will require heavy text-based data cleaning.",
         notes=["Sheet says '1663951 lakh' - read as 1,663,951 rows"]),
    _src("raw", "college", "raw_college_universities_data",
         "Unified AISHE database covering all higher education institutes (colleges, universities, R&D) with "
         "establishment years and official URLs.",
         "72,327", "Prachi", ""),
    _src("raw", "restaurant", "raw_hotels_restaurants",
         "Overture Maps (AWS S3) source. This data includes Latitudes, Longitudes, Phone numbers, Websites, "
         "and exact City locations.",
         "2,53,346", "Prachi",
         "Includes precise geolocation; ready for immediate map-based use without requiring heavy data cleaning."),
    _src("raw", "train", "raw_train_information",
         "Raw train information dataset containing Train Number, Train Name, Source Station Name, Destination "
         "Station Name and Days of Operation.",
         "11113", "Prem",
         "Raw train data collected and imported into Data Enrichment DB. Data is kept in raw form; "
         "cleaning/enrichment not performed."),
    _src("raw", "places", "osm_places",
         "Open Street Maps places data containing various Indian places.",
         "967450", "Shubham", "",
         notes=["Listed twice in the sheet (once without details) - merged into one row"]),
    _src("raw", "place clean", "osm_places_clean", "", "", "", "",
         notes=["No detail, count or owner filled in the sheet yet"]),
    _src("raw", "shopping", "raw_shopping",
         "A filtered Pan-India Overture Maps dataset focusing exclusively on major retail hubs (Malls, Wholesale "
         "Markets, and Shopping Streets), complete with exact Lat/Long coordinates.",
         "31,473", "Prachi",
         "Carefully filtered to remove small, random shops. Includes exact map coordinates (Latitude/Longitude), "
         "so places can be shown directly on a map without extra location fixing."),
    _src("raw", "bank / ifsc", "raw_ifsc",
         "Comprehensive Indian IFSC bank branch database containing bank names, IFSC codes, branch details, "
         "addresses, contact information, and transaction service availability.",
         "1,64,836", "Mukul",
         "Contains detailed bank and branch-level IFSC information including NEFT, RTGS, IMPS, UPI, MICR, and SWIFT "
         "service details. Requires successful CSV import into PostgreSQL"),
    _src("raw", "tourism", "raw_places",
         "City-wise tourist places dataset containing place names, ratings, distance information, and detailed "
         "place descriptions.",
         "2,989", "Mukul",
         "Contains city, place, ratings, distance, and detailed descriptions; imported into PostgreSQL as raw_places"),
    _src("raw", "tourism", "tourist",
         "Tourist places dataset containing city-wise tourist places, place descriptions, ratings, distance from "
         "city center, ideal duration, best time to visit, city descriptions, and categories.",
         "2,989", "Ishika",
         "Contains 10 columns including City, Place, Ratings, Distance, Place Description, Ideal Duration, Best Time "
         "to Visit, City Description, and Category; imported into PostgreSQL as tourist.",
         notes=["Same row count (2,989) as raw_places - check whether it is the same dataset imported twice"]),
    _src("raw", "tourism", "raw_top_indian_places_to_visit",
         "Top Indian tourist places dataset containing zone, state, city, place name, place type, establishment "
         "year, visit duration, Google review rating, entrance fee, nearby airport, weekly off, significance, DSLR "
         "availability, review count, and best time to visit.",
         "325", "Ishika",
         "Contains 325 Indian tourist places with 16 columns covering location, ratings, fees, visiting information, "
         "significance, and other tourism details; imported into PostgreSQL as raw_top_indian_places_to_visit."),
    _src("raw", "dmart", "raw_dmart",
         "Raw DMart transaction dataset containing transaction date and time, customer type, product category, unit "
         "price, quantity, total amount, and customer name.",
         "1,000,000", "Mukul",
         "Contains raw DMart transaction-level data with 8 columns including date, time, customer type, product "
         "category, unit price, quantity, total amount, and customer name; imported into PostgreSQL as raw_dmart"),
    _src("raw", "weather", "raw_weather",
         "Weather dataset containing city names and their geographic coordinates, including latitude and longitude.",
         "5,933", "Ishika",
         "Contains 5,933 weather/location records with 4 columns: Unnamed: 0, city, lat, and lng; imported into "
         "PostgreSQL as raw_weather."),
    _src("raw", "myntra", "raw_mayntra",
         "Myntra product dataset containing product ID, product name, image URL, ASIN, price, MRP, rating, total "
         "ratings, discount, seller, and product URL.",
         "1060213", "Mukul",
         "CSV data successfully imported into PostgreSQL as raw_mayntra table. Contains Myntra product records with "
         "product details.",
         candidates=["raw_myntra"]),
    _src("raw", "amazon", "raw_amazon_ind_product",
         "Amazon India product dataset containing ASIN, product title, image URL, product URL, ratings, reviews, "
         "price, list price, category, bestseller status, and monthly purchase information.",
         "1589160", "Ishika",
         "Contains Amazon India product data with detailed product information and monthly purchase information. "
         "The processed dataset was imported into PostgreSQL for further data cleaning, enrichment, validation, "
         "and analysis."),
    _src("raw", "shopping mall", "raw_shopping_mall",
         "Comprehensive shopping mall dataset containing mall names, locations, mall types, number of floors and "
         "shops, parking capacity, facilities such as food courts, multiplexes and hypermarkets, ratings, reviews, "
         "and opening years.",
         "1000", "Mukul",
         "Structured dataset with standardized location, infrastructure, facility, rating, review, and opening-year "
         "information. Suitable for database ingestion and further analysis after basic data validation and cleaning."),
    _src("raw", "atm", "raw_atm",
         "List of Axis Bank branch onsite ATM centres across India, containing Zone, State, District, and Complete "
         "Address information for each ATM location.",
         "1908", "Mukul",
         "Source data contains branch onsite ATM centres with Zone, State, District, and Complete Address. Address "
         "details include location information such as PIN codes. Data is structured and suitable for database "
         "ingestion after basic cleaning and standardization."),
    _src("raw", "hospital", "raw_hospital",
         "Hospital dataset containing hospital names, types, ownership, locations, addresses, facilities, medical "
         "services, bed capacity, staff information, ratings, reviews, consultation fees, patient volume, "
         "accreditation, and other healthcare-related attributes.",
         "24822", "Mukul",
         "Structured healthcare dataset with hospital, location, infrastructure, facility, service, and "
         "performance-related information. Suitable for database ingestion and further analysis after basic data "
         "validation, cleaning, and standardization."),
    _src("raw", "city", "cities",
         "City dataset containing city and state information along with tier, population, area, population "
         "density, geographic coordinates, property and rental metrics, economic indicators, infrastructure, "
         "connectivity, tourism, environmental factors, healthcare and education facilities, and other city-level "
         "attributes.",
         "1001", "Mukul",
         "Metro station dataset successfully imported into the PostgreSQL raw table. The imported data contains "
         "station details, metro lines, location information, accessibility features, daily footfall, nearby "
         "facilities, property impact, and smart city area information.",
         notes=["Group is blank in the sheet (placed with raw)",
                "Remarks describe metro stations, not cities - looks copied from raw_metro_stations, please re-check"]),
    _src("raw", "properties", "raw_properties",
         "Comprehensive property dataset containing property IDs, property names, developer details, property types, "
         "locations, addresses, pricing, area details, amenities, nearby facilities, ratings, and property-related "
         "indicators.",
         "500000", "Ishika",
         "Contains 5,00,000 property records with detailed property information. Successfully imported into "
         "PostgreSQL as raw_properties."),
    _src("raw", "localities", "raw_localities",
         "Raw locality dataset containing locality, city, state, pincode, geographical coordinates, nearby "
         "facilities, property and rental information, livability and infrastructure scores, and other "
         "locality-level attributes.",
         "12,991", "Ishika",
         "Raw locality data imported into PostgreSQL. Contains 40 columns and 12,991 records."),
    _src("raw", "metro station", "raw_metro_stations",
         "Imported metro station data including station details, metro lines, location information, accessibility, "
         "footfall, nearby facilities, property impact, and smart city information.",
         "1,000", "Ishika",
         "Metro station dataset successfully imported into the PostgreSQL raw table. The imported data contains "
         "station details, metro lines, location information, accessibility features, daily footfall, nearby "
         "facilities, property impact, and smart city area information."),
    _src("raw", "kotak", "raw_kotak",
         "ATM dataset containing ATM/Recycler records with branch code, ATM ID, location, complete address, city, "
         "state, PIN code, launch date, and RBI classification (Onsite/Offsite).",
         "3,827", "Ishika",
         "Data contains detailed ATM location and address information across different cities and states. The "
         "dataset includes both Onsite and Offsite ATM records and requires basic cleaning and standardization "
         "before database ingestion."),
    _src("raw", "schools", "raw_schools2",
         "Imported school data including school details, city and locality information, school type, board, "
         "management, facilities, student and teacher information, fees, accessibility, nearby metro connectivity, "
         "and location details.",
         "25,000", "Ishika",
         "School dataset successfully imported into the PostgreSQL raw table. The data includes school information, "
         "academic details, infrastructure and facilities, student and teacher statistics, transportation, nearby "
         "metro connectivity, and geographical information."),
    _src("raw", "baroda", "raw_baroda",
         "ATM dataset containing ATM IDs, locations, regions, states, PIN codes, and zone information for ATM records.",
         "8287", "Ishika",
         "Structured ATM location dataset with regional and geographical information. Data is suitable for "
         "PostgreSQL database ingestion after basic validation, cleaning, and standardization."),
    _src("raw", "indian places review", "review_db_clean",
         "Kaggle \"Indian Places to Visit Reviews\" dataset containing city-wise place reviews with columns City, "
         "Date, Name, Place, Rating, Raw_Review, Review.",
         "1,482,466", "Riya",
         "Raw dump only, no cleaning applied. All columns kept as text to avoid import failures from malformed rows; "
         "Rating to be cast to numeric during cleaning phase."),
    _src("raw", "geonames", "geonames_india_raw",
         "GeoNames bulk export for India containing place names, coordinates, feature classes/codes, and population.",
         "660,025", "Riya", "Raw dump, unfiltered."),
    _src("raw", "indian religious places", "religious_places_india",
         "Subset of the GeoNames data filtered to temples, shrines, ziarats/mazars and other places of worship.",
         "1,745", "Riya", "Derived from the GeoNames raw table above, not a separate source."),
    _src("raw", "osm points", "osm_points_raw",
         "Geofabrik OpenStreetMap extract for India, filtered to named points of interest only (shops, temples, "
         "landmarks, etc.) via ogr2ogr, with x/y coordinates and raw tag data.",
         "3,445,555", "Riya",
         "Extracted from india-260811.osm.pbf. Raw dump, all-text columns, not filtered by category"),
]

# ─── same sheet - product group (names written informally in the sheet) ─────
PRODUCT_SOURCES = [
    _src("product", "category", "page_product_categories", "Product category (sheet: 'product categroy')", "", "", "",
         candidates=["product_categories", "product_category_master"]),
    _src("product", "brand", "brand_master", "Brand master (sheet: 'Brand master')", "", "", "",
         candidates=["brands", "product_brands", "brand_masters"]),
    _src("product", "catalogue", "product_catalogue", "Product catalogue", "", "", ""),
    _src("product", "attributes", "product_attributes_master", "Product attribute master", "", "", ""),
    _src("product", "attributes", "product_attributes", "Product attribute values", "", "", ""),
    _src("product", "affiliate", "affiliate_products", "Affiliate products (sheet: 'affiliate')", "", "", "",
         candidates=["affiliate"]),
]

# groups written in the sheet with no tables yet
EMPTY_GROUPS = ["business", "service"]

ALL_SOURCES = RAW_SOURCES + PRODUCT_SOURCES
SOURCE_BY_TABLE = {}
for _s in ALL_SOURCES:
    for _c in _s["candidates"]:
        SOURCE_BY_TABLE.setdefault(_c.lower(), _s)


# ─── 01 Final Data Enrichment Master Report ─────────────────────────────────
PROCESS_TITLE = "Final Data Enrichment Master Report"
PROCESS_OBJECTIVE = (
    "Document, end to end, everything done in the data enrichment project - from receiving the CSV data from "
    "the marketing team to the final load of the enriched data into TestDB (PostgreSQL)."
)
PROCESS_OVERVIEW = (
    "The process starts with a CSV file from the marketing team. The data is cleaned with a Python script, ranked "
    "by search volume, and mapped to the location master and to business and product categories. Category "
    "parent-child relations are then set and the final data is validated with an automation script. The validated "
    "data is loaded into TestDB (PostgreSQL), and the data enrichment reports are shown in the dashboard."
)
PROCESS_STEPS = [
    (1, "Get CSV data", "Collect & Clean", "Receive the CSV data from the marketing team"),
    (2, "Data clean", "Collect & Clean", "Clean the CSV data using a Python script"),
    (3, "URL extraction", "Ranking", "Run the ranking URL extraction process"),
    (4, "Ranking", "Ranking", "Rank records on the basis of search volume"),
    (5, "Location mapping", "Mapping", "Map all location details with the location master"),
    (6, "Business category mapping", "Mapping", "Map business category data to the extracted data"),
    (7, "Product category mapping", "Mapping", "Map product category data to the extracted data"),
    (8, "Business category hierarchy", "Category Hierarchy", "Set the business category parent-child relation"),
    (9, "Product category hierarchy", "Category Hierarchy", "Set the product category parent-child relation"),
    (10, "Validation", "Validate & Load", "Validate the final data with an automation script before it is loaded into TestDB"),
    (11, "Load into TestDB", "Validate & Load", "Load the validated data into TestDB (PostgreSQL)"),
    (12, "Dashboard report", "Report", "Show all the data enrichment reports in the dashboard"),
]
PROCESS_KEY_POINTS = [
    "Ranking is based on search volume.",
    "Location, business category and product category data are all mapped before loading.",
    "Data is validated by an automation script before it is loaded into TestDB (PostgreSQL).",
    "In the flowchart, a failed validation returns the data to the cleaning step (the report marks this return path as an assumption).",
    "TestDB is the staging database: its tables can change as the project needs change.",
]

# ─── 02 Dynamic URL Extraction and CSV Enrichment System ────────────────────
URL_DOC_TITLE = "Dynamic URL Extraction and CSV Enrichment System"
URL_DOC_DATE = "28 September 2026"
URL_TABLE = "url_extraction_master"
# output field -> population rule (section 7 of the document)
URL_OUTPUT_FIELDS = [
    ("city", "City", "Dynamic or static city extraction."),
    ("state", "State", "STATE MAP match in the normalized URL path."),
    ("country", "Country", "India if location evidence exists or india occurs in the URL."),
    ("region", "Region", "REGION MAP lookup by extracted state."),
    ("url_location", "URL Location", "Copy of City."),
    ("area", "Area", "Always blank in this version."),
    ("category", "Category", "Category marker or broad category heuristic."),
    ("business_category", "Business Category", "Copy of Category."),
    ("product_category", "Product Category", "Copy of Category."),
    ("source", "Source", "Normalized URL network location without leading www."),
    ("url_keyword", "URL Keyword", "Path tokens that fuzzy match Keyword tokens."),
    ("unknown", "Unknown", "Always blank in this version."),
    ("remaining_url_keywords", "Remaining URL Keywords", "Retained path tokens that do not fuzzy match Keyword."),
    ("priority_rank", "Priority Rank", "Always 1 in this version."),
]
URL_METRIC_FIELDS = ["volume", "position", "estimated_visits", "cpc", "paid_difficulty", "seo_difficulty"]
URL_CATEGORY_VOCAB = [
    ("Restaurant", "restaurant, food, cafe, dining, eatery"),
    ("Hotel", "hotel, resort, stay, accommodation"),
    ("Education", "tutor, classes, training, course, institute"),
    ("B2B Manufacturing", "manufacturer, supplier, exporter, wholesaler"),
    ("Events", "event, workshop, tickets, booking"),
]
URL_LIMITS = [
    ("First URL-like column wins", "A column containing 'ranking' may be selected even if it is not the landing-page URL.",
     "Make the URL column configurable or prefer exact names such as Ranking URL."),
    ("Bare domains are not normalized as URLs", "example.com/path has no parsed netloc, so Source is blank.",
     "Add https:// when a scheme is absent before parsing."),
    ("Location maps are limited", "Unlisted cities and some regional assignments remain blank.",
     "Maintain maps from a reviewed reference file and add confidence flags."),
    ("Region map is incomplete", "A recognized state can still produce a blank Region.",
     "Complete REGION MAP for all supported states and territories."),
    ("Token order is unstable", "Set iteration can reorder URL Keyword output across runs.",
     "Use an ordered list with a seen set, preserving path order."),
    ("Several fields are placeholders", "Area and Unknown are always blank; all ranks are 1; three category fields are copies.",
     "Either document them as placeholders or implement separate business rules."),
    ("Row-wise iterrows processing", "Large files may run slowly.", "Benchmark and consider vectorized preprocessing or progress logging."),
    ("No automated test suite", "Future map or regex changes can silently alter enrichment.",
     "Add unit tests for normal URLs, malformed URLs, aliases, missing fields, and ambiguous paths."),
    ("Output is overwritten", "A rerun can replace a prior approved result.", "Add a timestamp, versioned output name, or overwrite confirmation."),
]

# ─── 03 Location matching reports ───────────────────────────────────────────
STATES_ADDED = ["Odisha", "Ladakh", "Jammu and Kashmir", "Andaman and Nicobar Islands",
                "Dadra and Nagar Haveli and Daman and Diu"]
NEW_CITIES = [  # (city, state, new location id) - Location Master Data Matching report, section 6
    ("Panaji", "Goa", 327602), ("Anjuna", "Goa", 327603), ("Candolim", "Goa", 327604), ("Baga", "Goa", 327605),
    ("Calangute", "Goa", 327606), ("Margao", "Goa", 327607), ("Raipur", "Chhattisgarh", 327608),
    ("Mysuru", "Karnataka", 327609), ("Mangaluru", "Karnataka", 327610), ("Kota", "Rajasthan", 327611),
    ("Prayagraj", "Uttar Pradesh", 327612), ("Ooty", "Tamil Nadu", 327613), ("Vrindavan", "Uttar Pradesh", 327614),
    ("Pushkar", "Rajasthan", 327615),
]
CITIES_TO_INVESTIGATE = [  # (city, unmatched records at the time of the report)
    ("Mysuru", 136), ("Raipur", 120), ("Mangaluru", 103), ("Kota", 46), ("Prayagraj", 44), ("Ooty", 42),
    ("Vrindavan", 36), ("Panaji", 4), ("Pushkar", 3), ("Anjuna", 2), ("Calangute", 1),
]
STATE_ALIASES = [("up", "uttar pradesh"), ("mh", "maharashtra"), ("bom", "mumbai"), ("bengaluru", "bangalore")]
CITY_MATCH_ORDER = [
    ("Exact City + State", "Perfect match for both city and state."),
    ("Exact City only", "Matched if there is only one city with that name in the entire database."),
    ("Reused City", "State blank in the priority file, but the city belongs to only one state in the master."),
    ("Fuzzy (rapidfuzz >= 92%)", "Catches minor spelling mistakes."),
    ("New City", "All steps failed - assigned a new ID and added under its State."),
]
LOCATION_DOCS = {
    "state_sync": {"title": "State match - Location Data Matching & Synchronization",
                   "original_states": 35, "added_states": 5, "total_after_sync": 40},
    "regions": {"title": "Data Enrichment and Missing Regions Report",
                "filled": 50536, "total": 69371, "location_master_rows_fixed": 221, "brand_rows_fixed": 2,
                "nraipur_rows_reverted": 179,
                "limits": ["Zero-signal searches (e.g. 'restaurants near me') with no location in keyword, URL or ID",
                           "Micro-localities that yield only 1-2 rows each",
                           "Incomplete scrapes - location only on the live webpage, not in the exported CSV"],
                "recommendation": "Accept the 50,536 filled rows; send the rest (master_priority_missing_region.csv) for manual review."},
    "areas": {"title": "Data Enrichment and Missing Area Report",
              "area_rows": 307870, "digit_names": 1080, "duplicate_parent_names": 987, "incorrect_total": 2067,
              "cities_affected": 875, "priority_cities": 28, "fixable_cities": 25, "corrected": 30, "unresolved": 2037},
    "matching": {"title": "Location Master Data Matching - Data Matching, Validation and Migration Readiness",
                 "location_master_total": 321190, "countries": 1, "states": 35, "cities": 9828,
                 "priority_total": 69371, "priority_unique_cities": 89, "priority_city_state_combos": 172,
                 "exact_city_state": 10627, "exact_city": 28547, "new_locations": 14,
                 "updated_location_master": 321204, "unmatched": 29742, "unmatched_no_city_state": 24937},
}

# ─── 04 Location Master Data Report (ranking) ───────────────────────────────
LOCATION_RANK_DOC = {
    "title": "Location Master Data Report",
    "total": 322886,
    "by_rank": {"Rank 1": 321662, "Rank 2": 402, "Rank 3": 308, "Rank 4": 241, "Rank 5": 272},
    "by_type_rank1": {"City": 321661, "Area": 307059, "Building": 5944, "Street": 5957, "Locality": 5934,
                      "State": 35, "Country": 1},
    "city_rank_2_5": {"Rank 2": 402, "Rank 3": 308, "Rank 4": 241, "Rank 5": 272},
}
