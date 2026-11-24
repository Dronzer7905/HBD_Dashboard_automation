"""BG-1.11 source mappings, verified product catalog, and opt-in local associations.

No discovery, taxonomy generation, cleanup, or background sync is performed here.
"""

import re
import unicodedata
from datetime import datetime, timezone

from flask import current_app
from sqlalchemy import or_, text
from sqlalchemy.orm import joinedload
from sqlalchemy.exc import IntegrityError, OperationalError

from extensions import db
from model.category_mapping_history import CategoryMappingHistory
from model.category_mapping_synonyms import CategoryMappingSynonym
from model.master_category import MasterCategory
from model.platform_category_mapping import PlatformCategoryMapping
from model.product_category import ProductCategory


MAX_TAXONOMY = 2000
MAX_SYNONYMS = 5000
MAX_DEPTH = 10
THRESHOLD = 0.8
AMBIGUITY_MARGIN = 0.05
PERSISTENCE_THRESHOLD = 0.9


def local_associations_enabled():
    return (current_app.config.get('MAPPING_LOCAL_ASSOCIATIONS_ENABLED') is True
            and db.engine.dialect.name == 'sqlite')


def postgres_associations_enabled():
    config = current_app.config
    return (config.get('MAPPING_POSTGRES_ASSOCIATIONS_ENABLED') is True
            and config.get('MAPPING_DEPLOYMENT_ENV') in ('local', 'staging')
            and db.engine.dialect.name == 'postgresql'
            and bool(config.get('MAPPING_POSTGRES_DATABASE'))
            and config['MAPPING_POSTGRES_DATABASE'] == db.engine.url.database)


def association_storage():
    return 'postgresql.category_mapping' if postgres_associations_enabled() else 'local_sqlite_only'


def capabilities():
    return {
        'target_model': 'master_categories', 'targets_per_source': 1,
        'business_product_associations': local_associations_enabled() or postgres_associations_enabled(),
        'business_product_storage': association_storage(),
        'automatic_persistence': True,
        'automatic_persistence_requires': 'MAPPING_ADMIN_IDS and Bearer authentication',
        'limitation': 'PostgreSQL associations require operator-installed category_mapping schema and '
                      'an explicit non-production feature/database gate; silver_clean is unchanged.',
    }


class MappingError(Exception):
    def __init__(self, message, status=400, code='validation_error'):
        super().__init__(message)
        self.status = status
        self.code = code


def integer(value, field, maximum=2_147_483_647):
    if type(value) is not int or not 1 <= value <= maximum:
        raise MappingError(f'{field} must be an integer between 1 and {maximum}')
    return value


def text_value(value, field, maximum=255, allow_empty=False):
    if not isinstance(value, str) or len(value) > maximum:
        raise MappingError(f'{field} must be a string of at most {maximum} characters')
    if not allow_empty and not value.strip():
        raise MappingError(f'{field} must not be blank')
    return value


def check_fields(data, allowed, *, relationship=False):
    unsupported = {'business_category_id', 'business_subcategory_id',
                   'product_category_id', 'product_category_ids'} & data.keys()
    if unsupported and not relationship:
        raise MappingError('Business/product associations are not supported by the existing schema',
                           422, 'unsupported_relationship')
    if data.keys() - allowed:
        raise MappingError('Unknown parameters: ' + ', '.join(sorted(data.keys() - allowed)))


def normalize(value):
    """Comparison only: preserve source values and canonical names in storage."""
    value = unicodedata.normalize('NFKC', value).casefold().replace('&', ' and ')
    value = re.sub(r'[_\-,;:.]+', ' ', value)
    value = re.sub(r'\s*>\s*', ' > ', value)
    return ' '.join(value.split())


def similarity(left, right):
    """1 - Levenshtein distance / max length, or None when below 80%.

    A bounded dynamic-programming band and length check avoid computing full
    edit matrices for obviously unsuitable candidates. Threshold uses integer
    arithmetic; scores are rounded only for presentation.
    """
    size = max(len(left), len(right))
    if not size:
        return 1.0
    budget = size // 5
    if abs(len(left) - len(right)) > budget:
        return None
    if left == right:
        return 1.0
    previous = {j: j for j in range(min(len(right), budget) + 1)}
    for i, char in enumerate(left, 1):
        current = {0: i} if i <= budget else {}
        for j in range(max(1, i - budget), min(len(right), i + budget) + 1):
            current[j] = min(
                previous.get(j, budget + 1) + 1,
                current.get(j - 1, budget + 1) + 1,
                previous.get(j - 1, budget + 1) + (char != right[j - 1]),
            )
        if not current or min(current.values()) > budget:
            return None
        previous = current
    distance = previous.get(len(right), budget + 1)
    return 1 - distance / size if distance <= budget else None


def source_query(platform=None, search=None, status='unmapped'):
    query = PlatformCategoryMapping.query.options(joinedload(PlatformCategoryMapping.master_category))
    query = query.filter(PlatformCategoryMapping.is_active.is_(True))
    if status == 'unmapped':
        query = query.filter(
            PlatformCategoryMapping.mapping_status.in_(['PENDING', 'UNMAPPED']),
            PlatformCategoryMapping.master_category_id.is_(None),
        )
    elif status != 'all':
        raise MappingError('status must be unmapped or all')
    if platform:
        query = query.filter(PlatformCategoryMapping.platform_name == platform)
    if search:
        query = query.filter(or_(
            PlatformCategoryMapping.platform_category_raw.contains(search, autoescape=True),
            PlatformCategoryMapping.platform_subcategory_raw.contains(search, autoescape=True),
        ))
    return query.order_by(PlatformCategoryMapping.id)


def page_data(query, page, limit, serialize):
    result = query.paginate(page=page, per_page=limit, error_out=False)
    return {
        'data': [serialize(row) for row in result.items],
        'total_count': result.total, 'total_pages': result.pages,
        'current_page': page, 'limit': limit,
    }


def categories(*, page=1, limit=50, category_page=1, category_limit=100,
               platform=None, search=None, status='unmapped', parent_id=None,
               product_page=1, product_limit=50, product_search=None, marketplace=None,
               product_parent_id=None, product_level=None):
    targets = MasterCategory.query.filter(MasterCategory.is_active.is_(True))
    if parent_id == 'root':
        targets = targets.filter(MasterCategory.parent_id.is_(None))
    elif parent_id is not None:
        targets = targets.filter_by(parent_id=parent_id)
    products = product_query()
    if product_search:
        products = products.filter(or_(*(column.icontains(product_search, autoescape=True)
            for column in (ProductCategory.category_name, ProductCategory.subcategory_name,
                           ProductCategory.child_category_name, ProductCategory.category_path))))
    if marketplace:
        products = products.filter_by(marketplace_name=marketplace)
    if product_parent_id == 'root':
        products = products.filter(ProductCategory.parent_id.is_(None))
    elif product_parent_id is not None:
        products = products.filter_by(parent_id=product_parent_id)
    if product_level is not None:
        products = products.filter_by(category_level=product_level)
    return {
        'source_categories': page_data(source_query(platform, search, status), page, limit,
                                       lambda row: row.to_dict()),
        'canonical_categories': page_data(targets.order_by(MasterCategory.id), category_page,
                                          category_limit, lambda row: row.to_dict()),
        'business_categories': None,
        'business_subcategories': None,
        'product_service_categories': page_data(products.order_by(ProductCategory.id), product_page,
                                                  product_limit, lambda row: row.to_dict()),
        'capabilities': capabilities(),
    }


def category_chain(target):
    """Validate a complete active chain using real FKs, never trusting path text."""
    chain = []
    seen = set()
    current = target
    for _ in range(MAX_DEPTH):
        if current is None or not current.is_active or current.id in seen:
            break
        chain.append(current)
        seen.add(current.id)
        if current.parent_id is None:
            if current.level != 1:
                break
            return list(reversed(chain))
        parent = db.session.get(MasterCategory, current.parent_id)
        if parent is None or parent.level != current.level - 1:
            break
        current = parent
    raise MappingError('Target has an inactive, missing, cyclic, or invalid category hierarchy',
                       422, 'invalid_hierarchy')


def save_mapping(data, actor):
    if {'business_category_id', 'business_subcategory_id', 'product_category_ids'} <= data.keys():
        return save_product_mappings(data, actor)
    check_fields(data, {'mapping_id', 'platform_name', 'platform_category_raw',
                        'platform_subcategory_raw', 'master_category_id', 'parent_category_id'})
    target_id = integer(data.get('master_category_id'), 'master_category_id')
    if 'mapping_id' in data:
        mapping_id = integer(data['mapping_id'], 'mapping_id')
        query = PlatformCategoryMapping.query.filter_by(id=mapping_id)
    else:
        platform = text_value(data.get('platform_name'), 'platform_name', 100)
        raw = text_value(data.get('platform_category_raw'), 'platform_category_raw')
        sub = text_value(data.get('platform_subcategory_raw', ''), 'platform_subcategory_raw',
                         allow_empty=True)
        query = PlatformCategoryMapping.query.filter_by(platform_name=platform,
                                                        platform_category_raw=raw)
        if sub == '':
            query = query.filter(or_(PlatformCategoryMapping.platform_subcategory_raw == '',
                                     PlatformCategoryMapping.platform_subcategory_raw.is_(None)))
        else:
            query = query.filter_by(platform_subcategory_raw=sub)

    # Lock the existing source row: concurrent approvals serialize on PostgreSQL.
    rows = query.with_for_update().limit(2).all()
    if not rows:
        raise MappingError('Source mapping not found; discovery must be performed separately', 404,
                           'source_not_found')
    if len(rows) > 1:
        raise MappingError('Source identity is ambiguous; use mapping_id', 409, 'duplicate_source')
    mapping = rows[0]
    if not mapping.is_active:
        raise MappingError('Source mapping is inactive', 422)
    for field, maximum in [('platform_name', 100), ('platform_category_raw', 255),
                           ('platform_subcategory_raw', 255)]:
        if field in data:
            text_value(data[field], field, maximum, allow_empty=field == 'platform_subcategory_raw')
            if data[field] != (getattr(mapping, field) or ''):
                raise MappingError(f'{field} does not match mapping_id', 409, 'source_conflict')

    target = db.session.get(MasterCategory, target_id)
    if target is None:
        raise MappingError('master_category_id does not exist', 404, 'category_not_found')
    chain = category_chain(target)
    if 'parent_category_id' in data:
        parent_id = integer(data['parent_category_id'], 'parent_category_id')
        if len(chain) < 2 or chain[-2].id != parent_id:
            raise MappingError('parent_category_id must be the direct parent of the target',
                               422, 'invalid_hierarchy')
    if mapping.master_category_id == target_id and mapping.mapping_status == 'MANUALLY_MAPPED':
        return mapping.to_dict(), False
    if mapping.mapping_status == 'MANUALLY_MAPPED':
        raise MappingError('An approved mapping cannot be overwritten through this endpoint',
                           409, 'approved_mapping_conflict')

    old_id, old_status = mapping.master_category_id, mapping.mapping_status
    mapping.master_category_id = target_id
    mapping.master_category = target
    mapping.mapping_status = 'MANUALLY_MAPPED'
    mapping.confidence_score = 1.0
    mapping.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.session.add(CategoryMappingHistory(
        mapping_id=mapping.id, master_category_id=target_id,
        action='REMAPPED' if old_id else 'MAPPED',
        old_value=f'master_id={old_id}, status={old_status}',
        new_value=f'master_id={target_id}, status=MANUALLY_MAPPED',
        changed_by=actor, notes='BG-1.11 manual approval',
    ))
    # Serialize before commit so expiration cannot trigger a post-commit query.
    db.session.flush()
    result = mapping.to_dict()
    db.session.commit()
    return result, True


def candidate_catalog(nodes):
    """Build validated paths in memory; reject broken/inactive ancestor chains."""
    by_id = {node.id: node for node in nodes}
    candidates = []
    for node in nodes:
        if not node.is_active or not node.name.strip() or len(node.name) > 255:
            continue
        chain, seen, current = [], set(), node
        for _ in range(MAX_DEPTH):
            if current is None or not current.is_active or current.id in seen:
                break
            chain.append(current)
            seen.add(current.id)
            if current.parent_id is None:
                if current.level == 1:
                    ordered = list(reversed(chain))
                    path = ' > '.join(n.name for n in ordered)
                    if len(path) <= 512:
                        candidates.append({'id': node.id, 'name': node.name, 'path': path,
                                           'parent_id': node.parent_id, 'level': node.level,
                                           'normalized_name': normalize(node.name),
                                           'normalized_path': normalize(path)})
                break
            parent = by_id.get(current.parent_id)
            if parent is None or parent.level != current.level - 1:
                break
            current = parent
    return candidates


def suggest(mapping, catalog, aliases, *, with_scores=False):
    parts = [mapping.platform_category_raw]
    if mapping.platform_subcategory_raw:
        parts.append(mapping.platform_subcategory_raw)
    raw = normalize(' > '.join(parts))
    # An explicit configured alias is authoritative; unresolved alias targets do
    # not fall back to unrelated fuzzy guesses. Colliding aliases remain reviewable.
    alias_targets = aliases.get(raw)
    searches = alias_targets if alias_targets else {raw}
    ranked = []
    for candidate in catalog:
        best = None
        for search in searches:
            target = candidate['normalized_path'] if ' > ' in search else candidate['normalized_name']
            if alias_targets:
                score = 1.0 if search and search == target else None
            else:
                score = similarity(search, target) if search else None
            if score is not None and (best is None or score > best):
                best = score
        if best is not None:
            ranked.append((best, candidate))
    ranked.sort(key=lambda item: (-item[0], item[1]['id']))
    ambiguous = bool(alias_targets and len(alias_targets) > 1) or (
        len(ranked) > 1 and ranked[0][0] - ranked[1][0] <= AMBIGUITY_MARGIN + 1e-12)
    if not ranked:
        state, reason = 'unmatched', 'unresolved_synonym' if alias_targets else 'below_threshold'
    elif ambiguous:
        state, reason = 'ambiguous', 'competing_candidates'
    elif ranked[0][0] == 1.0:
        state, reason = 'high_confidence', 'synonym' if alias_targets else 'exact_normalized'
    else:
        state, reason = 'review_required', 'fuzzy_similarity_only'
    result = {
        'mapping_id': mapping.id, 'platform_name': mapping.platform_name,
        'platform_category_raw': mapping.platform_category_raw,
        'platform_subcategory_raw': mapping.platform_subcategory_raw or '',
        'normalized_source': raw, 'classification': state, 'reason': reason,
        'requires_manual_approval': True, 'candidate_count': len(ranked),
        'candidates': [dict({k: v for k, v in candidate.items() if not k.startswith('normalized_')},
                            score=round(score, 6), score_percent=round(score * 100, 2))
                       for score, candidate in ranked[:3]],
    }
    return (result, ranked) if with_scores else result


def prepare_write_transaction():
    if db.engine.dialect.name == 'postgresql':
        db.session.execute(text("SET LOCAL lock_timeout = '2s'"))
        db.session.execute(text("SET LOCAL statement_timeout = '10s'"))
        return
    if db.engine.dialect.name != 'sqlite':
        return
    connection = db.session.connection()
    if not connection.connection.driver_connection.in_transaction:
        try:
            connection.exec_driver_sql('BEGIN IMMEDIATE')
        except OperationalError as error:
            db.session.rollback()
            code = getattr(error.orig, 'sqlite_errorcode', None)
            if code is not None and (code & 255) in (5, 6):
                raise MappingError('Local mapping storage is busy; retry the complete request',
                                   409, 'mapping_busy') from None
            raise


def auto_map(data, actor=None):
    check_fields(data, {'dry_run', 'after_id', 'limit', 'platform_name'})
    dry_run = data.get('dry_run', True)
    if type(dry_run) is not bool:
        raise MappingError('dry_run must be a boolean')
    if not dry_run and actor is None:
        raise MappingError('Administrator authorization is required', 403, 'forbidden')
    limit = integer(data.get('limit', 25), 'limit', 50)
    after_id = data.get('after_id', 0)
    if type(after_id) is not int or not 0 <= after_id <= 2_147_483_647:
        raise MappingError('after_id must be a non-negative 32-bit integer')
    platform = data.get('platform_name')
    if platform is not None:
        text_value(platform, 'platform_name', 100)
    if not dry_run:
        prepare_write_transaction()
    query = source_query(platform).filter(PlatformCategoryMapping.id > after_id)
    if not dry_run:
        # OF prevents locking the nullable side of the joined category load.
        query = query.with_for_update(of=PlatformCategoryMapping)
    rows = query.limit(limit + 1).all()
    has_more, rows = len(rows) > limit, rows[:limit]
    response = {
        'dry_run': dry_run, 'threshold': THRESHOLD,
        'persistence_threshold': PERSISTENCE_THRESHOLD, 'ambiguity_margin': AMBIGUITY_MARGIN,
        'data': [], 'has_more': has_more,
        'next_after_id': rows[-1].id if rows and has_more else None,
        'capabilities': capabilities(),
        'summary': {'saved': 0, 'skipped': 0, 'failed': 0, 'ambiguous': 0},
        'transaction_failed': False,
    }
    if not rows:
        if not dry_run:
            db.session.rollback()
        return response
    nodes_query = MasterCategory.query.filter_by(is_active=True).order_by(MasterCategory.id)
    if not dry_run:
        nodes_query = nodes_query.with_for_update(read=True)
    nodes = nodes_query.limit(MAX_TAXONOMY + 1).all()
    synonyms = CategoryMappingSynonym.query.order_by(CategoryMappingSynonym.id).limit(MAX_SYNONYMS + 1).all()
    if len(nodes) > MAX_TAXONOMY or len(synonyms) > MAX_SYNONYMS:
        raise MappingError('Taxonomy or synonym safety limit exceeded; a scoped matching index is required',
                           422, 'matching_capacity_exceeded')
    aliases = {}
    for synonym in synonyms:
        aliases.setdefault(normalize(synonym.raw_value), set()).add(normalize(synonym.canonical_value))
    catalog = candidate_catalog(nodes)
    pending = []
    for row in rows:
        item, ranked = suggest(row, catalog, aliases, with_scores=True)
        response['data'].append(item)
        if item['classification'] == 'ambiguous':
            outcome, reason = 'ambiguous', 'competing_candidates'
        elif dry_run:
            outcome, reason = 'skipped', 'dry_run'
        elif not ranked or ranked[0][0] < PERSISTENCE_THRESHOLD:
            outcome, reason = 'skipped', 'below_persistence_threshold'
        else:
            target = db.session.get(MasterCategory, ranked[0][1]['id'])
            try:
                if target is None:
                    raise MappingError('Target disappeared', 422, 'invalid_hierarchy')
                category_chain(target)
            except MappingError:
                outcome, reason = 'failed', 'invalid_target'
            else:
                pending.append((row, target, ranked[0][0], item))
                outcome, reason = 'saved', 'confidence_at_least_90_percent'
        item.update(outcome=outcome, persistence_reason=reason)
        response['summary'][outcome] += 1
    if not pending:
        if not dry_run:
            db.session.rollback()
        return response
    try:
        for row, target, score, item in pending:
            old_status = row.mapping_status
            row.master_category_id = target.id
            row.master_category = target
            row.mapping_status = 'AUTO_MAPPED'
            row.confidence_score = score
            row.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
            db.session.add(CategoryMappingHistory(
                mapping_id=row.id, master_category_id=target.id, action='AUTO_MAPPED',
                old_value=f'master_id=None, status={old_status}',
                new_value=f'master_id={target.id}, status=AUTO_MAPPED',
                changed_by=actor, notes='BG-1.11 admin auto-map; unrounded confidence >= 90%',
            ))
            item['requires_manual_approval'] = False
        db.session.flush()
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.error('BG-1.11 auto-map batch failed; transaction rolled back')
        response['transaction_failed'] = True
        response['summary']['saved'] = 0
        response['summary']['failed'] += len(pending)
        for _, _, _, item in pending:
            item.update(outcome='failed', persistence_reason='transaction_rolled_back',
                        requires_manual_approval=True)
    return response


def product_query():
    query = ProductCategory.query
    if db.engine.dialect.name == 'postgresql':
        query = query.execution_options(schema_translate_map={None: 'public'})
    return query


def local_relationship_model():
    if postgres_associations_enabled():
        from services.mapping_schema import verify_contract, SchemaContractError
        from model.business_product_category_mapping import PostgresBusinessProductCategoryMapping
        try:
            verify_contract(db.session.connection().connection.driver_connection)
        except SchemaContractError as error:
            raise MappingError(str(error), 422, 'schema_not_ready') from None
        return PostgresBusinessProductCategoryMapping
    if not local_associations_enabled():
        raise MappingError('Association storage requires opt-in SQLite or a verified non-production PostgreSQL schema',
                           422, 'local_associations_disabled')
    from model.business_product_category_mapping import BusinessProductCategoryMapping
    return BusinessProductCategoryMapping


def validate_product_chain(target):
    current, seen = target, set()
    for _ in range(MAX_DEPTH):
        if current is None or current.id in seen or not current.category_name.strip():
            break
        seen.add(current.id)
        if current.parent_id is None:
            if current.category_level == 1:
                return
            break
        parent = product_query().filter_by(id=current.parent_id).with_for_update(read=True).populate_existing().first()
        if (parent is None or parent.category_level != current.category_level - 1
                or parent.marketplace_name != current.marketplace_name):
            break
        current = parent
    raise MappingError('Product category hierarchy is invalid', 422, 'invalid_hierarchy')


def save_product_mappings(data, actor):
    model = local_relationship_model()
    try:
        # SQLite has no FOR UPDATE. Reserve the writer before the duplicate read
        # so concurrent identical local requests serialize, including Python's
        # legacy sqlite transaction mode where SELECT does not issue BEGIN.
        prepare_write_transaction()
        result, changed = _save_product_mappings(data, actor, model)
        if not changed:
            db.session.rollback()  # Release the reservation on idempotent reads.
        return result, changed
    except IntegrityError:
        db.session.rollback()
        raise MappingError('Association constraints changed; retry the complete request',
                           409, 'association_conflict') from None
    except OperationalError as error:
        db.session.rollback()
        code = getattr(error.orig, 'sqlite_errorcode', None)
        if code is not None and (code & 255) in (5, 6):
            raise MappingError('Local association storage is busy; retry the complete request',
                               409, 'association_busy') from None
        raise


def _save_product_mappings(data, actor, model):
    check_fields(data, {'business_category_id', 'business_subcategory_id',
                        'product_category_ids', 'mapping_type'}, relationship=True)
    business_id = integer(data.get('business_category_id'), 'business_category_id')
    sub_id = integer(data.get('business_subcategory_id'), 'business_subcategory_id')
    mapping_type = text_value(data.get('mapping_type'), 'mapping_type', 40)
    if mapping_type != 'carries_products':
        raise MappingError('mapping_type must be carries_products', 422, 'invalid_mapping_type')
    product_ids = data.get('product_category_ids')
    if not isinstance(product_ids, list) or not 1 <= len(product_ids) <= 100:
        raise MappingError('product_category_ids must contain between 1 and 100 IDs')
    product_ids = [integer(value, 'product_category_ids') for value in product_ids]
    unique_ids = list(dict.fromkeys(product_ids))
    # Serialize requests for this business parent before checking/inserting associations.
    business = MasterCategory.query.filter_by(id=business_id).with_for_update().populate_existing().first()
    subcategory = MasterCategory.query.filter_by(id=sub_id).with_for_update(read=True).populate_existing().first()
    if business is None or subcategory is None:
        raise MappingError('Business category or subcategory does not exist', 404, 'category_not_found')
    category_chain(business)
    category_chain(subcategory)
    if business.parent_id is not None or business.level != 1 or subcategory.parent_id != business_id or subcategory.level != 2:
        raise MappingError('Business subcategory must be a direct level-2 child of the level-1 category',
                           422, 'invalid_hierarchy')
    products = {row.id: row for row in product_query().filter(ProductCategory.id.in_(unique_ids)).with_for_update(read=True).populate_existing().all()}
    if len(products) != len(unique_ids):
        raise MappingError('One or more product category IDs do not exist', 404, 'category_not_found')
    for product in products.values():
        validate_product_chain(product)
    existing = db.session.query(model).filter_by(business_category_id=business_id, business_subcategory_id=sub_id,
                                     mapping_type=mapping_type).filter(model.product_category_id.in_(unique_ids)).all()
    by_product = {row.product_category_id: row for row in existing}
    added = []
    for product_id in unique_ids:
        if product_id in by_product:
            continue
        association = model(business_category_id=business_id, business_subcategory_id=sub_id,
                            product_category_id=product_id, mapping_type=mapping_type,
                            status='APPROVED', approved_by_user_id=int(actor))
        db.session.add(association)
        added.append(association)
        by_product[product_id] = association
    if added:
        db.session.flush()
        for association in added:
            db.session.add(CategoryMappingHistory(
                mapping_id=None, master_category_id=sub_id, action='BUSINESS_PRODUCT_MAPPED',
                old_value=None,
                new_value=(f'{"association_id" if postgres_associations_enabled() else "local_association_id"}={association.id}, business_category_id={business_id}, '
                           f'business_subcategory_id={sub_id}, product_category_id={association.product_category_id}, '
                           f'mapping_type={mapping_type}, status=APPROVED'),
                changed_by=actor, notes='BG-1.11 business/product approval; storage=' + association_storage(),
            ))
        db.session.flush()
    result = {
        'associations': [by_product[product_id].to_dict() for product_id in unique_ids],
        'saved': len(added), 'skipped': len(existing),
        'duplicates_ignored': len(product_ids) - len(unique_ids), 'storage': association_storage(),
    }
    if added:
        db.session.commit()
    return result, bool(added)
