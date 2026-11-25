Publication note - 25 November 2026
==================================

Historical BG-1.11 delivery record follows. PR 29 has since been closed without
merge. The user reports the ZIP was applied by the team and has explicitly
authorized a new non-draft ingestion PR. This branch imports the shipped sources
because GitHub main lacked them. Current delivery/test/deployment qualifications
are in docs/BG-1.13-INGESTION-HANDOVER.rst; they supersede historical publication
status below. Company database access is currently revoked; its installation
has not been independently reverified today.

BG-1.11 PostgreSQL implementation handover
==========================================

24 November 2026 (Asia/Calcutta). Honeybee Digital / CityHangaround.
Task owner: Bhargav Sonawane. Existing Draft PR: #29.

IMPLEMENTATION READY FOR USER REVIEW â€” NO COMMIT OR PUSH PERFORMED.

Delivery and approved scope
----------------------------

Following the user's report of team-lead approval, the previously tested local
solution now includes exact PostgreSQL DDL, an explicit operator CLI, a shared
metadata/privilege verifier and real disposable PostgreSQL integration tests.
The user required scripts for review and expressly prohibited production DB work,
commits and pushes. This delivery is LOCAL SOURCE plus tested operator-run scripts,
not a company schema installation or deployment.

The existing silver_clean.business_product_category_mappings is preserved. The
new relationship contract uses category_mapping.business_product_category_mappings
in an isolated local or explicitly approved non-production staging database.
Do not retarget the new model to the incompatible silver relation. The original
SQLite prototype remains available under its separate default-off feature gate.

Primary review instructions: docs/BG-1.11-POSTGRES-RUNBOOK.rst.
Prepared PR update text: docs/BG-1.11-PR-UPDATE.txt. The PR remains Draft and its
published head remains fa346f041ed92990f8f58e91915757f93abfa808 until a later
explicitly approved commit and push. The authorized description-only update was verified on 24 November at 11:18 IST.
It identifies these files as local/unpublished, preserves the original published
implementation description, and leaves Draft status and the head SHA unchanged.

Verified repository and company schema
----------------------------------------

Feature worktree:
C:\Users\offic\OneDrive\Desktop\HBD DASHBOARD\HBD_BG_1_11.
Branch: bhargav/BG-1.11-category-mapping. HEAD:
fa346f041ed92990f8f58e91915757f93abfa808. Base/main at inspection:
617e91f3f36022dd57171382a0847d62749deb2c. No checkout, history rewrite, staging,
commit, push, merge, auto-merge, deployment or Ready for Review action performed.

The unrelated main checkout's backend/routes/zepto_routes.py is preserved; its
recorded SHA-256 is 8AAB54985A8717A30EF91FD1AE2047FCF5C5647382F21514D33729B48792FE5E.
No applicable AGENTS.md was found in repository files or inspected ancestors.

On 24 November, company metadata was reverified READ ONLY in testpostgrey as
team_dev. It is identical to docs/BG-1.11-SCHEMA-METADATA.json. Connection used
the approved pg-db.cityhangaround.com tunnel through temporary loopback 15434,
SSL disable per guide, default_transaction_read_only=on, explicit BEGIN READ ONLY,
statement_timeout=5s and lock_timeout=2s. The query read pg_catalog metadata only
and ended in ROLLBACK. Connection and owned tunnel process were closed afterward.
No customer/business rows, other databases (including dataenrichment), company
DDL/DML, grants, migration/sync scripts or app startup were accessed/run.
Credentials were not saved to source or printed in output.

Actual silver table columns:

* mapping_id bigint NOT NULL PK, sequence default.
* raw_category_string varchar(255) NOT NULL UNIQUE, no default.
* master_category_id bigint nullable, no default.
* target_product_category varchar(128) nullable, no default.
* confidence_score numeric(4,3) nullable, default 1.000.
* is_verified boolean nullable, default false.
* created_at timestamptz nullable, default now().

Only PK/unique btree indexes exist; no FK, CHECK, enum, domain or custom trigger.
All six business/subcategory/product/type/status/approver contract fields remain
absent. No semantics were inferred from company row data.

Verified public.product_category_master columns: id integer PK/sequence,
marketplace_name varchar(100) NOT NULL, category_name varchar(255) NOT NULL,
subcategory_name varchar(255) nullable, child_category_name varchar(255) nullable,
parent_id integer nullable, category_level integer NOT NULL, category_path text
NOT NULL, category_key varchar(255) nullable. Non-ID defaults are absent. Only its
PK index exists; parent_id has no database FK. The read model matches its columns,
types and nullability and explicitly selects public on PostgreSQL.

The inspected public users/master/source/history/synonym models still have schema
drift: extra ORM FK/unique/index declarations are absent in company metadata;
users.password is varchar(255) NOT NULL rather than the existing model's
varchar(200), nullable. No company role/admin field exists. These existing tables
are not repaired or altered. Their IDs are verified integer PKs, used by the new
DDL. Actual taxonomy/approver/admin choices remain operator-owned configuration.

New PostgreSQL contract and controls
--------------------------------------

category_mapping.business_product_category_mappings:

* id bigint GENERATED BY DEFAULT AS IDENTITY primary key.
* business_category_id integer NOT NULL FK public.master_categories(id), RESTRICT.
* business_subcategory_id integer NOT NULL FK public.master_categories(id), RESTRICT.
* product_category_id integer NOT NULL FK public.product_category_master(id), RESTRICT.
* mapping_type varchar(40) NOT NULL DEFAULT carries_products, CHECK to that value.
* status varchar(30) NOT NULL DEFAULT APPROVED, CHECK to that value.
* approved_by_user_id integer NOT NULL FK public.users(id), RESTRICT.
* created_at timestamptz NOT NULL DEFAULT now().
* UNIQUE(business_category_id,business_subcategory_id,product_category_id,mapping_type).
* Separate indexes on subcategory, product and approver IDs.

The model uses independent SQLAlchemy metadata. Application db.create_all cannot
install it, and its before_create guard also rejects ORM creation. Runtime requires
MAPPING_POSTGRES_ASSOCIATIONS_ENABLED=true, MAPPING_DEPLOYMENT_ENV=local|staging,
MAPPING_POSTGRES_DATABASE matching the actual connection database, PostgreSQL
dialect, and an exact installed schema/privilege contract. Defaults deny access.
Mismatched or missing schema returns 422/schema_not_ready; disabled/wrong-environment
storage returns 422/local_associations_disabled. No request performs DDL or repair.

001 SQL is transactional and requires explicit session settings for non-production
environment, exact database and confirmation. The CLI also requires explicit
write flags and delays COMMIT until the shared verifier passes. Compatible reruns
preserve data. Wrong columns, constraints, defaults, FK targets, indexes, identity,
privileges, unexpected triggers/RLS or prerequisites fail closed. No DROP/down
migration is included. Disable the feature to roll back application use and keep
audit/data; detailed operator steps are in the runbook.

003 SQL grants only USAGE on the new schema, SELECT/INSERT on the new table and
USAGE/SELECT on its identity sequence to a supplied existing non-superuser role.
It creates no role, grants no UPDATE/DELETE, changes no public-table grants and
revokes nothing. Existing backend public SELECT/source UPDATE/history INSERT
privileges are prerequisites and are checked by verification under the actual role.

Endpoint implementation
-------------------------

All routes retain JWT/body/query validation. POST objects are at most 16 KiB;
strict positive 32-bit input IDs, unknown fields and attribution spoofing are
checked. Existing routes and app registrations are unchanged by this follow-up.

POST /api/mapping/map-category
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Bearer auth, existing user and MAPPING_APPROVER_IDS are required (empty default
denies). Cookie-only approval is rejected. Existing mapping_id/master_category_id
and exact source-tuple manual approval, hierarchy checks, source row locking,
history, idempotency and approved-target protection remain backward compatible.

New association request::

    {"business_category_id":1,"business_subcategory_id":2,
     "product_category_ids":[101,102],"mapping_type":"carries_products"}

Accepts 1..100 strict IDs; deduplicates while preserving order. Validates active
level-1 business root, direct active level-2 child, all product IDs and valid
product ancestor chains/levels/marketplaces before any insert. Locks the business
root and shares locks on subcategory, selected products and product ancestors.
SQLite uses BEGIN IMMEDIATE instead. PostgreSQL new write transactions use a
two-second lock timeout and ten-second statement timeout.

All associations and actor-attributed BUSINESS_PRODUCT_MAPPED audit rows flush
and commit atomically. PostgreSQL timestamps are aware server timestamps; audit
mapping_id stays NULL so no product association is misrepresented as a source FK.
Audit new_value carries association/business/subcategory/product IDs/type/status.
Repeated associations preserve approver/history; requests add rather than remove
existing products. Responses retain status/changed/data and include associations,
saved, skipped, duplicates_ignored and storage. PostgreSQL storage is
postgresql.category_mapping; SQLite storage remains local_sqlite_only. Conflict
or contention rolls back; complete-request retry may be required.

GET /api/mapping/categories
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

source_categories and canonical_categories retain their envelopes/filters.
product_service_categories returns actual product catalog fields plus a deepest
available display name in the same data/count/pages/current_page/limit envelope.
Options: product_page (1..100000, default 1), product_limit (1..200, default 50),
product_search (case-insensitive literal substring, max 255, wildcards escaped),
marketplace_name (exact, max 100), product_parent_id (positive ID or root), and
product_level (1..10). Product/source/canonical pages are independent. GET writes
nothing; up to six queries including counts. Separate business option sections
remain null; local reviewed business hierarchy IDs come from canonical_categories.

POST /api/mapping/auto-map
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Default dry_run=true writes nothing. Suggestions retain >=80% similarity and a
five-point ambiguity margin, bounds 25 default/50 max, after_id cursor, platform
filter, and fail-closed catalog caps of 2000 active nodes/5000 synonyms.

dry_run=false additionally requires Bearer auth, existing user and MAPPING_ADMIN_IDS
(empty default denies); approver membership alone is insufficient. Only active,
PENDING/UNMAPPED unassigned source rows can be saved. Non-ambiguous targets need
UNROUNDED >=0.9 confidence and valid active ancestry. Display rounding is never
used for acceptance. Exact 0.9 passes; 0.8999996 displays as 0.9 but does not save.

PostgreSQL uses FOR UPDATE OF source rows plus shared taxonomy locks. SQLite
reserves its writer. Changes and AUTO_MAPPED audit rows commit together. Existing
or manually approved assignments are excluded; repeats do not repeat history.
summary reports saved/skipped/failed/ambiguous, per-row outcome/persistence_reason,
persistence_threshold and transaction_failed. Commit/audit failure rolls back all
planned writes and returns HTTP 500 with saved=0 and affected rows failed. Fuzzy
source matching never creates business/product associations.

Actual verification
---------------------

Working directory: the C: feature worktree above. Existing interpreter:
..\HBD_Dashboard_automation\venv\Scripts\python.exe.

Offline SQLite command::

    & '..\HBD_Dashboard_automation\venv\Scripts\python.exe' -m unittest discover -s backend/tests -p 'test_mapping*.py' -v

Actual disposable PostgreSQL command::

    & '..\HBD_Dashboard_automation\venv\Scripts\python.exe' backend/tests/run_mapping_postgres.py --postgres-bin 'D:\PostgresSQL\bin'

Offline demo::

    & '..\HBD_Dashboard_automation\venv\Scripts\python.exe' backend/tests/demo_mapping_api.py

Final passing suites: 79 SQLite tests in 3.498s and 27 actual PostgreSQL
integration tests in 7.587s; zero final failures/errors/skips. PostgreSQL version: 18.7 on Windows. These are
real local PostgreSQL results, NOT company staging/prod verification.

The runner creates an owned temporary cluster/database bg111_test_* on a random
loopback port with generated temporary credentials; it does not use existing
servers, services, .env or company DSNs. It reproduces the verified public/silver
metadata with synthetic rows only. SQL install/rerun, grants, metadata scripts,
CLI inspect/verify/apply/default deny, actual constraints and sequence/timezone,
API authorization, pagination/search, threshold/ambiguity/manual protection,
concurrent approvals/auto-map, product-parent share locks and mapping/audit rollback
are exercised. The server stops and owned temporary data/auth files are removed
in finally, including failure paths.

Development verification history: initial local launcher attempts required fixes
for Windows inherited pipe handles and CREATE DATABASE transaction handling.
An initial 23-case fixture run had 23 endpoint-assertion errors (inet text mask);
a later interrupted run had 1 assertion failure and 13 errors from fixture
transaction/teardown handling. These were corrected without company access.
The complete 23-case run then passed, followed by a 27-case extended passing run.
Final verification timings/counts are recorded in the delivery report. Negative
test logs intentionally simulate rollback failures; datetime.utcnow warnings
come from existing models. No new dependencies were installed.

Complete review files
-----------------------

Modified from fa346f0:

* backend/config.py
* backend/routes/mapping_routes.py
* backend/services/mapping_service.py
* backend/tests/test_mapping_api.py
* backend/tests/demo_mapping_api.py
* docs/BG-1.11-HANDOVER.rst

New review sources:

* backend/model/business_product_category_mapping.py
* backend/model/product_category.py
* backend/services/mapping_schema.py
* backend/scripts/bg111_postgres.py
* backend/sql/bg111/.gitignore
* backend/sql/bg111/001_create_relationships.sql
* backend/sql/bg111/002_inspect_relationships.sql
* backend/sql/bg111/003_application_permissions.sql
* backend/tests/test_mapping_local.py
* backend/tests/test_bg111_postgres.py
* backend/tests/run_mapping_postgres.py
* docs/BG-1.11-SCHEMA-INSPECTION.rst
* docs/BG-1.11-SCHEMA-METADATA.json
* docs/BG-1.11-POSTGRES-RUNBOOK.rst
* docs/BG-1.11-PR-UPDATE.txt

Generated scratch/bg-1.11-local.sqlite3 and bytecode caches remain Git-ignored.
The synthetic SQLite snapshot from 23 November is preserved. No .env, credentials,
frontend, scraper/scheduler, unrelated model or zepto_routes.py changes are included.

Remaining deployment review
----------------------------

Company schema installation, grants and application writes are deliberately NOT
performed. The DBA must approve the separate namespace/contract and actual taxonomy
IDs, select a non-production target/profile and application role, run verify,
install/grant with explicit flags, verify as the application role, and configure
approved existing approver/admin IDs before a staged smoke test. Production remains
outside this task. The existing silver relation needs no alteration for this design.

Actual company taxonomy provenance, existing schema/model drift and legacy category
routes with weaker authorization remain pre-existing review concerns. Test catalog
sizes are synthetic; evaluate actual query/index performance and existing backend
startup/ETL behavior separately. The tests execute real selected registration/auth
code in a safe harness; full app.py startup and frontend integration were not run.
No claim of production readiness or guaranteed merge approval is made.

Proposed commit message after explicit user approval::

    feat(BG-1.11): add guarded PostgreSQL mapping package and integration tests

PR 29 stays Draft. The user authorized a description update for the prepared
local package, but code remains unpublished until explicit commit/push approval.
No new PR, merge, deployment or remote code/branch change is authorized/performed.
