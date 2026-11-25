"""Authenticated BG-1.11 APIs; existing category-mapping routes stay unchanged."""

import json
from functools import wraps

from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import get_jwt_identity, get_jwt_request_location, jwt_required
from werkzeug.exceptions import BadRequest, UnsupportedMediaType

from extensions import db
from model.user import User
from services import mapping_service as service
from services import business_product_mapping_service as bpm_service


mapping_bp = Blueprint('mapping_bp', __name__)


def api_errors(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except service.MappingError as error:
            db.session.rollback()
            return jsonify(status='error', code=error.code, message=str(error)), error.status
        except (BadRequest, UnsupportedMediaType):
            db.session.rollback()
            return jsonify(status='error', code='invalid_json', message='A JSON object is required'), 400
        except Exception:
            db.session.rollback()
            # Do not log raw SQL exception parameters or confidential source data.
            current_app.logger.error('BG-1.11 mapping operation failed; transaction rolled back')
            return jsonify(status='error', code='mapping_failure', message='Category mapping operation failed'), 500
    return wrapped


def body():
    if request.content_length is not None and request.content_length > 16_384:
        raise service.MappingError('Payload exceeds 16 KiB', 413)
    # Bound reads even when Content-Length is absent (streamed requests).
    raw = request.stream.read(16_385)
    if len(raw) > 16_384:
        raise service.MappingError('Payload exceeds 16 KiB', 413)
    if not request.is_json:
        raise service.MappingError('A JSON object is required')
    try:
        data = json.loads(raw)
    except (ValueError, UnicodeError):
        raise service.MappingError('A JSON object is required') from None
    if not isinstance(data, dict):
        raise service.MappingError('A JSON object is required')
    return data


def query_integer(name, default, maximum):
    value = request.args.get(name)
    if value is None:
        return default
    if not value.isascii() or not value.isdecimal() or len(value) > 10:
        raise service.MappingError(f'{name} must be a positive integer')
    return service.integer(int(value), name, maximum)


@mapping_bp.route('/categories', methods=['GET'])
@jwt_required()
@api_errors
def get_categories():
    allowed = {'page', 'limit', 'category_page', 'category_limit', 'platform_name',
               'search', 'status', 'parent_id', 'product_page', 'product_limit',
               'product_search', 'marketplace_name', 'product_parent_id', 'product_level'}
    if request.args.keys() - allowed or any(len(request.args.getlist(k)) != 1 for k in request.args):
        raise service.MappingError('Unknown or repeated query parameters')
    kwargs = {
        'page': query_integer('page', 1, 100_000),
        'limit': query_integer('limit', 50, 200),
        'category_page': query_integer('category_page', 1, 100_000),
        'category_limit': query_integer('category_limit', 100, 200),
        'product_page': query_integer('product_page', 1, 100_000),
        'product_limit': query_integer('product_limit', 50, 200),
        'status': request.args.get('status', 'unmapped'),
    }
    for name in ('platform_name', 'search'):
        if name in request.args:
            value = service.text_value(request.args[name], name, 100 if name == 'platform_name' else 255)
            kwargs['platform' if name == 'platform_name' else name] = value
    if 'parent_id' in request.args:
        kwargs['parent_id'] = 'root' if request.args['parent_id'] == 'root' else query_integer('parent_id', None, 2_147_483_647)
    for name, argument, maximum in [('product_search', 'product_search', 255),
                                     ('marketplace_name', 'marketplace', 100)]:
        if name in request.args:
            kwargs[argument] = service.text_value(request.args[name], name, maximum)
    if 'product_parent_id' in request.args:
        kwargs['product_parent_id'] = ('root' if request.args['product_parent_id'] == 'root' else
                                       query_integer('product_parent_id', None, 2_147_483_647))
    if 'product_level' in request.args:
        kwargs['product_level'] = query_integer('product_level', None, 10)
    return jsonify(status='success', data=service.categories(**kwargs))


def authorized_user(setting):
    identity = get_jwt_identity()
    if not isinstance(identity, str) or not identity.isascii() or not identity.isdecimal() or len(identity) > 10:
        raise service.MappingError('A current user identity is required', 403, 'forbidden')
    actor_id = int(identity)
    configured = current_app.config.get(setting, '')
    approvers = {str(value).strip() for value in configured.split(',')} if isinstance(configured, str) else set()
    if identity not in approvers or not 1 <= actor_id <= 2_147_483_647:
        raise service.MappingError('Category mapping approval permission is required', 403, 'forbidden')
    if db.session.get(User, actor_id) is None:
        raise service.MappingError('A current user identity is required', 403, 'forbidden')
    return identity


@mapping_bp.route('/map-category', methods=['POST'])
@jwt_required(locations=['headers'])
@api_errors
def map_category():
    identity = authorized_user('MAPPING_APPROVER_IDS')
    result, changed = service.save_mapping(body(), actor=identity)
    return jsonify(status='success', data=result, changed=changed)


@mapping_bp.route('/auto-map', methods=['POST'])
@jwt_required()
@api_errors
def auto_map():
    data = body()
    actor = None
    if data.get('dry_run') is False:
        if get_jwt_request_location() != 'headers':
            raise service.MappingError('Bearer authentication is required for persistence', 401, 'unauthorized')
        actor = authorized_user('MAPPING_ADMIN_IDS')
    result = service.auto_map(data, actor=actor)
    if result['transaction_failed']:
        return jsonify(status='error', code='mapping_failure', **result), 500
    return jsonify(status='success', **result)


# ═══════════════════════════════════════════════════════════════════════
#  BUSINESS CATEGORY <-> PRODUCT CATEGORY MAPPING & REPORTING ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════

@mapping_bp.route('/business-products', methods=['GET'])
@jwt_required()
@api_errors
def get_business_products():
    """List paginated active associations with rich details."""
    page = query_integer('page', 1, 100_000)
    limit = query_integer('limit', 50, 200)
    b_id = request.args.get('business_category_id')
    sub_id = request.args.get('business_subcategory_id')
    marketplace = request.args.get('marketplace_name')
    search = request.args.get('search')
    result = bpm_service.get_business_product_mappings(
        page=page, limit=limit, business_id=b_id,
        subcategory_id=sub_id, marketplace=marketplace, search=search
    )
    return jsonify(status='success', data=result)


@mapping_bp.route('/business-products/stats', methods=['GET'])
@jwt_required()
@api_errors
def get_business_products_stats():
    """Executive KPI summary and platform breakdown."""
    stats = bpm_service.get_business_product_stats()
    return jsonify(status='success', data=stats)


@mapping_bp.route('/business-products/auto-map', methods=['POST'])
@jwt_required()
@api_errors
def auto_map_business_products():
    """Discover candidate product mappings for business subcategories."""
    data = body()
    b_id = data.get('business_category_id')
    marketplace = data.get('marketplace_name')
    limit = int(data.get('limit', 100))
    threshold = float(data.get('threshold', 0.75))
    suggestions = bpm_service.auto_map_business_to_products(
        business_id=b_id, marketplace=marketplace, limit=limit, threshold=threshold
    )
    return jsonify(status='success', count=len(suggestions), data=suggestions)


@mapping_bp.route('/business-products/approve', methods=['POST'])
@jwt_required(locations=['headers'])
@api_errors
def approve_business_products():
    """Approve candidate associations (single or batch)."""
    identity = authorized_user('MAPPING_APPROVER_IDS')
    data = body()
    items = data.get('items', [])
    if not isinstance(items, list) or not items:
        # Support single item format
        if 'business_category_id' in data and 'business_subcategory_id' in data and 'product_category_id' in data:
            items = [data]
        else:
            raise service.MappingError('A list of items to approve is required')
    result = bpm_service.approve_business_product_mappings(items, actor_id=identity)
    return jsonify(status='success', data=result)


@mapping_bp.route('/business-products/<int:mapping_id>', methods=['DELETE'])
@jwt_required(locations=['headers'])
@api_errors
def delete_business_product(mapping_id):
    """Remove an association from storage."""
    identity = authorized_user('MAPPING_APPROVER_IDS')
    success = bpm_service.delete_business_product_mapping(mapping_id, actor_id=identity)
    if not success:
        return jsonify(status='error', message='Mapping association not found'), 404
    return jsonify(status='success', message='Mapping association deleted')

