-- Metadata only. Safe to run without enabling installation or application writes.
BEGIN TRANSACTION READ ONLY;
SET LOCAL statement_timeout = '5s';
SET LOCAL lock_timeout = '2s';
SELECT current_database() AS database_name, current_user AS user_name,
       current_setting('transaction_read_only') AS read_only,
       to_regclass('category_mapping.business_product_category_mappings') AS proposed_relation,
       to_regclass('silver_clean.business_product_category_mappings') AS legacy_relation;
SELECT n.nspname AS schema_name, t.relname AS table_name, a.attname AS column_name,
       format_type(a.atttypid,a.atttypmod) AS data_type, NOT a.attnotnull AS nullable,
       pg_get_expr(d.adbin,d.adrelid) AS column_default, a.attidentity AS identity_kind
FROM pg_class t JOIN pg_namespace n ON n.oid=t.relnamespace
JOIN pg_attribute a ON a.attrelid=t.oid
LEFT JOIN pg_attrdef d ON d.adrelid=a.attrelid AND d.adnum=a.attnum
WHERE (n.nspname,t.relname) IN
  (('category_mapping','business_product_category_mappings'),('silver_clean','business_product_category_mappings'))
  AND a.attnum>0 AND NOT a.attisdropped ORDER BY n.nspname,a.attnum;
SELECT conname, contype, convalidated, pg_get_constraintdef(oid,true) AS definition
FROM pg_constraint WHERE conrelid=to_regclass('category_mapping.business_product_category_mappings') ORDER BY conname;
SELECT indexname,indexdef FROM pg_indexes
WHERE schemaname='category_mapping' AND tablename='business_product_category_mappings' ORDER BY indexname;
ROLLBACK;
