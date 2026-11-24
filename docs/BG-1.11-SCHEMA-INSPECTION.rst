BG-1.11 read-only PostgreSQL schema inspection
============================================

Purpose
-------

Run this in pgAdmin Query Tool connected to the existing Honey Bee Digital
profile, database testpostgrey, user team_dev. Authenticate in the database
client itself. Do not put credentials in this document or returned results.
Run the complete block in a fresh Query Tool without an existing transaction.
Return only the schema_metadata JSON cell. No customer/business rows are read.
If any statement fails, execute ROLLBACK in that Query Tool.

The query inspects the two approved relations, existing category/mapping models,
and up to three levels of their outgoing FK targets. Missing tables remain
explicitly visible. CHECK constraints and enum labels describe allowed values;
if neither constrains status/mapping_type, metadata cannot establish business
policy. Do not run SELECT DISTINCT on company records to fill that gap.

Every metadata scan is gated to the assigned database and user. A wrong context
returns context_approved=false with empty metadata. This file contains no DDL,
migration, application startup, synchronization, or persistence operation.

SQL for pgAdmin
---------------

.. code-block:: sql

    BEGIN TRANSACTION READ ONLY;
    SET LOCAL statement_timeout = '5s';
    SET LOCAL lock_timeout = '2s';

    WITH RECURSIVE
    context AS (
        SELECT current_database() AS database_name,
               current_user AS user_name,
               current_database() = 'testpostgrey'
                   AND current_user = 'team_dev' AS approved
    ),
    requested(schema_name, table_name) AS (
        VALUES ('silver_clean', 'business_product_category_mappings'),
               ('public', 'product_category_master'),
               ('public', 'master_categories'),
               ('public', 'platform_category_mapping'),
               ('public', 'category_mapping_history'),
               ('public', 'category_mapping_synonyms'),
               ('public', 'users')
    ),
    resolved AS (
        SELECT r.*, to_regclass(format('%I.%I', schema_name, table_name))::oid AS oid
        FROM requested r CROSS JOIN context c
        WHERE c.approved
    ),
    related(oid, depth) AS (
        SELECT oid, 0 FROM resolved WHERE oid IS NOT NULL
        UNION
        SELECT fk.confrelid, r.depth + 1
        FROM related r
        JOIN pg_catalog.pg_constraint fk
          ON fk.conrelid = r.oid AND fk.contype = 'f'
        WHERE r.depth < 3
    ),
    scope AS (SELECT DISTINCT oid FROM related),
    relations AS (
        SELECT c.oid, n.nspname AS schema_name, c.relname AS table_name,
               c.relkind::text AS relation_kind,
               c.relrowsecurity AS row_security,
               pg_catalog.obj_description(c.oid, 'pg_class') AS description
        FROM scope s
        JOIN pg_catalog.pg_class c ON c.oid = s.oid
        JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
    ),
    columns AS (
        SELECT r.schema_name, r.table_name, a.attnum AS ordinal_position,
               a.attname AS column_name,
               pg_catalog.format_type(a.atttypid, a.atttypmod) AS data_type,
               tn.nspname AS type_schema, t.typname AS type_name,
               t.typtype::text AS type_kind,
               NOT a.attnotnull AS is_nullable,
               pg_catalog.pg_get_expr(d.adbin, d.adrelid) AS default_value,
               a.attidentity::text AS identity_kind,
               a.attgenerated::text AS generated_kind,
               pg_catalog.col_description(r.oid, a.attnum) AS description
        FROM relations r
        JOIN pg_catalog.pg_attribute a ON a.attrelid = r.oid
        JOIN pg_catalog.pg_type t ON t.oid = a.atttypid
        JOIN pg_catalog.pg_namespace tn ON tn.oid = t.typnamespace
        LEFT JOIN pg_catalog.pg_attrdef d
          ON d.adrelid = a.attrelid AND d.adnum = a.attnum
        WHERE a.attnum > 0 AND NOT a.attisdropped
    ),
    constraints AS (
        SELECT r.schema_name, r.table_name, c.conname AS constraint_name,
               c.contype::text AS constraint_type,
               pg_catalog.pg_get_constraintdef(c.oid, true) AS definition,
               c.condeferrable AS deferrable, c.condeferred AS initially_deferred,
               c.convalidated AS validated,
               CASE WHEN c.confrelid <> 0
                    THEN c.confrelid::regclass::text END AS referenced_table
        FROM relations r
        JOIN pg_catalog.pg_constraint c ON c.conrelid = r.oid
    ),
    indexes AS (
        SELECT r.schema_name, r.table_name, idx.relname AS index_name,
               i.indisprimary AS is_primary, i.indisunique AS is_unique,
               i.indisvalid AS is_valid,
               pg_catalog.pg_get_indexdef(i.indexrelid) AS definition
        FROM relations r
        JOIN pg_catalog.pg_index i ON i.indrelid = r.oid
        JOIN pg_catalog.pg_class idx ON idx.oid = i.indexrelid
    ),
    types AS (
        SELECT DISTINCT t.oid, t.typbasetype
        FROM relations r
        JOIN pg_catalog.pg_attribute a ON a.attrelid = r.oid
        JOIN pg_catalog.pg_type t ON t.oid = a.atttypid
        WHERE a.attnum > 0 AND NOT a.attisdropped
    ),
    enum_types AS (
        SELECT oid FROM types
        UNION SELECT typbasetype FROM types WHERE typbasetype <> 0
    ),
    enums AS (
        SELECT n.nspname AS type_schema, t.typname AS type_name,
               e.enumlabel AS allowed_value, e.enumsortorder AS sort_order
        FROM enum_types et
        JOIN pg_catalog.pg_type t ON t.oid = et.oid
        JOIN pg_catalog.pg_namespace n ON n.oid = t.typnamespace
        JOIN pg_catalog.pg_enum e ON e.enumtypid = t.oid
    ),
    domains AS (
        SELECT n.nspname AS type_schema, t.typname AS type_name,
               pg_catalog.format_type(t.typbasetype, t.typtypmod) AS base_type,
               t.typnotnull AS not_null, t.typdefault AS default_value,
               c.conname AS constraint_name,
               pg_catalog.pg_get_constraintdef(c.oid, true) AS definition
        FROM types st
        JOIN pg_catalog.pg_type t ON t.oid = st.oid AND t.typtype = 'd'
        JOIN pg_catalog.pg_namespace n ON n.oid = t.typnamespace
        LEFT JOIN pg_catalog.pg_constraint c ON c.contypid = t.oid
    ),
    triggers AS (
        SELECT r.schema_name, r.table_name, t.tgname AS trigger_name,
               t.tgenabled::text AS enabled,
               pg_catalog.pg_get_triggerdef(t.oid, true) AS definition
        FROM relations r
        JOIN pg_catalog.pg_trigger t ON t.tgrelid = r.oid
        WHERE NOT t.tgisinternal
    )
    SELECT jsonb_pretty(jsonb_build_object(
        'database', c.database_name,
        'user', c.user_name,
        'context_approved', c.approved,
        'transaction_read_only', current_setting('transaction_read_only'),
        'statement_timeout', current_setting('statement_timeout'),
        'requested_relations', COALESCE((
            SELECT jsonb_agg(jsonb_build_object(
                'schema', schema_name, 'table', table_name,
                'exists', oid IS NOT NULL) ORDER BY schema_name, table_name)
            FROM resolved), '[]'::jsonb),
        'relations', COALESCE((SELECT jsonb_agg(to_jsonb(x) - 'oid'
            ORDER BY x.schema_name, x.table_name) FROM relations x), '[]'::jsonb),
        'columns', COALESCE((SELECT jsonb_agg(to_jsonb(x)
            ORDER BY x.schema_name, x.table_name, x.ordinal_position)
            FROM columns x), '[]'::jsonb),
        'constraints', COALESCE((SELECT jsonb_agg(to_jsonb(x)
            ORDER BY x.schema_name, x.table_name, x.constraint_name)
            FROM constraints x), '[]'::jsonb),
        'indexes', COALESCE((SELECT jsonb_agg(to_jsonb(x)
            ORDER BY x.schema_name, x.table_name, x.index_name)
            FROM indexes x), '[]'::jsonb),
        'enum_values', COALESCE((SELECT jsonb_agg(to_jsonb(x)
            ORDER BY x.type_schema, x.type_name, x.sort_order)
            FROM enums x), '[]'::jsonb),
        'domains', COALESCE((SELECT jsonb_agg(to_jsonb(x)
            ORDER BY x.type_schema, x.type_name, x.constraint_name)
            FROM domains x), '[]'::jsonb),
        'triggers', COALESCE((SELECT jsonb_agg(to_jsonb(x)
            ORDER BY x.schema_name, x.table_name, x.trigger_name)
            FROM triggers x), '[]'::jsonb)
    )) AS schema_metadata
    FROM context c;

    ROLLBACK;
