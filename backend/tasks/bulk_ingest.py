"""Resumable streaming ingestion. Checkpoint, inserts and counters commit together."""
import itertools
import time

from celery import shared_task
import sqlalchemy as sa

from services.ingestion_storage import data_rows, load_upload, normalize_row
from services.ingestion_store import now, require_schema, tables


def process_batch(engine, settings, batch_id):
    require_schema(engine)
    batches, businesses, quarantine = tables(engine.dialect.name)
    with engine.connect() as connection:
        record = connection.execute(sa.select(batches).where(batches.c.batch_id == batch_id)).mappings().first()
    if record is None:
        return {'status': 'not_found'}
    if record['status'] == 'COMPLETED':
        return {'status': 'completed', 'batch_id': batch_id}
    stream_rows = None
    try:
        manifest, path = load_upload(record['file_id'], record['owner_id'], settings, verify=True)
        count_rows = data_rows(path)
        try:
            total = sum(1 for _ in count_rows)
        finally:
            count_rows.close()
        with engine.begin() as connection:
            connection.execute(batches.update().where(batches.c.batch_id == batch_id,
                batches.c.status != 'COMPLETED').values(status='PROCESSING', total_rows=total,
                                                       error_message=None, updated_at=now()))
        stream_rows = data_rows(path)
        stream = enumerate(stream_rows, 1)
        chunk_size = min(max(int(settings.get('INGESTION_CHUNK_SIZE', 2500)), 1), 2500)
        while True:
            chunk = list(itertools.islice(stream, chunk_size))
            if not chunk:
                break
            with engine.begin() as connection:
                if engine.dialect.name == 'sqlite':
                    connection.exec_driver_sql('BEGIN IMMEDIATE')
                else:
                    connection.exec_driver_sql("SET LOCAL lock_timeout = '5s'")
                    connection.exec_driver_sql("SET LOCAL statement_timeout = '30s'")
                current = connection.execute(sa.select(batches).where(
                    batches.c.batch_id == batch_id).with_for_update()).mappings().one()
                if current['status'] == 'COMPLETED':
                    return {'status': 'completed', 'batch_id': batch_id}
                good, bad = [], []
                for number, row in chunk:
                    if number <= current['processed_rows']:
                        continue
                    values, reason = normalize_row(row, manifest['headers'], record['column_mapping'])
                    raw = dict(batch_id=batch_id, row_number=number, raw_data=row)
                    if reason:
                        bad.append(dict(raw, error_reason=reason))
                    else:
                        # Equal insert keys for executemany, including unmapped optional fields.
                        fields = {c.name: None for c in businesses.c if c.name not in
                                  {'id', 'batch_id', 'row_number', 'raw_data', 'category_type'}}
                        fields.update(values)
                        good.append(dict(raw, category_type=record['category_type'], **fields))
                if good:
                    connection.execute(businesses.insert(), good)
                if bad:
                    connection.execute(quarantine.insert(), bad)
                connection.execute(batches.update().where(batches.c.batch_id == batch_id).values(
                    processed_rows=current['processed_rows'] + len(good) + len(bad),
                    valid_count=current['valid_count'] + len(good),
                    quarantine_count=current['quarantine_count'] + len(bad), updated_at=now()))
            time.sleep(float(settings.get('INGESTION_CHUNK_COOLDOWN', 0.25)))
        with engine.begin() as connection:
            connection.execute(batches.update().where(batches.c.batch_id == batch_id,
                batches.c.processed_rows == total).values(status='COMPLETED', updated_at=now()))
        return {'status': 'completed', 'batch_id': batch_id}
    except Exception:
        # No raw input, credentials, SQL parameters, or customer data in task results.
        with engine.begin() as connection:
            connection.execute(batches.update().where(batches.c.batch_id == batch_id,
                batches.c.status != 'COMPLETED').values(status='FAILED',
                error_message='Ingestion failed; completed chunks are preserved and can be retried', updated_at=now()))
        raise RuntimeError('Batch ingestion failed; completed chunks are preserved') from None
    finally:
        if stream_rows is not None:
            stream_rows.close()


@shared_task(name='tasks.bulk_ingest.stream_chunked_ingest', bind=True,
             ignore_result=False, track_started=True, acks_late=True, reject_on_worker_lost=True)
def stream_chunked_ingest(self, batch_id):
    from config import Config
    engine = sa.create_engine(Config.SQLALCHEMY_DATABASE_URI, **Config.SQLALCHEMY_ENGINE_OPTIONS)
    settings = {key: getattr(Config, key) for key in dir(Config) if key.startswith('INGESTION_')}
    try:
        return process_batch(engine, settings, batch_id)
    finally:
        engine.dispose()
