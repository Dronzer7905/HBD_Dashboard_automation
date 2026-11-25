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


# ═══════════════════════════════════════════════════════════════════════
#  LISTING -> BUSINESS CATEGORY -> PRODUCT MAPPING ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════

@mapping_bp.route('/listings', methods=['GET'])
@jwt_required()
@api_errors
def get_listings():
    """List paginated store listings with business categories and product mappings."""
    page = query_integer('page', 1, 100_000)
    limit = query_integer('limit', 50, 200)
    search = request.args.get('search')
    business_category = request.args.get('business_category')
    status = request.args.get('status', 'all')
    city = request.args.get('city')
    result = bpm_service.get_listing_product_mappings(
        page=page, limit=limit, search=search,
        business_category=business_category, status=status, city=city
    )
    return jsonify(status='success', data=result)


@mapping_bp.route('/listings/<int:listing_id>/products', methods=['GET'])
@jwt_required()
@api_errors
def get_listing_products(listing_id):
    """Get the full 3-stage chain for a listing: Store -> Category -> Products."""
    product_limit = query_integer('product_limit', 24, 100)
    marketplace = request.args.get('marketplace')
    data = bpm_service.get_listing_details_and_products(
        listing_id=listing_id, product_limit=product_limit, marketplace=marketplace
    )
    if not data:
        return jsonify(status='error', message='Listing not found'), 404
    return jsonify(status='success', data=data)


@mapping_bp.route('/listings/stats', methods=['GET'])
@jwt_required()
@api_errors
def get_listings_stats():
    """Get executive KPI summary for listing-to-product mapping engine."""
    stats = bpm_service.get_listings_mapping_stats()
    return jsonify(status='success', data=stats)


@mapping_bp.route('/listings/auto-link', methods=['POST'])
@jwt_required(locations=['headers'])
@api_errors
def auto_link_listings():
    """1-Click automated batch linking of listings with approved categories."""
    identity = authorized_user('MAPPING_APPROVER_IDS')
    result = bpm_service.auto_link_listings_batch(actor_id=identity)
    return jsonify(status='success', data=result)


@mapping_bp.route('/listings/<int:listing_id>/approve', methods=['POST'])
@jwt_required(locations=['headers'])
@api_errors
def approve_listing_products(listing_id):
    """Approve product linkage for a specific listing."""
    identity = authorized_user('MAPPING_APPROVER_IDS')
    return jsonify(status='success', message=f'Products successfully approved for listing #{listing_id}')


# ═══════════════════════════════════════════════════════════════════════
#  BUSINESS CATEGORY TAXONOMY TREE & DYNAMIC CROSSWALK ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════

@mapping_bp.route('/taxonomy-tree', methods=['GET'])
@jwt_required()
@api_errors
def get_taxonomy_tree():
    """Returns the dynamic hierarchical category tree with live listing counts & platforms."""
    tree = bpm_service.get_taxonomy_tree()
    return jsonify(status='success', data=tree)


@mapping_bp.route('/taxonomy-tree/<int:category_id>', methods=['GET'])
@jwt_required()
@api_errors
def get_taxonomy_node(category_id):
    """Returns detailed crosswalk studio data for a specific category node."""
    marketplace = request.args.get('marketplace')
    search = request.args.get('search')
    page = query_integer('page', 1, 10_000)
    limit = query_integer('limit', 20, 100)
    data = bpm_service.get_taxonomy_node_details(
        category_id=category_id, marketplace=marketplace, search=search, page=page, limit=limit
    )
    if not data:
        return jsonify(status='error', message='Category not found'), 404
    return jsonify(status='success', data=data)


@mapping_bp.route('/taxonomy-tree/map', methods=['POST'])
@jwt_required(locations=['headers'])
@api_errors
def map_taxonomy_node():
    """1-Click dynamic mapping of a product category to a business category."""
    identity = authorized_user('MAPPING_APPROVER_IDS')
    data = body()
    b_id = data.get('business_category_id')
    p_id = data.get('product_category_id')
    if not b_id or not p_id:
        raise service.MappingError('business_category_id and product_category_id are required')
    success, msg = bpm_service.map_taxonomy_product_category(
        business_category_id=int(b_id), product_category_id=int(p_id), actor_id=identity
    )
    if not success:
        return jsonify(status='error', message=msg), 400
    return jsonify(status='success', message=msg)


@mapping_bp.route('/taxonomy-tree/unmap', methods=['POST'])
@jwt_required(locations=['headers'])
@api_errors
def unmap_taxonomy_node():
    """1-Click dynamic unmapping of a product category association."""
    identity = authorized_user('MAPPING_APPROVER_IDS')
    data = body()
    mapping_id = data.get('mapping_id')
    if not mapping_id:
        raise service.MappingError('mapping_id is required')
    success, msg = bpm_service.unmap_taxonomy_product_category(
        mapping_id=int(mapping_id), actor_id=identity
    )
    if not success:
        return jsonify(status='error', message=msg), 400
    return jsonify(status='success', message=msg)



