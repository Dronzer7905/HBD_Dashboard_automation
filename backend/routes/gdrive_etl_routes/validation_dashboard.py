"""
📊 Validation Dashboard API Routes
🔍 Provides endpoints for the ETL validation pipeline dashboard.
🌐 Supports ALL Indian languages — Zero data loss
"""
from flask import Blueprint, jsonify, request
from sqlalchemy import text
from database.session import engine
import logging

logger = logging.getLogger("ValidationDashboard")
validation_dashboard_bp = Blueprint("validation_dashboard", __name__)

# 🗄️ Table Names
CLEAN_TABLE = "raw_clean_google_map_data"
RAW_TABLE = "raw_google_map_drive_data"
MASTER_TABLE = "g_map_master_table"


def execute_read(query, params=None):
    """⚡ Fast read query executor with READ UNCOMMITTED for speed."""
    with engine.connect() as conn:
        conn.execute(text("SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED"))
        result = conn.execute(text(query), params or {})
        return result.fetchall()


# ═══════════════════════════════════════════════════════════════════
# 📊 MAIN DASHBOARD — All stats in one call
# ═══════════════════════════════════════════════════════════════════

@validation_dashboard_bp.route("/api/validation/dashboard", methods=["GET"])
def get_validation_dashboard():
    """📊 Main dashboard endpoint — refactored for Tier 1/2/3 Architecture."""
    try:
        # 📈 1. Overall counts (Real-time)
        raw_count = execute_read(f"SELECT COUNT(*) FROM {RAW_TABLE}")[0][0]
        clean_count = execute_read(f"SELECT COUNT(*) FROM {CLEAN_TABLE}")[0][0]
        
        # 🔄 2. Processing Stats (from Logs)
        log_totals = execute_read("""
            SELECT SUM(total_processed), SUM(missing_count), SUM(valid_count), SUM(duplicate_count), MAX(last_id)
            FROM data_validation_log
        """)[0]
        
        total_p = int(log_totals[0] or 0)
        missing = int(log_totals[1] or 0)
        valid = int(log_totals[2] or 0)
        duplicate = int(log_totals[3] or 0)
        last_id = int(log_totals[4] or 0)
        
        # 🏷️ 3. Validation status breakdown (derived)
        pending = max(0, raw_count - last_id)
        
        validation_breakdown = {
            "PENDING": pending,
            "VALID": clean_count,
            "MISSING": missing,
            "DUPLICATE": duplicate
        }

        # 📊 4. Pipeline progress percentage
        ingestion_pct = 100 # Ingestion is direct now
        validation_pct = round((last_id / raw_count * 100), 2) if raw_count > 0 else 0
        cleaning_pct = round((clean_count / raw_count * 100), 2) if raw_count > 0 else 0

        # ❌ 5. Error rows (most recent 100)
        error_rows = execute_read(f"""
            SELECT id, raw_id, name, city, state, category, phone_number, bank_number, 
                   validation_label, error_reason, missing_fields, invalid_format_fields, created_at
            FROM {INVALID_TABLE}
            ORDER BY created_at DESC
            LIMIT 100
        """)
        errors = []
        for r in error_rows:
            errors.append({
                "id": r[0], "raw_id": r[1], "name": r[2], "city": r[3], "state": r[4],
                "category": r[5], "phone_number": r[6], "bank_number": r[7],
                "validation_status": r[8], "error_reason": r[9],
                "missing_fields": r[10], "invalid_format_fields": r[11],
                "processed_at": str(r[12]) if r[12] else None
            })

        # ✅ 6. Clean data sample
        clean_rows = execute_read(f"""
            SELECT id, raw_id, name, address, phone_number, category, city, state, reviews_count, reviews_avg, created_at
            FROM {CLEAN_TABLE}
            ORDER BY id DESC
            LIMIT 50
        """)
        clean_data = []
        for r in clean_rows:
            clean_data.append({
                "id": r[0], "raw_id": r[1], "name": r[2], "address": r[3],
                "phone_number": r[4], "category": r[5], "city": r[6], "state": r[7],
                "reviews_count": r[8], "reviews_avg": float(r[9] or 0), "created_at": str(r[10]) if r[10] else None
            })

        return jsonify({
            "status": "success",
            "raw_count": raw_count,
            "validation_count": last_id, # How far we've processed from raw
            "clean_count": clean_count,
            "validation_breakdown": validation_breakdown,
            "progress": {
                "ingestion_pct": ingestion_pct,
                "validation_pct": validation_pct,
                "cleaning_pct": cleaning_pct
            },
            "summary": {
                "pending": pending,
                "valid": clean_count,
                "missing": missing,
                "duplicate": duplicate
            },
            "errors": [],
            "clean_data": clean_data
        })

    except Exception as e:
        logger.error(f"🔥 Validation Dashboard Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


# ═══════════════════════════════════════════════════════════════════
# ❌ ERRORS — Paginated error rows
# ═══════════════════════════════════════════════════════════════════

@validation_dashboard_bp.route("/api/validation/errors", methods=["GET"])
def get_validation_errors():
    """❌ Return empty list (Invalid Table removed)."""
    return jsonify({"status": "success", "data": [], "page": 1, "total": 0})


# ═══════════════════════════════════════════════════════════════════
# ✅ CLEAN DATA — Paginated production data
# ═══════════════════════════════════════════════════════════════════

@validation_dashboard_bp.route("/api/validation/clean", methods=["GET"])
def get_clean_data():
    """✅ Paginated clean/production data."""
    page = int(request.args.get("page", 1))
    limit = int(request.args.get("limit", 50))
    offset = (page - 1) * limit

    try:
        rows = execute_read(f"""
            SELECT id, raw_id, name, address, website, phone_number, toll_free_number, reviews_count, reviews_avg,
                   category, subcategory, city, state, area, created_at
            FROM {CLEAN_TABLE}
            ORDER BY id DESC
            LIMIT :limit OFFSET :offset
        """, {"limit": limit, "offset": offset})

        data = []
        for r in rows:
            data.append({
                "id": r[0], "raw_id": r[1], "name": r[2], "address": r[3], "website": r[4],
                "phone_number": r[5], "toll_free_number": r[6], "reviews_count": r[7], "reviews_avg": float(r[8] or 0),
                "category": r[9], "subcategory": r[10], "city": r[11], "state": r[12],
                "area": r[13], "created_at": str(r[14]) if r[14] else None
            })

        total = execute_read(f"SELECT COUNT(*) FROM {CLEAN_TABLE}")[0][0]
        return jsonify({"status": "success", "data": data, "page": page, "total": total})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ═══════════════════════════════════════════════════════════════════
# 📈 VALIDATION REPORT — Detailed analytics
# ═══════════════════════════════════════════════════════════════════

@validation_dashboard_bp.route("/api/validation/report", methods=["GET"])
def get_validation_report():
    """📈 Detailed analytics from logs and production tables."""
    try:
        # 🎯 1. KPIs
        raw_count = execute_read(f"SELECT COUNT(*) FROM {RAW_TABLE}")[0][0]
        clean_count = execute_read(f"SELECT COUNT(*) FROM {CLEAN_TABLE}")[0][0]
        
        log_totals = execute_read("""
            SELECT SUM(total_processed), MAX(timestamp)
            FROM data_validation_log
        """)[0]
        
        total_p = int(log_totals[0] or 0)
        last_updated = log_totals[1]
        
        accuracy = round((clean_count / total_p * 100), 2) if total_p > 0 else 0

        # 🔍 2. Issues Report (derived from log)
        issue_report = [
            {"type": "MISSING", "count": int(execute_read("SELECT SUM(missing_count) FROM data_validation_log")[0][0] or 0)},
            {"type": "DUPLICATE", "count": int(execute_read("SELECT SUM(duplicate_count) FROM data_validation_log")[0][0] or 0)}
        ]

        # 📈 3. 7-Day Trend (from log)
        trend_rows = execute_read("""
            SELECT DATE(timestamp) as d, SUM(total_processed) 
            FROM data_validation_log
            WHERE timestamp >= DATE_SUB(NOW(), INTERVAL 7 DAY)
            GROUP BY d ORDER BY d ASC
        """)
        trend = [{"date": str(r[0]), "count": int(r[1])} for r in trend_rows]

        report_data = {
            "status": "success",
            "kpis": {
                "total": total_p,
                "valid": clean_count,
                "accuracy": accuracy,
                "last_updated": str(last_updated) if last_updated else None
            },
            "issue_report": issue_report,
            "trend": trend,
            "state_stats": []
        }

        # 🗺️ 4. State-wise Breakdown (Quality per state)
        state_rows = execute_read(f"""
            SELECT 
                state,
                COUNT(*) as total
            FROM {CLEAN_TABLE}
            GROUP BY state
            ORDER BY total DESC
            LIMIT 15
        """)
        
        for r in state_rows:
            report_data["state_stats"].append({
                "state": r[0] if r[0] else "Unknown",
                "total": int(r[1]),
                "status": "CLEAN"
            })

        return jsonify(report_data)
    except Exception as e:
        logger.error(f"🔥 Report API error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


# ═══════════════════════════════════════════════════════════════════
# 🔄 SYNC OPERATIONS — Trigger GDrive Sync from UI
# ═══════════════════════════════════════════════════════════════════

import threading
from force_sync_missing_rows import process_missing_rows

# Concurrency locks
is_syncing = False
sync_lock = threading.Lock()

@validation_dashboard_bp.route("/api/validation/sync-now", methods=["POST"])
def trigger_sync():
    global is_syncing
    with sync_lock:
        if is_syncing:
            return jsonify({
                "status": "busy", 
                "message": "A database sync is already in progress in the background."
            }), 400
        is_syncing = True

    def run_sync():
        global is_syncing
        try:
            logger.info("🔄 UI-triggered GDrive database sync started in the background.")
            process_missing_rows()
            logger.info("✅ UI-triggered GDrive database sync completed successfully.")
        except Exception as se:
            logger.error(f"🔥 UI-triggered GDrive database sync failed: {se}")
        finally:
            with sync_lock:
                is_syncing = False

    # Start the task in a background thread to prevent Gateway Timeout
    thread = threading.Thread(target=run_sync)
    thread.daemon = True
    thread.start()

    return jsonify({
        "status": "success", 
        "message": "Database sync started successfully in the background."
    }), 202


@validation_dashboard_bp.route("/api/validation/sync-status", methods=["GET"])
def get_sync_status():
    global is_syncing
    return jsonify({
        "status": "success",
        "is_syncing": is_syncing
    })

