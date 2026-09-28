"""
Data Enrichment reporting routes (read-only).

Live counts and chart-ready breakdowns for the six product-schema tables that
were populated for the new website:
    product_catalogue, page_product_categories, affiliate_products,
    page_products, product_attributes_master, product_attributes

Endpoints (all under /api/data-enrichment):
    GET /all-tables            everything in one: counts, columns, platforms, levels, attributes
    GET /summary               row count of each table
    GET /categories            page_product_categories by level + parent-link health
    GET /products-by-platform  page_products by source marketplace
    GET /attributes            filled attribute values per attribute (Brand, MRP ...)

Uses the shared reports connection (utils/reports_db.py -> REPORTS_DB_URL),
so it reads the PostgreSQL database where these tables live. Add
?refresh=true to bypass the short cache.
"""

import traceback

from flask import Blueprint, jsonify, request

from utils.reports_db import cached, now_iso, pct, report_connection, to_json_safe

data_enrichment_bp = Blueprint('data_enrichment_bp', __name__)

PRODUCT_TABLES = [
    ("product_catalogue", "Product Catalogue", "One row per product (master product list)"),
    ("page_product_categories", "Categories", "Category tree with parent-child levels"),
    ("affiliate_products", "Affiliate Products", "Products linked to an affiliate (Amazon) listing"),
    ("page_products", "Page Products", "Products from 8 marketplaces, linked to a category"),
    ("product_attributes_master", "Attribute Definitions", "Which attributes each category has"),
    ("product_attributes", "Attribute Values", "One row per product per filled attribute"),
]

# Slug prefixes used when each marketplace's products were inserted into
# page_products - used to attribute rows back to their source platform
# without needing a dedicated source column.
PLATFORM_PREFIX_MAP = [
    ("amz-", "Amazon"),
    ("dmart-", "DMart"),
    ("flipkart-", "Flipkart"),
    ("bb-", "BigBasket"),
    ("blk-", "Blinkit"),
    ("zpt-", "Zepto"),
    ("im-", "IndiaMART"),
    ("jm-", "JioMart"),
]


def _refresh():
    return request.args.get("refresh", "false").lower() in ("1", "true", "yes")


def _respond(key, builder):
    try:
        payload, from_cache = cached(key, builder, refresh=_refresh())
        body = {"status": "success", "cached": from_cache}
        body.update(payload)
        return jsonify(to_json_safe(body)), 200
    except Exception as e:  # noqa: BLE001
        print(f"[data_enrichment] {key} error: {traceback.format_exc()}")
        msg = str(getattr(e, "orig", e)).strip().splitlines()[0][:500]
        return jsonify({"status": "error", "message": msg}), 500


# ─── builders (each works on an open report connection) ─────────────────────

def _summary(rc):
    counts = {}
    for key, _, _ in PRODUCT_TABLES:
        t = rc.find_table(key)
        counts[key] = rc.safe(f"count {key}", lambda t=t: rc.scalar(f"SELECT COUNT(*) FROM {rc.q(t)}")) if t else None
    counts = {k: int(v) if v is not None else 0 for k, v in counts.items()}
    counts["chart"] = [{"name": label, "count": counts[key]} for key, label, _ in PRODUCT_TABLES]
    return counts


def _categories(rc):
    t = rc.find_table("page_product_categories")
    if not t:
        rc.errors.append({"step": "categories", "error": "page_product_categories not found"})
        return {"total_categories": 0, "levels": [], "chart": []}
    lvl = rc.q(rc.find_col(t, "category_level", "level") or "category_level")
    par = rc.q(rc.find_col(t, "parent_id") or "parent_id")
    levels = rc.safe("categories by level", lambda: rc.rows(
        f"SELECT {lvl} AS category_level, COUNT(*) AS total, COUNT({par}) AS has_parent "
        f"FROM {rc.q(t)} GROUP BY {lvl} ORDER BY {lvl}"
    ), [])
    for r in levels:
        r["total"] = int(r["total"] or 0)
        r["has_parent"] = int(r["has_parent"] or 0)
        r["missing_parent"] = r["total"] - r["has_parent"]
    return {
        "total_categories": sum(r["total"] for r in levels),
        "levels": levels,
        "chart": [{"name": f"Level {r['category_level']}", "count": r["total"],
                   "has_parent": r["has_parent"], "missing_parent": r["missing_parent"]} for r in levels],
    }


def _platforms(rc):
    t = rc.find_table("page_products")
    if not t:
        rc.errors.append({"step": "platforms", "error": "page_products not found"})
        return {"total_products": 0, "platforms": [], "chart": []}
    slug = rc.q(rc.find_col(t, "slug") or "slug")
    cat = rc.q(rc.find_col(t, "category_id") or "category_id")
    params, whens = {}, []
    for i, (prefix, label) in enumerate(PLATFORM_PREFIX_MAP):
        params[f"p{i}"] = prefix + "%"
        params[f"l{i}"] = label
        whens.append(f"WHEN {slug} LIKE :p{i} THEN :l{i}")
    rows = rc.safe("products by platform", lambda: rc.rows(
        f"SELECT platform, COUNT(*) AS total, COUNT(cat) AS with_category FROM ("
        f"  SELECT CASE {' '.join(whens)} ELSE 'Other' END AS platform, {cat} AS cat FROM {rc.q(t)}"
        f") x GROUP BY platform ORDER BY total DESC", params
    ), [])
    for r in rows:
        r["total"] = int(r["total"] or 0)
        r["with_category"] = int(r["with_category"] or 0)
        r["without_category"] = r["total"] - r["with_category"]
        r["category_match_pct"] = pct(r["with_category"], r["total"])
    return {
        "total_products": sum(r["total"] for r in rows),
        "platforms": rows,
        "chart": [{"name": r["platform"], "count": r["total"], "with_category": r["with_category"],
                   "without_category": r["without_category"]} for r in rows],
    }


def _attributes(rc):
    m = rc.find_table("product_attributes_master")
    v = rc.find_table("product_attributes")
    if not (m and v):
        rc.errors.append({"step": "attributes", "error": "product_attributes tables not found"})
        return {"total_attribute_definitions": 0, "total_attribute_values": 0, "by_attribute": [], "chart": []}
    rows = rc.safe("attributes by name", lambda: rc.rows(
        f"SELECT m.name AS attribute_name, COUNT(DISTINCT m.id) AS definitions, COUNT(pa.id) AS total_values "
        f"FROM {rc.q(m)} m LEFT JOIN {rc.q(v)} pa ON pa.attribute_id = m.id "
        f"GROUP BY m.name ORDER BY total_values DESC"
    ), [])
    for r in rows:
        r["definitions"] = int(r["definitions"] or 0)
        r["total_values"] = int(r["total_values"] or 0)
    defs = rc.safe("attribute definitions", lambda: rc.scalar(f"SELECT COUNT(*) FROM {rc.q(m)}"), 0) or 0
    vals = rc.safe("attribute values", lambda: rc.scalar(f"SELECT COUNT(*) FROM {rc.q(v)}"), 0) or 0
    return {
        "total_attribute_definitions": int(defs),
        "total_attribute_values": int(vals),
        "by_attribute": rows,
        "chart": [{"name": r["attribute_name"], "count": r["total_values"]} for r in rows],
    }


def _table_details(rc, counts):
    out = []
    for key, label, purpose in PRODUCT_TABLES:
        t = rc.find_table(key)
        cols = rc.columns(t) if t else []
        out.append({
            "table": key, "label": label, "purpose": purpose, "found": bool(t),
            "rows": counts.get(key, 0), "columns_count": len(cols),
            "columns": [{"name": c, "type": dt} for c, dt in cols],
        })
    return out


def _payload(fn):
    with report_connection(timeout_ms=120000) as rc:
        data = fn(rc)
        errors = rc.errors
    return {"data": data, "errors": errors, "generated_at": now_iso()}


def _all_tables(rc):
    counts = _summary(rc)
    pp = counts.get("page_products") or 0
    return {
        "counts": counts,
        "tables": _table_details(rc, counts),
        "platforms": _platforms(rc),
        "categories": _categories(rc),
        "attributes": _attributes(rc),
        "affiliate_share_pct": pct(counts.get("affiliate_products") or 0, counts.get("product_catalogue") or 0),
        "avg_attributes_per_product": round((counts.get("product_attributes") or 0) / pp, 2) if pp else None,
    }


# ─── routes ─────────────────────────────────────────────────────────────────

@data_enrichment_bp.route('/all-tables', methods=['GET'])
def get_all_tables():
    return _respond("de:all-tables", lambda: _payload(_all_tables))


@data_enrichment_bp.route('/summary', methods=['GET'])
def get_data_enrichment_summary():
    return _respond("de:summary", lambda: _payload(_summary))


@data_enrichment_bp.route('/categories', methods=['GET'])
def get_categories_report():
    return _respond("de:categories", lambda: _payload(_categories))


@data_enrichment_bp.route('/products-by-platform', methods=['GET'])
def get_products_by_platform():
    return _respond("de:platforms", lambda: _payload(_platforms))


@data_enrichment_bp.route('/attributes', methods=['GET'])
def get_attributes_report():
    return _respond("de:attributes", lambda: _payload(_attributes))
