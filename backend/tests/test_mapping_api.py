"""Offline BG-1.11 integration tests using real models and SQLite in memory.

Run only this test directory, not backend/test_areas_query.py (a live diagnostic).
The model package initializer imports ETL/config/.env code, so load its actual
model submodules through a namespace package instead. Never import app/config.
"""

import ast
import itertools
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
model_namespace = types.ModuleType('model')
model_namespace.__path__ = [str(BACKEND / 'model')]
sys.modules['model'] = model_namespace

from flask import Flask, jsonify, request
from flask_jwt_extended import create_access_token, verify_jwt_in_request
from sqlalchemy import event
from sqlalchemy.dialects import postgresql

from extensions import db, jwt
from model.user import User
from model.master_category import MasterCategory
from model.platform_category_mapping import PlatformCategoryMapping
from model.category_mapping_history import CategoryMappingHistory
from model.category_mapping_synonyms import CategoryMappingSynonym
from model.product_category import ProductCategory
from routes.mapping_routes import mapping_bp
from routes.category_mapping_routes import category_mapping_bp
from routes.master_category_routes import master_category_bp
from services import mapping_service as service


def install_app_registration(app):
    """Execute the real selected registration calls and global auth hook safely."""
    tree = ast.parse((BACKEND / 'app.py').read_text(encoding='utf-8'))
    selected = []
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'PUBLIC_ROUTES' for t in node.targets):
            selected.append(node)
        elif isinstance(node, ast.FunctionDef) and node.name == 'protect_all_routes':
            selected.append(node)
        elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            call = node.value
            if (isinstance(call.func, ast.Attribute) and call.func.attr == 'register_blueprint'
                    and call.args and isinstance(call.args[0], ast.Name)
                    and call.args[0].id in {'mapping_bp', 'category_mapping_bp', 'master_category_bp'}):
                selected.append(node)
    namespace = dict(app=app, request=request, jsonify=jsonify,
                     verify_jwt_in_request=verify_jwt_in_request,
                     mapping_bp=mapping_bp, category_mapping_bp=category_mapping_bp,
                     master_category_bp=master_category_bp)
    exec(compile(ast.Module(body=selected, type_ignores=[]), 'app.py:selected', 'exec'), namespace)


class MappingAPITests(unittest.TestCase):
    def setUp(self):
        self.network_guard = patch('socket.socket.connect', side_effect=AssertionError('Network forbidden in mapping tests'))
        self.network_guard.start()
        self.addCleanup(self.network_guard.stop)
        self.app = Flask(__name__)
        self.app.config.update(TESTING=True, SQLALCHEMY_DATABASE_URI=getattr(self, 'database_uri', 'sqlite://'),
                               SQLALCHEMY_TRACK_MODIFICATIONS=False,
                               JWT_SECRET_KEY='offline-mapping-test-key-with-at-least-32-bytes',
                               JWT_TOKEN_LOCATION=['headers', 'cookies'],
                               JWT_COOKIE_CSRF_PROTECT=False,
                               MAPPING_APPROVER_IDS='1')
        db.init_app(self.app)
        jwt.init_app(self.app)
        install_app_registration(self.app)
        self.context = self.app.app_context()
        self.context.push()
        with db.engine.connect() as connection:
            connection.exec_driver_sql('PRAGMA foreign_keys=ON')
        db.create_all()
        db.session.add_all([
            User(id=1, email='approver@example.test'), User(id=2, email='viewer@example.test'),
            MasterCategory(id=1, name='Shopping', level=1, path='Shopping', is_active=True),
            MasterCategory(id=4, name='Services', level=1, path='Services', is_active=True),
        ])
        db.session.flush()
        db.session.add_all([
            MasterCategory(id=2, name='Kirana Stores', parent_id=1, level=2,
                           path='Shopping > Kirana Stores', is_active=True),
            MasterCategory(id=3, name='Dairy Products', parent_id=1, level=2,
                           path='Shopping > Dairy Products', is_active=True),
            MasterCategory(id=5, name='Hidden', parent_id=4, level=2,
                           path='Services > Hidden', is_active=False),
            PlatformCategoryMapping(id=1, platform_name='Synthetic', platform_category_raw='kirana stores',
                                     platform_subcategory_raw='', mapping_status='PENDING'),
            PlatformCategoryMapping(id=2, platform_name='Other', platform_category_raw='Unrelated Quasar',
                                     platform_subcategory_raw='', mapping_status='UNMAPPED'),
            CategoryMappingSynonym(raw_value='local grocery shop', canonical_value='Shopping > Kirana Stores'),
        ])
        db.session.commit()
        self.headers = {'Authorization': 'Bearer ' + create_access_token(identity='1')}
        self.viewer = {'Authorization': 'Bearer ' + create_access_token(identity='2')}
        self.client = self.app.test_client()

    def tearDown(self):
        db.session.remove()
        # Disposing the in-memory engine destroys the database, including its
        # self-referencing RESTRICT FKs; DROP TABLE is unnecessary and invalid.
        db.engine.dispose()
        self.context.pop()

    def get(self, query=''):
        return self.client.get('/api/mapping/categories' + query, headers=self.headers)

    def post(self, endpoint, data, headers=None):
        return self.client.post('/api/mapping/' + endpoint, json=data,
                                headers=self.headers if headers is None else headers)

    def auto(self, **data):
        response = self.post('auto-map', data)
        self.assertEqual(response.status_code, 200, response.json)
        return response.json['data']

    def set_source(self, raw, sub=''):
        row = db.session.get(PlatformCategoryMapping, 1)
        row.platform_category_raw = raw
        row.platform_subcategory_raw = sub
        db.session.commit()

    def test_retrieval_and_capabilities(self):
        response = self.get()
        self.assertEqual(response.status_code, 200)
        data = response.json['data']
        self.assertEqual(data['source_categories']['total_count'], 2)
        self.assertEqual(data['canonical_categories']['total_count'], 4)
        self.assertEqual(data['product_service_categories']['total_count'], 0)
        self.assertFalse(data['capabilities']['business_product_associations'])

    def test_pagination_filtering_and_hierarchy(self):
        data = self.get('?limit=1&page=2&category_limit=1&category_page=2').json['data']
        self.assertEqual(data['source_categories']['data'][0]['id'], 2)
        self.assertEqual(data['canonical_categories']['data'][0]['id'], 2)
        data = self.get('?platform_name=Synthetic&search=kirana&parent_id=1').json['data']
        self.assertEqual(data['source_categories']['total_count'], 1)
        self.assertEqual([c['parent_id'] for c in data['canonical_categories']['data']], [1, 1])
        roots = self.get('?parent_id=root').json['data']['canonical_categories']['data']
        self.assertTrue(all(c['parent_id'] is None for c in roots))

    def test_literal_search_wildcards(self):
        self.assertEqual(self.get('?search=%25').json['data']['source_categories']['total_count'], 0)
        self.assertEqual(self.get('?search=_').json['data']['source_categories']['total_count'], 0)

    def test_query_validation(self):
        for query in ['?page=0', '?page=-1', '?limit=201', '?page=x', '?limit=1.5',
                      '?status=invalid', '?parent_id=-1', '?page=1&page=2', '?unexpected=1',
                      '?page=99999999999999999']:
            with self.subTest(query=query):
                self.assertEqual(self.get(query).status_code, 400)

    def test_manual_approval_and_audit(self):
        response = self.post('map-category', {'mapping_id': 1, 'master_category_id': 2, 'parent_category_id': 1})
        self.assertEqual(response.status_code, 200, response.json)
        self.assertTrue(response.json['changed'])
        row = db.session.get(PlatformCategoryMapping, 1)
        self.assertEqual((row.master_category_id, row.mapping_status, row.confidence_score),
                         (2, 'MANUALLY_MAPPED', 1.0))
        self.assertEqual(row.platform_category_raw, 'kirana stores')
        history = CategoryMappingHistory.query.one()
        self.assertEqual((history.changed_by, history.action, history.master_category_id), ('1', 'MAPPED', 2))

    def test_raw_identity_and_null_subcategory(self):
        row = db.session.get(PlatformCategoryMapping, 1)
        row.platform_subcategory_raw = None
        db.session.commit()
        result = self.post('map-category', {'platform_name': 'Synthetic',
                           'platform_category_raw': 'kirana stores', 'master_category_id': 2})
        self.assertEqual(result.status_code, 200, result.json)
        self.assertEqual(PlatformCategoryMapping.query.count(), 2)

    def test_legacy_duplicate_source_requires_id(self):
        db.session.get(PlatformCategoryMapping, 1).platform_subcategory_raw = None
        db.session.add(PlatformCategoryMapping(id=3, platform_name='Synthetic',
                       platform_category_raw='kirana stores', platform_subcategory_raw=''))
        db.session.commit()
        result = self.post('map-category', {'platform_name': 'Synthetic',
                           'platform_category_raw': 'kirana stores', 'master_category_id': 2})
        self.assertEqual((result.status_code, result.json['code']), (409, 'duplicate_source'))
        self.assertEqual(self.post('map-category', {'mapping_id': 1, 'master_category_id': 2}).status_code, 200)

    def test_missing_source_does_not_create_records(self):
        result = self.post('map-category', {'platform_name': 'Synthetic',
                           'platform_category_raw': 'New label', 'master_category_id': 2})
        self.assertEqual(result.status_code, 404)
        self.assertEqual(PlatformCategoryMapping.query.count(), 2)
        self.assertEqual(CategoryMappingHistory.query.count(), 0)

    def test_missing_and_invalid_manual_parameters(self):
        for data in [{}, {'mapping_id': 1}, {'master_category_id': 2},
                     {'mapping_id': True, 'master_category_id': 2},
                     {'mapping_id': 1, 'master_category_id': '2'},
                     {'mapping_id': 1, 'master_category_id': 2, 'changed_by': 'spoofed'}]:
            with self.subTest(data=data):
                self.assertEqual(self.post('map-category', data).status_code, 400)
        self.assertEqual(CategoryMappingHistory.query.count(), 0)

    def test_invalid_ids_and_relationships(self):
        for data, status in [({'mapping_id': 999, 'master_category_id': 2}, 404),
                             ({'mapping_id': 1, 'master_category_id': 999}, 404),
                             ({'mapping_id': 1, 'master_category_id': 5}, 422),
                             ({'mapping_id': 1, 'master_category_id': 2, 'parent_category_id': 4}, 422),
                             ({'mapping_id': 1, 'master_category_id': 1, 'parent_category_id': 4}, 422)]:
            self.assertEqual(self.post('map-category', data).status_code, status)
        self.assertIsNone(db.session.get(PlatformCategoryMapping, 1).master_category_id)

    def test_inactive_ancestor_rejected(self):
        db.session.get(MasterCategory, 1).is_active = False
        db.session.commit()
        self.assertEqual(self.post('map-category', {'mapping_id': 1, 'master_category_id': 2}).status_code, 422)
        self.assertEqual(self.auto()[0]['classification'], 'unmatched')

    def test_bad_level_and_cycle_rejected(self):
        node = db.session.get(MasterCategory, 2)
        node.level = 7
        db.session.commit()
        self.assertEqual(self.post('map-category', {'mapping_id': 1, 'master_category_id': 2}).status_code, 422)
        node.level = 2
        db.session.get(MasterCategory, 1).parent_id = 2
        db.session.commit()
        self.assertEqual(self.post('map-category', {'mapping_id': 1, 'master_category_id': 2}).status_code, 422)
        self.assertEqual(self.auto()[0]['classification'], 'unmatched')

    def test_idempotency_and_approved_mapping_protection(self):
        data = {'mapping_id': 1, 'master_category_id': 2}
        self.assertEqual(self.post('map-category', data).status_code, 200)
        self.assertFalse(self.post('map-category', data).json['changed'])
        self.assertEqual(CategoryMappingHistory.query.count(), 1)
        self.assertEqual(self.post('map-category', {'mapping_id': 1, 'master_category_id': 3}).status_code, 409)
        self.assertEqual(CategoryMappingHistory.query.count(), 1)
        self.assertEqual(self.get().json['data']['source_categories']['total_count'], 1)
        data = self.get('?status=all').json['data']['source_categories']['data'][0]
        self.assertEqual(data['master_category_name'], 'Kirana Stores')

    def test_identity_conflict_and_inactive_source(self):
        self.assertEqual(self.post('map-category', {'mapping_id': 1, 'master_category_id': 2,
                         'platform_category_raw': 'different'}).status_code, 409)
        db.session.get(PlatformCategoryMapping, 1).is_active = False
        db.session.commit()
        self.assertEqual(self.post('map-category', {'mapping_id': 1, 'master_category_id': 2}).status_code, 422)

    def test_unsupported_product_association(self):
        for field in ['product_category_ids', 'product_category_id', 'business_category_id', 'business_subcategory_id']:
            result = self.post('map-category', {'mapping_id': 1, 'master_category_id': 2, field: [2, 3]})
            self.assertEqual(result.status_code, 422)
            self.assertEqual(result.json['code'], 'unsupported_relationship')

    def test_known_synonym(self):
        self.set_source('local grocery shop')
        result = self.auto()[0]
        self.assertEqual((result['classification'], result['reason']), ('high_confidence', 'synonym'))
        self.assertEqual(result['candidates'][0]['id'], 2)
        self.assertEqual(result['candidates'][0]['score'], 1.0)

    def test_normalization_and_original_preservation(self):
        self.assertEqual(service.normalize('  FOOD&  Dining. '), service.normalize('Food and Dining'))
        self.assertNotEqual(service.normalize('Pet food'), service.normalize('Food'))
        self.assertNotEqual(service.normalize('Accomodation'), service.normalize('Accommodation'))
        self.set_source('  KIRANA_STORES. ')
        result = self.auto()[0]
        self.assertEqual(result['classification'], 'high_confidence')
        self.assertEqual(result['platform_category_raw'], '  KIRANA_STORES. ')
        self.assertEqual(db.session.get(PlatformCategoryMapping, 1).platform_category_raw, '  KIRANA_STORES. ')

    def test_fuzzy_typo_needs_review(self):
        self.set_source('Kirana Store')
        result = self.auto()[0]
        self.assertEqual(result['classification'], 'review_required')
        self.assertGreaterEqual(result['candidates'][0]['score'], 0.8)
        self.assertTrue(result['requires_manual_approval'])

    def test_threshold_boundary(self):
        self.assertAlmostEqual(service.similarity('abcde', 'abcdx'), 0.8)
        self.assertIsNone(service.similarity('abcd', 'abcx'))
        self.assertAlmostEqual(service.similarity('abcde', 'abcdef'), 5 / 6)
        self.assertEqual(service.similarity('', ''), 1.0)
        self.assertIsNone(service.similarity('', 'a'))

    def test_threshold_boundary_through_api(self):
        db.session.add(MasterCategory(id=6, name='abcde', level=1, path='abcde'))
        db.session.commit()
        self.set_source('abcdx')
        result = self.auto()[0]
        self.assertEqual(result['classification'], 'review_required')
        self.assertEqual(result['candidates'][0]['score'], 0.8)
        self.set_source('abcxx')
        self.assertEqual(self.auto()[0]['classification'], 'unmatched')

    def test_ambiguous_duplicate_names(self):
        db.session.add(MasterCategory(id=6, name='Kirana Stores', parent_id=4, level=2,
                                      path='Services > Kirana Stores'))
        db.session.commit()
        result = self.auto()[0]
        self.assertEqual(result['classification'], 'ambiguous')
        self.assertEqual(result['candidate_count'], 2)

    def test_close_competing_candidates(self):
        db.session.add_all([MasterCategory(id=6, name='abcdf', level=1, path='abcdf'),
                            MasterCategory(id=7, name='abcdg', level=1, path='abcdg')])
        db.session.commit()
        self.set_source('abcde')
        self.assertEqual(self.auto()[0]['classification'], 'ambiguous')

    def test_path_disambiguation_and_wrong_parent(self):
        db.session.add(MasterCategory(id=6, name='Kirana Stores', parent_id=4, level=2,
                                      path='Services > Kirana Stores'))
        db.session.commit()
        self.set_source('Shopping', 'Kirana Stores')
        result = self.auto()[0]
        self.assertEqual(result['classification'], 'high_confidence')
        self.assertEqual(result['candidates'][0]['id'], 2)
        self.set_source('Unrelated Quasar', 'Kirana Stores')
        self.assertEqual(self.auto()[0]['classification'], 'unmatched')

    def test_unmatched_and_unresolved_alias(self):
        self.assertEqual(self.auto()[1]['classification'], 'unmatched')
        self.set_source('local grocery shop')
        CategoryMappingSynonym.query.one().canonical_value = 'Missing Approved Target'
        db.session.commit()
        self.assertEqual(self.auto()[0]['reason'], 'unresolved_synonym')

    def test_colliding_normalized_synonyms(self):
        db.session.add(CategoryMappingSynonym(raw_value='LOCAL GROCERY SHOP', canonical_value='Dairy Products'))
        db.session.commit()
        self.set_source('local grocery shop')
        self.assertEqual(self.auto()[0]['classification'], 'ambiguous')

    def test_dry_run_zero_writes(self):
        statements = []
        def capture(conn, cursor, statement, parameters, context, executemany):
            statements.append(statement)
        event.listen(db.engine, 'before_cursor_execute', capture)
        try:
            self.auto()
            self.get()
        finally:
            event.remove(db.engine, 'before_cursor_execute', capture)
        self.assertFalse(any(s.lstrip().split()[0].upper() in {'INSERT', 'UPDATE', 'DELETE'} for s in statements))
        self.assertEqual(CategoryMappingHistory.query.count(), 0)
        self.assertEqual(MasterCategory.query.count(), 5)

    def test_auto_eligibility_preserves_existing_assignments(self):
        row = db.session.get(PlatformCategoryMapping, 1)
        for status in ['AUTO_MAPPED', 'MANUALLY_MAPPED']:
            row.mapping_status = status
            row.master_category_id = 2
            db.session.commit()
            self.assertEqual(self.auto(platform_name='Synthetic'), [])
            self.assertEqual(db.session.get(PlatformCategoryMapping, 1).master_category_id, 2)
        row.mapping_status = 'PENDING'
        db.session.commit()
        self.assertEqual(self.auto(platform_name='Synthetic'), [])

    def test_persistence_requires_configured_admin(self):
        result = self.post('auto-map', {'dry_run': False})
        self.assertEqual((result.status_code, result.json['code']), (403, 'forbidden'))
        self.assertEqual(CategoryMappingHistory.query.count(), 0)

    def test_auto_cursor_and_filters(self):
        response = self.post('auto-map', {'limit': 1}).json
        self.assertTrue(response['has_more'])
        self.assertEqual(response['next_after_id'], 1)
        self.assertEqual(self.auto(after_id=1)[0]['mapping_id'], 2)
        self.assertEqual(len(self.auto(platform_name='Synthetic')), 1)
        self.assertEqual(self.auto(after_id=2), [])

    def test_auto_validation(self):
        for data in [{'dry_run': 'false'}, {'limit': True}, {'limit': 51}, {'after_id': -1},
                     {'after_id': True}, {'platform_name': []}, {'surprise': 1}]:
            self.assertEqual(self.post('auto-map', data).status_code, 400)

    def test_capacity_fails_closed(self):
        with patch.object(service, 'MAX_TAXONOMY', 1):
            result = self.post('auto-map', {})
        self.assertEqual((result.status_code, result.json['code']), (422, 'matching_capacity_exceeded'))
        with patch.object(service, 'MAX_SYNONYMS', 0):
            self.assertEqual(self.post('auto-map', {}).status_code, 422)

    def test_rollback_on_commit_failure(self):
        with patch.object(db.session, 'commit', side_effect=RuntimeError('synthetic secret details')):
            result = self.post('map-category', {'mapping_id': 1, 'master_category_id': 2})
        self.assertEqual(result.status_code, 500)
        self.assertNotIn('secret', str(result.json))
        self.assertIsNone(db.session.get(PlatformCategoryMapping, 1).master_category_id)
        self.assertEqual(CategoryMappingHistory.query.count(), 0)
        self.assertEqual(self.post('map-category', {'mapping_id': 1, 'master_category_id': 2}).status_code, 200)

    def test_unauthenticated_requests(self):
        for method, path in [('get', 'categories'), ('post', 'map-category'), ('post', 'auto-map')]:
            result = getattr(self.client, method)('/api/mapping/' + path)
            self.assertEqual(result.status_code, 401)

    def test_unauthorized_and_default_deny(self):
        data = {'mapping_id': 1, 'master_category_id': 2}
        self.assertEqual(self.post('map-category', data, self.viewer).status_code, 403)
        self.app.config['MAPPING_APPROVER_IDS'] = ''
        self.assertEqual(self.post('map-category', data).status_code, 403)
        self.assertEqual(CategoryMappingHistory.query.count(), 0)

    def test_deleted_user_and_spoofed_identity(self):
        db.session.delete(db.session.get(User, 1))
        db.session.commit()
        self.assertEqual(self.post('map-category', {'mapping_id': 1, 'master_category_id': 2}).status_code, 403)
        for identity in ['not-a-user', '99999999999999999999999999']:
            headers = {'Authorization': 'Bearer ' + create_access_token(identity=identity)}
            self.assertEqual(self.post('map-category', {'mapping_id': 1, 'master_category_id': 2}, headers).status_code, 403)

    def test_cookie_only_cannot_approve(self):
        self.client.set_cookie('access_token_cookie', create_access_token(identity='1'))
        result = self.post('map-category', {'mapping_id': 1, 'master_category_id': 2}, {})
        self.assertEqual(result.status_code, 401)

    def test_json_and_payload_bounds(self):
        for payload, content_type in [('[]', 'application/json'), ('{', 'application/json'),
                                      ('null', 'application/json'), ('{}', 'text/plain')]:
            response = self.client.post('/api/mapping/auto-map', data=payload,
                                        content_type=content_type, headers=self.headers)
            self.assertEqual(response.status_code, 400)
        response = self.client.post('/api/mapping/auto-map', data=' ' * 16_385,
                                    content_type='application/json', headers=self.headers)
        self.assertEqual(response.status_code, 413)

    def test_route_registration_and_legacy_compatibility(self):
        for path in ['/api/mapping/categories', '/api/mapping/map-category', '/api/mapping/auto-map']:
            self.assertEqual(len([r for r in self.app.url_map.iter_rules() if r.rule == path]), 1)
        self.assertEqual(self.client.get('/api/category-mapping/pending').status_code, 200)
        self.assertEqual(self.client.get('/api/master-categories/tree').status_code, 200)
        self.assertEqual(self.client.options('/api/mapping/map-category').status_code, 200)

    def test_bounded_query_count(self):
        db.session.add_all([
            PlatformCategoryMapping(platform_name='Synthetic', platform_category_raw=f'Synthetic {i}',
                                    platform_subcategory_raw='', master_category_id=2 if i % 2 else 3,
                                    mapping_status='MANUALLY_MAPPED')
            for i in range(25)
        ])
        db.session.commit()
        statements = []
        def capture(*args):
            statements.append(args[2])
        event.listen(db.engine, 'before_cursor_execute', capture)
        try:
            self.get('?status=all')
            count = len(statements)
            statements.clear()
            self.auto()
            auto_count = len(statements)
        finally:
            event.remove(db.engine, 'before_cursor_execute', capture)
        self.assertLessEqual(count, 6)
        self.assertLessEqual(auto_count, 3)

    def test_postgresql_source_lock_sql(self):
        query = PlatformCategoryMapping.query.filter_by(id=1).with_for_update()
        self.assertIn('FOR UPDATE', str(query.statement.compile(dialect=postgresql.dialect())))


class SimilarityAlgorithmTests(unittest.TestCase):
    def test_banded_distance_against_full_reference(self):
        def reference(a, b):
            previous = list(range(len(b) + 1))
            for i, left in enumerate(a, 1):
                current = [i]
                for j, right in enumerate(b, 1):
                    current.append(min(current[-1] + 1, previous[j] + 1,
                                       previous[j - 1] + (left != right)))
                previous = current
            size = max(len(a), len(b))
            return (1 - previous[-1] / size) if size else 1.0, previous[-1], size
        strings = [''.join(chars) for length in range(7) for chars in itertools.product('ab', repeat=length)]
        for left in strings:
            for right in strings:
                expected, distance, size = reference(left, right)
                actual = service.similarity(left, right)
                if not size or distance * 5 <= size:
                    self.assertEqual(actual, expected, (left, right))
                else:
                    self.assertIsNone(actual, (left, right))


if __name__ == '__main__':
    unittest.main()
