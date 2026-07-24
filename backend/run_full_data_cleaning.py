import os
import sys
import uuid
import argparse
from dotenv import load_dotenv

# Ensure we are in backend dir context
backend_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(backend_dir)
os.chdir(backend_dir)

# Load env variables
load_dotenv('.env')

from app import app
from extensions import db
from services.data_cleaning_service import run_cleaning_async
from model.data_cleaning_log import DataCleaningLog

def main():
    parser = argparse.ArgumentParser(description="Run the HBD Data Cleaning and Standardization Pipeline.")
    parser.add_argument("--table", choices=["master_table", "product_master", "all"], default="master_table",
                        help="Target table to clean. Options: master_table, product_master, all. (Default: master_table)")
    parser.add_argument("--apply", action="store_true", 
                        help="Apply changes to the database. By default, it runs in dry-run mode.")
    args = parser.parse_args()

    run_type = "apply" if args.apply else "dry-run"
    table_name = args.table

    with app.app_context():
        run_id = f"cmd_{uuid.uuid4().hex[:8]}"
        print(f"============================================================")
        print(f"🚀 STARTING DATA CLEANING RUN (Run ID: {run_id})")
        print(f"👉 Target Table: {table_name}")
        print(f"👉 Run Mode:     {run_type.upper()}")
        print(f"============================================================")

        # Create log entry
        log_entry = DataCleaningLog(
            run_id=run_id,
            run_type=run_type,
            status="running",
            table_name=table_name
        )
        db.session.add(log_entry)
        db.session.commit()

        # Run the cleaning process synchronously in terminal
        try:
            run_cleaning_async(run_id, table_name, run_type, app.app_context())
            
            # Fetch final logs
            db.session.expire_all()
            final_log = DataCleaningLog.query.filter_by(run_id=run_id).first()
            
            print(f"\n=================== RUN RESULTS SUMMARY ===================")
            print(f"Status:             {final_log.status.upper()}")
            print(f"Total Rows Checked: {final_log.total_rows:,}")
            print(f"Standardized Rows:  {final_log.cleaned_rows:,}")
            print(f"Duplicates Found:   {final_log.duplicate_rows:,}")
            print(f"Unmatched Location: {final_log.unmatched_location_rows:,}")
            print(f"Missing Location:   {final_log.missing_location_rows:,}")
            print(f"Invalid Contact:    {final_log.invalid_phone_email_rows:,}")
            print(f"Wrong Category:     {final_log.wrong_category_rows:,}")
            print(f"============================================================")
        except Exception as e:
            print(f"\n❌ Pipeline run failed with error: {e}")
            db.session.rollback()

if __name__ == "__main__":
    main()
