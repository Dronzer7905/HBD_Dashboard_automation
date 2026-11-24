"""Explicit operator CLI. Defaults to metadata inspection; never imports app/.env.

Uses libpq PGHOST/PGPORT/PGDATABASE/PGUSER/PGPASSFILE or PGSERVICE authentication.
Passwords/DSNs are not accepted as command-line options and are never printed.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
from services.mapping_schema import inspect_contract, verify_contract, SchemaContractError

SQL_FILE = BACKEND / 'sql/bg111/001_create_relationships.sql'


def apply_schema(connection, expected_database, environment):
    if environment not in ('local', 'staging'):
        raise ValueError('Only an explicitly confirmed non-production target is allowed')
    with connection.cursor() as cursor:
        cursor.execute('SELECT current_database()')
        if cursor.fetchone()[0] != expected_database:
            raise ValueError('Connected database differs from the explicit expected database')
        for setting, value in [('bg111.environment', environment),
                               ('bg111.target_database', expected_database),
                               ('bg111.confirm_write', 'I_CONFIRM_NON_PRODUCTION')]:
            cursor.execute('SELECT set_config(%s,%s,false)', (setting, value))
    source = SQL_FILE.read_text(encoding='utf-8')
    if not source.rstrip().endswith('COMMIT;'):
        raise ValueError('Installation SQL has an unexpected transaction boundary')
    # Preserve all SQL guards, but delay commit until the shared verifier passes.
    try:
        with connection.cursor() as cursor:
            cursor.execute(source.rstrip()[:-len('COMMIT;')])
        evidence = verify_contract(connection)
        with connection.cursor() as cursor:
            cursor.execute('COMMIT')
        return evidence
    except Exception:
        with connection.cursor() as cursor:
            cursor.execute('ROLLBACK')
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['inspect', 'verify', 'apply', 'grant'], nargs='?', default='inspect')
    parser.add_argument('--expected-database', required=True)
    parser.add_argument('--application-role', help='Approved existing role, required by grant only')
    parser.add_argument('--environment', choices=['local', 'staging'])
    parser.add_argument('--allow-nonproduction-write', action='store_true')
    args = parser.parse_args(argv)
    if args.action in ('apply', 'grant') and (not args.allow_nonproduction_write or args.environment is None):
        parser.error('apply/grant require --environment local|staging AND --allow-nonproduction-write')
    if args.action not in ('apply', 'grant') and args.allow_nonproduction_write:
        parser.error('Write confirmation is accepted only by explicit apply/grant commands')
    if (args.action == 'grant') != bool(args.application_role):
        parser.error('--application-role is required for grant and forbidden for other commands')
    import psycopg2
    connection = None
    try:
        connection = psycopg2.connect(connect_timeout=8,
            options='-c default_transaction_read_only=on -c statement_timeout=5000 -c lock_timeout=2000',
            application_name='BG111-operator-' + args.action)
        connection.autocommit = True
        with connection.cursor() as cursor:
            cursor.execute('BEGIN TRANSACTION READ ONLY')
            cursor.execute('SELECT current_database()')
            if cursor.fetchone()[0] != args.expected_database:
                raise ValueError('Connected database differs from --expected-database; no writes attempted')
            if args.action in ('apply', 'grant'):
                cursor.execute('ROLLBACK')
        if args.action == 'grant':
            verify_contract(connection)
            with connection.cursor() as cursor:
                for setting,value in [('bg111.environment',args.environment),('bg111.target_database',args.expected_database),
                                      ('bg111.confirm_write','I_CONFIRM_NON_PRODUCTION'),('bg111.application_role',args.application_role)]:
                    cursor.execute('SELECT set_config(%s,%s,false)',(setting,value))
                cursor.execute((SQL_FILE.parent/'003_application_permissions.sql').read_text())
            evidence=verify_contract(connection)
            evidence['granted_to']=args.application_role
        elif args.action == 'apply':
            evidence = apply_schema(connection, args.expected_database, args.environment)
            evidence['installation_sha256'] = hashlib.sha256(SQL_FILE.read_bytes()).hexdigest()
        else:
            evidence = inspect_contract(connection)
            with connection.cursor() as cursor:
                cursor.execute('ROLLBACK')
        print(json.dumps(evidence, indent=2, default=str))
        return 0 if args.action == 'inspect' or evidence['ready'] else 2
    except (ValueError, SchemaContractError) as error:
        print(json.dumps({'status':'blocked', 'message':str(error)}))
        return 2
    except psycopg2.Error as error:
        print(json.dumps({'status':'error', 'code':error.pgcode or 'connection_error',
                          'message':'Database operation failed; no confidential SQL parameters are logged'}))
        return 1
    finally:
        if connection is not None:
            if not connection.closed:
                with connection.cursor() as cursor:
                    cursor.execute('ROLLBACK')
            connection.close()


if __name__ == '__main__':
    raise SystemExit(main())
