"""Proposed bronze contract. Declared independently; app db.create_all cannot install it.

No application path creates or migrates tables. DBA verification is required
before enabling this contract on the shared database.
"""
from datetime import datetime, timezone
from functools import lru_cache

import sqlalchemy as sa

from services.ingestion_storage import IngestionError


def now():
    return datetime.now(timezone.utc)


@lru_cache(maxsize=4)
def tables(dialect='postgresql'):
    metadata = sa.MetaData(schema=None if dialect == 'sqlite' else 'bronze_staging')
    batches = sa.Table('raw_ingest_batches', metadata,
        sa.Column('batch_id', sa.String(32), primary_key=True),
        sa.Column('file_id', sa.String(32), nullable=False, unique=True),
        sa.Column('owner_id', sa.String(64), nullable=False),
        sa.Column('category_type', sa.String(40), nullable=False),
        sa.Column('column_mapping', sa.JSON, nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('total_rows', sa.BigInteger),
        sa.Column('processed_rows', sa.BigInteger, nullable=False, default=0),
        sa.Column('valid_count', sa.BigInteger, nullable=False, default=0),
        sa.Column('quarantine_count', sa.BigInteger, nullable=False, default=0),
        sa.Column('task_id', sa.String(36), nullable=False),
        sa.Column('error_message', sa.Text),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint('processed_rows = valid_count + quarantine_count'),
        sa.CheckConstraint('processed_rows >= 0 AND valid_count >= 0 AND quarantine_count >= 0'),
        sa.CheckConstraint('total_rows IS NULL OR total_rows >= processed_rows'))
    common = lambda: [
        sa.Column('id', sa.BigInteger().with_variant(sa.Integer, 'sqlite'), primary_key=True),
        sa.Column('batch_id', sa.String(32), sa.ForeignKey(batches.c.batch_id), nullable=False),
        sa.Column('row_number', sa.BigInteger, nullable=False),
        sa.Column('raw_data', sa.JSON, nullable=False),
        sa.UniqueConstraint('batch_id', 'row_number')]
    businesses = sa.Table('raw_businesses', metadata, *common(),
        sa.Column('category_type', sa.String(40), nullable=False),
        sa.Column('business_name', sa.String(255), nullable=False),
        *[sa.Column(field, sa.Text) for field in ['phone', 'email', 'address', 'city', 'state',
                                                'country', 'pincode', 'category']],
        sa.Column('latitude', sa.Float), sa.Column('longitude', sa.Float))
    quarantine = sa.Table('quarantine_records', metadata, *common(),
        sa.Column('error_reason', sa.Text, nullable=False))
    return batches, businesses, quarantine


def require_schema(engine):
    """Check names/types needed for operations before accepting uploads as batches."""
    inspector = sa.inspect(engine)
    for table in tables(engine.dialect.name):
        if not inspector.has_table(table.name, schema=table.schema):
            raise IngestionError('Ingestion schema is not installed; DBA verification is required',
                                 503, 'schema_not_ready')
        columns = {c['name']: c for c in inspector.get_columns(table.name, schema=table.schema)}
        if set(table.c.keys()) - columns.keys():
            raise IngestionError('Ingestion columns differ from the reviewed contract', 503, 'schema_not_ready')
        for expected in table.c:
            info = columns[expected.name]
            actual = info['type']
            if actual._type_affinity is not expected.type._type_affinity:
                raise IngestionError('Ingestion column types differ from the reviewed contract',
                                     503, 'schema_not_ready')
            if not expected.nullable and info['nullable']:
                raise IngestionError('Required ingestion columns must be NOT NULL', 503, 'schema_not_ready')
            actual_length, expected_length = getattr(actual, 'length', None), getattr(expected.type, 'length', None)
            if actual_length is not None and (expected_length is None or actual_length < expected_length):
                raise IngestionError('Ingestion text columns are narrower than the reviewed contract', 503, 'schema_not_ready')
            if isinstance(expected.type.dialect_impl(engine.dialect), sa.BigInteger) and not isinstance(actual, sa.BigInteger):
                raise IngestionError('Ingestion row counters require BIGINT columns', 503, 'schema_not_ready')
        for name in columns.keys() - set(table.c.keys()):
            info = columns[name]
            if not info['nullable'] and info.get('default') is None and not info.get('identity'):
                raise IngestionError('Additional required ingestion columns need DBA review', 503, 'schema_not_ready')
        expected_unique = {tuple(c.name for c in table.primary_key)}
        expected_unique.update(tuple(c.name for c in constraint.columns)
                               for constraint in table.constraints if isinstance(constraint, sa.UniqueConstraint))
        actual_unique = {tuple(inspector.get_pk_constraint(table.name, schema=table.schema)['constrained_columns'])}
        actual_unique.update(tuple(c['column_names']) for c in inspector.get_unique_constraints(table.name, schema=table.schema))
        if not expected_unique <= actual_unique:
            raise IngestionError('Ingestion uniqueness constraints are missing', 503, 'schema_not_ready')
        if table.name != 'raw_ingest_batches':
            references = inspector.get_foreign_keys(table.name, schema=table.schema)
            if not any(fk['constrained_columns'] == ['batch_id'] and
                       fk['referred_table'] == 'raw_ingest_batches' and
                       fk['referred_schema'] == table.schema and
                       fk['referred_columns'] == ['batch_id'] for fk in references):
                raise IngestionError('Ingestion batch foreign keys are missing', 503, 'schema_not_ready')


def progress(record):
    total = record['total_rows']
    completed = record['status'] == 'COMPLETED'
    percentage = 100.0 if completed else (min(99.9, record['processed_rows'] * 100 / total) if total else 0.0)
    return dict(batch_id=record['batch_id'], status=record['status'].lower(),
                total_rows=total, processed_rows=record['processed_rows'], valid_count=record['valid_count'],
                quarantine_count=record['quarantine_count'], progress_pct=round(percentage, 1),
                imported=record['valid_count'], total=total, percent=round(percentage, 1),
                error_message=record['error_message'], task_id=record['task_id'],
                created_at=record['created_at'].isoformat(), updated_at=record['updated_at'].isoformat())
