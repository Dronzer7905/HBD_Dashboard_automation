"""Synthetic API, streaming/checkpoint and scheduler contract tests.

Default: SQLite, with all network connections forbidden. The owned PostgreSQL
runner can execute the same suite against its explicitly scoped temporary DB.
Never imports app/config, reads .env, or connects to the company tunnel.
"""
import ast
from contextlib import nullcontext
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from flask import Flask, jsonify, request
from flask_jwt_extended import create_access_token, verify_jwt_in_request
from openpyxl import Workbook
import sqlalchemy as sa

from extensions import db, jwt
from routes.ingestion_routes import ingestion_bp
from services import ingestion_monitoring as monitor
from services.ingestion_storage import load_upload, storage_root
from services.ingestion_store import now, progress, tables
from tasks.bulk_ingest import process_batch


class MemoryRedis:
    def __init__(self):
        self.values = {}

    def ping(self):
        return True

    def llen(self, key):
        return 3 if key == 'heavy_ingestion' else 0

    def get(self, key):
        return self.values.get(key)

    def set(self, key, value, **kwargs):
        self.values[key] = value


def install_registration(app):
    source = Path(__file__).resolve().parents[1] / 'app.py'
    tree = ast.parse(source.read_text(encoding='utf-8'))
    selected = []
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'PUBLIC_ROUTES' for t in node.targets):
            selected.append(node)
        elif isinstance(node, ast.FunctionDef) and node.name == 'protect_all_routes':
            selected.append(node)
        elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            call = node.value
            if (isinstance(call.func, ast.Attribute) and call.func.attr == 'register_blueprint'
                    and call.args and isinstance(call.args[0], ast.Name) and call.args[0].id == 'ingestion_bp'):
                selected.append(node)
    namespace = dict(app=app, request=request, jsonify=jsonify,
                     verify_jwt_in_request=verify_jwt_in_request, ingestion_bp=ingestion_bp)
    exec(compile(ast.Module(body=selected, type_ignores=[]), 'app.py:selected', 'exec'), namespace)


class IngestionTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix='bg113-fixture-')
        self.addCleanup(self.directory.cleanup)
        database_uri = 'sqlite:///' + str(Path(self.directory.name) / 'fixture.sqlite3')
        profile_path = os.getenv('INGESTION_TEST_PG_PROFILE')
        if profile_path:
            profile = json.loads(Path(profile_path).read_text())
            directory = Path(profile['cluster_directory']).resolve()
            assert (profile['owned_cluster'] is True and profile['host'] == '127.0.0.1'
                    and profile['database'].startswith('bg113_test_')
                    and profile['port'] not in [5432, 5433, 15432, 15434]
                    and directory.parent == Path(tempfile.gettempdir()).resolve()
                    and directory.name.startswith('bg113-owned-pg-'))
            database_uri = sa.URL.create('postgresql+psycopg2', username=profile['user'],
                host=profile['host'], port=profile['port'], database=profile['database'],
                query={'passfile': profile['passfile'], 'sslmode': 'disable'})
        else:
            guard = patch('socket.socket.connect', side_effect=AssertionError('Network forbidden in SQLite tests'))
            guard.start()
            self.addCleanup(guard.stop)
        self.app = Flask(__name__)
        self.app.config.update(TESTING=True, SQLALCHEMY_DATABASE_URI=database_uri,
            JWT_SECRET_KEY='offline-ingestion-test-key-with-at-least-32-bytes',
            JWT_TOKEN_LOCATION=['headers', 'cookies'], JWT_COOKIE_CSRF_PROTECT=False,
            SCHEDULER_OPERATOR_IDS='1', INGESTION_UPLOAD_DIR=str(Path(self.directory.name) / 'staging'),
            INGESTION_MAX_UPLOAD_BYTES=1024 * 1024, INGESTION_CHUNK_SIZE=2, INGESTION_CHUNK_COOLDOWN=0,
            PIPELINE_STAGE_SOURCES={key: {'schema': 'bronze_staging', 'table': 'raw_businesses'} for key in monitor.STAGES})
        db.init_app(self.app)
        jwt.init_app(self.app)
        install_registration(self.app)
        self.context = self.app.app_context()
        self.context.push()
        self.engine = db.engine
        self.addCleanup(self.dispose)
        self.batches, self.businesses, self.quarantine = tables(self.engine.dialect.name)
        if self.engine.dialect.name == 'postgresql':
            with self.engine.begin() as connection:
                connection.exec_driver_sql('CREATE SCHEMA IF NOT EXISTS bronze_staging')
        self.batches.metadata.create_all(self.engine)  # Synthetic fixture ONLY.
        self.users = sa.Table('users', sa.MetaData(), sa.Column('id', sa.Integer, primary_key=True))
        self.users.create(self.engine)
        with self.engine.begin() as connection:
            connection.execute(self.users.insert(), [{'id': 1}, {'id': 2}])
        self.client = self.app.test_client()
        self.headers = {'Authorization': 'Bearer ' + create_access_token(identity='1')}
        self.other = {'Authorization': 'Bearer ' + create_access_token(identity='2')}
        self.publisher = patch.object(monitor, 'dispatch', return_value=SimpleNamespace(id='synthetic-task'))
        self.dispatch = self.publisher.start()
        self.addCleanup(self.publisher.stop)
        self.redis = MemoryRedis()
        self.celery = SimpleNamespace(tasks={name: object() for name in monitor.TASK_ALIASES.values()},
            conf=SimpleNamespace(beat_schedule={'stats': {'task': 'tasks.gdrive.refresh_stats', 'schedule': 300}},
                                 timezone='UTC', task_default_queue='celery', broker_url='redis://unused/0',
                                 result_backend='cache+memory://'),
            control=SimpleNamespace(inspect=lambda **kw: SimpleNamespace(stats=lambda: {'fixture-worker': {}})),
            connection_for_write=lambda **kw: nullcontext(SimpleNamespace(ensure_connection=lambda **kw: None)),
            AsyncResult=lambda task_id: SimpleNamespace(state='SUCCESS'))
        self.addCleanup(patch.stopall)
        patch.object(monitor, 'get_celery', return_value=self.celery).start()
        patch.object(monitor, 'get_redis', return_value=self.redis).start()

    def dispose(self):
        self.batches.metadata.drop_all(self.engine)
        self.users.drop(self.engine, checkfirst=True)
        db.session.remove()
        self.engine.dispose()
        self.context.pop()

    def upload(self, content=b'Name,Lat,Lng,Phone\nAlpha,0,0,00123\nBeta,19,72,00987\n', filename='input.csv', headers=None):
        return self.client.post('/api/ingest/upload', data={'file': (io.BytesIO(content), filename)},
                                headers=self.headers if headers is None else headers)

    def start(self, file_id, mapping=None, **changes):
        data = dict(file_id=file_id, category_type='Retail',
                    column_mapping=({'Name': 'business_name', 'Lat': 'latitude', 'Lng': 'longitude', 'Phone': 'phone'}
                                    if mapping is None else mapping))
        data.update(changes)
        return self.client.post('/api/ingest/start-batch', json=data, headers=self.headers)

    def batch(self, content=None):
        uploaded = self.upload() if content is None else self.upload(content)
        self.assertEqual(uploaded.status_code, 201, uploaded.json)
        started = self.start(uploaded.json['file_id'])
        self.assertEqual(started.status_code, 202, started.json)
        return uploaded.json['file_id'], started.json['batch_id']

    def run_batch(self, batch_id):
        return process_batch(self.engine, self.app.config, batch_id)

    def get_progress(self, batch_id, headers=None):
        return self.client.get('/api/ingest/batch-progress/' + batch_id,
                               headers=self.headers if headers is None else headers)

    def count(self, table):
        with self.engine.connect() as connection:
            return connection.scalar(sa.select(sa.func.count()).select_from(table))

    def test_actual_app_registration_and_authentication(self):
        for path in ['/pipeline-status', '/schedulers/status', '/ingest/batch-progress/' + 'a'*32]:
            self.assertEqual(self.client.get('/api'+path).status_code, 401)
        self.assertEqual(self.upload(headers={}).status_code, 401)
        self.assertEqual(self.client.post('/api/ingest/start-batch', json={}).status_code, 401)
        self.assertEqual(self.client.post('/api/schedulers/trigger/news', json={}).status_code, 401)
        self.assertEqual(self.client.options('/api/ingest/upload').status_code, 200)

    def test_preview_five_rows_and_string_preservation(self):
        response = self.upload(b'\xef\xbb\xbfName,Phone\n' + b'Store,00123\n'*8)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json['headers'], ['Name', 'Phone'])
        self.assertEqual(response.json['sample_rows'], [['Store', '00123']]*5)
        self.assertNotIn('path', response.json)
        self.assertEqual(self.count(self.batches), 0)

    def test_tsv_and_quoted_csv(self):
        self.assertEqual(self.upload(b'Name\tPhone\nStore\t001\n', 'input.tsv').json['headers'], ['Name', 'Phone'])
        self.assertEqual(self.upload(b'Name,Address\n"Store, One","Street\nBlock"\n').json['sample_rows'][0],
                         ['Store, One', 'Street\nBlock'])

    def test_xlsx_stream_preview_and_worker(self):
        workbook = Workbook()
        workbook.active.append(['Name', 'Lat', 'Lng', 'Phone'])
        workbook.active.append(['Store', 0, 0, '00123'])
        stream = io.BytesIO()
        workbook.save(stream)
        response = self.upload(stream.getvalue(), 'book.xlsx')
        self.assertEqual(response.status_code, 201, response.json)
        self.assertEqual(response.json['sample_rows'], [['Store', '0', '0', '00123']])
        batch_id = self.start(response.json['file_id']).json['batch_id']
        self.run_batch(batch_id)
        self.assertEqual(self.get_progress(batch_id).json['valid_count'], 1)

    def test_bad_files_cleaned_up(self):
        for content, filename in [(b'', 'x.csv'), (b'A,A\nx,y', 'x.csv'), (b',B\nx,y', 'x.csv'),
                                  (b'Name\n\xff', 'x.csv'),
                                  (b'not a workbook', 'x.xlsx'), (b'anything', 'x.exe'), (b'x', 'x.xls')]:
            with self.subTest(filename=filename, content=content):
                response = self.upload(content, filename)
                self.assertIn(response.status_code, [400, 415])
        self.assertEqual(list(storage_root(self.app.config).iterdir()), [])

    def test_upload_bounds_and_duplicate_file_fields(self):
        self.app.config['INGESTION_MAX_UPLOAD_BYTES'] = 20
        self.assertEqual(self.upload(b'Name\n' + b'x'*21).status_code, 413)
        self.assertEqual(self.client.post('/api/ingest/upload', headers=self.headers).status_code, 400)

    def test_deleted_user_and_cookie_only_mutations_denied(self):
        deleted = {'Authorization': 'Bearer '+create_access_token(identity='999')}
        self.assertEqual(self.upload(headers=deleted).status_code, 403)
        self.client.set_cookie('access_token_cookie', create_access_token(identity='1'))
        self.assertEqual(self.upload(headers={}).status_code, 401)

    def test_foreign_file_and_path_traversal_denied(self):
        response = self.upload()
        file_id = response.json['file_id']
        self.assertEqual(self.client.post('/api/ingest/start-batch', json=dict(file_id=file_id,
            category_type='retail', column_mapping={'Name': 'business_name'}), headers=self.other).status_code, 404)
        for invalid in ['../file', 'a'*33, None, 123, 'A'*32]:
            self.assertEqual(self.start(invalid).status_code, 400)

    def test_mapping_validation(self):
        file_id = self.upload().json['file_id']
        for mapping in [{}, [], {'Unknown': 'business_name'}, {'Name': 'id'}, {'Name': 'phone'},
                        {'Name': 'business_name', 'Phone': 'business_name'}, {'Name': 5}]:
            self.assertEqual(self.start(file_id, mapping=mapping).status_code, 400)
        self.assertEqual(self.start(file_id, category_type='unsupported').status_code, 400)
        self.assertEqual(self.start(file_id, owner_id='2').status_code, 400)

    def test_json_objects_and_bounds(self):
        for payload in [[], None, 'string']:
            response = self.client.post('/api/ingest/start-batch', data=json.dumps(payload),
                                        content_type='application/json', headers=self.headers)
            self.assertEqual(response.status_code, 400)
        response = self.client.post('/api/ingest/start-batch', data='{'+' '*16385,
                                    content_type='application/json', headers=self.headers)
        self.assertEqual(response.status_code, 413)

    def test_start_is_async_and_repeat_idempotent(self):
        file_id, batch_id = self.batch()
        self.assertEqual(self.count(self.businesses), 0)
        self.assertEqual(self.get_progress(batch_id).json['status'], 'queued')
        repeated = self.start(file_id)
        self.assertEqual(repeated.json['batch_id'], batch_id)
        self.assertEqual(self.count(self.batches), 1)
        self.assertEqual(self.dispatch.call_args.kwargs['queue'], 'heavy_ingestion')
        self.assertEqual(self.start(file_id, category_type='dining').status_code, 409)

    def test_broker_failure_then_retry_same_file(self):
        file_id = self.upload().json['file_id']
        self.dispatch.side_effect = OSError('broker-down-secret')
        failed = self.start(file_id)
        self.assertEqual(failed.status_code, 503)
        self.assertNotIn('broker-down-secret', failed.text)
        with self.engine.connect() as connection:
            record = connection.execute(sa.select(self.batches)).mappings().one()
        self.assertEqual(record['status'], 'QUEUE_FAILED')
        self.dispatch.side_effect = None
        retried = self.start(file_id)
        self.assertEqual(retried.json['batch_id'], record['batch_id'])

    def test_valid_rows_and_quarantine_complete(self):
        content = (b'Name,Lat,Lng,Phone\nValid,0,0,00123\n,1,1,0099\n'
                   b'BadLat,95,1,0044\nPair,1,,0044\nNaN,nan,2,0055\n')
        _, batch_id = self.batch(content)
        self.run_batch(batch_id)
        report = self.get_progress(batch_id).json
        self.assertEqual((report['status'], report['processed_rows'], report['valid_count'], report['quarantine_count']),
                         ('completed', 5, 1, 4))
        self.assertEqual(report['progress_pct'], 100)
        self.assertEqual(self.count(self.businesses), 1)
        self.assertEqual(self.count(self.quarantine), 4)
        with self.engine.connect() as connection:
            row = connection.execute(sa.select(self.businesses)).mappings().one()
        self.assertEqual(row['phone'], '00123')
        self.assertEqual(row['latitude'], 0)
        self.assertEqual(row['longitude'], 0)

    def test_width_mismatch_after_preview_quarantined(self):
        content = b'Name,Lat,Lng,Phone\n' + b'Valid,0,0,001\n'*5 + b'Extra,1,1,001,extra\n'
        _, batch_id = self.batch(content)
        self.run_batch(batch_id)
        self.assertEqual(self.get_progress(batch_id).json['quarantine_count'], 1)

    def test_duplicate_delivery_does_not_duplicate_rows(self):
        file_id, batch_id = self.batch()
        self.run_batch(batch_id)
        self.run_batch(batch_id)
        self.assertEqual(self.count(self.businesses), 2)
        self.assertEqual(self.count(self.quarantine), 0)
        self.dispatch.reset_mock()
        self.assertEqual(self.start(file_id).json['status'], 'completed')
        self.dispatch.assert_not_called()

    def test_chunk_failure_rolls_back_and_retry_resumes(self):
        _, batch_id = self.batch(b'Name,Lat,Lng,Phone\n' + b'Valid,1,1,001\n'*7)
        from tasks import bulk_ingest
        original = bulk_ingest.normalize_row
        calls = 0
        def fail_in_second_chunk(*args):
            nonlocal calls
            calls += 1
            if calls == 4:
                raise RuntimeError('synthetic-row-secret')
            return original(*args)
        with patch.object(bulk_ingest, 'normalize_row', side_effect=fail_in_second_chunk):
            with self.assertRaisesRegex(RuntimeError, 'completed chunks are preserved'):
                self.run_batch(batch_id)
        report = self.get_progress(batch_id).json
        self.assertEqual(report['status'], 'failed')
        self.assertEqual(report['processed_rows'], 2)
        self.assertEqual(self.count(self.businesses), 2)
        self.assertNotIn('synthetic-row-secret', json.dumps(report))
        self.run_batch(batch_id)
        self.assertEqual(self.count(self.businesses), 7)
        self.assertEqual(self.get_progress(batch_id).json['processed_rows'], 7)

    def test_failed_batch_never_reports_100_percent(self):
        _, batch_id = self.batch()
        self.run_batch(batch_id)
        with self.engine.begin() as connection:
            connection.execute(self.batches.update().values(status='FAILED'))
        self.assertLess(self.get_progress(batch_id).json['percent'], 100)

    def test_staged_file_changed_or_missing_fails_without_writes(self):
        for changed in [True, False]:
            file_id, batch_id = self.batch()
            manifest, path = load_upload(file_id, '1', self.app.config)
            if changed:
                path.write_text('Name\nTampered\n')
            else:
                path.unlink()
            with self.assertRaises(RuntimeError):
                self.run_batch(batch_id)
            self.assertEqual(self.get_progress(batch_id).json['status'], 'failed')
        self.assertEqual(self.count(self.businesses), 0)

    def test_progress_and_quarantine_are_owner_scoped(self):
        _, batch_id = self.batch(b'Name,Lat,Lng,Phone\nBad,100,1,001\n')
        self.run_batch(batch_id)
        self.assertEqual(self.get_progress(batch_id, self.other).status_code, 404)
        path = '/api/ingest/quarantine-records/' + batch_id
        self.assertEqual(self.client.get(path, headers=self.other).status_code, 404)
        response = self.client.get(path, headers=self.headers)
        self.assertEqual(response.json['records'][0]['row_number'], 1)
        self.assertIn('Invalid latitude', response.json['records'][0]['error_reason'])

    def test_quarantine_keyset_pagination_and_validation(self):
        _, batch_id = self.batch(b'Name,Lat,Lng,Phone\n' + b'Bad,100,1,001\n'*5)
        self.run_batch(batch_id)
        path = '/api/ingest/quarantine-records/' + batch_id
        first = self.client.get(path+'?limit=2', headers=self.headers).json
        second = self.client.get(path+'?limit=2&after_row=2', headers=self.headers).json
        self.assertEqual([r['row_number'] for r in first['records']], [1, 2])
        self.assertEqual(first['next_after_row'], 2)
        self.assertEqual([r['row_number'] for r in second['records']], [3, 4])
        for query in ['limit=0', 'limit=201', 'limit=2&limit=3', 'after_row=-1', 'owner_id=2']:
            self.assertEqual(self.client.get(path+'?'+query, headers=self.headers).status_code, 400)

    def test_empty_file_with_header_completes(self):
        _, batch_id = self.batch(b'Name,Lat,Lng,Phone\n')
        self.run_batch(batch_id)
        self.assertEqual(self.get_progress(batch_id).json['total_rows'], 0)
        self.assertEqual(self.get_progress(batch_id).json['percent'], 100)

    def test_legacy_multipart_start(self):
        response = self.client.post('/api/ingest/start', data={
            'file': (io.BytesIO(b'Store\nCafe\n'), 'input.csv'), 'archetype': 'Dining',
            'column_mapping': json.dumps({'Store': 'business_name'})}, headers=self.headers)
        self.assertEqual(response.status_code, 202, response.json)
        self.run_batch(response.json['batch_id'])
        self.assertEqual(self.get_progress(response.json['batch_id']).json['imported'], 1)

    def test_missing_schema_returns_service_unavailable_and_creates_nothing(self):
        self.quarantine.drop(self.engine)
        file_id = self.upload().json['file_id']
        response = self.start(file_id)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json['code'], 'schema_not_ready')
        self.assertEqual(self.count(self.batches), 0)
        self.assertFalse(sa.inspect(self.engine).has_table(self.quarantine.name, schema=self.quarantine.schema))

    def test_pipeline_counts_and_frontend_aliases(self):
        _, batch_id = self.batch()
        self.run_batch(batch_id)
        response = self.client.get('/api/pipeline-status', headers=self.headers)
        self.assertEqual(response.status_code, 200, response.json)
        self.assertEqual(response.json['status'], 'success')
        self.assertEqual([s['count'] for s in response.json['stages']], [2]*5)
        self.assertEqual(response.json['total_staged_businesses'], 2)
        self.assertEqual(response.json['health']['database']['status'], 'healthy')

    def test_pipeline_unknown_stages_are_null_and_missing_source_isolated(self):
        self.app.config['PIPELINE_STAGE_SOURCES'] = {
            'raw_ingest': {'schema': 'bronze_staging', 'table': 'raw_businesses'},
            'tier1_clean': {'table': 'missing_table'}}
        response = self.client.get('/api/pipeline-status', headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['raw_ingest'], 0)
        self.assertIsNone(response.json['tier1_clean'])
        self.assertIsNone(response.json['geo_mapped'])
        self.assertEqual(response.json['status'], 'degraded')

    def test_pipeline_predicates_and_unsafe_configuration(self):
        _, batch_id = self.batch()
        self.run_batch(batch_id)
        self.app.config['PIPELINE_STAGE_SOURCES']['raw_ingest'].update(column='business_name', equals='Alpha')
        response = self.client.get('/api/pipeline-status', headers=self.headers)
        self.assertEqual(response.json['raw_ingest'], 1)
        self.app.config['PIPELINE_STAGE_SOURCES']['raw_ingest']['table'] = 'raw_businesses; DROP TABLE users'
        response = self.client.get('/api/pipeline-status', headers=self.headers)
        self.assertIsNone(response.json['raw_ingest'])
        self.assertEqual(self.count(self.users), 2)

    def test_scheduler_status_and_worker_offline(self):
        self.celery.tasks.pop(monitor.TASK_ALIASES['news'])
        response = self.client.get('/api/schedulers/status', headers=self.headers)
        self.assertEqual(response.json['health']['broker']['queue_depth']['heavy_ingestion'], 3)
        self.assertEqual(response.json['health']['workers']['online_workers'], 1)
        self.assertEqual(response.json['schedulers']['news']['status'], 'not_implemented')
        self.assertEqual(response.json['health']['beat']['status'], 'unknown')
        self.celery.control.inspect = lambda **kw: SimpleNamespace(stats=lambda: {})
        self.assertEqual(self.client.get('/api/schedulers/status', headers=self.headers).json['status'], 'degraded')

    def test_scheduler_operator_and_task_allowlist(self):
        path = '/api/schedulers/trigger/refresh-stats-every-5-mins'
        self.assertEqual(self.client.post(path, json={}, headers=self.other).status_code, 403)
        response = self.client.post('/api/schedulers/trigger/celery.backend_cleanup', json={}, headers=self.headers)
        self.assertEqual(response.status_code, 404)
        self.dispatch.assert_not_called()

    def test_scheduler_trigger_both_paths_and_monitor_result(self):
        for path in ['/api/schedulers/trigger/refresh-stats-every-5-mins',
                     '/api/schedulers/refresh-stats-every-5-mins/trigger']:
            response = self.client.post(path, json={}, headers=self.headers)
            self.assertEqual(response.status_code, 202, response.json)
            self.assertEqual(response.json['status'], 'queued')
        response = self.client.get('/api/schedulers/status', headers=self.headers)
        self.assertEqual(response.json['schedulers']['refresh-stats-every-5-mins']['last_run']['state'], 'SUCCESS')

    def test_frontend_empty_json_trigger_body(self):
        response = self.client.post('/api/schedulers/refresh-stats-every-5-mins/trigger',
                                    content_type='application/json', headers=self.headers)
        self.assertEqual(response.status_code, 202, response.json)

    def test_malformed_first_row_is_quarantined(self):
        _, batch_id = self.batch(b'Name,Lat,Lng,Phone\nInvalid,1,1,001,extra\nValid,0,0,001\n')
        self.run_batch(batch_id)
        self.assertEqual(self.get_progress(batch_id).json['quarantine_count'], 1)

    def test_scheduler_scraper_arguments_and_unimplemented(self):
        path = '/api/schedulers/trigger/amazon'
        for data in [{}, {'kwargs': {'search_term': 'rice', 'pages': 100}},
                     {'kwargs': {'search_term': 'rice', 'pages': True}}, {'kwargs': {'task_id': 1}},
                     {'kwargs': {'search_term': 'rice', 'command': 'rm'}}]:
            self.assertEqual(self.client.post(path, json=data, headers=self.headers).status_code, 400)
        response = self.client.post(path, json={'kwargs': {'search_term': 'rice', 'pages': 2}}, headers=self.headers)
        self.assertEqual(response.status_code, 202)
        self.celery.tasks.pop(monitor.TASK_ALIASES['news'])
        self.assertEqual(self.client.post('/api/schedulers/trigger/news', json={}, headers=self.headers).status_code, 503)

    def test_scheduler_broker_failure_is_explicit(self):
        self.dispatch.side_effect = RuntimeError('private-broker-uri')
        response = self.client.post('/api/schedulers/trigger/refresh-stats-every-5-mins', json={}, headers=self.headers)
        self.assertEqual(response.status_code, 503)
        self.assertNotIn('private-broker-uri', response.text)

    @unittest.skipUnless(os.getenv('INGESTION_TEST_PG_PROFILE'), 'Real concurrent row locks require owned PostgreSQL runner')
    def test_postgresql_duplicate_workers_serialize_checkpoints(self):
        _, batch_id = self.batch(b'Name,Lat,Lng,Phone\n' + b'Valid,1,1,001\n'*13)
        settings = dict(self.app.config)
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(process_batch, self.engine, settings, batch_id) for _ in range(2)]
            for future in futures:
                self.assertEqual(future.result(timeout=15)['status'], 'completed')
        self.assertEqual(self.count(self.businesses), 13)
        self.assertEqual(self.get_progress(batch_id).json['processed_rows'], 13)

    @unittest.skipUnless(os.getenv('INGESTION_TEST_PG_PROFILE'), 'Metadata CLI requires owned PostgreSQL runner')
    def test_postgresql_readonly_inspection_cli(self):
        profile = json.loads(Path(os.environ['INGESTION_TEST_PG_PROFILE']).read_text())
        env = {key: value for key, value in os.environ.items() if not key.startswith('PG')}
        env.update(PGHOST='127.0.0.1', PGPORT=str(profile['port']), PGUSER=profile['user'],
                   PGDATABASE=profile['database'], PGPASSFILE=profile['passfile'], PGSSLMODE='disable')
        result = subprocess.run([sys.executable, str(Path(__file__).resolve().parents[1] /
            'scripts/inspect_ingestion_schema.py'), '--expected-database', profile['database']],
            env=env, capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        report = json.loads(result.stdout)
        self.assertTrue(report['schema_contract_compatible'])
        self.assertEqual(report['context']['read_only'], 'on')
        self.assertEqual(self.count(self.businesses), 0)


if __name__ == '__main__':
    unittest.main()
