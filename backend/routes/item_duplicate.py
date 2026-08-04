# from flask import Blueprint, jsonify, Response, stream_with_context
# from sqlalchemy import func
# from database.session import SessionLocal
# from model.item_csv_model import ItemData

# item_duplicate_bp = Blueprint("item_duplicate", __name__)

# # Helper
# def serialize(item):
#     data = item.__dict__.copy()
#     data.pop("_sa_instance_state", None)
#     return data


# # Duplicate Items API (JSON response)
# @item_duplicate_bp.route("/items/duplicates", methods=["GET"])
# def get_duplicate_items():
#     db = SessionLocal()
#     try:
#         # Find duplicates by (name, category, sub_category, email, city)
#         subquery = (
#             db.query(
#                 ItemData.name,
#                 ItemData.category,
#                 ItemData.sub_category,
#                 ItemData.email,
#                 ItemData.city,
#                 ItemData.area,
#                 ItemData.address,
#                 func.count(ItemData.id).label("count")   
#             )
#             .group_by(
#                 ItemData.name,
#                 ItemData.category,
#                 ItemData.sub_category,
#                 ItemData.email,
#                 ItemData.city,
#                 ItemData.area,
#                 ItemData.address
#             )
#             .having(func.count(ItemData.name) > 1)
#             .subquery()
#         )

#         # Get all rows that match duplicates
#         duplicates = (
#             db.query(ItemData)
#             .join(
#                 subquery,
#                 (ItemData.name == subquery.c.name) &
#                 (ItemData.category == subquery.c.category) &
#                 (ItemData.sub_category == subquery.c.sub_category) &
#                 (ItemData.email == subquery.c.email) &
#                 (ItemData.area == subquery.c.area) &
#                 (ItemData.city == subquery.c.city)&
#                 (ItemData.address == subquery.c.address)
#             )
#             .all()
#         )

#         # Group by combination & remove first entry
#         result = []
#         seen = set()
#         for item in duplicates:
#             key = (item.name, item.category, item.sub_category, item.email, item.city, item.area, item.address)
#             if key not in seen:
#                 seen.add(key)   # keep first one
#             else:
#                 result.append(serialize(item))  # duplicates

#         return jsonify({"total": len(result), "items": result})
#     finally:
#         db.close()


# # Duplicate Items CSV Download
# @item_duplicate_bp.route("/items/duplicates/csv", methods=["GET"])
# def download_duplicate_items():
#     db = SessionLocal()
#     try:
#         # Step 1: Find duplicate groups
#         subquery = (
#             db.query(
#                 ItemData.name,
#                 ItemData.category,
#                 ItemData.sub_category,
#                 ItemData.email,
#                 ItemData.city,
#                 ItemData.area,
#                 func.count(ItemData.id).label("count")  
#             )
#             .group_by(
#                 ItemData.name,
#                 ItemData.category,
#                 ItemData.sub_category,
#                 ItemData.email,
#                 ItemData.city,
#                 ItemData.area
#             )
#             .having(func.count(ItemData.name) > 1)
#             .subquery()
#         )

#         # Step 2: Join with original table
#         duplicates = (
#             db.query(ItemData)
#             .join(
#                 subquery,
#                 (ItemData.name == subquery.c.name) &
#                 (ItemData.category == subquery.c.category) &
#                 (ItemData.sub_category == subquery.c.sub_category) &
#                 (ItemData.email == subquery.c.email) &
#                 (ItemData.area == subquery.c.area) &
#                 (ItemData.city == subquery.c.city)
#             )
#             .all()
#         )

#         # Step 3: Exclude first occurrence
#         result = []
#         seen = set()
#         for item in duplicates:
#             key = (item.name, item.category, item.sub_category, item.email, item.city, item.area)
#             if key not in seen:
#                 seen.add(key)
#             else:
#                 result.append(item)

#         # Step 4: Generate CSV
#         def generate():
#             data = [c.name for c in ItemData.__table__.columns]  # all 27 fields
#             yield ",".join(data) + "\n"

#             for item in result:
#                 row = [
#                     str(getattr(item, col)) if getattr(item, col) is not None else ""
#                     for col in data
#                 ]
#                 yield ",".join(row) + "\n"

#         return Response(
#             stream_with_context(generate()),
#             mimetype="text/csv",
#             headers={"Content-Disposition": "attachment; filename=duplicates_data.csv"}
#         )
#     finally:
#         db.close()


from flask import Blueprint, request, jsonify
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, text
from sqlalchemy.exc import OperationalError
import logging
from database.session import SessionLocal
from model.item_csv_model import ItemData

item_duplicate_bp = Blueprint("item_duplicate", __name__)

# Serializer
def serialize(item):
    return {
        "id": item.id,
        "name": item.name,
        "category": item.category,
        "sub_category": item.sub_category,
        "email": item.email,
        "city": item.city,
        "area": item.area,
        "address": item.address,
        "phone_no_1": item.phone_no_1,
        "phone_no_2": item.phone_no_2,
        "phone_no_3": item.phone_no_3,
        "whatsapp_no": item.whatsapp_no,
        "virtual_phone_no": item.virtual_phone_no,
        "avg_spent": item.avg_spent,
        "cost_for_two": item.cost_for_two,
        "source": item.source,
        "ratings": item.ratings,
        "reviews": item.reviews,
        "facebook_url": item.facebook_url,
        "linkedin_url": item.linkedin_url,
        "twitter_url": item.twitter_url,
        "description": item.description,
        "pincode": item.pincode,
        "state": item.state,
        "country": item.country,
        "latitude": item.latitude,
        "longitude": item.longitude,
    }


# ---------------- DUPLICATES FETCH ----------------
# TODO (long-term fix): Precompute duplicates via a Celery task into a
# dedicated `duplicate_items` table (or add `is_duplicate` + `duplicate_group_id`
# columns to `item_data`).  This endpoint would then become a simple
# SELECT ... WHERE is_duplicate = true with pagination — no live GROUP BY/JOIN.
# The two full-table GROUP BY scans below are O(N) on every page load and will
# time out once `item_data` grows past ~500k rows.
@item_duplicate_bp.route("/duplicates", methods=["GET"])
def get_duplicate_items():
    db: Session = SessionLocal()
    try:
        # Stopgap: cap MySQL query execution time to 30 seconds so a slow
        # query returns a clear timeout error instead of dropping the connection.
        db.execute(text("SET SESSION max_execution_time = 30000"))

        page = int(request.args.get("page", 1))
        limit = int(request.args.get("limit", 10))
        offset = (page - 1) * limit

        # Simple duplicate flag query
        duplicates_query = db.query(ItemData).filter(ItemData.is_duplicate == True)


        # Apply search and city filters
        search = request.args.get("search", "").strip()
        city = request.args.get("city", "").strip()

        if search:
            duplicates_query = duplicates_query.filter(
                or_(
                    ItemData.name.ilike(f"%{search}%"),
                    ItemData.category.ilike(f"%{search}%"),
                    ItemData.sub_category.ilike(f"%{search}%"),
                    ItemData.area.ilike(f"%{search}%"),
                    ItemData.address.ilike(f"%{search}%"),
                )
            )
        if city:
            duplicates_query = duplicates_query.filter(ItemData.city.ilike(f"%{city}%"))

        # Count total filtered duplicates
        total_duplicates = duplicates_query.count()

        # Paginate results
        paginated_duplicates = duplicates_query.order_by(ItemData.id).offset(offset).limit(limit).all()

        result = [serialize(item) for item in paginated_duplicates]

        return jsonify({
    "success": True,
    "page": page,
    "limit": limit,
    "total_records": total_duplicates,
    "total_pages": (total_duplicates + limit - 1) // limit,
    "data": result,
})

    except OperationalError as e:
        # MySQL connection drop or query timeout (max_execution_time exceeded)
        error_msg = str(e.orig) if hasattr(e, "orig") else str(e)
        print(f"[DUPLICATE QUERY] OperationalError: {error_msg}")
        return jsonify({
            "success": False,
            "message": "Duplicate query timed out — the dataset is too large for live computation. "
                       "A precomputed duplicate table (Celery task) is needed.",
            "error": error_msg,
        }), 504

    except Exception as e:
        print(f"[DUPLICATE QUERY] Unexpected error: {str(e)}")
        return jsonify({
            "success": False,
            "message": "Failed to fetch duplicate data",
            "error": str(e),
        }), 500

    finally:
        db.close()


# ---------------- DUPLICATES DELETE ----------------
@item_duplicate_bp.route("/duplicates", methods=["DELETE"])
def delete_selected_duplicates():
    db: Session = SessionLocal()
    try:
        data = request.get_json()
        ids_to_delete = data.get("ids", [])

        if not ids_to_delete:
            return jsonify({"error": "No IDs provided"}), 400

        # Delete only those ids
        deleted_count = (
            db.query(ItemData)
            .filter(ItemData.id.in_(ids_to_delete))
            .delete(synchronize_session=False)
        )
        db.commit()

        return jsonify({
            "success": True,
            "message": "Selected duplicates deleted successfully",
            "deleted_count": deleted_count,
            "deleted_ids": ids_to_delete
        })
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)})
    finally:
        db.close()
