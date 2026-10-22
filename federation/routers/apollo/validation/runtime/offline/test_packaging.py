"""Offline checks of the Apollo router packaging: the router configuration, the whole-stack compose file, the Rover image definition,
the composition script, the start script, the stub of the Missions service and the expected outcomes.

No container of the stack runs here. Docker is used only to validate the compose file (`docker compose config`).
"""
from pathlib import Path
import http.client
import importlib.util
import json
import os
import re
import socket
import subprocess
import sys
import threading
import unittest
from http.server import ThreadingHTTPServer

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import stack_support as support  # noqa: E402

ROUTER_IMAGE = 'ghcr.io/apollographql/router@sha256:5b02af03e8f0268b8fcf85132c9e54ea36a1029b0823b00bb9151f698a991215'
PYTHON_IMAGE = 'python:3.13-slim-bookworm@sha256:a1165e272e578941b84abc79e4ab38a0305cd12803a5c4247979ac7655f4d641'
POSTGRES_IMAGE = 'postgres:17-bookworm@sha256:3645570cccdfa447589da9f57dd740faa29b30938e861289a5574b6ca6b03826'
NODE_IMAGE = 'node:22-slim@sha256:c3de60bf2f9dd0ac6370e6117950ff62d6e339527e7472301c9c78a017978392'
JRE_IMAGE = 'eclipse-temurin:21-jre@sha256:ccbad9e7cb84c27092b12c40a4143e5733e050db9c3784d84f632dcf423fb2ef'
MISSIONS_XML = support.ROOT / 'uss-enterprise/missions/datasets/releases/1.0/missions.xml'


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


COMPOSE_SCRIPT = load(support.COMPOSE_SCRIPT, 'compose_supergraph')
DERIVE = load(support.FEDERATION / 'acceptance/derive_expected.py', 'derive_expected')


def text(path):
    return Path(path).read_text(encoding='utf-8')


def stack_env(**extra):
    env = {k: v for k, v in os.environ.items() if not k.startswith(('STACK_', 'COMPOSE_', 'SUPERGRAPH_', 'APOLLO_', 'ROUTER_'))}
    env.update(STACK_ASSETS_DB_ADMIN_PASSWORD='unused', STACK_ASSETS_DB_SERVICE_PASSWORD='unused', SUPERGRAPH_FILE=str(support.ROUTER_DIR / 'router.yaml'))
    env.update(extra)
    return env


class ExpectedOutcomes(unittest.TestCase):
    def test_the_expected_outcomes_are_the_derivation_from_the_released_files(self):
        self.assertEqual(DERIVE.main([]), 0)

    def test_the_expected_outcomes_match_the_controlled_cases_of_the_assets_dataset(self):
        expected = json.loads(text(support.EXPECTED))
        provenance = json.loads(text(support.ROOT / 'uss-enterprise/assets/datasets/releases/1.1/provenance.json'))
        wanted = {'RESOLVED': 'RESOLVED', 'UNRESOLVED': 'UNRESOLVED', 'NO_MAPPING': 'UNMAPPED'}
        # The Assets provenance lists the missions of Missions release 1.0; release 1.1 appends 269 more, and some use the same references.
        # So the provenance missions are a subset of the missions that use the reference, and the missions beyond them are all new in 1.1.
        released_10 = {m for entry in provenance['expectedMapping'] for m in entry['missionIds']}
        for entry in provenance['expectedMapping']:
            ref = entry['missionsReference']
            self.assertEqual(expected['references'][ref]['resolution'], wanted[entry['resolution']], ref)
            self.assertEqual(expected['references'][ref]['assetId'], entry['mapsTo'], ref)
            using = sorted(m for m, v in expected['missions'].items() if ref in v['assetRefs'])
            self.assertEqual(sorted(m for m in using if m in released_10 or m in entry['missionIds']), sorted(entry['missionIds']), ref)
        unresolved = sorted(next(e for e in provenance['expectedMapping'] if e['missionsReference'] == 'EQ-97')['missionIds'])
        self.assertTrue(set(unresolved) <= set(expected['question3']['unresolvedMissionIds']))
        self.assertEqual(expected['question4']['chains'][0]['chain'], provenance['parentChains'][0])


class StackDefaults(unittest.TestCase):
    """The whole stack serves the large data by default: Missions release 1.2, Personnel personnel-v2-large-004, asked in mapping release 1.3."""

    def test_the_compose_file_serves_missions_release_1_2_and_the_large_personnel_snapshot_and_no_opt_in_file_is_left(self):
        compose = text(support.COMPOSE_FILE)
        self.assertIn('../../uss-enterprise/missions/datasets/releases/1.2:/data/release:ro', compose)
        self.assertNotIn('releases/1.0', compose)
        self.assertNotIn('releases/1.1', compose)
        self.assertIn('${STACK_PERSONNEL_DATASET_VERSION:-personnel-v2-large-004}', compose)
        self.assertFalse((support.STACK_DIR / 'compose.missions-1.1.yaml').exists())

    def test_the_expected_outcomes_are_those_of_the_large_data_and_ask_mapping_release_1_3(self):
        expected = json.loads(text(support.EXPECTED))
        self.assertEqual(expected['mappingRelease'], '1.3')
        self.assertEqual(expected['crew']['release'], '1.3')
        self.assertEqual(len(expected['missionOrder']), 300)
        self.assertEqual(expected['question6']['totalMissions'], 300)


class RouterConfiguration(unittest.TestCase):
    def test_the_router_listens_on_4000_answers_introspection_passes_subgraph_errors_through_waits_5_seconds_for_a_subgraph_and_needs_no_account(self):
        config = text(support.ROUTER_YAML)
        lines = [line.strip() for line in config.splitlines() if line.strip() and not line.lstrip().startswith('#')]
        self.assertEqual(lines, ['supergraph:', 'listen: 0.0.0.0:4000', 'introspection: true', 'include_subgraph_errors:', 'all: true', 'traffic_shaping:', 'all:', 'timeout: 5s'])
        self.assertNotRegex(config.lower(), r'apollo_key|graph_ref|apollo_graph|api[_-]?key|token')
        self.assertNotIn('\r', config)

    def test_the_router_is_published_on_loopback_8170_only_and_the_image_is_pinned_by_digest(self):
        compose = text(support.COMPOSE_FILE)
        self.assertIn('image: ' + ROUTER_IMAGE, compose)
        self.assertIn('"127.0.0.1:${ROUTER_HOST_PORT:-8170}:4000"', compose)
        self.assertNotIn('8180', compose)
        images = re.findall(r'(?m)^\s+image: (\S*apollographql\S*)$', compose)
        self.assertEqual(images, [ROUTER_IMAGE], 'one router image, by digest, never a preview or release-candidate tag')


class ComposeFile(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        result = support.run(['docker', 'compose', '-f', str(support.COMPOSE_FILE), 'config', '--format', 'json'], stack_env(), 120)
        if result.returncode:
            raise RuntimeError('docker compose config failed: ' + result.stderr[-1500:])
        cls.config = json.loads(result.stdout)

    def test_the_services_are_the_router_the_four_adapters_and_their_backends(self):
        self.assertEqual(sorted(self.config['services']), sorted(support.SERVICES + ('router',)))

    def test_only_loopback_ports_are_published_and_only_the_decided_ones(self):
        published = {}
        for name, service in self.config['services'].items():
            for port in service.get('ports', []):
                self.assertEqual(port['host_ip'], '127.0.0.1', name)
                published[name] = int(port['published'])
        self.assertEqual(published, {'router': 8170, 'personnel-adapter': 8182, 'missions-adapter': 8183, 'assets-adapter': 8184, 'mapping-adapter': 8190})

    def test_every_image_that_is_not_built_here_is_pinned_by_digest(self):
        for name, service in self.config['services'].items():
            if 'build' not in service:
                self.assertRegex(service['image'], r'@sha256:[0-9a-f]{64}$', name)
        self.assertEqual(self.config['services']['missions-stub']['image'], PYTHON_IMAGE)
        self.assertEqual(self.config['services']['assets-db']['image'], POSTGRES_IMAGE)

    def test_every_container_has_explicit_limits_and_the_adapters_are_read_only_without_capabilities(self):
        for name, service in self.config['services'].items():
            self.assertIn('mem_limit', service, name)
            self.assertIn('cpus', service, name)
        for name in ('missions-adapter', 'personnel-adapter', 'assets-adapter', 'mapping-adapter', 'router'):
            service = self.config['services'][name]
            self.assertTrue(service['read_only'], name)
            self.assertEqual(service['cap_drop'], ['ALL'], name)

    def test_the_adapters_reach_their_backends_by_service_name(self):
        services = self.config['services']
        self.assertEqual(services['missions-adapter']['environment']['MISSIONS_SERVICE_URL'], 'http://missions-stub:8083')
        self.assertEqual(services['assets-adapter']['environment']['ASSETS_SERVICE_URL'], 'http://assets-service:8084')
        self.assertEqual(services['personnel-adapter']['environment']['PERSONNEL_SERVICE_URL'], 'http://personnel-service:8082/soap/personnel-v2')

    def test_the_router_waits_for_all_four_adapters_and_mounts_the_supergraph_and_the_configuration_read_only(self):
        router = self.config['services']['router']
        self.assertEqual(sorted(router['depends_on']), ['assets-adapter', 'mapping-adapter', 'missions-adapter', 'personnel-adapter'])
        self.assertEqual(sorted(v['target'] for v in router['volumes']), ['/config/router.yaml', '/config/supergraph.graphql'])
        self.assertTrue(all(v['read_only'] for v in router['volumes']))
        self.assertEqual(router['environment']['APOLLO_TELEMETRY_DISABLED'], 'true')

    def test_the_database_password_is_required_and_no_secret_is_written_in_the_file(self):
        compose = text(support.COMPOSE_FILE)
        self.assertIn('${STACK_ASSETS_DB_ADMIN_PASSWORD:?', compose)
        self.assertIn('${STACK_ASSETS_DB_SERVICE_PASSWORD:?', compose)
        env = {k: v for k, v in stack_env().items() if not k.startswith('STACK_ASSETS_DB')}
        result = support.run(['docker', 'compose', '-f', str(support.COMPOSE_FILE), 'config', '--quiet'], env, 120)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('STACK_ASSETS_DB_ADMIN_PASSWORD', result.stderr)

    def test_the_supergraph_path_is_required(self):
        env = {k: v for k, v in stack_env().items() if k != 'SUPERGRAPH_FILE'}
        result = support.run(['docker', 'compose', '-f', str(support.COMPOSE_FILE), 'config', '--quiet'], env, 120)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('SUPERGRAPH_FILE', result.stderr)


class RoverImage(unittest.TestCase):
    def test_the_dockerfile_pins_both_bases_and_rover_and_refuses_to_build_without_the_license_acceptance(self):
        dockerfile = text(support.ROUTER_DIR / 'rover/Dockerfile')
        self.assertIn('FROM ' + NODE_IMAGE, dockerfile)
        self.assertIn('FROM ' + JRE_IMAGE, dockerfile)
        self.assertIn('@apollo/rover@1.0.0', dockerfile)
        self.assertRegex(dockerfile, r'test "\$APOLLO_ELV2_LICENSE" = "accept"')
        self.assertNotRegex(dockerfile, r'(?m)^ENV .*APOLLO_ELV2_LICENSE')

    def test_the_plugin_version_is_pinned_the_same_everywhere(self):
        self.assertEqual(COMPOSE_SCRIPT.FEDERATION_VERSION, '=2.9.3')
        self.assertIn('federation_version: =2.9.3', text(support.ROUTER_DIR / 'rover/seed.yaml'))
        self.assertIn('federation_version: =2.9.3', COMPOSE_SCRIPT.render_config(['assets']))


class CompositionScript(unittest.TestCase):
    def test_the_config_lists_the_four_subgraphs_in_sorted_order_with_the_same_routing_urls_in_every_mode(self):
        config = COMPOSE_SCRIPT.render_config(COMPOSE_SCRIPT.sorted_names())
        self.assertEqual(re.findall(r'(?m)^  (\w+):$', config), ['assets', 'mapping', 'missions', 'personnel'])
        for url in ('http://assets-adapter:8184/graphql', 'http://mapping-adapter:8190/graphql', 'http://missions-adapter:8183/graphql',
                    'http://personnel-adapter:8182/graphql'):
            self.assertIn('routing_url: ' + url, config)
        self.assertNotIn('127.0.0.1', config)
        self.assertNotIn('\r', config)
        self.assertTrue(config.endswith('\n') and not config.endswith('\n\n'))

    def test_the_routing_urls_are_the_service_names_of_the_compose_file(self):
        services = json.loads(support.run(['docker', 'compose', '-f', str(support.COMPOSE_FILE), 'config', '--format', 'json'], stack_env(), 120).stdout)['services']
        for name, (service, port, _, _) in COMPOSE_SCRIPT.ROUTING.items():
            self.assertIn(service, services)
            self.assertEqual(services[service]['environment']['ADAPTER_PORT'], str(port))

    def test_the_sdl_is_only_normalized_to_lf_and_one_trailing_newline(self):
        self.assertEqual(COMPOSE_SCRIPT.normalize_sdl('a\r\nb\r\n\r\n'), 'a\nb\n')
        self.assertEqual(COMPOSE_SCRIPT.normalize_sdl('a\nb'), 'a\nb\n')

    def test_the_script_refuses_without_the_license_acceptance_with_one_line(self):
        env = {k: v for k, v in os.environ.items() if k != 'APOLLO_ELV2_LICENSE'}
        result = support.run([sys.executable, '-B', str(support.COMPOSE_SCRIPT), '--out', str(support.ROUTER_DIR / 'build/never.graphql')], env, 60)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(len(result.stderr.strip().splitlines()), 1)
        self.assertIn('Elastic License 2.0', result.stderr)
        self.assertFalse((support.ROUTER_DIR / 'build/never.graphql').exists())

    def test_an_order_that_is_not_the_four_names_is_refused(self):
        env = dict(os.environ, APOLLO_ELV2_LICENSE='accept')
        result = support.run([sys.executable, '-B', str(support.COMPOSE_SCRIPT), '--out', 'x.graphql', '--order', 'assets,mapping'], env, 60)
        self.assertEqual(result.returncode, 2)


class StartScript(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bash = support.bash()

    def start(self, *args, env=None):
        merged = {k: v for k, v in os.environ.items() if not k.startswith(('APOLLO_', 'ROUTER_', 'PERSONNEL_ADAPTER', 'MISSIONS_ADAPTER', 'ASSETS_ADAPTER', 'MAPPING_ADAPTER'))}
        merged.update(env or {})
        return support.run([self.bash, str(support.START)] + list(args), merged, 120)

    def test_it_refuses_with_one_line_when_a_port_is_taken(self):
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0))
            listener.listen(1)
            port = listener.getsockname()[1]
            result = self.start('--dry-run', 'start', env={'ROUTER_HOST_PORT': str(port), 'APOLLO_ELV2_LICENSE': 'accept'})
        self.assertEqual(result.returncode, 1)
        self.assertEqual(len(result.stderr.strip().splitlines()), 1)
        self.assertIn(f'127.0.0.1:{port} is already in use', result.stderr)

    def test_it_refuses_without_the_license_acceptance(self):
        result = self.start('--dry-run', 'start', env={'ROUTER_HOST_PORT': str(support.free_port())})
        self.assertEqual(result.returncode, 1)
        self.assertIn('Elastic License 2.0', result.stderr)

    def test_a_dry_run_prints_the_three_steps_in_order_and_runs_nothing(self):
        ports = {name: str(support.free_port()) for name in ('ROUTER_HOST_PORT', 'PERSONNEL_ADAPTER_HOST_PORT', 'MISSIONS_ADAPTER_HOST_PORT',
                                                           'ASSETS_ADAPTER_HOST_PORT', 'MAPPING_ADAPTER_HOST_PORT')}
        result = self.start('--dry-run', 'start', env=dict(ports, APOLLO_ELV2_LICENSE='accept'))
        self.assertEqual(result.returncode, 0, result.stderr)
        lines = [line for line in result.stdout.splitlines() if line.startswith('would run:')]
        self.assertEqual(len(lines), 3)
        self.assertIn('up -d --build --wait', lines[0])
        self.assertNotIn(' router', lines[0])
        self.assertIn('compose_supergraph.py', lines[1])
        self.assertTrue(lines[2].endswith('router'))

    def test_it_never_removes_anything(self):
        script = text(support.START)
        code = re.sub(r"(?s)<<'USAGE'.*?\nUSAGE\n", '', script)
        code = '\n'.join(line for line in code.splitlines() if not line.lstrip().startswith('#'))
        self.assertNotRegex(code, r'docker compose[^\n]* (down|rm)\b|docker (rm|rmi|system|volume|network|image)\b|\bprune\b|rm -')
        self.assertTrue(script.startswith('#!/usr/bin/env bash'))
        self.assertNotIn('\r', script)

    def test_a_dry_run_of_stop_and_status_needs_no_port_and_no_license(self):
        self.assertEqual(self.start('--dry-run', 'stop').returncode, 0)
        self.assertEqual(self.start('--dry-run', 'status').returncode, 0)


class MissionsStub(unittest.TestCase):
    """The stub that stands in for the Missions service serves the released dataset with the contract's read operations."""

    @classmethod
    def setUpClass(cls):
        module = load(support.STACK_DIR / 'missions-stub/server.py', 'missions_stub')
        blocks = re.findall(r'(?s)<mission>.*?</mission>', MISSIONS_XML.read_bytes().decode('utf-8').replace('\r\n', '\n'))
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), module.make_handler(blocks))
        cls.port = cls.server.server_address[1]
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def get(self, target):
        connection = http.client.HTTPConnection('127.0.0.1', self.port, timeout=10)
        connection.request('GET', target)
        response = connection.getresponse()
        body = response.read().decode('utf-8')
        connection.close()
        return response.status, body

    def test_the_list_is_the_released_dataset_and_a_mission_is_served_by_id(self):
        status, body = self.get('/missions?pageSize=50')
        self.assertEqual(status, 200)
        self.assertIn('<totalCount>31</totalCount>', body)
        self.assertEqual(body.count('<mission>'), 31)
        status, body = self.get('/missions/ST-00000LD4O')
        self.assertEqual(status, 200)
        self.assertIn('<mission xmlns="urn:starfleet:missions:v1"><missionId>ST-00000LD4O</missionId>', body)

    def test_paging_and_filters(self):
        status, body = self.get('/missions?page=2&pageSize=10')
        self.assertEqual((status, body.count('<mission>')), (200, 10))
        self.assertIn('<totalPages>4</totalPages>', body)
        status, body = self.get('/missions?assignedAssetId=SH-53&pageSize=50')
        self.assertIn('<totalCount>2</totalCount>', body)
        status, body = self.get('/missions?assignedCrewId=C-120&pageSize=50')
        self.assertEqual(status, 200)
        self.assertIn('<crewId>C-120</crewId>', body)

    def test_the_contract_error_bodies(self):
        self.assertEqual(self.get('/missions/ST-000000000')[0], 404)
        self.assertIn('<code>MISSION_NOT_FOUND</code>', self.get('/missions/ST-000000000')[1])
        self.assertEqual(self.get('/missions/bad')[0], 400)
        self.assertIn('<code>INVALID_MISSION_ID</code>', self.get('/missions/bad')[1])
        self.assertEqual(self.get('/missions?pageSize=51')[0], 400)
        self.assertIn('<code>INVALID_REQUEST</code>', self.get('/missions?bogus=1')[1])
        self.assertEqual(self.get('/other')[0], 404)


class CommittedSupergraph(unittest.TestCase):
    """The committed supergraph is a build product; the stack gate proves it fresh. These checks need no container."""

    @classmethod
    def setUpClass(cls):
        cls.raw = support.COMMITTED_SUPERGRAPH.read_bytes()
        cls.text = cls.raw.decode('utf-8')

    def test_it_is_lf_only_and_exactly_the_bytes_rover_printed(self):
        self.assertNotIn(b'\r', self.raw)
        self.assertTrue(self.raw.startswith(b'schema\n  @link(url: "https://specs.apollo.dev/link/v1.0")'))
        self.assertTrue(self.raw.endswith(b'}'), 'Rover prints no newline after the last brace and the script adds none')

    def test_it_joins_exactly_the_four_subgraphs_with_the_routing_urls_of_the_stack(self):
        graphs = re.findall(r'(?m)^  (\w+) @join__graph\(name: "(\w+)", url: "([^"]+)"\)$', self.text)
        self.assertEqual(graphs, [('ASSETS', 'assets', 'http://assets-adapter:8184/graphql'), ('MAPPING', 'mapping', 'http://mapping-adapter:8190/graphql'),
                                  ('MISSIONS', 'missions', 'http://missions-adapter:8183/graphql'), ('PERSONNEL', 'personnel', 'http://personnel-adapter:8182/graphql')])
        self.assertNotIn('127.0.0.1', self.text)
        self.assertNotIn('localhost', self.text)

    def test_it_uses_only_the_fewest_federation_features(self):
        used = set()
        uses = '\n'.join(line for line in self.text.splitlines() if not line.startswith('directive '))
        for arguments in re.findall(r'@join__field\(([^)]*)\)', uses):
            used |= set(re.findall(r'(\w+):', arguments))
        self.assertLessEqual(used - {'graph'}, {'requires', 'external'})
        self.assertEqual(used - {'graph'}, {'requires', 'external'})
        for forbidden in (r'provides:', r'override:', r'@tag', r'isInterfaceObject: true', r'@shareable'):
            self.assertNotRegex(uses, forbidden)
        # @inaccessible is on the mapping adapter's two plain lookups and nowhere else: it keeps them out of the API schema.
        hidden = [line.strip().split('(')[0] for line in uses.splitlines() if '@inaccessible' in line]
        self.assertEqual(hidden, ['assetReferences', 'personnelReferences'])
        for line in uses.splitlines():
            if '@inaccessible' in line:
                self.assertIn('@join__field(graph: MAPPING)', line)

    def test_the_reference_types_are_owned_by_assets_and_personnel_and_named_by_missions_and_supplied_by_mapping(self):
        asset = self.text[self.text.index('type AssetReference'):self.text.index('enum AssetStatus')]
        for line in ('@join__type(graph: ASSETS, key: "localRef release", resolvable: true)', '@join__type(graph: MAPPING, key: "localRef release", resolvable: true)',
                     '@join__type(graph: MISSIONS, key: "localRef release", resolvable: false)', 'asset: Asset @join__field(graph: ASSETS, requires: "assetId mappingOutcome")'):
            self.assertIn(line, asset)
        crew = self.text[self.text.index('type PersonnelReference'):self.text.index('type Query')]
        for line in ('@join__type(graph: PERSONNEL, key: "localRef release", resolvable: true)', '@join__type(graph: MISSIONS, key: "localRef release", resolvable: false)',
                     'personnel: Personnel @join__field(graph: PERSONNEL, requires: "personnelId mappingOutcome")'):
            self.assertIn(line, crew)

class Sources(unittest.TestCase):
    def test_every_python_file_of_the_router_the_stack_and_the_acceptance_folder_compiles_so_a_broken_stack_test_fails_offline(self):
        import ast
        files = [p for folder in (support.ROUTER_DIR, support.STACK_DIR, support.FEDERATION / 'acceptance') for p in folder.rglob('*.py')]
        self.assertGreaterEqual(len(files), 7)
        for path in files:
            with self.subTest(path=path.name):
                ast.parse(path.read_text(encoding='utf-8'), str(path))


class Readme(unittest.TestCase):
    def test_the_readme_says_which_mode_is_which_and_what_the_supergraph_is(self):
        readme = text(support.ROUTER_DIR / 'README.md')
        self.assertIn('stub-backend mode', readme.lower())
        self.assertIn('real-service mode', readme.lower())
        self.assertIn('8170', readme)
        self.assertIn('build product', readme)
        self.assertNotIn('router 8180', readme)
        self.assertIn('supergraph.introspection: true', readme)


class MissionsStubRelease12(unittest.TestCase):
    """The stub serves release 1.2 (300 missions in six real pages), in the contract's order; it is the stack default. Release 1.1 has the same shape."""

    RELEASE_12 = support.ROOT / 'uss-enterprise/missions/datasets/releases/1.2'

    @classmethod
    def setUpClass(cls):
        cls.module = load(support.STACK_DIR / 'missions-stub/server.py', 'missions_stub_12')
        blocks = cls.module.read_blocks(cls.RELEASE_12)
        cls.blocks = blocks
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), cls.module.make_handler(blocks))
        cls.port = cls.server.server_address[1]
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def get(self, target):
        connection = http.client.HTTPConnection('127.0.0.1', self.port, timeout=10)
        connection.request('GET', target)
        response = connection.getresponse()
        body = response.read().decode('utf-8')
        connection.close()
        return response.status, body

    def test_the_default_release_is_unchanged_and_already_in_the_contract_order(self):
        blocks = self.module.read_blocks(MISSIONS_XML)
        raw = re.findall(r'(?s)<mission>.*?</mission>', MISSIONS_XML.read_bytes().decode('utf-8').replace('\r\n', '\n'))
        self.assertEqual(blocks, raw)
        self.assertEqual(len(blocks), 31)

    def test_a_folder_of_pages_is_joined_and_listed_in_the_contract_order(self):
        self.assertEqual(len(self.blocks), 300)
        keys = [(float(self.module.field(b, 'stardate')), int(self.module.field(b, 'priority')), self.module.field(b, 'missionId')) for b in self.blocks]
        self.assertEqual(keys, sorted(keys))
        status, body = self.get('/missions?pageSize=50')
        self.assertEqual(status, 200)
        self.assertIn('<totalCount>300</totalCount><totalPages>6</totalPages>', body)
        self.assertEqual(body.count('<mission>'), 50)
        status, body = self.get('/missions?page=6&pageSize=50')
        self.assertEqual(body.count('<mission>'), 50)
        status, body = self.get('/missions?page=7&pageSize=50')
        self.assertEqual((status, body.count('<mission>')), (200, 0))

    def test_filters_and_the_page_boundaries_of_the_edge_cases(self):
        status, body = self.get('/missions?type=MAINTENANCE&pageSize=50')
        self.assertIn('<totalCount>50</totalCount><totalPages>1</totalPages>', body)
        status, body = self.get('/missions?type=MAINTENANCE&page=2&pageSize=50')
        self.assertEqual((status, body.count('<mission>')), (200, 0))
        self.assertIn('<totalCount>50</totalCount><totalPages>1</totalPages>', body)
        status, body = self.get('/missions?commandingOfficerId=C-71&pageSize=50')
        self.assertIn('<totalCount>52</totalCount><totalPages>2</totalPages>', body)
        status, body = self.get('/missions?commandingOfficerId=C-71&page=2&pageSize=50')
        self.assertEqual(body.count('<mission>'), 2)
        status, body = self.get('/missions?commandingOfficerId=C-78&pageSize=50')
        self.assertIn('<totalCount>50</totalCount><totalPages>1</totalPages>', body)

    def test_a_mission_of_each_part_is_served_by_id(self):
        carried = self.get('/missions/ST-00000LD4O')
        self.assertEqual(carried[0], 200)
        last = self.module.field(self.blocks[-1], 'missionId')
        self.assertEqual(self.get('/missions/' + last)[0], 200)
        self.assertEqual(self.get('/missions/ST-000000000')[0], 404)


if __name__ == '__main__':
    unittest.main()
