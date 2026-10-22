"""Offline checks of the Cosmo router packaging: the router configuration, the Cosmo service of the whole-stack compose file, the wgc image
definition, the composition script, the committed execution config, the start script's Cosmo branch and the settings the Cosmo gate
declares to the shared acceptance suite.

No container of the stack runs here. Docker is used only to validate the compose file (`docker compose config`).
"""
from pathlib import Path
import importlib.util
import json
import os
import re
import socket
import subprocess
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import stack_support as support  # noqa: E402

sys.path.insert(0, str(support.ACCEPTANCE))
import shared_suite  # noqa: E402

ROUTER_IMAGE = 'ghcr.io/wundergraph/cosmo/router@sha256:a125c80b7c759837901a080bb9f64518eb5826a979f7b2f512661cacf1caff6d'
APOLLO_ROUTER_IMAGE = 'ghcr.io/apollographql/router@sha256:5b02af03e8f0268b8fcf85132c9e54ea36a1029b0823b00bb9151f698a991215'
NODE_IMAGE = 'node:22-slim@sha256:c3de60bf2f9dd0ac6370e6117950ff62d6e339527e7472301c9c78a017978392'


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


COMPOSE_SCRIPT = load(support.COMPOSE_SCRIPT, 'compose_execution_config')


def text(path):
    return Path(path).read_text(encoding='utf-8')


def stack_env(**extra):
    env = {k: v for k, v in os.environ.items() if not k.startswith(('STACK_', 'COMPOSE_', 'SUPERGRAPH_', 'EXECUTION_', 'FEDERATION_', 'APOLLO_', 'ROUTER_', 'COSMO_'))}
    env.update(STACK_ASSETS_DB_ADMIN_PASSWORD='unused', STACK_ASSETS_DB_SERVICE_PASSWORD='unused', SUPERGRAPH_FILE=str(support.APOLLO_DIR / 'router.yaml'))
    env.update(extra)
    return env


def compose_config(profile=True, env=None):
    argv = ['docker', 'compose', '-f', str(support.COMPOSE_FILE)] + (support.PROFILE if profile else []) + ['config', '--format', 'json']
    result = support.run(argv, env or stack_env(), 120)
    if result.returncode:
        raise RuntimeError('docker compose config failed: ' + result.stderr[-1500:])
    return json.loads(result.stdout)


class RouterConfiguration(unittest.TestCase):
    def test_the_router_listens_on_4000_answers_introspection_passes_subgraph_errors_through_waits_5_seconds_without_retry_and_needs_no_account(self):
        config = text(support.ROUTER_CONFIG)
        lines = [line.strip() for line in config.splitlines() if line.strip() and not line.lstrip().startswith('#')]
        settings = '\n'.join(lines)
        self.assertEqual(lines, ['version: "1"', 'listen_addr: "0.0.0.0:4000"', 'introspection:', 'enabled: true', 'subgraph_error_propagation:', 'mode: pass-through', 'traffic_shaping:',
                                 'all:', 'request_timeout: 5s', 'retry:', 'enabled: false'])
        self.assertNotRegex(settings.lower(), r'graph[_-]?token|api[_-]?key|controlplane|cdn|router_registration|graph_ref')
        self.assertNotIn('\r', config)

    def test_the_timeout_is_the_one_of_the_apollo_router(self):
        apollo = text(support.APOLLO_DIR / 'router.yaml')
        self.assertIn('timeout: 5s', apollo)
        self.assertIn('request_timeout: 5s', text(support.ROUTER_CONFIG))

    def test_the_router_is_published_on_loopback_8171_only_and_the_image_is_pinned_by_digest(self):
        compose = text(support.COMPOSE_FILE)
        self.assertIn('image: ' + ROUTER_IMAGE, compose)
        self.assertIn('"127.0.0.1:${COSMO_ROUTER_HOST_PORT:-8171}:4000"', compose)
        self.assertNotIn('8180', compose)
        images = re.findall(r'(?m)^\s+image: (\S*wundergraph\S*)$', compose)
        self.assertEqual(images, [ROUTER_IMAGE], 'one Cosmo router image, by digest, never a tag')


class ComposeFile(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = compose_config(True)
        cls.apollo = compose_config(False)

    def test_the_cosmo_router_belongs_to_the_profile_and_the_file_without_the_profile_is_the_apollo_stack_as_before(self):
        self.assertEqual(sorted(self.config['services']), sorted(support.SERVICES + ('router', 'cosmo-router')))
        self.assertEqual(sorted(self.apollo['services']), sorted(support.SERVICES + ('router',)))
        self.assertEqual(self.config['services']['cosmo-router']['profiles'], ['cosmo'])
        self.assertNotIn('profiles', self.config['services']['router'])

    def test_only_loopback_ports_are_published_and_only_the_decided_ones(self):
        published = {}
        for name, service in self.config['services'].items():
            for port in service.get('ports', []):
                self.assertEqual(port['host_ip'], '127.0.0.1', name)
                published[name] = int(port['published'])
        self.assertEqual(published, {'router': 8170, 'cosmo-router': 8171, 'personnel-adapter': 8182, 'missions-adapter': 8183, 'assets-adapter': 8184, 'mapping-adapter': 8190})

    def test_the_router_images_are_pinned_by_digest_and_the_cosmo_one_is_the_one_of_this_gate(self):
        self.assertEqual(self.config['services']['cosmo-router']['image'], ROUTER_IMAGE)
        self.assertEqual(self.config['services']['router']['image'], APOLLO_ROUTER_IMAGE)
        for name, service in self.config['services'].items():
            if 'build' not in service:
                self.assertRegex(service['image'], r'@sha256:[0-9a-f]{64}$', name)

    def test_the_cosmo_router_has_explicit_limits_is_read_only_without_capabilities_and_turns_its_usage_tracking_off(self):
        service = self.config['services']['cosmo-router']
        self.assertIn('mem_limit', service)
        self.assertIn('cpus', service)
        self.assertTrue(service['read_only'])
        self.assertEqual(service['cap_drop'], ['ALL'])
        self.assertEqual(service['environment']['COSMO_TELEMETRY_DISABLED'], 'true')
        self.assertEqual(service['environment']['CONFIG_PATH'], '/config/config.yaml')
        self.assertEqual(service['environment']['EXECUTION_CONFIG_FILE_PATH'], '/config/execution-config.json')

    def test_the_router_waits_for_all_four_adapters_and_mounts_the_configuration_and_the_execution_config_read_only(self):
        router = self.config['services']['cosmo-router']
        self.assertEqual(sorted(router['depends_on']), ['assets-adapter', 'mapping-adapter', 'missions-adapter', 'personnel-adapter'])
        self.assertEqual(sorted(v['target'] for v in router['volumes']), ['/config/config.yaml', '/config/execution-config.json'])
        self.assertTrue(all(v['read_only'] for v in router['volumes']))
        sources = {v['target']: Path(v['source']).resolve() for v in router['volumes']}
        self.assertEqual(sources['/config/config.yaml'], support.ROUTER_CONFIG.resolve())
        self.assertEqual(sources['/config/execution-config.json'], support.COMMITTED_EXECUTION_CONFIG.resolve(), 'the committed file is the default')

    def test_the_execution_config_can_be_pointed_elsewhere(self):
        other = support.ROUTER_DIR / 'validation/elsewhere.json'
        config = compose_config(True, stack_env(EXECUTION_CONFIG_FILE=str(other)))
        mounts = {v['target']: Path(v['source']).resolve() for v in config['services']['cosmo-router']['volumes']}
        self.assertEqual(mounts['/config/execution-config.json'], other.resolve())

    def test_a_plain_compose_run_still_needs_no_cosmo_variable(self):
        result = support.run(['docker', 'compose', '-f', str(support.COMPOSE_FILE), 'config', '--quiet'], stack_env(), 120)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_no_secret_is_written_for_the_cosmo_router(self):
        compose = text(support.COMPOSE_FILE)
        block = compose[compose.index('  cosmo-router:'):]
        self.assertNotRegex(block.lower(), r'graph_api_token|api_key|password|secret')


class WgcImage(unittest.TestCase):
    def test_the_dockerfile_pins_the_base_and_wgc_and_turns_telemetry_and_the_update_check_off(self):
        dockerfile = text(support.ROUTER_DIR / 'wgc/Dockerfile')
        self.assertIn('FROM ' + NODE_IMAGE, dockerfile)
        self.assertIn('wgc@0.133.0', dockerfile)
        self.assertRegex(dockerfile, r'(?m)^ENV COSMO_TELEMETRY_DISABLED=true\b')
        self.assertRegex(dockerfile, r'(?m)^ENV DISABLE_UPDATE_CHECK=true$')
        self.assertNotRegex(dockerfile, r'(?i)license.*accept|ELV2')

    def test_the_node_base_is_the_one_of_the_rover_image(self):
        self.assertIn(NODE_IMAGE, text(support.APOLLO_DIR / 'rover/Dockerfile'))

    def test_the_image_tag_names_the_wgc_version(self):
        self.assertEqual(COMPOSE_SCRIPT.WGC_IMAGE, 'starfleet-federation-wgc:0.133.0')


class CompositionScript(unittest.TestCase):
    def test_the_input_lists_the_four_subgraphs_in_sorted_order_with_the_same_routing_urls_in_every_mode(self):
        config = COMPOSE_SCRIPT.render_input(COMPOSE_SCRIPT.sorted_names())
        self.assertEqual(re.findall(r'(?m)^  - name: (\w+)$', config), ['assets', 'mapping', 'missions', 'personnel'])
        for url in ('http://assets-adapter:8184/graphql', 'http://mapping-adapter:8190/graphql', 'http://missions-adapter:8183/graphql',
                    'http://personnel-adapter:8182/graphql'):
            self.assertIn('routing_url: ' + url, config)
        self.assertNotIn('127.0.0.1', config)
        self.assertNotIn('\r', config)
        self.assertTrue(config.startswith('version: 1\n') and config.endswith('\n') and not config.endswith('\n\n'))

    def test_the_routing_urls_are_the_service_names_of_the_compose_file(self):
        services = compose_config(True)['services']
        for name, (service, port, _, _) in COMPOSE_SCRIPT.ROUTING.items():
            self.assertIn(service, services)
            self.assertEqual(services[service]['environment']['ADAPTER_PORT'], str(port))

    def test_the_routing_urls_are_the_ones_of_the_apollo_composition(self):
        apollo = load(support.APOLLO_DIR / 'compose_supergraph.py', 'compose_supergraph')
        self.assertEqual({n: COMPOSE_SCRIPT.routing_url(n) for n in COMPOSE_SCRIPT.sorted_names()}, {n: apollo.routing_url(n) for n in apollo.sorted_names()})

    def test_the_sdl_is_only_normalized_to_lf_and_one_trailing_newline(self):
        self.assertEqual(COMPOSE_SCRIPT.normalize_sdl('a\r\nb\r\n\r\n'), 'a\nb\n')
        self.assertEqual(COMPOSE_SCRIPT.normalize_sdl('a\nb'), 'a\nb\n')

    def test_the_execution_config_is_wgcs_json_written_indented_with_lf_and_one_final_newline_and_nothing_else_changes(self):
        raw = b'{"b":[1,{"x":"\xc3\xa9\\n"}],"a":"\\u00e9"}'
        out = COMPOSE_SCRIPT.normalize_config(raw)
        self.assertEqual(json.loads(out.decode('utf-8')), json.loads(raw.decode('utf-8')))
        self.assertEqual(list(json.loads(out.decode('utf-8'))), ['b', 'a'], "wgc's key order is kept")
        self.assertTrue(out.endswith(b'}\n') and not out.endswith(b'\n\n'))
        self.assertNotIn(b'\r', out)
        self.assertIn(b'\n  "b": [\n    1,', out)
        self.assertEqual(COMPOSE_SCRIPT.normalize_config(out), out, 'writing it again changes nothing')

    def test_an_order_that_is_not_the_four_names_is_refused(self):
        result = support.run([sys.executable, '-B', str(support.COMPOSE_SCRIPT), '--out', 'x.json', '--order', 'assets,mapping'], dict(os.environ), 60)
        self.assertEqual(result.returncode, 2)


class StartScript(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bash = support.bash()

    def start(self, *args, env=None):
        merged = {k: v for k, v in os.environ.items() if not k.startswith(('APOLLO_', 'ROUTER_', 'COSMO_', 'FEDERATION_', 'PERSONNEL_ADAPTER', 'MISSIONS_ADAPTER', 'ASSETS_ADAPTER', 'MAPPING_ADAPTER'))}
        merged.update(env or {})
        return support.run([self.bash, str(support.START)] + list(args), merged, 120)

    def ports(self):
        return {name: str(support.free_port()) for name in ('COSMO_ROUTER_HOST_PORT', 'PERSONNEL_ADAPTER_HOST_PORT', 'MISSIONS_ADAPTER_HOST_PORT',
                                                          'ASSETS_ADAPTER_HOST_PORT', 'MAPPING_ADAPTER_HOST_PORT')}

    def test_it_refuses_with_one_line_when_the_cosmo_port_is_taken(self):
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0))
            listener.listen(1)
            port = listener.getsockname()[1]
            result = self.start('--dry-run', 'start', env={'FEDERATION_ROUTER': 'cosmo', 'COSMO_ROUTER_HOST_PORT': str(port)})
        self.assertEqual(result.returncode, 1)
        self.assertEqual(len(result.stderr.strip().splitlines()), 1)
        self.assertIn(f'127.0.0.1:{port} is already in use', result.stderr)

    def test_the_cosmo_start_needs_no_license_acceptance(self):
        result = self.start('--dry-run', 'start', env=dict(self.ports(), FEDERATION_ROUTER='cosmo'))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn('Elastic License', result.stderr)

    def test_a_cosmo_dry_run_prints_the_three_steps_in_order_with_the_profile_and_runs_nothing(self):
        result = self.start('--dry-run', 'start', env=dict(self.ports(), FEDERATION_ROUTER='cosmo'))
        self.assertEqual(result.returncode, 0, result.stderr)
        lines = [line for line in result.stdout.splitlines() if line.startswith('would run:')]
        self.assertEqual(len(lines), 3)
        self.assertIn('up -d --build --wait', lines[0])
        self.assertNotIn('cosmo-router', lines[0])
        self.assertNotIn(' router', lines[0])
        self.assertIn('compose_execution_config.py', lines[1])
        self.assertNotIn('compose_supergraph.py', result.stdout)
        self.assertIn('--profile cosmo up -d --wait', lines[2])
        self.assertTrue(lines[2].endswith('cosmo-router'))

    def test_the_apollo_dry_run_is_unchanged_by_the_switch(self):
        ports = {name: str(support.free_port()) for name in ('ROUTER_HOST_PORT', 'PERSONNEL_ADAPTER_HOST_PORT', 'MISSIONS_ADAPTER_HOST_PORT',
                                                           'ASSETS_ADAPTER_HOST_PORT', 'MAPPING_ADAPTER_HOST_PORT')}
        result = self.start('--dry-run', 'start', env=dict(ports, APOLLO_ELV2_LICENSE='accept'))
        self.assertEqual(result.returncode, 0, result.stderr)
        lines = [line for line in result.stdout.splitlines() if line.startswith('would run:')]
        self.assertEqual(len(lines), 3)
        self.assertIn('compose_supergraph.py', lines[1])
        self.assertTrue(lines[2].endswith(' router'))
        self.assertNotIn('--profile', result.stdout)

    def test_stop_and_status_name_the_profile_for_cosmo_and_only_then(self):
        for command in ('stop', 'status'):
            cosmo = self.start('--dry-run', command, env={'FEDERATION_ROUTER': 'cosmo'})
            self.assertEqual(cosmo.returncode, 0, cosmo.stderr)
            self.assertIn('--profile cosmo', cosmo.stdout)
            self.assertNotIn('--profile', self.start('--dry-run', command).stdout)

    def test_another_router_name_is_refused(self):
        result = self.start('--dry-run', 'status', env={'FEDERATION_ROUTER': 'hive'})
        self.assertEqual(result.returncode, 2)
        self.assertIn('apollo or cosmo', result.stderr)


class CommittedExecutionConfig(unittest.TestCase):
    """The committed execution config is a build product; the stack gate proves it fresh. These checks need no container."""

    @classmethod
    def setUpClass(cls):
        cls.raw = support.COMMITTED_EXECUTION_CONFIG.read_bytes()
        cls.config = json.loads(cls.raw.decode('utf-8'))

    def test_it_is_lf_only_and_exactly_the_bytes_the_script_writes(self):
        self.assertNotIn(b'\r', self.raw)
        self.assertTrue(self.raw.endswith(b'}\n') and not self.raw.endswith(b'\n\n'))
        self.assertEqual(COMPOSE_SCRIPT.normalize_config(self.raw), self.raw)

    def test_it_has_no_timestamp_and_no_graph_identity_so_that_it_can_be_byte_stable(self):
        self.assertEqual(self.config['version'], '00000000-0000-0000-0000-000000000000')
        self.assertEqual(sorted(self.config), ['compatibilityVersion', 'engineConfig', 'featureFlagConfigs', 'subgraphs', 'version'])
        self.assertNotRegex(self.raw.decode('utf-8'), r'20\d\d-\d\d-\d\dT')

    def test_it_joins_exactly_the_four_subgraphs_with_the_routing_urls_of_the_stack(self):
        subgraphs = [(s['name'], s['routingUrl']) for s in self.config['subgraphs']]
        self.assertEqual(subgraphs, [('assets', 'http://assets-adapter:8184/graphql'), ('mapping', 'http://mapping-adapter:8190/graphql'),
                                     ('missions', 'http://missions-adapter:8183/graphql'), ('personnel', 'http://personnel-adapter:8182/graphql')])
        text_ = self.raw.decode('utf-8')
        self.assertNotIn('127.0.0.1', text_)
        self.assertNotIn('localhost', text_)

    def test_the_two_field_requires_with_an_enum_from_another_subgraph_is_in_the_config_for_both_reference_types(self):
        requires = {(r['typeName'], r['fieldName']): r['selectionSet'] for dc in self.config['engineConfig']['datasourceConfigurations'] for r in dc.get('requires', [])}
        self.assertEqual(requires, {('AssetReference', 'asset'): 'assetId mappingOutcome', ('AssetReference', 'resolution'): 'assetId mappingOutcome',
                                    ('PersonnelReference', 'personnel'): 'mappingOutcome personnelId', ('PersonnelReference', 'resolution'): 'mappingOutcome personnelId'})

    def test_it_uses_only_keys_and_requires_no_provides_no_entity_interface_and_no_interface_object(self):
        allowed = {'kind', 'rootNodes', 'childNodes', 'overrideFieldPathFromAlias', 'customGraphql', 'requestTimeoutSeconds', 'id', 'keys', 'requires'}
        for datasource in self.config['engineConfig']['datasourceConfigurations']:
            with self.subTest(datasource=datasource['id']):
                self.assertLessEqual(set(datasource), allowed)
                self.assertTrue(datasource['keys'])
        self.assertEqual(self.config['featureFlagConfigs'], {})

    def test_the_composition_of_cosmo_and_the_one_of_rover_agree_on_the_lab_schemas(self):
        """A matrix item: Cosmo's own composition code against Rover's, on the four subgraphs. Same types, fields with arguments and
        nullability, and enum values; the join directives and the federation spec's own scalar are not part of the comparison."""
        cosmo = schema_inventory(self.config['engineConfig']['graphqlSchema'])
        apollo = schema_inventory(support.APOLLO_SUPERGRAPH.read_bytes().decode('utf-8').replace('\r\n', '\n'))
        self.assertEqual(sorted(cosmo), sorted(apollo))
        for key in sorted(cosmo):
            with self.subTest(type=key):
                self.assertEqual(cosmo[key], apollo[key])
        self.assertGreaterEqual(len(cosmo), 25)


def schema_inventory(sdl):
    """(kind, name) -> sorted member signatures (fields with arguments and type, or enum values or union members) of a printed SDL."""
    inventory, current = {}, None
    for raw in sdl.split('\n'):
        line = raw.rstrip()
        head = re.match(r'^(type|interface|enum|input|union|scalar)\s+(\w+)\b(.*)$', line)
        if head and not raw.startswith(' '):
            kind, name, tail = head.groups()
            current = None
            if name.startswith(('join__', 'link__', 'core__', 'federation__')):
                continue
            inventory[(kind, name)] = []
            if kind == 'union' and '=' in tail:
                inventory[(kind, name)] = [m.strip() for m in tail.split('=', 1)[1].split('@')[0].split('|')]
            elif kind != 'scalar':
                current = (kind, name)
            continue
        if line == '}':
            current = None
        elif current and current[0] == 'union':
            member = re.search(r'@join__unionMember\(.*member: "(\w+)"', line)
            if member and member.group(1) not in inventory[current]:
                inventory[current].append(member.group(1))
        elif current and raw.startswith('  ') and not raw.startswith('   ') and not line.strip().startswith(('@', '#', '"')):
            member = re.split(r'\s@', line.strip())[0]
            if current[0] == 'enum':
                member = member.split()[0]
            inventory[current].append(member)
    return {key: sorted(members) for key, members in inventory.items()}


class SharedSuiteSettings(unittest.TestCase):
    """The settings the Cosmo gate declares to the shared suite, and the helpers that read them, on sample entries (no stack)."""

    COSMO = shared_suite.RouterSettings(adapter_down_code=None, subgraph_key=None, adapter_down_seconds=(4.5, 15),
                                        subgraph_in_message=r"Subgraph '([^']+)'", entries_per='subgraph_fetch')
    APOLLO = shared_suite.RouterSettings(adapter_down_code='GATEWAY_TIMEOUT', subgraph_key='service', adapter_down_seconds=(4.5, 15))

    @staticmethod
    def router(settings):
        return shared_suite.Router('http://127.0.0.1:1/', shared_suite.Controls(), settings)

    def test_the_cosmo_entry_of_a_dead_adapter_has_no_code_and_names_its_subgraph_in_its_message(self):
        router = self.router(self.COSMO)
        entries = [{'message': "Failed to fetch from Subgraph 'assets' at Path 'mission.assets'."}]
        self.assertEqual(router.failed_fetches(entries), {router.expected_failure('assets')})
        self.assertEqual(router.expected_failure('assets'), (None, 'assets'))
        self.assertEqual(router.subgraphs(entries), ['assets'])

    def test_cosmo_counts_one_entry_per_failed_fetch_and_apollo_one_per_reference(self):
        self.assertEqual(self.router(self.COSMO).expected_entries(2), 1)
        self.assertEqual(self.router(self.APOLLO).expected_entries(2), 2)
        self.assertEqual(self.router(self.COSMO).expected_subgraphs(['assets', 'assets', 'personnel', 'personnel']), ['assets', 'personnel'])
        self.assertEqual(self.router(self.APOLLO).expected_subgraphs(['assets', 'assets', 'personnel']), ['assets', 'assets', 'personnel'])

    def test_the_apollo_entry_is_read_exactly_as_before(self):
        router = self.router(self.APOLLO)
        entries = [{'message': 'x', 'extensions': {'code': 'GATEWAY_TIMEOUT', 'service': 'assets'}}] * 2
        self.assertEqual(router.failed_fetches(entries), {('GATEWAY_TIMEOUT', 'assets')})
        self.assertEqual(router.expected_failure('assets'), ('GATEWAY_TIMEOUT', 'assets'))
        self.assertEqual(router.subgraphs(entries), ['assets', 'assets'])
        self.assertEqual(router.codes_of(entries), {'GATEWAY_TIMEOUT'})

    def test_a_router_that_names_the_subgraph_nowhere_is_matched_by_code_and_number_only(self):
        router = self.router(shared_suite.RouterSettings(adapter_down_code='X', subgraph_key=None, adapter_down_seconds=(1, 2)))
        entries = [{'message': 'boom', 'extensions': {'code': 'X'}}] * 2
        self.assertEqual(router.failed_fetches(entries), {('X', None)})
        self.assertEqual(router.subgraphs(entries), [None, None])
        self.assertEqual(router.expected_subgraphs(['assets', 'assets']), [None, None])

    def test_a_cosmo_entry_that_does_not_name_a_subgraph_fails_loudly(self):
        with self.assertRaises(AssertionError):
            self.router(self.COSMO).failed_fetches([{'message': 'Something else failed'}])

    def test_the_gate_declares_the_same_settings_as_these_samples(self):
        gate = load(support.ROUTER_DIR / 'validation/runtime/stack/test_stack.py', 'cosmo_test_stack')
        self.assertEqual(gate.COSMO, self.COSMO)


class Sources(unittest.TestCase):
    def test_every_python_file_of_the_router_compiles_so_a_broken_stack_test_fails_offline(self):
        import ast
        files = [p for p in support.ROUTER_DIR.rglob('*.py')]
        self.assertGreaterEqual(len(files), 5)
        for path in files:
            with self.subTest(path=path.name):
                ast.parse(path.read_text(encoding='utf-8'), str(path))


class Readme(unittest.TestCase):
    def test_the_readme_says_what_the_execution_config_is_and_which_ports_and_versions_are_used(self):
        readme = text(support.ROUTER_DIR / 'README.md')
        self.assertIn('8171', readme)
        self.assertIn('build product', readme)
        self.assertIn('0.359.0', readme)
        self.assertIn('0.133.0', readme)
        self.assertIn('Apache', readme)
        self.assertIn('COSMO_TELEMETRY_DISABLED', readme)
        self.assertIn('five Cosmo Cloud features', readme)
        self.assertIn('introspection.enabled: true', readme)


if __name__ == '__main__':
    unittest.main()
