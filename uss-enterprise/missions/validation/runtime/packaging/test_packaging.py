"""Missions packaging acceptance: the committed Dockerfile, .dockerignore and compose.yaml, through Docker Compose, joined to the
reviewed Oracle 18c container.

The heavy API matrix stays in the service gates (which build from the same committed Dockerfile); this gate checks what only
the packaging owns: both base images pinned by digest, a compose file that fails closed without credentials, an image that
builds from the committed files and runs as UID 10001, a service started by compose on the external internal Oracle network
that answers GET /missions through the loopback publication, and a container that exits non-zero with Config's message on a bad
configuration.

Everything is disposable and uniquely named per run: one compose project, one image tag, one container name, an ephemeral
loopback port, a MS_TEST_ schema loaded with release 1.0 and a MS_SVC_ login that can only read it. The Oracle container and
its network are reused and never removed, recreated or changed beyond that schema and login. Missing Docker, Compose or Oracle
is a failure, never a skip.
"""
from pathlib import Path
import json
import os
import re
import secrets
import socket
import subprocess
import sys
import time
import unittest

COMPONENT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(COMPONENT / 'validation/runtime/service'))
import service_harness as harness
from lxml import etree

operator = harness.operator
q = harness.q

COMPOSE_FILE = COMPONENT / 'compose.yaml'
BASES = ('maven:3.9.11-eclipse-temurin-17@sha256:e4a7ace3dc0d645ed97f8d9ad0b0d3f0b14fa8d150138f27f116d7105a639b82',
         'eclipse-temurin:17-jre-jammy@sha256:97137382c6f0c30427d9b7c44ad8b2d55ac823b0768c171d81a643ed219023c5')
CREDENTIALS = ('MISSIONS_JDBC_URL', 'MISSIONS_DB_USER', 'MISSIONS_DB_PASSWORD')
# Throwaway values for the checks that never reach a database; the real login's password is used only by test_04.
DUMMY = {'MISSIONS_JDBC_URL': 'jdbc:oracle:thin:@//unused:1521/unused', 'MISSIONS_DB_USER': 'unused', 'MISSIONS_DB_PASSWORD': 'unused'}
TIMINGS = {}


def phase(name, started):
    TIMINGS[name] = round(time.monotonic() - started, 1)
    print('missions-packaging timing: ' + name + ' ' + str(TIMINGS[name]) + 's', flush=True)


def free_port():
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        return probe.getsockname()[1]


class PackagingAcceptance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.run_id = secrets.token_hex(6)
        cls.project = 'missions-pkg-' + cls.run_id
        cls.image = 'missions-packaging-validation:' + cls.run_id
        cls.container = 'missions-packaging-' + cls.run_id
        cls.port = free_port()
        cls.schema = 'MS_TEST_' + cls.run_id.upper()
        cls.login = 'MS_SVC_' + cls.run_id.upper()
        cls.password = 'P' + secrets.token_hex(12)
        cls.owned = []
        cls.started = time.monotonic()
        try:
            started = time.monotonic()
            operator.db_guard()
            operator.create_schema(cls.schema)
            cls.owned.append('schema')
            operator.reset('1.0', cls.schema, check_service=False)
            # The password travels on SQL stdin, never argv or output.
            operator.sql('CREATE USER ' + cls.login + ' IDENTIFIED BY "' + cls.password + '" DEFAULT TABLESPACE USERS;\n'
                         'GRANT CREATE SESSION TO ' + cls.login + ';')
            cls.owned.append('login')
            for table in operator.TABLES:
                operator.sql('GRANT SELECT ON ' + cls.schema + '.' + table + ' TO ' + cls.login + ';')
            phase('oracle-schema-load-and-login', started)
        except BaseException:
            cls.cleanup()
            raise

    @classmethod
    def tearDownClass(cls):
        cls.cleanup()
        TIMINGS['class total'] = round(time.monotonic() - cls.started, 1)
        print('missions-packaging timings (seconds): ' + json.dumps(TIMINGS), flush=True)

    @classmethod
    def cleanup(cls):
        problems = []

        def attempt(label, action):
            try:
                action()
            except Exception as error:
                problems.append(label + ': ' + str(error))

        def down():
            result = cls.compose(['down', '--volumes', '--remove-orphans'], cls.env(DUMMY), timeout=180)
            if result.returncode:
                raise RuntimeError(result.stderr[-1500:])
        attempt('compose project', down)
        attempt('image', lambda: harness.docker(['rmi', '--force', cls.image], check=False))
        if 'login' in cls.owned:
            attempt('login', lambda: operator.sql('DROP USER ' + cls.login + ' CASCADE;'))
        if 'schema' in cls.owned:
            attempt('schema', lambda: operator.drop_test_schema(cls.schema))
        if problems:
            raise RuntimeError('Cleanup of owned resources failed: ' + '; '.join(problems))

    # --- helpers -----------------------------------------------------------------------------------------

    @classmethod
    def env(cls, credentials, overrides=True):
        """The compose process environment: any inherited MISSIONS_ setting is dropped so only the given credentials count."""
        env = {k: v for k, v in os.environ.items() if not k.startswith('MISSIONS_')}
        if overrides:
            env.update(MISSIONS_IMAGE=cls.image, MISSIONS_CONTAINER_NAME=cls.container, MISSIONS_HOST_PORT=str(cls.port))
        env.update(credentials)
        return env

    @classmethod
    def compose(cls, args, env, timeout=120):
        result = subprocess.run(['docker', 'compose', '-f', str(COMPOSE_FILE), '-p', cls.project] + args, cwd=str(COMPONENT), env=env,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
        result.stdout, result.stderr = result.stdout.decode('utf-8', 'replace'), result.stderr.decode('utf-8', 'replace')
        return result

    def config(self, credentials, overrides=True):
        result = self.compose(['config', '--format', 'json'], self.env(credentials, overrides))
        self.assertEqual(result.returncode, 0, result.stderr[-1500:])
        return json.loads(result.stdout)

    # --- acceptance ---------------------------------------------------------------------------------------

    def test_01_committed_files_pin_the_bases_by_digest_and_are_the_one_copy(self):
        dockerfile = (COMPONENT / 'Dockerfile').read_text(encoding='utf-8')
        self.assertEqual(re.findall(r'(?m)^FROM (\S+)', dockerfile), list(BASES))
        for base in BASES:
            self.assertRegex(base, r'@sha256:[0-9a-f]{64}$')
        self.assertRegex(dockerfile, r'(?m)^USER 10001:10001$')
        self.assertRegex(dockerfile, r'(?m)^ENV MISSIONS_BIND_HOST=0\.0\.0\.0 MISSIONS_PORT=8083$')
        self.assertRegex(dockerfile, r'(?m)^EXPOSE 8083$')
        # The service gates build from this Dockerfile: the harness keeps no copy of it or of the bases.
        for name in ('DOCKERFILE', 'BUILD_IMAGE', 'RUN_IMAGE'):
            self.assertFalse(hasattr(harness, name), name)
        ignore = (COMPONENT / '.dockerignore').read_text(encoding='utf-8').split('\n')
        self.assertEqual(ignore[0], '*', 'the build context excludes everything but what it names')
        self.assertEqual(ignore[1:], ['!pom.xml', '!contracts/missions-v1.1.xsd', '!fixtures/valid', '!src', ''])
        compose = COMPOSE_FILE.read_text(encoding='utf-8')
        for key in CREDENTIALS:
            self.assertRegex(compose, r'(?m)^      ' + key + r': \$\{' + key + r':\?[^}]+\}$')

    def test_02_compose_is_valid_and_fails_closed_without_credentials(self):
        configuration = self.config(DUMMY)
        self.assertEqual(list(configuration['services']), ['missions'])
        service = configuration['services']['missions']
        self.assertEqual([(p['host_ip'], str(p['published']), p['target'], p['protocol']) for p in service['ports']],
                         [('127.0.0.1', str(self.port), 8083, 'tcp')])
        self.assertEqual((service['environment']['MISSIONS_PORT'], service['environment']['MISSIONS_BIND_HOST']), ('8083', '0.0.0.0'))
        self.assertEqual(service['environment']['MISSIONS_DB_SCHEMA'], 'MISSIONS_LAB')
        self.assertEqual(sorted(service['networks']), ['default', 'oracle'])
        # The Oracle network is the existing one, external to the project; the other is an ordinary bridge.
        self.assertEqual(configuration['networks']['oracle']['name'], operator.ENV['network'])
        self.assertIs(configuration['networks']['oracle']['external'], True)
        self.assertFalse(configuration['networks']['default'].get('internal'))
        # Without overrides the file keeps its pinned defaults: the documented container name and the loopback port 8083.
        service = self.config(DUMMY, overrides=False)['services']['missions']
        self.assertEqual(service['container_name'], operator.ENV['serviceContainer'])
        self.assertEqual([(p['host_ip'], str(p['published'])) for p in service['ports']], [('127.0.0.1', '8083')])
        for key in CREDENTIALS:
            for value in (None, ''):
                with self.subTest(missing=key, value=value):
                    credentials = {k: v for k, v in DUMMY.items() if k != key}
                    if value is not None:
                        credentials[key] = value
                    result = self.compose(['config', '--quiet'], self.env(credentials))
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn(key, result.stderr)

    def test_03_image_builds_from_the_committed_files_and_runs_non_root(self):
        started = time.monotonic()
        result = self.compose(['build'], self.env(DUMMY), timeout=1800)
        self.assertEqual(result.returncode, 0, 'Image build (Maven verify on JDK 17) failed:\n' + (result.stderr + result.stdout)[-6000:])
        tests = re.findall(r'Tests run: (\d+), Failures: (\d+), Errors: (\d+), Skipped: (\d+)\n?', result.stdout + result.stderr)
        print('missions-packaging: image ' + self.image + ' built; Maven test summaries: ' + str(tests[-1:] or 'not echoed'), flush=True)
        phase('image-build-with-maven-verify', started)
        config = json.loads(harness.docker(['image', 'inspect', self.image]))[0]['Config']
        self.assertEqual(config['User'], '10001:10001')
        self.assertIn('8083/tcp', config['ExposedPorts'])
        self.assertIn('MISSIONS_PORT=8083', config['Env'])
        self.assertIn('MISSIONS_BIND_HOST=0.0.0.0', config['Env'])
        self.assertEqual(harness.docker(['run', '--rm', '--entrypoint', 'id', self.image, '-u']), '10001')
        self.assertEqual(harness.docker(['run', '--rm', '--entrypoint', 'id', self.image, '-g']), '10001')

    def test_04_compose_starts_the_service_on_the_oracle_network_and_it_answers(self):
        started = time.monotonic()
        credentials = {'MISSIONS_JDBC_URL': 'jdbc:oracle:thin:@//' + operator.ENV['container'] + ':1521/' + operator.ENV['pdb'],
                       'MISSIONS_DB_USER': self.login, 'MISSIONS_DB_PASSWORD': self.password, 'MISSIONS_DB_SCHEMA': self.schema}
        env = self.env(credentials)
        result = self.compose(['up', '--detach', '--no-build'], env, timeout=300)
        self.assertEqual(result.returncode, 0, result.stderr[-3000:])
        base = ('127.0.0.1', self.port)
        deadline = time.monotonic() + 90
        while True:
            try:
                response = harness.ServiceCase.get(base, '/missions')
                if response.status == 200:
                    break
            except OSError:
                pass
            if time.monotonic() >= deadline:
                self.fail('Service failed readiness: ' + self.compose(['logs', '--tail', '60'], env).stdout[-3000:])
            time.sleep(.25)
        phase('compose-up-until-ready', started)
        document = etree.fromstring(response.body)
        self.assertTrue(harness.SCHEMA.validate(document), harness.SCHEMA.error_log)
        self.assertEqual((document.tag, document.findtext(q('totalCount'))), (q('missionList'), '31'))
        inspected = json.loads(harness.docker(['inspect', self.container]))[0]
        self.assertTrue(inspected['State']['Running'])
        self.assertEqual(inspected['Config']['User'], '10001:10001')
        self.assertEqual(inspected['HostConfig']['PortBindings'], {'8083/tcp': [{'HostIp': '127.0.0.1', 'HostPort': str(self.port)}]})
        self.assertEqual(set(inspected['NetworkSettings']['Networks']), {operator.ENV['network'], self.project + '_default'})
        # Taking the project down removes only what it created: the Oracle container and its network stay as reviewed.
        result = self.compose(['down', '--volumes', '--remove-orphans'], env, timeout=180)
        self.assertEqual(result.returncode, 0, result.stderr[-1500:])
        self.assertNotIn(self.container, harness.docker(['ps', '--all', '--format', '{{.Names}}']).splitlines())
        operator.db_guard()
        operator.service_stopped()

    def test_05_bad_configuration_exits_non_zero_with_the_configs_message(self):
        cases = (('MISSIONS_PORT', '70000', 'MISSIONS_PORT must be 1..65535'),
                 ('MISSIONS_BIND_HOST', '10.1.2.3', 'MISSIONS_BIND_HOST must be 127.0.0.1 or 0.0.0.0'),
                 ('MISSIONS_DB_SCHEMA', 'not a schema', 'MISSIONS_DB_SCHEMA is not a plain Oracle identifier'))
        for key, value, message in cases:
            with self.subTest(setting=key):
                started = time.monotonic()
                result = self.compose(['run', '--rm', '--no-deps', '-T', '-e', key + '=' + value, 'missions'], self.env(DUMMY), timeout=120)
                self.assertNotEqual(result.returncode, 0, 'a bad ' + key + ' must stop the container')
                self.assertIn(message, result.stdout + result.stderr)
                phase('bad-' + key.lower(), started)


if __name__ == '__main__':
    unittest.main()
