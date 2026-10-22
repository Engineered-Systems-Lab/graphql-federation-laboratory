"""The end-to-end acceptance tests of the federation layer through the Apollo router, against the STUB-BACKEND stack.

The stack (federation/stack/compose.yaml) runs the four adapters, the REAL Assets service with its PostgreSQL, the REAL Personnel v2
service and a stub of the Missions service that serves the released dataset 1.1 (300 missions), so no Oracle is needed. The REAL-SERVICE mode (the
real Missions service) is not run here. The supergraph is composed by the committed script from the adapters' own SDL.

The expected outcomes are in federation/acceptance/expected-outcomes.json. They were derived from the RELEASED datasets and the
mapping release 1.2 (the large data) by federation/acceptance/derive_expected.py BEFORE any router code existed, never from a run; a test of the
offline stage re-derives them.

The acceptance questions 2 to 6 of the federation design (list A) and the controlled cases (the outage, the dead adapters) are the
ROUTER-NEUTRAL suite in federation/acceptance/shared_suite.py: this module only starts the stack and the Apollo router, binds that
suite to the router's address with the Apollo settings below (Part 1 and Part 3, the same test ids as before the suite was shared),
and keeps what is Apollo's own: Part 2, the determinism and the freshness of the composition, the subgraph timeout of router.yaml
and the code and subgraph name of its errors entries, and the router restart. The parts run in that order (the class names sort that way).
The facts that belong in the README's Apollo table are collected in FACTS and printed at the end.

Everything is disposable and uniquely named per run; the gate removes only what it created. Missing Docker is a failure, and so is
a missing acceptance of Rover's Elastic License 2.0 (set APOLLO_ELV2_LICENSE=accept on purpose).
"""
from pathlib import Path
import difflib
import hashlib
import json
import os
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

# What is Apollo's own, declared to the shared suite (router.yaml: `traffic_shaping.all.timeout: 5s` and `include_subgraph_errors`).
# A dead adapter gives an errors entry with the code GATEWAY_TIMEOUT whose `extensions.service` names the subgraph, after the 5 s the
# router waits for a subgraph request; the answer must come in 4.5 s to 15 s (the 30 s default of the router is not in force).
# In a whole list of 300 missions asked in three pages, a page that comes after the first failures can meet a connection that is refused
# at once instead of waiting: the entry then has the code SUBREQUEST_HTTP_ERROR (and the same `service`). It is declared for lists only;
# a single answer stays strict.
APOLLO = shared_suite.RouterSettings(adapter_down_code='GATEWAY_TIMEOUT', subgraph_key='service', adapter_down_seconds=(4.5, 15),
                                     adapter_down_other_codes=('SUBREQUEST_HTTP_ERROR',))


class ApolloControls(shared_suite.Controls):
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
        # Apollo keeps the addresses it resolved for adapters that were stopped and started again until it is restarted.
        STATE['stack'].restart('router')
        support.wait_for_graphql(STATE['stack'].router_url)


def setUpModule():
    if os.environ.get('APOLLO_ELV2_LICENSE') != 'accept':
        raise RuntimeError("Rover's composition plugin is under the Elastic License 2.0: set APOLLO_ELV2_LICENSE=accept to accept it on purpose")
    support.docker(['version', '--format', '{{.Server.Version}}'])
    scratch = tempfile.mkdtemp(prefix='fed-router-gate-')
    stack = support.Stack(scratch)
    STATE.update(stack=stack, scratch=scratch, started=time.monotonic())
    started = time.monotonic()
    stack.start_backends()
    TIMINGS['backends and adapters built and started'] = round(time.monotonic() - started, 1)
    started = time.monotonic()
    output = stack.compose_supergraph(stack.supergraph, ['--save-sdl', str(Path(scratch) / 'sdl-first')])
    TIMINGS['first composition'] = round(time.monotonic() - started, 1)
    FACTS['compose output'] = output.strip().splitlines()
    stack.start_router()
    STATE['router'] = shared_suite.Router(stack.router_url, ApolloControls(), APOLLO, FACTS)


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


class ApolloRouter:
    """The router under test: the one of this run's stack."""

    @property
    def router(self):
        return STATE['router']


class Part1Acceptance(ApolloRouter, shared_suite.AcceptanceQuestions, unittest.TestCase):
    """The acceptance questions 2 to 6 and the controlled cases of the queries: the shared suite against the Apollo router."""


class Part2Determinism(unittest.TestCase):
    """Is the supergraph reproducible? The evidence for the decision whether to commit it (see the README)."""
    maxDiff = None

    def scratch(self, name):
        path = Path(STATE['scratch']) / name
        path.mkdir(parents=True, exist_ok=True)
        return path

    def sdl_files(self, directory):
        return {name: (Path(directory) / f'{name}.graphql').read_bytes() for name in support.ADAPTERS}

    def test_01_each_adapter_serves_the_same_sdl_bytes_twice(self):
        first = self.sdl_files(Path(STATE['scratch']) / 'sdl-first')
        STATE['stack'].compose_supergraph(Path(STATE['scratch']) / 'second-fetch.graphql', ['--save-sdl', str(self.scratch('sdl-second'))])
        second = self.sdl_files(Path(STATE['scratch']) / 'sdl-second')
        self.assertEqual(first, second)
        FACTS['sdl sizes (bytes)'] = {name: len(data) for name, data in first.items()}

    def test_02_composing_twice_from_the_same_inputs_gives_the_same_sha256(self):
        stack, root = STATE['stack'], Path(STATE['scratch'])
        a, b = root / 'twice-a.graphql', root / 'twice-b.graphql'
        stack.compose_supergraph(a, ['--sdl-dir', str(root / 'sdl-first')])
        stack.compose_supergraph(b, ['--sdl-dir', str(root / 'sdl-first')])
        self.assertEqual(sha256(a), sha256(b))
        self.assertEqual(sha256(a), sha256(stack.supergraph), 'composing from the saved SDL gives the supergraph the router runs')
        FACTS['supergraph sha256'] = sha256(a)
        FACTS['supergraph bytes'] = a.stat().st_size

    def test_03_composing_from_restarted_adapters_gives_the_same_sdl_and_the_same_sha256(self):
        stack, root = STATE['stack'], Path(STATE['scratch'])
        for name in support.ADAPTERS:
            stack.restart(name + '-adapter')
        restarted = root / 'restarted.graphql'
        stack.compose_supergraph(restarted, ['--save-sdl', str(self.scratch('sdl-restarted'))])
        self.assertEqual(self.sdl_files(root / 'sdl-first'), self.sdl_files(root / 'sdl-restarted'))
        self.assertEqual(sha256(restarted), sha256(stack.supergraph))
        stack.start_router()

    def test_04_another_order_of_the_subgraphs_is_recorded_as_information_only(self):
        stack, root = STATE['stack'], Path(STATE['scratch'])
        reversed_out = root / 'reversed.graphql'
        stack.compose_supergraph(reversed_out, ['--sdl-dir', str(root / 'sdl-first'), '--order', ','.join(reversed(sorted(support.ADAPTERS)))])
        same = sha256(reversed_out) == sha256(stack.supergraph)
        FACTS['reversed order gives the same sha256 (information only, not a gate)'] = same
        if not same:
            diff = list(difflib.unified_diff(stack.supergraph.read_text(encoding='utf-8').splitlines(), reversed_out.read_text(encoding='utf-8').splitlines(), lineterm='', n=0))
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
        out = root / 'changed.graphql'
        stack.compose_supergraph(out, ['--sdl-dir', str(changed)])
        diff = list(difflib.unified_diff(stack.supergraph.read_text(encoding='utf-8').splitlines(), out.read_text(encoding='utf-8').splitlines(), lineterm='', n=0))
        changes = [line for line in diff if line[:1] in '+-' and not line.startswith(('+++', '---'))]
        self.assertTrue(changes)
        self.assertTrue(all('reviewNote' in line for line in changes), 'every changed line is the change: ' + '\n'.join(changes))
        FACTS['small sdl change: diff'] = changes

    def test_06_the_committed_supergraph_is_the_fresh_composition_of_the_adapters_sdl(self):
        committed = support.COMMITTED_SUPERGRAPH.read_bytes().replace(b'\r\n', b'\n')
        fresh = STATE['stack'].supergraph.read_bytes()
        if committed != fresh:
            diff = list(difflib.unified_diff(committed.decode('utf-8').splitlines(), fresh.decode('utf-8').splitlines(), 'committed', 'fresh', lineterm='', n=0))
            self.fail('federation/routers/apollo/supergraph.graphql is stale: a schema changed. Regenerate it with '
                      '`APOLLO_ELV2_LICENSE=accept bash federation/stack/start.sh start` and review the diff. First lines:\n' + '\n'.join(diff[:30]))

    def test_07_the_supergraph_routes_to_the_service_names_of_the_stack_in_every_mode(self):
        text = STATE['stack'].supergraph.read_text(encoding='utf-8')
        for url in ('http://assets-adapter:8184/graphql', 'http://mapping-adapter:8190/graphql', 'http://missions-adapter:8183/graphql',
                    'http://personnel-adapter:8182/graphql'):
            self.assertIn(f'url: "{url}"', text)
        self.assertNotIn('127.0.0.1', text)
        self.assertNotIn('\r', text)


class Part3Outage(ApolloRouter, shared_suite.ControlledCases, unittest.TestCase):
    """The outage and the dead adapters: the shared suite against the Apollo router, with the Apollo settings declared above."""


class Part4Introspection(ApolloRouter, unittest.TestCase):
    """Schema discovery for the Abstraction ladder study: the router answers introspection (the Apollo setting is written in its configuration), and the
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
