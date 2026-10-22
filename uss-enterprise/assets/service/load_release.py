"""Apply the Assets schema and load an immutable dataset release into PostgreSQL.

Reads datasets/releases/<version>/assets.json after checking the release against its own manifest (the content
hash of every file and of the contract, the counts, the version) and loads it in one transaction, parents before
children, in a fixed order, so that two loads of one release give the same database. It refuses a database that
already holds assets. The release stays the source of truth; nothing here edits it.

The connection comes from the libpq environment (PGHOST, PGPORT, PGDATABASE, PGUSER, PGPASSWORD), an administrative
login for these two steps, never the service's read-only login.

    python load_release.py [--release 1.1] [--with-schema]
"""
from pathlib import Path
import argparse
import hashlib
import json
import sys

COMPONENT = Path(__file__).resolve().parents[1]
SCHEMA = COMPONENT / 'schema/schema.sql'
CONTRACT = COMPONENT / 'contracts/assets-v1.1.openapi.json'
RELEASES = COMPONENT / 'datasets/releases'
MEMBERS = ('asset_id', 'kind', 'name', 'description', 'status', 'parent_asset_id')


def read_text_bytes(path):
    """File bytes with CRLF turned into LF: the repository hashes its text releases that way (a checkout may convert)."""
    return Path(path).read_bytes().replace(b'\r\n', b'\n')


def sha256(content):
    return hashlib.sha256(content).hexdigest()


def read_release(release_directory, contract=CONTRACT):
    """The assets of a release, after its manifest has vouched for every file. Raises ValueError on any difference."""
    release = Path(release_directory)
    manifest = json.loads(read_text_bytes(release / 'manifest.json').decode('utf-8'))
    if manifest.get('datasetVersion') != release.name:
        raise ValueError('The manifest names another dataset version than its folder')
    for name, expected in manifest['files'].items():
        if sha256(read_text_bytes(release / name)) != expected:
            raise ValueError(f'Content hash differs from the manifest: {name}')
    if 'assets.json' not in manifest['files']:
        raise ValueError('The manifest does not cover assets.json')
    if sha256(read_text_bytes(contract)) != manifest['contractSha256']:
        raise ValueError('The contract differs from the one the release was made against')
    document = json.loads(read_text_bytes(release / 'assets.json').decode('utf-8'))
    assets = document['assets']
    if manifest['counts']['assets'] != len(assets):
        raise ValueError('The asset count differs from the manifest')
    return manifest, assets


def parents_first(assets):
    """The assets ordered so that every parent comes before its children: by depth, then by identifier order."""
    by_id = {a['assetId']: a for a in assets}
    if len(by_id) != len(assets):
        raise ValueError('Duplicate asset identifiers')

    def depth(asset_id):
        seen = set()
        count = 0
        parent = by_id[asset_id]['parentAssetId']
        while parent is not None:
            if parent not in by_id:
                raise ValueError(f'{asset_id}: the parent {parent} is not in the release')
            if parent in seen or parent == asset_id:
                raise ValueError(f'{asset_id}: the parent chain has a cycle')
            seen.add(parent)
            count += 1
            parent = by_id[parent]['parentAssetId']
        return count

    def order(asset):
        prefix, number = asset['assetId'].split('-')
        return depth(asset['assetId']), prefix, int(number)

    return sorted(assets, key=order)


def apply_schema(connection):
    connection.execute(SCHEMA.read_text(encoding='utf-8'))
    connection.commit()


def verify_stored(connection, assets):
    """Check that the database holds exactly these assets, the derived category included. Raises ValueError otherwise."""
    stored = {row[0]: row for row in connection.execute(
        'SELECT asset_id, kind, category, name, description, status, parent_asset_id FROM asset_records')}
    if len(stored) != len(assets):
        raise ValueError('The number of stored assets differs from the release')
    for asset in assets:
        row = stored.get(asset['assetId'])
        if row is None or list(row[1:]) != [asset['kind'], asset['category'], asset['name'], asset['description'], asset['status'], asset['parentAssetId']]:
            raise ValueError(f'{asset["assetId"]}: the stored record differs from the release (the category included)')


def load(connection, assets):
    """Insert the assets in one transaction; refuse a database that already has some; verify what was stored."""
    with connection.transaction():
        if connection.execute('SELECT count(*) FROM assets').fetchone()[0]:
            raise ValueError('The database already holds assets; the release is loaded into an empty database only')
        for asset in parents_first(assets):
            connection.execute(
                'INSERT INTO assets (asset_id, kind, name, description, status, parent_asset_id) VALUES (%s, %s, %s, %s, %s, %s)',
                (asset['assetId'], asset['kind'], asset['name'], asset['description'], asset['status'], asset['parentAssetId']))
        verify_stored(connection, assets)
    return len(assets)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--release', default='1.1')
    parser.add_argument('--with-schema', action='store_true', help='apply schema/schema.sql first (an empty database)')
    args = parser.parse_args(argv)
    import psycopg
    try:
        manifest, assets = read_release(RELEASES / args.release)
        with psycopg.connect(connect_timeout=10, application_name='assets-load') as connection:
            if args.with_schema:
                apply_schema(connection)
            count = load(connection, assets)
    except (ValueError, OSError, psycopg.Error) as error:
        print('FAIL: ' + str(error), file=sys.stderr)
        return 1
    print(f'LOADED {count} assets of release {manifest["datasetVersion"]}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
