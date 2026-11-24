"""Existing public.product_category_master columns, verified read-only on 2026-11-23.

No FK or hierarchy constraints are invented for this existing catalog. On
PostgreSQL, service queries explicitly translate the default schema to public.
"""
from extensions import db


class ProductCategory(db.Model):
    __tablename__ = 'product_category_master'

    id = db.Column(db.Integer, primary_key=True)
    marketplace_name = db.Column(db.String(100), nullable=False)
    category_name = db.Column(db.String(255), nullable=False)
    subcategory_name = db.Column(db.String(255))
    child_category_name = db.Column(db.String(255))
    parent_id = db.Column(db.Integer)
    category_level = db.Column(db.Integer, nullable=False)
    category_path = db.Column(db.Text, nullable=False)
    category_key = db.Column(db.String(255))

    def to_dict(self):
        result = {column.name: getattr(self, column.name) for column in self.__table__.columns}
        result['name'] = (self.child_category_name if self.category_level >= 3 else
                          self.subcategory_name if self.category_level == 2 else None) or self.category_name
        return result
