"""Metadata-only verifier shared by the operator CLI and PostgreSQL feature gate.

No application/config/model imports, DDL, row reads, or implicit schema repair.
"""
import re

RELATION = 'category_mapping.business_product_category_mappings'
EXPECTED_COLUMNS = [
    ('id', 'bigint'), ('business_category_id', 'integer'), ('business_subcategory_id', 'integer'),
    ('product_category_id', 'integer'), ('mapping_type', 'character varying(40)'),
    ('status', 'character varying(30)'), ('approved_by_user_id', 'integer'),
    ('created_at', 'timestamp with time zone'),
]


class SchemaContractError(ValueError):
    pass


def rows(connection, statement, parameters=()):
    with connection.cursor() as cursor:
        cursor.execute(statement, parameters)
        columns = [column.name for column in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]


def inspect_contract(connection):
    context = rows(connection, "SELECT current_database() AS database, current_user AS actor, "
                   "current_setting('transaction_read_only') AS read_only, "
                   "to_regclass(%s)::text AS relation", (RELATION,))[0]
    evidence = {'context': context, 'columns': [], 'constraints': [], 'indexes': [], 'errors': []}
    if context['relation'] is None:
        evidence['errors'].append('Reviewed relationship table is not installed')
        evidence['ready'] = False
        return evidence
    evidence['columns'] = rows(connection, """
        SELECT a.attname AS name, format_type(a.atttypid,a.atttypmod) AS type,
               a.attnotnull AS not_null, a.attidentity AS identity,
               pg_get_expr(d.adbin,d.adrelid) AS default_value
        FROM pg_attribute a LEFT JOIN pg_attrdef d ON d.adrelid=a.attrelid AND d.adnum=a.attnum
        WHERE a.attrelid=to_regclass(%s) AND a.attnum>0 AND NOT a.attisdropped
        ORDER BY a.attnum LIMIT 65
    """, (RELATION,))
    actual = [(column['name'], column['type']) for column in evidence['columns']]
    if actual != EXPECTED_COLUMNS or not all(column['not_null'] for column in evidence['columns']):
        evidence['errors'].append('Column names/types/nullability differ from the reviewed contract')
        evidence['ready'] = False
        return evidence
    if not evidence['columns'] or evidence['columns'][0]['identity'] not in ('a', 'd'):
        evidence['errors'].append('Identity primary-key generation is missing')
    defaults = {item['name']: item['default_value'] for item in evidence['columns']}
    for name, literal in [('mapping_type', "'carries_products'"), ('status', "'APPROVED'")]:
        if (defaults.get(name) or '').replace('::character varying', '') != literal:
            evidence['errors'].append('Required default differs: ' + name)
    if defaults.get('created_at') != 'now()':
        evidence['errors'].append('Required timestamp default differs')
    protection = rows(connection, '''SELECT c.relrowsecurity AS rls,
        EXISTS(SELECT 1 FROM pg_trigger t WHERE t.tgrelid=c.oid AND NOT t.tgisinternal) AS custom_triggers
        FROM pg_class c WHERE c.oid=to_regclass(%s)''', (RELATION,))[0]
    if protection['rls'] or protection['custom_triggers']:
        evidence['errors'].append('Unexpected row-security policy or user trigger requires review')
    evidence['constraints'] = rows(connection, """
        SELECT c.conname AS name, c.contype AS kind, c.convalidated AS validated,
               c.condeferrable AS deferrable, c.confdeltype AS on_delete,
               ARRAY(SELECT a.attname FROM unnest(c.conkey) WITH ORDINALITY AS k(num,ord)
                     JOIN pg_attribute a ON a.attrelid=c.conrelid AND a.attnum=k.num ORDER BY k.ord) AS columns,
               CASE WHEN c.confrelid<>0 THEN (SELECT n.nspname || '.' || t.relname FROM pg_class t
                 JOIN pg_namespace n ON n.oid=t.relnamespace WHERE t.oid=c.confrelid) END AS referenced,
               ARRAY(SELECT a.attname FROM unnest(c.confkey) WITH ORDINALITY AS k(num,ord)
                     JOIN pg_attribute a ON a.attrelid=c.confrelid AND a.attnum=k.num ORDER BY k.ord) AS referenced_columns,
               pg_get_expr(c.conbin,c.conrelid) AS expression
        FROM pg_constraint c WHERE c.conrelid=to_regclass(%s) ORDER BY c.conname LIMIT 65
    """, (RELATION,))
    constraints = {item['name']: item for item in evidence['constraints']}
    expected = {
        'pk_bpcm': ('p', ['id'], None),
        'uq_bpcm_relationship': ('u', ['business_category_id', 'business_subcategory_id', 'product_category_id', 'mapping_type'], None),
        'fk_bpcm_business': ('f', ['business_category_id'], 'master_categories'),
        'fk_bpcm_subcategory': ('f', ['business_subcategory_id'], 'master_categories'),
        'fk_bpcm_product': ('f', ['product_category_id'], 'product_category_master'),
        'fk_bpcm_approver': ('f', ['approved_by_user_id'], 'users'),
    }
    for name, (kind, columns, target) in expected.items():
        item = constraints.get(name)
        if (item is None or item['kind'] != kind or item['columns'] != columns
                or not item['validated'] or item['deferrable']):
            evidence['errors'].append('Required key/constraint differs: ' + name)
        elif target and (item['referenced'] != 'public.' + target
                         or item['referenced_columns'] != ['id'] or item['on_delete'] != 'r'):
            evidence['errors'].append('Foreign-key target/delete policy differs: ' + name)
    for name, expression in [('ck_bpcm_type', "mapping_type='carries_products'"),
                              ('ck_bpcm_status', "status='APPROVED'")]:
        item = constraints.get(name)
        normalized = re.sub(r'[\s()]', '', ((item or {}).get('expression') or '').replace('::text', ''))
        if item is None or item['kind'] != 'c' or not item['validated'] or normalized != expression:
            evidence['errors'].append('Required check constraint differs: ' + name)
    evidence['indexes'] = rows(connection, """
        SELECT idx.relname AS name, i.indisvalid AS valid, (i.indpred IS NULL AND i.indexprs IS NULL) AS not_partial,
               ARRAY(SELECT a.attname FROM unnest(i.indkey::smallint[]) WITH ORDINALITY AS k(num,ord)
                     JOIN pg_attribute a ON a.attrelid=i.indrelid AND a.attnum=k.num ORDER BY k.ord) AS columns
        FROM pg_index i JOIN pg_class idx ON idx.oid=i.indexrelid
        WHERE i.indrelid=to_regclass(%s) ORDER BY idx.relname LIMIT 65
    """, (RELATION,))
    indexes = {item['name']: item for item in evidence['indexes']}
    for name, column in [('ix_bpcm_subcategory','business_subcategory_id'),
                         ('ix_bpcm_product','product_category_id'), ('ix_bpcm_approver','approved_by_user_id')]:
        item = indexes.get(name)
        if item is None or not item['valid'] or not item['not_partial'] or item['columns'] != [column]:
            evidence['errors'].append('Required index differs: ' + name)
    evidence['privileges'] = rows(connection, """
        SELECT has_schema_privilege(current_user,'category_mapping','USAGE') AS schema_usage,
               (has_table_privilege(current_user,%s,'SELECT') AND
                has_table_privilege(current_user,%s,'INSERT')) AS relationship_access,
               has_sequence_privilege(current_user,pg_get_serial_sequence(%s,'id'),'USAGE') AS sequence_usage
    """, (RELATION, RELATION, RELATION))[0]
    if not all(evidence['privileges'].values()):
        evidence['errors'].append('Current role lacks schema/table/identity privileges')
    evidence['public_privileges'] = rows(connection, '''
        SELECT name AS relation,
               has_table_privilege(current_user,to_regclass('public.' || name),'SELECT') AS can_select,
               CASE WHEN name='platform_category_mapping'
                    THEN has_table_privilege(current_user,to_regclass('public.' || name),'UPDATE')
                    WHEN name='category_mapping_history'
                    THEN has_table_privilege(current_user,to_regclass('public.' || name),'INSERT')
                    ELSE true END AS required_write
        FROM unnest(ARRAY['users','master_categories','product_category_master',
             'platform_category_mapping','category_mapping_history','category_mapping_synonyms']) AS required(name)
        ORDER BY name
    ''')
    if not all(item['can_select'] and item['required_write'] for item in evidence['public_privileges']):
        evidence['errors'].append('Existing backend public table privileges/prerequisites are missing')
    if len(evidence['constraints']) >= 65 or len(evidence['indexes']) >= 65:
        evidence['errors'].append('Schema metadata exceeds the safety limit')
    evidence['ready'] = not evidence['errors']
    return evidence


def verify_contract(connection):
    evidence = inspect_contract(connection)
    if not evidence['ready']:
        raise SchemaContractError('; '.join(evidence['errors']))
    return evidence
