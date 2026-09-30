"""
Data Enrichment documentation reports - the team's sheet + reports 01-04,
each shown next to LIVE numbers from the database.

Builders only (no routes here); data_enrichment_routes.py exposes them:
    GET /api/data-enrichment/raw-sources        the "Data enrichment tables" sheet, live
    GET /api/data-enrichment/process            01 Final Data Enrichment Master Report, step by step
    GET /api/data-enrichment/url-extraction     02 URL Extraction system - url_extraction_master, live
    GET /api/data-enrichment/location-matching  03 + 04 location reports, re-checked live

Numbers written in the documents are always labelled as "from the report";
live numbers come from the database at request time. Nothing is written.
"""

from sqlalchemy import bindparam, text

from routes.hbd_reports_routes import (
    COMPLETE_FILL_PCT,
    EXACT_COUNT_LIMIT,
    SAMPLE_ROWS,
    TABLE_GROUPS,
    _filled_cond,
    _load_team_statuses,
    _rank_key,
    _sample_fill,
    build_count_report,
    build_db_tables,
    build_hierarchy,
    build_ranking,
)
from utils import enrichment_register as REG
from utils.reports_db import cached, engine_source, now_iso, pct, report_connection

GEO_COLS = {"lat", "latitude", "lng", "lon", "long", "longitude", "x", "y", "geom", "geometry",
            "coordinates", "latlong", "lat_long", "lat_lng", "location_lat", "location_lng"}


# ─── helpers: find tables in ANY schema ─────────────────────────────────────

class Catalog:
    """Every base table in every user schema: lower name -> (schema, real name, quoted relation)."""

    def __init__(self, rc):
        self.rc = rc
        if rc.is_pg:
            rows = rc.rows(
                "SELECT table_schema AS s, table_name AS t FROM information_schema.tables "
                "WHERE table_type = 'BASE TABLE' AND table_schema NOT IN ('pg_catalog', 'information_schema') "
                "AND LEFT(table_schema, 3) <> 'pg_'"
            )
            current = rc.scalar("SELECT current_schema()")
        else:
            rows = rc.rows("SELECT table_schema AS s, table_name AS t FROM information_schema.tables "
                           "WHERE table_type = 'BASE TABLE' AND table_schema = DATABASE()")
            current = rc.scalar("SELECT DATABASE()")
        self.current = current
        self.by_name = {}
        for r in rows:
            key = r["t"].lower()
            prev = self.by_name.get(key)
            if prev is None or (r["s"] == current and prev[0] != current):
                self.by_name[key] = (r["s"], r["t"])

    def find(self, *names):
        for n in names:
            hit = self.by_name.get((n or "").lower())
            if hit:
                schema, name = hit
                return {"schema": schema, "table": name, "rel": f"{self.rc.q(schema)}.{self.rc.q(name)}",
                        "label": name if schema == self.current else f"{schema}.{name}"}
        return None

    def columns(self, found_list):
        """[(schema, table)] -> {(schema, table): [(col, dtype)]} in one query."""
        if not found_list:
            return {}
        names = sorted({t for _, t in found_list})
        q = text("SELECT table_schema AS s, table_name AS t, column_name AS c, data_type AS d "
                 "FROM information_schema.columns WHERE table_name IN :names "
                 "ORDER BY table_schema, table_name, ordinal_position").bindparams(bindparam("names", expanding=True))
        out = {}
        wanted = set(found_list)
        for r in self.rc.conn.execute(q, {"names": names}).mappings():
            key = (r["s"], r["t"])
            if key in wanted:
                out.setdefault(key, []).append((r["c"], (r["d"] or "").lower()))
        return out

    def estimates(self):
        rc = self.rc
        if rc.is_pg:
            rows = rc.rows(
                "SELECT n.nspname AS s, c.relname AS t, GREATEST(c.reltuples, 0)::bigint AS est, "
                "st.n_live_tup AS live FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
                "LEFT JOIN pg_stat_user_tables st ON st.relid = c.oid WHERE c.relkind IN ('r', 'p')"
            )
            return {(r["s"], r["t"]): int(max(r["est"] or 0, r["live"] or 0)) for r in rows}
        rows = rc.rows("SELECT table_schema AS s, table_name AS t, table_rows AS est "
                       "FROM information_schema.tables WHERE table_schema = DATABASE()")
        return {(r["s"], r["t"]): int(r["est"] or 0) for r in rows}


def _count(rc, found, est, exact):
    if exact or est is None or est < EXACT_COUNT_LIMIT:
        n = rc.safe(f"count {found['label']}", lambda: rc.scalar(f"SELECT COUNT(*) FROM {found['rel']}"))
        if n is not None:
            return int(n), "exact"
    return est, "estimate"


def _geo(cols):
    names = {c.lower() for c, _ in cols}
    has_xy = "x" in names and "y" in names
    return [c for c, _ in cols
            if (c.lower() in GEO_COLS and (c.lower() not in ("x", "y") or has_xy))
            or "latitude" in c.lower() or "longitude" in c.lower()]


def _col(cols, *names):
    low = {c.lower(): c for c, _ in cols}
    for n in names:
        if n.lower() in low:
            return low[n.lower()]
    return None


def _filled_pct_query(rc, rel, cols):
    """Fill % of each column on the FULL table (one scan)."""
    if not cols:
        return {}, 0
    exprs = [f"SUM(CASE WHEN {_filled_cond(rc, c, dt)} THEN 1 ELSE 0 END) AS c{i}" for i, (c, dt) in enumerate(cols)]
    row = rc.rows(f"SELECT COUNT(*) AS n, {', '.join(exprs)} FROM {rel}")[0]
    n = int(row.get("n") or 0)
    return {c: (int(row.get(f"c{i}") or 0)) for i, (c, _) in enumerate(cols)}, n


def _top(rc, rel, col, limit=15):
    qc = rc.q(col)
    return rc.rows(
        f"SELECT TRIM({rc.as_text(qc)}) AS name, COUNT(*) AS value FROM {rel} "
        f"WHERE {rc.not_blank(qc)} GROUP BY TRIM({rc.as_text(qc)}) ORDER BY COUNT(*) DESC LIMIT {int(limit)}"
    )


# ═════════════════════════════════════════════════════════════════════════════
# Raw data sources (the "Data enrichment tables" sheet)
# ═════════════════════════════════════════════════════════════════════════════

def build_raw_sources(exact=False):
    with report_connection(timeout_ms=120000) as main:
        team = main.safe("team statuses", lambda: _load_team_statuses(main), {}) or {}

    with report_connection(timeout_ms=120000, db="enrichment") as rc:
        cat = rc.safe("list tables in all schemas", lambda: Catalog(rc))
        if cat is None:
            return {"data": {"sources": []}, "errors": rc.errors, "generated_at": now_iso()}
        estimates = rc.safe("row estimates", cat.estimates, {}) or {}

        entries = []
        for s in REG.ALL_SOURCES:
            entries.append((s, cat.find(*s["candidates"])))
        # tables that look raw (raw_ / osm_ prefix) but are not in the sheet
        documented = {c.lower() for s in REG.ALL_SOURCES for c in s["candidates"]}
        for key, (schema, name) in sorted(cat.by_name.items()):
            if key.startswith(("raw_", "osm_")) and key not in documented and key not in TABLE_GROUPS:
                extra = {"group": "raw", "subgroup": "(not in sheet)", "table": name, "candidates": [name],
                         "detail": "", "sheet_count_text": "", "sheet_count": None, "done_by": "",
                         "sheet_remarks": "", "sheet_notes": ["In the database but not listed in the sheet"]}
                entries.append((extra, cat.find(name)))

        found_keys = [(f["schema"], f["table"]) for _, f in entries if f]
        cols_by = rc.safe("columns", lambda: cat.columns(found_keys), {}) or {}

        rows = []
        for s, f in entries:
            row = {
                "group": s["group"], "subgroup": s["subgroup"], "table": s["table"], "detail": s["detail"],
                "sheet_count": s["sheet_count"], "sheet_count_text": s["sheet_count_text"],
                "done_by": s["done_by"], "sheet_remarks": s["sheet_remarks"], "notes": list(s["sheet_notes"]),
                "in_db": bool(f), "db_table": f["label"] if f else None,
                "rows": None, "count_type": None, "columns_count": None, "columns": [],
                "fill_pct": None, "empty_columns": None, "geo_columns": [],
            }
            if f:
                cols = cols_by.get((f["schema"], f["table"]), [])
                count, ctype = _count(rc, f, estimates.get((f["schema"], f["table"])), exact)
                row.update({"rows": count, "count_type": ctype, "columns_count": len(cols),
                            "columns": [c for c, _ in cols], "geo_columns": _geo(cols)})
                if count:
                    fp, ec = rc.safe(f"fill sample {f['label']}",
                                     lambda: _sample_fill(rc, f["table"], cols, rel=f["rel"]), (None, None))
                    row["fill_pct"], row["empty_columns"] = fp, ec
                if s["sheet_count"] is not None and count is not None:
                    diff = count - s["sheet_count"]
                    row["diff"] = diff
                    tolerance = 0 if ctype == "exact" else max(int(s["sheet_count"] * 0.02), 1)
                    row["matches_sheet"] = abs(diff) <= tolerance
                    if not row["matches_sheet"]:
                        row["notes"].append(f"Live rows differ from the sheet by {diff:+,}")
            # auto status (same rule as Database Tables) + team override
            if not f:
                auto = "Not in database"
            elif not row["rows"]:
                auto = "Empty"
            elif row["fill_pct"] is None:
                auto = "Unknown"
            else:
                auto = "Complete" if row["fill_pct"] >= COMPLETE_FILL_PCT else "Partial"
            ts = team.get((f["table"] if f else s["table"]).lower(), {})
            row["auto_status"] = auto
            row["team_status"] = ts.get("team_status") or None
            row["status"] = row["team_status"] or auto
            row["team_done_by"] = ts.get("done_by") or ""
            row["team_remarks"] = ts.get("remarks") or ""
            rows.append(row)
        errors = rc.errors

    in_db = [r for r in rows if r["in_db"]]
    people = {}
    for r in rows:
        who = r["team_done_by"] or r["done_by"] or "(not set)"
        p = people.setdefault(who, {"name": who, "tables": 0, "in_db": 0, "rows": 0})
        p["tables"] += 1
        p["in_db"] += 1 if r["in_db"] else 0
        p["rows"] += int(r["rows"] or 0)
    groups = {}
    for r in rows:
        g = groups.setdefault(r["group"], {"group": r["group"], "tables": 0, "in_db": 0, "rows": 0})
        g["tables"] += 1
        g["in_db"] += 1 if r["in_db"] else 0
        g["rows"] += int(r["rows"] or 0)
    for g in REG.EMPTY_GROUPS:
        groups.setdefault(g, {"group": g, "tables": 0, "in_db": 0, "rows": 0, "note": "No tables yet (listed in the sheet)"})

    order = ["Complete", "Partial", "In progress", "Not started", "Empty", "Unknown", "Not in database"]
    return {
        "data": {
            "sources": rows,
            "totals": {
                "in_sheet": sum(1 for r in rows if r["subgroup"] != "(not in sheet)"),
                "in_db": len(in_db),
                "missing": sum(1 for r in rows if not r["in_db"]),
                "not_in_sheet": sum(1 for r in rows if r["subgroup"] == "(not in sheet)"),
                "rows": sum(int(r["rows"] or 0) for r in in_db),
                "sheet_rows": sum(int(r["sheet_count"] or 0) for r in rows),
                "with_geo": sum(1 for r in in_db if r["geo_columns"]),
                "differs": sum(1 for r in rows if r.get("matches_sheet") is False),
            },
            "people": sorted(people.values(), key=lambda p: -p["rows"]),
            "groups": list(groups.values()),
            "status_summary": [{"name": st, "value": sum(1 for r in rows if r["status"] == st)}
                               for st in order if any(r["status"] == st for r in rows)],
            "complete_fill_pct": COMPLETE_FILL_PCT, "sample_rows": SAMPLE_ROWS,
            "database": engine_source("enrichment"),
        },
        "errors": errors, "generated_at": now_iso(),
    }


# ═════════════════════════════════════════════════════════════════════════════
# 02  URL extraction  (url_extraction_master)
# ═════════════════════════════════════════════════════════════════════════════

def build_url_extraction():
    doc = {
        "title": REG.URL_DOC_TITLE, "date": REG.URL_DOC_DATE, "table": REG.URL_TABLE,
        "fields": [{"key": k, "label": l, "rule": r} for k, l, r in REG.URL_OUTPUT_FIELDS],
        "category_vocab": [{"category": c, "terms": t} for c, t in REG.URL_CATEGORY_VOCAB],
        "limits": [{"observation": o, "why": w, "improvement": i} for o, w, i in REG.URL_LIMITS],
    }
    with report_connection(timeout_ms=180000, db="enrichment") as rc:
        cat = rc.safe("list tables", lambda: Catalog(rc))
        f = cat.find(REG.URL_TABLE, "url_extraction") if cat else None
        live = {"found": bool(f)}
        if f:
            cols = cat.columns([(f["schema"], f["table"])]).get((f["schema"], f["table"]), [])
            live["table"] = f["label"]
            live["columns"] = [c for c, _ in cols]
            filled, total = rc.safe("field fill", lambda: _filled_pct_query(rc, f["rel"], cols), ({}, 0))
            live["total"] = total
            fields = []
            for key, label, rule in REG.URL_OUTPUT_FIELDS + [(m, m.replace("_", " ").title(), "Keyword metric from the input CSV")
                                                              for m in REG.URL_METRIC_FIELDS] + \
                    [("keyword", "Keyword", "Search phrase from the input CSV"),
                     ("ranking_url", "Ranking URL", "Original ranking URL")]:
                c = _col(cols, key)
                n = filled.get(c) if c else None
                fields.append({"key": key, "label": label, "rule": rule, "exists": bool(c), "filled": n,
                               "fill_pct": pct(n or 0, total) if (c and total) else (None if not c else 0)})
            live["fields"] = fields

            def top(key, limit=15):
                c = _col(cols, key)
                return rc.safe(f"top {key}", lambda: _top(rc, f["rel"], c, limit), []) if c else []

            live["top"] = {k: top(k) for k in ("source", "category", "city", "state", "region", "country")}
            sf = _col(cols, "source_file")
            live["source_files"] = rc.safe("source files", lambda: _top(rc, f["rel"], sf, 100), []) if sf else []
            pr = _col(cols, "priority_rank")
            live["priority_rank"] = rc.safe("priority rank", lambda: rc.rows(
                f"SELECT {rc.q(pr)} AS rank_value, COUNT(*) AS value FROM {f['rel']} "
                f"GROUP BY {rc.q(pr)} ORDER BY {rc.q(pr)}"), []) if pr else []
            for r in live["priority_rank"]:
                r["name"] = "Blank" if r["rank_value"] is None else f"Rank {r['rank_value']}"
            # the document says the three category fields are copies - check it
            c1, c2, c3 = _col(cols, "category"), _col(cols, "business_category"), _col(cols, "product_category")
            if c1 and c2 and c3 and total:
                same = rc.safe("category copies", lambda: rc.scalar(
                    f"SELECT COUNT(*) FROM {f['rel']} WHERE COALESCE({rc.as_text(rc.q(c1))}, '') = "
                    f"COALESCE({rc.as_text(rc.q(c2))}, '') AND COALESCE({rc.as_text(rc.q(c1))}, '') = "
                    f"COALESCE({rc.as_text(rc.q(c3))}, '')"))
                live["category_copies"] = {"same": same, "pct": pct(same or 0, total)}
            # documented limitations, checked against the data
            checks = []
            by_key = {x["key"]: x for x in fields}
            for key, text_ in (("area", "Area is always blank"), ("unknown", "Unknown is always blank")):
                x = by_key.get(key)
                if x and x["exists"]:
                    checks.append({"check": text_, "holds": (x["filled"] or 0) == 0,
                                   "live": f"{x['filled'] or 0:,} rows filled"})
            if live["priority_rank"]:
                non1 = sum(int(r["value"]) for r in live["priority_rank"] if _rank_key(r["rank_value"]) != 1)
                checks.append({"check": "Priority Rank is always 1", "holds": non1 == 0,
                               "live": f"{non1:,} rows with another rank"})
            if live.get("category_copies"):
                cc = live["category_copies"]
                checks.append({"check": "Category, Business Category and Product Category are copies",
                               "holds": (cc["same"] or 0) == total, "live": f"{cc['pct'] or 0}% of rows identical"})
            for key, label in (("city", "City"), ("state", "State"), ("region", "Region"), ("source", "Source")):
                x = by_key.get(key)
                if x and x["exists"]:
                    checks.append({"check": f"{label} can stay blank when the URL gives no evidence",
                                   "holds": None, "live": f"{100 - (x['fill_pct'] or 0):.1f}% blank"})
            live["checks"] = checks
        errors = rc.errors
    return {"data": {"doc": doc, "live": live}, "errors": errors, "generated_at": now_iso()}


# ═════════════════════════════════════════════════════════════════════════════
# 03 + 04  Location matching
# ═════════════════════════════════════════════════════════════════════════════

def _norm_name(s):
    return " ".join(str(s or "").lower().replace("&", " and ").split())


def build_location_matching():
    out = {"docs": REG.LOCATION_DOCS, "new_cities_doc": REG.NEW_CITIES, "states_added_doc": REG.STATES_ADDED,
           "cities_to_investigate_doc": REG.CITIES_TO_INVESTIGATE, "city_match_order": REG.CITY_MATCH_ORDER,
           "aliases": REG.STATE_ALIASES, "rank_doc": REG.LOCATION_RANK_DOC}
    errors = []
    with report_connection(timeout_ms=180000) as rc:
        lm = rc.find_table("location_master")
        live = {"found": bool(lm)}
        if lm:
            tcol = rc.find_col(lm, "location_type")
            lcol = rc.find_col(lm, "location_level", "level")
            ncol = rc.find_col(lm, "name")
            pcol = rc.find_col(lm, "parent_id")
            icol = rc.find_col(lm, "id")
            t = rc.q(lm)
            ttxt = f"LOWER(TRIM({rc.as_text('m.' + rc.q(tcol))}))" if tcol else None

            # totals by type
            if tcol:
                by_type = rc.safe("location_master by type", lambda: rc.rows(
                    f"SELECT {rc.q(tcol)} AS name, COUNT(*) AS value FROM {t} GROUP BY {rc.q(tcol)} ORDER BY COUNT(*) DESC"), [])
                live["by_type"] = by_type
                live["total"] = sum(int(r["value"]) for r in by_type)

            same_type = lambda a, b: rc.as_text(f"{a}.{rc.q(icol)}") + " = " + rc.as_text(f"{b}.{rc.q(pcol)}")

            # states now in location_master, and the 5 added by the state sync
            if tcol and ncol:
                states = rc.safe("states", lambda: [r["name"] for r in rc.rows(
                    f"SELECT m.{rc.q(ncol)} AS name FROM {t} m WHERE {ttxt} = 'state'")], [])
                live["states"] = {"count": len(states), "names": sorted(states, key=str.lower)}
                have = {_norm_name(s) for s in states}
                live["states_added"] = [{"state": s, "found": _norm_name(s) in have} for s in REG.STATES_ADDED]

            # the 14 new city records
            if icol and ncol and pcol:
                ids = [c[2] for c in REG.NEW_CITIES]
                q = text(
                    f"SELECT m.{rc.q(icol)} AS id, m.{rc.q(ncol)} AS name, "
                    f"{('m.' + rc.q(tcol)) if tcol else 'NULL'} AS location_type, "
                    f"{('m.' + rc.q(lcol)) if lcol else 'NULL'} AS level_value, "
                    f"p.{rc.q(ncol)} AS parent_name, {('p.' + rc.q(tcol)) if tcol else 'NULL'} AS parent_type "
                    f"FROM {t} m LEFT JOIN {t} p ON {same_type('p', 'm')} "
                    f"WHERE {rc.as_text('m.' + rc.q(icol))} IN :ids"
                ).bindparams(bindparam("ids", expanding=True))
                got = rc.safe("new city ids", lambda: {str(r["id"]): dict(r) for r in rc.conn.execute(
                    q, {"ids": [str(i) for i in ids]}).mappings()}, {}) or {}
                # same name elsewhere as a City (maybe created under another id)
                by_name = {}
                if tcol:
                    qn = text(
                        f"SELECT m.{rc.q(icol)} AS id, m.{rc.q(ncol)} AS name, p.{rc.q(ncol)} AS parent_name "
                        f"FROM {t} m LEFT JOIN {t} p ON {same_type('p', 'm')} "
                        f"WHERE {ttxt} = 'city' AND LOWER(TRIM(m.{rc.q(ncol)})) IN :names"
                    ).bindparams(bindparam("names", expanding=True))
                    for r in (rc.safe("new city names", lambda: list(rc.conn.execute(
                            qn, {"names": [c[0].lower() for c in REG.NEW_CITIES]}).mappings()), []) or []):
                        by_name.setdefault(_norm_name(r["name"]), []).append(dict(r))
                checks = []
                for city, state, cid in REG.NEW_CITIES:
                    r = got.get(str(cid))
                    issues = []
                    if not r:
                        issues.append(f"ID {cid} not found")
                    else:
                        if _norm_name(r["name"]) != _norm_name(city):
                            issues.append(f"name is '{r['name']}'")
                        if tcol and _norm_name(r["location_type"]) != "city":
                            issues.append(f"type is '{r['location_type']}' (expected City)")
                        if lcol and _rank_key(r["level_value"]) != 3:
                            issues.append(f"level is {r['level_value']} (expected 3)")
                        if _norm_name(r["parent_name"]) != _norm_name(state):
                            issues.append(f"parent is '{r['parent_name'] or 'none'}' (expected {state})")
                    others = [o for o in by_name.get(_norm_name(city), []) if str(o["id"]) != str(cid)]
                    checks.append({
                        "city": city, "state": state, "id": cid, "found": bool(r),
                        "live_name": r["name"] if r else None,
                        "live_type": r["location_type"] if r else None,
                        "live_level": _rank_key(r["level_value"]) if r else None,
                        "live_parent": r["parent_name"] if r else None,
                        "valid": bool(r) and not issues, "issues": issues,
                        "other_city_records": [f"{o['id']} ({o['parent_name'] or 'no parent'})" for o in others][:5],
                    })
                live["new_cities"] = checks

            # incorrect Area names (Missing Area report): no letters, or same name as its City/State/Country
            if tcol and ncol and pcol and icol:
                an, cn, sn, kn = (f"LOWER(TRIM({x}.{rc.q(ncol)}))" for x in ("m", "c", "s", "k"))
                base = (f"FROM {t} m LEFT JOIN {t} c ON {same_type('c', 'm')} "
                        f"LEFT JOIN {t} s ON {same_type('s', 'c')} LEFT JOIN {t} k ON {same_type('k', 's')} "
                        f"WHERE {ttxt} = 'area'")
                digits = rc.no_letters("m." + rc.q(ncol))
                dup = f"({an} = {cn} OR {an} = {sn} OR {an} = {kn})"
                summary = rc.safe("bad area names", lambda: rc.rows(
                    f"SELECT COUNT(*) AS area_rows, "
                    f"SUM(CASE WHEN {digits} THEN 1 ELSE 0 END) AS no_letters, "
                    f"SUM(CASE WHEN NOT ({digits}) AND {dup} THEN 1 ELSE 0 END) AS same_as_parent, "
                    f"COUNT(DISTINCT CASE WHEN ({digits}) OR {dup} THEN m.{rc.q(pcol)} END) AS cities_affected "
                    f"{base}")[0], {})
                if summary:
                    summary = {k: int(v or 0) for k, v in summary.items()}
                    summary["incorrect_total"] = summary["no_letters"] + summary["same_as_parent"]
                live["bad_areas"] = summary
                live["bad_area_rows"] = rc.safe("bad area list", lambda: rc.rows(
                    f"SELECT m.{rc.q(icol)} AS id, m.{rc.q(ncol)} AS name, c.{rc.q(ncol)} AS city, "
                    f"s.{rc.q(ncol)} AS state, CASE WHEN {digits} THEN 'No letters (code / number)' "
                    f"WHEN {an} = {cn} THEN 'Same as its City' WHEN {an} = {sn} THEN 'Same as its State' "
                    f"ELSE 'Same as its Country' END AS reason {base} AND (({digits}) OR {dup}) "
                    f"ORDER BY c.{rc.q(ncol)}, m.{rc.q(icol)} LIMIT 5000"), [])
        errors += rc.errors
    out["live"] = live

    # master_priority (the file the matching reports worked on) - if it has been loaded
    with report_connection(timeout_ms=180000, db="enrichment") as rc:
        cat = rc.safe("list tables", lambda: Catalog(rc))
        f = cat.find("master_priority_updated", "master_priority") if cat else None
        mp = {"found": bool(f)}
        if f:
            cols = cat.columns([(f["schema"], f["table"])]).get((f["schema"], f["table"]), [])
            mp["table"] = f["label"]
            rel = f["rel"]
            total = rc.safe("priority total", lambda: rc.scalar(f"SELECT COUNT(*) FROM {rel}"))
            mp["total"] = total
            for key in ("region", "location_id", "city", "state", "area", "matched_location_name"):
                c = _col(cols, key)
                if c:
                    n = rc.safe(f"priority {key} filled", lambda c=c: rc.scalar(
                        f"SELECT COUNT(*) FROM {rel} WHERE {_filled_cond(rc, c, '')}"))
                    mp[f"{key}_filled"] = n
                    mp[f"{key}_pct"] = pct(n or 0, total)
            for key in ("region", "location_match_status"):
                c = _col(cols, key)
                if c:
                    mp[f"by_{key}"] = rc.safe(f"priority by {key}", lambda c=c: _top(rc, rel, c, 20), [])
            cc, sc, lc = _col(cols, "city"), _col(cols, "state"), _col(cols, "location_id")
            if cc and sc:
                mp["no_city_state"] = rc.safe("no city and state", lambda: rc.scalar(
                    f"SELECT COUNT(*) FROM {rel} WHERE NOT ({_filled_cond(rc, cc, '')}) "
                    f"AND NOT ({_filled_cond(rc, sc, '')})"))
            if cc and lc:
                q = text(f"SELECT LOWER(TRIM({rc.as_text(rc.q(cc))})) AS city, COUNT(*) AS n FROM {rel} "
                         f"WHERE NOT ({_filled_cond(rc, lc, '')}) AND LOWER(TRIM({rc.as_text(rc.q(cc))})) IN :names "
                         f"GROUP BY LOWER(TRIM({rc.as_text(rc.q(cc))}))").bindparams(bindparam("names", expanding=True))
                live_unmatched = rc.safe("unmatched per city", lambda: {r["city"]: int(r["n"]) for r in rc.conn.execute(
                    q, {"names": [c.lower() for c, _ in REG.CITIES_TO_INVESTIGATE]}).mappings()}, {}) or {}
                mp["cities_to_investigate"] = [{"city": c, "doc": n, "live": live_unmatched.get(c.lower(), 0)}
                                               for c, n in REG.CITIES_TO_INVESTIGATE]
                mp["unmatched"] = rc.safe("unmatched total", lambda: rc.scalar(
                    f"SELECT COUNT(*) FROM {rel} WHERE NOT ({_filled_cond(rc, lc, '')})"))
        errors += rc.errors
    out["priority"] = mp

    # 04 ranking: report numbers vs live ranking
    ranking, _ = cached("ranking", build_ranking)
    lr = (ranking.get("data") or {}).get("location_rank") or {}
    doc = REG.LOCATION_RANK_DOC
    type_sum = sum(doc["by_type_rank1"].values())
    out["rank_compare"] = {
        "by_rank": [{"name": k, "doc": v, "live": (lr.get("totals") or {}).get(k)} for k, v in doc["by_rank"].items()],
        "by_type_rank1": [{"name": k, "doc": v,
                           "live": next((r.get("Rank 1") for r in lr.get("rows", []) if r["location_type"] == k), None)}
                          for k, v in doc["by_type_rank1"].items()],
        "doc_total": doc["total"], "live_total": lr.get("total_location_master"),
        "doc_note": (f"In the report, the Rank 1 numbers by location type add up to {type_sum:,}, "
                     f"but its Rank 1 total is {doc['by_rank']['Rank 1']:,} - the type table and the rank table "
                     f"do not agree. The live numbers here are calculated directly from location_master.")
        if type_sum != doc["by_rank"]["Rank 1"] else None,
    }
    return {"data": out, "errors": errors, "generated_at": now_iso()}


# ═════════════════════════════════════════════════════════════════════════════
# 01  Final Data Enrichment Master Report - the 12 steps, with live evidence
# ═════════════════════════════════════════════════════════════════════════════

def _step(n, metrics=None, note=None, link=None, status=None):
    num, name, phase, desc = REG.PROCESS_STEPS[n - 1]
    metrics = [m for m in (metrics or []) if m and m.get("value") is not None]
    return {"no": num, "step": name, "phase": phase, "description": desc, "metrics": metrics,
            "status": status or ("live" if metrics else "not_measured"), "note": note, "link": link}


def _m(label, value, fmt="number", status=None):
    return {"label": label, "value": value, "format": fmt, "status": status}


def build_process():
    errors = []

    def use(key, builder, ttl=None):
        try:
            payload, _ = cached(key, builder, ttl=ttl)
            errors.extend(payload.get("errors") or [])
            return payload.get("data") or {}
        except Exception as e:  # noqa: BLE001
            errors.append({"step": key, "error": str(getattr(e, "orig", e)).splitlines()[0][:300]})
            return {}

    url = use("de:url-extraction", build_url_extraction)
    loc = use("de:location-matching", build_location_matching)
    counts = use("count-report", build_count_report)
    hier = use("hierarchy", build_hierarchy)
    inv = use("db-tables:False", lambda: build_db_tables(False), ttl=600)
    raw = use("de:raw-sources:False", lambda: build_raw_sources(False), ttl=600)
    ranking = use("ranking", build_ranking)

    ul = url.get("live") or {}
    ufield = {f["key"]: f for f in ul.get("fields", [])}
    count_row = {r["field"]: r for r in counts.get("rows", [])}
    hcheck = {c["key"]: c for c in hier.get("checks", [])}
    mp = loc.get("priority") or {}
    lr = ranking.get("location_rank") or {}
    url_note = None if ul.get("found") else f"{REG.URL_TABLE} is not in the database yet"

    def hier_metrics(key):
        c = hcheck.get(key) or {}
        if not c.get("found"):
            return []
        return [_m(f"{c['label']} rows", c.get("total")),
                _m("Missing parent (below top level)", c.get("non_root_missing_parent"),
                   status="good" if not c.get("non_root_missing_parent") else "warning"),
                _m("Broken parent links", c.get("orphans"), status="good" if not c.get("orphans") else "critical")]

    def map_metrics(field, label):
        r = count_row.get(field) or {}
        if r.get("master_count") is None:
            return []
        return [_m(f"{label} master entries", r.get("master_count")),
                _m("Matched in data", r.get("matched")),
                _m("Match %", r.get("match_pct"), "pct",
                   status="good" if (r.get("match_pct") or 0) >= 90 else "warning" if (r.get("match_pct") or 0) >= 25 else "critical"),
                _m("Pending", r.get("pending"))]

    new_cities = (loc.get("live") or {}).get("new_cities") or []
    rt = raw.get("totals") or {}
    steps = [
        _step(1, [_m("CSV files loaded", len(ul.get("source_files") or []) or None),
                  _m("Rows in " + REG.URL_TABLE, ul.get("total")),
                  _m("Raw sources in the database", rt.get("in_db")),
                  _m("Raw source records", rt.get("rows"))],
              note=url_note, link="/data-enrichment/raw-sources"),
        _step(2, note="Cleaning runs in the Python script before loading; no table records it, so there is no live number for this step.",
              status="documented"),
        _step(3, [_m("Rows with a Ranking URL", (ufield.get("ranking_url") or {}).get("filled")),
                  _m("City extracted", (ufield.get("city") or {}).get("fill_pct"), "pct"),
                  _m("Category extracted", (ufield.get("category") or {}).get("fill_pct"), "pct"),
                  _m("Source extracted", (ufield.get("source") or {}).get("fill_pct"), "pct")],
              note=url_note, link="/data-enrichment/url-extraction"),
        _step(4, [_m("Rows with search volume", (ufield.get("volume") or {}).get("filled")),
                  _m("Location master at Rank 1", (lr.get("totals") or {}).get("Rank 1")),
                  _m("Location master at Rank 2-5",
                     sum((lr.get("totals") or {}).get(f"Rank {i}", 0) for i in range(2, 6)) if lr else None)],
              link="/ranking"),
        _step(5, [_m("Priority rows with a location_id", mp.get("location_id_filled")),
                  _m("Location mapped %", mp.get("location_id_pct"), "pct"),
                  _m("Still unmatched", mp.get("unmatched")),
                  _m("New city records valid", sum(1 for c in new_cities if c["valid"]) if new_cities else None)],
              note=None if mp.get("found") else "master_priority is not in the database yet - location results shown are the live location_master checks",
              link="/data-enrichment/location-matching"),
        _step(6, map_metrics("business_category", "Business category"), link="/count"),
        _step(7, map_metrics("product_category", "Product category"), link="/count"),
        _step(8, hier_metrics("master_categories"), link="/hierarchy"),
        _step(9, hier_metrics("product_category_master") or hier_metrics("page_product_categories"), link="/hierarchy"),
        _step(10, [_m("New city records checked", len(new_cities) or None),
                   _m("New city records valid", sum(1 for c in new_cities if c["valid"]) if new_cities else None,
                      status="good" if new_cities and all(c["valid"] for c in new_cities) else "warning"),
                   _m("Incorrect Area names (live)", ((loc.get("live") or {}).get("bad_areas") or {}).get("incorrect_total"))],
               note="The automation script's own results are not stored in the database; these are the live validation checks from the location reports.",
               link="/data-enrichment/location-matching"),
        _step(11, [_m("Tables in TestDB", (inv.get("totals") or {}).get("tables")),
                   _m("Records in TestDB", (inv.get("totals") or {}).get("rows")),
                   _m("Complete tables", sum(1 for x in inv.get("tables", []) if x.get("status") == "Complete") if inv else None)],
               link="/db-tables"),
        _step(12, [], status="live",
              note="You are looking at it - every page under HBD Reports and Data Enrichment reads the database live."),
    ]
    phases = []
    for s in steps:
        if not phases or phases[-1]["phase"] != s["phase"]:
            phases.append({"phase": s["phase"], "steps": []})
        phases[-1]["steps"].append(s["no"])
    return {
        "data": {"title": REG.PROCESS_TITLE, "objective": REG.PROCESS_OBJECTIVE, "overview": REG.PROCESS_OVERVIEW,
                 "key_points": REG.PROCESS_KEY_POINTS, "steps": steps, "phases": phases,
                 "database": engine_source()},
        "errors": errors, "generated_at": now_iso(),
    }
