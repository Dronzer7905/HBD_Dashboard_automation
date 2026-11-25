Pipeline monitoring and guided ingestion handover
=================================================

25 November 2026, Asia/Calcutta. Scope: BG-1.13 and BG-1.8 through BG-1.10.

Delivery status
---------------

Local implementation and synthetic integration tests are complete. Company
database access was revoked following a network change, as confirmed by the
team lead through the user. The earlier connection attempt was rejected by
Cloudflare before PostgreSQL authentication. No company schema, records, grants,
scrapers, or deployment were changed. Company installation and live API operation
of the previous BG-1.11 ZIP remain team-reported, not independently reverified.

The new branch is based on main 617e91f. Main did not contain the shipped BG-1.11
ZIP implementation, so this PR also brings that prerequisite into version control
with its mapping configuration and blueprint registration. The original BG-1.11
worktree and unrelated main-checkout Zepto edit are preserved. Historical BG-1.11
documents describe the earlier delivery; their Draft PR/publication restrictions
are superseded by the user's 25 November instruction to open a non-draft PR.

API contract
------------

All endpoints require the existing JWT. Mutations require header Bearer auth.
Upload and batch reads/writes require an existing public.users ID. Users can only
start/read their own uploads and batches; another owner's IDs return 404.
Scheduler mutations additionally require SCHEDULER_OPERATOR_IDS membership
(comma-separated existing user IDs; empty by default). No new public auth bypass.

POST /api/ingest/upload
~~~~~~~~~~~~~~~~~~~~~~

multipart/form-data, exactly one ``file`` field. UTF-8 CSV (optional BOM), TSV,
or XLSX; default file limit 100 MiB, workbook expanded size limit 512 MiB.
XLS must be converted to XLSX. Preview reads the first sheet or first five
nonblank data rows lazily and retains strings, phone leading zeroes and headers.
Headers must be unique, nonblank, at most 255 characters, and at most 200 columns.
Malformed row widths can be previewed and are quarantined by the worker.

HTTP 201 example::

    {
      "status":"success", "file_id":"<32 lower-case hex characters>",
      "filename":"stores.csv", "headers":["Store","Phone"],
      "sample_rows":[["Fresh Mart","001234"]],
      "size_bytes":42, "supported_target_fields":["business_name","phone"]
    }

supported_target_fields contains the complete allowlist in actual responses.
Only opaque server IDs leave the API. File paths are never accepted or returned.
The server manifest records the owner, extension, headers and SHA-256. File IDs,
resolved paths and ownership are checked; the worker verifies the hash before
ingesting. Failed upload parsing removes its staged file and manifest.

POST /api/ingest/start-batch
~~~~~~~~~~~~~~~~~~~~~~~~~~

JSON object, maximum 16 KiB::

    {"file_id":"<upload ID>", "category_type":"Retail",
     "column_mapping":{"Store":"business_name","Phone":"phone"}}

Mapping direction is uploaded header -> standard field; an empty target skips
a header. A business_name mapping is required, unknown headers/targets and
duplicate targets are rejected. Optional targets: phone, email, address, city,
state, country, pincode, category, latitude, longitude. Archetypes: dining, retail,
services, healthcare, tourism, itineraries, hotels and play-areas (case-insensitive).

HTTP 202: ``{"status":"started","batch_id":"<ID>","task_id":"<UUID>"}``.
The tracker is committed before publishing tasks.bulk_ingest.stream_chunked_ingest
to heavy_ingestion. Publication failure is an explicit 503/broker_unavailable
and persisted QUEUE_FAILED, never successful ingestion. Retry the canonical
request with the SAME file_id and mapping: one unique tracker is retained,
completed/processing batches are returned, queued/failed batches can be
republished safely. Changed settings for the same upload return 409.

Repeated QUEUED requests may deliver the same batch more than once. Database row
locks, (batch_id,row_number) uniqueness and atomic chunk checkpoints prevent
duplicate committed records. There is no automatic outbox dispatcher: if the web
process dies after committing the tracker but before publishing, repeat the
canonical request. Progress may remain queued until that retry.

The worker first streams a counting pass, then imports chunks of up to 2,500
nonblank logical rows. Counter changes, accepted rows, quarantine rows and the
checkpoint commit together. Committed chunks survive failure; retry reopens the
unchanged file and skips the committed prefix. Blank-name, invalid/nonfinite/
out-of-range coordinates, incomplete coordinate pairs, long/NUL fields and
wrong-width rows are quarantined with a reason. Zero coordinates are valid.
Unreadable CSV structure or file/DB failure fails the batch. This task stages
bronze records; it does not run unverified silver/gold cleaning or category sync.

POST /api/ingest/start
~~~~~~~~~~~~~~~~~~~~~

Compatibility route for the current Anusha branch: multipart ``file``,
``archetype`` (or category_type), and JSON-string ``column_mapping``. It uses
the same validation and worker. Canonical upload + start-batch is preferred for
retry idempotency: repeating multipart start creates a new upload identity.

GET /api/ingest/batch-progress/<batch_id>
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Returns batch_id, task_id, status, total_rows, processed_rows, valid_count,
quarantine_count, progress_pct, error_message and timestamps. The initial total
is null until counting finishes. Counters come from committed database state,
not web-process memory or a short-lived Celery result. Lowercase statuses:
queued, queue_failed, processing, failed, completed. Completed empty files report
100%; unfinished/failed batches never report 100%. ``imported`` (= valid_count),
``total`` and ``percent`` aliases support the current wizard.

GET /api/ingest/quarantine-records/<batch_id>
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Owner-scoped rows with row_number, raw_data and error_reason. Query parameters:
limit (default 50, maximum 200), after_row (default 0). Returns records and
next_after_row, null at the end. No offset scan or unbounded response.

GET /api/pipeline-status
~~~~~~~~~~~~~~~~~~~~~~~

Returns raw_ingest, tier1_clean, geo_mapped, catalog_mapped and live_ready,
plus stages [{key,count,available,error,source}], updated_at and health metrics:
database pool size/checked-out/overflow, Redis queue depths, responding workers.
total_staged_businesses is the existing frontend's raw-ingest alias.

Each stage uses an exact count and an independent read-only PostgreSQL transaction
with a configurable statement timeout. Missing/slow sources return null with an
explicit reason. The endpoint remains HTTP 200/degraded when individual sources
are unavailable, preserving usable counts. It never substitutes demo values or
zero for unavailable metrics. Stage counts are independent observations, not
mutually exclusive buckets or a guaranteed common transaction snapshot.

Default sources: bronze_staging.raw_businesses and silver_clean.tier1_master_clean.
Geo, catalog and live-ready defaults are UNCONFIGURED until their real readiness
definitions are verified. Coordinates alone are not proof of location mapping;
category text alone is not proof of catalog attachment. Configure all sources
after the team lead identifies the appropriate tables or views.

PIPELINE_STAGE_SOURCES is a server-controlled JSON object, for example::

    {"raw_ingest":{"schema":"bronze_staging","table":"raw_businesses"},
     "tier1_clean":{"schema":"silver_clean","table":"tier1_master_clean"},
     "geo_mapped":{"schema":"silver_clean","table":"<verified geo view>"},
     "catalog_mapped":{"schema":"silver_clean","table":"<verified catalog view>"},
     "live_ready":{"schema":"gold_mart","table":"<verified ready view>"}}

Replace placeholders with verified SQL identifiers. A source optionally supports
``column`` with either ``equals`` (bound scalar) or ``not_null:true``. Complex
joins/cohort unions belong in DBA-owned views. Client SQL is not accepted. Raw
defaults only count raw_businesses, not all older Drive/source tables; a verified
union view is required if the dashboard's staged cohort includes those records.

GET /api/schedulers/status
~~~~~~~~~~~~~~~~~~~~~~~~~

Returns schedulers keyed by aliases, task_name, registered, enabled, healthy,
status, configured schedule and last manual-trigger task/result metadata. Also
reports Redis queue depths, responding worker names/count, timezone and Beat
health ``unknown``: schedule configuration is not a Beat heartbeat. No assertion
that Beat is running is made. Expired/missing task results are UNKNOWN_OR_QUEUED.
Celery result TTL remains the existing 1,200 seconds; the last-trigger pointer
lasts 24 hours. Beat-triggered historical runs are not captured by that pointer.

POST /api/schedulers/trigger/<task_name>
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Also accepts /api/schedulers/<task_name>/trigger. Empty body or
``{"kwargs":{...}}`` (maximum 16 KiB). Known aliases and exact allowlisted task
names only; no arbitrary Celery task execution. HTTP 202 means queued, not
completed. Explicit 503 for broker/configuration/unregistered tasks. A failure
to save monitoring AFTER confirmed publishing returns queued with
monitoring_available=false, avoiding a misleading failure and duplicate trigger.

Implemented scraper aliases: amazon, dmart, indiamart, blinkit. Amazon and
IndiaMART accept search_term and pages (1..20); DMart accepts search_term, mode,
pincodes and max_categories (1..100); Blinkit accepts pincode, mode,
max_categories and resume. Client-supplied scraper task IDs are rejected.
Existing refresh/cleaner Beat entry names are also allowlisted.

Planned frontend aliases news, quick-commerce, zomato and gdrive are visible,
but their BG-1.3..1.7 task implementations are absent in the current repository.
They remain not_implemented/503 until the real workers are supplied; this PR
does not fabricate them or dispatch unknown tasks. Existing scraper functions
may swallow their own internal exceptions: Celery SUCCESS only proves that the
worker function returned, not that a desired number of scraper rows was saved.

Frontend integration notes
--------------------------

Anusha's rondaanusha1-art-feature branch was inspected read-only. Its wizard's
multipart start URL, mapping direction, archetype field and progress aliases are
supported; the requested two-step upload/start-batch flow is also available.
Scheduler trigger URL aliases are supported. XLS is deliberately unsupported;
the current wizard's 1 GB client limit must match the server's configured limit.

PipelineStatus.jsx currently calls bare fetch without the shared Axios Bearer
interceptor. Use the existing authenticated api.get('/pipeline-status') or send
the Bearer token explicitly. No auth bypass was introduced to compensate for it.
CommandCenter is currently a static shell. Scheduler pause/resume/log-history
buttons are outside these requested endpoints and still require their later
backend/UI work. No frontend files or other contributor branches were changed.

Deployment prerequisites and configuration
-----------------------------------------

The bronze table/column contract below is a LOCAL IMPLEMENTATION CONTRACT, not
verified company metadata. No migration or startup create_all hook is supplied.
Core metadata is independent of Flask db.metadata. Start-batch checks tables,
types, NOT NULLs, text widths, unique keys and batch FKs before publishing; a
missing/incompatible contract returns 503/schema_not_ready. Existing schema is
never auto-altered. The DBA must reconcile/install this contract after access
returns; do not run fixture table creation on testpostgrey.

* bronze_staging.raw_ingest_batches: batch_id varchar(32) PK; file_id varchar(32)
  NOT NULL UNIQUE; owner_id varchar(64), category_type varchar(40), column_mapping
  JSON, status varchar(20), task_id varchar(36), created_at/updated_at timestamptz,
  all NOT NULL; total_rows BIGINT nullable; processed_rows/valid_count/
  quarantine_count BIGINT NOT NULL; error_message TEXT nullable. Counters are
  nonnegative, processed_rows=valid_count+quarantine_count, total_rows (if known)
  cannot be below processed_rows. Application inserts initial counters.
* bronze_staging.raw_businesses: generated BIGINT id PK; batch_id varchar(32)
  NOT NULL FK batches.batch_id; row_number BIGINT NOT NULL; raw_data JSON NOT NULL;
  category_type varchar(40), business_name varchar(255), both NOT NULL;
  phone/email/address/city/state/country/pincode/category TEXT nullable;
  latitude/longitude double precision nullable. UNIQUE(batch_id,row_number).
* bronze_staging.quarantine_records: generated BIGINT id PK; batch_id varchar(32)
  NOT NULL FK batches.batch_id; row_number BIGINT NOT NULL; raw_data JSON NOT NULL;
  error_reason TEXT NOT NULL. UNIQUE(batch_id,row_number).

Exact executable fixture declarations are services/ingestion_store.py; schema
installation is DBA-owned. Required runtime privileges are schema USAGE, SELECT
on users and the bronze tables, INSERT/UPDATE on batches, INSERT on raw/quarantine,
and sequence USAGE for generated child IDs, plus SELECT on configured metric views.

Read-only CLI once approved libpq PG*/PGSERVICE auth is available::

    python backend/scripts/inspect_ingestion_schema.py --expected-database testpostgrey

The CLI loads no app/.env, requires the exact expected database, sets read-only
defaults and short timeouts on every connection, and reads metadata only. A
compatible result is NOT proof of live API, role privileges, feature flags or
frontend deployment. Recheck BG-1.11 separately with its existing operator CLI.

Configuration (same values on API and worker):

* INGESTION_UPLOAD_DIR: shared persistent staging directory. Compose uses the
  existing uploads volume at /app/tmp/uploads/staging for both containers. Default
  without configuration is OS temp/hbd-ingestion/staging, appropriate for local
  development. Other deployments must configure persistent shared storage.
* INGESTION_MAX_UPLOAD_BYTES: 104857600 default. Align the reverse proxy/client
  request limits. These limits apply to the new upload routes only.
* INGESTION_CHUNK_SIZE: 2500 maximum/default; INGESTION_CHUNK_COOLDOWN: 0.25 seconds.
* SCHEDULER_OPERATOR_IDS: empty denies scheduler triggers; set approved user IDs.
* PIPELINE_STAGE_SOURCES: JSON above; PIPELINE_QUERY_TIMEOUT_MS: 2000 default,
  constrained to 100..10000 ms in the monitoring query.
* CELERY_BROKER_URL / CELERY_RESULT_BACKEND: existing Redis configuration.

Bulk routing is registered in celery_app.py. Existing launchers now consume
celery,heavy_ingestion; existing schedules remain intact. Separate heavy-only
workers can be deployed for capacity isolation (BG-1.1 infrastructure work).
Staged files/manifests are retained for retries; this PR supplies no automatic
retention/deletion job. The operator must define retention/disk quotas before
large-scale usage. Do not delete files for queued/processing/retryable batches.

Verification
------------

Commands, run from repository root using the existing virtualenv interpreter::

    python -m unittest discover -s backend/tests -p 'test_mapping*.py' -q
    python -m unittest discover -s backend/tests -p 'test_ingestion*.py' -q
    python backend/tests/run_mapping_postgres.py --postgres-bin <existing PG bin>
    python backend/tests/run_ingestion_postgres.py --postgres-bin <existing PG bin>

The runners create owned temporary clusters on random loopback ports and remove
them/auth files after shutdown. No .env, company DSN, company data or existing
PostgreSQL service is used. Linux non-root and Windows are supported. SQLite
tests forbid Python socket connections. Actual Celery worker tests use the
memory transport, serialization and a solo worker (not eager execution); no
Redis service or external scraper is contacted. CI runs these same four suites
with synthetic data and no company secrets.

Verified locally after integration: mapping 79 SQLite + 27 PostgreSQL tests;
ingestion 35 SQLite passes with two PostgreSQL-only skips + 37 PostgreSQL passes,
including both skipped cases and actual worker tests. Total 178 passed, zero
failures/errors. Expected negative-case logs show sanitized rollback/task errors.
Python compilation and whitespace checks pass. Full legacy app startup, live
Redis, external scraping, company schema and browser UI integration remain
unverified; AST tests execute the real app auth hook/blueprint registrations.
