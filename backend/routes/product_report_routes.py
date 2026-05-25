from flask import Blueprint, request, jsonify
from sqlalchemy import text, create_engine
from config import config

product_report_bp = Blueprint('product_report_bp', __name__)

engine = create_engine(
    config.SQLALCHEMY_DATABASE_URI,
    pool_pre_ping=True,
    pool_recycle=280,
)


@product_report_bp.route('/summary', methods=['GET'])
def get_report_summary():
    """Fetch the latest summary counts from product_dashboard_report_summary."""
    try:
        with engine.connect() as conn:
            row = conn.execute(text("""
                SELECT
                    total_categories,
                    total_products,
                    mapped_products,
                    unmapped_products,
                    completed_categories,
                    pending_categories,
                    available_products,
                    out_of_stock_products,
                    total_brands,
                    avg_selling_price
                FROM product_dashboard_report_summary
                ORDER BY id DESC
                LIMIT 1
            """)).mappings().fetchone()

            if not row:
                return jsonify({"status": "success", "data": None}), 200

            data = {
                "total_categories": row["total_categories"] or 0,
                "total_products": row["total_products"] or 0,
                "mapped_products": row["mapped_products"] or 0,
                "unmapped_products": row["unmapped_products"] or 0,
                "completed_categories": row["completed_categories"] or 0,
                "pending_categories": row["pending_categories"] or 0,
                "available_products": row["available_products"] or 0,
                "out_of_stock_products": row["out_of_stock_products"] or 0,
                "total_brands": row["total_brands"] or 0,
                "avg_selling_price": float(row["avg_selling_price"]) if row["avg_selling_price"] else 0.0,
            }

        return jsonify({"status": "success", "data": data}), 200

    except Exception as e:
        import traceback
        print(f"[product_report] summary error: {traceback.format_exc()}")
        return jsonify({"status": "error", "message": str(e)}), 500


@product_report_bp.route('/top-products', methods=['GET'])
def get_top_products():
    """Fetch top selling products from product_top_selling_report ordered by ranking_score."""
    try:
        with engine.connect() as conn:
            rows = conn.execute(text("""
                SELECT
                    product_id,
                    asin,
                    marketplace_name,
                    product_name,
                    brand,
                    category_name,
                    sub_category_name,
                    price,
                    list_price,
                    discount,
                    stars,
                    reviews,
                    rating_count,
                    is_prime,
                    is_best_seller,
                    bought_in_last_month,
                    availability,
                    img_url,
                    product_url,
                    ranking_score,
                    last_refreshed_at
                FROM product_top_selling_report
                ORDER BY ranking_score DESC
                LIMIT 20
            """)).mappings().fetchall()

            data = []
            for r in rows:
                data.append({
                    "product_id":          r["product_id"],
                    "asin":                r["asin"] or "",
                    "marketplace_name":    r["marketplace_name"] or "",
                    "product_name":        r["product_name"] or "",
                    "brand":               r["brand"] or "",
                    "category_name":       r["category_name"] or "",
                    "sub_category_name":   r["sub_category_name"] or "",
                    "price":               float(r["price"]) if r["price"] else None,
                    "list_price":          float(r["list_price"]) if r["list_price"] else None,
                    "discount":            r["discount"] or "",
                    "stars":               float(r["stars"]) if r["stars"] else None,
                    "reviews":             r["reviews"] or 0,
                    "rating_count":        r["rating_count"] or 0,
                    "is_prime":            bool(r["is_prime"]),
                    "is_best_seller":      bool(r["is_best_seller"]),
                    "bought_in_last_month":r["bought_in_last_month"] or 0,
                    "availability":        r["availability"] or "",
                    "img_url":             r["img_url"] or "",
                    "product_url":         r["product_url"] or "",
                    "ranking_score":       float(r["ranking_score"]) if r["ranking_score"] else 0,
                    "last_refreshed_at":   str(r["last_refreshed_at"]) if r["last_refreshed_at"] else "",
                })

        return jsonify({"status": "success", "data": data}), 200

    except Exception as e:
        import traceback
        print(f"[product_report] top-products error: {traceback.format_exc()}")
        return jsonify({"status": "error", "message": str(e)}), 500


@product_report_bp.route('/products/<string:asin>', methods=['GET'])
def get_product_by_asin(asin):
    """Fetch product details from amazon_products by ASIN."""
    try:
        with engine.connect() as conn:
            row = conn.execute(text("""
                SELECT
                    id,
                    asin,
                    title,
                    imgUrl,
                    productUrl,
                    stars,
                    reviews,
                    price,
                    listPrice,
                    categoryName,
                    isBestSeller,
                    boughtInLastMonth
                FROM amazon_products
                WHERE asin = :asin
                LIMIT 1
            """), {"asin": asin}).mappings().fetchone()

            if not row:
                return jsonify({"status": "error", "message": f"Product with ASIN '{asin}' not found in amazon_products"}), 404

            product = {
                "id":               row["id"],
                "asin":             row["asin"] or "",
                "title":            row["title"] or "",
                "imgUrl":           row["imgUrl"] or "",
                "productUrl":       row["productUrl"] or "",
                "stars":            float(row["stars"]) if row["stars"] else None,
                "reviews":          row["reviews"] or 0,
                "price":            float(row["price"]) if row["price"] else None,
                "listPrice":        float(row["listPrice"]) if row["listPrice"] else None,
                "categoryName":     row["categoryName"] or "",
                "isBestSeller":     bool(row["isBestSeller"]),
                "boughtInLastMonth":row["boughtInLastMonth"] or 0,
            }

        return jsonify({"status": "success", "data": product}), 200

    except Exception as e:
        import traceback
        print(f"[product_report] product detail error: {traceback.format_exc()}")
        return jsonify({"status": "error", "message": str(e)}), 500
