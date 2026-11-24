"""Explicit SQLite prototype and operator-installed PostgreSQL relationship contract.

The existing silver_clean relation is never retargeted or altered. PostgreSQL
uses a separate category_mapping schema installed by reviewed operator SQL.
The original SQLite prototype remains available behind its own feature gate.
"""
from datetime import datetime, timezone
from sqlalchemy import event
from extensions import db


class BusinessProductCategoryMapping(db.Model):
    __tablename__ = 'local_business_product_category_mappings'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    business_category_id = db.Column(db.Integer, db.ForeignKey('master_categories.id'), nullable=False)
    business_subcategory_id = db.Column(db.Integer, db.ForeignKey('master_categories.id'), nullable=False)
    product_category_id = db.Column(db.Integer, db.ForeignKey('product_category_master.id'), nullable=False)
    mapping_type = db.Column(db.String(40), nullable=False, default='carries_products')
    status = db.Column(db.String(30), nullable=False, default='APPROVED')
    approved_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False,
                           default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    __table_args__ = (
        db.UniqueConstraint('business_category_id', 'business_subcategory_id',
                            'product_category_id', 'mapping_type', name='uq_local_business_product'),
        db.CheckConstraint("mapping_type = 'carries_products'", name='ck_local_mapping_type'),
        db.CheckConstraint("status = 'APPROVED'", name='ck_local_mapping_status'),
    )

    def to_dict(self):
        result = {column.name: getattr(self, column.name) for column in self.__table__.columns}
        result['created_at'] = self.created_at.isoformat() if self.created_at else None
        return result


def sqlite_only(connection):
    if connection.dialect.name != 'sqlite':
        raise RuntimeError('The provisional business/product table is restricted to local SQLite')


@event.listens_for(BusinessProductCategoryMapping.__table__, 'before_create')
def prevent_remote_ddl(target, connection, **kwargs):
    sqlite_only(connection)


@event.listens_for(BusinessProductCategoryMapping, 'before_insert')
@event.listens_for(BusinessProductCategoryMapping, 'before_update')
@event.listens_for(BusinessProductCategoryMapping, 'before_delete')
def prevent_remote_write(mapper, connection, target):
    sqlite_only(connection)


# Dedicated metadata: application db.create_all() must never install this schema.
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import Identity, func
from model.master_category import MasterCategory
from model.product_category import ProductCategory
from model.user import User


class PostgresMappingBase(DeclarativeBase):
    pass


class PostgresBusinessProductCategoryMapping(PostgresMappingBase):
    __tablename__ = 'business_product_category_mappings'
    id = db.Column(db.BigInteger, Identity(), primary_key=True)
    business_category_id = db.Column(db.Integer, db.ForeignKey(MasterCategory.id, ondelete='RESTRICT'), nullable=False)
    business_subcategory_id = db.Column(db.Integer, db.ForeignKey(MasterCategory.id, ondelete='RESTRICT'), nullable=False)
    product_category_id = db.Column(db.Integer, db.ForeignKey(ProductCategory.id, ondelete='RESTRICT'), nullable=False)
    mapping_type = db.Column(db.String(40), nullable=False, server_default='carries_products')
    status = db.Column(db.String(30), nullable=False, server_default='APPROVED')
    approved_by_user_id = db.Column(db.Integer, db.ForeignKey(User.id, ondelete='RESTRICT'), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, server_default=func.now())
    __table_args__ = (
        db.UniqueConstraint('business_category_id', 'business_subcategory_id', 'product_category_id',
                            'mapping_type', name='uq_bpcm_relationship'),
        db.CheckConstraint("mapping_type = 'carries_products'", name='ck_bpcm_type'),
        db.CheckConstraint("status = 'APPROVED'", name='ck_bpcm_status'),
        {'schema': 'category_mapping'},
    )
    to_dict = BusinessProductCategoryMapping.to_dict


@event.listens_for(PostgresBusinessProductCategoryMapping.__table__, 'before_create')
def require_operator_install(target, connection, **kwargs):
    raise RuntimeError('Install the reviewed BG111 SQL explicitly; ORM schema creation is disabled')


@event.listens_for(PostgresBusinessProductCategoryMapping, 'before_insert')
@event.listens_for(PostgresBusinessProductCategoryMapping, 'before_update')
@event.listens_for(PostgresBusinessProductCategoryMapping, 'before_delete')
def guard_postgres_write(mapper, connection, target):
    from services.mapping_service import postgres_associations_enabled
    if connection.dialect.name != 'postgresql' or not postgres_associations_enabled():
        raise RuntimeError('PostgreSQL association writes require the explicit non-production gate')
