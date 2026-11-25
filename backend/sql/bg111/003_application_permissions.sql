-- OPERATOR RUN ONLY. Existing app role; new relationship objects only.
-- Also set bg111.application_role to the approved existing role name.
BEGIN READ WRITE;
SET LOCAL statement_timeout='10s';
SET LOCAL lock_timeout='2s';
DO $permissions$
DECLARE app_role text := current_setting('bg111.application_role',true);
identity_sequence regclass;
BEGIN
  IF current_setting('bg111.environment',true) IS NULL
     OR current_setting('bg111.environment',true) NOT IN ('local','staging')
     OR current_setting('bg111.target_database',true) IS DISTINCT FROM current_database()
     OR current_setting('bg111.confirm_write',true) IS DISTINCT FROM 'I_CONFIRM_NON_PRODUCTION' THEN
    RAISE EXCEPTION 'BG111 permissions require explicit non-production target and write confirmation';
  END IF;
  IF app_role IS NULL OR NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname=app_role AND NOT rolsuper) THEN
    RAISE EXCEPTION 'Choose an approved existing non-superuser application role';
  END IF;
  identity_sequence := pg_get_serial_sequence('category_mapping.business_product_category_mappings','id')::regclass;
  IF identity_sequence IS NULL THEN RAISE EXCEPTION 'Relationship identity sequence is missing'; END IF;
  EXECUTE format('GRANT USAGE ON SCHEMA category_mapping TO %I',app_role);
  EXECUTE format('GRANT SELECT, INSERT ON TABLE category_mapping.business_product_category_mappings TO %I',app_role);
  EXECUTE format('GRANT USAGE, SELECT ON SEQUENCE %s TO %I',identity_sequence,app_role);
END
$permissions$;
COMMIT;
