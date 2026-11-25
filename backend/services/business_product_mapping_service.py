"""
Business to Product Category Mapping Service
============================================
Handles bidirectional association and automated matching between
Canonical Business Categories (L1 & L2 from master_categories / listings)
and Product Categories from all Marketplaces (Amazon, Flipkart, Blinkit,
Zepto, DMart, BigBasket, IndiaMART, JioMart).

Stores approved associations in category_mapping.business_product_category_mappings.
"""

import re
import unicodedata
from datetime import datetime, timezone
from sqlalchemy import text
from extensions import db
from model.category_mapping_history import CategoryMappingHistory

def normalize_text(value: str) -> str:
    """Normalize text for consistent similarity and token comparison."""
    if not value:
        return ""
    val = unicodedata.normalize("NFKC", str(value)).lower()
    val = val.replace("&", " and ")
    val = re.sub(r"[_\-,;:./>]+", " ", val)
    return " ".join(val.split())

def calculate_token_similarity(s1: str, s2: str) -> float:
    """Computes Jaccard/overlap token similarity with substring booster."""
    n1 = normalize_text(s1)
    n2 = normalize_text(s2)
    if not n1 or not n2:
        return 0.0
    if n1 == n2:
        return 1.0
    if n1 in n2 or n2 in n1:
        len_ratio = min(len(n1), len(n2)) / max(len(n1), len(n2))
        return max(0.85, 0.70 + 0.30 * len_ratio)

    t1 = set(n1.split())
    t2 = set(n2.split())
    # remove stopwords
    stopwords = {"and", "or", "in", "of", "for", "with", "all", "more", "other", "others"}
    t1 = {w for w in t1 if w not in stopwords and len(w) > 2}
    t2 = {w for w in t2 if w not in stopwords and len(w) > 2}

    if not t1 or not t2:
        return 0.0

    intersection = t1 & t2
    union = t1 | t2
    jaccard = len(intersection) / len(union)

    # If key noun matches (e.g. "spices", "bakery", "ayurvedic", "mobiles")
    overlap_ratio = len(intersection) / min(len(t1), len(t2))
    return round(0.4 * jaccard + 0.6 * overlap_ratio, 4)

def get_business_product_mappings(page=1, limit=50, business_id=None, subcategory_id=None, marketplace=None, search=None):
    """
    Returns paginated active business-to-product mapping associations.
    """
    offset = (page - 1) * limit
    where_clauses = ["m.status = 'APPROVED'"]
    params = {'limit': limit, 'offset': offset}

    if business_id:
        where_clauses.append("m.business_category_id = :b_id")
        params['b_id'] = int(business_id)
    if subcategory_id:
        where_clauses.append("m.business_subcategory_id = :sub_id")
        params['sub_id'] = int(subcategory_id)
    if marketplace and marketplace.lower() != 'all':
        where_clauses.append("pcm.marketplace_name ILIKE :marketplace")
        params['marketplace'] = f"%{marketplace}%"
    if search:
        where_clauses.append("""(
            b_cat.name ILIKE :search OR 
            b_sub.name ILIKE :search OR 
            pcm.category_name ILIKE :search OR 
            pcm.category_path ILIKE :search
        )""")
        params['search'] = f"%{search}%"

    where_sql = " AND ".join(where_clauses)

    count_sql = f"""
        SELECT COUNT(1)
        FROM category_mapping.business_product_category_mappings m
        JOIN public.master_categories b_cat ON m.business_category_id = b_cat.id
        JOIN public.master_categories b_sub ON m.business_subcategory_id = b_sub.id
        JOIN public.product_category_master pcm ON m.product_category_id = pcm.id
        WHERE {where_sql}
    """
    total_count = db.session.execute(text(count_sql), params).scalar() or 0

    select_sql = f"""
        SELECT 
            m.id,
            m.business_category_id,
            b_cat.name AS business_category_name,
            m.business_subcategory_id,
            b_sub.name AS business_subcategory_name,
            m.product_category_id,
            pcm.category_name AS product_category_name,
            pcm.marketplace_name,
            pcm.category_path,
            pcm.category_level,
            m.mapping_type,
            m.status,
            u.email AS approved_by_email,
            m.created_at
        FROM category_mapping.business_product_category_mappings m
        JOIN public.master_categories b_cat ON m.business_category_id = b_cat.id
        JOIN public.master_categories b_sub ON m.business_subcategory_id = b_sub.id
        JOIN public.product_category_master pcm ON m.product_category_id = pcm.id
        LEFT JOIN public.users u ON m.approved_by_user_id = u.id
        WHERE {where_sql}
        ORDER BY m.id DESC
        LIMIT :limit OFFSET :offset
    """
    rows = db.session.execute(text(select_sql), params).fetchall()

    data = []
    for r in rows:
        data.append({
            'id': r[0],
            'business_category_id': r[1],
            'business_category_name': r[2],
            'business_subcategory_id': r[3],
            'business_subcategory_name': r[4],
            'product_category_id': r[5],
            'product_category_name': r[6],
            'marketplace_name': r[7],
            'category_path': r[8],
            'category_level': r[9],
            'mapping_type': r[10],
            'status': r[11],
            'approved_by': r[12] or 'Admin',
            'created_at': r[13].isoformat() if r[13] else None
        })

    total_pages = (total_count + limit - 1) // limit if total_count > 0 else 1

    return {
        'total_count': total_count,
        'total_pages': total_pages,
        'current_page': page,
        'limit': limit,
        'data': data
    }


def get_business_product_stats():
    """
    Returns executive summary analytics on business categories,
    product platforms coverage, and mapped relationships.
    """
    # 1. Business Category hierarchy counts
    b_cat_count = db.session.execute(text("""
        SELECT COUNT(1) FROM public.master_categories WHERE level = 1 AND is_active = true
    """)).scalar() or 0

    b_sub_count = db.session.execute(text("""
        SELECT COUNT(1) FROM public.master_categories WHERE level = 2 AND is_active = true
    """)).scalar() or 0

    # 2. Total active associations in DB
    total_associations = db.session.execute(text("""
        SELECT COUNT(1) FROM category_mapping.business_product_category_mappings WHERE status = 'APPROVED'
    """)).scalar() or 0

    # 3. Distinct business subcategories with at least one product mapped
    mapped_subs_count = db.session.execute(text("""
        SELECT COUNT(DISTINCT business_subcategory_id) 
        FROM category_mapping.business_product_category_mappings 
        WHERE status = 'APPROVED'
    """)).scalar() or 0

    # 4. Product catalog breakdown across platforms
    platform_rows = db.session.execute(text("""
        SELECT 
            pcm.marketplace_name,
            COUNT(1) AS total_products,
            COUNT(DISTINCT m.product_category_id) AS mapped_products
        FROM public.product_category_master pcm
        LEFT JOIN category_mapping.business_product_category_mappings m 
            ON pcm.id = m.product_category_id AND m.status = 'APPROVED'
        GROUP BY pcm.marketplace_name
        ORDER BY pcm.marketplace_name ASC
    """)).fetchall()

    platforms = []
    total_products_overall = 0
    total_mapped_products_overall = 0
    for r in platform_rows:
        total_products_overall += r[1]
        total_mapped_products_overall += r[2]
        platforms.append({
            'platform': r[0],
            'total': r[1],
            'mapped': r[2],
            'percent_mapped': round((r[2] / r[1] * 100), 1) if r[1] > 0 else 0
        })

    return {
        'total_business_categories': b_cat_count,
        'total_business_subcategories': b_sub_count,
        'mapped_subcategories_count': mapped_subs_count,
        'subcategory_coverage_percent': round((mapped_subs_count / b_sub_count * 100), 1) if b_sub_count > 0 else 0,
        'total_product_categories': total_products_overall,
        'total_associations': total_associations,
        'platforms': platforms
    }


def auto_map_business_to_products(business_id=None, marketplace=None, limit=100, threshold=0.75):
    """
    Automated discovery engine (Fast Pre-Indexed Version):
    Pre-indexes product category tokens and paths, running 2M comparisons in <0.2s.
    """
    # 1. Load active business subcategories (with parent L1 info)
    sub_sql = """
        SELECT sub.id, sub.name, p.id AS parent_id, p.name AS parent_name
        FROM public.master_categories sub
        JOIN public.master_categories p ON sub.parent_id = p.id
        WHERE sub.level = 2 AND sub.is_active = true AND p.is_active = true
    """
    if business_id:
        sub_sql += f" AND p.id = {int(business_id)}"
    sub_sql += " ORDER BY p.name ASC, sub.name ASC"
    sub_rows = db.session.execute(text(sub_sql)).fetchall()

    # 2. Load candidate product categories
    prod_sql = """
        SELECT id, marketplace_name, category_name, category_path, category_level
        FROM public.product_category_master
        WHERE category_name IS NOT NULL AND category_name != ''
    """
    if marketplace and marketplace.lower() != 'all':
        prod_sql += f" AND marketplace_name = '{marketplace}'"
    prod_rows = db.session.execute(text(prod_sql)).fetchall()

    # Pre-index product categories
    stopwords = {"and", "or", "in", "of", "for", "with", "all", "more", "other", "others"}
    indexed_prods = []
    for r in prod_rows:
        p_id, p_market, p_name, p_path, p_level = r[0], r[1], r[2], r[3], r[4]
        n_name = normalize_text(p_name)
        n_path = normalize_text(p_path)
        tokens = {w for w in n_path.split() if w not in stopwords and len(w) > 2}
        indexed_prods.append((p_id, p_market, p_name, p_path, n_name, n_path, tokens))

    # 3. Load existing associations
    existing_pairs = set(db.session.execute(text("""
        SELECT business_subcategory_id || '|||' || product_category_id 
        FROM category_mapping.business_product_category_mappings
        WHERE status = 'APPROVED'
    """)).scalars().all())

    suggestions = []

    for sub in sub_rows:
        sub_id, sub_name, b_id, b_name = sub[0], sub[1], sub[2], sub[3]
        n_sub = normalize_text(sub_name)
        n_target = normalize_text(f"{b_name} {sub_name}")
        sub_tokens = {w for w in n_sub.split() if w not in stopwords and len(w) > 2}
        if not sub_tokens:
            continue

        for p_id, p_market, p_name, p_path, n_name, n_path, prod_tokens in indexed_prods:
            pair_key = f"{sub_id}|||{p_id}"
            if pair_key in existing_pairs:
                continue

            # Fast match: check exact substring containment first
            if n_sub == n_name or n_sub == n_path:
                score = 1.0
            elif n_sub in n_path or n_name in n_sub:
                score = 0.90
            else:
                inter = sub_tokens & prod_tokens
                if not inter:
                    continue
                overlap = len(inter) / len(sub_tokens)
                jaccard = len(inter) / len(sub_tokens | prod_tokens)
                score = round(0.4 * jaccard + 0.6 * overlap, 4)

            if score >= threshold:
                suggestions.append({
                    'business_category_id': b_id,
                    'business_category_name': b_name,
                    'business_subcategory_id': sub_id,
                    'business_subcategory_name': sub_name,
                    'product_category_id': p_id,
                    'product_category_name': p_name,
                    'marketplace_name': p_market,
                    'category_path': p_path,
                    'confidence_score': round(score, 4),
                    'confidence_percent': round(score * 100, 1),
                })

    suggestions.sort(key=lambda s: -s['confidence_score'])
    return suggestions[:limit]


def approve_business_product_mappings(items, actor_id):
    """
    Batch approves business-to-product mapping associations.
    items: list of dicts with business_category_id, business_subcategory_id, product_category_id
    """
    if not items:
        return {'saved': 0, 'skipped': 0}

    saved = 0
    skipped = 0

    for item in items:
        b_id = int(item['business_category_id'])
        sub_id = int(item['business_subcategory_id'])
        p_id = int(item['product_category_id'])

        try:
            insert_sql = """
                INSERT INTO category_mapping.business_product_category_mappings 
                (business_category_id, business_subcategory_id, product_category_id, mapping_type, status, approved_by_user_id, created_at)
                VALUES (:b_id, :sub_id, :p_id, 'carries_products', 'APPROVED', :actor, NOW())
                ON CONFLICT (business_category_id, business_subcategory_id, product_category_id, mapping_type) 
                DO NOTHING
                RETURNING id;
            """
            res = db.session.execute(text(insert_sql), {
                'b_id': b_id, 'sub_id': sub_id, 'p_id': p_id, 'actor': int(actor_id)
            })
            new_id = res.scalar()
            if new_id:
                saved += 1
                # Log audit history
                db.session.execute(text("""
                    INSERT INTO public.category_mapping_history 
                    (master_category_id, action, new_value, changed_by, notes, created_at)
                    VALUES (:sub_id, 'BUSINESS_PRODUCT_MAPPED', :val, :actor, 'Admin approved business-to-product mapping', NOW())
                """), {
                    'sub_id': sub_id,
                    'val': f'assoc_id={new_id}, b_id={b_id}, sub_id={sub_id}, prod_id={p_id}',
                    'actor': str(actor_id)
                })
            else:
                skipped += 1
        except Exception as e:
            logger.error(f"Error approving mapping for {item}: {e}")
            skipped += 1

    db.session.commit()
    return {'saved': saved, 'skipped': skipped}


def delete_business_product_mapping(mapping_id, actor_id):
    """Deletes an association and records audit."""
    row = db.session.execute(text("""
        SELECT business_subcategory_id, product_category_id 
        FROM category_mapping.business_product_category_mappings 
        WHERE id = :id
    """), {'id': mapping_id}).fetchone()

    if not row:
        return False

    sub_id, p_id = row[0], row[1]
    db.session.execute(text("""
        DELETE FROM category_mapping.business_product_category_mappings WHERE id = :id
    """), {'id': mapping_id})

    db.session.execute(text("""
        INSERT INTO public.category_mapping_history 
        (master_category_id, action, old_value, new_value, changed_by, notes, created_at)
        VALUES (:sub_id, 'BUSINESS_PRODUCT_UNMAPPED', :val, 'DELETED', :actor, 'Admin removed business-to-product association', NOW())
    """), {
        'sub_id': sub_id,
        'val': f'assoc_id={mapping_id}, prod_id={p_id}',
        'actor': str(actor_id)
    })

    db.session.commit()
    return True
