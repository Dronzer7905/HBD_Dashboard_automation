"""Metadata-only bronze contract check. Uses libpq PG* / PGSERVICE authentication.

Does not import app/config/.env, install tables, migrate, or read business rows.
No passwords or credential-bearing URIs are accepted on the command line.
"""
import argparse
import json
from pathlib import Path
import sys

import sqlalchemy as sa

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services.ingestion_storage import IngestionError
from services.ingestion_store import require_schema, tables


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected-database', required=True)
    args = parser.parse_args()
    engine = sa.create_engine('postgresql+psycopg2://', connect_args={
        'connect_timeout': 8,
        'options': '-c default_transaction_read_only=on -c statement_timeout=5000 -c lock_timeout=2000',
        'application_name': 'BG113-contract-inspection-readonly'})
    try:
        with engine.connect() as connection:
            context = connection.execute(sa.text("SELECT current_database() AS database, current_user AS actor, "
                                                 "current_setting('transaction_read_only') AS read_only")).mappings().one()
            if context['database'] != args.expected_database or context['read_only'] != 'on':
                print(json.dumps({'schema_contract_compatible': False, 'code': 'unexpected_database_context'}))
                return 2
        report = {'context': dict(context), 'schema_contract_compatible': False, 'tables': {}}
        inspector = sa.inspect(engine)
        for table in tables('postgresql'):
            exists = inspector.has_table(table.name, schema=table.schema)
            report['tables'][table.fullname] = {'exists': exists}
            if exists:
                report['tables'][table.fullname]['columns'] = [
                    {'name': c['name'], 'type': str(c['type']), 'nullable': c['nullable']}
                    for c in inspector.get_columns(table.name, schema=table.schema)]
        try:
            require_schema(engine)
            report['schema_contract_compatible'] = True
        except IngestionError as error:
            report['message'] = str(error)
        print(json.dumps(report, indent=2))
        return 0 if report['schema_contract_compatible'] else 2
    except sa.exc.SQLAlchemyError:
        print(json.dumps({'schema_contract_compatible': False, 'code': 'connection_or_metadata_error',
                          'message': 'Read-only inspection failed; confidential connection details withheld'}))
        return 1
    finally:
        engine.dispose()


if __name__ == '__main__':
    raise SystemExit(main())
