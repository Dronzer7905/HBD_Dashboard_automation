"""Offline walkthrough; optional persistent SQLite snapshot with synthetic data only.

Never imports the application/config, reads .env, or connects to company systems.
--database must name a NEW SQLite file directly under this worktree's scratch/.
"""
import argparse
import json
from pathlib import Path

from test_mapping_local import LocalMappingTests, Association, History, Source
from extensions import db


def show(label, response, expected=200):
    print(f'\n{label} -> HTTP {response.status_code}')
    print(json.dumps(response.json, indent=2, ensure_ascii=True))
    if response.status_code != expected:
        raise AssertionError(f'Unexpected HTTP status for {label}')
    return response.json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, help='New local SQLite file under scratch/')
    options = parser.parse_args()
    fixture = LocalMappingTests('test_single_product_mapping_and_actor_audit')
    if options.database:
        path = options.database.resolve()
        scratch = Path(__file__).resolve().parents[2] / 'scratch'
        if path.parent != scratch or path.suffix != '.sqlite3' or path.exists():
            parser.error('--database must be a new .sqlite3 file directly under this worktree scratch/')
        fixture.database_uri = 'sqlite:///' + path.as_posix()
    fixture.setUp()
    try:
        fixture.set_source('local grocery shop')
        show('1. Product options from verified catalog columns', fixture.get('?product_limit=2'))
        dry = show('2. Default dry-run', fixture.post('auto-map', {'platform_name': 'Synthetic'}))
        assert dry['dry_run'] is True and History.query.count() == 0
        payload = {'mapping_id': 1, 'master_category_id': 2, 'parent_category_id': 1}
        show('3. Viewer cannot approve', fixture.post('map-category', payload, fixture.viewer), 403)
        show('4. Existing manual approval', fixture.post('map-category', payload))
        repeat = show('5. Repeated manual approval', fixture.post('map-category', payload))
        assert repeat['changed'] is False and History.query.count() == 1
        associations = show('6. Two local product associations', fixture.associate([101, 102]))
        assert associations['data']['saved'] == 2
        repeat = show('7. Repeated product associations', fixture.associate([101, 102]))
        assert repeat['data']['saved'] == 0 and repeat['changed'] is False
        db.session.add(Source(platform_name='Synthetic', platform_category_raw='Dairy Products',
                              platform_subcategory_raw='', mapping_status='PENDING'))
        db.session.commit()
        saved = show('8. Administrator persists a source mapping', fixture.persist(platform_name='Synthetic'))
        assert saved['summary']['saved'] == 1
        repeat = show('9. Repeated admin request', fixture.persist(platform_name='Synthetic'))
        assert repeat['summary']['saved'] == 0
        assert Association.query.count() == 2 and History.query.count() == 4
        print('\nVerified: 2 local associations; 4 audit rows; no company connection.')
        if options.database:
            print('Synthetic local database:', options.database.resolve())
    finally:
        fixture.tearDown()
        fixture.doCleanups()


if __name__ == '__main__':
    main()
