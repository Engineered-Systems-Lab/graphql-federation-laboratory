"""Offline tests of the study MCP servers: the allow-list, the plumbing guard, the mapping files and the call log.

They need the pinned `mcp` package (requirements.txt) and no running stack: a small HTTP server on the loopback stands in for a service.
Run: python -B -m unittest test_mcp_offline   (from this folder, with the virtual environment's Python)
"""
import asyncio
import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from mcp import Client

import adapters_server
import graph_server
import mcp_core as core
import raw_server


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        return

    def _send(self, status, body, headers=()):
        raw = body.encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(raw)))
        for name, value in headers:
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if self.path == '/redirect':
            self._send(302, '', [('Location', 'http://127.0.0.1:1/elsewhere')])
        elif self.path == '/big':
            self._send(200, 'x' * 5000)
        elif self.path == '/missing':
            self._send(404, '{"error": "nope"}')
        else:
            self._send(200, json.dumps({'path': self.path}))

    def do_POST(self):
        size = int(self.headers.get('Content-Length') or 0)
        body = self.rfile.read(size).decode('utf-8')
        if self.path == '/graphql':
            payload = json.loads(body)
            if '__schema' in payload['query']:
                fields = [{'name': 'thing'}, {'name': '_service'}, {'name': '_entities'}]
                types = [{'name': 'Thing'}, {'name': '_Entity'}, {'name': '_Service'}, {'name': '_Any'}, {'name': 'federation__FieldSet'}]
                directives = [{'name': 'include'}, {'name': 'key'}, {'name': 'federation__shareable'}, {'name': 'deprecated'}]
                self._send(200, json.dumps({'data': {'__schema': {'queryType': {'fields': fields}, 'types': types, 'directives': directives}}}))
            else:
                self._send(200, json.dumps({'data': {'echo': payload}}))
        else:
            self._send(200, json.dumps({'soapBody': body, 'action': self.headers.get('SOAPAction')}))


class Fixture(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.http = ThreadingHTTPServer(('127.0.0.1', 0), _Handler)
        cls.port = cls.http.server_address[1]
        threading.Thread(target=cls.http.serve_forever, daemon=True).start()
        cls.base = f'http://127.0.0.1:{cls.port}'
        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(cls.tmp.name)
        for release, names in (('1.0', ['assets.json', 'manifest.json']), ('1.3', ['assets.json', 'crew.json', 'manifest.json'])):
            (root / 'releases' / release).mkdir(parents=True)
            for name in names:
                (root / 'releases' / release / name).write_text('{"release": "%s"}' % release, encoding='utf-8')
        (root / 'releases' / 'notes').mkdir()
        (root / 'secret.json').write_text('{"secret": true}', encoding='utf-8')
        cls.releases = root / 'releases'
        cls.log_path = root / 'calls.jsonl'

    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown()
        cls.tmp.cleanup()

    def log(self):
        return core.CallLog('test', self.log_path)

    def lines(self):
        return [json.loads(line) for line in self.log_path.read_text(encoding='utf-8').splitlines()]

    def call(self, server, tool, arguments):
        async def run():
            async with Client(server) as client:
                return await client.call_tool(tool, arguments)
        return asyncio.run(run())

    def tools(self, server):
        async def run():
            async with Client(server) as client:
                return (await client.list_tools()).tools
        return asyncio.run(run())


class AllowList(unittest.TestCase):
    BASES = ['http://127.0.0.1:8084', 'http://127.0.0.1:8082/soap/personnel-v2']

    def test_inside(self):
        for url in ('http://127.0.0.1:8084/assets?limit=1', 'http://127.0.0.1:8084', 'http://127.0.0.1:8082/soap/personnel-v2',
                    'http://127.0.0.1:8082/soap/personnel-v2/x'):
            self.assertTrue(core.url_allowed(url, self.BASES), url)

    def test_outside(self):
        for url in ('http://127.0.0.1:8170/', 'http://localhost:8084/assets', 'https://127.0.0.1:8084/assets',
                    'http://127.0.0.1:8082/soap/personnel-v2-other', 'http://127.0.0.1:8082/other', 'http://example.com/',
                    'http://user:pw@127.0.0.1:8084/', 'http://127.0.0.1:8084@evil.example/', 'http://127.0.0.1:8084/a/../b',
                    'http://127.0.0.1:8084/a/%2e%2e/b', 'http://127.0.0.1:8084/a%2fb', 'http://127.0.0.1:8084\\@x/', 'file:///etc/passwd',
                    'http://127.0.0.1:8084#frag', 'http://127.0.0.1:80840/', ''):
            self.assertFalse(core.url_allowed(url, self.BASES), url)


class Plumbing(unittest.TestCase):
    def test_names_are_caught(self):
        for query in ('{ _service { sdl } }', '{ _entities(representations: []) { __typename } }', '{ a: _service { sdl } }',
                      '{ __type(name: "_Entity") { name } }', '{ __type(name: "\\u005fEntity") { name } }',
                      '# _service\n{ __typename }', '{ __type(name: "federation__FieldSet") { name } }'):
            self.assertTrue(core.mentions_plumbing(query, None), query)
        self.assertTrue(core.mentions_plumbing('query($n: String!) { __type(name: $n) { name } }', {'n': '_Service'}))

    def test_ordinary_queries_pass(self):
        for query in ('{ assets { items { assetId } } }', '{ __schema { types { name } } }', '{ my_service_x: assets { total } }',
                      '{ __type(name: "Query") { fields { name } } }'):
            self.assertFalse(core.mentions_plumbing(query, None), query)

    def test_scrub(self):
        data = {'__schema': {'queryType': {'fields': [{'name': 'thing'}, {'name': '_service'}, {'name': '_entities'}]},
                             'types': [{'name': 'Thing'}, {'name': '_Entity'}, {'name': 'link__Import'}],
                             'directives': [{'name': 'include'}, {'name': 'key'}, {'name': 'federation__override'}]}}
        scrubbed = core.scrub_plumbing(data)['__schema']
        self.assertEqual([f['name'] for f in scrubbed['queryType']['fields']], ['thing'])
        self.assertEqual([t['name'] for t in scrubbed['types']], ['Thing'])
        self.assertEqual([d['name'] for d in scrubbed['directives']], ['include'])


class Servers(Fixture):
    def raw(self, **kwargs):
        return raw_server.build([self.base], self.releases, self.log(), **kwargs)

    def test_tool_lists_are_the_decided_ones(self):
        self.assertEqual([t.name for t in self.tools(self.raw())], ['http_request', 'soap_request', 'read_mapping_release'])
        adapters = adapters_server.build({n: self.base + '/graphql' for n in adapters_server.DEFAULT_ADAPTERS}, self.log())
        self.assertEqual([t.name for t in self.tools(adapters)], ['graphql_query'])
        self.assertEqual([t.name for t in self.tools(graph_server.build(self.base + '/graphql', self.log()))], ['graphql_query'])

    def test_no_file_or_shell_tool(self):
        names = {t.name for server in (self.raw(), adapters_server.build({n: self.base for n in adapters_server.DEFAULT_ADAPTERS}, self.log()),
                                       graph_server.build(self.base, self.log())) for t in self.tools(server)}
        self.assertFalse({n for n in names if any(w in n for w in ('file', 'shell', 'exec', 'bash', 'command', 'write'))} - {'read_mapping_release'})

    def test_http_request_inside_and_outside(self):
        server = self.raw()
        result = self.call(server, 'http_request', {'method': 'GET', 'url': self.base + '/x?a=1'})
        self.assertFalse(result.is_error)
        body = json.loads(result.content[0].text)
        self.assertEqual(body['status'], 200)
        self.assertEqual(json.loads(body['body']), {'path': '/x?a=1'})
        refused = self.call(server, 'http_request', {'method': 'GET', 'url': 'http://127.0.0.1:1/'})
        self.assertTrue(refused.is_error)
        self.assertIn('Address refused', refused.content[0].text)
        self.assertEqual([line['outcome'] for line in self.lines()[-2:]], ['ok', 'refused'])

    def test_method_and_header_limits(self):
        server = self.raw()
        self.assertTrue(self.call(server, 'http_request', {'method': 'DELETE', 'url': self.base + '/'}).is_error)
        bad = self.call(server, 'http_request', {'method': 'GET', 'url': self.base + '/', 'headers': {'Authorization': 'x'}})
        self.assertTrue(bad.is_error)
        self.assertIn('not allowed', bad.content[0].text)

    def test_error_status_is_a_result_and_redirect_is_not_followed(self):
        server = self.raw()
        missing = json.loads(self.call(server, 'http_request', {'method': 'GET', 'url': self.base + '/missing'}).content[0].text)
        self.assertEqual(missing['status'], 404)
        redirect = json.loads(self.call(server, 'http_request', {'method': 'GET', 'url': self.base + '/redirect'}).content[0].text)
        self.assertEqual(redirect['status'], 302)

    def test_truncation_is_reported(self):
        result = json.loads(self.call(self.raw(max_chars=100), 'http_request', {'method': 'GET', 'url': self.base + '/big'}).content[0].text)
        self.assertTrue(result['truncated'])
        self.assertEqual(len(result['body']), 100)
        self.assertTrue(self.lines()[-1]['truncated'])

    def test_soap_request(self):
        result = json.loads(self.call(self.raw(), 'soap_request', {'url': self.base + '/soap', 'envelope': '<e/>', 'soap_action': 'A'}).content[0].text)
        self.assertEqual(json.loads(result['body']), {'soapBody': '<e/>', 'action': 'A'})

    def test_unreachable_service_is_an_honest_error(self):
        stopped = raw_server.build(['http://127.0.0.1:9'], self.releases, self.log(), timeout=2)
        result = self.call(stopped, 'http_request', {'method': 'GET', 'url': 'http://127.0.0.1:9/x'})
        self.assertTrue(result.is_error)
        self.assertIn('did not answer', result.content[0].text)
        self.assertEqual(self.lines()[-1]['outcome'], 'error')

    def test_mapping_release_files(self):
        server = self.raw()
        listing = json.loads(json.loads(self.call(server, 'read_mapping_release', {'release': '1.3'}).content[0].text)['content'])
        self.assertEqual(listing['files'], ['assets.json', 'crew.json', 'manifest.json'])
        content = json.loads(self.call(server, 'read_mapping_release', {'release': '1.0', 'file': 'manifest.json'}).content[0].text)['content']
        self.assertEqual(json.loads(content), {'release': '1.0'})
        unknown = self.call(server, 'read_mapping_release', {'release': '2.0'})
        self.assertTrue(unknown.is_error)
        self.assertIn('Releases present: 1.0, 1.3', unknown.content[0].text)
        self.assertIn('crew.json', self.call(server, 'read_mapping_release', {'release': '1.0', 'file': 'crew.json'}).content[0].text)

    def test_mapping_tool_cannot_leave_the_folder(self):
        server = self.raw()
        for release, name in (('1.0', '../../secret.json'), ('..', 'secret.json'), ('1.0', '..\\secret.json'), ('notes', None), ('1.0/../1.3', None)):
            self.assertTrue(self.call(server, 'read_mapping_release', {'release': release, 'file': name}).is_error, (release, name))

    def test_adapters_plumbing_blocked_and_scrubbed(self):
        server = adapters_server.build({n: self.base + '/graphql' for n in adapters_server.DEFAULT_ADAPTERS}, self.log())
        blocked = self.call(server, 'graphql_query', {'service': 'assets', 'query': '{ _service { sdl } }'})
        self.assertTrue(blocked.is_error)
        self.assertEqual(self.lines()[-1]['outcome'], 'refused')
        schema = json.loads(json.loads(self.call(server, 'graphql_query',
                                                 {'service': 'assets', 'query': '{ __schema { queryType { fields { name } } } }'}).content[0].text)['body'])
        self.assertEqual([f['name'] for f in schema['data']['__schema']['queryType']['fields']], ['thing'])
        self.assertEqual([t['name'] for t in schema['data']['__schema']['types']], ['Thing'])
        self.assertEqual([d['name'] for d in schema['data']['__schema']['directives']], ['include', 'deprecated'])
        self.assertTrue(self.call(server, 'graphql_query', {'service': 'nothing', 'query': '{ a }'}).is_error)

    def test_adapters_reach_only_their_own_urls(self):
        server = adapters_server.build({n: self.base + '/graphql' for n in adapters_server.DEFAULT_ADAPTERS}, self.log())
        echo = json.loads(json.loads(self.call(server, 'graphql_query', {'service': 'missions', 'query': '{ a }', 'variables': {'v': 1}}).content[0].text)['body'])
        self.assertEqual(echo['data']['echo']['variables'], {'v': 1})

    def test_data_answers_are_not_scrubbed(self):
        server = adapters_server.build({n: self.base + '/graphql' for n in adapters_server.DEFAULT_ADAPTERS}, self.log())
        sent = {'items': [{'name': 'key'}, {'name': 'tag'}]}
        echo = json.loads(json.loads(self.call(server, 'graphql_query', {'service': 'assets', 'query': '{ a }', 'variables': sent}).content[0].text)['body'])
        self.assertEqual(echo['data']['echo']['variables'], sent)

    def test_graph_forwards_unchanged(self):
        server = graph_server.build(self.base + '/graphql', self.log())
        text = json.loads(self.call(server, 'graphql_query', {'query': '{ __schema { queryType { fields { name } } } }'}).content[0].text)['body']
        names = [f['name'] for f in json.loads(text)['data']['__schema']['queryType']['fields']]
        self.assertEqual(names, ['thing', '_service', '_entities'])

    def test_call_log_fields(self):
        self.call(self.raw(), 'http_request', {'method': 'GET', 'url': self.base + '/y'})
        record = self.lines()[-1]
        self.assertEqual(set(record), {'ts', 'server', 'tool', 'run_id', 'args', 'outcome', 'http_status', 'response_chars', 'truncated',
                                       'duration_ms', 'error'})
        self.assertEqual((record['server'], record['tool'], record['outcome'], record['http_status']), ('test', 'http_request', 'ok', 200))
        self.assertGreaterEqual(record['duration_ms'], 0)

    def test_run_id_from_header(self):
        class Ctx:
            headers = {'x-study-run-id': 'run-42'}
        self.assertEqual(core.run_id_of(Ctx()), 'run-42')
        self.assertIsNone(core.run_id_of(object()))


if __name__ == '__main__':
    unittest.main()
