"""Real PostgreSQL 17 acceptance of the Assets read service, slice 3.

A disposable postgres container is created, the schema is applied, release 1.1 is loaded by the real load script and the
service runs as a local process against it. The tests then check the service against contract 1.1, the expected outcomes
written in the dataset provenance, the filters, the paging and the order, the rules the database enforces and the fact
that the service never writes. The container is always removed. Docker, the image or the driver missing is a failure.
Established: this slice only. Not established: the Dockerfile and compose packaging, the federation, Python 3.13 (the gate
runs under the admitted interpreter) and any write endpoint (none exists).
"""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import quote, urlencode
import hashlib
import json
import re
import subprocess
import sys
import tempfile
import time
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import gate_support as gate  # noqa: E402

COMPONENT = gate.COMPONENT
sys.path.insert(0, str(gate.SERVICE))
sys.path.insert(0, str(COMPONENT / 'validation'))
import load_release  # noqa: E402
import jsonschema_subset as js  # noqa: E402
import validate_dataset  # noqa: E402

RELEASE = COMPONENT / 'datasets/releases/1.1'
CONTRACT_FILE = COMPONENT / 'contracts/assets-v1.1.openapi.json'  # the current contract; 1.0 stays published and its examples stay valid
CONTRACT = js.load_json(CONTRACT_FILE)
MANIFEST, ASSETS = load_release.read_release(RELEASE)
PROVENANCE = json.loads(load_release.read_text_bytes(RELEASE / 'provenance.json').decode('utf-8'))
BY_ID = {a['assetId']: a for a in ASSETS}
JSON_TYPE = 'application/json; charset=utf-8'
SCHEMAS = {name: {'$ref': '#/components/schemas/' + name} for name in ('Asset', 'AssetList', 'Error')}
STATE = {}


def number_key(asset_id):
    """Independent of the service: the order the contract states, spelled out once more for the check."""
    prefix, number = asset_id.split('-')
    return prefix, int(number)


EXPECTED_ORDER = sorted(ASSETS, key=lambda a: number_key(a['assetId']))


def setUpModule():
    import psycopg
    from psycopg import sql
    started = time.monotonic()
    postgres = gate.Postgres()
    STATE['postgres'] = postgres
    postgres.start()
    admin = postgres.admin()
    STATE['admin'] = admin
    STATE['version'] = admin.execute('SHOW server_version').fetchone()[0]
    print('assets-service: PostgreSQL ' + STATE['version'] + ' in ' + gate.IMAGE, flush=True)
    phase_started = time.monotonic()
    admin_env = {**postgres.service_env(user='postgres', password=postgres.admin_password)}
    result = subprocess.run([sys.executable, '-B', str(gate.SERVICE / 'load_release.py'), '--with-schema'], env=admin_env,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
    if result.returncode:
        raise RuntimeError('load_release.py failed: ' + result.stderr.decode('utf-8', 'replace') + result.stdout.decode('utf-8', 'replace'))
    print('assets-service: ' + result.stdout.decode('utf-8').strip(), flush=True)
    admin.execute(sql.SQL('CREATE ROLE {} LOGIN PASSWORD {} IN ROLE assets_reader').format(
        sql.Identifier(gate.READER), sql.Literal(postgres.reader_password)))
    admin.execute(sql.SQL('ALTER ROLE {} SET default_transaction_read_only = on').format(sql.Identifier(gate.READER)))
    gate.phase('schema-and-load', phase_started)
    phase_started = time.monotonic()
    service = gate.ServiceProcess(postgres.service_env())
    STATE['service'] = service
    service.start()
    STATE['port'] = service.port
    gate.phase('service-start', phase_started)
    STATE['tests_started'] = time.monotonic()
    gate.phase('setup-total', started)


def tearDownModule():
    started = time.monotonic()
    service = STATE.get('service')
    if service:
        service.stop()
    admin = STATE.get('admin')
    if admin:
        admin.close()
    postgres = STATE.get('postgres')
    if postgres:
        postgres.stop()
    gate.phase('teardown', started)
    if 'tests_started' in STATE:
        gate.phase('tests', STATE['tests_started'])
    print('assets-service: pinned image ' + gate.IMAGE + ' (resolved ' + gate.IMAGE_RESOLVED_ON + '), PostgreSQL ' + str(STATE.get('version')) +
          ', Python ' + sys.version.split()[0] + ', psycopg ' + _psycopg_version(), flush=True)


def _psycopg_version():
    import psycopg
    return psycopg.__version__


def get(target, **kwargs):
    return gate.request(STATE['port'], 'GET', target, **kwargs)


def lookup(asset_id):
    return get('/assets/' + asset_id)


def page(**parameters):
    return get('/assets?' + urlencode(parameters))


class GateCase(unittest.TestCase):
    def assert_error(self, reply, status, code, schema_check=True):
        self.assertEqual(reply.status, status, reply.body)
        self.assertEqual(reply.header('Content-Type'), [JSON_TYPE])
        body = reply.json()
        self.assertEqual(body['code'], code)
        if schema_check:
            self.assertEqual(js.errors(body, SCHEMAS['Error'], CONTRACT), [])
        return body

    def assert_ok(self, reply, schema):
        self.assertEqual(reply.status, 200, reply.body)
        self.assertEqual(reply.header('Content-Type'), [JSON_TYPE])
        body = reply.json()
        self.assertEqual(js.errors(body, SCHEMAS[schema], CONTRACT), [])
        return body


class DatabaseGate(unittest.TestCase):
    """The schema, the load and the rules the database itself enforces (the service is not involved)."""

    def admin(self):
        return STATE['admin']

    def test_01_server_is_postgresql_17(self):
        self.assertTrue(STATE['version'].startswith('17.'), STATE['version'])
        self.assertIn('PostgreSQL 17', self.admin().execute('SELECT version()').fetchone()[0])
        self.assertEqual(self.admin().execute('SHOW server_encoding').fetchone()[0], 'UTF8')

    def test_02_reference_tables_are_the_one_kind_table_and_agree_with_the_contract(self):
        admin = self.admin()
        kinds = dict(admin.execute('SELECT kind, category FROM asset_kinds').fetchall())
        self.assertEqual(kinds, validate_dataset.KIND_CATEGORY)
        schemas = CONTRACT['components']['schemas']
        self.assertEqual(sorted(kinds), sorted(schemas['AssetKind']['enum']))
        self.assertEqual(sorted(set(kinds.values())), sorted(schemas['AssetCategory']['enum']))
        self.assertEqual(sorted(r[0] for r in admin.execute('SELECT status FROM asset_statuses')), sorted(schemas['AssetStatus']['enum']))
        self.assertEqual(dict(admin.execute('SELECT category, can_be_parent FROM asset_categories').fetchall()),
                         {'VEHICLE': True, 'EQUIPMENT': False})
        columns = {r[0] for r in admin.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'assets'")}
        self.assertNotIn('category', columns, 'the category is derived from the kind and never stored')
        self.assertIn('category', {r[0] for r in admin.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'asset_records'")})

    def test_03_the_load_is_exactly_the_release(self):
        rows = self.admin().execute('SELECT asset_id, kind, category, name, description, status, parent_asset_id FROM asset_records').fetchall()
        stored = {r[0]: dict(zip(('assetId', 'kind', 'category', 'name', 'description', 'status', 'parentAssetId'), r)) for r in rows}
        self.assertEqual(len(stored), MANIFEST['counts']['assets'])
        self.assertEqual(stored, BY_ID)

    def test_04_a_second_load_is_refused_and_a_tampered_release_never_loads(self):
        env = gate.Postgres.service_env(STATE['postgres'], user='postgres', password=STATE['postgres'].admin_password)
        again = subprocess.run([sys.executable, '-B', str(gate.SERVICE / 'load_release.py')], env=env, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, timeout=60)
        self.assertEqual(again.returncode, 1)
        self.assertIn('already holds assets', again.stderr.decode('utf-8'))
        self.assertEqual(self.admin().execute('SELECT count(*) FROM assets').fetchone()[0], len(ASSETS))
        with tempfile.TemporaryDirectory() as temporary:
            copy = Path(temporary) / '1.1'
            copy.mkdir()
            for source in RELEASE.iterdir():
                (copy / source.name).write_bytes(source.read_bytes())
            (copy / 'assets.json').write_bytes((copy / 'assets.json').read_bytes().replace(b'ACTIVE', b'MISSING', 1))
            with self.assertRaisesRegex(ValueError, 'Content hash differs'):
                load_release.read_release(copy)
            other = Path(temporary) / '9.9'
            copy.rename(other)
            with self.assertRaisesRegex(ValueError, 'another dataset version'):
                load_release.read_release(other)

    def test_05_schema_and_load_are_reproducible(self):
        postgres = STATE['postgres']
        admin = self.admin()
        names = ['assets_repro_a', 'assets_repro_b']
        try:
            for name in names:
                admin.execute(f'CREATE DATABASE {name}')
                with postgres.admin(name, autocommit=False) as connection:
                    load_release.apply_schema(connection)
                    load_release.load(connection, ASSETS)
                    connection.commit()
            strip = lambda text: '\n'.join(line for line in text.splitlines() if not line.startswith(('\\restrict', '\\unrestrict')))
            schema = [strip(postgres.dump(name, '--schema-only')) for name in names + [gate.DATABASE]]
            data = [strip(postgres.dump(name, '--data-only')) for name in names + [gate.DATABASE]]
            self.assertEqual(schema[0], schema[1])
            self.assertEqual(schema[0], schema[2], 'the schema of the loaded database is the committed schema')
            self.assertEqual(data[0], data[1])
            self.assertEqual(data[0], data[2], 'two loads of one release give the same rows in the same order')
            self.assertEqual(hashlib.sha256(data[0].encode('utf-8')).hexdigest(), hashlib.sha256(data[1].encode('utf-8')).hexdigest())
            self.assertIn('INSERT', data[0] + 'INSERT')  # a plain dump uses COPY; the point is that the text is identical
            self.assertIn('AST-0029', data[0])
        finally:
            for name in names:
                admin.execute(f'DROP DATABASE IF EXISTS {name} WITH (FORCE)')

    def refused(self, statement, parameters=(), states=('23514',), fragment=None):
        import psycopg
        with self.admin().transaction() if False else _rollback(self.admin()) as connection:
            with self.assertRaises(psycopg.Error) as context:
                connection.execute(statement, parameters)
            self.assertIn(context.exception.sqlstate, states, str(context.exception))
            if fragment:
                self.assertIn(fragment, str(context.exception))

    def test_06_only_a_vehicle_may_be_a_parent_and_the_parent_must_exist(self):
        insert = "INSERT INTO assets (asset_id, kind, name, description, status, parent_asset_id) VALUES (%s, %s, 'n', 'd', 'ACTIVE', %s)"
        # a non-VEHICLE parent: AST-0004 is a scientific instrument
        self.refused(insert, ('AST-0901', 'TRICORDER', 'AST-0004'), ('23514',), 'only a VEHICLE may carry')
        # a missing parent
        self.refused(insert, ('AST-0902', 'TRICORDER', 'AST-9998'), ('23503',), 'does not exist')
        # an asset is not its own parent (the trigger or the check refuses it, whichever fires first)
        self.refused(insert, ('AST-0903', 'STARSHIP', 'AST-0903'), ('23503', '23514'))
        # moving an existing asset under equipment, or under itself, or into a cycle
        self.refused("UPDATE assets SET parent_asset_id = 'AST-0004' WHERE asset_id = 'AST-0016'", (), ('23514',), 'only a VEHICLE may carry')
        self.refused("UPDATE assets SET parent_asset_id = 'AST-0029' WHERE asset_id = 'AST-0029'", (), ('23514',))
        self.refused("UPDATE assets SET parent_asset_id = 'AST-0023' WHERE asset_id = 'AST-0029'", (), ('23514',), 'its own ancestor')
        self.refused("UPDATE assets SET parent_asset_id = 'AST-0020' WHERE asset_id = 'AST-0031'", (), ('23514',), 'its own ancestor')
        # a vehicle that carries others cannot become equipment
        self.refused("UPDATE assets SET kind = 'PHASER' WHERE asset_id = 'AST-0029'", (), ('23514',), 'carries other assets')
        # a deletion that would orphan a child
        self.refused("DELETE FROM assets WHERE asset_id = 'AST-0029'", (), ('23503',))
        # the valid cases of the same statements are accepted: the refusals above are about the rule, not the shape
        with _rollback(self.admin()) as connection:
            connection.execute(insert, ('AST-0904', 'TRICORDER', 'AST-0029'))
            connection.execute(insert, ('AST-0905', 'PHASER', 'AST-0020'))
            connection.execute(insert, ('AST-0906', 'ROVER', 'AST-0029'))
            connection.execute(insert, ('AST-0907', 'ARMORED_VEHICLE', None))
            self.assertEqual(connection.execute("SELECT category FROM asset_records WHERE asset_id = 'AST-0907'").fetchone()[0], 'VEHICLE')

    def test_07_identifier_text_and_value_constraints(self):
        insert = "INSERT INTO assets (asset_id, kind, name, description, status) VALUES (%s, %s, %s, %s, %s)"
        base = ('AST-0950', 'TRICORDER', 'name', 'description', 'ACTIVE')
        for bad in ('ast-0950', 'AST-0', 'AST-950', 'AST-0000', 'AST-00950', 'E-0950', 'ABCDEFGHI-0950', 'AST-', '-0950', 'AST-0950 ',
                    ' AST-0950', 'AST-0950\n', 'AST_0950', '_AST-0950', 'AST_-0950', 'AS__T-0950', '\xc9ST-0950', 'AST-095a', 'EQ-950', 'SH-17'):
            with self.subTest(asset_id=bad):
                self.refused(insert, (bad,) + base[1:], ('23514',))
        for index, bad in ((2, ''), (2, 'x' * 121), (3, ''), (3, 'x' * 1001), (2, '\U0001F680' * 121)):
            values = list(base)
            values[index] = bad
            with self.subTest(index=index, length=len(bad)):
                self.refused(insert, values, ('23514',))
        self.refused(insert, ('AST-0951', 'SHIP', 'name', 'description', 'ACTIVE'), ('23503',))
        self.refused(insert, ('AST-0952', 'TRICORDER', 'name', 'description', 'LOST'), ('23503',))
        # the bounds count code points: 120 and 1000 of them, each a four-byte character, are accepted
        with _rollback(self.admin()) as connection:
            connection.execute(insert, ('AST-0953', 'TRICORDER', '\U0001F680' * 120, '\U0001F680' * 1000, 'ACTIVE'))
            row = connection.execute("SELECT char_length(name), char_length(description) FROM assets WHERE asset_id = 'AST-0953'").fetchone()
            self.assertEqual(row, (120, 1000))

    def test_08_reference_data_is_append_only_and_a_new_kind_is_one_row(self):
        for statement in ("UPDATE asset_kinds SET category = 'EQUIPMENT' WHERE kind = 'STARSHIP'", "DELETE FROM asset_kinds WHERE kind = 'PHASER'",
                          'TRUNCATE asset_kinds CASCADE', "UPDATE asset_categories SET can_be_parent = true WHERE category = 'EQUIPMENT'",
                          "DELETE FROM asset_statuses WHERE status = 'MISSING'", 'TRUNCATE asset_statuses CASCADE'):
            with self.subTest(statement=statement):
                self.refused(statement, (), ('23000',), 'append-only')
        with _rollback(self.admin()) as connection:
            connection.execute("INSERT INTO asset_kinds (kind, category) VALUES ('STATION', 'VEHICLE')")
            connection.execute("INSERT INTO assets (asset_id, kind, name, description, status) VALUES ('ST-0001', 'STATION', 'n', 'd', 'ACTIVE')")
            self.assertEqual(connection.execute("SELECT category FROM asset_records WHERE asset_id = 'ST-0001'").fetchone()[0], 'VEHICLE')

    def test_09_the_database_order_matches_the_contract_order(self):
        rows = self.admin().execute('SELECT asset_id FROM asset_records ORDER BY asset_prefix COLLATE "C", asset_number').fetchall()
        self.assertEqual([r[0] for r in rows], [a['assetId'] for a in EXPECTED_ORDER])
        # AST-9999 before AST-10000, the shorter prefix before the longer and a prefix with an underscore after its stem, on rows that the dataset does not hold
        with _rollback(self.admin()) as connection:
            for asset_id in ('AB_C-0001', 'AB-0100', 'AST-10000', 'AST-9999'):
                connection.execute("INSERT INTO assets (asset_id, kind, name, description, status) VALUES (%s, 'SHUTTLE', 'n', 'd', 'ACTIVE')", (asset_id,))
            ordered = [r[0] for r in connection.execute(
                "SELECT asset_id FROM asset_records WHERE asset_id IN ('AB_C-0001', 'AB-0100', 'AST-10000', 'AST-9999', 'AST-0023', 'AST-0025') "
                'ORDER BY asset_prefix COLLATE "C", asset_number')]
        self.assertEqual(ordered, ['AB-0100', 'AB_C-0001', 'AST-0023', 'AST-0025', 'AST-9999', 'AST-10000'])


class _rollback:
    """A connection in a transaction that is always rolled back, so that a refusal or an experiment leaves nothing behind."""

    def __init__(self, connection):
        self.connection = connection

    def __enter__(self):
        self.connection.autocommit = False
        return self.connection

    def __exit__(self, *exception):
        self.connection.rollback()
        self.connection.autocommit = True
        return False


class ExpectedOutcomes(GateCase):
    """The expected mapping of the dataset provenance, in its three layers, for each Missions reference.

    The first layer (what the mapping says) is the integration layer's; Assets is asked only for the targets of the mapping, and the
    service never sees a Missions reference except as a malformed identifier.
    """

    def test_01_every_expected_reference(self):
        expected = PROVENANCE['expectedMapping']
        self.assertEqual({e['missionsReference'] for e in expected}, {'EQ-64', 'EQ-75', 'EQ-86', 'EQ-97', 'EQ-108', 'EQ-119', 'SH-42', 'SH-53', 'VS-31'})
        for entry in expected:
            with self.subTest(reference=entry['missionsReference'], case=entry['case']):
                if entry['mapsTo'] is None:
                    self.assertEqual(entry['case'], 'UNMAPPED')
                    self.assertTrue(entry['assetsAnswers'].startswith('not asked'))
                    continue
                reply = lookup(entry['mapsTo'])
                if entry['heldByAssets']:
                    self.assertEqual(entry['assetsAnswers'][:3], '200')
                    body = self.assert_ok(reply, 'Asset')
                    self.assertEqual(body['status'], entry['status'])
                    self.assertEqual(body, BY_ID[entry['mapsTo']])
                else:
                    self.assertEqual(entry['assetsAnswers'], '404 ASSET_NOT_FOUND')
                    self.assert_error(reply, 404, 'ASSET_NOT_FOUND')

    def test_02_the_named_cases(self):
        # mapped but not found: well formed, held by nobody
        self.assert_error(lookup('AST-0097'), 404, 'ASSET_NOT_FOUND')
        # unmapped: Assets is never asked; and a Missions reference asked of it by mistake is a malformed id, never a missing asset
        for reference in ('EQ-108', 'EQ-97', 'EQ-64', 'VS-31', 'SH-53'):
            self.assert_error(lookup(reference), 400, 'INVALID_ASSET_ID')
        self.assertEqual(self.assert_ok(lookup('AST-0025'), 'Asset')['status'], 'DESTROYED')
        self.assertEqual(self.assert_ok(lookup('AST-0006'), 'Asset')['status'], 'MISSING')
        for asset_id in ('AST-0029', 'AST-0024', 'AST-0004', 'AST-0005', 'AST-0007'):
            self.assertEqual(self.assert_ok(lookup(asset_id), 'Asset')['status'], 'ACTIVE')

    def test_03_every_unreferenced_asset_resolves(self):
        reached = {e['mapsTo'] for e in PROVENANCE['expectedMapping'] if e['heldByAssets']}
        unreferenced = [a for a in ASSETS if a['assetId'] not in reached]
        self.assertEqual(len(unreferenced), len(ASSETS) - 7)
        for asset in unreferenced:
            with self.subTest(asset=asset['assetId']):
                self.assertEqual(self.assert_ok(lookup(asset['assetId']), 'Asset'), asset)

    def test_04_every_asset_of_the_release_is_served_unchanged(self):
        for asset in ASSETS:
            with self.subTest(asset=asset['assetId']):
                self.assertEqual(self.assert_ok(lookup(asset['assetId']), 'Asset'), asset)

    def test_05_the_parent_chains(self):
        self.assertEqual(PROVENANCE['parentChains'], [['AST-0004', 'AST-0023', 'AST-0029'], ['AST-0012', 'AST-0020', 'AST-0027', 'AST-0031']])
        for chain in PROVENANCE['parentChains']:
            walked = [chain[0]]
            current = self.assert_ok(lookup(chain[0]), 'Asset')
            while current['parentAssetId'] is not None:
                walked.append(current['parentAssetId'])
                parent = self.assert_ok(lookup(current['parentAssetId']), 'Asset')
                self.assertEqual(parent['category'], 'VEHICLE')
                current = parent
            self.assertEqual(walked, chain)
        # the assets aboard a vehicle are listed by the parent filter
        aboard = self.assert_ok(page(parentAssetId='AST-0029'), 'AssetList')
        self.assertEqual([i['assetId'] for i in aboard['items']], [a['assetId'] for a in EXPECTED_ORDER if a['parentAssetId'] == 'AST-0029'])


# Each valid example of the contract: the request that produces it, the status the contract documents and what must agree.
EXAMPLES = {
    'asset-starship-active.json': ('GET', '/assets/AST-0029', 200, 'Asset', ('kind', 'status')),
    'asset-shuttle-maintenance.json': ('GET', '/assets/AST-0026', 200, 'Asset', ('kind', 'status')),
    'asset-shuttle-destroyed.json': ('GET', '/assets/AST-0025', 200, 'Asset', ('kind', 'status')),
    'asset-rover-active.json': ('GET', '/assets/AST-0020', 200, 'Asset', ('kind', 'status')),
    'asset-armored-vehicle-active.json': ('GET', '/assets/AST-0001', 200, 'Asset', ('kind', 'status')),
    'asset-equipment-with-parent.json': ('GET', '/assets/AST-0005', 200, 'Asset', ('kind', 'status')),
    'asset-equipment-aboard-rover.json': ('GET', '/assets/AST-0016', 200, 'Asset', ('kind', 'status')),
    'asset-equipment-decommissioned.json': ('GET', '/assets/AST-0010', 200, 'Asset', ('kind', 'status')),
    'asset-equipment-missing.json': ('GET', '/assets/AST-0006', 200, 'Asset', ('category', 'status')),  # the dataset holds no missing communicator
    'asset-musical-instrument-active.json': ('GET', '/assets/AST-0017', 200, 'Asset', ('kind', 'status')),
    'asset-list.json': ('GET', '/assets?limit=3', 200, 'AssetList', ('offset', 'limit')),
    'asset-list-category-vehicle.json': ('GET', '/assets?category=VEHICLE', 200, 'AssetList', ('offset', 'limit')),
    'asset-list-empty.json': ('GET', '/assets?parentAssetId=AST-0097', 200, 'AssetList', ('offset', 'limit', 'total', 'items')),
    'asset-list-beyond-end.json': ('GET', '/assets?offset=40', 200, 'AssetList', ('offset', 'limit')),
    'error-asset-not-found.json': ('GET', '/assets/AST-0097', 404, 'Error', ('code',)),
    'error-path-not-found.json': ('GET', '/other', 404, 'Error', ('code',)),
    'error-invalid-asset-id.json': ('GET', '/assets/eq-64', 400, 'Error', ('code',)),
    'error-invalid-request.json': ('GET', '/assets?limit=51', 400, 'Error', ('code',)),
    'error-method-not-allowed.json': ('POST', '/assets/AST-0004', 405, 'Error', ('code',)),
    'error-internal-error.json': ('GET', '/assets/AST-0029', 500, 'Error', ('code',)),  # produced by the failure test below
}


class ContractExamples(GateCase):
    """Every valid example of the contract is answered by the live service with the documented status and a body of the documented shape."""

    def fixture(self, name):
        return js.load_json(COMPONENT / 'fixtures/v1.1/valid' / name)

    def documented(self, method, target, status):
        if status == 404 and not target.startswith('/assets'):
            self.assertEqual(CONTRACT['x-unmatchedPath']['response'], {'$ref': '#/components/responses/PathNotFound'})
            return
        path = '/assets' if target.split('?')[0] == '/assets' else '/assets/{assetId}'
        operation = CONTRACT['paths'][path]
        if status == 405:
            self.assertIn(method, operation['x-unsupportedMethods']['methods'])
        else:
            self.assertIn(str(status), operation['get']['responses'])

    def test_01_the_table_covers_every_valid_example_and_each_is_used_by_the_contract(self):
        on_disk = sorted(p.name for p in (COMPONENT / 'fixtures/v1.1/valid').glob('*.json'))
        self.assertEqual(sorted(EXAMPLES), on_disk)
        linked = re.findall(r'"externalValue": "\.\./fixtures/v1\.1/valid/([^"]+)"', CONTRACT_FILE.read_text(encoding='utf-8'))
        self.assertEqual(sorted(linked), on_disk)

    def test_02_each_example_is_answered(self):
        for name, (method, target, status, schema, same) in EXAMPLES.items():
            if status == 500:
                continue  # needs a failing database: see InternalFailure
            with self.subTest(example=name):
                self.documented(method, target, status)
                reply = gate.request(STATE['port'], method, target)
                example = self.fixture(name)
                self.assertEqual(js.errors(example, SCHEMAS[schema], CONTRACT), [], 'the example itself')
                self.assertEqual(reply.status, status)
                body = reply.json()
                self.assertEqual(js.errors(body, SCHEMAS[schema], CONTRACT), [])
                self.assertEqual(reply.header('Content-Type'), [JSON_TYPE])
                if status == 405:
                    self.assertEqual(reply.header('Allow'), ['GET'])
                if schema == 'Asset':
                    self.assertEqual(sorted(body), sorted(example))
                if schema == 'AssetList':
                    self.assertEqual(sorted(body), sorted(example))
                for member in same:
                    self.assertEqual(body[member], example[member], member)

    def test_03_the_list_examples_carry_the_documented_meaning(self):
        self.assertEqual(len(get('/assets?limit=3').json()['items']), 3)
        vehicles = get('/assets?category=VEHICLE').json()
        self.assertTrue(vehicles['items'] and all(i['category'] == 'VEHICLE' for i in vehicles['items']))
        self.assertEqual(vehicles['total'], sum(1 for a in ASSETS if a['category'] == 'VEHICLE'))
        beyond = get('/assets?offset=100').json()
        self.assertEqual((beyond['items'], beyond['total']), ([], len(ASSETS)))


class Listing(GateCase):
    """Filters alone and combined, paging and order, checked against what the release itself says."""

    def expected(self, offset=0, limit=20, **filters):
        matching = [a for a in EXPECTED_ORDER if all(a[field] == value for field, value in filters.items())]
        return {'items': matching[offset:offset + limit], 'offset': offset, 'limit': limit, 'total': len(matching)}

    def check(self, offset=0, limit=20, **filters):
        parameters = dict(filters)
        if offset:
            parameters['offset'] = offset
        if limit != 20:
            parameters['limit'] = limit
        query = {('parentAssetId' if k == 'parentAssetId' else k): v for k, v in parameters.items()}
        body = self.assert_ok(get('/assets' + ('?' + urlencode(query) if query else '')), 'AssetList')
        self.assertEqual(body, self.expected(offset, limit, **filters), (filters, offset, limit))
        return body

    def test_01_no_filter_uses_the_documented_defaults(self):
        body = self.check()
        self.assertEqual((body['offset'], body['limit'], body['total'], len(body['items'])), (0, 20, len(ASSETS), 20))
        self.assertEqual(self.check(offset=20)['items'], EXPECTED_ORDER[20:])

    def test_02_order_is_prefix_as_text_then_number_as_a_number(self):
        everything = []
        for offset in range(0, len(ASSETS), 7):
            everything += self.check(offset=offset, limit=7)['items']
        self.assertEqual([a['assetId'] for a in everything], [a['assetId'] for a in EXPECTED_ORDER])
        ids = [a['assetId'] for a in everything]
        self.assertLess(ids.index('AST-0023'), ids.index('AST-0024'))
        self.assertLess(ids.index('AST-0004'), ids.index('AST-0007'))
        self.assertLess(ids.index('AST-0005'), ids.index('AST-0008'))
        self.assertLess(ids.index('AST-0027'), ids.index('AST-0028'))
        # the numbers are zero-padded to four digits, so the text order is the number order here; the database test
        # for the order shows the five-digit case on rows that the dataset does not hold
        self.assertEqual(ids, sorted(ids))

    def test_03_each_filter_alone(self):
        for kind in sorted({a['kind'] for a in ASSETS}):
            self.check(kind=kind)
        for category in ('VEHICLE', 'EQUIPMENT'):
            self.check(category=category)
        for status in ('ACTIVE', 'MAINTENANCE', 'DECOMMISSIONED', 'DESTROYED', 'MISSING'):
            self.check(status=status)
        for parent in sorted({a['parentAssetId'] for a in ASSETS if a['parentAssetId']}):
            self.check(parentAssetId=parent)

    def test_04_the_filters_combine_with_and(self):
        for filters in ({'category': 'VEHICLE', 'status': 'ACTIVE'}, {'category': 'EQUIPMENT', 'status': 'MISSING'},
                        {'kind': 'SHUTTLE', 'status': 'MAINTENANCE'}, {'kind': 'TRICORDER', 'parentAssetId': 'AST-0029'},
                        {'category': 'EQUIPMENT', 'parentAssetId': 'AST-0029', 'status': 'ACTIVE'},
                        {'kind': 'PHASER', 'category': 'EQUIPMENT', 'status': 'ACTIVE', 'parentAssetId': 'AST-0029'},
                        {'kind': 'PHASER', 'category': 'VEHICLE'},  # a kind and a category that disagree select nothing
                        {'status': 'DESTROYED', 'category': 'VEHICLE'}):
            with self.subTest(filters=filters):
                self.check(**filters)
        self.assertEqual(self.check(kind='PHASER', category='VEHICLE')['total'], 0)

    def test_05_a_parent_that_names_no_asset_selects_nothing(self):
        for parent in ('AST-0097', 'AST-0500', 'AST-31000'):
            body = self.assert_ok(get('/assets?parentAssetId=' + parent), 'AssetList')
            self.assertEqual(body, {'items': [], 'offset': 0, 'limit': 20, 'total': 0})
        # an asset that exists but carries nothing also selects nothing
        self.assertEqual(self.check(parentAssetId='AST-0004')['total'], 0)

    def test_06_paging_and_its_bounds(self):
        total = len(ASSETS)
        self.assertEqual(len(self.check(limit=1)['items']), 1)
        self.assertEqual(len(self.check(limit=50)['items']), min(50, total))
        self.check(offset=total - 1, limit=5)
        for offset in (total, total + 1, 1000, 10 ** 12):
            body = self.assert_ok(get(f'/assets?offset={offset}'), 'AssetList')
            self.assertEqual((body['items'], body['offset'], body['limit'], body['total']), ([], offset, 20, total))
        huge = 99999999999999999999999999
        body = self.assert_ok(get(f'/assets?offset={huge}&limit=50'), 'AssetList')
        self.assertEqual((body['items'], body['offset'], body['total']), ([], huge, total))
        self.assertEqual(self.assert_ok(get('/assets?offset=0&limit=20'), 'AssetList'), self.expected())
        self.check(category='VEHICLE', offset=5, limit=4)
        self.check(category='EQUIPMENT', offset=100, limit=4)

    def test_07_every_bad_query_is_400_invalid_request(self):
        bad = ['limit=0', 'limit=51', 'limit=-1', 'limit=05', 'limit=1.5', 'limit=abc', 'limit=', 'limit=+5', 'limit=%2B5', 'limit=1e1', 'limit=%20', 'limit=5%20',
               'offset=-1', 'offset=01', 'offset=1.5', 'offset=abc', 'offset=', 'offset=+1', 'offset=0x10', 'offset=%D9%A1',
               'kind=SHIP', 'kind=shuttle', 'kind=Shuttle', 'kind=', 'kind=SHUTTLE%20', 'kind=SHUTTLE,ROVER', 'kind=EQUIPMENT', 'kind=GROUND_VEHICLE',
               'category=vehicle', 'category=', 'category=SHUTTLE', 'category=VEHICLE,EQUIPMENT', 'category=STATION',
               'status=active', 'status=LOST', 'status=', 'status=ACTIVE,MISSING', 'status=Missing',
               'parentAssetId=ast-0001', 'parentAssetId=', 'parentAssetId=AST-001', 'parentAssetId=AST-', 'parentAssetId=SH-17', 'parentAssetId=AST-0029%20', 'parentAssetId=AST-0029,AST-0023',
               'unknown=1', 'Kind=SHUTTLE', 'KIND=SHUTTLE', 'sort=assetId', 'q=phaser', 'fields=name', 'page=1', 'pageSize=5', 'limit=5&limit=6', 'limit=5&limit=5',
               'kind=SHUTTLE&kind=ROVER', 'kind=SHUTTLE&kind=SHUTTLE', 'offset=1&offset=2', 'status=ACTIVE&status=MISSING',
               'kind', 'kind&limit=5', '&', 'limit=5&', '&limit=5', 'limit=5&&offset=1', '=', '=1', 'limit=5;offset=1',
               'limit=%FF', 'kind=%FF', '%FF=1', 'parentAssetId=%C3%A9']
        for query in bad:
            with self.subTest(query=query):
                self.assert_error(get('/assets?' + query), 400, 'INVALID_REQUEST')
        for query in ('', 'limit=5&offset=1', 'kind=PHASER&status=ACTIVE', 'kind=%53HUTTLE', 'category=%56EHICLE&limit=%35'):
            with self.subTest(good=query):
                self.assertEqual(get('/assets' + ('?' + query if query else '')).status, 200)
        # a lone question mark is an empty query, and the order of parameters carries no meaning
        self.assertEqual(get('/assets?').json(), self.expected())
        self.assertEqual(get('/assets?limit=3&kind=PHASER').json(), get('/assets?kind=PHASER&limit=3').json())
        # the same identifier-looking text in a filter is judged as sent: lower case is refused
        self.assert_error(get('/assets?parentAssetId=vs-31'), 400, 'INVALID_REQUEST')

    def test_08_the_error_message_never_echoes_the_input(self):
        reply = get('/assets?limit=' + quote('<script>alert(1)</script>'))
        self.assertNotIn(b'script', reply.body)
        self.assertLessEqual(len(reply.json()['message']), 1000)


class AssetLookup(GateCase):
    def test_01_status_does_not_change_the_answer(self):
        for status in ('ACTIVE', 'MAINTENANCE', 'DECOMMISSIONED', 'DESTROYED', 'MISSING'):
            asset = next(a for a in EXPECTED_ORDER if a['status'] == status)
            self.assertEqual(self.assert_ok(lookup(asset['assetId']), 'Asset'), asset)

    def test_02_an_identifier_is_validated_exactly_as_sent(self):
        for bad in ('ast-0004', 'Ast-0004', 'AST-004', 'AST-00004', 'AST-0000', 'AST-', '-0004', 'A-0004', 'ABCDEFGHI-0004', 'AST0004', 'AST--0004',
                    'AST-0004-1', 'AST-000a', 'AST-+004', 'AST-4.04', '_AST-0004', 'AST_-0004', 'AS__T-0004', 'SH-17', 'EQ-64', 'VS-31',
                    '%20AST-0004', 'AST-0004%20', 'AST-0004%0A', 'AST-0004%00', '%00', 'AST%2D0004x', 'AST-0004%2F', 'AST%2F0004', '%C3%89ST-0004',
                    'AST-0004%FF', '%FF', 'AST-%EF%BC%90%EF%BC%90%EF%BC%90%EF%BC%94', 'AST-%D9%A0%D9%A0%D9%A0%D9%A4', 'AST-0004%E2%80%8B'):
            with self.subTest(identifier=bad):
                self.assert_error(get('/assets/' + bad), 400, 'INVALID_ASSET_ID')

    def test_03_a_well_formed_identifier_that_names_nothing_is_404(self):
        for unknown in ('AST-0097', 'AST-0108', 'AST-0500', 'AST-1000', 'AST-' + '9' * 40, 'AB-0001', 'AB_CD-0001', 'ABCDE-12345'):
            with self.subTest(identifier=unknown):
                self.assert_error(get('/assets/' + unknown), 404, 'ASSET_NOT_FOUND')

    def test_04_percent_decoding_is_the_only_normalization(self):
        self.assertEqual(self.assert_ok(get('/assets/%41ST-0004'), 'Asset')['assetId'], 'AST-0004')
        self.assertEqual(self.assert_ok(get('/assets/AST%2D0004'), 'Asset')['assetId'], 'AST-0004')
        self.assertEqual(self.assert_ok(get('/assets/%41%53%54-0029'), 'Asset')['assetId'], 'AST-0029')

    def test_05_paths_outside_the_contract_are_404(self):
        for path in ('/', '/assets/', '/assets//', '/assets/AST-0004/', '/assets/AST-0004/extra', '/assets/AST-0004/changes', '/asset/AST-0004', '/Assets', '/ASSETS/AST-0004',
                     '/assets/../assets', '/assets/./AST-0004', '/v1/assets', '/other', '/health', '/openapi.json', '/%61ssets', '/assets%2FAST-0004', '//assets'):
            with self.subTest(path=path):
                self.assert_error(get(path), 404, 'PATH_NOT_FOUND')
        # a path outside the contract is never read as an asset that was looked up and not found
        for path in ('/', '/assets/', '/other'):
            self.assertNotEqual(get(path).json()['code'], 'ASSET_NOT_FOUND', path)
        # outside the two paths a method does not matter; on them only GET is allowed
        self.assert_error(gate.request(STATE['port'], 'POST', '/other'), 404, 'PATH_NOT_FOUND')

    def test_06_unicode_survives_the_trip(self):
        name = 'Ünïcødé ' + '\U0001F680' * 112
        description = 'Prüfung: é中\U0001F680' * 5
        self.assertEqual(len(name), 120)
        admin = STATE['admin']
        admin.execute("INSERT INTO assets (asset_id, kind, name, description, status) VALUES ('AST-0999', 'MUSICAL_INSTRUMENT', %s, %s, 'ACTIVE')", (name, description))
        try:
            reply = get('/assets/AST-0999')
            body = self.assert_ok(reply, 'Asset')
            self.assertEqual((body['name'], body['description'], body['category']), (name, description, 'EQUIPMENT'))
            self.assertEqual(int(reply.header('Content-Length')[0]), len(reply.body))
            self.assertGreater(len(reply.body), len(json.dumps(body, ensure_ascii=False)))  # bytes, not characters
            self.assertEqual(reply.body.decode('utf-8'), json.dumps(body, ensure_ascii=False))
        finally:
            admin.execute("DELETE FROM assets WHERE asset_id = 'AST-0999'")


class HttpMechanics(GateCase):
    def test_01_every_method_but_get_is_405_with_allow_get(self):
        methods = set(CONTRACT['paths']['/assets']['x-unsupportedMethods']['methods']) | set(CONTRACT['paths']['/assets/{assetId}']['x-unsupportedMethods']['methods'])
        self.assertEqual(methods, {'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS'})
        for method in sorted(methods | {'TRACE', 'FOO', 'PROPFIND', 'get'}):
            for target in ('/assets', '/assets/AST-0004', '/assets/AST-0097', '/assets/not-an-id', '/assets?limit=999', '/assets?bogus=1'):
                with self.subTest(method=method, target=target):
                    reply = gate.request(STATE['port'], method, target)
                    self.assertEqual(reply.status, 405)
                    self.assertEqual(reply.header('Allow'), ['GET'])
                    self.assertEqual(reply.header('Content-Type'), [JSON_TYPE])
                    if method == 'HEAD':
                        self.assertEqual(reply.body, b'')
                    else:
                        self.assertEqual(self.assert_error(reply, 405, 'METHOD_NOT_ALLOWED')['code'], 'METHOD_NOT_ALLOWED')

    def test_02_a_write_with_a_body_is_refused_and_changes_nothing(self):
        before = _fingerprint()
        for method in ('POST', 'PUT', 'PATCH', 'DELETE'):
            body = json.dumps({'assetId': 'AST-0998', 'kind': 'PHASER', 'name': 'x', 'description': 'x', 'status': 'ACTIVE', 'parentAssetId': None}).encode()
            reply = gate.request(STATE['port'], method, '/assets/AST-0004' if method != 'POST' else '/assets', {'Content-Type': 'application/json'}, body)
            self.assertEqual(reply.status, 405)
            self.assertEqual(reply.header('Allow'), ['GET'])
        self.assertEqual(_fingerprint(), before)
        self.assertEqual(get('/assets/AST-0998').status, 404)

    def test_03_headers(self):
        for target in ('/assets/AST-0029', '/assets', '/assets/AST-0097', '/assets/bad', '/assets?limit=0', '/nothing'):
            with self.subTest(target=target):
                reply = get(target, headers={'Accept': 'application/xml', 'If-None-Match': '*', 'Accept-Language': 'fr'})
                self.assertEqual(reply.header('Content-Type'), [JSON_TYPE])
                self.assertEqual(int(reply.header('Content-Length')[0]), len(reply.body))
                for name in ('ETag', 'Last-Modified', 'Cache-Control', 'Expires', 'Pragma', 'Age', 'Vary', 'Location', 'Content-Location', 'Set-Cookie', 'Allow'):
                    self.assertEqual(reply.header(name), [], name)
                self.assertEqual(reply.header('Server'), ['AssetsService/1.0'])
                reply.json()  # always JSON, whatever Accept says, and no 406

    def test_04_one_connection_serves_several_requests(self):
        import http.client
        connection = http.client.HTTPConnection('127.0.0.1', STATE['port'], timeout=10)
        try:
            for target, status in (('/assets/AST-0029', 200), ('/assets/AST-0097', 404), ('/assets?limit=2', 200), ('/assets/bad', 400)):
                connection.request('GET', target)
                response = connection.getresponse()
                response.read()
                self.assertEqual(response.status, status)
                self.assertEqual(response.version, 11)
        finally:
            connection.close()

    def test_05_requests_the_server_cannot_parse_answer_json_errors(self):
        port = STATE['port']
        for raw in (b'GARBAGE\r\n\r\n', b'GET\r\n\r\n', b'GET /assets HTTP/9.9\r\n\r\n', b'GET /assets HTTP/1.1 extra\r\n\r\n'):
            with self.subTest(raw=raw):
                reply = gate.raw_exchange(port, raw)
                head, _, body = reply.partition(b'\r\n\r\n')
                self.assertTrue(head.split(b'\r\n')[0].split()[1] in (b'400', b'505'), head)
                self.assertIn(b'application/json', head)
                self.assertEqual(json.loads(body.decode('utf-8'))['code'], 'INVALID_REQUEST')
        long_target = b'GET /assets?' + b'a' * 70000 + b' HTTP/1.1\r\nHost: x\r\n\r\n'
        reply = gate.raw_exchange(port, long_target)
        head, _, body = reply.partition(b'\r\n\r\n')
        self.assertEqual(head.split(b'\r\n')[0].split()[1], b'400')
        self.assertEqual(json.loads(body.decode('utf-8'))['code'], 'INVALID_REQUEST')
        # the service is still healthy afterwards
        self.assertEqual(lookup('AST-0029').status, 200)

    def test_06_concurrent_requests(self):
        ids = [a['assetId'] for a in ASSETS] * 3
        with ThreadPoolExecutor(max_workers=16) as pool:
            replies = list(pool.map(lookup, ids))
        self.assertEqual([r.status for r in replies], [200] * len(ids))
        self.assertEqual([r.json()['assetId'] for r in replies], ids)

    def test_07_the_service_binds_to_loopback_only(self):
        import socket
        connection = socket.create_connection(('127.0.0.1', STATE['port']), timeout=5)
        connection.close()
        listening = subprocess.run(['netstat', '-an'], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=30).stdout.decode('utf-8', 'replace')
        lines = [line for line in listening.splitlines() if f':{STATE["port"]} ' in line and 'LISTEN' in line.upper()]
        self.assertTrue(lines, 'the service is listening')
        for line in lines:
            self.assertTrue('127.0.0.1:' in line or '[::1]:' in line, line)


def _fingerprint():
    rows = STATE['admin'].execute('SELECT asset_id, kind, name, description, status, parent_asset_id FROM assets ORDER BY asset_id').fetchall()
    return hashlib.sha256(json.dumps(rows, ensure_ascii=False).encode('utf-8')).hexdigest()


class ReadOnly(GateCase):
    WRITE = re.compile(r'\b(INSERT|UPDATE|DELETE|TRUNCATE|CREATE|ALTER|DROP|GRANT|REVOKE|COPY|VACUUM|ANALYZE|LOCK|SET|CALL|DO)\b', re.I)

    def test_01_the_database_login_cannot_write(self):
        import psycopg
        postgres = STATE['postgres']
        connection = psycopg.connect(host='127.0.0.1', port=postgres.port, user=gate.READER, password=postgres.reader_password, dbname=gate.DATABASE)
        try:
            self.assertEqual(connection.execute('SHOW default_transaction_read_only').fetchone()[0], 'on')
            for statement in ("INSERT INTO assets (asset_id, kind, name, description, status) VALUES ('AST-0990', 'PHASER', 'n', 'd', 'ACTIVE')",
                              "UPDATE assets SET name = 'x'", 'DELETE FROM assets', 'TRUNCATE assets', 'CREATE TABLE t (a int)',
                              "UPDATE asset_kinds SET category = 'EQUIPMENT'"):
                with self.subTest(statement=statement):
                    with self.assertRaises(psycopg.Error):
                        connection.execute(statement)
                    connection.rollback()
            # even with the privilege granted, the role's own setting keeps its sessions read-only
            STATE['admin'].execute(f'GRANT INSERT, UPDATE, DELETE ON assets TO {gate.READER}')
            try:
                with self.assertRaises(psycopg.errors.ReadOnlySqlTransaction):
                    connection.execute("UPDATE assets SET name = 'x'")
            finally:
                connection.rollback()
                STATE['admin'].execute(f'REVOKE INSERT, UPDATE, DELETE ON assets FROM {gate.READER}')
        finally:
            connection.close()

    @staticmethod
    def server_log():
        result = subprocess.run(['docker', 'logs', STATE['postgres'].name], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
        return (result.stdout + result.stderr).decode('utf-8', 'replace').splitlines()

    def test_02_the_service_only_sent_read_statements_in_read_only_transactions(self):
        before = _fingerprint()
        skipped = len(self.server_log())
        for target in ('/assets', '/assets/AST-0029', '/assets?category=VEHICLE&offset=3', '/assets?status=MISSING', '/assets/AST-0097', '/assets/bad', '/assets?bad=1'):
            get(target)
        gate.request(STATE['port'], 'POST', '/assets')
        self.assertEqual(_fingerprint(), before)
        # The server logged every statement (log_statement=all): read what the service's login sent during this test only.
        statements = [line for line in self.server_log()[skipped:] if f'{gate.READER}@{gate.DATABASE}' in line and ('statement:' in line or 'execute ' in line)]
        self.assertTrue(statements, 'the service connected and its statements were logged')
        text = ' '.join(statements)
        self.assertIn('READ ONLY', text)
        self.assertIn('asset_records', text)
        for line in statements:
            body = line.split('statement:', 1)[-1] if 'statement:' in line else line.split(':  ', 1)[-1]
            if body.strip().upper().startswith('BEGIN'):
                self.assertIn('READ ONLY', body.upper(), 'every transaction the service opens is read-only')
                continue
            if body.strip() in ('COMMIT', 'ROLLBACK'):
                continue
            self.assertTrue(body.strip().upper().startswith('SELECT') or 'SELECT' in body.upper().split('FROM')[0], body)
            self.assertIsNone(self.WRITE.search(re.sub(r'asset_[a-z_]+', '', body)), body)


class InternalFailure(GateCase):
    def test_a_database_failure_is_500_internal_error_without_detail(self):
        admin = STATE['admin']
        postgres = STATE['postgres']
        admin.execute('REVOKE SELECT ON asset_records FROM assets_reader')
        try:
            for target in ('/assets/AST-0029', '/assets'):
                reply = get(target)
                body = self.assert_error(reply, 500, 'INTERNAL_ERROR')
                for fragment in ('asset_records', 'permission', 'psycopg', 'Traceback', 'postgres', 'SELECT', postgres.reader_password):
                    self.assertNotIn(fragment.lower(), reply.body.decode('utf-8').lower(), fragment)
                self.assertLessEqual(len(body['message']), 1000)
            example = js.load_json(COMPONENT / 'fixtures/v1.1/valid/error-internal-error.json')
            self.assertEqual(self.assert_error(get('/assets/AST-0029'), 500, 'INTERNAL_ERROR')['code'], example['code'])
            # errors that need no database are still answered as before
            self.assert_error(get('/assets/bad'), 400, 'INVALID_ASSET_ID')
        finally:
            admin.execute('GRANT SELECT ON asset_records TO assets_reader')
        self.assertEqual(lookup('AST-0029').status, 200)


if __name__ == '__main__':
    unittest.main()
