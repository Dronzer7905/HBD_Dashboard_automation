"""Actual Celery worker/message round trip, using the in-memory transport.

The worker runs the real task (not eager mode), opens its own engine, reads the
shared staged file and updates the same DB observed through the HTTP API.
"""
import sys
import unittest
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

from celery import Celery
from celery.contrib.testing.worker import start_worker

import test_ingestion as fixture


class WorkerIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixture.IngestionTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.worker_app = Celery('bg113-worker-integration', broker='memory://', backend='cache+memory://')
        self.worker_app.conf.update(task_always_eager=False, task_ignore_result=True,
            task_track_started=True, result_expires=1200,
            task_routes={'tasks.bulk_ingest.*': {'queue': 'heavy_ingestion'}},
            imports=['tasks.bulk_ingest'])
        self.worker_app.loader.import_default_modules()
        self.addCleanup(self.worker_app.close)
        config = ModuleType('config')
        settings = {k: v for k, v in self.fixture.app.config.items() if k.startswith('INGESTION_')}
        config.Config = SimpleNamespace(SQLALCHEMY_DATABASE_URI=self.fixture.app.config['SQLALCHEMY_DATABASE_URI'],
                                        SQLALCHEMY_ENGINE_OPTIONS={}, **settings)
        patch.dict(sys.modules, {'config': config}).start()
        self.addCleanup(patch.stopall)
        patch.object(fixture.monitor, 'get_celery', return_value=self.worker_app).start()
        # Restore the actual publisher; the fixture normally replaces only the broker boundary.
        self.fixture.publisher.stop()

    def test_real_async_task_updates_api_progress_and_quarantine(self):
        with start_worker(self.worker_app, pool='solo', concurrency=1, queues=['heavy_ingestion'],
                          perform_ping_check=False, shutdown_timeout=10):
            _, batch_id = self.fixture.batch(b'Name,Lat,Lng,Phone\nStore,0,0,001\nBad,95,1,002\n')
            report = self.fixture.get_progress(batch_id).json
            result = self.worker_app.AsyncResult(report['task_id']).get(timeout=12)
            self.assertEqual(result['status'], 'completed')
            report = self.fixture.get_progress(batch_id).json
            self.assertEqual((report['status'], report['valid_count'], report['quarantine_count']), ('completed', 1, 1))

    def test_actual_task_failure_is_persisted_and_result_is_sanitized(self):
        file_id = self.fixture.upload().json['file_id']
        _, path = fixture.load_upload(file_id, '1', self.fixture.app.config)
        path.unlink()
        # Start requires the file to exist, so delete after the API has queued it.
        path.write_text('Name,Lat,Lng,Phone\nSecretChangedRow,1,1,001\n')
        started = self.fixture.start(file_id)
        self.assertEqual(started.status_code, 202)
        with start_worker(self.worker_app, pool='solo', concurrency=1, queues=['heavy_ingestion'],
                          perform_ping_check=False, shutdown_timeout=10):
            task_id = started.json['task_id']
            with self.assertRaisesRegex(RuntimeError, 'completed chunks are preserved'):
                self.worker_app.AsyncResult(task_id).get(timeout=12)
            report = self.fixture.get_progress(started.json['batch_id']).json
            self.assertEqual(report['status'], 'failed')
            self.assertNotIn('SecretChangedRow', str(self.worker_app.AsyncResult(task_id).result))


if __name__ == '__main__':
    unittest.main()
