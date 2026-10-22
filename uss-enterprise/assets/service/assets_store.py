"""PostgreSQL access of the Assets read service: reads only, through psycopg 3.

The connection comes from the libpq environment (PGHOST, PGPORT, PGDATABASE, PGUSER, PGPASSWORD), so no credential
is ever written to a file or to a command line. Every connection is read-only, and the service never issues a
statement that changes data. One short connection per request keeps the service plain and survives a restart of the
database.
"""
import psycopg
from psycopg import IsolationLevel
from psycopg.rows import dict_row

from assets_logic import Reference

COLUMNS = 'asset_id, kind, category, name, description, status, parent_asset_id'
ORDER = 'ORDER BY asset_prefix COLLATE "C", asset_number'
FILTER_COLUMNS = (('kind', 'kind'), ('category', 'category'), ('status', 'status'), ('parent_asset_id', 'parent_asset_id'))


class PostgresStore:
    def __init__(self, connect_timeout=5):
        self.connect_timeout = connect_timeout

    def connect(self):
        connection = psycopg.connect(connect_timeout=self.connect_timeout, application_name='assets-service', row_factory=dict_row)
        connection.read_only = True
        return connection

    def reference(self):
        """The kinds, categories and statuses the database defines: the one place those tables live."""
        with self.connect() as connection:
            kinds = frozenset(r['kind'] for r in connection.execute('SELECT kind FROM asset_kinds'))
            categories = frozenset(r['category'] for r in connection.execute('SELECT category FROM asset_categories'))
            statuses = frozenset(r['status'] for r in connection.execute('SELECT status FROM asset_statuses'))
        return Reference(kinds=kinds, categories=categories, statuses=statuses)

    def get(self, asset_id):
        with self.connect() as connection:
            return connection.execute(f'SELECT {COLUMNS} FROM asset_records WHERE asset_id = %s', (asset_id,)).fetchone()

    def page(self, query):
        """The assets that match the filters in id order, one page of them, and the total before paging."""
        conditions = []
        parameters = []
        for field, column in FILTER_COLUMNS:
            value = getattr(query, field, None)
            if value is not None:
                conditions.append(f'{column} = %s')
                parameters.append(value)
        where = ('WHERE ' + ' AND '.join(conditions)) if conditions else ''
        with self.connect() as connection:
            # One snapshot for the count and the page, so that the two agree.
            connection.isolation_level = IsolationLevel.REPEATABLE_READ
            total = connection.execute(f'SELECT count(*) AS total FROM asset_records {where}', parameters).fetchone()['total']
            if query.offset >= total:
                return [], total
            rows = connection.execute(f'SELECT {COLUMNS} FROM asset_records {where} {ORDER} LIMIT %s OFFSET %s',
                                      parameters + [query.limit, query.offset]).fetchall()
        return rows, total
