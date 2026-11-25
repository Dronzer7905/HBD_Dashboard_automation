"""Read-only pipeline metrics and bounded Celery/Redis scheduler controls."""
import json
import re
import uuid

import redis
import sqlalchemy as sa

from services.ingestion_storage import IngestionError
from services.ingestion_store import now


STAGES = ('raw_ingest', 'tier1_clean', 'geo_mapped', 'catalog_mapped', 'live_ready')
DEFAULT_SOURCES = {
    'raw_ingest': {'schema': 'bronze_staging', 'table': 'raw_businesses'},
    'tier1_clean': {'schema': 'silver_clean', 'table': 'tier1_master_clean'},
    # Semantics of these stages must come from verified schema, never guessed
    # from the presence of raw coordinates or a non-empty category string.
    'geo_mapped': None, 'catalog_mapped': None, 'live_ready': None,
}
TASK_ALIASES = {
    'news': 'tasks.news.crawl_local_news_feeds',
    'quick-commerce': 'tasks.products_task.crawl_quick_commerce_prices',
    'zomato': 'tasks.listings_task.sync_restaurant_menus',
    'gdrive': 'tasks.gdrive_task.sync_drive_dumps',
    'amazon': 'tasks.products.scrape_amazon',
    'dmart': 'tasks.products.scrape_dmart',
    'indiamart': 'tasks.products.scrape_indiamart',
    'blinkit': 'tasks.products.scrape_blinkit',
    'refresh-stats-every-5-mins': 'tasks.gdrive.refresh_stats',
    'refresh-top-cities-every-24-hours': 'tasks.refresh_top_cities.update_business_counts',
    'auto-sync-locations-daily': 'tasks.refresh_locations.sync_new_locations',
    'auto-clean-master-twice-weekly': 'tasks.auto_clean_pipeline.auto_clean_master_table',
    'auto-clean-product-twice-weekly': 'tasks.auto_clean_pipeline.auto_clean_product_master',
    'auto-route-tiers-twice-weekly': 'tasks.auto_clean_pipeline.auto_route_item_tiers',
}


def get_celery():
    try:
        from celery_app import celery
    except Exception:
        raise IngestionError('Celery configuration could not be initialized', 503, 'worker_configuration_error') from None
    return celery


def get_redis(celery):
    if not celery.conf.broker_url or not celery.conf.broker_url.startswith(('redis://', 'rediss://')):
        raise IngestionError('A Redis broker must be configured', 503, 'broker_unavailable')
    return redis.Redis.from_url(celery.conf.broker_url, socket_connect_timeout=2,
                               socket_timeout=2, decode_responses=True)


def bounded_connection(celery):
    # Avoid the existing broker's 120-second connection/retry defaults in HTTP.
    return celery.connection_for_write(connect_timeout=2, transport_options={
        'socket_connect_timeout': 2, 'socket_timeout': 2, 'retry_on_timeout': False,
        'max_retries': 0})


def dispatch(task_name, *, args=None, kwargs=None, task_id=None, queue=None):
    celery = get_celery()
    with bounded_connection(celery) as connection:
        return celery.send_task(task_name, args=args or [], kwargs=kwargs or {}, task_id=task_id,
                                queue=queue, connection=connection, retry=False, ignore_result=False)


def pipeline_status(engine, settings):
    sources = settings.get('PIPELINE_STAGE_SOURCES') or DEFAULT_SOURCES
    if isinstance(sources, str):
        try:
            sources = json.loads(sources)
        except ValueError:
            raise IngestionError('PIPELINE_STAGE_SOURCES must be a JSON object', 503, 'configuration_error') from None
    if not isinstance(sources, dict) or sources.keys() - set(STAGES):
        raise IngestionError('Invalid pipeline stage configuration', 503, 'configuration_error')
    stages, counts = [], {}
    database_ok = False
    pool = engine.pool
    pool_health = {'status': 'unavailable'}
    try:
        with engine.connect() as connection:
            connection.execute(sa.select(sa.literal(1)))
            database_ok = True
        pool_health = dict(status='healthy', checked_out=pool.checkedout() if hasattr(pool, 'checkedout') else None,
                           size=pool.size() if callable(getattr(pool, 'size', None)) else None,
                           overflow=pool.overflow() if hasattr(pool, 'overflow') else None)
    except sa.exc.SQLAlchemyError:
        pass
    for key in STAGES:
        source = sources.get(key)
        count, error = None, None
        if source is None:
            error = 'source_not_configured'
        elif not database_ok:
            error = 'database_unavailable'
        else:
            try:
                if not isinstance(source, dict) or source.keys() - {'schema', 'table', 'column', 'equals', 'not_null'}:
                    raise ValueError()
                for identifier in [source.get('schema'), source.get('table'), source.get('column')]:
                    if identifier is not None and (not isinstance(identifier, str) or
                            not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,62}', identifier)):
                        raise ValueError()
                if not source.get('table') or ('equals' in source and 'not_null' in source):
                    raise ValueError()
                if ('equals' in source or 'not_null' in source) and not source.get('column'):
                    raise ValueError()
                if source.get('not_null', True) is not True:
                    raise ValueError()
                columns = [sa.column(source['column'])] if source.get('column') else []
                table = sa.table(source['table'], *columns,
                                 schema=None if engine.dialect.name == 'sqlite' else source.get('schema'))
                statement = sa.select(sa.func.count()).select_from(table)
                if 'equals' in source:
                    statement = statement.where(table.c[source['column']] == source['equals'])
                elif source.get('not_null'):
                    statement = statement.where(table.c[source['column']].is_not(None))
                with engine.begin() as connection:
                    if engine.dialect.name == 'postgresql':
                        connection.exec_driver_sql('SET TRANSACTION READ ONLY')
                        connection.execute(sa.text("SELECT set_config('statement_timeout', :timeout, true)"),
                                           {'timeout': str(min(max(int(settings.get('PIPELINE_QUERY_TIMEOUT_MS', 2000)), 100), 10000))})
                    count = int(connection.scalar(statement))
            except (ValueError, TypeError, KeyError):
                error = 'invalid_source_configuration'
            except sa.exc.SQLAlchemyError:
                error = 'source_unavailable'
        counts[key] = count
        stages.append(dict(key=key, count=count, available=count is not None, error=error,
                           source=source if isinstance(source, dict) else None))
    health = {'database': pool_health, **runtime_health()}
    healthy = all(v is not None for v in counts.values()) and all(
        health[key]['status'] == 'healthy' for key in ['database', 'broker', 'workers'])
    return dict(status='success' if healthy else 'degraded',
                **counts, total_staged_businesses=counts['raw_ingest'], stages=stages,
                health=health, updated_at=now().isoformat())


def worker_health(celery):
    try:
        with bounded_connection(celery) as connection:
            connection.ensure_connection(max_retries=0)
            replies = celery.control.inspect(timeout=1, connection=connection).stats() or {}
        return {'status': 'healthy' if replies else 'offline', 'online_workers': len(replies),
                'workers': sorted(replies)}
    except Exception:
        return {'status': 'unavailable', 'online_workers': None, 'workers': []}


def runtime_health():
    try:
        celery = get_celery()
    except IngestionError:
        return {'broker': {'status': 'unavailable', 'queue_depth': None},
                'workers': {'status': 'unavailable', 'online_workers': None, 'workers': []}}
    broker = {'status': 'unavailable', 'queue_depth': None}
    try:
        store = get_redis(celery)
        store.ping()
        queues = {celery.conf.task_default_queue or 'celery', 'heavy_ingestion'}
        broker = {'status': 'healthy', 'queue_depth': {q: store.llen(q) for q in sorted(queues)}}
    except Exception:
        pass
    return {'broker': broker, 'workers': worker_health(celery)}


def schedulers_status():
    celery = get_celery()
    workers = worker_health(celery)
    broker_health = {'status': 'unavailable', 'queue_depth': None}
    store = None
    try:
        store = get_redis(celery)
        store.ping()
        queues = {celery.conf.task_default_queue or 'celery', 'heavy_ingestion'}
        broker_health = {'status': 'healthy', 'queue_depth': {q: store.llen(q) for q in sorted(queues)}}
    except Exception:
        store = None
    schedules = celery.conf.beat_schedule or {}
    result = {}
    for alias, name in TASK_ALIASES.items():
        registered = name in celery.tasks
        schedule = next((entry for entry in schedules.values() if entry['task'] == name), None)
        last_run = None
        if store is not None:
            try:
                task_id = store.get('hbd:scheduler:last:' + name)
                if task_id:
                    state = result_state(celery, task_id)
                    last_run = dict(task_id=task_id, state='UNKNOWN_OR_QUEUED' if state == 'PENDING' else state,
                                    error='Worker task failed' if state == 'FAILURE' else None)
            except Exception:
                last_run = {'state': 'UNAVAILABLE'}
        result[alias] = dict(task_name=name, registered=registered, enabled=registered,
            healthy=registered and workers['status'] == 'healthy' and broker_health['status'] == 'healthy',
            status='available' if registered else 'not_implemented',
            schedule=str(schedule['schedule']) if schedule else None,
            schedule_configured=schedule is not None, last_run=last_run)
    return dict(status='success' if broker_health['status'] == 'healthy' and workers['status'] == 'healthy'
                else 'degraded', schedulers=result, health={'broker': broker_health, 'workers': workers,
                'beat': {'status': 'unknown', 'message': 'Configuration is visible; Beat heartbeat is not instrumented'}},
                timezone=celery.conf.timezone, updated_at=now().isoformat())


def result_state(celery, task_id):
    url = celery.conf.result_backend
    if url and url.startswith(('redis://', 'rediss://')):
        # An independent client preserves the HTTP timeout even if the worker's
        # backend uses long retries. Respect Celery's configured key prefix.
        client = redis.Redis.from_url(url, socket_connect_timeout=2, socket_timeout=2)
        try:
            raw = client.get(celery.backend.get_key_for_task(task_id))
            return json.loads(raw)['status'] if raw else 'PENDING'
        finally:
            client.close()
    if url and url.startswith('cache+memory://'):
        return celery.AsyncResult(task_id).state
    return 'UNAVAILABLE'


def scheduler_arguments(name, body):
    if not isinstance(body, dict) or body.keys() - {'kwargs'} or not isinstance(body.get('kwargs', {}), dict):
        raise IngestionError('Expected an optional kwargs object')
    kwargs = body.get('kwargs', {})
    allowed = {}
    if name == 'tasks.products.scrape_amazon':
        allowed = {'search_term': str, 'pages': int}
    elif name == 'tasks.products.scrape_dmart':
        allowed = {'search_term': str, 'mode': str, 'pincodes': str, 'max_categories': int}
    elif name == 'tasks.products.scrape_indiamart':
        allowed = {'search_term': str, 'pages': int}
    elif name == 'tasks.products.scrape_blinkit':
        allowed = {'pincode': str, 'mode': str, 'max_categories': int, 'resume': bool}
    if kwargs.keys() - allowed.keys():
        raise IngestionError('Unsupported scheduler task arguments')
    for key, value in kwargs.items():
        if type(value) is not allowed[key]:
            raise IngestionError(f'Invalid {key}')
        if isinstance(value, str) and (not value.strip() or len(value) > 255 or '\x00' in value):
            raise IngestionError(f'Invalid {key}')
        if type(value) is int and not 1 <= value <= (20 if key == 'pages' else 100):
            raise IngestionError(f'{key} is out of range')
    if name.endswith('scrape_blinkit'):
        if 'pincode' in kwargs and not re.fullmatch(r'[1-9][0-9]{5}', kwargs['pincode']):
            raise IngestionError('pincode must be six digits')
        if kwargs.get('mode', 'full') not in {'full', 'categories', 'incremental'}:
            raise IngestionError('Unsupported Blinkit mode')
    if 'search_term' in allowed and 'search_term' not in kwargs:
        raise IngestionError('search_term is required for this scraper')
    if name.endswith(('scrape_dmart', 'scrape_indiamart', 'scrape_blinkit')):
        kwargs = dict(kwargs, task_id=None)
    return kwargs


def trigger_scheduler(task_name, body):
    name = TASK_ALIASES.get(task_name, task_name)
    if name not in TASK_ALIASES.values():
        raise IngestionError('Unknown scheduler task', 404, 'task_not_found')
    celery = get_celery()
    if name not in celery.tasks:
        raise IngestionError('This worker task has not been implemented or registered', 503, 'task_unavailable')
    kwargs = scheduler_arguments(name, body)
    task_id = str(uuid.uuid4())
    store = get_redis(celery)
    try:
        store.ping()
        dispatch(name, kwargs=kwargs, task_id=task_id)
        try:
            store.set('hbd:scheduler:last:' + name, task_id, ex=86400)
            monitoring = True
        except redis.RedisError:
            # Publishing already succeeded: never report failure and prompt a duplicate.
            monitoring = False
    except Exception:
        raise IngestionError('Task broker is unavailable; trigger was not confirmed', 503, 'broker_unavailable') from None
    return dict(status='queued', task_name=name, task_id=task_id, monitoring_available=monitoring)
