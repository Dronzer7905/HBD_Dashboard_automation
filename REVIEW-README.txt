BG-1.11 PostgreSQL review package - 24 November 2026

Review source changes over existing feature checkout fa346f0. This is a source
update package, not a standalone application or a database backup.
Start with docs/BG-1.11-POSTGRES-RUNBOOK.rst and docs/BG-1.11-HANDOVER.rst.
SQL: backend/sql/bg111/001_create_relationships.sql, 002_inspect_relationships.sql,
and 003_application_permissions.sql. CLI: backend/scripts/bg111_postgres.py.

79 SQLite tests and 27 actual local PostgreSQL tests passed. Company access was
metadata-only and read-only. No company schema, data or grants were changed.
PR 29 stays Draft at fa346f0; its updated description labels this code local and
unpublished. All sources remain unstaged. No commit, push, merge or deployment.
No credentials, environment files, binary databases, dependencies or Git internals
are included. See REVIEW-MANIFEST.json for each source file SHA-256.
