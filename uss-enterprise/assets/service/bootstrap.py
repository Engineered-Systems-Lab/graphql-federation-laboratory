"""Prepare the Assets database at start: the schema, dataset release 1.1 and the service's read-only login.

Runs as the one-shot bootstrap container of compose.yaml, with the administrative login from the libpq environment
(PGHOST, PGPORT, PGDATABASE, PGUSER, PGPASSWORD). It is idempotent:

  - no schema yet: apply the schema, load the release, create the service login;
  - schema present and empty (an earlier start stopped half way): load the release;
  - assets present: verify that they are exactly the release and change nothing (a difference is a failure).

The service login (ASSETS_SERVICE_USER, ASSETS_SERVICE_PASSWORD) is created or its password set on every start,
a member of assets_reader and read-only. Passwords are never printed, and the server is told not to log the
statement of an error while they travel in it.

    python bootstrap.py [--release 1.1]
"""
from pathlib import Path
import argparse
import os
import re
import sys

import load_release

LOGIN = re.compile(r'^[a-z_][a-z0-9_]{0,62}$')


def ensure_service_login(connection, user, password):
    from psycopg import sql
    if not LOGIN.match(user):
        raise ValueError('ASSETS_SERVICE_USER is not a plain lower-case identifier')
    if not password:
        raise ValueError('ASSETS_SERVICE_PASSWORD is empty')
    # A password inside a failed statement must not reach the server log (the administrative login may set this).
    connection.execute("SET log_min_error_statement = 'panic'")
    exists = connection.execute('SELECT 1 FROM pg_roles WHERE rolname = %s', (user,)).fetchone()
    name, secret = sql.Identifier(user), sql.Literal(password)
    if exists:
        connection.execute(sql.SQL('ALTER ROLE {} WITH LOGIN PASSWORD {}').format(name, secret))
        connection.execute(sql.SQL('GRANT assets_reader TO {}').format(name))
    else:
        connection.execute(sql.SQL('CREATE ROLE {} LOGIN PASSWORD {} IN ROLE assets_reader').format(name, secret))
    connection.execute(sql.SQL('ALTER ROLE {} SET default_transaction_read_only = on').format(name))
    connection.commit()


def prepare(connection, assets, user, password):
    """Bring the database to the release; returns what was done: 'loaded' or 'verified'."""
    if connection.execute("SELECT to_regclass('public.assets')").fetchone()[0] is None:
        load_release.apply_schema(connection)
    if connection.execute('SELECT count(*) FROM assets').fetchone()[0] == 0:
        load_release.load(connection, assets)
        action = 'loaded'
    else:
        with connection.transaction():
            load_release.verify_stored(connection, assets)
        action = 'verified'
    ensure_service_login(connection, user, password)
    return action


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--release', default='1.1')
    args = parser.parse_args(argv)
    import psycopg
    try:
        manifest, assets = load_release.read_release(load_release.RELEASES / args.release)
        user = os.environ.get('ASSETS_SERVICE_USER', 'assets_service')
        password = os.environ.get('ASSETS_SERVICE_PASSWORD', '')
        with psycopg.connect(connect_timeout=10, application_name='assets-bootstrap') as connection:
            action = prepare(connection, assets, user, password)
    except (ValueError, OSError, psycopg.Error) as error:
        print('FAIL: ' + str(error), file=sys.stderr)
        return 1
    print(f'BOOTSTRAP {action} {len(assets)} assets of release {manifest["datasetVersion"]}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
