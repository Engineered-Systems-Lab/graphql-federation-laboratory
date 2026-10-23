"""Tests of the study MCP servers against the RUNNING large-data federation stack.

Skipped unless STUDY_MCP_STACK=1. The stack must be up (federation/stack/start.sh start, Apollo router on 8170) and the three legacy
backends published with legacy-ports.json (see README.md); STUDY_MCP_MAPPING_DIR names the folder that holds the mapping release
folders. Optional: STUDY_MCP_COSMO_URL (the Cosmo router's URL) adds the Epsilon check; STUDY_MCP_ROUTER_URL overrides the Apollo URL.
Run: STUDY_MCP_STACK=1 STUDY_MCP_MAPPING_DIR=<folder> python -B -m unittest test_mcp_stack
"""
import asyncio
import json
import os
import tempfile
import unittest
from pathlib import Path

from mcp import Client

import adapters_server
import graph_server
import mcp_core as core
import raw_server

LIVE = os.environ.get('STUDY_MCP_STACK') == '1'
PERSONNEL_LIST = ('<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"><soapenv:Body>'
                  '<ListPersonnelMembersRequest xmlns="urn:graphql-federation-lab:personnel:v2"><limit>2</limit></ListPersonnelMembersRequest>'
                  '</soapenv:Body></soapenv:Envelope>')
SCHEMA_FIELDS = '{ __schema { queryType { fields { name } } types { name } directives { name } } }'


def call(server, tool, arguments):
    async def run():
        async with Client(server) as client:
            return await client.call_tool(tool, arguments)
    return asyncio.run(run())


def body(result):
    assert not result.is_error, result.content[0].text
    outer = json.loads(result.content[0].text)
    return outer['status'], json.loads(outer['body']) if outer['body'].lstrip().startswith('{') else outer['body']


@unittest.skipUnless(LIVE, 'set STUDY_MCP_STACK=1 with the large-data stack running')
class AgainstTheStack(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.log_path = Path(cls.tmp.name) / 'calls.jsonl'
        cls.log = core.CallLog('stack-test', cls.log_path)
        cls.mapping_dir = os.environ['STUDY_MCP_MAPPING_DIR']

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def raw(self):
        return raw_server.build(raw_server.DEFAULT_ALLOW, self.mapping_dir, self.log)

    def adapters(self):
        return adapters_server.build(adapters_server.DEFAULT_ADAPTERS, self.log)

    # ALPHA / BETA: the raw legacy systems and the mapping release files
    def test_raw_assets_rest_json(self):
        status, data = body(call(self.raw(), 'http_request', {'method': 'GET', 'url': 'http://127.0.0.1:8084/assets?limit=2'}))
        self.assertEqual((status, data['total'], len(data['items'])), (200, 32, 2))

    def test_raw_missions_rest_xml(self):
        status, text = body(call(self.raw(), 'http_request', {'method': 'GET', 'url': 'http://127.0.0.1:8083/missions?pageSize=1'}))
        self.assertEqual(status, 200)
        self.assertIn('<totalCount>300</totalCount>', text)

    def test_raw_personnel_soap(self):
        status, text = body(call(self.raw(), 'soap_request', {'url': 'http://127.0.0.1:8082/soap/personnel-v2', 'envelope': PERSONNEL_LIST}))
        self.assertEqual(status, 200)
        self.assertIn('personnel-v2-large-004', text)
        self.assertIn('PRS-0001', text)

    def test_raw_mapping_release_files(self):
        server = self.raw()
        listing = json.loads(json.loads(call(server, 'read_mapping_release', {'release': '1.0'}).content[0].text)['content'])
        self.assertNotIn('crew.json', listing['files'])
        listing = json.loads(json.loads(call(server, 'read_mapping_release', {'release': '1.3'}).content[0].text)['content'])
        self.assertEqual(listing['files'], ['assets.json', 'crew.json', 'manifest.json', 'participants.json'])
        crew = call(server, 'read_mapping_release', {'release': '1.3', 'file': 'crew.json'})
        self.assertFalse(crew.is_error)
        missing = call(server, 'read_mapping_release', {'release': '2.0'})
        self.assertTrue(missing.is_error)
        self.assertIn('no mapping release', missing.content[0].text)

    def test_raw_allow_list_refuses_the_adapters_and_the_routers(self):
        server = self.raw()
        before = self.refused_count()
        for url in ('http://127.0.0.1:8170/', 'http://127.0.0.1:8171/', 'http://127.0.0.1:8183/graphql', 'http://127.0.0.1:8190/graphql',
                    'http://127.0.0.1:8191/mcp', 'http://example.com/'):
            result = call(server, 'http_request', {'method': 'GET', 'url': url})
            self.assertTrue(result.is_error, url)
            self.assertIn('Address refused', result.content[0].text)
        self.assertEqual(self.refused_count() - before, 6)

    def refused_count(self):
        return sum(1 for line in self.log_path.read_text(encoding='utf-8').splitlines() if json.loads(line)['outcome'] == 'refused')

    # GAMMA: each adapter on its own, no federation plumbing
    def test_adapters_ordinary_queries(self):
        server = self.adapters()
        queries = {'personnel': '{ personnelMembers(limit: 2) { totalCount } personnel(personnelId: "PRS-0001") { personnelId } }',
                   'missions': '{ mission(missionId: "ST-00000LD4O") { missionId title } }',
                   'assets': '{ asset(assetId: "AST-0029") { assetId name } }',
                   'mapping': '{ mappingReleases { release sections } }'}
        for service, query in queries.items():
            status, data = body(call(server, 'graphql_query', {'service': service, 'query': query}))
            self.assertEqual(status, 200, service)
            self.assertNotIn('errors', data, (service, data))
            self.assertTrue(data['data'], service)
        self.assertEqual(body(call(server, 'graphql_query', {'service': 'assets', 'query': queries['assets']}))[1]['data']['asset']['name'],
                         'USS Enterprise NCC-1701-D')

    def test_adapters_discovery_shows_the_api_and_hides_the_plumbing(self):
        server = self.adapters()
        expected = {'personnel': {'personnel', 'personnelMembers'}, 'missions': {'mission', 'missions'}, 'assets': {'asset', 'assets'},
                    'mapping': {'mappingReleases', 'assetReferences', 'personnelReferences'}}
        for service, fields in expected.items():
            _, data = body(call(server, 'graphql_query', {'service': service, 'query': SCHEMA_FIELDS}))
            schema = data['data']['__schema']
            self.assertEqual({f['name'] for f in schema['queryType']['fields']}, fields, service)
            types = {t['name'] for t in schema['types']}
            self.assertFalse(types & core.BLOCKED_TYPES, service)
            self.assertFalse({d['name'] for d in schema['directives']} & core.BLOCKED_DIRECTIVES, service)
            self.assertIn('__Schema', types)

    def test_adapters_mapping_lookups_through_the_tool(self):
        """The path a Gamma agent takes: the mapping lookups through graphql_query, the plumbing filter in between."""
        server = self.adapters()
        release = Path(self.mapping_dir) / '1.3'
        assets = json.loads((release / 'assets.json').read_text(encoding='utf-8'))['entries']
        crew = json.loads((release / 'crew.json').read_text(encoding='utf-8'))['entries']
        self.assertEqual((assets['EQ-64'], crew['C-120']), ('AST-0004', 'PRS-0714'))
        self.assertNotIn('EQ-108', assets)
        # (1) Discovery through the tool shows both lookups with their two arguments.
        _, data = body(call(server, 'graphql_query', {'service': 'mapping', 'query':
                                                       '{ __type(name: "Query") { fields { name args { name } } } }'}))
        fields = {f['name']: sorted(a['name'] for a in f['args']) for f in data['data']['__type']['fields']}
        for name in ('assetReferences', 'personnelReferences'):
            self.assertEqual(fields.get(name), ['localRefs', 'release'], name)
        # (2) A mapped asset and a mapped crew reference give the ids of mapping release 1.3.
        status, data = body(call(server, 'graphql_query', {'service': 'mapping', 'query':
                                                            'query($r: [ID!]!) { assetReferences(release: "1.3", localRefs: $r) { localRef assetId mappingOutcome } }',
                                                            'variables': {'r': ['EQ-64', 'EQ-108']}}))
        self.assertEqual(status, 200)
        self.assertNotIn('errors', data)
        self.assertEqual(data['data']['assetReferences'], [{'localRef': 'EQ-64', 'assetId': assets['EQ-64'], 'mappingOutcome': 'MAPPED'},
                                                           {'localRef': 'EQ-108', 'assetId': None, 'mappingOutcome': 'NO_ENTRY'}])
        # (3) An outsider is answered with its stated outcome and the adapter's own errors entry, never refused by the filter.
        result = call(server, 'graphql_query', {'service': 'mapping', 'query':
                                                '{ personnelReferences(release: "1.3", localRefs: ["C-120", "O-860"]) { localRef personnelId mappingOutcome } }'})
        self.assertFalse(result.is_error, result.content[0].text)
        status, data = body(result)
        self.assertEqual(status, 200)
        self.assertEqual(data['data']['personnelReferences'], [{'localRef': 'C-120', 'personnelId': crew['C-120'], 'mappingOutcome': 'MAPPED'},
                                                               {'localRef': 'O-860', 'personnelId': None, 'mappingOutcome': 'NO_ENTRY'}])
        self.assertEqual([e['extensions']['code'] for e in data['errors']], ['MAPPING_CLASS_REFUSED'])

    def test_adapters_plumbing_is_blocked_for_every_adapter(self):
        server = self.adapters()
        for service in ('personnel', 'missions', 'assets', 'mapping'):
            for query in ('{ _service { sdl } }', '{ _entities(representations: []) { __typename } }',
                          '{ __type(name: "_Service") { name } }'):
                result = call(server, 'graphql_query', {'service': service, 'query': query})
                self.assertTrue(result.is_error, (service, query))

    # DELTA / EPSILON: the graph through a router
    def router_check(self, url):
        server = graph_server.build(url, self.log)
        status, data = body(call(server, 'graphql_query', {'query': '{ mappingReleases { release } asset(assetId: "AST-0029") { name } '
                                                                    'mission(missionId: "ST-00000LD4O") { missionId } }'}))
        self.assertEqual(status, 200)
        self.assertEqual(data['data']['asset']['name'], 'USS Enterprise NCC-1701-D')
        self.assertEqual(len(data['data']['mappingReleases']), 4)
        # Introspection is forwarded as it is. Whether the router answers it is the router's configuration: report, do not assume.
        _, discovery = body(call(server, 'graphql_query', {'query': SCHEMA_FIELDS}))
        return discovery

    def test_graph_through_apollo(self):
        discovery = self.router_check(os.environ.get('STUDY_MCP_ROUTER_URL', 'http://127.0.0.1:8170/'))
        self.report('apollo', discovery)

    @unittest.skipUnless(os.environ.get('STUDY_MCP_COSMO_URL'), 'set STUDY_MCP_COSMO_URL with the Cosmo router running')
    def test_graph_through_cosmo(self):
        self.report('cosmo', self.router_check(os.environ['STUDY_MCP_COSMO_URL']))

    def report(self, name, discovery):
        if 'errors' in discovery:
            print(f'\n[{name}] introspection answered with: {discovery["errors"][0].get("extensions", {}).get("code")}')
        else:
            fields = {f['name'] for f in discovery['data']['__schema']['queryType']['fields']}
            print(f'\n[{name}] introspection answered; Query fields: {sorted(fields)}')
            self.assertTrue({'mission', 'missions', 'asset', 'personnel', 'mappingReleases'} <= fields)


if __name__ == '__main__':
    unittest.main()
