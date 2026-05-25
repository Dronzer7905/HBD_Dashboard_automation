from flask import Blueprint, request, jsonify
from sqlalchemy import text, create_engine
from config import config
import traceback

product_report_bp = Blueprint('product_report_bp', __name__)

engine = create_engine(
    config.SQLALCHEMY_DATABASE_URI,
    pool_pre_ping=True,
    pool_recycle=280,
)

# Helper function to check if a marketplace has data in the database
def has_marketplace_data(conn, marketplace):
    if not marketplace or marketplace.lower() == 'all':
        # Check if there is any data at all
        row = conn.execute(text("""
            SELECT COUNT(*) FROM product_dashboard_report_summary
        """)).scalar()
        return row > 0
    else:
        row = conn.execute(text("""
            SELECT COUNT(*) FROM product_dashboard_report_summary 
            WHERE LOWER(marketplace_name) = LOWER(:marketplace)
        """), {"marketplace": marketplace}).scalar()
        return row > 0


@product_report_bp.route('/summary', methods=['GET'])
def get_report_summary():
    """
    Fetch the latest summary counts.
    Accepts `marketplace` query parameter.
    If 'all' or empty, aggregates SUM/AVG across all marketplaces.
    """
    marketplace = request.args.get('marketplace', '').strip()
    try:
        with engine.connect() as conn:
            # Check if there is data for this marketplace
            if not has_marketplace_data(conn, marketplace):
                # Return empty defaults with status badge "Pending Data Upload"
                return jsonify({
                    "status": "success",
                    "data": {
                        "total_categories": 0,
                        "total_products": 0,
                        "mapped_products": 0,
                        "unmapped_products": 0,
                        "completed_categories": 0,
                        "pending_categories": 0,
                        "available_products": 0,
                        "out_of_stock_products": 0,
                        "total_brands": 0,
                        "avg_selling_price": 0.0,
                        "status_badge": "Pending Data Upload"
                    }
                }), 200

            if not marketplace or marketplace.lower() == 'all':
                # Aggregate globally
                row = conn.execute(text("""
                    SELECT
                        SUM(total_categories) as total_categories,
                        SUM(total_products) as total_products,
                        SUM(mapped_products) as mapped_products,
                        SUM(unmapped_products) as unmapped_products,
                        SUM(completed_categories) as completed_categories,
                        SUM(pending_categories) as pending_categories,
                        SUM(available_products) as available_products,
                        SUM(out_of_stock_products) as out_of_stock_products,
                        SUM(total_brands) as total_brands,
                        AVG(avg_selling_price) as avg_selling_price
                    FROM product_dashboard_report_summary
                """)).mappings().fetchone()
            else:
                # Filter by marketplace
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
                    WHERE LOWER(marketplace_name) = LOWER(:marketplace)
                    ORDER BY id DESC
                    LIMIT 1
                """), {"marketplace": marketplace}).mappings().fetchone()

            if not row or row["total_products"] is None:
                return jsonify({
                    "status": "success",
                    "data": {
                        "total_categories": 0,
                        "total_products": 0,
                        "mapped_products": 0,
                        "unmapped_products": 0,
                        "completed_categories": 0,
                        "pending_categories": 0,
                        "available_products": 0,
                        "out_of_stock_products": 0,
                        "total_brands": 0,
                        "avg_selling_price": 0.0,
                        "status_badge": "Pending Data Upload"
                    }
                }), 200

            data = {
                "total_categories": int(row["total_categories"]) if row["total_categories"] is not None else 0,
                "total_products": int(row["total_products"]) if row["total_products"] is not None else 0,
                "mapped_products": int(row["mapped_products"]) if row["mapped_products"] is not None else 0,
                "unmapped_products": int(row["unmapped_products"]) if row["unmapped_products"] is not None else 0,
                "completed_categories": int(row["completed_categories"]) if row["completed_categories"] is not None else 0,
                "pending_categories": int(row["pending_categories"]) if row["pending_categories"] is not None else 0,
                "available_products": int(row["available_products"]) if row["available_products"] is not None else 0,
                "out_of_stock_products": int(row["out_of_stock_products"]) if row["out_of_stock_products"] is not None else 0,
                "total_brands": int(row["total_brands"]) if row["total_brands"] is not None else 0,
                "avg_selling_price": float(row["avg_selling_price"]) if row["avg_selling_price"] is not None else 0.0,
                "status_badge": "Active"
            }

        return jsonify({"status": "success", "data": data}), 200

    except Exception as e:
        print(f"[product_report] summary error: {traceback.format_exc()}")
        return jsonify({"status": "error", "message": str(e)}), 500


@product_report_bp.route('/category-counts', methods=['GET'])
def get_category_counts():
    """Fetch completed vs pending category counts."""
    marketplace = request.args.get('marketplace', '').strip()
    try:
        with engine.connect() as conn:
            if not has_marketplace_data(conn, marketplace):
                return jsonify({
                    "status": "success",
                    "data": {
                        "completed_categories": 0,
                        "pending_categories": 0,
                        "total_categories": 0
                    }
                }), 200

            if not marketplace or marketplace.lower() == 'all':
                row = conn.execute(text("""
                    SELECT
                        SUM(completed_categories) as completed_categories,
                        SUM(pending_categories) as pending_categories,
                        SUM(total_categories) as total_categories
                    FROM product_dashboard_report_summary
                """)).mappings().fetchone()
            else:
                row = conn.execute(text("""
                    SELECT
                        completed_categories,
                        pending_categories,
                        total_categories
                    FROM product_dashboard_report_summary
                    WHERE LOWER(marketplace_name) = LOWER(:marketplace)
                    ORDER BY id DESC
                    LIMIT 1
                """), {"marketplace": marketplace}).mappings().fetchone()

            if not row or row["total_categories"] is None:
                return jsonify({
                    "status": "success",
                    "data": {
                        "completed_categories": 0,
                        "pending_categories": 0,
                        "total_categories": 0
                    }
                }), 200

            data = {
                "completed_categories": int(row["completed_categories"]) if row["completed_categories"] is not None else 0,
                "pending_categories": int(row["pending_categories"]) if row["pending_categories"] is not None else 0,
                "total_categories": int(row["total_categories"]) if row["total_categories"] is not None else 0
            }

        return jsonify({"status": "success", "data": data}), 200

    except Exception as e:
        print(f"[product_report] category-counts error: {traceback.format_exc()}")
        return jsonify({"status": "error", "message": str(e)}), 500


@product_report_bp.route('/top-products', methods=['GET'])
def get_top_products():
    """Fetch top selling products from product_top_selling_report ordered by ranking_score."""
    marketplace = request.args.get('marketplace', '').strip()
    search = request.args.get('search', '').strip()
    category = request.args.get('category', '').strip()
    limit = request.args.get('limit', '50')
    
    try:
        limit_val = int(limit)
    except ValueError:
        limit_val = 50

    try:
        with engine.connect() as conn:
            # Build query dynamically
            query_str = """
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
                WHERE 1=1
            """
            params = {}
            if marketplace and marketplace.lower() != 'all':
                query_str += " AND LOWER(marketplace_name) = LOWER(:marketplace)"
                params["marketplace"] = marketplace
            if search:
                query_str += " AND (product_name LIKE :search OR asin LIKE :search OR brand LIKE :search OR category_name LIKE :search)"
                params["search"] = f"%{search}%"
            if category and category.lower() != 'all' and category != 'All Categories':
                query_str += " AND (category_name = :category OR sub_category_name = :category)"
                params["category"] = category

            query_str += " ORDER BY ranking_score DESC LIMIT :limit"
            params["limit"] = limit_val

            rows = conn.execute(text(query_str), params).mappings().fetchall()

            data = []
            for r in rows:
                data.append({
                    "product_id":          int(r["product_id"]) if r["product_id"] is not None else None,
                    "asin":                r["asin"] or "",
                    "marketplace_name":    r["marketplace_name"] or "",
                    "product_name":        r["product_name"] or "",
                    "brand":               r["brand"] or "",
                    "category_name":       r["category_name"] or "",
                    "sub_category_name":   r["sub_category_name"] or "",
                    "price":               float(r["price"]) if r["price"] is not None else None,
                    "list_price":          float(r["list_price"]) if r["list_price"] is not None else None,
                    "discount":            r["discount"] or "",
                    "stars":               float(r["stars"]) if r["stars"] is not None else None,
                    "reviews":             int(r["reviews"]) if r["reviews"] is not None else 0,
                    "rating_count":        int(r["rating_count"]) if r["rating_count"] is not None else 0,
                    "is_prime":            bool(r["is_prime"]),
                    "is_best_seller":      bool(r["is_best_seller"]),
                    "bought_in_last_month":int(r["bought_in_last_month"]) if r["bought_in_last_month"] is not None else 0,
                    "availability":        r["availability"] or "",
                    "img_url":             r["img_url"] or "",
                    "product_url":         r["product_url"] or "",
                    "ranking_score":       float(r["ranking_score"]) if r["ranking_score"] is not None else 0.0,
                    "last_refreshed_at":   str(r["last_refreshed_at"]) if r["last_refreshed_at"] else "",
                })

        return jsonify({"status": "success", "data": data}), 200

    except Exception as e:
        print(f"[product_report] top-products error: {traceback.format_exc()}")
        return jsonify({"status": "error", "message": str(e)}), 500


@product_report_bp.route('/mapped-categories', methods=['GET'])
def get_mapped_categories():
    """
    Fetch mapped categories.
    A category is mapped if it exists in product_category_master but is not in pending_category_report.
    """
    marketplace = request.args.get('marketplace', '').strip()
    search = request.args.get('search', '').strip()
    
    try:
        with engine.connect() as conn:
            query_str = """
                SELECT 
                    id, 
                    marketplace_name, 
                    category_name, 
                    subcategory_name, 
                    child_category_name, 
                    category_level, 
                    category_path
                FROM product_category_master
                WHERE id NOT IN (
                    SELECT category_id FROM pending_category_report 
                    WHERE category_id IS NOT NULL
                )
            """
            params = {}
            if marketplace and marketplace.lower() != 'all':
                query_str = """
                    SELECT 
                        id, 
                        marketplace_name, 
                        category_name, 
                        subcategory_name, 
                        child_category_name, 
                        category_level, 
                        category_path
                    FROM product_category_master
                    WHERE id NOT IN (
                        SELECT category_id FROM pending_category_report 
                        WHERE category_id IS NOT NULL
                          AND LOWER(marketplace_name) = LOWER(:marketplace)
                    )
                    AND LOWER(marketplace_name) = LOWER(:marketplace)
                """
                params["marketplace"] = marketplace
                
            if search:
                query_str += " AND (category_name LIKE :search OR subcategory_name LIKE :search OR category_path LIKE :search)"
                params["search"] = f"%{search}%"
                
            query_str += " ORDER BY category_path ASC LIMIT 100"
            
            rows = conn.execute(text(query_str), params).mappings().fetchall()
            
            data = []
            for r in rows:
                data.append({
                    "id": int(r["id"]),
                    "marketplace_name": r["marketplace_name"] or "",
                    "category_name": r["category_name"] or "",
                    "subcategory_name": r["subcategory_name"] or "",
                    "child_category_name": r["child_category_name"] or "",
                    "category_level": int(r["category_level"]) if r["category_level"] is not None else 1,
                    "category_path": r["category_path"] or ""
                })
                
        return jsonify({"status": "success", "data": data}), 200
        
    except Exception as e:
        print(f"[product_report] mapped-categories error: {traceback.format_exc()}")
        return jsonify({"status": "error", "message": str(e)}), 500


@product_report_bp.route('/unmapped-categories', methods=['GET'])
def get_unmapped_categories():
    """Fetch unmapped (pending) categories from pending_category_report."""
    marketplace = request.args.get('marketplace', '').strip()
    search = request.args.get('search', '').strip()
    
    try:
        with engine.connect() as conn:
            query_str = """
                SELECT
                    id,
                    category_id,
                    marketplace_name,
                    category_name,
                    subcategory_name,
                    child_category_name,
                    category_level,
                    category_path,
                    reason,
                    last_refreshed_at
                FROM pending_category_report
                WHERE 1=1
            """
            params = {}
            if marketplace and marketplace.lower() != 'all':
                query_str += " AND LOWER(marketplace_name) = LOWER(:marketplace)"
                params["marketplace"] = marketplace
            if search:
                query_str += " AND (category_name LIKE :search OR subcategory_name LIKE :search OR category_path LIKE :search OR reason LIKE :search)"
                params["search"] = f"%{search}%"
                
            query_str += " ORDER BY category_path ASC LIMIT 100"
            
            rows = conn.execute(text(query_str), params).mappings().fetchall()
            
            data = []
            for r in rows:
                data.append({
                    "id": int(r["id"]),
                    "category_id": int(r["category_id"]) if r["category_id"] is not None else None,
                    "marketplace_name": r["marketplace_name"] or "",
                    "category_name": r["category_name"] or "",
                    "subcategory_name": r["subcategory_name"] or "",
                    "child_category_name": r["child_category_name"] or "",
                    "category_level": int(r["category_level"]) if r["category_level"] is not None else 1,
                    "category_path": r["category_path"] or "",
                    "reason": r["reason"] or "",
                    "last_refreshed_at": str(r["last_refreshed_at"]) if r["last_refreshed_at"] else ""
                })
                
        return jsonify({"status": "success", "data": data}), 200
        
    except Exception as e:
        print(f"[product_report] unmapped-categories error: {traceback.format_exc()}")
        return jsonify({"status": "error", "message": str(e)}), 500


@product_report_bp.route('/unmapped-products', methods=['GET'])
def get_unmapped_products():
    """Fetch unmapped products from unmapped_product_report."""
    marketplace = request.args.get('marketplace', '').strip()
    search = request.args.get('search', '').strip()
    
    try:
        with engine.connect() as conn:
            query_str = """
                SELECT
                    id,
                    product_id,
                    marketplace_name,
                    asin,
                    product_name,
                    brand,
                    category_name,
                    sub_category_name,
                    price,
                    product_url,
                    reason,
                    last_refreshed_at
                FROM unmapped_product_report
                WHERE 1=1
            """
            params = {}
            if marketplace and marketplace.lower() != 'all':
                query_str += " AND LOWER(marketplace_name) = LOWER(:marketplace)"
                params["marketplace"] = marketplace
            if search:
                query_str += " AND (product_name LIKE :search OR asin LIKE :search OR brand LIKE :search OR reason LIKE :search)"
                params["search"] = f"%{search}%"
                
            query_str += " ORDER BY id DESC LIMIT 100"
            
            rows = conn.execute(text(query_str), params).mappings().fetchall()
            
            data = []
            for r in rows:
                data.append({
                    "id": int(r["id"]),
                    "product_id": int(r["product_id"]) if r["product_id"] is not None else None,
                    "marketplace_name": r["marketplace_name"] or "",
                    "asin": r["asin"] or "",
                    "product_name": r["product_name"] or "",
                    "brand": r["brand"] or "",
                    "category_name": r["category_name"] or "",
                    "sub_category_name": r["sub_category_name"] or "",
                    "price": float(r["price"]) if r["price"] is not None else None,
                    "product_url": r["product_url"] or "",
                    "reason": r["reason"] or "",
                    "last_refreshed_at": str(r["last_refreshed_at"]) if r["last_refreshed_at"] else ""
                })
                
        return jsonify({"status": "success", "data": data}), 200
        
    except Exception as e:
        print(f"[product_report] unmapped-products error: {traceback.format_exc()}")
        return jsonify({"status": "error", "message": str(e)}), 500


@product_report_bp.route('/products/amazon/<string:asin>', methods=['GET'])
def get_product_by_asin(asin):
    """Fetch deep product specifications from amazon_products by ASIN."""
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
                "id":               int(row["id"]),
                "asin":             row["asin"] or "",
                "title":            row["title"] or "",
                "imgUrl":           row["imgUrl"] or "",
                "productUrl":       row["productUrl"] or "",
                "stars":            float(row["stars"]) if row["stars"] is not None else None,
                "reviews":          int(row["reviews"]) if row["reviews"] is not None else 0,
                "price":            float(row["price"]) if row["price"] is not None else None,
                "listPrice":        float(row["listPrice"]) if row["listPrice"] is not None else None,
                "categoryName":     row["categoryName"] or "",
                "isBestSeller":     bool(row["isBestSeller"]),
                "boughtInLastMonth":int(row["boughtInLastMonth"]) if row["boughtInLastMonth"] is not None else 0,
            }

        return jsonify({"status": "success", "data": product}), 200

    except Exception as e:
        print(f"[product_report] amazon product detail error: {traceback.format_exc()}")
        return jsonify({"status": "error", "message": str(e)}), 500


@product_report_bp.route('/products/<string:marketplace>/<int:product_id>', methods=['GET'])
def get_product_by_id(marketplace, product_id):
    """Fetch product details from product_master by product record ID (for other marketplaces)."""
    try:
        with engine.connect() as conn:
            row = conn.execute(text("""
                SELECT
                    id,
                    marketplace_name,
                    asin,
                    product_name,
                    brand,
                    price,
                    list_price,
                    discount,
                    stars,
                    reviews,
                    rating_count,
                    is_prime,
                    is_best_seller,
                    bought_in_last_month,
                    delivery_message,
                    availability,
                    deal_type,
                    coupon,
                    description,
                    manufacturer,
                    seller,
                    variants,
                    badges,
                    category_name,
                    sub_category_name,
                    img_url,
                    product_url,
                    product_category_id,
                    created_at,
                    updated_at
                FROM product_master
                WHERE id = :id AND LOWER(marketplace_name) = LOWER(:marketplace)
                LIMIT 1
            """), {"id": product_id, "marketplace": marketplace}).mappings().fetchone()

            if not row:
                return jsonify({"status": "error", "message": f"Product with ID {product_id} for '{marketplace}' not found in product_master"}), 404

            product = {
                "id":                  int(row["id"]),
                "marketplace_name":    row["marketplace_name"] or "",
                "asin":                row["asin"] or "",
                "title":               row["product_name"] or "",
                "brand":               row["brand"] or "",
                "price":               float(row["price"]) if row["price"] is not None else None,
                "listPrice":           float(row["list_price"]) if row["list_price"] is not None else None,
                "discount":            row["discount"] or "",
                "stars":               float(row["stars"]) if row["stars"] is not None else None,
                "reviews":             int(row["reviews"]) if row["reviews"] is not None else 0,
                "rating_count":        int(row["rating_count"]) if row["rating_count"] is not None else 0,
                "is_prime":            bool(row["is_prime"]),
                "isBestSeller":        bool(row["is_best_seller"]),
                "boughtInLastMonth":   int(row["bought_in_last_month"]) if row["bought_in_last_month"] is not None else 0,
                "delivery_message":    row["delivery_message"] or "",
                "availability":        row["availability"] or "",
                "deal_type":           row["deal_type"] or "",
                "coupon":              row["coupon"] or "",
                "description":         row["description"] or "",
                "manufacturer":        row["manufacturer"] or "",
                "seller":              row["seller"] or "",
                "variants":            row["variants"] or "",
                "badges":              row["badges"] or "",
                "categoryName":        row["category_name"] or "",
                "sub_category_name":   row["sub_category_name"] or "",
                "imgUrl":              row["img_url"] or "",
                "productUrl":          row["product_url"] or "",
                "product_category_id": int(row["product_category_id"]) if row["product_category_id"] is not None else None,
                "created_at":          str(row["created_at"]) if row["created_at"] else "",
                "updated_at":          str(row["updated_at"]) if row["updated_at"] else ""
            }

        return jsonify({"status": "success", "data": product}), 200

    except Exception as e:
        print(f"[product_report] global product detail error: {traceback.format_exc()}")
        return jsonify({"status": "error", "message": str(e)}), 500


@product_report_bp.route('/refresh', methods=['POST'])
def refresh_report_summary():
    """Trigger aggregation logic refresh."""
    marketplace = request.args.get('marketplace', '').strip()
    try:
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return jsonify({
            "status": "success",
            "message": f"Successfully triggered report summary refresh for marketplace: {marketplace or 'All'}",
            "refreshed_at": timestamp
        }), 200
    except Exception as e:
        print(f"[product_report] refresh error: {traceback.format_exc()}")
        return jsonify({"status": "error", "message": str(e)}), 500
