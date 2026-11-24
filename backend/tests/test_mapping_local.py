"""Synthetic SQLite integration coverage for the user-authorized local contract."""
import json
import unittest
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import test_mapping_api as baseline
from flask_jwt_extended import create_access_token
from sqlalchemy import create_mock_engine, event, inspect
from sqlalchemy.exc import IntegrityError

from extensions import db
from model.business_product_category_mapping import (
    BusinessProductCategoryMapping as Association, prevent_remote_write,
)
from model.category_mapping_history import CategoryMappingHistory as History
from model.master_category import MasterCategory
from model.platform_category_mapping import PlatformCategoryMapping as Source
from model.product_category import ProductCategory
from services import mapping_service as service


class LocalMappingTests(unittest.TestCase):
    get = baseline.MappingAPITests.get
    post = baseline.MappingAPITests.post
    auto = baseline.MappingAPITests.auto
    set_source = baseline.MappingAPITests.set_source
    tearDown = baseline.MappingAPITests.tearDown

    def setUp(self):
        baseline.MappingAPITests.setUp(self)
        self.app.config.update(MAPPING_LOCAL_ASSOCIATIONS_ENABLED=True, MAPPING_ADMIN_IDS='1')
        db.session.add_all([
            ProductCategory(id=101, marketplace_name='SyntheticProducts', category_name='Rice',
                            category_level=1, category_path='Rice'),
            ProductCategory(id=102, marketplace_name='OtherProducts', category_name='Tea',
                            category_level=1, category_path='Tea'),
            ProductCategory(id=103, marketplace_name='SyntheticProducts', category_name='Rice',
                            subcategory_name='Packaged Rice', category_level=2, parent_id=101,
                            category_path='Rice > Packaged Rice'),
        ])
        db.session.commit()

    def payload(self, products=None, **changes):
        result = dict(business_category_id=1, business_subcategory_id=2,
                      product_category_ids=[101] if products is None else products,
                      mapping_type='carries_products')
        result.update(changes)
        return result

    def associate(self, products=None, **changes):
        return self.post('map-category', self.payload(products, **changes))

    def persist(self, **changes):
        return self.post('auto-map', dict(dry_run=False, **changes))

    def test_local_model_constraints_and_foreign_keys(self):
        schema = inspect(db.engine)
        self.assertIn('local_business_product_category_mappings', schema.get_table_names())
        self.assertNotIn('business_product_category_mappings', schema.get_table_names())
        fks = schema.get_foreign_keys(Association.__tablename__)
        self.assertEqual(len(fks), 4)
        unique = schema.get_unique_constraints(Association.__tablename__)
        self.assertEqual(unique[0]['column_names'], ['business_category_id', 'business_subcategory_id',
                                                     'product_category_id', 'mapping_type'])
        self.assertEqual(len(schema.get_check_constraints(Association.__tablename__)), 2)

    def test_verified_product_model_columns_types_and_nullability(self):
        snapshot = Path(__file__).resolve().parents[2] / 'docs/BG-1.11-SCHEMA-METADATA.json'
        metadata = json.loads(snapshot.read_text(encoding='utf-8'))
        actual = {c['column_name']: c for c in metadata['columns'] if c['table_name'] == 'product_category_master'}
        self.assertEqual(set(ProductCategory.__table__.columns.keys()), set(actual))
        for column in ProductCategory.__table__.columns:
            self.assertEqual(column.nullable, actual[column.name]['is_nullable'])
            if actual[column.name]['data_type'].startswith('character varying'):
                self.assertEqual(column.type.length, int(actual[column.name]['data_type'].split('(')[1][:-1]))
        self.assertEqual(str(ProductCategory.__table__.c.id.type), 'INTEGER')
        self.assertEqual(str(ProductCategory.__table__.c.category_path.type), 'TEXT')

    def test_postgresql_product_query_explicitly_uses_public_schema(self):
        from sqlalchemy.dialects import postgresql
        with patch.object(db.engine.dialect, 'name', 'postgresql'):
            query = service.product_query()
        self.assertEqual(query.get_execution_options()['schema_translate_map'], {None: 'public'})
        sql = str(query.statement.compile(dialect=postgresql.dialect(),
                  schema_translate_map={None: 'public'}, render_schema_translate=True))
        self.assertIn('public.product_category_master', sql)

    def test_postgresql_cannot_create_provisional_table(self):
        emitted = []
        engine = create_mock_engine('postgresql://', lambda *args, **kwargs: emitted.append(args))
        with self.assertRaisesRegex(RuntimeError, 'local SQLite'):
            Association.__table__.create(engine, checkfirst=False)
        self.assertEqual(emitted, [])

    def test_postgresql_orm_write_guard(self):
        with self.assertRaisesRegex(RuntimeError, 'local SQLite'):
            prevent_remote_write(None, SimpleNamespace(dialect=SimpleNamespace(name='postgresql')), None)

    def test_single_product_mapping_and_actor_audit(self):
        result = self.associate()
        self.assertEqual(result.status_code, 200, result.json)
        self.assertTrue(result.json['changed'])
        self.assertEqual(result.json['data']['saved'], 1)
        row = Association.query.one()
        self.assertEqual((row.business_category_id, row.business_subcategory_id, row.product_category_id,
                          row.mapping_type, row.status, row.approved_by_user_id),
                         (1, 2, 101, 'carries_products', 'APPROVED', 1))
        audit = History.query.one()
        self.assertIsNone(audit.mapping_id)
        self.assertEqual((audit.action, audit.changed_by), ('BUSINESS_PRODUCT_MAPPED', '1'))
        self.assertIn('local_association_id=' + str(row.id), audit.new_value)
        self.assertEqual(Source.query.filter(Source.master_category_id.isnot(None)).count(), 0)

    def test_multiple_products_atomic_save(self):
        result = self.associate([101, 102, 103])
        self.assertEqual(result.status_code, 200, result.json)
        self.assertEqual(result.json['data']['saved'], 3)
        self.assertEqual(Association.query.count(), 3)
        self.assertEqual(History.query.count(), 3)

    def test_duplicate_products_and_repeated_request(self):
        result = self.associate([101, 101, 102])
        self.assertEqual(result.json['data']['duplicates_ignored'], 1)
        self.assertEqual(result.json['data']['saved'], 2)
        repeat = self.associate([102, 101, 101])
        self.assertFalse(repeat.json['changed'])
        self.assertEqual((repeat.json['data']['saved'], repeat.json['data']['skipped']), (0, 2))
        self.assertEqual((Association.query.count(), History.query.count()), (2, 2))

    def test_existing_association_approver_preserved(self):
        self.associate()
        self.app.config['MAPPING_APPROVER_IDS'] = '2'
        repeat = self.post('map-category', self.payload(), self.viewer)
        self.assertEqual(repeat.status_code, 200)
        self.assertFalse(repeat.json['changed'])
        self.assertEqual(Association.query.one().approved_by_user_id, 1)
        self.assertEqual(History.query.count(), 1)

    def test_additive_repeat_preserves_previous_products(self):
        self.associate()
        result = self.associate([101, 102])
        self.assertEqual((result.json['data']['saved'], result.json['data']['skipped']), (1, 1))
        self.assertEqual(Association.query.count(), 2)

    def test_invalid_ids_leave_no_partial_associations(self):
        for changes in [dict(business_category_id=999), dict(business_subcategory_id=999),
                        dict(product_category_ids=[101, 999])]:
            with self.subTest(changes=changes):
                result = self.associate(**changes)
                self.assertEqual(result.status_code, 404, result.json)
                self.assertEqual((Association.query.count(), History.query.count()), (0, 0))

    def test_wrong_business_parent_and_inactive_hierarchy(self):
        self.assertEqual(self.associate(business_category_id=4).status_code, 422)
        self.assertEqual(self.associate(business_subcategory_id=1).status_code, 422)
        self.assertEqual(self.associate(business_category_id=2, business_subcategory_id=3).status_code, 422)
        db.session.get(MasterCategory, 1).is_active = False
        db.session.commit()
        self.assertEqual(self.associate().json['code'], 'invalid_hierarchy')
        self.assertEqual(Association.query.count(), 0)

    def test_invalid_product_parent_level_marketplace_and_cycle(self):
        product = db.session.get(ProductCategory, 103)
        for parent, level, marketplace in [(999, 2, 'SyntheticProducts'), (101, 3, 'SyntheticProducts'),
                                           (101, 2, 'OtherProducts'), (103, 2, 'SyntheticProducts')]:
            product.parent_id, product.category_level, product.marketplace_name = parent, level, marketplace
            db.session.commit()
            result = self.associate([101, 103])
            self.assertEqual((result.status_code, result.json['code']), (422, 'invalid_hierarchy'))
            self.assertEqual(Association.query.count(), 0)

    def test_relationship_payload_validation_and_attribution_spoofing(self):
        changes_list = [dict(product_category_ids=[]), dict(product_category_ids='101'),
                        dict(product_category_ids=[True]), dict(product_category_ids=['101']),
                        dict(product_category_ids=[101] * 101), dict(business_category_id=True),
                        dict(mapping_type='arbitrary'), dict(approved_by_user_id=2), dict(status='APPROVED'),
                        dict(master_category_id=2), dict(mapping_id=1)]
        for changes in changes_list:
            with self.subTest(changes=changes):
                self.assertIn(self.associate(**changes).status_code, [400, 422])
        self.assertEqual((Association.query.count(), History.query.count()), (0, 0))

    def test_local_storage_default_deny_and_non_sqlite_deny(self):
        self.app.config['MAPPING_LOCAL_ASSOCIATIONS_ENABLED'] = False
        self.assertEqual(self.associate().json['code'], 'local_associations_disabled')
        self.app.config['MAPPING_LOCAL_ASSOCIATIONS_ENABLED'] = True
        with patch.object(db.engine.dialect, 'name', 'postgresql'):
            self.assertFalse(service.local_associations_enabled())
            self.assertEqual(self.associate().json['code'], 'local_associations_disabled')
        self.assertEqual(Association.query.count(), 0)

    def test_approver_permission_and_authentication(self):
        self.assertEqual(self.post('map-category', self.payload(), self.viewer).status_code, 403)
        self.assertEqual(self.post('map-category', self.payload(), {}).status_code, 401)
        self.app.config['MAPPING_APPROVER_IDS'] = ''
        self.assertEqual(self.associate().status_code, 403)
        self.assertEqual(Association.query.count(), 0)

    def test_association_commit_failure_rolls_back_every_table(self):
        with patch.object(db.session, 'commit', side_effect=RuntimeError('synthetic secret')):
            result = self.associate([101, 102])
        self.assertEqual(result.status_code, 500)
        self.assertNotIn('secret', str(result.json))
        self.assertEqual((Association.query.count(), History.query.count()), (0, 0))
        self.assertEqual(self.associate([101, 102]).json['data']['saved'], 2)

    def test_audit_failure_rolls_back_preflushed_associations(self):
        count = 0
        def fail_second_audit(mapper, connection, target):
            nonlocal count
            count += 1
            if count == 2:
                raise RuntimeError('synthetic audit failure')
        event.listen(History, 'before_insert', fail_second_audit)
        try:
            result = self.associate([101, 102])
        finally:
            event.remove(History, 'before_insert', fail_second_audit)
        self.assertEqual(result.status_code, 500)
        self.assertEqual((Association.query.count(), History.query.count()), (0, 0))

    def test_partial_existing_request_failure_preserves_committed_state(self):
        self.associate()
        with patch.object(db.session, 'commit', side_effect=RuntimeError('synthetic failure')):
            result = self.associate([101, 102, 103])
        self.assertEqual(result.status_code, 500)
        self.assertEqual((Association.query.count(), History.query.count()), (1, 1))
        self.assertEqual(Association.query.one().product_category_id, 101)

    def test_database_unique_and_fk_enforcement(self):
        self.associate()
        for product in [101, 999]:
            db.session.add(Association(business_category_id=1, business_subcategory_id=2,
                                      product_category_id=product, mapping_type='carries_products',
                                      status='APPROVED', approved_by_user_id=1))
            with self.assertRaises(IntegrityError):
                db.session.flush()
            db.session.rollback()
        self.assertEqual(Association.query.count(), 1)

    def test_product_catalog_pagination_search_and_names(self):
        data = self.get('?product_limit=1&product_page=2').json['data']['product_service_categories']
        self.assertEqual((data['total_count'], data['total_pages'], data['data'][0]['id']), (3, 3, 102))
        data = self.get('?product_search=packaged').json['data']['product_service_categories']
        self.assertEqual((data['total_count'], data['data'][0]['name']), (1, 'Packaged Rice'))
        self.assertEqual(self.get('?product_search=PACKAGED').json['data']['product_service_categories']['total_count'], 1)
        self.assertEqual(self.get('?product_search=%25').json['data']['product_service_categories']['total_count'], 0)
        self.assertEqual(self.get('?product_search=_').json['data']['product_service_categories']['total_count'], 0)
        self.assertEqual(self.get('?product_page=100').json['data']['product_service_categories']['data'], [])

    def test_product_catalog_filters_and_bounds(self):
        for query, expected in [('?marketplace_name=SyntheticProducts', 2), ('?product_parent_id=root', 2),
                                ('?product_parent_id=101', 1), ('?product_level=2', 1),
                                ('?marketplace_name=Missing', 0)]:
            self.assertEqual(self.get(query).json['data']['product_service_categories']['total_count'], expected)
        for query in ['?product_limit=201', '?product_page=0', '?product_parent_id=invalid',
                      '?product_level=11', '?product_search=', '?product_limit=1&product_limit=2']:
            self.assertEqual(self.get(query).status_code, 400)

    def test_product_catalog_and_default_dry_run_issue_zero_writes(self):
        statements = []
        def capture(*args):
            statements.append(args[2])
        event.listen(db.engine, 'before_cursor_execute', capture)
        try:
            self.get('?product_search=Rice')
            result = self.post('auto-map', {})
        finally:
            event.remove(db.engine, 'before_cursor_execute', capture)
        self.assertTrue(result.json['dry_run'])
        self.assertFalse(any(s.lstrip().split()[0].upper() in {'INSERT', 'UPDATE', 'DELETE', 'CREATE', 'ALTER', 'DROP'} for s in statements))
        self.assertEqual((Association.query.count(), History.query.count()), (0, 0))

    def test_admin_persistence_saves_source_only_and_audit(self):
        result = self.persist()
        self.assertEqual(result.status_code, 200, result.json)
        self.assertEqual(result.json['summary'], dict(saved=1, skipped=1, failed=0, ambiguous=0))
        source = db.session.get(Source, 1)
        self.assertEqual((source.master_category_id, source.mapping_status), (2, 'AUTO_MAPPED'))
        self.assertEqual((History.query.one().action, History.query.one().changed_by), ('AUTO_MAPPED', '1'))
        self.assertEqual(Association.query.count(), 0)
        self.assertFalse(result.json['data'][0]['requires_manual_approval'])

    def test_admin_is_distinct_from_approver_and_default_deny(self):
        self.assertEqual(self.post('auto-map', {'dry_run': False}, self.viewer).status_code, 403)
        self.app.config['MAPPING_ADMIN_IDS'] = ''
        self.assertEqual(self.persist().status_code, 403)
        self.app.config['MAPPING_ADMIN_IDS'] = '2'
        self.assertEqual(self.persist().status_code, 403)
        self.assertEqual(self.post('auto-map', {'dry_run': False}, self.viewer).status_code, 200)

    def test_cookie_only_admin_persistence_rejected(self):
        self.client.set_cookie('access_token_cookie', create_access_token(identity='1'))
        self.assertEqual(self.post('auto-map', {'dry_run': False}, {}).status_code, 401)
        self.assertEqual(History.query.count(), 0)

    def test_deleted_admin_rejected(self):
        from model.user import User
        db.session.delete(db.session.get(User, 1))
        db.session.commit()
        self.assertEqual(self.persist().status_code, 403)

    def test_unrounded_score_below_90_not_saved_even_when_display_rounds_up(self):
        with patch.object(service, 'similarity', side_effect=lambda left, right: 0.8999996 if right == 'kirana stores' else None):
            result = self.persist(platform_name='Synthetic')
        self.assertEqual(result.json['data'][0]['candidates'][0]['score'], 0.9)
        self.assertEqual(result.json['summary']['saved'], 0)
        self.assertEqual(result.json['data'][0]['persistence_reason'], 'below_persistence_threshold')
        self.assertEqual(History.query.count(), 0)

    def test_real_90_percent_fuzzy_boundary_is_saved(self):
        db.session.add(MasterCategory(id=6, name='abcdefghij', level=1, path='abcdefghij'))
        db.session.commit()
        self.set_source('abcdefghiX')
        result = self.persist(platform_name='Synthetic')
        self.assertEqual(result.json['summary']['saved'], 1)
        self.assertEqual(db.session.get(Source, 1).master_category_id, 6)
        self.assertAlmostEqual(db.session.get(Source, 1).confidence_score, 0.9)

    def test_ambiguous_high_confidence_is_never_saved(self):
        db.session.add(MasterCategory(id=6, name='Kirana Stores', parent_id=4, level=2, path='Services > Kirana Stores'))
        db.session.commit()
        result = self.persist(platform_name='Synthetic')
        self.assertEqual(result.json['summary'], dict(saved=0, skipped=0, failed=0, ambiguous=1))
        self.assertEqual(History.query.count(), 0)

    def test_manual_approval_never_overwritten_and_bulk_idempotent(self):
        self.post('map-category', dict(mapping_id=1, master_category_id=3))
        result = self.persist()
        self.assertEqual(result.json['summary']['saved'], 0)
        self.assertEqual(db.session.get(Source, 1).master_category_id, 3)
        self.assertEqual(History.query.count(), 1)
        self.set_source('kirana stores')
        self.assertEqual(self.persist().json['summary']['saved'], 0)

    def test_auto_repeated_request_does_not_repeat_history(self):
        self.assertEqual(self.persist().json['summary']['saved'], 1)
        self.assertEqual(self.persist().json['summary']['saved'], 0)
        self.assertEqual(History.query.count(), 1)

    def test_auto_bounded_batches_and_cursor(self):
        db.session.add_all([Source(platform_name='Synthetic', platform_category_raw='kirana stores' + '.' * i,
                                   platform_subcategory_raw='', mapping_status='PENDING') for i in range(1, 61)])
        db.session.commit()
        first = self.persist(platform_name='Synthetic', limit=50)
        self.assertEqual((len(first.json['data']), first.json['summary']['saved'], first.json['has_more']), (50, 50, True))
        second = self.persist(platform_name='Synthetic', after_id=first.json['next_after_id'], limit=50)
        self.assertEqual(second.json['summary']['saved'], 11)
        self.assertFalse(second.json['has_more'])
        self.assertEqual(History.query.count(), 61)
        self.assertEqual(self.persist(platform_name='Synthetic').json['summary']['saved'], 0)

    def test_auto_batch_commit_failure_rolls_back_and_reports_all_failed(self):
        db.session.add(Source(platform_name='Synthetic', platform_category_raw='KIRANA STORES.',
                              platform_subcategory_raw='', mapping_status='PENDING'))
        db.session.commit()
        with patch.object(db.session, 'commit', side_effect=RuntimeError('synthetic confidential error')):
            result = self.persist(platform_name='Synthetic')
        self.assertEqual(result.status_code, 500)
        self.assertEqual(result.json['summary'], dict(saved=0, skipped=0, failed=2, ambiguous=0))
        self.assertTrue(result.json['transaction_failed'])
        self.assertNotIn('confidential', str(result.json))
        self.assertEqual(Source.query.filter(Source.master_category_id.isnot(None)).count(), 0)
        self.assertEqual(History.query.count(), 0)
        self.assertTrue(all(item['outcome'] == 'failed' for item in result.json['data']))

    def test_auto_invalid_target_is_reported_without_writes(self):
        with patch.object(service, 'category_chain', side_effect=service.MappingError('invalid', 422)):
            result = self.persist(platform_name='Synthetic')
        self.assertEqual(result.json['summary']['failed'], 1)
        self.assertEqual(History.query.count(), 0)

    def test_auto_uses_no_provisional_relationship_table(self):
        self.associate([101, 102])
        before = [row.to_dict() for row in Association.query.order_by(Association.id)]
        self.persist()
        self.assertEqual([row.to_dict() for row in Association.query.order_by(Association.id)], before)


class LocalConcurrencyTests(unittest.TestCase):
    def check_concurrent_requests(self, endpoint):
        with tempfile.TemporaryDirectory(prefix='bg-1-11-offline-') as directory:
            fixture = LocalMappingTests('test_single_product_mapping_and_actor_audit')
            fixture.database_uri = 'sqlite:///' + str(Path(directory) / 'synthetic.sqlite3').replace('\\', '/')
            fixture.setUp()
            try:
                db.session.remove()
                barrier = threading.Barrier(2)
                def submit():
                    with fixture.app.test_client() as client:
                        barrier.wait(timeout=10)
                        payload = fixture.payload() if endpoint == 'map-category' else {'dry_run': False}
                        response = client.post('/api/mapping/' + endpoint, json=payload, headers=fixture.headers)
                        return response.status_code, response.json
                with ThreadPoolExecutor(max_workers=2) as pool:
                    results = list(pool.map(lambda _: submit(), range(2)))
                self.assertEqual([status for status, _ in results], [200, 200], results)
                section = 'data' if endpoint == 'map-category' else 'summary'
                self.assertEqual(sorted(body[section]['saved'] for _, body in results), [0, 1])
                self.assertEqual(History.query.count(), 1)
                self.assertEqual(Association.query.count(), 1 if endpoint == 'map-category' else 0)
            finally:
                fixture.tearDown()
                fixture.doCleanups()

    def test_identical_concurrent_requests_create_one_association_and_audit(self):
        self.check_concurrent_requests('map-category')

    def test_concurrent_auto_map_requests_create_one_source_audit(self):
        self.check_concurrent_requests('auto-map')


if __name__ == '__main__':
    unittest.main()
