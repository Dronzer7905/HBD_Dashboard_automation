import pymysql
import random

import os
from dotenv import load_dotenv

load_dotenv()

# Credentials
DEV_HOST = os.getenv('DEV_DB_HOST', '172.105.48.130')
DEV_USER = os.getenv('DEV_DB_USER', 'genuineh_dashboard')
DEV_PASS = os.getenv('DEV_DB_PASSWORD')
DEV_DB = os.getenv('DEV_DB_NAME', 'genuineh_dashboard')

PROD_HOST = os.getenv('PROD_DB_HOST', '77.42.78.20')
PROD_USER = os.getenv('PROD_DB_USER', 'genuineh_dashboard')
PROD_PASS = os.getenv('PROD_DB_PASSWORD')
PROD_DB = os.getenv('PROD_DB_NAME', 'genuinehdashboard')

def get_prod_conn():
    try:
        return pymysql.connect(host=PROD_HOST, user=PROD_USER, password=PROD_PASS, database=PROD_DB)
    except Exception as e:
        print(f"Failed PROD connect with genuineh_dashboard user: {e}. Trying genuinehdashboard...")
        try:
            return pymysql.connect(host=PROD_HOST, user='genuinehdashboard', password=PROD_PASS, database=PROD_DB)
        except Exception as e2:
            print(f"Failed PROD connect with genuinehdashboard user: {e2}")
            return None

def main():
    print("Connecting to Dev...")
    dev_conn = pymysql.connect(host=DEV_HOST, user=DEV_USER, password=DEV_PASS, database=DEV_DB)
    
    print("Connecting to Prod...")
    prod_conn = get_prod_conn()
    if not prod_conn:
        print("Could not connect to Prod DB.")
        return

    with dev_conn.cursor() as dev_c, prod_conn.cursor() as prod_c:
        # 1. Counts and IDs
        dev_c.execute("SELECT COUNT(*), MIN(ID), MAX(ID) FROM item_data")
        dev_stats = dev_c.fetchone()
        
        prod_c.execute("SELECT COUNT(*), MIN(ID), MAX(ID) FROM item_data")
        prod_stats = prod_c.fetchone()
        
        print(f"\n[DEV]  item_data -> Count: {dev_stats[0]}, Min ID: {dev_stats[1]}, Max ID: {dev_stats[2]}")
        print(f"[PROD] item_data -> Count: {prod_stats[0]}, Min ID: {prod_stats[1]}, Max ID: {prod_stats[2]}")
        
        # 2. Timestamps
        dev_c.execute("SHOW COLUMNS FROM item_data LIKE '%at'")
        print(f"\n[DEV] Timestamp columns: {[row[0] for row in dev_c.fetchall()]}")
        
        prod_c.execute("SHOW COLUMNS FROM item_data LIKE '%at'")
        print(f"[PROD] Timestamp columns: {[row[0] for row in prod_c.fetchall()]}")
        
        # Min max for random logic
        min_id = max(dev_stats[1] or 0, prod_stats[1] or 0)
        max_id = min(dev_stats[2] or 0, prod_stats[2] or 0)
        
        if min_id <= max_id:
            print(f"\nChecking 20 random IDs between {min_id} and {max_id}...")
            # We'll just fetch a bunch of overlapping IDs
            dev_c.execute(f"SELECT ID FROM item_data WHERE ID >= {min_id} AND ID <= {max_id} LIMIT 1000")
            possible_ids = [r[0] for r in dev_c.fetchall()]
            
            if possible_ids:
                sample_ids = random.sample(possible_ids, min(20, len(possible_ids)))
                
                print(f"{'ID':<10} | {'DEV NAME':<25} | {'PROD NAME':<25} | MATCH?")
                print("-" * 75)
                
                for sid in sample_ids:
                    dev_c.execute(f"SELECT name, city, address FROM item_data WHERE ID = {sid}")
                    d_row = dev_c.fetchone()
                    
                    prod_c.execute(f"SELECT name, city, address FROM item_data WHERE ID = {sid}")
                    p_row = prod_c.fetchone()
                    
                    if d_row and p_row:
                        d_name, d_city, d_addr = d_row
                        p_name, p_city, p_addr = p_row
                        
                        match = (d_name == p_name) and (d_city == p_city) and (d_addr == p_addr)
                        
                        d_name_str = str(d_name)[:25]
                        p_name_str = str(p_name)[:25]
                        print(f"{sid:<10} | {d_name_str:<25} | {p_name_str:<25} | {match}")
                    else:
                        print(f"{sid:<10} | Missing in one of the DBs")
        else:
            print("No overlapping ID ranges!")

main()
