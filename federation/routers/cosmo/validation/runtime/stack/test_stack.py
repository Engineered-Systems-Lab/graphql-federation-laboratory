"""The end-to-end acceptance tests of the federation layer through the Cosmo router, against the STUB-BACKEND stack.

The stack (federation/stack/compose.yaml, with the profile `cosmo`) runs the four adapters, the REAL Assets service with its PostgreSQL,
the REAL Personnel v2 service and a stub of the Missions service that serves the released dataset 1.1 (300 missions), so no Oracle is needed, and the
Cosmo router instead of the Apollo router. The REAL-SERVICE mode (the real Missions service) is not run here. The execution config is
composed by the committed script (wgc) from the adapters' own SDL; no account, token, control plane or CDN is used.

The expected outcomes are in federation/acceptance/expected-outcomes.json, derived from the RELEASED datasets by
federation/acceptance/derive_expected.py before any router code existed, never from a run.

The acceptance questions 2 to 6 of the federation design (list A) and the controlled cases (the outage, the dead adapters) are the
ROUTER-NEUTRAL suite in federation/acceptance/shared_suite.py, the SAME file the Apollo gate runs: this module only starts the stack and
the Cosmo router, binds that suite to the router's address with the Cosmo settings below (Part 1 and Part 3), and keeps what is Cosmo's
own: Part 2, the determinism and the freshness of the composition, and Part 4, what the router does when adapters come back. The parts
run in that order (the class names sort that way). The facts that belong in the README's Cosmo table are collected in FACTS and printed
at the end.

Everything is disposable and uniquely named per run; the gate removes only what it created. Missing Docker is a failure.
"""
from pathlib import Path
import difflib
import hashlib
import json
import re
import shutil
import sys
import tempfile
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import stack_support as support  # noqa: E402

sys.path.insert(0, str(support.ACCEPTANCE))
import shared_suite  # noqa: E402

STATE = {}
FACTS = {}
TIMINGS = {}

# What is Cosmo's own, declared to the shared suite (config.yaml: `traffic_shaping.all.request_timeout: 5s`, no retry, and
# `subgraph_error_propagation.mode: pass-through`). A dead adapter gives an errors entry that the router writes itself, "Failed to fetch
# from Subgraph 'assets' at Path 'mission.assets'.", with NO extensions: no code, and the subgraph named only in the message. The router
# sends the references of one list to a subgraph in one request, so a failed fetch is one entry, not one per reference. The answer
# comes after the 5 s the router waits for a subgraph request: 4.5 s to 15 s (the router's own default of 60 s is not in force).
# The settings the Apollo gate declares are three; Cosmo needed two more (subgraph_in_message and entries_per).
COSMO = shared_suite.RouterSettings(adapter_down_code=None, subgraph_key=None, adapter_down_seconds=(4.5, 15),
                                    subgraph_in_message=r"Subgraph '([^']+)'", entries_per='subgraph_fetch')


class CosmoControls(shared_suite.Controls):
    """The controls of the shared suite over this run's compose project (a stopped service keeps its container; it is started again)."""

    def stop(self, service):
        STATE['stack'].compose_ok(['stop', '--timeout', '30', service])

    def restore(self, service):
        stack = STATE['stack']
        stack.compose_ok(['start', service])
        stack.compose_ok(['up', '-d', '--wait', '--wait-timeout', '120', service])
        if service.endswith('-adapter'):
            support.wait_for_graphql(stack.adapter_url(service[:-len('-adapter')]))

    def restart_router(self):
        # Cosmo finds adapters that were stopped and started again by itself after a few seconds (Part 4 measures how long), but the
        # shared suite checks the graph two seconds after the last restore, so the router is restarted first, as the Apollo gate does.
        STATE['stack'].restart(support.ROUTER_SERVICE)
        support.wait_for_graphql(STATE['stack'].router_url)


def setUpModule():
    support.docker(['version', '--format', '{{.Server.Version}}'])
    scratch = tempfile.mkdtemp(prefix='fed-cosmo-gate-')
    stack = support.Stack(scratch)
    STATE.update(stack=stack, scratch=scratch, started=time.monotonic())
    started = time.monotonic()
    stack.start_backends()
    TIMINGS['backends and adapters built and started'] = round(time.monotonic() - started, 1)
    started = time.monotonic()
    output = stack.compose_execution_config(stack.execution_config, ['--save-sdl', str(Path(scratch) / 'sdl-first')])
    TIMINGS['first composition'] = round(time.monotonic() - started, 1)
    FACTS['compose output'] = output.strip().splitlines()
    stack.start_router()
    STATE['router'] = shared_suite.Router(stack.router_url, CosmoControls(), COSMO, FACTS)


def tearDownModule():
    stack = STATE.get('stack')
    problems = stack.teardown() if stack else []
    shutil.rmtree(STATE.get('scratch', ''), ignore_errors=True)
    TIMINGS['module total'] = round(time.monotonic() - STATE['started'], 1) if 'started' in STATE else None
    print('router stack timings (seconds): ' + json.dumps(TIMINGS), flush=True)
    print('router stack facts: ' + json.dumps(FACTS, indent=1, sort_keys=True), flush=True)
    if problems:
        raise RuntimeError('Cleanup of owned resources failed: ' + '; '.join(problems))


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class CosmoRouter:
    """The router under test: the one of this run's stack."""

    @property
    def router(self):
        return STATE['router']


class Part1Acceptance(CosmoRouter, shared_suite.AcceptanceQuestions, unittest.TestCase):
    """The acceptance questions 2 to 6 and the controlled cases of the queries: the shared suite against the Cosmo router."""


class Part2Determinism(unittest.TestCase):
    """Is the execution config reproducible? The evidence for the decision whether to commit it (see the README)."""
    maxDiff = None

    def scratch(self, name):
        path = Path(STATE['scratch']) / name
        path.mkdir(parents=True, exist_ok=True)
        return path

    def sdl_files(self, directory):
        return {name: (Path(directory) / f'{name}.graphql').read_bytes() for name in support.ADAPTERS}

    def test_01_each_adapter_serves_the_same_sdl_bytes_twice(self):
        first = self.sdl_files(Path(STATE['scratch']) / 'sdl-first')
        STATE['stack'].compose_execution_config(Path(STATE['scratch']) / 'second-fetch.json', ['--save-sdl', str(self.scratch('sdl-second'))])
        second = self.sdl_files(Path(STATE['scratch']) / 'sdl-second')
        self.assertEqual(first, second)
        FACTS['sdl sizes (bytes)'] = {name: len(data) for name, data in first.items()}

    def test_02_composing_twice_from_the_same_inputs_gives_the_same_sha256(self):
        stack, root = STATE['stack'], Path(STATE['scratch'])
        a, b = root / 'twice-a.json', root / 'twice-b.json'
        stack.compose_execution_config(a, ['--sdl-dir', str(root / 'sdl-first')])
        stack.compose_execution_config(b, ['--sdl-dir', str(root / 'sdl-first')])
        self.assertEqual(sha256(a), sha256(b))
        self.assertEqual(sha256(a), sha256(stack.execution_config), 'composing from the saved SDL gives the execution config the router runs')
        FACTS['execution config sha256'] = sha256(a)
        FACTS['execution config bytes'] = a.stat().st_size

    def test_03_composing_from_restarted_adapters_gives_the_same_sdl_and_the_same_sha256(self):
        stack, root = STATE['stack'], Path(STATE['scratch'])
        for name in support.ADAPTERS:
            stack.restart(name + '-adapter')
        restarted = root / 'restarted.json'
        stack.compose_execution_config(restarted, ['--save-sdl', str(self.scratch('sdl-restarted'))])
        self.assertEqual(self.sdl_files(root / 'sdl-first'), self.sdl_files(root / 'sdl-restarted'))
        self.assertEqual(sha256(restarted), sha256(stack.execution_config))
        stack.start_router()

    def test_04_another_order_of_the_subgraphs_is_recorded_as_information_only(self):
        stack, root = STATE['stack'], Path(STATE['scratch'])
        reversed_out = root / 'reversed.json'
        stack.compose_execution_config(reversed_out, ['--sdl-dir', str(root / 'sdl-first'), '--order', ','.join(reversed(sorted(support.ADAPTERS)))])
        same = sha256(reversed_out) == sha256(stack.execution_config)
        FACTS['reversed order gives the same sha256 (information only, not a gate)'] = same
        if not same:
            diff = list(difflib.unified_diff(stack.execution_config.read_text(encoding='utf-8').splitlines(),
                                             reversed_out.read_text(encoding='utf-8').splitlines(), lineterm='', n=0))
            FACTS['reversed order diff (first 60 lines)'] = diff[:60]
            FACTS['reversed order diff lines'] = len(diff)

    def test_05_a_small_real_sdl_change_gives_a_diff_with_only_the_change(self):
        stack, root = STATE['stack'], Path(STATE['scratch'])
        changed = self.scratch('sdl-changed')
        for name in support.ADAPTERS:
            shutil.copyfile(root / 'sdl-first' / f'{name}.graphql', changed / f'{name}.graphql')
        path = changed / 'missions.graphql'
        text = path.read_text(encoding='utf-8')
        marker = '  title: String!\n'
        self.assertEqual(text.count(marker), 1)
        path.write_bytes(text.replace(marker, marker + '  reviewNote: String\n').encode('utf-8'))
        out = root / 'changed.json'
        stack.compose_execution_config(out, ['--sdl-dir', str(changed)])
        diff = list(difflib.unified_diff(stack.execution_config.read_text(encoding='utf-8').splitlines(), out.read_text(encoding='utf-8').splitlines(), lineterm='', n=0))
        changes = [line for line in diff if line[:1] in '+-' and not line.startswith(('+++', '---'))]
        self.assertTrue(changes)
        # The change shows in four places that quote the SDL (the field list of the Mission type, the subgraph's serviceSdl, the client
        # schema and the string storage) and in the two content keys that name the stored SDL, which are hashes of the text: a changed
        # schema changes its key and nothing else. No line is reordered and nothing is random.
        # The proof: take the changed lines without their mark, indentation and leading content hash, drop the new entry of the field
        # list and take the inserted field out of the added lines; what is left is exactly the removed lines.
        def body(line):
            return re.sub(r'^\s*("key": )?"[0-9a-f]{40}"(: )?', '', line[1:]).strip()

        added = [body(line) for line in changes if line[0] == '+' and body(line) != '"reviewNote",']
        removed = [body(line) for line in changes if line[0] == '-']
        self.assertEqual(sorted(a.replace('  reviewNote: String\\n', '') for a in added), sorted(removed),
                         'every changed line is the inserted field or a content key')
        self.assertLessEqual(len(changes), 12)
        FACTS['small sdl change: changed lines'] = len(changes)

    def test_06_the_committed_execution_config_is_the_fresh_composition_of_the_adapters_sdl(self):
        committed = support.COMMITTED_EXECUTION_CONFIG.read_bytes().replace(b'\r\n', b'\n')
        fresh = STATE['stack'].execution_config.read_bytes()
        if committed != fresh:
            diff = list(difflib.unified_diff(committed.decode('utf-8').splitlines(), fresh.decode('utf-8').splitlines(), 'committed', 'fresh', lineterm='', n=0))
            self.fail('federation/routers/cosmo/execution-config.json is stale: a schema changed. Regenerate it with '
                      '`FEDERATION_ROUTER=cosmo bash federation/stack/start.sh start` and review the diff. First lines:\n' + '\n'.join(diff[:30]))

    def test_07_the_execution_config_routes_to_the_service_names_of_the_stack_in_every_mode(self):
        text = STATE['stack'].execution_config.read_text(encoding='utf-8')
        for url in ('http://assets-adapter:8184/graphql', 'http://mapping-adapter:8190/graphql', 'http://missions-adapter:8183/graphql',
                    'http://personnel-adapter:8182/graphql'):
            self.assertIn(f'"{url}"', text)
        self.assertNotIn('127.0.0.1', text)
        self.assertNotIn('\r', text)


class Part3Outage(CosmoRouter, shared_suite.ControlledCases, unittest.TestCase):
    """The outage and the dead adapters: the shared suite against the Cosmo router, with the Cosmo settings declared above."""


class Part4Recovery(unittest.TestCase):
    """What only Cosmo is asked: does the router find adapters again after they were stopped and started, with no restart of the router?"""

    def test_01_the_router_finds_a_restarted_adapter_again_by_itself(self):
        stack = STATE['stack']
        router = STATE['router']
        query = '{ mission(missionId: "ST-00000LD4O") { assets(release: "1.0") { localRef resolution } } }'
        stack.compose_ok(['stop', '--timeout', '30', 'assets-adapter'])
        stack.compose_ok(['start', 'assets-adapter'])
        started = time.monotonic()
        support.wait_for_graphql(stack.adapter_url('assets'))
        recovered = None
        while time.monotonic() - started < 90:
            status, body, _ = router.ask(query)
            if status == 200 and 'errors' not in body:
                recovered = round(time.monotonic() - started, 1)
                break
            time.sleep(2)
        FACTS['adapter stopped and started again: seconds until the router (not restarted) answered with no errors'] = recovered
        self.assertIsNotNone(recovered, 'the router did not find the restarted adapter within 90 s')
        self.assertEqual([a['resolution'] for a in body['data']['mission']['assets']], ['RESOLVED', 'RESOLVED'])


class Part5Introspection(CosmoRouter, unittest.TestCase):
    """Schema discovery for the Abstraction ladder study: the router answers introspection (the Cosmo setting is written in its configuration), and the
    four adapters answer it on their own endpoints, so that every GraphQL scenario can discover the schema in the same way."""

    DISCOVERY = '{ __schema { queryType { name } types { name } } }'

    def test_01_the_router_answers_a_schema_query_and_a_type_query(self):
        status, body, _ = STATE['router'].ask(self.DISCOVERY)
        self.assertEqual(status, 200)
        self.assertNotIn('errors', body, body.get('errors'))
        schema = body['data']['__schema']
        self.assertEqual(schema['queryType']['name'], 'Query')
        names = {t['name'] for t in schema['types']}
        self.assertTrue({'Mission', 'Asset'} <= names, 'the types of the lab graph are discoverable through the router')
        status, body, _ = STATE['router'].ask('{ __type(name: "Mission") { fields { name } } }')
        self.assertEqual(status, 200)
        self.assertNotIn('errors', body, body.get('errors'))
        self.assertIn('assets', {f['name'] for f in body['data']['__type']['fields']})
        FACTS['introspection through the router: types discoverable'] = len(names)

    def test_02_each_adapter_answers_a_schema_query_on_its_own_endpoint(self):
        stack = STATE['stack']
        counts = {}
        for name in support.ADAPTERS:
            status, body, _ = support.post(stack.adapter_url(name), self.DISCOVERY)
            self.assertEqual(status, 200, name)
            self.assertNotIn('errors', body, name)
            self.assertEqual(body['data']['__schema']['queryType']['name'], 'Query', name)
            counts[name] = len(body['data']['__schema']['types'])
        FACTS['introspection on the adapters: types per adapter'] = counts
