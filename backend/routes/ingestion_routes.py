"""BG-1.8..1.10 / BG-1.13 authenticated ingestion and monitoring APIs."""
import json
import uuid
from functools import wraps

from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required
import sqlalchemy as sa
from werkzeug.exceptions import BadRequest, RequestEntityTooLarge, UnsupportedMediaType

from extensions import db
from services import ingestion_monitoring as monitor
from services.ingestion_storage import (CATEGORY_TYPES, IngestionError, checked_id, load_upload,
                                        save_upload, validate_mapping)
from services.ingestion_store import now, progress, require_schema, tables


ingestion_bp = Blueprint('ingestion', __name__)


def api_errors(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except IngestionError as error:
            return jsonify(status='error', code=error.code, message=str(error)), error.status
        except RequestEntityTooLarge:
            return jsonify(status='error', code='upload_too_large', message='Request exceeds the configured size limit'), 413
        except (BadRequest, UnsupportedMediaType, ValueError, TypeError):
            return jsonify(status='error', code='invalid_request', message='Invalid request payload'), 400
        except sa.exc.SQLAlchemyError:
            current_app.logger.error('Ingestion database operation failed; confidential parameters withheld')
            return jsonify(status='error', code='schema_or_database_unavailable',
                           message='Ingestion database is unavailable or its schema requires verification'), 503
        except Exception:
            current_app.logger.error('Ingestion operation failed; confidential details withheld')
            return jsonify(status='error', code='ingestion_failure', message='Ingestion operation failed'), 500
    return wrapped


def actor():
    identity = get_jwt_identity()
    if (not isinstance(identity, str) or not identity.isascii() or not identity.isdecimal()
            or len(identity) > 10 or not 0 < int(identity) <= 2147483647):
        raise IngestionError('A current user identity is required', 403, 'forbidden')
    users = sa.table('users', sa.column('id'), schema='public' if db.engine.dialect.name == 'postgresql' else None)
    with db.engine.connect() as connection:
        if connection.scalar(sa.select(users.c.id).where(users.c.id == int(identity))) is None:
            raise IngestionError('A current user identity is required', 403, 'forbidden')
    return identity


def json_body(allow_empty=False):
    if not request.is_json:
        if allow_empty and not request.stream.read(1):
            return {}
        raise IngestionError('A JSON object is required')
    raw = request.stream.read(16385)
    if len(raw) > 16384:
        raise IngestionError('JSON exceeds 16 KiB', 413)
    if allow_empty and not raw:
        return {}
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise IngestionError('A JSON object is required')
    return data


def upload_file(owner):
    # Set before parsing multipart, and enforce actual file bytes again while copying.
    request.max_content_length = int(current_app.config.get('INGESTION_MAX_UPLOAD_BYTES', 100 * 1024 * 1024)) + 65536
    if set(request.files) != {'file'} or len(request.files.getlist('file')) != 1:
        raise IngestionError('Exactly one multipart file field is required')
    return save_upload(request.files['file'], owner, current_app.config)


@ingestion_bp.get('/pipeline-status')
@jwt_required()
@api_errors
def get_pipeline_status():
    return jsonify(monitor.pipeline_status(db.engine, current_app.config))


@ingestion_bp.get('/schedulers/status')
@jwt_required()
@api_errors
def get_schedulers_status():
    return jsonify(monitor.schedulers_status())


@ingestion_bp.post('/schedulers/trigger/<task_name>')
@ingestion_bp.post('/schedulers/<task_name>/trigger')
@jwt_required(locations=['headers'])
@api_errors
def trigger_scheduler(task_name):
    owner = actor()
    operators = str(current_app.config.get('SCHEDULER_OPERATOR_IDS', '')).split(',')
    if owner not in {value.strip() for value in operators}:
        raise IngestionError('Scheduler operator permission is required', 403, 'forbidden')
    body = json_body(allow_empty=True)
    return jsonify(monitor.trigger_scheduler(task_name, body)), 202


@ingestion_bp.post('/ingest/upload')
@jwt_required(locations=['headers'])
@api_errors
def upload():
    return jsonify(status='success', **upload_file(actor())), 201


def start_batch(data, owner):
    if data.keys() - {'file_id', 'category_type', 'column_mapping'}:
        raise IngestionError('Unknown batch request fields')
    file_id = checked_id(data.get('file_id'))
    category_type = data.get('category_type')
    if not isinstance(category_type, str) or category_type.lower() not in CATEGORY_TYPES:
        raise IngestionError('Unsupported category_type')
    category_type = category_type.lower()
    manifest, _ = load_upload(file_id, owner, current_app.config)
    mapping = validate_mapping(data.get('column_mapping'), manifest['headers'])
    require_schema(db.engine)
    batches = tables(db.engine.dialect.name)[0]
    batch_id, task_id = uuid.uuid4().hex, str(uuid.uuid4())
    try:
        with db.engine.begin() as connection:
            existing = connection.execute(sa.select(batches).where(batches.c.file_id == file_id).with_for_update()).mappings().first()
            if existing:
                if (existing['owner_id'] != owner or existing['column_mapping'] != mapping
                        or existing['category_type'] != category_type):
                    raise IngestionError('This upload already belongs to a batch with different settings', 409, 'batch_conflict')
                batch_id, task_id = existing['batch_id'], existing['task_id']
                if existing['status'] in {'PROCESSING', 'COMPLETED'}:
                    return dict(status=existing['status'].lower(), batch_id=batch_id, task_id=task_id)
                connection.execute(batches.update().where(batches.c.batch_id == batch_id).values(
                    status='QUEUED', error_message=None, updated_at=now()))
            else:
                connection.execute(batches.insert().values(batch_id=batch_id, file_id=file_id,
                    owner_id=owner, category_type=category_type, column_mapping=mapping, status='QUEUED',
                    task_id=task_id, created_at=now(), updated_at=now()))
    except sa.exc.IntegrityError:
        raise IngestionError('Concurrent batch request; retry the same request', 409, 'batch_conflict') from None
    try:
        monitor.dispatch('tasks.bulk_ingest.stream_chunked_ingest', args=[batch_id],
                         task_id=task_id, queue='heavy_ingestion')
    except Exception:
        with db.engine.begin() as connection:
            connection.execute(batches.update().where(batches.c.batch_id == batch_id,
                batches.c.status == 'QUEUED').values(status='QUEUE_FAILED', updated_at=now(),
                error_message='Task publication was not confirmed; retry start-batch with the same file_id'))
        raise IngestionError('Task publication was not confirmed; retry with the same file_id', 503, 'broker_unavailable') from None
    return dict(status='started', batch_id=batch_id, task_id=task_id)


@ingestion_bp.post('/ingest/start-batch')
@jwt_required(locations=['headers'])
@api_errors
def start():
    return jsonify(start_batch(json_body(), actor())), 202


@ingestion_bp.post('/ingest/start')
@jwt_required(locations=['headers'])
@api_errors
def start_multipart():
    owner = actor()
    preview = upload_file(owner)
    if set(request.form) - {'archetype', 'category_type', 'column_mapping'}:
        raise IngestionError('Unknown multipart fields')
    data = dict(file_id=preview['file_id'], category_type=request.form.get('category_type') or request.form.get('archetype'),
                column_mapping=json.loads(request.form.get('column_mapping', '{}')))
    return jsonify(start_batch(data, owner)), 202


def owned_batch(batch_id):
    checked_id(batch_id, 'batch_id')
    owner = actor()
    batches = tables(db.engine.dialect.name)[0]
    with db.engine.connect() as connection:
        record = connection.execute(sa.select(batches).where(batches.c.batch_id == batch_id,
                                                            batches.c.owner_id == owner)).mappings().first()
    if record is None:
        raise IngestionError('Batch not found', 404, 'batch_not_found')
    return record


@ingestion_bp.get('/ingest/batch-progress/<batch_id>')
@jwt_required()
@api_errors
def batch_progress(batch_id):
    return jsonify(progress(owned_batch(batch_id)))


@ingestion_bp.get('/ingest/quarantine-records/<batch_id>')
@jwt_required()
@api_errors
def quarantine_records(batch_id):
    owned_batch(batch_id)
    if set(request.args) - {'limit', 'after_row'} or any(len(request.args.getlist(k)) != 1 for k in request.args):
        raise IngestionError('Unknown or repeated query parameters')
    limit, after = request.args.get('limit', '50'), request.args.get('after_row', '0')
    if (not limit.isascii() or not limit.isdecimal() or len(limit) > 3 or not 1 <= int(limit) <= 200
            or not after.isascii() or not after.isdecimal() or len(after) > 12):
        raise IngestionError('Invalid quarantine pagination')
    table = tables(db.engine.dialect.name)[2]
    with db.engine.connect() as connection:
        rows = connection.execute(sa.select(table.c.row_number, table.c.raw_data, table.c.error_reason).where(
            table.c.batch_id == batch_id, table.c.row_number > int(after)).order_by(table.c.row_number).limit(int(limit)+1)).mappings().all()
    return jsonify(batch_id=batch_id, records=[dict(row) for row in rows[:int(limit)]],
                   next_after_row=rows[int(limit)-1]['row_number'] if len(rows) > int(limit) else None)
