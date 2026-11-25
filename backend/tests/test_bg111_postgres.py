"""Actual PostgreSQL integration tests; only the owned-cluster runner may enable.

No company connection settings, .env imports or shared database credentials.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from unittest.mock import patch

import test_mapping_api as baseline
from flask import Flask
from flask_jwt_extended import create_access_token
from sqlalchemy import event, text
import psycopg2

from extensions import db, jwt
from model.user import User
from model.master_category import MasterCategory
from model.product_category import ProductCategory
from model.platform_category_mapping import PlatformCategoryMapping as Source
from model.category_mapping_history import CategoryMappingHistory as History
from model.business_product_category_mapping import PostgresBusinessProductCategoryMapping as Association
from services import mapping_service as service
from services.mapping_schema import verify_contract, SchemaContractError
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from bg111_postgres import apply_schema, SQL_FILE


@unittest.skipUnless(os.getenv('BG111_PG_TEST_PROFILE'), 'Use run_mapping_postgres.py to create an isolated server')
class PostgresMappingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        profile_path=Path(os.environ['BG111_PG_TEST_PROFILE']).resolve()
        cls.profile=json.loads(profile_path.read_text())
        cls.p=cls.profile
        if not (cls.p.get('owned_cluster') is True and cls.p['host']=='127.0.0.1'
                and cls.p['database'].startswith('bg111_test_')
                and profile_path.parent.name.startswith('bg111-owned-pg-')
                and cls.p['port'] not in (5432,5433,15432,15434)):
            raise RuntimeError('Refusing a non-owned/shared PostgreSQL test target')
        cls.uri=f"postgresql+psycopg2://{cls.p['user']}@127.0.0.1:{cls.p['port']}/{cls.p['database']}"

    @classmethod
    @contextmanager
    def connection(cls):
        connection=psycopg2.connect(host='127.0.0.1',port=cls.p['port'],user=cls.p['user'],
                   dbname=cls.p['database'],passfile=cls.p['passfile'],sslmode='disable',connect_timeout=5,
                   options='-c statement_timeout=8000 -c lock_timeout=2000')
        connection.autocommit=True
        with connection.cursor() as cursor:
            cursor.execute('SELECT current_database(), host(inet_server_addr()), inet_server_port()')
            if cursor.fetchone() != (cls.p['database'],'127.0.0.1',cls.p['port']):
                connection.close(); raise RuntimeError('Unexpected test database endpoint')
        try:
            yield connection
        finally:
            connection.close()

    def setUp(self):
        self.app=Flask(__name__)
        self.app.config.update(TESTING=True,SQLALCHEMY_DATABASE_URI=self.uri,
             SQLALCHEMY_TRACK_MODIFICATIONS=False,
             SQLALCHEMY_ENGINE_OPTIONS={'connect_args':{'options':'-c statement_timeout=8000 -c lock_timeout=2000'}},
             JWT_SECRET_KEY='isolated-postgres-test-only-key-at-least-32-bytes',
             JWT_TOKEN_LOCATION=['headers','cookies'],JWT_COOKIE_CSRF_PROTECT=False,
             MAPPING_APPROVER_IDS='1',MAPPING_ADMIN_IDS='1',
             MAPPING_POSTGRES_ASSOCIATIONS_ENABLED=True,MAPPING_DEPLOYMENT_ENV='local',
             MAPPING_POSTGRES_DATABASE=self.p['database'])
        db.init_app(self.app); jwt.init_app(self.app); baseline.install_app_registration(self.app)
        self.context=self.app.app_context(); self.context.push()
        self.addCleanup(self.context.pop)
        self.addCleanup(db.engine.dispose)
        self.addCleanup(db.session.remove)
        # This endpoint/database was created by the runner and verified above.
        with self.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute('TRUNCATE category_mapping.business_product_category_mappings, '
                  'public.category_mapping_history,public.platform_category_mapping,public.category_mapping_synonyms,'
                  'public.master_categories,public.product_category_master,public.users RESTART IDENTITY CASCADE')
        db.session.add_all([User(id=1,email='approver@example.test',password='synthetic-unused'),
             User(id=2,email='viewer@example.test',password='synthetic-unused'),
             MasterCategory(id=1,name='Shopping',level=1,path='Shopping',is_active=True),
             MasterCategory(id=4,name='Services',level=1,path='Services',is_active=True)])
        db.session.flush()
        db.session.add_all([MasterCategory(id=2,name='Kirana Stores',parent_id=1,level=2,path='Shopping > Kirana Stores',is_active=True),
             MasterCategory(id=3,name='Dairy Products',parent_id=1,level=2,path='Shopping > Dairy Products',is_active=True),
             ProductCategory(id=101,marketplace_name='Synthetic',category_name='Rice',category_level=1,category_path='Rice'),
             ProductCategory(id=102,marketplace_name='Synthetic',category_name='Tea',category_level=1,category_path='Tea'),
             ProductCategory(id=103,marketplace_name='Synthetic',category_name='Rice',subcategory_name='Packaged Rice',
                             parent_id=101,category_level=2,category_path='Rice > Packaged Rice'),
             Source(platform_name='Synthetic',platform_category_raw='kirana stores',platform_subcategory_raw='',mapping_status='PENDING'),
             Source(platform_name='Other',platform_category_raw='Unrelated Quasar',platform_subcategory_raw='',mapping_status='UNMAPPED')])
        db.session.commit()
        self.headers={'Authorization':'Bearer '+create_access_token(identity='1')}
        self.viewer={'Authorization':'Bearer '+create_access_token(identity='2')}
        self.client=self.app.test_client()

    def payload(self, products=None, **changes):
        data=dict(business_category_id=1,business_subcategory_id=2,
                  product_category_ids=[101,102] if products is None else products,mapping_type='carries_products')
        data.update(changes); return data

    def post(self, endpoint='map-category', data=None, headers=None):
        return self.client.post('/api/mapping/'+endpoint,json=self.payload() if data is None else data,
                               headers=self.headers if headers is None else headers)

    def count(self, model):
        return db.session.query(model).count()

    def test_install_contract_identity_fk_and_indexes(self):
        with self.connection() as connection:
            contract=verify_contract(connection)
        self.assertTrue(contract['ready'])
        self.assertEqual(len([c for c in contract['constraints'] if c['kind']=='f']),4)
        self.assertEqual(contract['columns'][0]['type'],'bigint')
        self.assertEqual(contract['columns'][-1]['type'],'timestamp with time zone')
        self.assertNotIn(Association.__table__,db.metadata.tables.values())

    def test_multiple_products_real_commit_and_timezone(self):
        result=self.post()
        self.assertEqual(result.status_code,200,result.json)
        self.assertEqual(result.json['data']['storage'],'postgresql.category_mapping')
        self.assertEqual(result.json['data']['saved'],2)
        self.assertEqual((self.count(Association),self.count(History)),(2,2))
        association=db.session.query(Association).first()
        self.assertIsNotNone(association.created_at.tzinfo)
        self.assertEqual(association.approved_by_user_id,1)
        audit=History.query.first()
        self.assertIsNone(audit.mapping_id)
        self.assertIn('association_id=',audit.new_value)

    def test_single_duplicate_and_repeat_idempotency(self):
        result=self.post(data=self.payload([101,101]))
        self.assertEqual(result.json['data']['duplicates_ignored'],1)
        repeat=self.post(data=self.payload([101]))
        self.assertFalse(repeat.json['changed'])
        self.assertEqual((self.count(Association),self.count(History)),(1,1))

    def test_invalid_id_parent_and_payload_leave_zero_rows(self):
        for payload,status in [(self.payload([101,999]),404),
                               (self.payload(business_category_id=4),422),
                               (self.payload(approved_by_user_id=2),400)]:
            response=self.post(data=payload)
            self.assertEqual(response.status_code,status,response.json)
            self.assertEqual((self.count(Association),self.count(History)),(0,0))

    def test_product_parent_validation(self):
        product=db.session.get(ProductCategory,103); product.parent_id=999; db.session.commit()
        self.assertEqual(self.post(data=self.payload([101,103])).status_code,422)
        self.assertEqual(self.count(Association),0)

    def test_permission_and_cookie_only_denial(self):
        self.assertEqual(self.post(headers=self.viewer).status_code,403)
        self.client.set_cookie('access_token_cookie',create_access_token(identity='1'))
        self.assertEqual(self.post(headers={}).status_code,401)
        self.assertEqual(self.post('auto-map',dict(dry_run=False),self.viewer).status_code,403)

    def test_feature_environment_and_database_fail_closed(self):
        for key,value in [('MAPPING_POSTGRES_ASSOCIATIONS_ENABLED',False),
                          ('MAPPING_DEPLOYMENT_ENV','production'),('MAPPING_POSTGRES_DATABASE','wrong_database')]:
            original=self.app.config[key]; self.app.config[key]=value
            try:
                self.assertEqual(self.post().json['code'],'local_associations_disabled')
            finally:
                self.app.config[key]=original
        self.assertEqual(self.count(Association),0)

    def test_real_unique_fk_and_check_constraints(self):
        self.post(data=self.payload([101]))
        with self.connection() as connection:
            for product,kind,status,expected in [(101,'carries_products','APPROVED','23505'),
               (999,'carries_products','APPROVED','23503'),(102,'unsupported','APPROVED','23514'),
               (102,'carries_products','PENDING','23514')]:
                with self.assertRaises(psycopg2.Error) as error:
                    with connection.cursor() as cursor:
                        cursor.execute('INSERT INTO category_mapping.business_product_category_mappings '
                          '(business_category_id,business_subcategory_id,product_category_id,mapping_type,status,approved_by_user_id) '
                          'VALUES (1,2,%s,%s,%s,1)',(product,kind,status))
                self.assertEqual(error.exception.pgcode,expected)

    def test_approver_delete_restricted(self):
        self.post(data=self.payload([101])); db.session.remove()
        with self.connection() as connection:
            with self.assertRaises(psycopg2.Error) as error:
                with connection.cursor() as cursor: cursor.execute('DELETE FROM public.users WHERE id=1')
            self.assertEqual(error.exception.pgcode,'23001')

    def test_audit_failure_rolls_back_real_flushed_associations(self):
        count=0
        def fail(mapper,connection,target):
            nonlocal count
            count+=1
            if count==2: raise RuntimeError('synthetic audit failure')
        event.listen(History,'before_insert',fail)
        try: result=self.post()
        finally: event.remove(History,'before_insert',fail)
        self.assertEqual(result.status_code,500)
        self.assertEqual((self.count(Association),self.count(History)),(0,0))

    def test_commit_failure_rolls_back_real_associations(self):
        with patch.object(db.session,'commit',side_effect=RuntimeError('synthetic private failure')):
            result=self.post()
        self.assertEqual(result.status_code,500)
        self.assertNotIn('private',str(result.json))
        self.assertEqual((self.count(Association),self.count(History)),(0,0))

    def concurrent(self,endpoint,payload):
        db.session.remove(); barrier=threading.Barrier(2)
        def submit():
            with self.app.test_client() as client:
                barrier.wait(timeout=10)
                response=client.post('/api/mapping/'+endpoint,json=payload,headers=self.headers)
                return response.status_code,response.json
        with ThreadPoolExecutor(max_workers=2) as executor:
            results=list(executor.map(lambda _:submit(),range(2)))
        self.assertEqual([status for status,_ in results],[200,200],results)
        return results

    def test_concurrent_associations_serialize_and_no_duplicate_audit(self):
        results=self.concurrent('map-category',self.payload([101]))
        self.assertEqual(sorted(body['data']['saved'] for _,body in results),[0,1])
        self.assertEqual((self.count(Association),self.count(History)),(1,1))

    def test_concurrent_auto_map_uses_real_for_update(self):
        results=self.concurrent('auto-map',dict(dry_run=False,platform_name='Synthetic'))
        self.assertEqual(sorted(body['summary']['saved'] for _,body in results),[0,1])
        self.assertEqual(self.count(History),1)
        self.assertEqual(self.count(Association),0)

    def test_product_catalog_pagination_and_case_insensitive_literal_search(self):
        result=self.client.get('/api/mapping/categories?product_limit=1&product_page=2',headers=self.headers)
        self.assertEqual(result.status_code,200,result.json)
        self.assertEqual(result.json['data']['product_service_categories']['data'][0]['id'],102)
        result=self.client.get('/api/mapping/categories?product_search=PACKAGED',headers=self.headers)
        self.assertEqual(result.json['data']['product_service_categories']['total_count'],1)
        result=self.client.get('/api/mapping/categories?product_search=%25',headers=self.headers)
        self.assertEqual(result.json['data']['product_service_categories']['total_count'],0)

    def test_default_dry_run_and_get_issue_zero_dml_or_ddl(self):
        statements=[]
        def capture(*args): statements.append(args[2])
        event.listen(db.engine,'before_cursor_execute',capture)
        try:
            self.post('auto-map',{})
            self.client.get('/api/mapping/categories',headers=self.headers)
        finally: event.remove(db.engine,'before_cursor_execute',capture)
        self.assertFalse(any(s.lstrip().split()[0].upper() in {'INSERT','UPDATE','DELETE','CREATE','ALTER','DROP'} for s in statements))
        self.assertEqual(self.count(History),0)

    def test_auto_map_threshold_ambiguity_idempotency_and_manual_protection(self):
        with patch.object(service,'similarity',side_effect=lambda left,right:0.8999996 if right=='kirana stores' else None):
            result=self.post('auto-map',dict(dry_run=False,platform_name='Synthetic'))
        self.assertEqual(result.json['summary']['saved'],0)
        with patch.object(service,'similarity',side_effect=lambda left,right:0.9 if right=='kirana stores' else None):
            result=self.post('auto-map',dict(dry_run=False,platform_name='Synthetic'))
        self.assertEqual(result.json['summary']['saved'],1)
        self.assertEqual(self.post('auto-map',dict(dry_run=False)).json['summary']['saved'],0)
        self.assertEqual(self.count(History),1)
        self.post('map-category',dict(mapping_id=1,master_category_id=3))
        self.assertEqual(self.post('auto-map',dict(dry_run=False)).json['summary']['saved'],0)
        self.assertEqual(db.session.get(Source,1).master_category_id,3)

    def test_high_confidence_ambiguous_match_not_saved(self):
        db.session.add(MasterCategory(id=6,name='Kirana Stores',parent_id=4,level=2,path='Services > Kirana Stores'))
        db.session.commit()
        result=self.post('auto-map',dict(dry_run=False,platform_name='Synthetic'))
        self.assertEqual(result.json['summary']['ambiguous'],1)
        self.assertEqual(self.count(History),0)

    def test_auto_map_commit_failure_rolls_back_source_and_audit(self):
        with patch.object(db.session,'commit',side_effect=RuntimeError('synthetic failure')):
            result=self.post('auto-map',dict(dry_run=False,platform_name='Synthetic'))
        self.assertEqual(result.status_code,500)
        self.assertEqual(result.json['summary']['saved'],0)
        self.assertEqual(result.json['summary']['failed'],1)
        self.assertIsNone(db.session.get(Source,1).master_category_id)
        self.assertEqual(self.count(History),0)

    def test_install_rerun_preserves_associations_and_silver_schema(self):
        self.post(data=self.payload([101])); db.session.remove()
        with self.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT array_agg(attname ORDER BY attnum) FROM pg_attribute WHERE attrelid='silver_clean.business_product_category_mappings'::regclass AND attnum>0 AND NOT attisdropped")
                before=cursor.fetchone()[0]
            apply_schema(connection,self.p['database'],'local')
            with connection.cursor() as cursor:
                cursor.execute("SELECT array_agg(attname ORDER BY attnum) FROM pg_attribute WHERE attrelid='silver_clean.business_product_category_mappings'::regclass AND attnum>0 AND NOT attisdropped")
                self.assertEqual(cursor.fetchone()[0],before)
        self.assertEqual((self.count(Association),self.count(History)),(1,1))

    def test_raw_sql_without_operator_confirmation_rejected(self):
        with self.connection() as connection:
            with self.assertRaises(psycopg2.Error):
                with connection.cursor() as cursor: cursor.execute(SQL_FILE.read_text())
            with connection.cursor() as cursor: cursor.execute('ROLLBACK')
            self.assertTrue(verify_contract(connection)['ready'])

    def test_wrong_database_apply_is_rejected_before_ddl(self):
        with self.connection() as connection:
            with self.assertRaisesRegex(ValueError,'expected database'):
                apply_schema(connection,'wrong_database','local')
            with self.assertRaisesRegex(ValueError,'non-production'):
                apply_schema(connection,self.p['database'],'production')
            self.assertTrue(verify_contract(connection)['ready'])

    def test_incompatible_named_check_fails_runtime_and_install(self):
        db.session.remove()
        with self.connection() as connection:
            try:
                with connection.cursor() as cursor:
                    cursor.execute("ALTER TABLE category_mapping.business_product_category_mappings DROP CONSTRAINT ck_bpcm_status")
                    cursor.execute("ALTER TABLE category_mapping.business_product_category_mappings ADD CONSTRAINT ck_bpcm_status CHECK (status <> 'INVALID')")
                with self.assertRaises(SchemaContractError): verify_contract(connection)
                result=self.post()
                self.assertEqual((result.status_code,result.json['code']),(422,'schema_not_ready'))
                db.session.remove()
                with self.assertRaises(psycopg2.Error): apply_schema(connection,self.p['database'],'local')
            finally:
                with connection.cursor() as cursor:
                    cursor.execute('ROLLBACK')
                    cursor.execute('ALTER TABLE category_mapping.business_product_category_mappings DROP CONSTRAINT ck_bpcm_status')
                    cursor.execute("ALTER TABLE category_mapping.business_product_category_mappings ADD CONSTRAINT ck_bpcm_status CHECK (status = 'APPROVED')")
            self.assertTrue(verify_contract(connection)['ready'])

    def test_standalone_sql_and_readonly_metadata_script(self):
        with self.connection() as connection:
            for name,value in [('bg111.environment','local'),('bg111.target_database',self.p['database']),
                               ('bg111.confirm_write','I_CONFIRM_NON_PRODUCTION')]:
                with connection.cursor() as cursor: cursor.execute('SELECT set_config(%s,%s,false)',(name,value))
            with connection.cursor() as cursor: cursor.execute(SQL_FILE.read_text())
            self.assertTrue(verify_contract(connection)['ready'])
            with connection.cursor() as cursor:
                cursor.execute((SQL_FILE.parent/'002_inspect_relationships.sql').read_text())
            self.assertTrue(verify_contract(connection)['ready'])

    def test_grants_limit_new_objects_and_verify_missing_public_privileges(self):
        script=Path(__file__).resolve().parents[1]/'scripts/bg111_postgres.py'
        with self.connection() as connection:
            with connection.cursor() as cursor: cursor.execute('CREATE ROLE bg111_test_app NOLOGIN')
        result=subprocess.run([sys.executable,str(script),'grant','--expected-database',self.p['database'],
             '--environment','local','--allow-nonproduction-write','--application-role','bg111_test_app'],
             capture_output=True,text=True,timeout=15)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        with self.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT has_table_privilege('bg111_test_app','category_mapping.business_product_category_mappings','SELECT'),"
                  "has_table_privilege('bg111_test_app','category_mapping.business_product_category_mappings','INSERT'),"
                  "has_table_privilege('bg111_test_app','category_mapping.business_product_category_mappings','UPDATE'),"
                  "has_table_privilege('bg111_test_app','category_mapping.business_product_category_mappings','DELETE')")
                self.assertEqual(cursor.fetchone(),(True,True,False,False))
                cursor.execute('SET ROLE bg111_test_app')
            try:
                with self.assertRaisesRegex(SchemaContractError,'public table privileges'):
                    verify_contract(connection)
            finally:
                with connection.cursor() as cursor: cursor.execute('RESET ROLE')

    def test_product_parent_share_lock_blocks_concurrent_hierarchy_mutation(self):
        outcomes=[]
        def try_mutate(mapper,connection,target):
            with self.connection() as outsider:
                with outsider.cursor() as cursor:
                    cursor.execute("SET lock_timeout='100ms'")
                    try:
                        cursor.execute("UPDATE public.product_category_master SET category_name='Concurrent change' WHERE id=101")
                        outcomes.append('changed')
                    except psycopg2.Error as error: outcomes.append(error.pgcode)
        event.listen(History,'before_insert',try_mutate)
        try: result=self.post(data=self.payload([103]))
        finally: event.remove(History,'before_insert',try_mutate)
        self.assertEqual(result.status_code,200,result.json)
        self.assertEqual(outcomes,['55P03'])
        self.assertEqual(db.session.get(ProductCategory,101).category_name,'Rice')

    def test_operator_cli_apply_success_is_idempotent(self):
        script=Path(__file__).resolve().parents[1]/'scripts/bg111_postgres.py'
        result=subprocess.run([sys.executable,str(script),'apply','--expected-database',self.p['database'],
               '--environment','local','--allow-nonproduction-write'],capture_output=True,text=True,timeout=15)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertTrue(json.loads(result.stdout)['ready'])
        self.assertIn('installation_sha256',json.loads(result.stdout))

    def test_operator_cli_inspect_verify_and_default_write_denial(self):
        script=Path(__file__).resolve().parents[1]/'scripts/bg111_postgres.py'
        for action in ['inspect','verify']:
            result=subprocess.run([sys.executable,str(script),action,'--expected-database',self.p['database']],capture_output=True,text=True,timeout=15)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertTrue(json.loads(result.stdout)['ready'])
            self.assertEqual(json.loads(result.stdout)['context']['read_only'],'on')
        result=subprocess.run([sys.executable,str(script),'apply','--expected-database',self.p['database']],capture_output=True,text=True,timeout=15)
        self.assertNotEqual(result.returncode,0)
        self.assertIn('--allow-nonproduction-write',result.stderr)


if __name__=='__main__': unittest.main()
