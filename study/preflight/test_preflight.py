"""Offline tests of the study-2 preflight: argument handling, the guards and refusals, the shape of each step's record and the redaction
of credentials. A fake machine stands in for Docker, SQLPlus, HTTP and the launch kit; nothing is started, stopped or inspected, no
database is read and no network is used."""
import ast
import json
import re
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import preflight  # noqa: E402

ROOT = preflight.ROOT
ORACLE = preflight.oracle_environment()['container']
BASE = datetime(2026, 10, 27, 20, 0, tzinfo=timezone.utc)
GIB = 1024 ** 3


class FakeMachine:
    """Answers from functions, runs every guard of the real machine first, and keeps a clock that moves only when asked."""

    def __init__(self, docker=None, sql=None, http=None, launch=None):
        self.t, self.calls = 0.0, []
        self.docker_answer = docker or (lambda m, argv: (1, '', 'no such object'))
        self.sql_answer = sql or (lambda m, select: [])
        self.http_answer = http or (lambda m, method, url, headers, body: (404, {}, b''))
        self.launch_hook = launch or (lambda m, argv: 0)

    def docker(self, argv, input_text=None, timeout=120):
        argv = [str(a) for a in argv]
        preflight.assert_docker_read(argv, ORACLE)
        self.calls.append(('docker', argv))
        return self.docker_answer(self, argv)

    def sql(self, select, pdb):
        preflight.sql_script(select, pdb)
        self.calls.append(('sql', select))
        answer = self.sql_answer(self, select)
        if isinstance(answer, Exception):
            raise answer
        return answer

    def http(self, method, url, headers=None, body=None, timeout=30):
        preflight.assert_http(method, url, body)
        self.calls.append(('http', method, url))
        self.t += 0.5
        status, seen, data = self.http_answer(self, method, url, headers or {}, body)
        return status, seen, data, 0.05

    def host_free_bytes(self):
        return 10 * GIB

    def vmmem_bytes(self):
        return 6 * GIB

    def disk_free_bytes(self, path):
        return 50 * GIB

    def launch(self, argv):
        self.calls.append(('launch', [str(a) for a in argv]))
        return self.launch_hook(self, argv)

    def provenance_docker(self, provenance):
        return self.provenance_cli

    def now(self):
        return self.t

    def wall(self):
        return BASE + timedelta(seconds=self.t)

    def sleep(self, seconds):
        self.t += seconds


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.results = Path(self.tmp.name) / 'results'

    def tearDown(self):
        self.tmp.cleanup()

    def run_main(self, argv, machine):
        lines = []
        code = preflight.main(argv + ['--results', str(self.results)], machine=machine, out=lines.append)
        return code, lines

    def records(self, pattern='*.json'):
        return [json.loads(p.read_text(encoding='utf-8')) for p in sorted(self.results.glob(pattern))]

    def check(self, record, check_id):
        return next(c for c in record['checks'] if c['id'] == check_id)


def state(name, restarts=0, oom=False, status='running', started='2026-10-27T20:00:00.123456789Z'):
    return json.dumps({'name': '/' + name, 'status': status, 'startedAt': started, 'oomKilled': oom, 'restarts': restarts, 'image': 'x'})


# --------------------------------------------------------------------------------------------------------------- the guards
class GuardTests(unittest.TestCase):
    def test_docker_allows_only_the_read_only_forms(self):
        allowed = [
            ['image', 'inspect', '--format', '{"id":{{json .Id}}}', 'some:image'],
            ['inspect', '--format', preflight.STATE_TEMPLATE, 'a', 'b'],
            ['inspect', '--format', preflight.ENV_USER_TEMPLATE, preflight.SERVICE_CONTAINER],
            ['stats', '--no-stream', '--format', '{{json .}}', 'a'],
            ['system', 'df', '--format', '{{json .}}'],
            ['ps', '--filter', 'label=com.docker.compose.project=x', '--format', '{{.Names}}'],
            ['exec', '--user', 'oracle', '-i', '-e', 'NLS_LANG=.AL32UTF8', ORACLE, 'sqlplus', '-L', '-s', '/ as sysdba'],
        ]
        for argv in allowed:
            preflight.assert_docker_read(argv, ORACLE)
        refused = [
            ['start', ORACLE], ['stop', ORACLE], ['rm', '-f', ORACLE], ['run', 'image'], ['compose', 'up'], ['pull', 'image'],
            ['exec', ORACLE, 'sh'], ['exec', '--user', 'oracle', '-i', 'other', 'sqlplus', '-L', '-s', '/ as sysdba'],
            ['inspect', '--format', '{{json .Config.Env}}', 'x'], ['inspect', 'x'], ['inspect', '--format', '{{.Name}}', '--size', 'x'],
            ['ps', '--format', '{{json .Config.Env}}'], ['ps', '--latest', '--format', '{{.Names}}'],
            ['network', 'rm', 'x'], ['image', 'rm', 'x'], ['volume', 'ls'],
        ]
        for argv in refused:
            with self.assertRaises(preflight.Refused, msg=argv):
                preflight.assert_docker_read(argv, ORACLE)

    def test_sql_is_one_select_in_a_read_only_transaction(self):
        script = preflight.sql_script('SELECT COUNT(*) FROM MISSIONS_LAB.MISSIONS', 'XEPDB1')
        self.assertIn('SET TRANSACTION READ ONLY;\nSELECT COUNT(*) FROM MISSIONS_LAB.MISSIONS;\nROLLBACK;', script)
        self.assertIn('ALTER SESSION SET CONTAINER = XEPDB1;', script)
        for statement in ('INSERT INTO missions VALUES (1)', 'UPDATE missions SET title = 1', 'DELETE FROM missions',
                          'SELECT 1 FROM dual; DROP TABLE missions', 'SELECT * FROM missions FOR UPDATE', 'GRANT SELECT ON x TO y',
                          'BEGIN NULL; END', 'SELECT missions_clock_tick() FROM dual WHERE 1 = 1 AND EXECUTE', 'CREATE USER x',
                          'ALTER USER x IDENTIFIED BY y', 'TRUNCATE TABLE missions', 'MERGE INTO missions', 'host rm', 'COMMIT'):
            with self.assertRaises(preflight.Refused, msg=statement):
                preflight.sql_script(statement, 'XEPDB1')

    def test_graphql_is_queries_only(self):
        for query in (preflight.FULL_PAGE, '{ __typename }', 'query Name { missions { missionId } }'):
            preflight.assert_query(query)
        for query in ('mutation { x }', 'subscription { y }', 'mutation M($a: Int) { x }', '{ a } mutation { b }', 'nonsense'):
            with self.assertRaises(preflight.Refused, msg=query):
                preflight.assert_query(query)

    def test_http_is_get_to_loopback_and_queries_to_the_routers(self):
        preflight.assert_http('GET', 'http://127.0.0.1:8083/missions')
        preflight.assert_http('POST', 'http://127.0.0.1:8170/', json.dumps({'query': '{ __typename }'}).encode('utf-8'))
        for method, url, body in (('GET', 'http://example.org/missions', None), ('GET', 'https://127.0.0.1:8083/', None),
                                  ('POST', 'http://127.0.0.1:8083/missions', b'<mission/>'), ('PUT', 'http://127.0.0.1:8083/missions/x', b''),
                                  ('DELETE', 'http://127.0.0.1:8083/missions/x', None), ('HEAD', 'http://127.0.0.1:8083/missions', None),
                                  ('POST', 'http://127.0.0.1:8170/', json.dumps({'query': 'mutation { x }'}).encode('utf-8')),
                                  ('POST', 'http://127.0.0.1:8170/', b'not json'), ('GET', 'http://127.0.0.1:8083/', b'body')):
            with self.assertRaises(preflight.Refused, msg=(method, url)):
                preflight.assert_http(method, url, body)

    def test_the_one_action_is_launch_service_stop_or_start(self):
        state_dir = Path(tempfile.gettempdir()) / 'state'
        args = type('A', (), {'scenario': 'gamma', 'missions': 'real'})()
        for action in ('stop', 'start'):
            preflight.assert_launch(preflight.launch_argv(action, 'assets', args, state_dir), 'gamma', 'real', state_dir)
        good = preflight.launch_argv('stop', 'assets', args, state_dir)
        for bad in (good[:4] + ['up'] + good[5:], good[:6] + ['delta'] + good[7:], good[:8] + ['simulated'] + good[9:],
                    good[:5] + ['oracle'] + good[6:], [good[0], '-B', 'other.py'] + good[3:]):
            with self.assertRaises(preflight.Refused):
                preflight.assert_launch(bad, 'gamma', 'real', state_dir)


class RedactionTests(unittest.TestCase):
    def test_credentials_are_masked_in_text(self):
        secret = 'Ms' + 'abc123' + '9'
        text = 'ORACLE_PWD=%s MISSIONS_DB_PASSWORD="%s two" api_key: %s jdbc://reader:%s@host/db CREATE USER R IDENTIFIED BY %s' % (
            secret, secret, secret, secret, secret)
        masked = preflight.redact_text(text)
        self.assertNotIn(secret, masked)
        self.assertIn('ORACLE_PWD=[MASKED]', masked)
        self.assertIn('IDENTIFIED BY [MASKED]', masked)
        self.assertIn('jdbc://[MASKED]@host/db', masked)

    def test_a_record_masks_secret_named_keys_and_scans_every_text(self):
        secret = 'hunter' + '22'
        record = preflight.redact({'db_password': secret, 'nested': [{'note': 'TOKEN=%s' % secret}], 'count': 3})
        self.assertNotIn(secret, json.dumps(record))
        self.assertEqual(record['count'], 3)

    def test_a_failed_sql_session_never_reports_a_credential(self):
        secret = 'Zz' + '987654'

        class Failing(preflight.Machine):
            def docker(self, argv, input_text=None, timeout=120):
                preflight.sql_script('SELECT 1 FROM dual', 'XEPDB1')
                return 1, 'ORA-01017: invalid username/password; ORACLE_PWD=%s' % secret, 'MISSIONS_DB_PASSWORD=%s' % secret

        with self.assertRaises(RuntimeError) as caught:
            Failing(ORACLE).sql('SELECT 1 FROM dual', 'XEPDB1')
        self.assertIn('ORA-01017', str(caught.exception))
        self.assertNotIn(secret, str(caught.exception))


# --------------------------------------------------------------------------------------------------------------- the command line
class CommandLineTests(Base):
    def test_without_run_a_step_prints_its_plan_and_does_nothing(self):
        for argv in (['inventory'], ['oracle'], ['data', '--login', 'reader'], ['service', '--target', 'real'],
                     ['stack', 'gamma', '--missions', 'real'],
                     ['outage', 'gamma', '--missions', 'real', '--state-dir', str(Path(self.tmp.name) / 'state')],
                     ['provenance', 'delta', '--config', str(Path(self.tmp.name) / 'config.json')]):
            machine = FakeMachine()
            code, lines = self.run_main(argv, machine)
            self.assertEqual(code, 0, argv)
            self.assertTrue(lines[0].startswith('preflight step'), lines)
            self.assertEqual(lines[-1], 'nothing was run: add --run to run this step')
            self.assertEqual(machine.calls, [], argv)
            self.assertFalse(self.results.exists(), argv)

    def test_the_results_folder_must_be_outside_the_repository(self):
        lines = []
        code = preflight.main(['inventory', '--run', '--results', str(ROOT / 'study' / 'results')], machine=FakeMachine(), out=lines.append)
        self.assertEqual(code, 1)
        self.assertFalse((ROOT / 'study' / 'results').exists())

    def test_usage_errors(self):
        for argv in (['nostep'], ['stack', 'zeta', '--missions', 'real'], ['stack', 'gamma', '--missions', 'stub'],
                     ['service', '--target', 'other'], ['data'], ['outage', 'gamma', '--missions', 'real']):
            with self.assertRaises(SystemExit, msg=argv):
                preflight.build_parser().parse_args(argv + ['--results', 'x'])

    def test_the_outage_state_folder_must_be_outside_the_repository(self):
        code, _ = self.run_main(['outage', 'gamma', '--missions', 'real', '--state-dir', str(ROOT / 'state')], FakeMachine())
        self.assertEqual(code, 1)

    def test_a_record_is_never_overwritten(self):
        record = {'stepNumber': 1, 'step': 'inventory', 'label': None}
        preflight.write_record(self.results, record, 'stamp')
        with self.assertRaises(preflight.Refused):
            preflight.write_record(self.results, record, 'stamp')


# --------------------------------------------------------------------------------------------------------------- step 1
def inventory_docker(m, argv):
    env = preflight.oracle_environment()
    if argv[:2] == ['image', 'inspect'] and argv[-1] == '%s@%s' % (env['image'], env['digest']):
        return 0, json.dumps({'id': 'sha256:' + 'a' * 64, 'repoDigests': ['%s@%s' % (env['image'].split(':')[0], env['digest'])],
                              'size': 9 * GIB}), ''
    if argv[:2] == ['image', 'inspect']:
        return 1, '', 'Error: No such image'
    if argv[:2] == ['system', 'df']:
        return 0, json.dumps({'Type': 'Images', 'Size': '20GB'}), ''
    return 1, '', ''


class InventoryTests(Base):
    def test_the_record_of_step_one(self):
        code, lines = self.run_main(['inventory', '--run'], FakeMachine(docker=inventory_docker))
        self.assertEqual(code, 4)  # the service image is absent
        record, = self.records('01-inventory-*.json')
        self.assertEqual((record['step'], record['stepNumber'], record['schema']), ('inventory', 1, 1))
        self.assertEqual(self.check(record, 'oracle-digest')['result'], 'pass')
        self.assertEqual(self.check(record, 'service-image')['result'], 'fail')
        self.assertEqual(self.check(record, 'disk-reserve')['result'], 'pass')
        limit = preflight.compose_limits(preflight.MISSIONS_COMPOSE.read_text(encoding='utf-8'))['mem_limit']
        self.assertEqual(self.check(record, 'memory-limit')['result'], 'pass' if limit == '768m' else 'fail')
        self.assertEqual(record['measurements']['oracleImage']['sizeGiB'], 9.0)
        self.assertTrue(any(c.startswith('docker image inspect') for c in record['commands']))

    def test_a_fresh_results_folder_is_measured_on_its_nearest_existing_parent(self):
        seen = []

        class Disk(FakeMachine):
            def disk_free_bytes(self, path):
                seen.append(Path(path))
                return preflight.shutil.disk_usage(path).free

        self.assertFalse(self.results.exists())
        code, _ = self.run_main(['inventory', '--run'], Disk(docker=inventory_docker))
        self.assertEqual(code, 4)  # the service image is absent; the disk check itself ran
        self.assertTrue(seen and seen[0].exists())
        record, = self.records('01-inventory-*.json')
        self.assertIn(self.check(record, 'disk-reserve')['result'], ('pass', 'fail'))

    def test_compose_limits_read_the_service_settings(self):
        text = 'services:\n  missions:\n    mem_limit: 768m\n    environment:\n      JAVA_TOOL_OPTIONS: "-XX:MaxRAMPercentage=75"\n'
        self.assertEqual(preflight.compose_limits(text), {'mem_limit': '768m', 'JAVA_TOOL_OPTIONS': '-XX:MaxRAMPercentage=75'})
        self.assertEqual(preflight.compose_limits('services:\n  missions:\n    image: x\n'), {'mem_limit': None, 'JAVA_TOOL_OPTIONS': None})


# --------------------------------------------------------------------------------------------------------------- step 2
def oracle_docker(m, argv):
    if argv[:3] == ['inspect', '--format', preflight.STATE_TEMPLATE]:
        return 0, state(ORACLE), ''
    if argv[:2] == ['stats', '--no-stream']:
        return 0, json.dumps({'Name': ORACLE, 'MemUsage': '2.5GiB / 4GiB'}), ''
    return 1, '', ''


def oracle_sql(m, select):
    if select == 'SELECT 1 FROM dual':
        m.polls = getattr(m, 'polls', 0) + 1
        return RuntimeError('ORA-12514') if m.polls < 3 else ['1']
    if 'v$sgainfo' in select:
        return ['Maximum SGA Size|1610612736', 'Free SGA Memory Available|0']
    if 'v$pgastat' in select:
        return ['total PGA allocated|200000000|bytes', 'aggregate PGA target parameter|536870912|bytes']
    return []


class OracleTests(Base):
    def test_readiness_peaks_and_memory_views(self):
        code, _ = self.run_main(['oracle', '--run', '--window', '10', '--interval', '5'], FakeMachine(docker=oracle_docker, sql=oracle_sql))
        self.assertEqual(code, 0)
        record, = self.records('02-oracle-*.json')
        readiness = record['measurements']['readiness']
        self.assertEqual((readiness['seconds'], readiness['polls'], readiness['upperBound']), (9.9, 3, False))
        self.assertEqual(self.check(record, 'oracle-ready')['result'], 'pass')
        self.assertEqual(self.check(record, 'oracle-no-oom')['result'], 'pass')
        peaks = record['measurements']['peaks']
        self.assertEqual(peaks['perContainerGiB'], {ORACLE: 2.5})
        self.assertEqual((peaks['hostFreeMinGiB'], peaks['vmmemMaxGiB']), (10.0, 6.0))
        self.assertEqual(record['measurements']['sga']['Maximum SGA Size'], 1610612736)
        self.assertEqual(record['measurements']['pga']['total PGA allocated'], {'value': 200000000, 'unit': 'bytes'})

    def test_a_stopped_oracle_is_refused(self):
        machine = FakeMachine(docker=lambda m, argv: (0, state(ORACLE, status='exited'), ''))
        code, _ = self.run_main(['oracle', '--run'], machine)
        self.assertEqual(code, 1)
        self.assertFalse(any(kind == 'sql' for kind, *_ in machine.calls))

    def test_an_oracle_that_never_answers_fails_the_threshold(self):
        machine = FakeMachine(docker=oracle_docker, sql=lambda m, s: RuntimeError('ORA-12514') if s == 'SELECT 1 FROM dual' else [])
        code, _ = self.run_main(['oracle', '--run', '--window', '5', '--interval', '60'], machine)
        self.assertEqual(code, 4)
        self.assertEqual(self.check(self.records('02-oracle-*.json')[0], 'oracle-ready')['result'], 'fail')

    def test_sizes_and_times(self):
        self.assertEqual(preflight.parse_size('1.5GiB'), int(1.5 * GIB))
        self.assertEqual(preflight.parse_size('512MiB'), 512 * 1024 ** 2)
        self.assertEqual(preflight.parse_size('120.5kB'), 120500)
        self.assertIsNone(preflight.parse_size('lots'))
        self.assertEqual(preflight.parse_started('2026-10-27T20:00:01.5Z'), BASE + timedelta(seconds=1.5))
        self.assertIsNone(preflight.parse_started('0001-01-01T00:00:00Z'))
        self.assertEqual(preflight.parse_tasklist('"vmmem","1234","Console","1","2,048 K"\n"VmmemWSL","9","Services","0","1,024 K"\n'), 3072 * 1024)


# --------------------------------------------------------------------------------------------------------------- step 3
def data_sql(privileges=None):
    expected = preflight.expected_release()
    tables = privileges if privileges is not None else ['MISSIONS_LAB.%s|SELECT' % t for t in preflight.TABLES]

    def answer(m, select):
        for table, count in expected['counts'].items():
            if select == 'SELECT COUNT(*) FROM MISSIONS_LAB.%s' % table:
                return [str(count)]
        if 'mission_clock' in select:
            return ['%s|%s|0|%s' % (expected['datasetVersion'], expected['releaseSha256'], expected['baseline'])]
        if 'MAX(current_change_id)' in select:
            return ['9907221|2368-12-23T10:47:00.000Z']
        if 'dba_sys_privs' in select:
            return ['CREATE SESSION']
        if 'dba_role_privs' in select:
            return []
        if 'dba_tab_privs' in select:
            return tables
        return []
    return answer


def data_docker(m, argv):
    if argv[:3] == ['inspect', '--format', preflight.ENV_USER_TEMPLATE]:
        return 0, 'STUDY_READER', ''
    return 1, '', ''


class DataTests(Base):
    def test_counts_hash_clock_and_a_read_only_login(self):
        code, _ = self.run_main(['data', '--run', '--login', 'study_reader'], FakeMachine(docker=data_docker, sql=data_sql()))
        self.assertEqual(code, 0)
        record, = self.records('03-data-*.json')
        for check_id in ('release-file', 'row-counts', 'dataset-hash', 'clock-unmoved', 'login-read-only', 'login-in-use'):
            self.assertEqual(self.check(record, check_id)['result'], 'pass', check_id)
        self.assertEqual(record['measurements']['counts']['MISSIONS'], 300)
        self.assertRegex(record['measurements']['fingerprintSha256'], r'^[0-9a-f]{64}$')

    def test_a_login_that_can_write_fails(self):
        privileges = ['MISSIONS_LAB.MISSIONS|SELECT', 'MISSIONS_LAB.MISSIONS|INSERT']
        code, _ = self.run_main(['data', '--run', '--login', 'study_reader'], FakeMachine(docker=data_docker, sql=data_sql(privileges)))
        self.assertEqual(code, 4)
        self.assertEqual(self.check(self.records('03-data-*.json')[0], 'login-read-only')['result'], 'fail')

    def test_read_only_rules(self):
        good = {'system': ['CREATE SESSION'], 'roles': [], 'tables': ['MISSIONS_LAB.MISSIONS|SELECT']}
        self.assertTrue(preflight.read_only(good, 'MISSIONS_LAB'))
        for change in ({'system': ['CREATE SESSION', 'CREATE TABLE']}, {'roles': ['RESOURCE']}, {'tables': []},
                       {'tables': ['MISSIONS_LAB.MISSIONS|UPDATE']}, {'tables': ['OTHER.T|SELECT']},
                       {'tables': ['MISSIONS_LAB.MISSIONS_CLOCK_TICK|EXECUTE']}):
            self.assertFalse(preflight.read_only(dict(good, **change), 'MISSIONS_LAB'), change)

    def test_the_clock_check_compares_with_an_earlier_record(self):
        machine = FakeMachine(docker=data_docker, sql=data_sql())
        self.run_main(['data', '--run', '--login', 'study_reader'], machine)
        first = sorted(self.results.glob('03-data-*.json'))[0]
        machine.t += 3600
        code, _ = self.run_main(['data', '--run', '--login', 'study_reader', '--compare-to', str(first)], machine)
        self.assertEqual(code, 0)
        second = self.records('03-data-*.json')[1]
        self.assertEqual(self.check(second, 'clock-check')['result'], 'pass')

    def test_an_unsafe_login_name_is_refused_before_any_query(self):
        machine = FakeMachine(docker=data_docker, sql=data_sql())
        code, _ = self.run_main(['data', '--run', '--login', "x' OR '1'='1"], machine)
        self.assertEqual(code, 1)
        self.assertFalse(any(kind == 'sql' and 'dba_' in call[0] for kind, *call in machine.calls))

    def test_the_expected_release_is_the_committed_one(self):
        expected = preflight.expected_release()
        self.assertEqual(expected['datasetVersion'], '1.2')
        self.assertEqual(expected['committedReleaseSha256'], expected['releaseSha256'])
        self.assertEqual(expected['counts']['MISSIONS'], 300)


# --------------------------------------------------------------------------------------------------------------- step 4
def missions_page(page, size, total=300):
    ids = ['ST-%09d' % n for n in range((page - 1) * size + 1, min(page * size, total) + 1)]
    body = '<missionList xmlns="urn:starfleet:missions:v1"><page>%d</page><pageSize>%d</pageSize><totalCount>%d</totalCount>' \
           '<totalPages>%d</totalPages>%s</missionList>' % (page, size, total, (total + size - 1) // size,
                                                         ''.join('<mission><missionId>%s</missionId></mission>' % i for i in ids))
    return body.encode('utf-8')


def rest(variant):
    def answer(m, method, url, headers, body):
        parts = preflight.urllib.parse.urlsplit(url)
        query = dict(preflight.urllib.parse.parse_qsl(parts.query))
        common = {'Content-Type': 'application/xml;charset=UTF-8', 'Date': 'now'}
        if variant == 'simulated':
            common['Server'] = 'BaseHTTP/0.6 Python/3.13'
        page, size = query.get('page', '1'), query.get('pageSize', '20')
        if (parts.path == '/missions' and set(query) <= {'page', 'pageSize'} and page.isdigit() and size.isdigit()
                and int(page) >= 1 and 1 <= int(size) <= 50):
            return 200, common, missions_page(int(page), int(size))
        if parts.path == '/nope':
            if variant == 'real':
                return 404, {'Date': 'now'}, b''
            return 404, common, b'<error xmlns="urn:starfleet:missions:v1"><code>INVALID_REQUEST</code><message>m</message></error>'
        return 400, common, b'<error xmlns="urn:starfleet:missions:v1"><code>INVALID_REQUEST</code><message>m</message></error>'
    return answer


class ServiceTests(Base):
    def test_both_targets_and_their_comparison(self):
        for target in ('real', 'simulated'):
            code, _ = self.run_main(['service', '--run', '--target', target], FakeMachine(http=rest(target)))
            self.assertEqual(code, 0, target)
        real, simulated = (sorted(self.results.glob('04-service-%s-*.json' % t))[0] for t in ('real', 'simulated'))
        record = json.loads(real.read_text(encoding='utf-8'))
        self.assertEqual(self.check(record, 'three-hundred')['result'], 'pass')
        self.assertEqual(record['measurements']['walk']['missions'], 300)
        self.assertEqual(set(record['measurements']['probes']), {p[0] for p in preflight.PROBES})
        self.assertNotIn('date', record['measurements']['probes']['path-unknown']['headers'])
        code, lines = self.run_main(['compare', str(real), str(simulated), '--run'], FakeMachine())
        self.assertEqual(code, 0)
        compare, = self.records('04-compare-*.json')
        differences = compare['measurements']['differences']
        aspects = {(d['probe'], d['aspect']) for d in differences}
        self.assertIn(('path-unknown', 'errorCode'), aspects)
        self.assertIn(('path-unknown', 'header server'), aspects)
        self.assertTrue(all(d['explained'] is None and set(d['affects'].values()) == {None} for d in differences))
        self.assertEqual(set(compare['measurements']['latency']), {'real', 'simulated'})

    def test_compare_needs_two_service_records_of_different_targets(self):
        self.run_main(['service', '--run', '--target', 'real'], FakeMachine(http=rest('real')))
        real = str(sorted(self.results.glob('04-service-real-*.json'))[0])
        code, _ = self.run_main(['compare', real, real, '--run'], FakeMachine())
        self.assertEqual(code, 1)

    def test_only_get_is_sent_to_the_service(self):
        machine = FakeMachine(http=rest('real'))
        self.run_main(['service', '--run', '--target', 'real'], machine)
        self.assertEqual({call[1] for call in machine.calls if call[0] == 'http'}, {'GET'})

    def test_a_base_url_off_this_machine_is_refused(self):
        code, _ = self.run_main(['service', '--target', 'real', '--base-url', 'http://10.0.0.5:8083'], FakeMachine())
        self.assertEqual(code, 1)


# --------------------------------------------------------------------------------------------------------------- step 5
ROUTER_NAME = 'starfleet-federation-stack-router-1'


def stack_docker(restart_after=None, stats='all'):
    def answer(m, argv):
        if argv[:2] == ['stats', '--no-stream'] and stats == 'failing':
            return 1, '', 'error during connect'
        if argv[:2] == ['stats', '--no-stream'] and stats == 'partial':
            return 0, json.dumps({'Name': argv[4], 'MemUsage': '1GiB / 2GiB'}), ''
        if argv[0] == 'ps':
            label = argv[2]
            if label.endswith(preflight.STACK_PROJECT):
                return 0, ROUTER_NAME + '\nstarfleet-federation-stack-missions-adapter-1', ''
            if label.endswith(preflight.launch.MISSIONS_PROJECT):
                return 0, preflight.SERVICE_CONTAINER, ''
            return 0, ORACLE, ''
        if argv[:3] == ['inspect', '--format', preflight.STATE_TEMPLATE]:
            restarts = 1 if restart_after is not None and m.t > restart_after and argv[3] == ROUTER_NAME else 0
            return 0, state(argv[3], restarts=restarts), ''
        if argv[:2] == ['stats', '--no-stream']:
            return 0, '\n'.join(json.dumps({'Name': n, 'MemUsage': '1GiB / 2GiB'}) for n in argv[4:]), ''
        return 1, '', ''
    return answer


def router(down=()):
    def answer(m, method, url, headers, body):
        if method == 'GET':
            return 200, {}, missions_page(1, 50)
        query = json.loads(body.decode('utf-8'))['query']
        if query == '{ __typename }':
            return 200, {}, b'{"data": {"__typename": "Query"}}'
        for service, (probe, field) in preflight.OUTAGE_PROBES.items():
            if query == probe:
                if service in down:
                    return 200, {}, json.dumps({'data': {field: None}, 'errors': [{'message': 'down'}]}).encode('utf-8')
                return 200, {}, json.dumps({'data': {field: {'x': 1}}}).encode('utf-8')
        return 200, {}, b'{"data": {"missions": [{"missionId": "ST-1"}]}}'
    return answer


class StackTests(Base):
    def test_load_soak_and_peaks(self):
        code, _ = self.run_main(['stack', 'gamma', '--missions', 'real', '--run', '--minutes', '1', '--interval', '15', '--heavy-repeats', '1'],
                                FakeMachine(docker=stack_docker(), http=router()))
        self.assertEqual(code, 0)
        record, = self.records('05-stack-gamma-real-*.json')
        for check_id in ('docker-peak', 'host-free-min', 'no-oom-restart', 'load-errors'):
            self.assertEqual(self.check(record, check_id)['result'], 'pass', check_id)
        measurements = record['measurements']
        self.assertEqual(measurements['heavy']['latency']['count'], 3)
        self.assertGreater(measurements['soak']['cycles'], 10)
        self.assertEqual(measurements['peaks']['totalGiB'], 4.0)
        self.assertEqual(set(measurements['containersBefore']), {ROUTER_NAME, 'starfleet-federation-stack-missions-adapter-1',
                                                                 preflight.SERVICE_CONTAINER, ORACLE})

    def test_a_restart_during_the_soak_fails_the_threshold(self):
        code, _ = self.run_main(['stack', 'gamma', '--missions', 'real', '--run', '--minutes', '1', '--heavy-repeats', '1'],
                                FakeMachine(docker=stack_docker(restart_after=30), http=router()))
        self.assertEqual(code, 4)
        check = self.check(self.records('05-stack-*.json')[0], 'no-oom-restart')
        self.assertEqual((check['result'], check['observed']), ('fail', [ROUTER_NAME]))

    def test_missing_memory_readings_are_never_a_pass(self):
        for stats in ('failing', 'partial'):
            self.tearDown()
            self.setUp()
            code, _ = self.run_main(['stack', 'gamma', '--missions', 'real', '--run', '--minutes', '1', '--heavy-repeats', '1'],
                                    FakeMachine(docker=stack_docker(stats=stats), http=router()))
            record, = self.records('05-stack-*.json')
            check = self.check(record, 'docker-peak')
            self.assertEqual(check['result'], 'not-measured', stats)
            self.assertEqual(check['observed']['incompleteSamples'], check['observed']['samples'], stats)
            self.assertTrue(any('not measured' in note for note in record['notes']), stats)
            self.assertNotEqual(code, 1, stats)

    def test_epsilon_uses_the_cosmo_router_and_a_dead_router_is_refused(self):
        machine = FakeMachine(docker=stack_docker(), http=lambda m, method, url, headers, body: (None, {}, b''))
        code, _ = self.run_main(['stack', 'epsilon', '--missions', 'simulated', '--run', '--minutes', '1'], machine)
        self.assertEqual(code, 1)
        self.assertEqual([c[2] for c in machine.calls if c[0] == 'http'], [preflight.ROUTER_URLS['cosmo']])


# --------------------------------------------------------------------------------------------------------------- step 6
class OutageTests(Base):
    def outage(self, restore=True, services=('assets', 'missions'), timeout='300'):
        down = set()

        def hook(m, argv):
            argv = [str(a) for a in argv]
            if argv[4] == 'stop':
                down.add(argv[5])
            elif restore:
                down.discard(argv[5])
            return 0
        machine = FakeMachine(http=router(down), launch=hook)
        state_dir = Path(self.tmp.name) / 'state'
        code, _ = self.run_main(['outage', 'gamma', '--missions', 'real', '--state-dir', str(state_dir), '--run', '--timeout', timeout,
                                 '--services', *services], machine)
        return code, machine, state_dir

    def test_stop_and_restore_are_timed_through_the_kit(self):
        code, machine, state_dir = self.outage()
        self.assertEqual(code, 0)
        record, = self.records('06-outage-gamma-real-*.json')
        for service in ('assets', 'missions'):
            self.assertEqual(self.check(record, 'outage-%s' % service)['result'], 'pass')
            self.assertEqual(self.check(record, 'outage-%s-down' % service)['result'], 'pass')
        self.assertEqual(record['measurements']['services']['missions']['stopped'], preflight.SERVICE_CONTAINER)
        self.assertEqual(record['measurements']['services']['assets']['stopped'], 'assets-service')
        launches = [call[1] for call in machine.calls if call[0] == 'launch']
        self.assertEqual([argv[4:6] for argv in launches], [['stop', 'assets'], ['start', 'assets'], ['stop', 'missions'], ['start', 'missions']])
        self.assertEqual(launches[0][2], str(preflight.launch.HERE / 'launch.py'))

    def test_a_router_that_does_not_recover_fails_and_is_never_restarted(self):
        code, machine, _ = self.outage(restore=False, services=('personnel',), timeout='5')
        self.assertEqual(code, 4)
        record, = self.records('06-outage-*.json')
        self.assertEqual(self.check(record, 'outage-personnel')['result'], 'fail')
        self.assertTrue(any('never restarts the router' in note for note in record['notes']))
        self.assertEqual(len([c for c in machine.calls if c[0] == 'launch']), 2)

    def test_an_interruption_after_the_stop_still_starts_the_service(self):
        stopped = set()
        healthy = router()

        def answer(m, method, url, headers, body):
            if stopped:
                raise KeyboardInterrupt
            return healthy(m, method, url, headers, body)

        def hook(m, argv):
            if str(argv[4]) == 'stop':
                stopped.add(str(argv[5]))
            return 0
        machine = FakeMachine(http=answer, launch=hook)
        with self.assertRaises(KeyboardInterrupt):
            self.run_main(['outage', 'gamma', '--missions', 'real', '--state-dir', str(Path(self.tmp.name) / 'state'), '--run',
                           '--services', 'assets'], machine)
        launches = [call[1][4:6] for call in machine.calls if call[0] == 'launch']
        self.assertEqual(launches, [['stop', 'assets'], ['start', 'assets']])

    def test_nothing_is_stopped_when_the_stack_is_not_up(self):
        machine = FakeMachine(http=lambda m, method, url, headers, body: (None, {}, b''))
        code, _ = self.run_main(['outage', 'gamma', '--missions', 'real', '--state-dir', str(Path(self.tmp.name) / 's'), '--run'], machine)
        self.assertEqual(code, 1)
        self.assertFalse(any(c[0] == 'launch' for c in machine.calls))


# --------------------------------------------------------------------------------------------------------------- step 8
def doc(project, service, image, env=None):
    name = '%s-%s-1' % (project, service)
    return {'Id': 'id-' + name, 'Name': '/' + name, 'Image': 'sha256:' + 'c' * 64, 'State': {'Status': 'running'},
            'Config': {'Image': image, 'Env': ['%s=%s' % item for item in (env or {}).items()],
                       'Labels': {'com.docker.compose.project': project, 'com.docker.compose.service': service,
                                  'com.docker.compose.container-number': '1'}},
            'NetworkSettings': {'Ports': {}}, 'Mounts': []}


def fake_cli(docs):
    provenance = preflight.provenance_module()

    def call(argv):
        provenance.assert_read_only(argv)
        if argv[:2] == ['compose', '-p']:
            return ''.join(json.dumps({'ID': d['Id']}) + '\n' for d in docs if d['Config']['Labels']['com.docker.compose.project'] == argv[2])
        return json.dumps([d for d in docs if d['Id'] in argv[1:]])
    return call


class ProvenanceTests(Base):
    def config(self, url):
        block = {'compose_projects': [preflight.STACK_PROJECT, preflight.launch.MISSIONS_PROJECT],
                 'backends': {'missions': {'mode': 'real', 'service': 'starfleet-missions/missions', 'image_ref': preflight.SERVICE_IMAGE}},
                 'routing': {'env': {'missions-adapter': {'MISSIONS_SERVICE_URL': url}}}, 'launch_files': {}}
        path = Path(self.tmp.name) / 'config.json'
        path.write_text(json.dumps({'scenarios': {'delta': {'provenance': block, 'mcp_url': 'http://127.0.0.1:8193/mcp'}}}), encoding='utf-8')
        return path

    def test_the_real_missions_mode_is_observed(self):
        path = self.config(preflight.launch.MISSIONS_ADAPTER_URL['real'])
        machine = FakeMachine()
        machine.provenance_cli = fake_cli([doc(preflight.launch.MISSIONS_PROJECT, 'missions', preflight.SERVICE_IMAGE),
                                           doc(preflight.STACK_PROJECT, 'missions-adapter', 'adapter:1',
                                               {'MISSIONS_SERVICE_URL': preflight.launch.MISSIONS_ADAPTER_URL['real']})])
        code, _ = self.run_main(['provenance', 'delta', '--config', str(path), '--run'], machine)
        self.assertEqual(code, 0)
        record, = self.records('08-provenance-*.json')
        self.assertEqual(record['measurements']['missionsMode'], {'intended': 'real', 'observed': 'real'})
        self.assertEqual(record['measurements']['problems'], [])

    def test_a_simulator_where_the_real_service_is_intended_fails(self):
        path = self.config(preflight.launch.MISSIONS_ADAPTER_URL['real'])
        machine = FakeMachine()
        machine.provenance_cli = fake_cli([doc(preflight.STACK_PROJECT, 'missions-stub', 'python:3.13'),
                                           doc(preflight.STACK_PROJECT, 'missions-adapter', 'adapter:1',
                                               {'MISSIONS_SERVICE_URL': preflight.launch.MISSIONS_ADAPTER_URL['simulated']})])
        code, _ = self.run_main(['provenance', 'delta', '--config', str(path), '--run'], machine)
        self.assertEqual(code, 4)
        record, = self.records('08-provenance-*.json')
        self.assertEqual(self.check(record, 'missions-real')['result'], 'fail')
        self.assertTrue(record['measurements']['problems'])

    def test_a_scenario_missing_from_the_config_is_refused(self):
        path = self.config(preflight.launch.MISSIONS_ADAPTER_URL['real'])
        code, _ = self.run_main(['provenance', 'alpha', '--config', str(path), '--run'], FakeMachine())
        self.assertEqual(code, 1)


# --------------------------------------------------------------------------------------------------------------- the report
class ReportTests(Base):
    def test_the_template_filled_from_the_records(self):
        self.run_main(['oracle', '--run', '--window', '5', '--interval', '5'], FakeMachine(docker=oracle_docker, sql=oracle_sql))
        self.run_main(['stack', 'gamma', '--missions', 'real', '--run', '--minutes', '1', '--heavy-repeats', '1'],
                      FakeMachine(docker=stack_docker(), http=router()))
        for target in ('real', 'simulated'):
            self.run_main(['service', '--run', '--target', target], FakeMachine(http=rest(target)))
        real, simulated = (str(sorted(self.results.glob('04-service-%s-*.json' % t))[0]) for t in ('real', 'simulated'))
        self.run_main(['compare', real, simulated, '--run'], FakeMachine())
        lines = []
        self.assertEqual(preflight.main(['report', '--results', str(self.results)], out=lines.append), 0)
        filled, = [json.loads(p.read_text(encoding='utf-8')) for p in self.results.glob('preflight-record-*.json')]
        statuses = {t['id']: t['status'] for t in filled['thresholds']}
        self.assertEqual(statuses['oracle-ready'], 'pass')
        self.assertEqual(statuses['docker-peak'], 'pass')
        self.assertEqual(statuses['answerability'], 'not-measured')
        self.assertFalse(filled['goNoGo']['measured']['allThresholdsPass'])
        self.assertIsNone(filled['goNoGo']['decision'])
        self.assertIsNone(filled['decisionL']['judgement'])
        self.assertTrue(filled['decisionL']['differences'])
        self.assertEqual([s['step'] for s in filled['steps'] if s['records']], [2, 4, 5])


# --------------------------------------------------------------------------------------------------------------- facts owned elsewhere
class PinnedFactTests(unittest.TestCase):
    def test_the_full_page_is_the_acceptance_suites(self):
        tree = ast.parse((ROOT / 'federation' / 'acceptance' / 'shared_suite.py').read_text(encoding='utf-8'))
        value = next(node.value for node in tree.body if isinstance(node, ast.Assign) and getattr(node.targets[0], 'id', None) == 'FULL_PAGE')
        self.assertEqual(ast.literal_eval(value), preflight.FULL_PAGE)

    def test_the_thresholds_are_the_designs(self):
        design = (ROOT / 'docs' / 'STUDY-2-DESIGN.md').read_text(encoding='utf-8')
        limits = preflight.thresholds()
        for item in limits.values():
            self.assertIn(item['text'], design.replace('\n', ' '), item['id'])
        self.assertEqual(limits['docker-peak']['limitBytes'], 12 * GIB)
        self.assertEqual(limits['host-free-min']['minBytes'], 6 * GIB)
        self.assertEqual(limits['oracle-ready']['maxSeconds'], 15 * 60)
        self.assertEqual(preflight.oracle_environment()['readyTimeoutSeconds'], 15 * 60)

    def test_the_template_names_every_step_and_command(self):
        steps = preflight.template()['steps']
        self.assertEqual([s['step'] for s in steps], list(range(1, 10)))
        commands = {s['command'] for s in steps} - {None}
        self.assertEqual(commands, set(preflight.STEPS))
        self.assertEqual({n for n, (number, _, _) in preflight.STEPS.items()}, commands)
        self.assertEqual({number for number, _, _ in preflight.STEPS.values()}, {s['step'] for s in steps if s['command']})

    def test_the_service_and_stack_names(self):
        compose = preflight.MISSIONS_COMPOSE.read_text(encoding='utf-8')
        self.assertEqual(re.search(r'MISSIONS_IMAGE:-([^}]+)\}', compose).group(1), preflight.SERVICE_IMAGE)
        self.assertEqual(re.search(r'MISSIONS_CONTAINER_NAME:-([^}]+)\}', compose).group(1), preflight.SERVICE_CONTAINER)
        stack = (ROOT / 'federation' / 'stack' / 'compose.yaml').read_text(encoding='utf-8')
        self.assertEqual(re.search(r'(?m)^name: (\S+)$', stack).group(1), preflight.STACK_PROJECT)
        self.assertEqual(set(preflight.OUTAGE_PROBES), set(preflight.launch.OUTAGE_SERVICES))
        self.assertIn('8170', preflight.ROUTER_URLS['apollo'])
        self.assertIn('8171', preflight.ROUTER_URLS['cosmo'])

    def test_no_machine_path_in_the_committed_files(self):
        # A drive letter that is not the end of a regex escape such as \d, then a separator, a folder name and another separator.
        drive = re.compile(r'(?<![\\\w])[A-Za-z]:[\\/][A-Za-z0-9_ .-]+[\\/]')
        self.assertTrue(drive.search('in ' + 'C:' + '\\Users\\someone\\repo'))
        self.assertTrue(drive.search('in ' + 'D:' + '/work/repo'))
        self.assertIsNone(drive.search(r'(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d)'))
        for path in sorted(p for p in HERE.iterdir() if p.is_file() and p.suffix in ('.py', '.json', '.md')):
            self.assertIsNone(drive.search(path.read_text(encoding='utf-8')), path.name)


if __name__ == '__main__':
    unittest.main()
