import os
import sys
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Load environment from current directory
load_dotenv('.env')

db_host = os.getenv('DB_HOST', 'localhost')
db_user = os.getenv('DB_USER', 'root').strip()
db_password = os.getenv('DB_PASSWORD', '')
db_name = os.getenv('DB_NAME', 'default')
db_port = int(os.getenv('DB_PORT', '3306'))

url = f"mysql+pymysql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
engine = create_engine(url)

# Save output SQL file directly in the current directory (which is /app in the container)
output_sql_path = 'sample_data_listings.sql'

# List of tables to export with a 5000-row limit
TABLES_TO_EXPORT = [
    # Staging Products
    "amazon_products",
    "blinkit",
    "bigbasket",
    "dmart_products",
    "indiamart_products",
    "zepto",
    "jiomart_products",
    
    # Mapping Tables
    "blinkit_mapping",
    "zepto_db_mapping",
    "bigbasket_dbmapping",
    "indiamart_mappings",
    "dmart_categories",
    "jiomart_categories",
    "flipkart_db_mapping",
    "platform_category_mapping",
    
    # Report & Summary Tables
    "product_dashboard_report_summary",
    "product_top_selling_report",
    
    # Master Tables
    "master_table",
    "product_master"
]

print("=============================================================")
print("📦 SAMPLE DATA EXPORTER UTILITY")
print("=============================================================")
print(f"Connecting to: {db_name} on {db_host}")
print(f"Target Output: {os.path.abspath(output_sql_path)}")
print("=============================================================\n")

try:
    with engine.connect() as conn:
        with open(output_sql_path, "w", encoding="utf-8") as out:
            # Write SQL headers
            out.write("SET FOREIGN_KEY_CHECKS = 0;\n")
            out.write("SET SQL_MODE = 'NO_AUTO_VALUE_ON_ZERO';\n")
            out.write("START TRANSACTION;\n\n")
            
            for table in TABLES_TO_EXPORT:
                # 1. Check if table exists
                table_exists = conn.execute(text(f"""
                    SELECT COUNT(*) 
                    FROM information_schema.tables 
                    WHERE table_schema = :db AND table_name = :tbl
                """), {"db": db_name, "tbl": table}).scalar() or 0
                
                if not table_exists:
                    print(f"⚠️ Table `{table}` does not exist. Skipping.")
                    continue
                
                # 2. Get table columns
                cols_res = conn.execute(text(f"SHOW COLUMNS FROM `{table}`")).fetchall()
                columns = [f"`{c[0]}`" for c in cols_res]
                col_names_str = ", ".join(columns)
                
                print(f"Exporting sample from `{table}`...")
                
                # 3. Fetch first 5000 rows
                rows = conn.execute(text(f"SELECT * FROM `{table}` LIMIT 5000")).fetchall()
                
                # Write Truncate statement
                out.write(f"--\n-- Truncate and Dumping data for table `{table}`\n--\n")
                out.write(f"TRUNCATE TABLE `{table}`;\n")
                
                if not rows:
                    out.write("\n")
                    continue
                
                # Write insert statements in chunks of 500
                chunk_size = 500
                for i in range(0, len(rows), chunk_size):
                    chunk = rows[i:i+chunk_size]
                    values_list = []
                    
                    for r in chunk:
                        row_vals = []
                        for val in r:
                            if val is None:
                                row_vals.append("NULL")
                            elif isinstance(val, (int, float)):
                                row_vals.append(str(val))
                            else:
                                # Escape quotes and format strings/bytes
                                escaped = str(val).replace("\\", "\\\\").replace("'", "\\'")
                                row_vals.append(f"'{escaped}'")
                        values_list.append(f"({', '.join(row_vals)})")
                        
                    insert_sql = f"INSERT INTO `{table}` ({col_names_str}) VALUES \n" + ",\n".join(values_list) + ";\n"
                    out.write(insert_sql)
                
                out.write("\n")
            
            # Write SQL footers
            out.write("COMMIT;\n")
            out.write("SET FOREIGN_KEY_CHECKS = 1;\n")
            
        print(f"\n✅ EXPORT COMPLETED SUCCESSFULLY!")
        print(f"Sample data written to: {os.path.abspath(output_sql_path)}")
        print("You can now download this file and import it locally.")
        
except Exception as e:
    print(f"\n❌ Error during export: {e}")
    sys.exit(1)
