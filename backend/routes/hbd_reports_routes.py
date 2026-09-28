"""
HBD Reports - live, read-only report endpoints for the "Reports" sidebar section.

Every number is calculated live from the database at request time (results are
cached for a few minutes to protect the DB; add ?refresh=true to force a fresh
pull). Nothing here writes to the database.

Endpoints (all under /api/hbd-reports):
    GET /health               which database the reports are reading, table count
    GET /count-report         Dashboard_count sheet: master vs data coverage per field
    GET /ranking              Ranking_Count sheet: location type x rank, city/category ranks
    GET /field-availability   column-by-column fill rate of a table (default master_table)
    GET /hierarchy            parent-child hierarchy health of the master lists
    GET /db-tables            every table: group, subgroup, columns, row count, remarks
    GET /hbd                  HBD documentation: 5-stage pipeline + targets vs live progress

Connection settings: see utils/reports_db.py (REPORTS_DB_URL etc.).
"""

import re
import traceback

from flask import Blueprint, jsonify, request

from utils.reports_db import (
    cached,
    engine_source,
    now_iso,
    pct,
    report_connection,
    to_json_safe,
)

hbd_reports_bp = Blueprint("hbd_reports_bp", __name__)


def _refresh_requested():
    return request.args.get("refresh", "false").lower() in ("1", "true", "yes")


def _respond(key, builder, ttl=None):
    try:
        payload, from_cache = cached(key, builder, refresh=_refresh_requested(), ttl=ttl)
        body = {"status": "success", "cached": from_cache}
        body.update(payload)
        return jsonify(to_json_safe(body)), 200
    except Exception as e:  # noqa: BLE001
        print(f"[hbd_reports] {key} failed: {traceback.format_exc()}")
        msg = str(getattr(e, "orig", e)).strip().splitlines()[0][:500]
        return jsonify({"status": "error", "message": msg}), 500


# ═════════════════════════════════════════════════════════════════════════════
# 1. COUNT REPORT  (Dashboard_count sheet + Coverage Report sections 4 & 10)
# ═════════════════════════════════════════════════════════════════════════════
#
# Total Master Count = rows in the official master list for that field
# Data Count         = distinct values of that field in the real scraped data
# Coverage %         = Data Count / Total Master Count
# Matched            = distinct data values that also exist in the master list
#                      (case/space-insensitive) - used for Pending = Master - Matched
#
# "masters" is a priority list: the first table that exists is the primary
# master; any others that exist are reported alongside for transparency.

COUNT_REPORT_FIELDS = [
    {
        "field": "country", "label": "Country",
        "masters": [{"table": "countries", "name_cols": ["country_name", "name"]}],
        "data": {"table": "master_table", "cols": ["country"]},
    },
    {
        "field": "state", "label": "State",
        "masters": [{"table": "State_Master", "name_cols": ["state_name", "name"]}],
        "data": {"table": "master_table", "cols": ["state"]},
    },
    {
        "field": "city", "label": "City",
        "masters": [
            {"table": "location_master", "level": 3, "name_cols": ["name"]},
            {"table": "cities", "name_cols": ["city_name", "name"]},
        ],
        "data": {"table": "master_table", "cols": ["city"]},
    },
    {
        "field": "area", "label": "Area",
        "masters": [
            {"table": "location_master", "level": 4, "name_cols": ["name"]},
            {"table": "areas", "name_cols": ["area_name", "name"]},
        ],
        "data": {"table": "master_table", "cols": ["area"]},
    },
    {
        "field": "business_category", "label": "Business Category",
        "masters": [
            {"table": "master_categories", "name_cols": ["name"]},
            {"table": "category_master", "name_cols": ["category_name", "name"]},
        ],
        "data": {"table": "master_table", "cols": ["business_category"]},
    },
    {
        "field": "pincode", "label": "Pincode",
        "masters": [
            {"table": "pincode_master", "name_cols": ["pincode", "pin_code", "postal_code"]},
            {"table": "location_postal_codes", "name_cols": ["postal_code", "pincode"]},
        ],
        "data": {"table": "master_table", "cols": ["pincode"], "exclude": ["0"]},
    },
    {
        "field": "product_category", "label": "Product Category",
        "masters": [{"table": "product_category_master", "name_cols": ["category_name", "name"]}],
        "data": {"table": "product_master", "cols": ["category_name", "category"]},
    },
]

VERY_LOW_COVERAGE_PCT = 25  # below this -> "Very low coverage" (matches the sheet's wording)


def _count_remark(master_exists, master, data):
    """Same remark wording as the Dashboard_count sheet, plus a status for colour + icon."""
    if not master_exists:
        return "critical", "Master table does not exist - needs to be created"
    if master == 0 and data > 0:
        return "critical", "Master table is empty but data exists - needs to be populated"
    if master == 0:
        return "critical", "Master table and data are both empty"
    if data > master:
        return "warning", (f"Data has MORE unique values than master ({data - master:,} extra) - "
                           "likely duplicate naming in data, needs cleanup")
    coverage = data * 100.0 / master
    if coverage >= 100:
        return "good", "Full coverage - every master entry has data"
    if coverage >= VERY_LOW_COVERAGE_PCT:
        return "warning", "Partial coverage - some master entries still missing from data"
    return "critical", "Very low coverage - most master entries have no matching data yet"


def _master_where(rc, table, level):
    if level is None:
        return "", {}
    level_col = rc.find_col(table, "location_level", "level")
    if not level_col:
        return None, None
    return f" WHERE {rc.q(level_col)} = :lvl", {"lvl": level}


def build_count_report():
    rows, chart = [], []
    with report_connection(timeout_ms=120000) as rc:
        for f in COUNT_REPORT_FIELDS:
            row = {"field": f["field"], "label": f["label"]}

            # ── master side ──
            primary, alternates = None, []
            for m in f["masters"]:
                table = rc.find_table(m["table"])
                if not table:
                    continue
                where, params = _master_where(rc, table, m.get("level"))
                if where is None:
                    continue
                name_col = rc.find_col(table, *m["name_cols"])
                count = rc.safe(
                    f"{f['field']}: count {table}",
                    lambda t=table, w=where, p=params: rc.scalar(f"SELECT COUNT(*) FROM {rc.q(t)}{w}", p),
                )
                src = table + (f" (level {m['level']})" if m.get("level") else "")
                entry = {"source": src, "table": table, "count": count, "name_col": name_col,
                         "where": where, "params": params}
                if primary is None and count is not None:
                    primary = entry
                else:
                    alternates.append({"source": src, "count": count})

            # ── data side ──
            d = f["data"]
            data_table = rc.find_table(d["table"])
            data_col = rc.find_col(data_table, *d["cols"]) if data_table else None
            data_distinct = records_total = records_with_value = matched = None
            if data_table and data_col:
                qc = rc.q(data_col)
                cond = rc.not_blank(qc, d.get("exclude", ()))
                agg = rc.safe(
                    f"{f['field']}: distinct values in {data_table}.{data_col}",
                    lambda: rc.rows(
                        f"SELECT COUNT(*) AS total_records, "
                        f"SUM(CASE WHEN {cond} THEN 1 ELSE 0 END) AS with_value, "
                        f"COUNT(DISTINCT CASE WHEN {cond} THEN {qc} END) AS distinct_values "
                        f"FROM {rc.q(data_table)}"
                    )[0],
                    {},
                )
                records_total = agg.get("total_records")
                records_with_value = agg.get("with_value")
                data_distinct = agg.get("distinct_values")

                if primary and primary["name_col"]:
                    mq = rc.q(primary["name_col"])
                    mwhere = primary["where"]
                    matched = rc.safe(
                        f"{f['field']}: match data against {primary['source']}",
                        lambda: rc.scalar(
                            f"SELECT COUNT(*) FROM ("
                            f"  SELECT DISTINCT LOWER(TRIM({rc.as_text(qc)})) AS v FROM {rc.q(data_table)} WHERE {cond}"
                            f") x WHERE x.v IN ("
                            f"  SELECT LOWER(TRIM({rc.as_text(mq)})) FROM {rc.q(primary['table'])}{mwhere}"
                            f")",
                            primary["params"],
                        ),
                    )

            master_count = primary["count"] if primary else None
            status, remark = _count_remark(primary is not None, master_count or 0, data_distinct or 0)
            if data_distinct is None:
                status, remark = "critical", "Data column not found - check the data table"

            row.update({
                "master_source": primary["source"] if primary else None,
                "master_count": master_count,
                "other_masters": alternates,
                "data_source": f"{data_table}.{data_col}" if data_table and data_col else None,
                "data_count": data_distinct,
                "records_total": records_total,
                "records_with_value": records_with_value,
                "coverage_pct": pct(data_distinct or 0, master_count) if master_count else None,
                "matched": matched,
                "match_pct": pct(matched or 0, master_count) if (master_count and matched is not None) else None,
                "pending": (max(master_count - matched, 0)
                            if (master_count is not None and matched is not None) else None),
                "status": status,
                "remarks": remark,
            })
            rows.append(row)
            chart.append({
                "name": f["label"],
                "master": master_count or 0,
                "data": data_distinct or 0,
                "matched": matched or 0,
                "pending": row["pending"] or 0,
            })
        errors = rc.errors

    return {"data": {"rows": rows, "chart": chart}, "errors": errors, "generated_at": now_iso()}


@hbd_reports_bp.route("/count-report", methods=["GET"])
def count_report():
    return _respond("count-report", build_count_report)


# ═════════════════════════════════════════════════════════════════════════════
# 2. RANKING  (Ranking_Count sheet + Coverage Report sections 5 & 6)
# ═════════════════════════════════════════════════════════════════════════════

LOCATION_TYPE_ORDER = ["City", "Area", "Building", "Street", "Locality", "State", "Country"]


def _rank_key(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _rank_table(rc, table_name, rank_candidates, label_col_candidates, label):
    """GROUP BY rank for Top_cities_rank / Top_categories_rank + top 10 by business_count."""
    table = rc.find_table(table_name)
    if not table:
        rc.errors.append({"step": label, "error": f"table {table_name} not found"})
        return None
    rank_col = rc.find_col(table, *rank_candidates)
    count_col = rc.find_col(table, "business_count")
    name_col = rc.find_col(table, *label_col_candidates)
    if not rank_col:
        rc.errors.append({"step": label, "error": f"no rank column in {table}"})
        return None
    rq = rc.q(rank_col)
    bc = rc.q(count_col) if count_col else "0"
    by_rank = rc.safe(label, lambda: rc.rows(
        f"SELECT {rq} AS rank_value, COUNT(*) AS items, "
        f"COALESCE(SUM({bc}), 0) AS businesses, "
        f"SUM(CASE WHEN {bc} > 0 THEN 1 ELSE 0 END) AS with_data "
        f"FROM {rc.q(table)} GROUP BY {rq} ORDER BY {rq}"
    ), [])
    top = []
    if count_col and name_col:
        top = rc.safe(f"{label}: top 10", lambda: rc.rows(
            f"SELECT {rc.q(name_col)} AS name, {rq} AS rank_value, {bc} AS businesses "
            f"FROM {rc.q(table)} ORDER BY {bc} DESC LIMIT 10"
        ), [])
    for r in top:
        r["rank"] = _rank_key(r.pop("rank_value"))
    for r in by_rank:
        r["rank"] = _rank_key(r.pop("rank_value"))
        r["with_data_pct"] = pct(r["with_data"] or 0, r["items"])
    return {"table": table, "by_rank": by_rank, "top": top,
            "total_items": sum(int(r["items"] or 0) for r in by_rank)}


def build_ranking():
    with report_connection(timeout_ms=120000) as rc:
        out = {}

        # ── location_master: location_type x city_rank pivot ──
        lm = rc.find_table("location_master")
        type_col = rc.find_col(lm, "location_type") if lm else None
        rank_col = rc.find_col(lm, "city_rank", "rank", "location_rank") if lm else None
        pivot = None
        if lm and type_col and rank_col:
            raw = rc.safe("location_master rank pivot", lambda: rc.rows(
                f"SELECT {rc.q(type_col)} AS location_type, {rc.q(rank_col)} AS rank_value, COUNT(*) AS cnt "
                f"FROM {rc.q(lm)} GROUP BY {rc.q(type_col)}, {rc.q(rank_col)}"
            ), [])
            ranks = sorted({_rank_key(r["rank_value"]) for r in raw if _rank_key(r["rank_value"]) is not None})
            # keep the sheet's Rank 1..5 layout; anything above 5 goes into "6+"
            columns = [f"Rank {i}" for i in range(1, 6)]
            if any(rk > 5 for rk in ranks):
                columns.append("Rank 6+")
            columns.append("Unranked")

            def col_for(rank):
                rk = _rank_key(rank)
                if rk is None:
                    return "Unranked"
                if rk > 5:
                    return "Rank 6+"
                if rk < 1:
                    return "Unranked"
                return f"Rank {rk}"

            by_type, totals = {}, {c: 0 for c in columns}
            for r in raw:
                t = r["location_type"] or "(blank)"
                c = col_for(r["rank_value"])
                n = int(r["cnt"] or 0)
                by_type.setdefault(t, {cc: 0 for cc in columns})
                by_type[t][c] += n
                totals[c] += n
            order = [t for t in LOCATION_TYPE_ORDER if t in by_type] + \
                    sorted(t for t in by_type if t not in LOCATION_TYPE_ORDER)
            grand_total = sum(totals.values())
            pivot = {
                "table": lm,
                "rank_column": rank_col,
                "columns": columns,
                "rows": [dict(location_type=t, total=sum(by_type[t].values()), **by_type[t]) for t in order],
                "totals": totals,
                "total_location_master": grand_total,
                "distribution": [
                    {"name": c, "value": totals[c], "share_pct": pct(totals[c], grand_total)}
                    for c in columns if totals[c] > 0
                ],
            }
        else:
            rc.errors.append({"step": "location_master rank pivot",
                              "error": "location_master, location_type or city_rank column not found"})
        out["location_rank"] = pivot

        out["city_rank"] = _rank_table(rc, "Top_cities_rank", ["city_rank", "rank"],
                                       ["city_name", "name"], "Top_cities_rank by rank")
        out["category_rank"] = _rank_table(rc, "Top_categories_rank", ["category_rank", "rank"],
                                           ["category_name", "name"], "Top_categories_rank by rank")
        errors = rc.errors
    return {"data": out, "errors": errors, "generated_at": now_iso()}


@hbd_reports_bp.route("/ranking", methods=["GET"])
def ranking():
    return _respond("ranking", build_ranking)


# ═════════════════════════════════════════════════════════════════════════════
# 3. FIELD AVAILABILITY  (Coverage Report section 9 - Master Table columns)
# ═════════════════════════════════════════════════════════════════════════════
#
# A value counts as "filled" when it is not NULL / empty / a placeholder
# ('0', 'null', 'none', 'nan', 'n/a', '-'). For flag columns (booleans, is_*,
# isBestSeller, boughtlnLastMonth) 0 is a real value, so only NULL/empty count
# as missing - same rule the coverage report used.

AVAILABLE_PCT = 40
PARTIAL_PCT = 5
PLACEHOLDERS = ("0", "0.0", "0.00", "null", "none", "nan", "n/a", "na", "-")
FLAG_COLUMNS = {"isbestseller", "boughtlnlastmonth", "boughtinlastmonth", "is_moved"}
FLAG_TYPES = {"boolean", "bool", "tinyint", "bit"}


def _is_flag(name, dtype):
    n = name.lower()
    return dtype in FLAG_TYPES or n in FLAG_COLUMNS or n.startswith(("is_", "has_"))


def _classify(p):
    if p is None:
        return "Not Available"
    if p >= AVAILABLE_PCT:
        return "Available"
    if p >= PARTIAL_PCT:
        return "Partially Available"
    return "Not Available"


def build_field_availability(table_param):
    with report_connection(timeout_ms=180000) as rc:
        table = rc.find_table(table_param)
        all_tables = sorted(rc.tables().values(), key=str.lower)
        if not table:
            return {"data": {"table": table_param, "found": False, "tables": all_tables, "columns": []},
                    "errors": [{"step": "find table", "error": f"table {table_param} not found"}],
                    "generated_at": now_iso()}

        cols = rc.columns(table)
        total = rc.safe("total rows", lambda: rc.scalar(f"SELECT COUNT(*) FROM {rc.q(table)}"), 0) or 0
        placeholder_list = ", ".join(f"'{p}'" for p in PLACEHOLDERS)

        results = []
        # chunk columns so a very wide table never produces one enormous statement
        for start in range(0, len(cols), 60):
            chunk = cols[start:start + 60]
            exprs = []
            for i, (name, dtype) in enumerate(chunk):
                qc = rc.q(name)
                txt = f"LOWER(TRIM({rc.as_text(qc)}))"
                if _is_flag(name, dtype):
                    cond = f"{qc} IS NOT NULL AND {txt} <> ''"
                else:
                    cond = f"{qc} IS NOT NULL AND {txt} <> '' AND {txt} NOT IN ({placeholder_list})"
                exprs.append(f"SUM(CASE WHEN {cond} THEN 1 ELSE 0 END) AS c{i}")
            counts = rc.safe(
                f"fill counts (columns {start + 1}-{start + len(chunk)})",
                lambda e=exprs: rc.rows(f"SELECT {', '.join(e)} FROM {rc.q(table)}")[0],
                {},
            )
            for i, (name, dtype) in enumerate(chunk):
                filled = counts.get(f"c{i}")
                filled = int(filled) if filled is not None else None
                p = pct(filled, total) if (filled is not None and total) else (0.0 if total == 0 else None)
                results.append({
                    "column": name,
                    "data_type": dtype,
                    "is_flag": _is_flag(name, dtype),
                    "filled": filled,
                    "total": total,
                    "pct": p,
                    "classification": _classify(p) if filled is not None else "Unknown (query failed)",
                })

        summary = {}
        for r in results:
            summary[r["classification"]] = summary.get(r["classification"], 0) + 1
        errors = rc.errors

    return {
        "data": {
            "table": table, "found": True, "tables": all_tables, "total_rows": total,
            "columns": results,
            "summary": [{"name": k, "value": v, "share_pct": pct(v, len(results))} for k, v in summary.items()],
            "thresholds": {"available_pct": AVAILABLE_PCT, "partial_pct": PARTIAL_PCT},
        },
        "errors": errors,
        "generated_at": now_iso(),
    }


@hbd_reports_bp.route("/field-availability", methods=["GET"])
def field_availability():
    table = (request.args.get("table") or "master_table").strip()
    if not re.fullmatch(r"[A-Za-z0-9_]+", table):
        return jsonify({"status": "error", "message": "invalid table name"}), 400
    return _respond(f"field-availability:{table.lower()}", lambda: build_field_availability(table), ttl=600)


# ═════════════════════════════════════════════════════════════════════════════
# 4. HIERARCHY  (Coverage Report section 7 - parent-child mapping)
# ═════════════════════════════════════════════════════════════════════════════

HIERARCHY_CHECKS = [
    {
        "key": "location_master", "label": "Location Master", "table": "location_master",
        "level_cols": ["location_level"], "parent_cols": ["parent_id"], "name_cols": ["name"],
        "expected_max_level": 4,
        "level_names": {1: "Country", 2: "State", 3: "City", 4: "Area",
                        5: "Locality", 6: "Street", 7: "Building"},
    },
    {
        "key": "master_categories", "label": "Master Categories", "table": "master_categories",
        "level_cols": ["level", "category_level"], "parent_cols": ["parent_id"], "name_cols": ["name"],
    },
    {
        "key": "product_category_master", "label": "Product Category Master",
        "table": "product_category_master",
        "level_cols": ["category_level", "level"], "parent_cols": ["parent_id"],
        "name_cols": ["category_name", "name"],
    },
    {
        "key": "page_product_categories", "label": "Page Product Categories (Data Enrichment)",
        "table": "page_product_categories",
        "level_cols": ["category_level", "level"], "parent_cols": ["parent_id"],
        "name_cols": ["name", "category_name"],
    },
]


def build_hierarchy():
    checks = []
    with report_connection(timeout_ms=120000) as rc:
        for chk in HIERARCHY_CHECKS:
            table = rc.find_table(chk["table"])
            result = {"key": chk["key"], "label": chk["label"], "table": table, "found": bool(table)}
            if not table:
                result["issues"] = [f"Table {chk['table']} not found in this database"]
                checks.append(result)
                continue
            level_col = rc.find_col(table, *chk["level_cols"])
            parent_col = rc.find_col(table, *chk["parent_cols"])
            name_col = rc.find_col(table, *chk["name_cols"])
            id_col = rc.find_col(table, "id")
            if not (level_col and parent_col):
                result["issues"] = [f"{table} has no level / parent_id column"]
                checks.append(result)
                continue
            lq, pq, t = rc.q(level_col), rc.q(parent_col), rc.q(table)

            levels = rc.safe(f"{table}: levels", lambda: rc.rows(
                f"SELECT {lq} AS lvl, COUNT(*) AS total, COUNT({pq}) AS has_parent "
                f"FROM {t} GROUP BY {lq} ORDER BY {lq}"
            ), [])
            level_names = chk.get("level_names", {})
            for r in levels:
                r["level"] = _rank_key(r.pop("lvl"))
                r["total"] = int(r["total"] or 0)
                r["has_parent"] = int(r["has_parent"] or 0)
                r["missing_parent"] = r["total"] - r["has_parent"]
                r["level_name"] = level_names.get(r["level"], f"Level {r['level']}")

            known = [r["level"] for r in levels if r["level"] is not None]
            root_level = min(known) if known else None
            non_root_missing = sum(r["missing_parent"] for r in levels
                                   if r["level"] is not None and r["level"] != root_level)

            orphans = None
            if id_col:
                iq = rc.q(id_col)
                orphans = rc.safe(f"{table}: orphan parent links", lambda: rc.scalar(
                    f"SELECT COUNT(*) FROM {t} c LEFT JOIN {t} p "
                    f"ON {rc.as_text('p.' + iq)} = {rc.as_text('c.' + pq)} "
                    f"WHERE c.{pq} IS NOT NULL AND p.{iq} IS NULL"
                ))

            issues = []
            beyond = None
            if chk.get("expected_max_level"):
                mx = chk["expected_max_level"]
                beyond_total = sum(r["total"] for r in levels if r["level"] is not None and r["level"] > mx)
                garbage = samples = None
                if beyond_total and name_col:
                    nq = rc.q(name_col)
                    garbage = rc.safe(f"{table}: numeric-only names", lambda: rc.scalar(
                        f"SELECT COUNT(*) FROM {t} WHERE {lq} > :mx AND {rc.no_letters(nq)}", {"mx": mx}
                    ))
                    samples = rc.safe(f"{table}: sample names", lambda: [r["name"] for r in rc.rows(
                        f"SELECT {nq} AS name FROM {t} WHERE {lq} > :mx AND {rc.no_letters(nq)} LIMIT 8", {"mx": mx}
                    )], [])
                beyond = {"expected_max_level": mx, "rows": beyond_total,
                          "numeric_only_names": garbage, "samples": samples or []}
                if beyond_total:
                    issues.append(f"{beyond_total:,} rows sit deeper than level {mx} "
                                  f"({level_names.get(mx, mx)}); "
                                  f"{(garbage or 0):,} of them have names with no letters at all "
                                  f"(phone numbers / shop numbers).")
            if non_root_missing:
                issues.append(f"{non_root_missing:,} row{'s' if non_root_missing != 1 else ''} below the top level "
                              f"{'have' if non_root_missing != 1 else 'has'} no parent_id.")
            if orphans:
                issues.append(f"{orphans:,} row{'s' if orphans != 1 else ''} point{'' if orphans != 1 else 's'} "
                              f"to a parent_id that does not exist.")

            result.update({
                "level_column": level_col, "parent_column": parent_col, "root_level": root_level,
                "levels": levels, "total": sum(r["total"] for r in levels),
                "non_root_missing_parent": non_root_missing, "orphans": orphans,
                "beyond_expected": beyond, "issues": issues,
                "status": "good" if not issues else ("warning" if len(issues) == 1 else "critical"),
            })
            checks.append(result)
        errors = rc.errors
    return {"data": {"checks": checks}, "errors": errors, "generated_at": now_iso()}


@hbd_reports_bp.route("/hierarchy", methods=["GET"])
def hierarchy():
    return _respond("hierarchy", build_hierarchy)


# ═════════════════════════════════════════════════════════════════════════════
# 5. DATABASE TABLES  ("dashboard db new" sheet + Coverage Report section 11)
# ═════════════════════════════════════════════════════════════════════════════
#
# Group / subgroup comes from the team's "dashboard db new" sheet. Tables that
# are not in the sheet (new ones) are classified by keywords in their name,
# with a fixed priority order (so uncleaned_product_master_table lands in
# cleaning-in-progress, not e-commerce).

TABLE_GROUPS = {
    # app/user
    "activities": ("app/user", ""), "addons": ("app/user", ""), "album_images": ("app/user", ""),
    "albums": ("app/user", ""), "users": ("app/user", ""),
    # backup
    "bk_0730": ("backup", ""), "master_table_backup_20260822_143353": ("backup", ""),
    "product_master_backup_20260822_143353": ("backup", ""),
    # category
    "category_mapping_history": ("category", ""), "category_mapping_platforms": ("category", ""),
    "category_mapping_synonyms": ("category", ""), "category_master": ("category", ""),
    "master_categories": ("category", ""), "master_category_summary": ("category", ""),
    "pagecategories": ("category", ""), "platform_category_mapping": ("category", ""),
    "product_category_master": ("category", ""), "target_cities_categories": ("category", ""),
    # cleaning-in-progress
    "tier1_master_clean": ("cleaning-in-progress", ""), "tier2_missing_contact": ("cleaning-in-progress", ""),
    "tier3_missing_location": ("cleaning-in-progress", ""), "tier4_partial_fragments": ("cleaning-in-progress", ""),
    "tier5_linked_duplicates": ("cleaning-in-progress", ""),
    "uncleaned_listing_master_table": ("cleaning-in-progress", ""),
    "uncleaned_product_master_table": ("cleaning-in-progress", ""),
    # core master
    "master_table": ("core master", ""),
    # ecommerce
    "amazon_products": ("ecommerce", "amazon"), "bigbasket": ("ecommerce", "bigbasket"),
    "bigbasket_dbmapping": ("ecommerce", "bigbasket"), "blinkit": ("ecommerce", "blinkit"),
    "blinkit_mapping": ("ecommerce", "blinkit"), "dmart_categories": ("ecommerce", "dmart"),
    "dmart_products": ("ecommerce", "dmart"), "flipkart_db_mapping": ("ecommerce", "flipkart"),
    "flipkart_products_new": ("ecommerce", "flipkart"), "indiamart_mappings": ("ecommerce", "indiamart"),
    "indiamart_products": ("ecommerce", "indiamart"), "item_data": ("ecommerce", ""),
    "jio_mart_products": ("ecommerce", "jiomart"), "jiomart_categories": ("ecommerce", "jiomart"),
    "jiomart_products": ("ecommerce", "jiomart"), "product_master": ("ecommerce", ""),
    "product_master_table": ("ecommerce", ""), "vivo": ("ecommerce", ""),
    "zepto": ("ecommerce", "zepto"), "zepto_db_mapping": ("ecommerce", "zepto"),
    # listing/directory
    "asklaila": ("listing/directory", "asklaila"), "businesses": ("listing/directory", ""),
    "college_dunia": ("listing/directory", "education"), "freelisting": ("listing/directory", "freelisting"),
    "g_map_master_table": ("listing/directory", "google maps"), "google_map": ("listing/directory", "google maps"),
    "google_map_scrape": ("listing/directory", "google maps"), "justdial": ("listing/directory", "justdial"),
    "listing_master_table": ("listing/directory", ""), "listmaster": ("listing/directory", ""),
    "magicpin": ("listing/directory", "magicpin"), "nearbuy": ("listing/directory", "nearbuy"),
    "pinda": ("listing/directory", "pinda"), "raw_clean_google_map_data": ("listing/directory", "google maps"),
    "raw_google_map": ("listing/directory", "google maps"),
    "raw_google_map_drive_data": ("listing/directory", "google maps"),
    "schoolgis": ("listing/directory", "education"), "shiksha": ("listing/directory", "education"),
    "temp_google_map_scrape": ("listing/directory", "google maps"),
    "validation_raw_google_map": ("listing/directory", "google maps"),
    "yellow_pages": ("listing/directory", "yellow pages"),
    # location
    "location_master_india": ("location", ""), "state_master": ("location", ""), "areas": ("location", ""),
    "cities": ("location", ""), "countries": ("location", ""), "location_aliases": ("location", ""),
    "location_master": ("location", ""), "location_postal_codes": ("location", ""),
    "top_1000_indian_cities": ("location", ""),
    # ranking
    "top_categories_rank": ("ranking", ""), "top_cities_rank": ("ranking", ""),
    # reference data
    "atm": ("reference data", ""), "bank_data": ("reference data", ""), "post_office": ("reference data", ""),
    # system/etl
    "clean_milestones": ("system/etl", ""), "dashboard_summary": ("system/etl", ""),
    "data_cleaning_log": ("system/etl", ""), "data_validation_log": ("system/etl", ""),
    "drive_folder_registry": ("system/etl", ""), "duplicate_records_review": ("system/etl", ""),
    "etl_dlq": ("system/etl", ""), "etl_metadata": ("system/etl", ""), "file_registry": ("system/etl", ""),
    "master_city_summary": ("system/etl", ""), "master_state_summary": ("system/etl", ""),
    "menu_aggregates": ("system/etl", ""), "product_dashboard_report_summary": ("system/etl", ""),
    "product_top_selling_report": ("system/etl", ""), "scraper_tasks": ("system/etl", ""),
    "unmatched_data_review": ("system/etl", ""), "upload_reports": ("system/etl", ""),
    # product enrichment (the six tables populated for the new website)
    "product_catalogue": ("product enrichment", "cityhangaround"),
    "page_product_categories": ("product enrichment", "cityhangaround"),
    "affiliate_products": ("product enrichment", "cityhangaround"),
    "page_products": ("product enrichment", "cityhangaround"),
    "product_attributes_master": ("product enrichment", "cityhangaround"),
    "product_attributes": ("product enrichment", "cityhangaround"),
}

PLATFORM_WORDS = ["amazon", "flipkart", "zepto", "blinkit", "bigbasket", "dmart", "jiomart", "jio_mart",
                  "indiamart", "justdial", "asklaila", "magicpin", "nearbuy", "pinda", "heyplaces",
                  "yellow_pages", "google_map", "shiksha", "schoolgis", "college_dunia", "freelisting"]

# (group, keywords) - checked in this order, first hit wins
KEYWORD_RULES = [
    ("backup", ["backup", "bk_", "_bak", "_old"]),
    ("cleaning-in-progress", ["tier1", "tier2", "tier3", "tier4", "tier5", "uncleaned", "staging", "temp_"]),
    ("ranking", ["rank"]),
    ("system/etl", ["_log", "log_", "etl", "registry", "summary", "report", "task", "milestone",
                    "review", "aggregate", "metadata", "dlq", "migration", "celery", "alembic"]),
    ("product enrichment", ["page_product", "product_attribute", "product_catalogue", "affiliate"]),
    ("category", ["categor", "mapping", "synonym", "taxonomy"]),
    ("location", ["location", "cities", "city", "areas", "state", "countr", "pincode", "postal"]),
    ("ecommerce", ["amazon", "flipkart", "zepto", "blinkit", "bigbasket", "dmart", "jiomart", "jio_mart",
                   "indiamart", "product", "vivo", "item"]),
    ("listing/directory", ["google", "justdial", "asklaila", "magicpin", "nearbuy", "pinda", "shiksha",
                           "schoolgis", "college", "yellow", "freelisting", "heyplaces", "listing", "business"]),
    ("reference data", ["atm", "bank", "post_office", "ifsc"]),
    ("core master", ["master_table"]),
    ("app/user", ["user", "album", "activit", "addon", "page", "auth", "session"]),
]

EXACT_COUNT_LIMIT = 1_000_000  # tables estimated below this get an exact COUNT(*)


def classify_table(name):
    n = name.lower()
    if n in TABLE_GROUPS:
        return TABLE_GROUPS[n] + ("sheet",)
    subgroup = next((p.replace("_", " ") for p in PLATFORM_WORDS if p in n), "")
    for group, words in KEYWORD_RULES:
        if any(w in n for w in words):
            return group, subgroup, "keyword"
    return "other", subgroup, "keyword"


def build_db_tables(exact=False):
    with report_connection(timeout_ms=60000) as rc:
        cols_by_table = rc.safe("list columns", rc.all_columns, {}) or {}
        estimates = rc.safe("row estimates", rc.estimated_counts, {}) or {}
        rc.set_timeout(60000 if exact else 20000)

        tables = []
        for name in sorted(rc.tables().values(), key=str.lower):
            est = estimates.get(name)
            count, count_type = None, "estimate"
            if exact or est is None or est < EXACT_COUNT_LIMIT:
                count = rc.safe(f"count {name}",
                                lambda n=name: rc.scalar(f"SELECT COUNT(*) FROM {rc.q(n)}"))
                if count is not None:
                    count_type = "exact"
            if count is None:
                count = est
            cols = [c for c, _ in cols_by_table.get(name, [])]
            group, subgroup, how = classify_table(name)
            if count == 0:
                remark = "Table is currently empty"
            elif count_type == "estimate":
                remark = "Approximate row count (from database statistics)"
            else:
                remark = ""
            tables.append({
                "group": group, "subgroup": subgroup, "table": name, "classified_by": how,
                "columns_count": len(cols), "columns": cols,
                "detail": f"{len(cols)} columns: " + ", ".join(cols[:8]) + (", ..." if len(cols) > 8 else ""),
                "rows": count, "count_type": count_type, "remarks": remark,
            })
        errors = rc.errors

    tables.sort(key=lambda t: (t["group"], t["subgroup"], t["table"].lower()))
    groups = {}
    for t in tables:
        g = groups.setdefault(t["group"], {"group": t["group"], "tables": 0, "rows": 0, "empty_tables": 0})
        g["tables"] += 1
        g["rows"] += int(t["rows"] or 0)
        g["empty_tables"] += 1 if t["rows"] == 0 else 0
    group_list = sorted(groups.values(), key=lambda g: g["rows"], reverse=True)
    return {
        "data": {
            "tables": tables,
            "groups": group_list,
            "totals": {
                "tables": len(tables),
                "rows": sum(int(t["rows"] or 0) for t in tables),
                "empty_tables": sum(1 for t in tables if t["rows"] == 0),
                "approximate_counts": sum(1 for t in tables if t["count_type"] == "estimate"),
            },
        },
        "errors": errors,
        "generated_at": now_iso(),
    }


@hbd_reports_bp.route("/db-tables", methods=["GET"])
def db_tables():
    exact = request.args.get("exact", "false").lower() in ("1", "true", "yes")
    return _respond(f"db-tables:{exact}", lambda: build_db_tables(exact), ttl=600)


# ═════════════════════════════════════════════════════════════════════════════
# 6. HBD REPORT  (HBD_Dashboard_Documentation.docx)
# ═════════════════════════════════════════════════════════════════════════════
#
# Targets below are copied from Section 4 of the HBD documentation - they are
# goals the team set, not database values. The "achieved" column next to them
# is live: distinct values in the scraped data that match the master list.

HBD_TARGETS = [
    {"key": "country", "label": "Country", "total_target": 1, "rank1_target": 1},
    {"key": "state", "label": "State", "total_target": 30, "rank1_target": 13},
    {"key": "city", "label": "City", "total_target": 15000, "rank1_target": 1500},
    {"key": "area", "label": "Area", "total_target": 300000, "rank1_target": 3800},
    {"key": "business_category", "label": "Business Category", "total_target": 25000, "rank1_target": 2000},
    {"key": "product_category", "label": "Product Category", "total_target": 34344, "rank1_target": 200},
    {"key": "product_name", "label": "Product Name", "total_target": 355655, "rank1_target": 4554},
]

TIER_TABLES = [
    ("tier1_master_clean", "Tier 1 - Verified / clean"),
    ("tier2_missing_contact", "Tier 2 - Missing contact"),
    ("tier3_missing_location", "Tier 3 - Missing location"),
    ("tier4_partial_fragments", "Tier 4 - Partial fragments"),
    ("tier5_linked_duplicates", "Tier 5 - Linked duplicates"),
]


def build_hbd():
    inventory, _ = cached("db-tables:False", lambda: build_db_tables(False), ttl=600)
    counts, _ = cached("count-report", build_count_report)
    by_table = {t["table"].lower(): t for t in inventory["data"]["tables"]}
    by_field = {r["field"]: r for r in counts["data"]["rows"]}

    def rows_of(name):
        t = by_table.get(name.lower())
        return int(t["rows"]) if t and t["rows"] is not None else None

    def group_sum(*groups):
        ts = [t for t in inventory["data"]["tables"] if t["group"] in groups]
        return sum(int(t["rows"] or 0) for t in ts), len(ts)

    errors = list(inventory.get("errors", [])) + list(counts.get("errors", []))

    # live "achieved" for Product Name = distinct product names in product_master
    product_names = None
    with report_connection(timeout_ms=120000) as rc:
        pm = rc.find_table("product_master")
        pn = rc.find_col(pm, "product_name") if pm else None
        if pm and pn:
            product_names = rc.safe("distinct product names", lambda: rc.scalar(
                f"SELECT COUNT(DISTINCT {rc.q(pn)}) FROM {rc.q(pm)} WHERE {rc.not_blank(rc.q(pn))}"))
        errors += rc.errors

    targets = []
    for t in HBD_TARGETS:
        if t["key"] == "product_name":
            achieved, source = product_names, "distinct product_name in product_master"
        else:
            r = by_field.get(t["key"], {})
            achieved = r.get("matched")
            source = f"{r.get('data_source')} matched to {r.get('master_source')}" if r else None
        targets.append(dict(t,
                            achieved=achieved,
                            achieved_source=source,
                            pending=(max(t["total_target"] - achieved, 0) if achieved is not None else None),
                            progress_pct=(min(pct(achieved, t["total_target"]), 100.0)
                                          if achieved is not None else None)))

    scraped_rows, scraped_tables = group_sum("ecommerce", "listing/directory", "reference data")
    tiers = [{"table": tbl, "name": label, "value": rows_of(tbl)} for tbl, label in TIER_TABLES]
    tier_total = sum(t["value"] or 0 for t in tiers)
    for t in tiers:
        t["share_pct"] = pct(t["value"] or 0, tier_total)

    stages = [
        {"key": "scrap", "title": "1. Scrap (Collect)",
         "text": "Scrapers pull raw data from Google Maps, directories, government lists and e-commerce sites.",
         "metrics": [
             {"label": "Raw rows across source tables", "value": scraped_rows,
              "source": "all tables in groups ecommerce + listing/directory + reference data"},
             {"label": "Source tables", "value": scraped_tables, "source": "same groups"},
         ]},
        {"key": "clean", "title": "2. Clean",
         "text": "Formatting fixed, junk removed, phones/addresses standardised; records sorted into tiers.",
         "metrics": [
             {"label": "Rows in cleaning tiers 1-5", "value": tier_total, "source": "tier1..tier5 tables"},
             {"label": "Uncleaned listing rows", "value": rows_of("uncleaned_listing_master_table"),
              "source": "uncleaned_listing_master_table"},
         ]},
        {"key": "merge", "title": "3. Merge",
         "text": "Records from different sources that are the same real business/product are combined.",
         "metrics": [
             {"label": "Linked duplicates found", "value": rows_of("tier5_linked_duplicates"),
              "source": "tier5_linked_duplicates"},
             {"label": "Product master rows", "value": rows_of("product_master"), "source": "product_master"},
         ]},
        {"key": "match", "title": "4. Match (against Master Data)",
         "text": "Each record is checked against the master lists; unmatched ones are held for review.",
         "metrics": [
             {"label": "Verified / clean (Tier 1)", "value": rows_of("tier1_master_clean"),
              "source": "tier1_master_clean"},
             {"label": "Missing location (Tier 3)", "value": rows_of("tier3_missing_location"),
              "source": "tier3_missing_location"},
             {"label": "Held for review", "value": rows_of("unmatched_data_review"),
              "source": "unmatched_data_review"},
         ]},
        {"key": "ready", "title": "5. Ready to Use",
         "text": "Matched, clean records form the Listing Master; affiliate products are a separate stream.",
         "metrics": [
             {"label": "Listing master records", "value": rows_of("master_table"), "source": "master_table"},
             {"label": "Product catalogue (affiliate stream)", "value": rows_of("product_catalogue"),
              "source": "product_catalogue"},
         ]},
    ]

    return {
        "data": {"stages": stages, "tiers": tiers, "tier_total": tier_total, "targets": targets},
        "errors": errors,
        "generated_at": now_iso(),
    }


@hbd_reports_bp.route("/hbd", methods=["GET"])
def hbd():
    if _refresh_requested():
        # the HBD page re-uses the inventory + count caches, so refresh those too
        cached("db-tables:False", lambda: build_db_tables(False), refresh=True, ttl=600)
        cached("count-report", build_count_report, refresh=True)
    return _respond("hbd", build_hbd)


# ═════════════════════════════════════════════════════════════════════════════
# 7. HEALTH - which database are the reports reading?
# ═════════════════════════════════════════════════════════════════════════════

@hbd_reports_bp.route("/health", methods=["GET"])
def health():
    try:
        with report_connection(timeout_ms=15000) as rc:
            if rc.is_pg:
                info = rc.rows("SELECT current_database() AS db, current_schema() AS schema, version() AS version")[0]
            else:
                info = rc.rows("SELECT DATABASE() AS db, DATABASE() AS schema, VERSION() AS version")[0]
            info.update({"dialect": rc.dialect, "tables": len(rc.tables()), "config_source": engine_source()})
        return jsonify(to_json_safe({"status": "success", "data": info, "generated_at": now_iso()})), 200
    except Exception as e:  # noqa: BLE001
        msg = str(getattr(e, "orig", e)).strip().splitlines()[0][:500]
        return jsonify({"status": "error", "message": msg}), 500
