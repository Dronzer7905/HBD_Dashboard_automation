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
from sqlalchemy import func, and_, or_
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
@item_duplicate_bp.route("/items/duplicates", methods=["GET"])
def get_duplicate_items():
    db: Session = SessionLocal()
    try:
        page = int(request.args.get("page", 1))
        limit = int(request.args.get("limit", 10))
        offset = (page - 1) * limit

        # Step 1: Group by duplicate keys
        duplicate_groups = (
            db.query(
                ItemData.name,
                ItemData.category,
                ItemData.sub_category,
                ItemData.email,
                ItemData.city,
                ItemData.area,
                ItemData.address,
                func.count(ItemData.id).label("count"),
            )
            .group_by(
                ItemData.name,
                ItemData.category,
                ItemData.sub_category,
                ItemData.email,
                ItemData.city,
                ItemData.area,
                ItemData.address,
            )
            .having(func.count(ItemData.id) > 1)
            .subquery()
        )

        # Step 2: Subquery to find minimum ID (first occurrence) of each duplicate group
        min_ids_subquery = (
            db.query(
                func.min(ItemData.id).label("min_id")
            )
            .group_by(
                ItemData.name,
                ItemData.category,
                ItemData.sub_category,
                ItemData.email,
                ItemData.city,
                ItemData.area,
                ItemData.address,
            )
            .having(func.count(ItemData.id) > 1)
            .subquery()
        )

        # Step 3: Join with duplicate groups, and filter where ID != min_id (getting the duplicates we want to show/delete)
        duplicates_query = (
            db.query(ItemData)
            .join(
                duplicate_groups,
                and_(
                    ItemData.name == duplicate_groups.c.name,
                    ItemData.category == duplicate_groups.c.category,
                    ItemData.sub_category == duplicate_groups.c.sub_category,
                    ItemData.email == duplicate_groups.c.email,
                    ItemData.city == duplicate_groups.c.city,
                    ItemData.area == duplicate_groups.c.area,
                    ItemData.address == duplicate_groups.c.address,
                ),
            )
            .outerjoin(
                min_ids_subquery,
                ItemData.id == min_ids_subquery.c.min_id
            )
            .filter(
                min_ids_subquery.c.min_id.is_(None)
            )
        )

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
            "total": total_duplicates,
            "total_pages": (total_duplicates + limit - 1) // limit,
            "items": result,
        })

    finally:
        db.close()


# ---------------- DUPLICATES DELETE ----------------
@item_duplicate_bp.route("/items/duplicates", methods=["DELETE"])
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
