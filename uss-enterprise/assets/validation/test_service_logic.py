"""Unit tests of the Assets service that need no database, no container and no psycopg: routing, identifier and query
parsing, error mapping, the order key, the HTTP mechanics over a fake store, and the pure parts of the load script."""
from pathlib import Path
import http.client
import json
import re
import socket
import sys
import threading
import unittest

COMPONENT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(COMPONENT / 'service'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import assets_logic as logic  # noqa: E402
import assets_service  # noqa: E402
import jsonschema_subset as js  # noqa: E402
import load_release  # noqa: E402

REFERENCE = logic.Reference(kinds=frozenset({'STARSHIP', 'SHUTTLE', 'PHASER'}), categories=frozenset({'VEHICLE', 'EQUIPMENT'}),
                            statuses=frozenset({'ACTIVE', 'MISSING'}))
CONTRACT = js.load_json(COMPONENT / 'contracts/assets-v1.1.openapi.json')
ROW = {'asset_id': 'AST-0029', 'kind': 'STARSHIP', 'category': 'VEHICLE', 'name': 'n', 'description': 'd', 'status': 'ACTIVE', 'parent_asset_id': None}


class FakeStore:
    def __init__(self, rows=(ROW,), fail=False):
        self.rows, self.fail, self.queries = list(rows), fail, []

    def get(self, asset_id):
        if self.fail:
            raise RuntimeError('secret database detail')
        return next((r for r in self.rows if r['asset_id'] == asset_id), None)

    def page(self, query):
        if self.fail:
            raise RuntimeError('secret database detail')
        self.queries.append(query)
        return self.rows[query.offset:query.offset + query.limit], len(self.rows)


class Identifiers(unittest.TestCase):
    def test_grammar_is_exact(self):
        for good in ('AST-0004', 'AST-0001', 'AB_CD-0100', 'AST-99999999999999999999', 'AST-0029'):
            self.assertEqual(logic.parse_asset_id(good), good)
        for bad in ('SH-17', 'ast-0004', 'AST-004', 'AST-0000', 'AST-', 'A-0001', 'AST-0004 ', ' AST-0004', 'AST-0004\n', 'AST-000a',
                    'AST--0001', '_AST-0004', 'AST_-0004', 'AS__T-0004', '', '\xc9ST-0004', 'AST-\u0660\u0660\u0660\u0664'):
            with self.subTest(bad=bad), self.assertRaises(logic.ApiError) as raised:
                logic.parse_asset_id(bad)
            self.assertEqual((raised.exception.status, raised.exception.code), (400, 'INVALID_ASSET_ID'))

    def test_order_key_compares_the_number_as_a_number(self):
        ids = ['AB_C-0001', 'AST-10000', 'AST-0017', 'AST-0002', 'AB-0100', 'AST-9999']
        self.assertEqual(sorted(ids, key=logic.id_sort_key), ['AB-0100', 'AB_C-0001', 'AST-0002', 'AST-0017', 'AST-9999', 'AST-10000'])


class Queries(unittest.TestCase):
    def parse(self, query):
        return logic.parse_list_query(query, REFERENCE)

    def invalid(self, query):
        with self.assertRaises(logic.ApiError) as raised:
            self.parse(query)
        self.assertEqual((raised.exception.status, raised.exception.code), (400, 'INVALID_REQUEST'), query)
        self.assertLessEqual(len(raised.exception.message), 1000)

    def test_defaults_and_values(self):
        self.assertEqual(self.parse(''), logic.ListQuery())
        parsed = self.parse('kind=SHUTTLE&category=VEHICLE&status=MISSING&parentAssetId=AST-0029&offset=40&limit=50')
        self.assertEqual((parsed.kind, parsed.category, parsed.status, parsed.parent_asset_id, parsed.offset, parsed.limit),
                         ('SHUTTLE', 'VEHICLE', 'MISSING', 'AST-0029', 40, 50))
        self.assertEqual(self.parse('kind=%53HUTTLE').kind, 'SHUTTLE')
        self.assertEqual((logic.DEFAULT_OFFSET, logic.DEFAULT_LIMIT), (0, 20))

    def test_everything_else_is_invalid(self):
        for query in ('limit=0', 'limit=51', 'limit=05', 'limit=', 'limit=1.5', 'limit=+5', 'offset=-1', 'offset=01', 'offset=', 'kind=shuttle', 'kind=SHIP',
                      'kind=SHUTTLE,STARSHIP', 'kind=', 'category=vehicle', 'status=LOST', 'parentAssetId=ast-0029', 'parentAssetId=', 'unknown=1', 'Kind=SHUTTLE',
                      'kind=SHUTTLE&kind=STARSHIP', 'limit=5&limit=5', 'kind', '&', 'limit=5&', '&limit=5', 'limit=%FF', 'kind=SHUTTLE%20', 'offset=%D9%A1'):
            with self.subTest(query=query):
                self.invalid(query)

    def test_a_huge_offset_is_accepted_as_a_number(self):
        self.assertEqual(self.parse('offset=' + '9' * 40).offset, int('9' * 40))

    def test_too_many_fields_are_refused(self):
        self.invalid('&'.join('a=1' for _ in range(30)))


class Routing(unittest.TestCase):
    def test_paths_and_methods(self):
        self.assertEqual(logic.route('GET', '/assets'), ('list', ''))
        self.assertEqual(logic.route('GET', '/assets?limit=5'), ('list', 'limit=5'))
        self.assertEqual(logic.route('GET', '/assets/AST-0004'), ('asset', 'AST-0004'))
        for path in ('/', '/assets/', '/assets/AST-0004/', '/assets/AST-0004/x', '/Assets', '//assets', '/other', 'assets', '/assets%2FAST-0004'):
            for method in ('GET', 'POST'):
                with self.subTest(path=path, method=method), self.assertRaises(logic.ApiError) as raised:
                    logic.route(method, path)
                self.assertEqual((raised.exception.status, raised.exception.code), (404, 'PATH_NOT_FOUND'))
        for method in ('POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS', 'FOO', 'get'):
            for path in ('/assets', '/assets/AST-0004', '/assets/not-an-id'):
                with self.subTest(method=method, path=path), self.assertRaises(logic.ApiError) as raised:
                    logic.route(method, path)
                self.assertEqual((raised.exception.status, raised.exception.code, raised.exception.headers), (405, 'METHOD_NOT_ALLOWED', {'Allow': 'GET'}))


class Handling(unittest.TestCase):
    def test_lookup_outcomes(self):
        store = FakeStore()
        found = logic.handle('GET', '/assets/AST-0029', store, REFERENCE)
        self.assertEqual((found.status, list(found.body)), (200, list(logic.ASSET_MEMBERS)))
        self.assertEqual(logic.handle('GET', '/assets/%41ST-0029', store, REFERENCE).body['assetId'], 'AST-0029')
        for target, status, code in (('/assets/AST-0999', 404, 'ASSET_NOT_FOUND'), ('/assets/ast-0001', 400, 'INVALID_ASSET_ID'),
                                     ('/assets/%FF', 400, 'INVALID_ASSET_ID'), ('/assets/AST-0029%00', 400, 'INVALID_ASSET_ID'), ('/assets?bad=1', 400, 'INVALID_REQUEST')):
            with self.subTest(target=target), self.assertRaises(logic.ApiError) as raised:
                logic.handle('GET', target, store, REFERENCE)
            self.assertEqual((raised.exception.status, raised.exception.code), (status, code))

    def test_list_response_shape_and_contract(self):
        body = logic.handle('GET', '/assets?limit=5', FakeStore(), REFERENCE).body
        self.assertEqual(body, {'items': [{'assetId': 'AST-0029', 'kind': 'STARSHIP', 'category': 'VEHICLE', 'name': 'n', 'description': 'd', 'status': 'ACTIVE',
                                           'parentAssetId': None}], 'offset': 0, 'limit': 5, 'total': 1})
        self.assertEqual(js.errors(body, {'$ref': '#/components/schemas/AssetList'}, CONTRACT), [])
        error = logic.ApiError(404, 'ASSET_NOT_FOUND', 'm').body()
        self.assertEqual(js.errors(error, {'$ref': '#/components/schemas/Error'}, CONTRACT), [])
        path_error = logic.ApiError(404, 'PATH_NOT_FOUND', 'm').body()
        self.assertEqual(js.errors(path_error, {'$ref': '#/components/schemas/Error'}, CONTRACT), [])

    def test_every_error_code_the_service_can_produce_is_in_the_contract(self):
        codes = set(CONTRACT['components']['schemas']['ErrorCode']['enum'])
        for error in (logic.internal_error(), logic.http_error(400), logic.http_error(414), logic.http_error(505), logic.http_error(501)):
            self.assertIn(error.code, codes)
        self.assertEqual(logic.http_error(501).status, 500)
        self.assertEqual(logic.http_error(505).status, 400)
        source = (COMPONENT / 'service/assets_logic.py').read_text(encoding='utf-8')
        used = set(re.findall(r"ApiError\(\d+, '([A-Z_]+)'", source))
        self.assertTrue(used and used <= codes, used - codes)


class WholeLookup(unittest.TestCase):
    """The HTTP layer over a fake store, on a loopback port: no database involved."""

    @classmethod
    def setUpClass(cls):
        cls.store = FakeStore()
        cls.server = assets_service.make_server(cls.store, REFERENCE, '127.0.0.1', 0)
        cls.port = cls.server.server_address[1]
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def call(self, method, target, body=None, headers=None):
        connection = http.client.HTTPConnection('127.0.0.1', self.port, timeout=10)
        try:
            connection.request(method, target, body=body, headers=headers or {})
            response = connection.getresponse()
            return response.status, dict((k.lower(), v) for k, v in response.getheaders()), response.read()
        finally:
            connection.close()

    def test_json_in_utf8_and_no_caching_metadata(self):
        status, headers, body = self.call('GET', '/assets/AST-0029')
        self.assertEqual((status, headers['content-type']), (200, 'application/json; charset=utf-8'))
        self.assertEqual(int(headers['content-length']), len(body))
        for name in ('etag', 'cache-control', 'last-modified', 'expires', 'allow', 'location'):
            self.assertNotIn(name, headers)

    def test_every_method_but_get_is_405_and_head_has_no_body(self):
        for method in ('POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS', 'TRACE', 'FOO'):
            status, headers, body = self.call(method, '/assets/AST-0029')
            self.assertEqual((status, headers['allow']), (405, 'GET'), method)
            if method == 'HEAD':
                self.assertEqual(body, b'')
            else:
                self.assertEqual(json.loads(body)['code'], 'METHOD_NOT_ALLOWED')

    def test_a_request_body_closes_the_connection(self):
        status, headers, _ = self.call('POST', '/assets', body=b'{"x":1}', headers={'Content-Type': 'application/json'})
        self.assertEqual((status, headers.get('connection')), (405, 'close'))

    def test_the_raw_target_is_judged_not_the_normalized_one(self):
        self.assertEqual(self.call('GET', '//assets')[0], 404)

    def test_unparseable_requests_are_json_400(self):
        for raw in (b'GARBAGE\r\n\r\n', b'GET /assets HTTP/9.9\r\n\r\n'):
            with socket.create_connection(('127.0.0.1', self.port), timeout=10) as connection:
                connection.sendall(raw)
                data = b''
                while chunk := connection.recv(4096):
                    data += chunk
            head, _, body = data.partition(b'\r\n\r\n')
            self.assertIn(b' 400 ', head.split(b'\r\n')[0], raw)
            self.assertEqual(json.loads(body)['code'], 'INVALID_REQUEST')

    def test_a_failing_store_is_500_without_detail(self):
        server = assets_service.make_server(FakeStore(fail=True), REFERENCE, '127.0.0.1', 0)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            connection = http.client.HTTPConnection('127.0.0.1', server.server_address[1], timeout=10)
            connection.request('GET', '/assets/AST-0029')
            response = connection.getresponse()
            body = response.read()
            self.assertEqual(response.status, 500)
            self.assertEqual(json.loads(body)['code'], 'INTERNAL_ERROR')
            self.assertNotIn(b'secret', body)
            connection.close()
        finally:
            server.shutdown()
            server.server_close()

    def test_default_bind_is_loopback_and_the_port_is_8084(self):
        self.assertEqual((assets_service.DEFAULT_HOST, assets_service.DEFAULT_PORT), ('127.0.0.1', 8084))


class StoreIsReadOnly(unittest.TestCase):
    def test_the_store_source_has_no_statement_that_changes_data(self):
        source = (COMPONENT / 'service/assets_store.py').read_text(encoding='utf-8')
        strings = re.findall(r"f?'([^'\n]*)'", source)
        self.assertTrue([s for s in strings if re.search(r'\b(SELECT|FROM)\b', s)])
        for text in strings:
            self.assertIsNone(re.search(r'\b(INSERT|UPDATE|DELETE|TRUNCATE|CREATE|ALTER|DROP|GRANT)\b', text), text)
        self.assertIn('read_only = True', source)

    def test_the_service_holds_no_credential(self):
        for name in ('assets_service.py', 'assets_store.py', 'assets_logic.py', 'load_release.py'):
            text = (COMPONENT / 'service' / name).read_text(encoding='utf-8')
            self.assertIsNone(re.search(r'password\s*=\s*[\'"][^\'"]+[\'"]', text, re.I), name)


class LoadScriptPureParts(unittest.TestCase):
    def test_parents_come_before_their_children_in_a_fixed_order(self):
        assets = [{'assetId': 'EQ-1', 'parentAssetId': 'SH-2'}, {'assetId': 'SH-2', 'parentAssetId': 'VS-9'}, {'assetId': 'VS-9', 'parentAssetId': None},
                  {'assetId': 'EQ-10', 'parentAssetId': None}, {'assetId': 'EQ-2', 'parentAssetId': None}]
        ordered = [a['assetId'] for a in load_release.parents_first(assets)]
        self.assertEqual(ordered, ['EQ-2', 'EQ-10', 'VS-9', 'SH-2', 'EQ-1'])
        self.assertEqual(ordered, [a['assetId'] for a in load_release.parents_first(list(reversed(assets)))])

    def test_cycles_missing_parents_and_duplicates_are_refused(self):
        for assets, message in (([{'assetId': 'AA-1', 'parentAssetId': 'BB-1'}, {'assetId': 'BB-1', 'parentAssetId': 'AA-1'}], 'cycle'),
                                ([{'assetId': 'AA-1', 'parentAssetId': 'ZZ-9'}], 'not in the release'),
                                ([{'assetId': 'AA-1', 'parentAssetId': 'AA-1'}], 'cycle'),
                                ([{'assetId': 'AA-1', 'parentAssetId': None}, {'assetId': 'AA-1', 'parentAssetId': None}], 'Duplicate')):
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                load_release.parents_first(assets)

    def test_the_real_release_reads_and_orders(self):
        manifest, assets = load_release.read_release(COMPONENT / 'datasets/releases/1.1')
        self.assertEqual(manifest['counts']['assets'], len(assets))
        seen = set()
        for asset in load_release.parents_first(assets):
            self.assertTrue(asset['parentAssetId'] is None or asset['parentAssetId'] in seen)
            seen.add(asset['assetId'])


if __name__ == '__main__':
    unittest.main()
