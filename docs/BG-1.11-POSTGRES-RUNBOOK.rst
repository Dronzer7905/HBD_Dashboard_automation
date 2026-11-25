Publication note - 25 November 2026
==================================

Historical BG-1.11 delivery record follows. PR 29 has since been closed without
merge. The user reports the ZIP was applied by the team and has explicitly
authorized a new non-draft ingestion PR. This branch imports the shipped sources
because GitHub main lacked them. Current delivery/test/deployment qualifications
are in docs/BG-1.13-INGESTION-HANDOVER.rst; they supersede historical publication
status below. Company database access is currently revoked; its installation
has not been independently reverified today.

BG-1.11 PostgreSQL operator runbook
===================================

24 November 2026. Prepared for team lead and DBA review. This is a reviewed source
package for isolated local or approved staging PostgreSQL. It has NOT been run
against a company database for installation, grants, application writes or tests.

Design decision
---------------

The verified silver_clean.business_product_category_mappings table uses raw
strings and a text product target and lacks the six reviewed relationship fields.
Do not alter, rename, reinterpret, migrate or backfill that table with this package.
The proposed normalized contract is installed separately at:

    category_mapping.business_product_category_mappings

Business root/subcategory IDs reference public.master_categories.id. Product IDs
reference public.product_category_master.id. Approver IDs reference public.users.id.
These integer PK types were verified against the company metadata. Confirm that
the selected master taxonomy IDs are the intended business hierarchy before
turning on any application writes. No company data is imported by these scripts.

Exact package components
------------------------

* backend/sql/bg111/001_create_relationships.sql: explicit transactional install,
  prerequisites, exact column/key/FK/check assertions, identity and lookup indexes.
* backend/sql/bg111/002_inspect_relationships.sql: BEGIN READ ONLY catalog-only
  comparison of the new schema and existing silver table, with short timeouts.
* backend/sql/bg111/003_application_permissions.sql: explicitly confirmed grants
  on the NEW schema/table/identity sequence only, to an existing non-superuser role.
* backend/scripts/bg111_postgres.py: inspect, verify, apply and grant commands.
  Imports neither app nor config/.env. Uses normal libpq authentication.
* backend/services/mapping_schema.py: shared metadata/privilege contract verifier.
* backend/tests/run_mapping_postgres.py: self-contained disposable PostgreSQL runner.
* backend/tests/test_bg111_postgres.py: actual PostgreSQL API/SQL/concurrency tests.

The nested .gitignore explicitly includes the SQL source files; the repository's
root *.sql rule otherwise hides them. No git add or force-add is required for
review, and no index operation was performed.

Connection authentication
--------------------------

Use an existing approved libpq PGSERVICE profile or PGHOST, PGPORT, PGDATABASE,
PGUSER, PGPASSFILE and PGSSLMODE configuration. Never put a password or a URI
containing credentials in scripts, command arguments, review comments or Git.
A DBA must supply the actual approved non-production target/profile and role.
Do not copy company data or credentials into the disposable local test cluster.

Every CLI action requires --expected-database. It checks current_database() before
writing. Its connections default to read-only with a five-second statement timeout
and two-second lock timeout. inspect and verify remain read-only and end in rollback.
apply and grant require BOTH --environment local|staging and
--allow-nonproduction-write; production is not an accepted environment value.
The guards are operator assertions and configuration checks, not an independent
certificate that a manually selected server is non-production. Use the approved
non-production profile, review it, and retain normal DBA change controls.

Inspection and verification
----------------------------

Run from the feature repository root with the project's existing environment.
On this workstation the verified interpreter is::

    $py = (Resolve-Path '..\HBD_Dashboard_automation\venv\Scripts\python.exe').Path

Select the approved existing libpq service profile and exact database name using
the normal operator configuration process. The following variables are explicit
operator inputs, not credentials::

    $env:PGSERVICE = Read-Host 'Approved nonproduction libpq service profile'
    $targetDb = Read-Host 'Exact approved nonproduction database name'
    & $py backend/scripts/bg111_postgres.py inspect --expected-database $targetDb
    & $py backend/scripts/bg111_postgres.py verify --expected-database $targetDb

inspect exits 0 even if the proposed table is absent; it reports ready=false and
the missing contract. verify exits 2 unless every required column, nullability,
identity, default, validated PK/FK/unique/check, index, trigger/RLS expectation and
current-role prerequisite privilege passes. It never repairs or creates anything.
An access or SQL error exits 1 with a generic error code, not raw SQL parameters.

Install only in an explicitly approved non-production database
--------------------------------------------------------------

A DBA/operator with approved schema creation privileges runs::

    & $py backend/scripts/bg111_postgres.py apply --expected-database $targetDb --environment staging --allow-nonproduction-write
    & $py backend/scripts/bg111_postgres.py verify --expected-database $targetDb

Use --environment local for an isolated local target. apply executes the reviewed
001 SQL without its final COMMIT, runs the shared verifier inside that same
transaction, then commits only on success. On any error it rolls back the complete
installation attempt. A compatible rerun preserves existing associations/audit.
An incompatible table is rejected, not silently adopted, repaired, dropped or
replaced. Existing public IDs must already be integer primary keys. No public or
silver table is altered. The CLI prints the installation SQL SHA-256 for review.

Standalone SQL for pgAdmin or psql
----------------------------------

The complete executable SQL is in the three .sql files; no placeholder fields
need to be substituted within those sources. For standalone 001 execution, set
these session values to the APPROVED literal environment and database first::

    SELECT set_config('bg111.environment', 'staging', false);
    SELECT set_config('bg111.target_database', 'APPROVED_DATABASE_NAME', false);
    SELECT set_config('bg111.confirm_write', 'I_CONFIRM_NON_PRODUCTION', false);

APPROVED_DATABASE_NAME above is an operator-supplied exact target name; it must
match current_database(). Then execute all of 001_create_relationships.sql.
Do not disable ON_ERROR_STOP in psql. After any error issue ROLLBACK and investigate.
Run 002 and the Python verify command before enabling the application. The Python
apply workflow is preferred because it also verifies privileges/index definitions
before commit. Do not use app.py startup or db.create_all as the installer.

Application role grants
-------------------------

Reuse the approved backend application role. It must already have SELECT on users,
master_categories, product_category_master, platform_category_mapping,
category_mapping_history and category_mapping_synonyms, UPDATE on the source bridge,
and INSERT on category_mapping_history. These are existing backend prerequisites.
No additional privileges on public tables are granted by this package.

For the new relationship objects only::

    $applicationRole = Read-Host 'Approved existing backend application role'
    & $py backend/scripts/bg111_postgres.py grant --expected-database $targetDb --environment staging --allow-nonproduction-write --application-role $applicationRole

The grants are schema USAGE; relationship SELECT/INSERT; identity sequence
USAGE/SELECT. UPDATE and DELETE are not granted. No role is created and no existing
privileges are revoked. Existing wider privileges are not removed automatically.
Run verify again under the ACTUAL application role/profile, not only the DBA role.
For raw 003 SQL set bg111.application_role to that existing role name as well.

Application configuration
--------------------------

After installation and verification, configure the existing approved environment
without putting secrets in the repository::

    MAPPING_POSTGRES_ASSOCIATIONS_ENABLED=true
    MAPPING_DEPLOYMENT_ENV=staging
    MAPPING_POSTGRES_DATABASE=<exact approved nonproduction database name>
    MAPPING_APPROVER_IDS=<approved existing user IDs separated by commas>
    MAPPING_ADMIN_IDS=<approved existing administrator IDs separated by commas>

Values in angle brackets are deployment-specific operator inputs. Empty/default
allowlists deny writes. dry_run=false requires Bearer authentication and the admin
allowlist; approver membership alone is insufficient. Association writes require
the feature flag, PostgreSQL dialect, local/staging environment, exact configured
connection database name and verified installed schema/privileges. Wrong schema
returns schema_not_ready; disabled storage returns local_associations_disabled.
The original SQLite flag remains available for the isolated synthetic prototype.

PostgreSQL ORM metadata is separate from the application schema registry, and its
before_create guard prohibits ORM installation even when the feature is enabled.
New association and bulk write transactions use a two-second lock timeout and a
ten-second statement timeout.
Source locks and category/product shared locks protect validation and persistence;
associations and audit records share one transaction. Busy/conflicting requests
roll back safely and may need a complete-request retry. Existing approved mappings
are not overwritten. Audit attribution always comes from the authorised JWT user.

Exact verification commands already exercised
----------------------------------------------

From the feature worktree, using the interpreter above::

    & $py -m unittest discover -s backend/tests -p 'test_mapping*.py' -v
    & $py backend/tests/run_mapping_postgres.py --postgres-bin 'D:\PostgresSQL\bin'
    & $py backend/tests/demo_mapping_api.py

Results: 79 offline SQLite tests and 27 actual PostgreSQL integration tests passed,
zero final failures/errors/skips. PostgreSQL version tested: 18.7 on Windows.
The PostgreSQL runner requires existing initdb/pg_ctl binaries, starts a NEW
cluster on a random loopback port, generates temporary synthetic-only credentials,
creates only a bg111_test_* database, reproduces verified public metadata and
runs the actual install/verification/API tests. It refuses the company tunnel and
standard shared ports. It never imports .env or reads an existing database DSN.
Its owned server stops and its verified temporary directory/authentication files
are removed on exit, including failure paths. Existing Windows PostgreSQL services
and data directories are not changed. A normal non-root OS user is required.

Disable or roll back application use
------------------------------------

Set MAPPING_POSTGRES_ASSOCIATIONS_ENABLED=false and remove any newly configured
admin/approver IDs through the approved environment configuration process. Keep
the schema, associations and audit history. This is a reversible application
rollback; no DROP, TRUNCATE, data deletion or destructive down migration is supplied.
A DBA should handle any separately approved schema/data recovery using normal
backup/change procedures. Do not repoint the application to the legacy silver
relation as a substitute contract.

Review and publication
------------------------

Local code and SQL are reviewable and tested. No company installation/grants/write
verification, full app startup, frontend integration, production migration or
deployment was performed. Review the actual staging taxonomy, role configuration,
query performance and application integration before deployment approval.
No commit, push, merge, auto-merge, deployment or Ready for Review action is allowed
without the user's later explicit instruction. PR 29 stays Draft. Its description
may record this local/unpublished evidence under the current user authorization;
it must not claim the remote PR already contains these uncommitted files.
