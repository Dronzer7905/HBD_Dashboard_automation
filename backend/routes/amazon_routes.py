import os
import json
import sys
import subprocess
from flask import Blueprint, request, jsonify
from sqlalchemy import text
from extensions import db
from model.scraper_task import ScraperTask
from model.product_model.amazon_product import AmazonProduct

amazon_api_bp = Blueprint('amazon_api_bp', __name__)

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
STATE_FILE = os.path.join(BACKEND_DIR, "output", "amazon_scrape_state.json")

def _load_state() -> dict:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def _get_engine():
    from sqlalchemy import create_engine
    from config import config
    return create_engine(config.SQLALCHEMY_DATABASE_URI, pool_pre_ping=True)

# --- ROUTE 1: Start Scraping (Subprocess) ---
@amazon_api_bp.route('/scrape_amazon', methods=['POST'])
def start_amazon_scrape():
    try:
        data = request.get_json(silent=True) or {}
        search_term = data.get('search_term')
        pages = int(data.get('pages', 1))
        resume = bool(data.get('resume', False))
        
        if not search_term:
            return jsonify({'error': 'search_term is required'}), 400

        # Create ScraperTask record
        task = ScraperTask(
            platform="Amazon",
            search_query=search_term,
            status="PENDING",
            progress=0,
            total_found=0,
        )
        db.session.add(task)
        db.session.commit()
        task_id = task.id

        # Build subprocess command
        cmd = [
            sys.executable,
            "-m", "services.scrapers.amazon_service",
            "--search_term", str(search_term),
            "--pages", str(pages),
            "--task_id", str(task_id),
        ]
        if resume:
            cmd.append("--resume")

        # Windows-compatible UTF-8 environment
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"

        # Log file
        log_dir = os.path.join(BACKEND_DIR, "logs")
        os.makedirs(log_dir, exist_ok=True)
        log_file_path = os.path.join(log_dir, f"amazon_task_{task_id}.log")
        log_file = open(log_file_path, "a", encoding="utf-8")

        # Launch background subprocess (non-blocking)
        subprocess.Popen(
            cmd,
            cwd=BACKEND_DIR,
            env=env,
            stdout=log_file,
            stderr=log_file,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )

        task.status = "RUNNING"
        db.session.commit()

        return jsonify({
            "status": "started",
            "task_id": task_id,
            "message": f"Amazon scraper running in background for '{search_term}'.",
            "search_term": search_term,
            "pages": pages,
            "resume": resume,
            "log_file": log_file_path,
        }), 202

    except Exception as e:
        import traceback
        return jsonify({"error": str(e), "trace": traceback.format_exc()[-500:]}), 500

# --- ROUTE 2: Fetch Data (Using SQLAlchemy) ---
@amazon_api_bp.route('/amazon-data', methods=['GET']) 
def get_amazon_data():
    try:
        products = AmazonProduct.query.order_by(AmazonProduct.id.desc()).limit(1000).all()
        results = []
        for p in products:
            results.append({
                "id": p.id,
                "ASIN": p.asin,
                "Product_name": p.title,
                "price": str(p.price),
                "rating": str(p.stars),
                "Number_of_ratings": str(p.reviews),
                "Brand": p.categoryName,
                "link": p.productUrl,
                "Image_URLs": p.imgUrl,
                "created_at": None
            })
        return jsonify(results)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# --- ROUTE 3: Status ---
@amazon_api_bp.route("/scrape_amazon/status", methods=["GET"])
def get_amazon_scrape_status():
    try:
        task = (
            ScraperTask.query
            .filter_by(platform="Amazon")
            .order_by(ScraperTask.id.desc())
            .first()
        )
        task_data = task.to_dict() if task else None
        state_data = _load_state()
        return jsonify({"task": task_data, "state": state_data}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- ROUTE 4: History ---
@amazon_api_bp.route("/scrape_amazon/history", methods=["GET"])
def get_amazon_scrape_history():
    try:
        limit = request.args.get("limit", 20, type=int)
        tasks = (
            ScraperTask.query
            .filter_by(platform="Amazon")
            .order_by(ScraperTask.id.desc())
            .limit(limit)
            .all()
        )
        return jsonify([t.to_dict() for t in tasks]), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- ROUTE 5: Stop ---
@amazon_api_bp.route("/scrape_amazon/stop", methods=["POST"])
def stop_amazon_scrape():
    try:
        data = request.get_json(silent=True) or {}
        task_id = data.get("task_id")

        if task_id:
            task = ScraperTask.query.get(task_id)
        else:
            task = (
                ScraperTask.query
                .filter_by(platform="Amazon")
                .filter(ScraperTask.status.in_(["PENDING", "RUNNING"]))
                .order_by(ScraperTask.id.desc())
                .first()
            )

        if not task:
            return jsonify({"error": "No active Amazon task found"}), 404

        task.should_stop = True
        task.status = "STOPPED"
        db.session.commit()

        return jsonify({"message": f"Stop signal sent to task #{task.id}", "task_id": task.id}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- ROUTE 6: Logs ---
@amazon_api_bp.route("/tasks/<int:task_id>/amazon-logs", methods=["GET"])
def get_amazon_task_logs(task_id: int):
    try:
        log_file = os.path.join(BACKEND_DIR, "logs", f"amazon_task_{task_id}.log")
        if not os.path.exists(log_file):
            return jsonify({"logs": [], "exists": False}), 200

        with open(log_file, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        cleaned = [line.rstrip("\n\r") for line in lines if line.strip()]
        return jsonify({"logs": cleaned[-500:], "total_lines": len(cleaned), "exists": True}), 200
    except Exception as e:
        return jsonify({"error": str(e), "logs": []}), 500

# --- ROUTE 7: DB Stats ---
@amazon_api_bp.route("/scrape_amazon/db-stats", methods=["GET"])
def get_amazon_db_stats():
    try:
        engine = _get_engine()
        with engine.connect() as conn:
            product_count = conn.execute(text("SELECT COUNT(*) FROM amazon_products")).scalar()
            brand_count = conn.execute(text(
                "SELECT COUNT(DISTINCT categoryName) FROM amazon_products WHERE categoryName IS NOT NULL AND categoryName != ''"
            )).scalar()
            null_cat_ids = 0

            # Top categories
            brand_breakdown = conn.execute(text("""
                SELECT categoryName, COUNT(*) as cnt
                FROM amazon_products
                WHERE categoryName IS NOT NULL AND categoryName != 'Unknown Brand'
                GROUP BY categoryName
                ORDER BY cnt DESC
                LIMIT 20
            """)).mappings().fetchall()

        state_data = _load_state()

        return jsonify({
            "total_products": int(product_count or 0),
            "distinct_brands": int(brand_count or 0),
            "products_null_category_id": int(null_cat_ids or 0),
            "top_categories": [
                {"category": r["categoryName"], "count": int(r["cnt"])}
                for r in brand_breakdown
            ],
            "last_scrape_state": {
                "products_scraped": state_data.get("products_scraped", 0),
                "products_inserted": state_data.get("products_inserted", 0),
                "products_updated": state_data.get("products_updated", 0),
                "duplicates_prevented": state_data.get("duplicates_prevented", 0),
                "is_complete": state_data.get("is_complete", False),
                "started_at": state_data.get("started_at", ""),
                "last_updated": state_data.get("last_updated", ""),
            }
        }), 200
    except Exception as e:
        import traceback
        return jsonify({"error": str(e), "trace": traceback.format_exc()[-800:]}), 500