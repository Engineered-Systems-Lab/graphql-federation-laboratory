"""Tests of run provenance with a fake Docker and a fake stack: the declaration, the read-only observation, the comparison that refuses before
any paid request, the records in the bundle, the drift check on resume and the redaction. No container is started, stopped or inspected."""
import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path

import provenance
from fakes import FakeDocker, FakeVendorClient, container, submit
from mcp_client import FakeToolSession
from runner import Study
from study_common import Redactor, read_jsonl, sha256_file
from test_runner import CORPUS, MODELS, PRICES, FakeStack, task

STUB_ID = 'sha256:' + '1' * 64
REAL_ID = 'sha256:' + '2' * 64
ADAPTER_ID = 'sha256:' + '3' * 64
ROUTER_ID = 'sha256:' + '4' * 64
DB_PASSWORD = 'local-db-pass-7731'
API_KEY = 'sk-ant-SECRETSECRETSECRET'


class Lab:
    """A temporary folder with a dataset file, a mapping folder, a launch script that holds a password and the scripted containers of a
    stub-mode stack."""

    def __init__(self, root):
        self.root = Path(root)
        self.dataset = self.root / 'data' / 'missions-1.2.json'
        self.dataset.parent.mkdir(parents=True)
        self.dataset.write_text('{"missions": 300}\n', encoding='utf-8')
        self.mapping = self.root / 'mapping'
        (self.mapping / '1.3').mkdir(parents=True)
        (self.mapping / '1.3' / 'manifest.json').write_text('{"release": "1.3"}\n', encoding='utf-8')
        self.script = self.root / 'start-stack.sh'
        self.script.write_text('export STACK_ASSETS_DB_ADMIN_PASSWORD=%s\ndocker compose up -d\n' % DB_PASSWORD, encoding='utf-8')

    def containers(self, missions_url='http://missions-stub:8083', stub_id=STUB_ID, stub_state='running', router_port='8170'):
        return [
            container('stack', 'missions-stub', 'stack-missions-stub:1.0.0', stub_id, state=stub_state,
                      mounts=[(self.dataset, '/data/missions.json', True)]),
            container('stack', 'missions-adapter', 'stack-missions-adapter:1.0.0', ADAPTER_ID,
                      env={'MISSIONS_SERVICE_URL': missions_url, 'ADAPTER_PORT': '8183', 'PATH': '/usr/local/bin:/usr/bin',
                           'PGPASSWORD': DB_PASSWORD, 'MISSIONS_READ_TIMEOUT_MS': '1500'},
                      ports={'8183/tcp': [('127.0.0.1', '8183')]}),
            container('stack', 'router', 'ghcr.io/apollographql/router@sha256:' + '5' * 64, ROUTER_ID,
                      env={'APOLLO_TELEMETRY_DISABLED': 'true'}, ports={'4000/tcp': [('127.0.0.1', router_port)]},
                      mounts=[(self.mapping, '/config/mapping', True)]),
            container('stack', 'assets-bootstrap', 'stack-assets:1.0.0', 'sha256:' + '6' * 64, state='exited'),
        ]

    def declaration(self, **backend_over):
        missions = {'mode': 'simulated', 'service': 'missions-stub', 'image_id': STUB_ID, 'image_ref': 'stack-missions-stub:1.0.0',
                    'dataset': {'id': 'missions-1.2', 'path': str(self.dataset), 'sha256': sha256_file(self.dataset),
                                'mount': '/data/missions.json'}}
        missions.update(backend_over)
        return {'compose_projects': ['stack'],
                'backends': {'missions': missions},
                'routing': {'endpoints': {'http://127.0.0.1:8170/': 'router'},
                            'env': {'missions-adapter': {'MISSIONS_SERVICE_URL': 'http://missions-stub:8083'}}},
                'launch_files': {'stack_start': str(self.script)}}

    def stack_commands(self):
        return {'start': [{'argv': ['bash', str(self.script), '--db-password', DB_PASSWORD], 'cwd': str(self.root),
                           'env': {'STACK_ASSETS_DB_ADMIN_PASSWORD': DB_PASSWORD, 'ROUTER': 'apollo'}},
                          {'argv': ['python', '-B', str(self.root / 'raw_server.py'), '--mapping-dir=%s' % self.mapping], 'background': True}],
                'teardown': [{'argv': ['bash', str(self.root / 'stop.sh')]}]}

    def scenario(self, **over):
        base = {'mcp_url': 'http://127.0.0.1:8191/mcp', 'stack': self.stack_commands(), 'provenance': self.declaration()}
        base.update(over)
        return base


class DeclarationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.lab = Lab(self.tmp.name)

    def test_a_good_declaration_passes(self):
        provenance.validate('alpha', self.lab.declaration())

    def test_a_missing_or_malformed_declaration_is_refused_naming_the_field(self):
        cases = [
            (None, 'scenario alpha: provenance is missing'),
            ({'backends': {}}, 'compose_projects'),
            ({'compose_projects': ['stack'], 'backends': {}}, 'at least one backend'),
            (self.lab.declaration(mode='oracle'), 'backends.missions.mode must be one of real, simulated'),
            ({**self.lab.declaration(), 'extra': 1}, 'unknown keys: extra'),
            ({'compose_projects': ['stack'], 'backends': {'missions': {'mode': 'real', 'service': 'missions'}}}, 'image_id or image_ref'),
            (self.lab.declaration(image_id='abc'), 'image_id must be sha256'),
            (self.lab.declaration(dataset={'id': 'd', 'path': 'p', 'sha256': 'XYZ'}), 'dataset.sha256'),
            (self.lab.declaration(dataset={'id': 'd', 'path': 'p', 'sha256': 'a' * 64, 'mount': 'data'}), 'container path'),
            ({**self.lab.declaration(), 'routing': {'endpoints': {'not a url': 'router'}}}, 'not an http'),
            ({**self.lab.declaration(), 'routing': {'endpoints': {'http://unrelated.example:8083/': 'router'}}}, 'does not name a loopback host'),
        ]
        for block, message in cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(ValueError, re.escape(message)):
                    provenance.validate('alpha', block)

    def test_the_intended_record_keeps_no_host_path(self):
        intended = provenance.intended(self.lab.declaration())
        text = json.dumps(intended)
        self.assertNotIn(self.tmp.name.replace('\\', '\\\\'), text)
        self.assertEqual(intended['backends']['missions']['dataset']['path'], '<path>/missions-1.2.json')
        self.assertEqual(intended['launch_files'], {'stack_start': '<path>/start-stack.sh'})
        self.assertEqual(intended['backends']['missions']['mode'], 'simulated')

    def test_the_intended_record_masks_secret_routing_values_and_url_credentials(self):
        declaration = self.lab.declaration()
        declaration['routing']['env']['missions-adapter']['DB_PASSWORD'] = DB_PASSWORD
        declaration['routing']['env']['missions-adapter']['BACKUP_SERVICE_URL'] = 'http://lab:%s@db:1521/x' % DB_PASSWORD
        declaration['routing']['endpoints']['http://lab:%s@127.0.0.1:8170/' % DB_PASSWORD] = 'router'
        text = json.dumps(provenance.intended(declaration))
        self.assertNotIn(DB_PASSWORD, text)
        env = provenance.intended(declaration)['routing']['env']['missions-adapter']
        self.assertEqual(env['DB_PASSWORD'], provenance.MASK)
        self.assertEqual(env['BACKUP_SERVICE_URL'], 'http://[MASKED]@db:1521/x')
        self.assertEqual(env['MISSIONS_SERVICE_URL'], 'http://missions-stub:8083')


class RedactionTests(unittest.TestCase):
    def test_secret_names_are_masked_and_the_name_kept(self):
        for name in ('PGPASSWORD', 'STACK_ASSETS_DB_ADMIN_PASSWORD', 'ANTHROPIC_API_KEY', 'OPENAI_API_KEY', 'graph_token', 'CLIENT_SECRET',
                     'MISSIONS_DB_PASSWORD'):
            self.assertEqual(provenance.redact_env(name, 'value-123'), provenance.MASK, name)
        self.assertEqual(provenance.redact_env('MISSIONS_SERVICE_URL', 'http://missions-stub:8083'), 'http://missions-stub:8083')

    def test_url_credentials_are_masked(self):
        self.assertEqual(provenance.redact_value('jdbc:oracle:thin://lab:pw123@db:1521/X'), 'jdbc:oracle:thin://[MASKED]@db:1521/X')

    def test_host_paths_are_reduced_and_urls_left_alone(self):
        self.assertEqual(provenance.reduce_paths(r'C:\esl\lab\federation\stack\start.sh'), '<path>/start.sh')
        self.assertEqual(provenance.reduce_paths('--mapping-dir=C:/Users/someone/mapping'), '--mapping-dir=<path>/mapping')
        self.assertEqual(provenance.reduce_paths('/home/someone/lab/compose.yaml'), '<path>/compose.yaml')
        self.assertEqual(provenance.reduce_paths('http://127.0.0.1:8170/graphql/v2'), 'http://127.0.0.1:8170/graphql/v2')
        self.assertEqual(provenance.reduce_paths('http://personnel-service:8082/soap/personnel-v2'), 'http://personnel-service:8082/soap/personnel-v2')

    def test_secret_options_of_a_command_line_are_masked(self):
        self.assertEqual(provenance.redact_argv(['run', '--db-password', 'x1', '--api-key=y2', '--port', '8']),
                         ['run', '--db-password', provenance.MASK, '--api-key=' + provenance.MASK, '--port', '8'])

    def test_the_launch_configuration_is_redacted(self):
        with tempfile.TemporaryDirectory() as root:
            lab = Lab(root)
            config = provenance.launch_configuration(lab.stack_commands())
            text = json.dumps(config)
            self.assertNotIn(DB_PASSWORD, text)
            self.assertNotIn(root.replace('\\', '\\\\'), text)
            self.assertEqual(config['start'][0]['env']['STACK_ASSETS_DB_ADMIN_PASSWORD'], provenance.MASK)
            self.assertEqual(config['start'][0]['argv'], ['bash', '<path>/start-stack.sh', '--db-password', provenance.MASK])
            self.assertEqual(config['start'][1]['argv'][-1], '--mapping-dir=<path>/mapping')
            self.assertTrue(config['start'][1]['background'])


class ObservationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.lab = Lab(self.tmp.name)

    def observe(self, docker=None, scenario=None):
        return provenance.observe('alpha', scenario or self.lab.scenario(), docker or FakeDocker(self.lab.containers()))

    def test_only_the_two_read_only_commands_are_run(self):
        docker = FakeDocker(self.lab.containers())
        self.observe(docker)
        self.assertEqual(docker.calls[0], ['compose', '-p', 'stack', 'ps', '--all', '--format', 'json'])
        self.assertEqual(docker.calls[1][0], 'inspect')
        self.assertEqual(len(docker.calls), 2)
        for argv in docker.calls:
            provenance.assert_read_only(argv)

    def test_the_real_docker_runner_refuses_anything_that_could_change_the_stack(self):
        ran = []
        cli = provenance.DockerCli(run=lambda *a, **k: ran.append(a))
        for argv in (['compose', '-p', 'stack', 'up', '-d'], ['compose', '-p', 'stack', 'down'], ['rm', '-f', 'x'], ['stop', 'x'],
                     ['inspect', '--format', '{{.State}}', 'x'], ['compose', '-p', 'stack', 'ps', '--all', '--format', 'json', '--quiet']):
            with self.subTest(argv=argv):
                with self.assertRaisesRegex(ValueError, 'Only docker compose ps and docker inspect'):
                    cli(argv)
        self.assertEqual(ran, [])

    def test_both_compose_ps_formats_give_the_same_observation(self):
        lines = self.observe(FakeDocker(self.lab.containers(), lines=True))
        array = self.observe(FakeDocker(self.lab.containers(), lines=False))
        self.assertEqual(lines['fingerprint'], array['fingerprint'])

    def test_the_observation_holds_images_routing_mounts_and_hashes(self):
        stable = self.observe()['stable']
        adapter = stable['services']['stack/missions-adapter']
        self.assertEqual(adapter['imageId'], ADAPTER_ID)
        self.assertEqual(adapter['env'], {'ADAPTER_PORT': '8183', 'MISSIONS_SERVICE_URL': 'http://missions-stub:8083'})  # no PATH, no password
        self.assertEqual(stable['services']['stack/router']['ports'], ['127.0.0.1:8170->4000/tcp'])
        stub_mount = stable['services']['stack/missions-stub']['mounts'][0]
        self.assertEqual(stub_mount, {'destination': '/data/missions.json', 'readOnly': True, 'kind': 'file', 'sha256': sha256_file(self.lab.dataset)})
        self.assertEqual(stable['services']['stack/router']['mounts'][0]['kind'], 'folder')
        self.assertEqual(stable['services']['stack/assets-bootstrap']['state'], 'exited')
        self.assertEqual(stable['datasets']['missions']['sha256'], sha256_file(self.lab.dataset))
        self.assertEqual(stable['launchFiles'], {'stack_start': sha256_file(self.lab.script)})
        self.assertEqual(stable['mcpUrl'], 'http://127.0.0.1:8191/mcp')

    def test_url_credentials_in_the_mcp_url_are_masked(self):
        stable = self.observe(scenario=self.lab.scenario(mcp_url='http://lab:%s@127.0.0.1:8191/mcp' % DB_PASSWORD))['stable']
        self.assertEqual(stable['mcpUrl'], 'http://[MASKED]@127.0.0.1:8191/mcp')

    def test_an_unreadable_mount_source_is_recorded_without_a_hash(self):
        containers = self.lab.containers()
        containers[0]['Mounts'][0]['Source'] = '/run/desktop/mnt/host/c/nowhere/missions-1.2.json'
        mount = self.observe(FakeDocker(containers))['stable']['services']['stack/missions-stub']['mounts'][0]
        self.assertEqual((mount['kind'], mount['sha256']), (None, None))
        self.assertNotIn('nowhere', json.dumps(mount))

    def test_an_unreadable_mount_of_a_declared_dataset_refuses(self):
        containers = self.lab.containers()
        containers[0]['Mounts'][0]['Source'] = '/run/desktop/mnt/host/c/nowhere/missions-1.2.json'
        problems = provenance.compare(self.lab.declaration(), self.observe(FakeDocker(containers)))
        self.assertTrue(any('the mount /data/missions.json of stack/missions-stub cannot be read from the harness' in p for p in problems),
                        problems)
        declaration = self.lab.declaration()
        del declaration['backends']['missions']['dataset']['mount']
        self.assertEqual(provenance.compare(declaration, self.observe(FakeDocker(containers))), [])

    def test_an_endpoint_needs_a_loopback_host_served_by_the_binding(self):
        def problems(url, binding):
            declaration = self.lab.declaration()
            declaration['routing']['endpoints'] = {url: 'router'}
            containers = self.lab.containers()
            containers[2]['NetworkSettings']['Ports'] = {'4000/tcp': [{'HostIp': binding, 'HostPort': '8170'}]}
            return provenance.compare(declaration, provenance.observe('alpha', self.lab.scenario(provenance=declaration), FakeDocker(containers)))
        self.assertTrue(any('not a loopback host' in p for p in problems('http://unrelated.example:8170/', '127.0.0.1')))
        self.assertEqual(problems('http://127.0.0.1:8170/', '127.0.0.1'), [])
        self.assertEqual(problems('http://localhost:8170/', '0.0.0.0'), [])
        self.assertEqual(problems('http://[::1]:8170/', '::'), [])
        self.assertTrue(any('does not publish port 8170 for [::1]' in p for p in problems('http://[::1]:8170/', '127.0.0.1')))
        self.assertTrue(any('does not publish port 8170 for 127.0.0.1' in p for p in problems('http://127.0.0.1:8170/', '192.168.1.5')))

    def test_the_fingerprint_ignores_container_ids_and_times_but_not_images(self):
        one = self.observe()
        containers = self.lab.containers()
        for c in containers:
            c['Id'] = c['Id'] + '-restarted'
        self.assertEqual(self.observe(FakeDocker(containers))['fingerprint'], one['fingerprint'])
        self.assertNotEqual(self.observe(FakeDocker(self.lab.containers(stub_id=REAL_ID)))['fingerprint'], one['fingerprint'])

    def test_a_matching_stack_has_no_problem(self):
        self.assertEqual(provenance.compare(self.lab.declaration(), self.observe()), [])

    def test_every_kind_of_mismatch_is_named(self):
        declaration = self.lab.declaration()
        cases = [
            # the study-1 case: declared real, but the adapter is routed to the simulator
            (dict(self.lab.declaration(mode='real', service='missions', image_ref='starfleet-missions-service:1.0.0'),
                  compose_projects=['stack'], routing={'env': {'missions-adapter': {'MISSIONS_SERVICE_URL': 'http://host.docker.internal:8083'}}}),
             self.lab.containers(), ['backend missions (real): service missions is not among the observed containers',
                                     'routing of stack/missions-adapter: MISSIONS_SERVICE_URL is http://missions-stub:8083, expected '
                                     'http://host.docker.internal:8083']),
            (declaration, self.lab.containers(stub_id=REAL_ID), ['runs image id %s, expected %s' % (REAL_ID, STUB_ID)]),
            (declaration, self.lab.containers(stub_state='exited'), ['stack/missions-stub is exited, not running']),
            (declaration, self.lab.containers(missions_url='http://other:8083'), ['MISSIONS_SERVICE_URL is http://other:8083']),
            (declaration, self.lab.containers(router_port='8171'), ['endpoint http://127.0.0.1:8170/: stack/router does not publish port 8170 for '
                                                                    '127.0.0.1']),
            (declaration, self.lab.containers()[1:], ['service missions-stub is not among the observed containers']),
        ]
        for block, containers, messages in cases:
            with self.subTest(messages=messages):
                problems = provenance.compare(block, provenance.observe('alpha', self.lab.scenario(provenance=block), FakeDocker(containers)))
                for message in messages:
                    self.assertTrue(any(message in p for p in problems), (message, problems))

    def test_a_changed_dataset_a_missing_mount_and_a_missing_launch_file_are_named(self):
        self.lab.dataset.write_text('{"missions": 299}\n', encoding='utf-8')
        declaration = self.lab.declaration()
        declaration['backends']['missions']['dataset']['sha256'] = 'f' * 64
        declaration['launch_files']['gone'] = str(Path(self.tmp.name) / 'gone.sh')
        containers = self.lab.containers()
        containers[0]['Mounts'] = []
        problems = provenance.compare(declaration, provenance.observe('alpha', self.lab.scenario(provenance=declaration), FakeDocker(containers)))
        text = '\n'.join(problems)
        self.assertIn('dataset missions-1.2 hashes to %s, expected %s' % (sha256_file(self.lab.dataset), 'f' * 64), text)
        self.assertIn('stack/missions-stub has no bind mount at /data/missions.json', text)
        self.assertIn('launch file gone could not be read at <path>/gone.sh', text)
        self.assertNotIn(self.tmp.name, text)

    def test_an_ambiguous_service_name_must_name_its_project(self):
        declaration = self.lab.declaration()
        declaration['compose_projects'] = ['stack', 'other']
        containers = self.lab.containers() + [container('other', 'missions-stub', 'x', STUB_ID)]
        problems = provenance.compare(declaration, provenance.observe('alpha', self.lab.scenario(provenance=declaration), FakeDocker(containers)))
        self.assertTrue(any('ambiguous' in p for p in problems), problems)
        declaration['backends']['missions']['service'] = 'stack/missions-stub'
        self.assertEqual(provenance.compare(declaration, provenance.observe('alpha', self.lab.scenario(provenance=declaration),
                                                                            FakeDocker(containers))), [])

    def test_drift_names_each_change(self):
        one = self.observe()['stable']
        two = self.observe(FakeDocker(self.lab.containers(missions_url='http://other:8083', stub_id=REAL_ID)))['stable']
        changes = provenance.drift(one, two)
        self.assertIn('services.stack/missions-adapter.env.MISSIONS_SERVICE_URL: "http://missions-stub:8083" -> "http://other:8083"', changes)
        self.assertIn('services.stack/missions-stub.imageId: "%s" -> "%s"' % (STUB_ID, REAL_ID), changes)
        self.assertEqual(provenance.drift(one, one), [])


class StudyProvenanceTests(unittest.TestCase):
    """The provenance check inside a whole (fake) study run."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.lab = Lab(root / 'lab')
        self.corpus = root / 'corpus'
        self.corpus.mkdir()
        shutil.copy(CORPUS / 'scoring.py', self.corpus / 'scoring.py')
        (self.corpus / 'corpus-manifest.json').write_text('{"freeze": "test"}\n', encoding='utf-8')
        (self.corpus / 'dev.json').write_text(json.dumps({'tasks': [task('P1'), task('P2')]}), encoding='utf-8')
        self.results = root / 'results'
        FakeStack.log = []
        self.made = []
        self.lookups = []

    def config(self, declaration=None):
        scenario = self.lab.scenario(warmup_calls=[{'tool': 'lookup', 'arguments': {}}])
        if declaration:
            scenario['provenance'] = declaration
        return {'scenarios': {'alpha': scenario}, 'scenario_order': ['alpha'], 'models': ['model-a', 'model-b'], 'trials': 1, 'seed': 3,
                'task_set': 'dev', 'warmup_passes': 1, 'budgets': {'va': {'tokens': 1_000_000}, 'vb': {'tokens': 1_000_000}},
                'limits': {'max_tool_calls': 5, 'retry_backoff_seconds': 0}}

    def factory(self, model):
        client = FakeVendorClient([lambda s, t, tools: submit({'value': 'blue'})] * 50, max_output_tokens=100, model=model)
        self.made.append(client)
        return client

    def study(self, docker, config=None):
        session = lambda scenario, run_id: FakeToolSession([{'name': 'lookup', 'description': 'd', 'input_schema': {'type': 'object'}}],
                                                           {'lookup': lambda a: self.lookups.append(a) or 'ok'})
        return Study(config or self.config(), MODELS, PRICES, 'r1', root=self.results, corpus_dir=self.corpus, client_factory=self.factory,
                     session_factory=session, stack_factory=FakeStack, redactor=Redactor([API_KEY]), sleep=lambda s: None, docker=docker)

    def paid_requests(self):
        return sum(len(c.calls) for c in self.made)

    def test_a_scenario_without_provenance_is_refused_before_anything_runs(self):
        config = self.config()
        del config['scenarios']['alpha']['provenance']
        with self.assertRaisesRegex(ValueError, 'scenario alpha: provenance is missing'):
            self.study(FakeDocker(self.lab.containers()), config)
        self.assertEqual(FakeStack.log, [])

    def test_a_matching_stack_is_recorded_in_the_manifest_and_the_bundle(self):
        study = self.study(FakeDocker(self.lab.containers()))
        self.assertEqual(study.run(), 'complete')
        manifest = json.loads((study.dir / 'manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(manifest['provenance']['schema'], 1)
        self.assertEqual(manifest['provenance']['intended']['alpha']['backends']['missions']['mode'], 'simulated')
        self.assertEqual(manifest['provenance']['observationCommands'], provenance.OBSERVATION_COMMANDS)
        observed = json.loads((study.dir / 'provenance' / 'alpha.json').read_text(encoding='utf-8'))
        self.assertEqual(observed['comparison'], {'result': 'match', 'problems': []})
        self.assertEqual(observed['stable']['services']['stack/missions-stub']['imageId'], STUB_ID)
        bundle = json.loads((study.dir / 'bundle.json').read_text(encoding='utf-8'))
        self.assertEqual(bundle['files']['provenance/alpha.json'], sha256_file(study.dir / 'provenance' / 'alpha.json'))
        self.assertFalse((study.dir / 'provenance' / 'checks.jsonl').exists())

    def test_the_observation_comes_after_ready_and_before_the_warm_up_and_any_paid_request(self):
        inner = FakeDocker(self.lab.containers())
        seen = []

        def docker(argv):
            seen.append((list(FakeStack.log), len(self.lookups), self.paid_requests()))
            return inner(argv)
        study = self.study(docker)
        self.assertEqual(study.run(), 'complete')
        self.assertTrue(seen)
        for log, lookups, paid in seen:
            self.assertEqual(log, [('start', 'alpha'), ('ready', 'alpha')])
            self.assertEqual((lookups, paid), (0, 0))
        self.assertGreater(len(self.lookups), 0)
        self.assertGreater(self.paid_requests(), 0)

    def test_a_mismatch_refuses_before_any_paid_request_and_keeps_a_refused_bundle(self):
        study = self.study(FakeDocker(self.lab.containers(missions_url='http://host.docker.internal:8083')))
        with self.assertRaises(provenance.ProvenanceRefused) as caught:
            study.run()
        self.assertIn('MISSIONS_SERVICE_URL is http://host.docker.internal:8083, expected http://missions-stub:8083', str(caught.exception))
        self.assertEqual(self.paid_requests(), 0)
        self.assertEqual(FakeStack.log[-1], ('teardown', 'alpha'))
        self.assertFalse((study.dir / 'provenance' / 'alpha.json').exists())
        check = read_jsonl(study.dir / 'provenance' / 'checks.jsonl')[0]
        self.assertEqual(check['result'], 'mismatch')
        bundle = json.loads((study.dir / 'bundle.json').read_text(encoding='utf-8'))
        self.assertEqual(bundle['status'], 'provenance_refused')
        self.assertIn('provenance/checks.jsonl', bundle['files'])
        # the stack is corrected: the resume runs and stores the observation
        self.assertEqual(self.study(FakeDocker(self.lab.containers())).run(resume=True), 'complete')
        self.assertTrue((study.dir / 'provenance' / 'alpha.json').exists())

    def test_a_stack_that_cannot_be_observed_is_refused(self):
        study = self.study(FakeDocker([], fail=RuntimeError('docker daemon not running')))
        with self.assertRaisesRegex(provenance.ProvenanceRefused, 'could not be observed: RuntimeError: docker daemon not running'):
            study.run()
        self.assertEqual(self.paid_requests(), 0)

    def test_a_resume_against_the_same_stack_records_a_match(self):
        config = self.config()
        config['budgets']['vb']['tokens'] = 50  # less than one request of vendor b: a budget stop after the observation
        self.assertEqual(self.study(FakeDocker(self.lab.containers()), config).run(), 'budget_stop')
        config['budgets']['vb']['tokens'] = 1_000_000
        restarted = self.lab.containers()
        for c in restarted:
            c['Id'] += '-2'
        study = self.study(FakeDocker(restarted), config)
        self.assertEqual(study.run(resume=True), 'complete')
        checks = read_jsonl(study.dir / 'provenance' / 'checks.jsonl')
        self.assertEqual([c['result'] for c in checks], ['match'])

    def test_a_resume_refuses_drift_naming_what_changed(self):
        config = self.config()
        config['budgets']['vb']['tokens'] = 50
        self.study(FakeDocker(self.lab.containers()), config).run()
        config['budgets']['vb']['tokens'] = 1_000_000
        self.made = []
        # the same declaration still matches a new adapter image, but the stored observation does not
        containers = self.lab.containers()
        containers[1]['Image'] = 'sha256:' + '9' * 64
        study = self.study(FakeDocker(containers), config)
        with self.assertRaises(provenance.ProvenanceRefused) as caught:
            study.run(resume=True)
        self.assertIn('services.stack/missions-adapter.imageId: "%s" -> "%s"' % (ADAPTER_ID, 'sha256:' + '9' * 64), str(caught.exception))
        self.assertEqual(self.paid_requests(), 0)
        self.assertEqual(read_jsonl(study.dir / 'provenance' / 'checks.jsonl')[-1]['result'], 'drift')
        self.assertEqual(json.loads((study.dir / 'bundle.json').read_text(encoding='utf-8'))['status'], 'provenance_refused')

    def test_a_resume_refuses_a_changed_declaration(self):
        self.study(FakeDocker(self.lab.containers())).run()
        declaration = self.lab.declaration(image_ref='stack-missions-stub:1.0.1')
        with self.assertRaisesRegex(RuntimeError, 'declared provenance differs'):
            self.study(FakeDocker(self.lab.containers()), self.config(declaration)).run(resume=True)

    def test_a_resume_of_a_bundle_without_provenance_is_refused(self):
        study = self.study(FakeDocker(self.lab.containers()))
        study.run()
        manifest = json.loads((study.dir / 'manifest.json').read_text(encoding='utf-8'))
        del manifest['provenance']
        (study.dir / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
        with self.assertRaisesRegex(RuntimeError, 'records no provenance'):
            self.study(FakeDocker(self.lab.containers())).run(resume=True)

    def test_nothing_written_holds_a_password_a_key_a_script_or_a_host_path(self):
        containers = self.lab.containers()
        containers[1]['Config']['Env'].append('MISSIONS_TOKEN_URL=' + API_KEY)
        containers[1]['Config']['Env'].append('BACKUP_SERVICE_URL=http://lab:%s@db:1521/x' % DB_PASSWORD)
        study = self.study(FakeDocker(containers))
        study.run()
        script_text = self.lab.script.read_text(encoding='utf-8')
        for path in study.dir.rglob('*'):
            if path.is_file():
                text = path.read_text(encoding='utf-8')
                self.assertNotIn(DB_PASSWORD, text, path.name)
                self.assertNotIn(API_KEY, text, path.name)
                self.assertNotIn(script_text.splitlines()[0], text, path.name)
                self.assertNotIn(self.tmp.name.replace('\\', '\\\\'), text, path.name)
                self.assertIsNone(re.search(r'(?<![A-Za-z])[A-Za-z]:[\\/]', text), path.name)
        observed = json.loads((study.dir / 'provenance' / 'alpha.json').read_text(encoding='utf-8'))
        env = observed['stable']['services']['stack/missions-adapter']['env']
        self.assertEqual(env['MISSIONS_TOKEN_URL'], provenance.MASK)
        self.assertEqual(env['BACKUP_SERVICE_URL'], 'http://[MASKED]@db:1521/x')
        self.assertEqual(observed['stable']['launchConfiguration']['start'][0]['env']['STACK_ASSETS_DB_ADMIN_PASSWORD'], provenance.MASK)


if __name__ == '__main__':
    unittest.main()
