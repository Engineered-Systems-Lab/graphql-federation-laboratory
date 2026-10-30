"""The tests of the request relay, offline: no stack, no Missions service, no API key.

- The rounds: the request file's shape, the round order, one run per round, the answers file and the ledger with its chain, and the
  verification that catches a changed, missing or unlisted file; on the harness's scripted session (study/harness/mcp_client.py).
- The fingerprint is read before and after every round; a round whose first reading fails runs nothing.
- The Missions backend on the Missions port is checked against --missions (on scripted docker ps output); a wrong one runs nothing.
- The round lock: a second run of a folder while one runs, or with a lock left behind, is refused and runs nothing.
- Through the raw MCP server's own code (built in this process, as the relay builds it) against the loopback service of the MCP offline
  tests (study/mcp/test_mcp_offline.py): the answers are the texts and error flags an agent's session reads, refusals included. These need
  the pinned `mcp` package and are skipped without it.
"""
import importlib.util
import io
import json
import os
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest import mock

import relay

sys.path.insert(0, str(relay.ROOT / 'study' / 'harness'))
from mcp_client import FakeToolSession  # noqa: E402

HAS_MCP = importlib.util.find_spec('mcp') is not None
LAB = {'labCommit': '0' * 40, 'code': {'study/blind/relay.py': 'a' * 64}}
SERVING = {'container': 'c1', 'name': 'starfleet-missions-service', 'project': 'starfleet-missions', 'service': 'missions-service',
           'ports': '127.0.0.1:8083->8083/tcp', 'missions': 'real', 'port': 8083}
FACTS = {'allow': ['http://127.0.0.1:8083'], 'mappingDir': 'federation/mapping-releases', 'timeoutSeconds': 20.0, 'maxChars': 200000}


def fake_session():
    tools = [{'name': name, 'description': '', 'input_schema': {}} for name in relay.TOOLS]
    return FakeToolSession(tools, {
        'http_request': lambda a: json.dumps({'status': 200, 'url': a['url']}),
        'soap_request': lambda a: ('The service did not answer: ConnectionRefusedError', True),
        'read_mapping_release': lambda a: json.dumps({'truncated': False, 'content': '{"release": "%s"}' % a['release']}),
    })


class Clock:
    def __init__(self):
        self.n = 0

    def __call__(self):
        self.n += 1
        return '2026-10-30T00:00:%02d.000+00:00' % self.n


class Rounds(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name) / 'relay'
        self.folder.mkdir()
        self.readings = []

    def fingerprint(self):
        self.readings.append(True)
        return {'fingerprint': 'missions-db:abc', 'session': 'oracle-instance:t0', 'missions': 'real'}

    def write(self, n, requests, raw=None):
        body = raw if raw is not None else json.dumps({'round': n, 'requests': requests}, indent=2)
        (self.folder / relay.requests_name(n)).write_text(body, encoding='utf-8', newline='\n')

    def run_round(self, n, session=None, fingerprint=None, backend=None):
        return relay.run_round(self.folder, n, session or fake_session(), fingerprint or self.fingerprint, FACTS, LAB,
                               backend=backend or (lambda: dict(SERVING)), clock=Clock())

    REQUESTS = [{'id': 'one', 'tool': 'http_request', 'arguments': {'method': 'GET', 'url': 'http://127.0.0.1:8083/missions?pageSize=1'}},
                {'tool': 'soap_request', 'arguments': {'url': 'http://127.0.0.1:8082/soap/personnel-v2', 'envelope': '<e/>'}},
                {'tool': 'read_mapping_release', 'arguments': {'release': '1.3'}}]

    def test_a_round_writes_its_answers_and_the_ledger(self):
        self.write(1, self.REQUESTS)
        session = fake_session()
        record = self.run_round(1, session)
        self.assertEqual(session.calls, [(r['tool'], r['arguments']) for r in self.REQUESTS])
        saved = json.loads((self.folder / relay.answers_name(1)).read_text(encoding='utf-8'))
        self.assertEqual(saved, record)
        self.assertEqual([a['index'] for a in saved['answers']], [1, 2, 3])
        self.assertEqual(saved['answers'][0]['id'], 'one')
        self.assertNotIn('id', saved['answers'][1])
        self.assertEqual([a['isError'] for a in saved['answers']], [False, True, False])
        self.assertEqual(saved['answers'][1]['text'], 'The service did not answer: ConnectionRefusedError')
        self.assertEqual([a['arguments'] for a in saved['answers']], [r['arguments'] for r in self.REQUESTS])
        self.assertEqual(saved['round'], 1)
        self.assertEqual((saved['startedAt'], saved['finishedAt']), ('2026-10-30T00:00:01.000+00:00', '2026-10-30T00:00:02.000+00:00'))
        self.assertEqual(saved['relay']['version'], relay.VERSION)
        self.assertEqual(saved['fingerprint']['before']['fingerprint'], 'missions-db:abc')
        self.assertTrue(saved['fingerprint']['same'])
        self.assertEqual(len(self.readings), 2)
        self.assertEqual(saved['requestFile']['sha256'], relay.sha256((self.folder / relay.requests_name(1)).read_bytes()))
        ledger = relay.read_ledger(self.folder)
        self.assertEqual(ledger['rounds'][0]['answers']['sha256'], relay.sha256((self.folder / relay.answers_name(1)).read_bytes()))
        self.assertEqual(relay.verify(self.folder), [])

    def test_rounds_follow_one_another_and_each_runs_once(self):
        self.write(1, self.REQUESTS[:1])
        self.run_round(1)
        with self.assertRaisesRegex(relay.Refused, 'not the next round'):
            self.run_round(1)
        with self.assertRaisesRegex(relay.Refused, 'not the next round; 1 round'):
            self.run_round(3)
        self.write(3, self.REQUESTS[:1])
        with self.assertRaisesRegex(relay.Refused, 'round-003.requests.json is not in the ledger'):
            self.run_round(3)
        (self.folder / relay.requests_name(3)).unlink()
        self.write(2, self.REQUESTS[2:])
        self.run_round(2)
        ledger = relay.read_ledger(self.folder)
        self.assertEqual([r['round'] for r in ledger['rounds']], [1, 2])
        first, second = ledger['rounds']
        self.assertEqual(second['chain'], relay.chain(first['chain'], second['requests']['sha256'], second['answers']['sha256']))
        self.assertEqual(relay.verify(self.folder), [])

    def test_a_request_file_of_another_shape_is_sent_back_unrun(self):
        cases = [
            ([{'tool': 'calculate', 'arguments': {}}], 'names the tool'),
            ([{'tool': 'ask_requester', 'arguments': {'question': 'q'}}], 'names the tool'),
            ([{'tool': 'graphql_query', 'arguments': {'query': '{ a }'}}], 'names the tool'),
            ([{'tool': 'http_request', 'arguments': {}, 'note': 'x'}], 'and nothing else'),
            ([{'tool': 'http_request', 'arguments': 'GET /'}], 'must be an object'),
            ([{'tool': 'http_request', 'arguments': {}, 'id': 7}], '"id" must be a string'),
            ([], 'non-empty list'),
        ]
        for requests, message in cases:
            with self.subTest(message=message):
                self.write(1, requests)
                session = fake_session()
                with self.assertRaisesRegex(relay.Refused, message):
                    self.run_round(1, session)
                self.assertEqual(session.calls, [])
                self.assertEqual(self.readings, [])
                self.assertFalse((self.folder / relay.answers_name(1)).exists())
                self.assertFalse((self.folder / relay.LEDGER).exists())
        for raw, message in (('{"round": 2, "requests": [{"tool": "http_request", "arguments": {}}]}', '"round" is 2'),
                             ('{"requests": []}', 'exactly the keys'), ('not json', 'not UTF-8 JSON')):
            with self.subTest(raw=raw):
                self.write(1, None, raw=raw)
                with self.assertRaisesRegex(relay.Refused, message):
                    self.run_round(1)

    def test_a_failed_first_fingerprint_runs_nothing_and_a_changed_one_is_recorded(self):
        self.write(1, self.REQUESTS[:1])

        def broken():
            raise relay.Refused('the dataset fingerprint could not be read: no Oracle')
        session = fake_session()
        with self.assertRaisesRegex(relay.Refused, 'no Oracle'):
            self.run_round(1, session, broken)
        self.assertEqual(session.calls, [])
        self.assertFalse((self.folder / relay.answers_name(1)).exists())
        readings = iter([{'fingerprint': 'missions-db:a'}, {'fingerprint': 'missions-db:b'}])
        record = self.run_round(1, fingerprint=lambda: next(readings))
        self.assertFalse(record['fingerprint']['same'])
        self.assertEqual(record['fingerprint']['after'], {'fingerprint': 'missions-db:b'})

    def test_verify_catches_a_changed_a_missing_and_an_unlisted_file(self):
        self.write(1, self.REQUESTS[:1])
        self.run_round(1)
        answers = self.folder / relay.answers_name(1)
        original = answers.read_bytes()
        answers.write_bytes(original.replace(b'missions?pageSize=1', b'missions?pageSize=2'))
        self.assertIn('round 1: %s changed since the round' % relay.answers_name(1), relay.verify(self.folder))
        with self.assertRaisesRegex(relay.Refused, 'does not match its ledger'):
            self.write(2, self.REQUESTS[:1])
            self.run_round(2)
        answers.write_bytes(original)
        self.assertEqual(relay.verify(self.folder), [])
        (self.folder / relay.answers_name(3)).write_text('{}', encoding='utf-8')
        self.assertIn('%s is not in the ledger' % relay.answers_name(3), relay.verify(self.folder))
        (self.folder / relay.answers_name(3)).unlink()
        (self.folder / relay.requests_name(1)).unlink()
        self.assertIn('round 1: %s is missing' % relay.requests_name(1), relay.verify(self.folder))

    def test_the_relay_folder_must_lie_outside_the_lab(self):
        with self.assertRaisesRegex(relay.Refused, 'inside the lab checkout'):
            relay.relay_folder(relay.ROOT / 'study')
        self.assertEqual(relay.relay_folder(self.folder), self.folder.resolve())

    def test_a_dry_run_prints_the_requests_and_runs_nothing(self):
        self.write(1, self.REQUESTS)
        lines = []
        self.assertEqual(relay.main(['run', '--dir', str(self.folder), '--round', '1', '--missions', 'real', '--dry-run'], out=lines.append), 0)
        self.assertEqual(lines[0], 'round 1: 3 request(s); nothing was run')
        self.assertIn('http_request', lines[1])
        self.assertEqual(sorted(p.name for p in self.folder.iterdir()), [relay.requests_name(1)])
        self.assertEqual(relay.main(['verify', '--dir', str(self.folder)], out=lines.append), 0)


def ps(*rows):
    """A scripted docker ps reader: each row (name, project, service, ports)."""
    lines = ['id%d\t%s\t%s\t%s\t%s' % (i, *row) for i, row in enumerate(rows)]
    calls = []

    def read(argv):
        calls.append(argv)
        return 0, '\n'.join(lines)
    read.calls = calls
    return read


REAL = ('starfleet-missions-service', 'starfleet-missions', 'missions-service', '127.0.0.1:8083->8083/tcp')
STUB = ('starfleet-federation-stack-missions-stub-1', 'starfleet-federation-stack', 'missions-stub', '127.0.0.1:8083->8083/tcp')
OTHER = ('starfleet-federation-stack-assets-service-1', 'starfleet-federation-stack', 'assets-service', '127.0.0.1:8084->8084/tcp')


class ServingBackend(unittest.TestCase):
    def test_the_named_backend_is_accepted(self):
        read = ps(REAL, OTHER)
        found = relay.serving_backend('real', read)
        self.assertEqual((found['name'], found['missions'], found['port']), ('starfleet-missions-service', 'real', 8083))
        self.assertEqual(read.calls[0][:2], ['docker', 'ps'])
        self.assertEqual(relay.serving_backend('simulated', ps(STUB, OTHER))['service'], 'missions-stub')

    def test_the_simulator_on_the_port_refuses_a_real_round_and_the_reverse(self):
        with self.assertRaisesRegex(relay.Refused, 'missions-stub.*not by the real Missions service'):
            relay.serving_backend('real', ps(STUB, OTHER))
        with self.assertRaisesRegex(relay.Refused, 'not by the Missions simulator'):
            relay.serving_backend('simulated', ps(REAL, OTHER))
        renamed = ('starfleet-missions-service', 'elsewhere', 'missions-stub', '127.0.0.1:8083->8083/tcp')
        with self.assertRaisesRegex(relay.Refused, 'not by the Missions simulator'):
            relay.serving_backend('simulated', ps(renamed))

    def test_none_two_or_an_unreadable_docker_refuse(self):
        with self.assertRaisesRegex(relay.Refused, '0 containers publish the Missions port 8083'):
            relay.serving_backend('real', ps(OTHER, (REAL[0], REAL[1], REAL[2], '8083/tcp')))  # exposed, not published
        with self.assertRaisesRegex(relay.Refused, '2 containers'):
            relay.serving_backend('real', ps(REAL, (STUB[0], STUB[1], STUB[2], '0.0.0.0:8083->8083/tcp, [::]:8083->8083/tcp')))
        with self.assertRaisesRegex(relay.Refused, 'docker ps failed'):
            relay.serving_backend('real', lambda argv: (1, ''))
        self.assertEqual(relay.serving_backend('real', ps((REAL[0], REAL[1], REAL[2], '[::1]:8083->8083/tcp')))['port'], 8083)
        self.assertRaises(relay.Refused, relay.serving_backend, 'real', ps((REAL[0], REAL[1], REAL[2], '127.0.0.1:18083->8083/tcp')))


class RoundGuards(unittest.TestCase):
    setUp, fingerprint, write, run_round, REQUESTS = Rounds.setUp, Rounds.fingerprint, Rounds.write, Rounds.run_round, Rounds.REQUESTS

    def test_a_wrong_backend_runs_nothing_and_a_change_is_recorded(self):
        self.write(1, self.REQUESTS)
        session = fake_session()

        def wrong():
            raise relay.Refused('port 8083 is served by missions-stub')
        with self.assertRaisesRegex(relay.Refused, 'missions-stub'):
            self.run_round(1, session, backend=wrong)
        self.assertEqual(session.calls, [])
        self.assertEqual(sorted(p.name for p in self.folder.iterdir()), [relay.requests_name(1)])
        readings = iter([dict(SERVING), {'error': 'gone'}])
        record = self.run_round(1, backend=lambda: next(readings))
        self.assertFalse(record['missionsBackend']['same'])
        self.assertEqual(record['missionsBackend']['before']['name'], 'starfleet-missions-service')

    def test_two_runs_at_once_run_the_round_once(self):
        self.write(1, self.REQUESTS)
        entered, release = threading.Event(), threading.Event()
        inner = fake_session()

        class Slow:
            def __init__(self):
                self.calls = []

            def call(self, name, arguments):
                self.calls.append(name)
                entered.set()
                release.wait(10)
                return inner.call(name, arguments)
        slow, results = Slow(), {}
        first = threading.Thread(target=lambda: results.setdefault('first', self.run_round(1, slow)))
        first.start()
        self.assertTrue(entered.wait(10))
        second = fake_session()
        with self.assertRaisesRegex(relay.Refused, 'relay.lock exists'):
            self.run_round(1, second)
        release.set()
        first.join(10)
        self.assertEqual(second.calls, [])
        self.assertEqual(len(slow.calls), len(self.REQUESTS))
        self.assertEqual(results['first']['round'], 1)
        self.assertEqual(len(relay.read_ledger(self.folder)['rounds']), 1)
        self.assertEqual(relay.verify(self.folder), [])
        self.assertFalse((self.folder / relay.LOCK).exists())

    def test_a_lock_left_behind_refuses_and_a_refusal_releases_the_lock(self):
        self.write(1, self.REQUESTS)
        with self.assertRaises(relay.Refused):
            self.run_round(2)  # not the next round: refused inside the lock
        self.assertFalse((self.folder / relay.LOCK).exists())
        (self.folder / relay.LOCK).write_text('{}\n', encoding='utf-8')
        session = fake_session()
        with self.assertRaisesRegex(relay.Refused, 'relay.lock exists'):
            self.run_round(1, session)
        self.assertEqual(session.calls, [])
        self.assertTrue((self.folder / relay.LOCK).exists())  # never removed by the relay

    def test_the_command_checks_the_backend_and_the_fingerprint_mode(self):
        self.write(1, self.REQUESTS)
        session = fake_session()
        with mock.patch.object(relay, 'lab_state', return_value=LAB), \
                mock.patch.object(relay, 'live_server', return_value=(None, FACTS)), \
                mock.patch.object(relay, 'ServerSession', return_value=session), \
                mock.patch.object(relay, 'docker_read', ps(STUB, OTHER)), \
                mock.patch.object(relay, 'live_fingerprint', side_effect=AssertionError('read after the backend check')):
            with mock.patch('sys.stderr', new_callable=io.StringIO) as err:
                self.assertEqual(relay.main(['run', '--dir', str(self.folder), '--round', '1', '--missions', 'real'], out=lambda *a: None), 1)
        self.assertIn('missions-stub-1 (compose starfleet-federation-stack/missions-stub), not by the real Missions service', err.getvalue())
        self.assertEqual(session.calls, [])
        self.assertEqual(sorted(p.name for p in self.folder.iterdir()), [relay.requests_name(1)])
        done = mock.Mock(returncode=0, stdout=json.dumps({'fingerprint': 'missions-release-1.2:x', 'missions': 'simulated'}), stderr='')
        with mock.patch.object(relay.subprocess, 'run', return_value=done):
            with self.assertRaisesRegex(relay.Refused, "names the Missions mode 'simulated', not 'real'"):
                relay.live_fingerprint('real')


@unittest.skipUnless(HAS_MCP, 'the pinned mcp package is not installed in this interpreter (STUDY_MCP_PYTHON)')
class ThroughTheRawServer(unittest.TestCase):
    """The relay's session on the raw MCP server built in this process, against the loopback service of the MCP offline tests."""

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(relay.MCP))
        from test_mcp_offline import _Handler  # the existing fake service; its test classes are not imported
        import mcp_core
        import raw_server
        cls.http = ThreadingHTTPServer(('127.0.0.1', 0), _Handler)
        threading.Thread(target=cls.http.serve_forever, daemon=True).start()
        cls.base = 'http://127.0.0.1:%d' % cls.http.server_address[1]
        cls.tmp = tempfile.TemporaryDirectory()
        cls.server = raw_server.build([cls.base], str(relay.MAPPING_RELEASES), mcp_core.CallLog('relay-test', Path(cls.tmp.name) / 'calls.jsonl'))

    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown()
        cls.tmp.cleanup()

    def direct(self, tool, arguments):
        import asyncio
        from mcp import Client

        async def run():
            async with Client(self.server) as client:
                return await client.call_tool(tool, arguments)
        result = asyncio.run(run())
        return '\n'.join(p.text for p in result.content if getattr(p, 'text', None) is not None), bool(result.is_error)

    def test_a_round_through_the_server_answers_as_the_agents_see_it(self):
        folder = Path(self.tmp.name) / 'relay'
        folder.mkdir()
        requests = [
            {'id': 'ok', 'tool': 'http_request', 'arguments': {'method': 'GET', 'url': self.base + '/missions?pageSize=1'}},
            {'id': 'head', 'tool': 'http_request', 'arguments': {'method': 'HEAD', 'url': self.base + '/missions'}},
            {'id': 'outside', 'tool': 'http_request', 'arguments': {'method': 'GET', 'url': 'http://127.0.0.1:1/'}},
            {'id': 'header', 'tool': 'http_request', 'arguments': {'method': 'GET', 'url': self.base + '/', 'headers': {'Authorization': 'x'}}},
            {'id': 'method', 'tool': 'http_request', 'arguments': {'method': 'DELETE', 'url': self.base + '/'}},
            {'id': 'missing', 'tool': 'http_request', 'arguments': {'method': 'GET', 'url': self.base + '/missing'}},
            {'id': 'soap', 'tool': 'soap_request', 'arguments': {'url': self.base + '/soap', 'envelope': '<e/>', 'soap_action': 'A'}},
            {'id': 'list', 'tool': 'read_mapping_release', 'arguments': {'release': '1.3'}},
            {'id': 'file', 'tool': 'read_mapping_release', 'arguments': {'release': '1.0', 'file': 'manifest.json'}},
            {'id': 'unknown', 'tool': 'read_mapping_release', 'arguments': {'release': '2.0'}},
        ]
        (folder / relay.requests_name(1)).write_text(json.dumps({'round': 1, 'requests': requests}), encoding='utf-8')
        record = relay.run_round(folder, 1, relay.ServerSession(self.server), lambda: {'fingerprint': 'f'}, FACTS, LAB,
                                 backend=lambda: dict(SERVING))
        answers = {a['id']: a for a in record['answers']}
        for request in requests:
            with self.subTest(id=request['id']):
                self.assertEqual((answers[request['id']]['text'], answers[request['id']]['isError']),
                                 self.direct(request['tool'], request['arguments']))
        self.assertEqual(json.loads(answers['ok']['text'])['status'], 200)
        self.assertEqual(json.loads(json.loads(answers['ok']['text'])['body']), {'path': '/missions?pageSize=1'})
        self.assertFalse(answers['head']['isError'])
        self.assertTrue(answers['outside']['isError'])
        self.assertIn('Address refused', answers['outside']['text'])
        self.assertTrue(answers['header']['isError'])
        self.assertIn('not allowed', answers['header']['text'])
        self.assertTrue(answers['method']['isError'])
        self.assertEqual(json.loads(answers['missing']['text'])['status'], 404)
        self.assertEqual(json.loads(json.loads(answers['soap']['text'])['body']), {'soapBody': '<e/>', 'action': 'A'})
        listing = json.loads(json.loads(answers['list']['text'])['content'])
        self.assertEqual(listing['files'], ['assets.json', 'crew.json', 'manifest.json', 'participants.json'])
        content = json.loads(answers['file']['text'])['content']
        self.assertEqual(content, (relay.MAPPING_RELEASES / '1.0' / 'manifest.json').read_text(encoding='utf-8'))
        self.assertTrue(answers['unknown']['isError'])
        self.assertIn('Releases present: 1.0, 1.1, 1.2, 1.3', answers['unknown']['text'])
        self.assertEqual(relay.verify(folder), [])

    def test_the_live_server_has_the_launch_kits_arguments(self):
        import raw_server
        with mock.patch.dict(os.environ, {'LAB_RESULTS_DIR': self.tmp.name}):
            server, facts = relay.live_server()
        self.assertEqual(facts['allow'], list(raw_server.DEFAULT_ALLOW))
        self.assertIn('http://127.0.0.1:%d' % relay.launch_kit().MISSIONS_HOST_PORT, raw_server.DEFAULT_ALLOW)  # the port the check reads
        self.assertEqual(facts['mappingDir'], 'federation/mapping-releases')
        self.assertEqual((facts['timeoutSeconds'], facts['maxChars']), (20.0, 200000))
        sys.path.insert(0, str(relay.ROOT / 'study' / 'launch'))
        import make_config
        argv = make_config.mcp_server('beta', 'python')['argv']
        self.assertEqual(argv[2:], [str(relay.MCP / 'raw_server.py'), '--mapping-dir', str(relay.MAPPING_RELEASES)])


if __name__ == '__main__':
    unittest.main()
