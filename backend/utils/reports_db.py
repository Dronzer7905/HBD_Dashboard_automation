"""
Shared database helpers for the HBD Reports + Data Enrichment pages.

Why a separate connection?
    The main app talks to the live MySQL database, but the reports are meant
    to read from the PostgreSQL copy (testpostgres), where the product tables
    (product_catalogue, page_products, product_attributes ...) were populated.
    So the reports get their own, read-only engine that can point somewhere
    different from the main app.

Configuration (environment variables, checked in this order):
    1. REPORTS_DB_URL   full SQLAlchemy URL, e.g.
                        postgresql+psycopg2://user:pass@152.53.94.20:5433/testpostgres
    2. REPORTS_DB_HOST / REPORTS_DB_PORT / REPORTS_DB_USER /
       REPORTS_DB_PASSWORD / REPORTS_DB_NAME   (driver: postgresql+psycopg2,
       override with REPORTS_DB_DRIVER)
    3. nothing set -> falls back to the main app database (config.py)

    Optional: REPORTS_DB_SCHEMA (defaults to the connection's current schema,
    normally "public" on Postgres).

Everything here is read-only. No INSERT / UPDATE / DELETE anywhere.
"""

import datetime
import decimal
import os
import threading
import time
import urllib.parse

from sqlalchemy import create_engine, text

_engine = None
_engine_lock = threading.Lock()
_engine_source = None


# ─── Engine ──────────────────────────────────────────────────────────────────

def _build_url():
    url = os.getenv("REPORTS_DB_URL")
    if url:
        return url, "REPORTS_DB_URL"

    host = os.getenv("REPORTS_DB_HOST")
    if host:
        user = os.getenv("REPORTS_DB_USER", "")
        pwd = urllib.parse.quote_plus(os.getenv("REPORTS_DB_PASSWORD", ""))
        port = os.getenv("REPORTS_DB_PORT", "5432")
        name = os.getenv("REPORTS_DB_NAME", "")
        driver = os.getenv("REPORTS_DB_DRIVER", "postgresql+psycopg2")
        return f"{driver}://{user}:{pwd}@{host}:{port}/{name}", "REPORTS_DB_HOST"

    from config import config  # imported lazily so this module has no side effects
    return config.SQLALCHEMY_DATABASE_URI, "main app database (config.py)"


def _make_psycopg_gevent_friendly():
    """
    Production runs gunicorn with gevent workers. psycopg2 is a C driver that
    would block the whole worker while a long report query runs; psycogreen
    makes it cooperative. Only applied when gevent has patched the process.
    """
    try:
        from gevent import monkey
        if monkey.is_module_patched("socket"):
            from psycogreen.gevent import patch_psycopg
            patch_psycopg()
    except Exception:
        pass


def get_engine():
    """Create the reports engine on first use (so a bad/missing driver never breaks app start-up)."""
    global _engine, _engine_source
    if _engine is None:
        with _engine_lock:
            if _engine is None:
                url, source = _build_url()
                if url.startswith("postgresql"):
                    _make_psycopg_gevent_friendly()
                _engine = create_engine(
                    url,
                    pool_pre_ping=True,
                    pool_recycle=280,
                    pool_size=5,
                    max_overflow=5,
                    connect_args={"connect_timeout": 15},
                )
                _engine_source = source
    return _engine


def engine_source():
    get_engine()
    return _engine_source


# ─── Dialect helpers ─────────────────────────────────────────────────────────

class ReportConn:
    """
    Thin wrapper around a SQLAlchemy connection that knows the dialect,
    quotes identifiers correctly (Postgres "x" vs MySQL `x`), discovers tables
    and columns case-insensitively, and runs each step inside a SAVEPOINT so
    one failing query never breaks the rest of a report.
    """

    def __init__(self, conn, timeout_ms=60000):
        self.conn = conn
        self.dialect = conn.dialect.name  # 'postgresql' or 'mysql'
        self.is_pg = self.dialect == "postgresql"
        self._prep = conn.dialect.identifier_preparer
        self.errors = []
        self._tables = None
        self._columns = {}
        self.set_timeout(timeout_ms)

    # quoting / casting
    def q(self, name):
        return self._prep.quote_identifier(name)

    def as_text(self, expr):
        return f"CAST({expr} AS TEXT)" if self.is_pg else f"CAST({expr} AS CHAR)"

    def not_blank(self, col_expr, extra_excluded=()):
        """SQL condition: value is present (not NULL / not empty / not in extra_excluded)."""
        cond = f"{col_expr} IS NOT NULL AND TRIM({self.as_text(col_expr)}) <> ''"
        for v in extra_excluded:
            cond += f" AND TRIM({self.as_text(col_expr)}) <> '{v}'"
        return cond

    def no_letters(self, col_expr):
        """SQL condition: text contains no letters at all (e.g. '099332 22243', '12/3')."""
        if self.is_pg:
            return f"{self.as_text(col_expr)} !~ '[A-Za-z]'"
        return f"{self.as_text(col_expr)} NOT REGEXP '[A-Za-z]'"

    def set_timeout(self, ms):
        try:
            if self.is_pg:
                self.conn.execute(text(f"SET LOCAL statement_timeout = {int(ms)}"))
            elif self.dialect == "mysql":
                self.conn.execute(text(f"SET SESSION max_execution_time = {int(ms)}"))
        except Exception:
            pass

    # schema discovery
    def _schema_filter(self):
        schema = os.getenv("REPORTS_DB_SCHEMA")
        if schema:
            return "table_schema = :schema", {"schema": schema}
        if self.is_pg:
            return "table_schema = current_schema()", {}
        return "table_schema = DATABASE()", {}

    def tables(self):
        """dict: lower-case name -> real name, for every base table."""
        if self._tables is None:
            where, params = self._schema_filter()
            rows = self.conn.execute(
                text(f"SELECT table_name FROM information_schema.tables "
                     f"WHERE {where} AND table_type = 'BASE TABLE'"),
                params,
            ).fetchall()
            self._tables = {r[0].lower(): r[0] for r in rows}
        return self._tables

    def find_table(self, *candidates):
        tbls = self.tables()
        for c in candidates:
            if c and c.lower() in tbls:
                return tbls[c.lower()]
        return None

    def all_columns(self):
        """dict: real table name -> [(column_name, data_type), ...] for the whole schema (one query)."""
        where, params = self._schema_filter()
        rows = self.conn.execute(
            text(f"SELECT table_name, column_name, data_type FROM information_schema.columns "
                 f"WHERE {where} ORDER BY table_name, ordinal_position"),
            params,
        ).fetchall()
        out = {}
        for t, c, dt in rows:
            out.setdefault(t, []).append((c, (dt or "").lower()))
        self._columns.update(out)
        return out

    def columns(self, table):
        if table not in self._columns:
            where, params = self._schema_filter()
            params = dict(params, t=table)
            rows = self.conn.execute(
                text(f"SELECT column_name, data_type FROM information_schema.columns "
                     f"WHERE {where} AND table_name = :t ORDER BY ordinal_position"),
                params,
            ).fetchall()
            self._columns[table] = [(r[0], (r[1] or "").lower()) for r in rows]
        return self._columns[table]

    def find_col(self, table, *candidates):
        cols = {c.lower(): c for c, _ in self.columns(table)}
        for c in candidates:
            if c and c.lower() in cols:
                return cols[c.lower()]
        return None

    # safe execution
    def safe(self, label, fn, default=None):
        """Run fn() inside a SAVEPOINT; on failure record the error and return default."""
        sp = self.conn.begin_nested()
        try:
            result = fn()
            sp.commit()
            return result
        except Exception as e:  # noqa: BLE001 - we want every failure reported, not raised
            try:
                sp.rollback()
            except Exception:
                pass
            msg = str(getattr(e, "orig", e)).strip().splitlines()[0][:300]
            self.errors.append({"step": label, "error": msg})
            return default

    def scalar(self, sql, params=None):
        return self.conn.execute(text(sql), params or {}).scalar()

    def rows(self, sql, params=None):
        return [dict(r) for r in self.conn.execute(text(sql), params or {}).mappings().fetchall()]

    def estimated_counts(self):
        """Fast row-count estimates from DB statistics: dict real table name -> int."""
        if self.is_pg:
            schema = os.getenv("REPORTS_DB_SCHEMA")
            ns = "n.nspname = :schema" if schema else "n.nspname = current_schema()"
            rows = self.conn.execute(text(f"""
                SELECT c.relname AS t,
                       GREATEST(c.reltuples, 0)::bigint AS reltuples,
                       s.n_live_tup AS live
                FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                LEFT JOIN pg_stat_user_tables s ON s.relid = c.oid
                WHERE {ns} AND c.relkind IN ('r', 'p')
            """), {"schema": schema} if schema else {}).fetchall()
            return {r[0]: int(max(r[1] or 0, r[2] or 0)) for r in rows}
        where, params = self._schema_filter()
        rows = self.conn.execute(
            text(f"SELECT table_name, table_rows FROM information_schema.tables WHERE {where}"), params
        ).fetchall()
        return {r[0]: int(r[1] or 0) for r in rows}


class report_connection:
    """
    Context manager: `with report_connection() as rc: ...`
    Opens one transaction (needed for SAVEPOINTs + statement timeout) and
    always rolls back at the end - reports never write anything.
    """

    def __init__(self, timeout_ms=60000):
        self.timeout_ms = timeout_ms

    def __enter__(self):
        self._conn = get_engine().connect()
        self._trans = self._conn.begin()
        return ReportConn(self._conn, self.timeout_ms)

    def __exit__(self, exc_type, exc, tb):
        try:
            self._trans.rollback()
        finally:
            self._conn.close()
        return False


# ─── Caching + JSON helpers ──────────────────────────────────────────────────

_cache = {}
_cache_lock = threading.Lock()
_key_locks = {}
CACHE_SECONDS = int(os.getenv("REPORTS_CACHE_SECONDS", "300"))


def _lock_for(key):
    with _cache_lock:
        return _key_locks.setdefault(key, threading.Lock())


def cached(key, builder, refresh=False, ttl=None):
    """
    Return (payload, from_cache). Payload is rebuilt when refresh=True or older than ttl.
    Only one request builds a given report at a time; others wait and reuse the result.
    """
    ttl = CACHE_SECONDS if ttl is None else ttl
    started = time.time()
    if not refresh:
        with _cache_lock:
            hit = _cache.get(key)
        if hit and started - hit[0] < ttl:
            return hit[1], True
    with _lock_for(key):
        with _cache_lock:
            hit = _cache.get(key)
        # someone else finished building while we waited
        if hit and hit[0] >= started:
            return hit[1], True
        if hit and not refresh and time.time() - hit[0] < ttl:
            return hit[1], True
        payload = builder()
        with _cache_lock:
            _cache[key] = (time.time(), payload)
        return payload, False


def to_json_safe(value):
    """Convert Decimal / datetime / nested structures into JSON-friendly values."""
    if isinstance(value, dict):
        return {k: to_json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_json_safe(v) for v in value]
    if isinstance(value, decimal.Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, (datetime.datetime, datetime.date)):
        return value.isoformat()
    return value


def pct(part, whole, digits=2):
    if not whole:
        return None
    return round(float(part) * 100.0 / float(whole), digits)


def now_iso():
    return datetime.datetime.now().isoformat(timespec="seconds")
