"""Assets packaging acceptance: the committed Dockerfile, .dockerignore, compose.yaml and start.sh, through Docker Compose.

The HTTP matrix is the service gate's own: the classes of test_service_gate (the contract examples, the dataset expected
outcomes, the parent chains, the filters, the paging, the order and the 405 cases) are subclassed here and run against the
service that compose publishes. The database-rule checks need an administrative connection that this stack deliberately
does not publish, so they stay in the service gate. This gate checks what only the packaging owns: both bases pinned by
digest, a compose file that fails closed without credentials, an image that builds from the committed files, holds only
what the service needs and runs as a non-root user, the loopback publication, the database published nowhere, the CPU and
memory limits, the start script's port rule, a second start that duplicates nothing, and a stack that comes down cleanly.

Everything is disposable and uniquely named per run: one compose project, one image tag, container names, an ephemeral
loopback port and random credentials from the process environment. Missing Docker or Compose is a failure, never a skip.
"""
from pathlib import Path
import hashlib
import json
import os
import re
import secrets
import socket
import subprocess
import sys
import time
import unittest

HERE = Path(__file__).resolve().parent
COMPONENT = HERE.parents[2]
sys.path.insert(0, str(COMPONENT / 'validation/runtime/service'))
import gate_support as support  # noqa: E402
import test_service_gate as service_gate  # noqa: E402

COMPOSE_FILE = COMPONENT / 'compose.yaml'
START = COMPONENT / 'start.sh'
PYTHON_BASE = 'python:3.13-slim-bookworm@sha256:a1165e272e578941b84abc79e4ab38a0305cd12803a5c4247979ac7655f4d641'
POSTGRES_BASE = support.IMAGE
CREDENTIALS = ('ASSETS_DB_ADMIN_PASSWORD', 'ASSETS_DB_SERVICE_PASSWORD')
IMAGE_FILES = ['contracts/assets-v1.1.openapi.json', 'datasets/releases/1.1/assets.json', 'datasets/releases/1.1/curation.json',
               'datasets/releases/1.1/generate.py', 'datasets/releases/1.1/manifest.json', 'datasets/releases/1.1/provenance.json',
               'schema/schema.sql', 'service/assets_logic.py', 'service/assets_service.py', 'service/assets_store.py',
               'service/bootstrap.py', 'service/load_release.py', 'service/requirements.txt']
TIMINGS = {}
STATE = {}


def phase(name, started):
    TIMINGS[name] = round(time.monotonic() - started, 1)
    print('assets-packaging timing: ' + name + ' ' + str(TIMINGS[name]) + 's', flush=True)


def free_port():
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        return probe.getsockname()[1]


def bash():
    """The bash of Git for Windows when there is one (the WSL launcher on the PATH fails on every call)."""
    for candidate in ('bash', r'C:\Program Files\Git\bin\bash.exe'):
        try:
            if subprocess.run([candidate, '-c', 'echo ok'], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=30).stdout.strip() == b'ok':
                return candidate
        except (OSError, subprocess.TimeoutExpired):
            continue
    raise RuntimeError('No working bash was found; the packaging gate runs from Git Bash')


def project_env(overrides=True, credentials=True):
    env = {k: v for k, v in os.environ.items() if not k.startswith(('ASSETS_', 'PG', 'COMPOSE_'))}
    if overrides:
        env.update(COMPOSE_PROJECT_NAME=STATE['project'], ASSETS_IMAGE=STATE['image'], ASSETS_CONTAINER_NAME=STATE['service'],
                   ASSETS_DB_CONTAINER_NAME=STATE['database'], ASSETS_HOST_PORT=str(STATE['port']))
    if credentials:
        env.update(ASSETS_DB_ADMIN_PASSWORD=STATE['admin_password'], ASSETS_DB_SERVICE_PASSWORD=STATE['service_password'])
    return env


def run(argv, env=None, timeout=300, cwd=None):
    result = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout, env=env, cwd=cwd)
    result.stdout, result.stderr = result.stdout.decode('utf-8', 'replace'), result.stderr.decode('utf-8', 'replace')
    return result


def compose(args, env=None, timeout=300):
    return run(['docker', 'compose', '-f', str(COMPOSE_FILE)] + args, env if env is not None else project_env(), timeout)


def start_script(command, env=None, dry_run=False, timeout=600):
    return run([bash(), str(START)] + (['--dry-run'] if dry_run else []) + [command], env if env is not None else project_env(), timeout)


def setUpModule():
    token = secrets.token_hex(6)
    STATE.update(token=token, project='assets-pkg-' + token, image='assets-packaging-validation:' + token,
                 service='assets-pkg-svc-' + token, database='assets-pkg-db-' + token, port=free_port(),
                 admin_password=secrets.token_hex(16), service_password=secrets.token_hex(16), started=time.monotonic())
    # The reused service-gate classes talk to the service through its module state.
    service_gate.STATE['port'] = STATE['port']
    support.docker(['version', '--format', '{{.Server.Version}}'])


def tearDownModule():
    problems = []
    result = compose(['down', '--volumes', '--remove-orphans'], timeout=240)
    if result.returncode:
        problems.append('compose down: ' + result.stderr[-1500:])
    result = run(['docker', 'rmi', '--force', STATE['image']])
    if result.returncode and 'No such image' not in result.stderr:
        problems.append('image: ' + result.stderr[-500:])
    TIMINGS['module total'] = round(time.monotonic() - STATE['started'], 1)
    print('assets-packaging timings (seconds): ' + json.dumps(TIMINGS), flush=True)
    print('assets-packaging: pinned ' + PYTHON_BASE + ' and ' + POSTGRES_BASE + ' (resolved 2026-10-15), Python ' + sys.version.split()[0], flush=True)
    if problems:
        raise RuntimeError('Cleanup of owned resources failed: ' + '; '.join(problems))


def inspect(name):
    return json.loads(support.docker(['inspect', name]))[0]


def psql(sql_text):
    """A statement run by the administrator inside the database container, over its socket (no password on any command line)."""
    return support.docker(['exec', STATE['database'], 'psql', '-U', 'postgres', '-d', 'assets', '-v', 'ON_ERROR_STOP=1', '-At', '-c', sql_text])


def data_dump():
    result = support.docker(['exec', STATE['database'], 'pg_dump', '-U', 'postgres', '--no-owner', '--no-privileges', '--data-only', 'assets'])
    return '\n'.join(line for line in result.splitlines() if not line.startswith(('\\restrict', '\\unrestrict')))


class PackagingAcceptance(unittest.TestCase):
    def test_01_committed_files_pin_both_bases_by_digest(self):
        dockerfile = (COMPONENT / 'Dockerfile').read_text(encoding='utf-8')
        self.assertEqual(re.findall(r'(?m)^FROM (\S+)', dockerfile), [PYTHON_BASE])
        self.assertRegex(dockerfile, r'(?m)^USER 10001:10001$')
        self.assertRegex(dockerfile, r'(?m)^EXPOSE 8084$')
        self.assertRegex(dockerfile, r'(?m)^ENV ASSETS_HOST=0\.0\.0\.0 ASSETS_PORT=8084$')
        self.assertIn('2026-10-15', dockerfile)
        ignore = (COMPONENT / '.dockerignore').read_text(encoding='utf-8').split('\n')
        self.assertEqual(ignore[0], '*', 'the build context excludes everything but what it names')
        self.assertEqual(ignore[1:], ['!service/*.py', '!service/requirements.txt', '!schema/schema.sql',
                                      '!contracts/assets-v1.1.openapi.json', '!datasets/releases/1.1', ''])
        text = COMPOSE_FILE.read_text(encoding='utf-8')
        self.assertIn('postgres:17-bookworm@sha256:' + POSTGRES_BASE.rsplit('sha256:', 1)[1], text)
        for key in CREDENTIALS:
            self.assertRegex(text, r'(?m)^      [A-Z_]+: \$\{' + key + r':\?[^}]+\}$')
        readme = (COMPONENT / 'README.md').read_text(encoding='utf-8')
        for digest in (PYTHON_BASE, POSTGRES_BASE):
            self.assertIn(digest.rsplit('sha256:', 1)[1], readme, 'the README records the pinned digests')
        self.assertIn('2026-10-15', readme)
        # No credential value lives in a committed file: the example holds placeholders only.
        example = (COMPONENT / '.env.example').read_text(encoding='utf-8')
        self.assertEqual(sorted(re.findall(r'(?m)^([A-Z_]+)=', example)), sorted(CREDENTIALS))
        self.assertTrue(all('change-me' in line for line in example.splitlines() if line.startswith('ASSETS_DB_')))

    def test_02_compose_is_valid_fails_closed_and_publishes_only_the_service_on_loopback(self):
        result = compose(['config', '--format', 'json'])
        self.assertEqual(result.returncode, 0, result.stderr[-1500:])
        config = json.loads(result.stdout)
        self.assertEqual(sorted(config['services']), ['assets', 'bootstrap', 'database'])
        assets, database, bootstrap = config['services']['assets'], config['services']['database'], config['services']['bootstrap']
        self.assertEqual([(p['host_ip'], str(p['published']), p['target']) for p in assets['ports']], [('127.0.0.1', str(STATE['port']), 8084)])
        self.assertNotIn('ports', database, 'the database is published nowhere')
        self.assertNotIn('ports', bootstrap)
        # The service holds the read-only login only; the administrative password goes to the database and the bootstrap.
        self.assertEqual(assets['environment']['PGUSER'], 'assets_service')
        self.assertNotIn(STATE['admin_password'], json.dumps(assets))
        self.assertEqual(bootstrap['environment']['PGUSER'], 'postgres')
        # Limits, healthchecks, ordering and the data volume.
        for name, cpus, memory in (('database', 1.0, 512 * 2 ** 20), ('bootstrap', 0.5, 256 * 2 ** 20), ('assets', 0.5, 256 * 2 ** 20)):
            service = config['services'][name]
            self.assertEqual((float(service['cpus']), int(service['mem_limit']), int(service['memswap_limit'])), (cpus, memory, memory), name)
        self.assertIn('healthcheck', database)
        self.assertIn('healthcheck', assets)
        self.assertEqual(bootstrap['depends_on']['database']['condition'], 'service_healthy')
        self.assertEqual(assets['depends_on']['bootstrap']['condition'], 'service_completed_successfully')
        self.assertEqual(list(config['volumes']), ['assets-pgdata'])
        # Without overrides the file keeps its documented defaults.
        defaults = json.loads(compose(['config', '--format', 'json'], project_env(overrides=False)).stdout)['services']
        self.assertEqual((defaults['assets']['container_name'], defaults['database']['container_name']),
                         ('starfleet-assets-service', 'starfleet-assets-database'))
        self.assertEqual([(p['host_ip'], str(p['published'])) for p in defaults['assets']['ports']], [('127.0.0.1', '8084')])
        for key in CREDENTIALS:
            for value in (None, ''):
                with self.subTest(missing=key, value=value):
                    env = project_env()
                    env.pop(key)
                    if value is not None:
                        env[key] = value
                    result = compose(['config', '--quiet'], env)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn(key, result.stderr)

    def test_03_image_builds_from_the_committed_files_and_holds_only_what_the_service_needs(self):
        started = time.monotonic()
        result = compose(['build'], timeout=1800)
        self.assertEqual(result.returncode, 0, 'Image build failed:\n' + (result.stderr + result.stdout)[-6000:])
        phase('image-build', started)
        config = inspect(STATE['image'])['Config']
        self.assertEqual(config['User'], '10001:10001')
        self.assertIn('8084/tcp', config['ExposedPorts'])
        self.assertEqual(support.docker(['run', '--rm', '--entrypoint', 'id', STATE['image'], '-u']), '10001')
        self.assertEqual(support.docker(['run', '--rm', '--entrypoint', 'id', STATE['image'], '-g']), '10001')
        listing = support.docker(['run', '--rm', '--entrypoint', 'find', STATE['image'], '/app', '-type', 'f']).splitlines()
        self.assertEqual(sorted(p[len('/app/'):] for p in listing), IMAGE_FILES, 'no tests, no credentials, nothing else')
        versions = support.docker(['run', '--rm', '--entrypoint', 'python', STATE['image'], '-c',
                                   'import sys, psycopg; print(sys.version.split()[0], psycopg.__version__)']).split()
        self.assertTrue(versions[0].startswith('3.13.'), versions)
        pinned = re.search(r'(?m)^psycopg==(\S+)$', (COMPONENT / 'service/requirements.txt').read_text(encoding='utf-8')).group(1)
        self.assertEqual(versions[1], pinned)

    def test_04_the_start_script_refuses_a_taken_port_and_starts_on_a_free_one(self):
        # A disposable listener on the very port, and the script refuses with one clear line and creates nothing.
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0))
            listener.listen(64)
            env = project_env()
            env['ASSETS_HOST_PORT'] = str(listener.getsockname()[1])
            refused = start_script('start', env)
            self.assertEqual(refused.returncode, 1, refused.stdout + refused.stderr)
            self.assertEqual(len(refused.stderr.strip().splitlines()), 1)
            self.assertIn('already in use', refused.stderr)
            dry = start_script('start', env, dry_run=True)
            self.assertEqual(dry.returncode, 1)
            self.assertNotIn('would run', dry.stdout)
        existing = support.docker(['ps', '--all', '--filter', 'label=com.docker.compose.project=' + STATE['project'], '--format', '{{.Names}}'])
        self.assertEqual(existing, '', 'a refused start creates nothing')
        free = start_script('start', dry_run=True)
        self.assertEqual(free.returncode, 0, free.stderr)
        self.assertIn('up -d --wait', free.stdout)
        started = time.monotonic()
        result = start_script('start')
        self.assertEqual(result.returncode, 0, 'start failed:\n' + (result.stderr + result.stdout)[-4000:])
        phase('start-script-up-to-healthy', started)
        # The same port is now taken, by this stack: the script refuses a second copy.
        again = start_script('start')
        self.assertEqual(again.returncode, 1)
        self.assertIn('already in use', again.stderr)

    def test_05_the_stack_is_healthy_non_root_limited_and_the_database_is_not_published(self):
        states = {item['Service']: item for item in json.loads('[' + ','.join(
            compose(['ps', '--all', '--format', 'json']).stdout.strip().splitlines()) + ']')}
        self.assertEqual(states['database']['Health'], 'healthy')
        self.assertEqual(states['assets']['Health'], 'healthy')
        self.assertEqual((states['bootstrap']['State'], states['bootstrap']['ExitCode']), ('exited', 0))
        service, database = inspect(STATE['service']), inspect(STATE['database'])
        self.assertTrue(service['State']['Running'])
        self.assertEqual(service['Config']['User'], '10001:10001')
        self.assertEqual(support.docker(['exec', STATE['service'], 'id', '-u']), '10001')
        self.assertEqual(service['HostConfig']['PortBindings'], {'8084/tcp': [{'HostIp': '127.0.0.1', 'HostPort': str(STATE['port'])}]})
        # The database has no host binding at all, and no port of the host leads to it.
        self.assertEqual(database['HostConfig']['PortBindings'], {})
        self.assertTrue(all(value is None for value in database['NetworkSettings']['Ports'].values()), database['NetworkSettings']['Ports'])
        self.assertEqual(support.docker(['port', STATE['database']]), '')
        # The limits are applied, as docker reports them.
        self.assertEqual((database['HostConfig']['NanoCpus'], database['HostConfig']['Memory'], database['HostConfig']['MemorySwap']),
                         (10 ** 9, 512 * 2 ** 20, 512 * 2 ** 20))
        self.assertEqual((service['HostConfig']['NanoCpus'], service['HostConfig']['Memory'], service['HostConfig']['MemorySwap']),
                         (5 * 10 ** 8, 256 * 2 ** 20, 256 * 2 ** 20))
        self.assertTrue(service['HostConfig']['ReadonlyRootfs'])
        self.assertTrue(psql('SHOW server_version').startswith('17.'))
        self.assertEqual(psql('SELECT count(*) FROM assets'), '32')
        self.assertIn('assets_reader', psql("SELECT string_agg(b.rolname, ',') FROM pg_auth_members m JOIN pg_roles r ON r.oid = m.member "
                                            "JOIN pg_roles b ON b.oid = m.roleid WHERE r.rolname = 'assets_service'"))
        self.assertIn('default_transaction_read_only=on', psql(
            "SELECT s.setconfig::text FROM pg_db_role_setting s JOIN pg_roles r ON r.oid = s.setrole WHERE r.rolname = 'assets_service'"))

    def test_06_second_start_duplicates_nothing_and_stop_removes_nothing(self):
        before = hashlib.sha256(data_dump().encode('utf-8')).hexdigest()
        self.assertEqual(support.docker(['volume', 'ls', '--quiet', '--filter', 'name=' + STATE['project'] + '_assets-pgdata']), STATE['project'] + '_assets-pgdata')
        stopped = start_script('stop', project_env(credentials=False))
        self.assertEqual(stopped.returncode, 0, stopped.stderr[-2000:])
        names = support.docker(['ps', '--all', '--filter', 'label=com.docker.compose.project=' + STATE['project'], '--format', '{{.Names}}']).splitlines()
        self.assertIn(STATE['database'], names, 'stop keeps the containers')
        self.assertIn(STATE['service'], names)
        self.assertEqual(support.docker(['inspect', '--format', '{{.State.Running}}', STATE['service']]), 'false')
        self.assertEqual(support.docker(['volume', 'ls', '--quiet', '--filter', 'name=' + STATE['project'] + '_assets-pgdata']), STATE['project'] + '_assets-pgdata')
        started = time.monotonic()
        result = start_script('start')
        self.assertEqual(result.returncode, 0, result.stderr[-3000:] + result.stdout[-1000:])
        phase('second-start-up-to-healthy', started)
        logs = compose(['logs', '--no-log-prefix', 'bootstrap']).stdout
        # The container keeps its log across a stop: the first start loaded the release, the second only verified it.
        self.assertEqual(re.findall(r'(?m)^BOOTSTRAP (\w+) 32 assets', logs), ['loaded', 'verified'], logs)
        self.assertEqual(psql('SELECT count(*) FROM assets'), '32')
        self.assertEqual(hashlib.sha256(data_dump().encode('utf-8')).hexdigest(), before, 'the rows are the same after the second start')
        # Running the bootstrap once more on its own changes nothing either.
        again = compose(['run', '--rm', '--no-deps', '-T', 'bootstrap'])
        self.assertEqual(again.returncode, 0, again.stderr[-2000:])
        self.assertIn('BOOTSTRAP verified 32 assets', again.stdout)
        self.assertEqual(hashlib.sha256(data_dump().encode('utf-8')).hexdigest(), before)

    def test_07_a_database_that_differs_from_the_release_is_refused_not_repaired(self):
        psql("UPDATE assets SET status = 'MISSING' WHERE asset_id = 'AST-0004'")
        try:
            result = compose(['run', '--rm', '--no-deps', '-T', 'bootstrap'])
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('differs from the release', result.stderr + result.stdout)
            self.assertEqual(psql("SELECT status FROM assets WHERE asset_id = 'AST-0004'"), 'MISSING', 'the bootstrap changes no data')
        finally:
            psql("UPDATE assets SET status = 'ACTIVE' WHERE asset_id = 'AST-0004'")
        self.assertEqual(compose(['run', '--rm', '--no-deps', '-T', 'bootstrap']).returncode, 0)


# The service gate's HTTP checks, against the service that compose publishes. unittest runs the classes of a module in
# the order of their names: PackagingAcceptance starts the stack, the ZHttp classes use it, ZZDown takes it down.
class ZHttpExpectedOutcomes(service_gate.ExpectedOutcomes):
    pass


class ZHttpContractExamples(service_gate.ContractExamples):
    pass


class ZHttpListing(service_gate.Listing):
    pass


class ZHttpAssetLookup(service_gate.AssetLookup):
    test_06_unicode_survives_the_trip = None  # inserts a row as the administrator, which this stack does not publish


class ZHttpHttpMechanics(service_gate.HttpMechanics):
    test_02_a_write_with_a_body_is_refused_and_changes_nothing = None  # fingerprints the table as the administrator


class ZZDown(unittest.TestCase):
    def test_08_the_stack_comes_down_cleanly(self):
        result = compose(['down', '--volumes', '--remove-orphans'], timeout=240)
        self.assertEqual(result.returncode, 0, result.stderr[-2000:])
        label = 'label=com.docker.compose.project=' + STATE['project']
        self.assertEqual(support.docker(['ps', '--all', '--filter', label, '--format', '{{.Names}}']), '')
        self.assertEqual(support.docker(['volume', 'ls', '--quiet', '--filter', label]), '')
        self.assertEqual(support.docker(['network', 'ls', '--quiet', '--filter', label]), '')


if __name__ == '__main__':
    unittest.main()
