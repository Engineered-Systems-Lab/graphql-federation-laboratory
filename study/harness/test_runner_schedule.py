"""Tests of the study-2 run protocol with a fake stack, fake MCP sessions, fake vendor clients, a fake Docker and a fake fingerprint command:
the blocks in schedule order, the provenance observation and the dataset fingerprint at every block start, resume per block, the vendor-error
requeue, the harness tools in the records, a version-2 scorer with the abstained outcome, and a study-1 config keeping its exact plan
identity. No real model call, no stack, no database and no key."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

import harness_tools
import provenance
import schedule
import scoring_contract
from fakes import FakeDocker, FakeVendorClient, submit, turn
from mcp_client import FakeToolSession
import runner as runner_module
from runner import SYSTEM_PROMPT, BudgetCarryRefused, FingerprintRefused, Study, load_config, parse_fingerprint
from study_common import Redactor, read_jsonl, sha256_file, sha256_json
from test_runner import CORPUS, MODELS, PRICES, PROVENANCE, FakeStack, fake_docker, task
from vendors import VendorFatalError

ARMS = ['beta', 'gamma', 'delta', 'epsilon']
V2_SCORING = '''SCORING_CONTRACT = 2


def score(submission, schema, expected, context):
    asked = bool(context['askRequester'])
    if submission.get('value') == 'ABSTAIN':
        return {'score': 0, 'outcome': 'abstained', 'tags': [], 'clarified': asked}
    ok = submission.get('value') == 'blue'
    return {'score': 1 if ok else 0, 'outcome': 'correct' if ok else 'wrong_answer', 'tags': [], 'clarified': asked}
'''
BROKEN_SCORING = '''SCORING_CONTRACT = 2


def score(submission, schema, expected, context):
    return {'score': 0, 'outcome': 'maybe', 'tags': []}
'''


class Fingerprints:
    """The fingerprint command: returns the scripted readings in order (the last one repeats); an exception instance is raised."""

    def __init__(self, *readings, on_call=None):
        self.readings, self.calls, self.on_call = list(readings) or [{'fingerprint': 'fp-1', 'session': 's-1'}], 0, on_call

    def __call__(self, command):
        self.calls += 1
        if self.on_call:
            self.on_call(self.calls)
        reading = self.readings[min(self.calls, len(self.readings)) - 1]
        if isinstance(reading, Exception):
            raise reading
        return reading if isinstance(reading, str) else json.dumps(reading)


UP = {'backends': {'missions': {'up': True}}}
DOWN = {'backends': {'missions': {'up': False, 'detail': 'connection refused'}}}


def budgets(va=10_000_000, vb=10_000_000, ceiling=85.0, basis='decision D (2026-10-27)'):
    return {'va': {'tokens': va, 'dollar_ceiling': ceiling, 'ceiling_basis': basis},
            'vb': {'tokens': vb, 'dollar_ceiling': ceiling, 'ceiling_basis': basis}}


class Health:
    """The health command: every backend up, except the calls named in `down` (1-based), which report missions down; a reading that is an
    exception instance is raised."""

    def __init__(self, down=(), reading=None, down_if=None, on_call=None):
        self.down, self.reading, self.down_if, self.on_call, self.calls = set(down), reading, down_if, on_call, 0
        self.timeouts = []

    def __call__(self, command, timeout=None):
        self.calls += 1
        self.timeouts.append(timeout)
        if self.on_call:
            self.on_call(self.calls)
        if self.reading is not None:
            if isinstance(self.reading, Exception):
                raise self.reading
            return self.reading
        down = self.calls in self.down or (self.down_if is not None and self.down_if(self.calls))
        return json.dumps(DOWN if down else UP)


class Clock:
    """A clock that advances one second at every reading."""

    def __init__(self):
        self.now = 0.0

    def __call__(self):
        self.now += 1.0
        return self.now


class ScheduleRunnerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.corpus = root / 'corpus'
        self.corpus.mkdir()
        shutil.copy(CORPUS / 'scoring.py', self.corpus / 'scoring.py')
        (self.corpus / 'corpus-manifest.json').write_text('{"freeze": "test"}\n', encoding='utf-8')
        tasks = [task('P1'), task('P2'), task('P3', 'D', 'assets'), task('P4')]
        (self.corpus / 'dev.json').write_text(json.dumps({'tasks': tasks}), encoding='utf-8')
        self.root = root / 'results'
        FakeStack.log = []
        self.sessions = []

    def config(self, **over):
        scenarios = {name: {'mcp_url': name, 'stack': {}, 'warmup_calls': [{'tool': 'lookup', 'arguments': {}}], 'provenance': PROVENANCE,
                            'health': {'argv': ['health', name]}}
                     for name in ARMS + ['alpha']}
        base = {'scenarios': scenarios, 'models': ['model-a', 'model-b'], 'seed': 7, 'task_set': 'dev', 'warmup_passes': 1,
                'budgets': budgets(), 'limits': {'max_tool_calls': 5, 'retry_backoff_seconds': 0},
                'schedule': {'design': 'williams-4-half', 'arms': list(ARMS), 'reference': 'alpha'},
                'dataset_fingerprint': {'argv': ['fingerprint', '--db-password', 'hunter2hunter2']},
                'harness_tools': ['calculate', 'ask_requester']}
        base.update(over)
        return base

    def session_factory(self, scenario, run_id, tools=None):
        session = FakeToolSession(tools or [{'name': 'lookup', 'description': 'd', 'input_schema': {'type': 'object'}}], {'lookup': lambda a: '[1]'})
        self.sessions.append((scenario, run_id))
        return session

    def clients(self, steps_by_model=None):
        """Per model, the scripted steps first, then submissions of the right answer."""
        steps_by_model = steps_by_model or {}
        made = {}

        def factory(model):
            def answer(system, transcript, tools):
                return submit({'value': 'blue'})
            client = FakeVendorClient(list(steps_by_model.get(model, [])) + [answer] * 500, max_output_tokens=100, model=model)
            made[model] = client
            return client
        factory.made = made
        return factory

    def study(self, config=None, run_id='s2', factory=None, fingerprints=None, docker=None, session_factory=None, health=None, clock=None):
        return Study(config or self.config(), MODELS, PRICES, run_id, root=self.root, corpus_dir=self.corpus,
                     client_factory=factory or self.clients(), session_factory=session_factory or self.session_factory, stack_factory=FakeStack,
                     redactor=Redactor(['sk-ant-SECRETSECRETSECRET']), sleep=lambda s: None, docker=docker or fake_docker(),
                     fingerprint_runner=fingerprints or Fingerprints(), health_runner=health or Health(), **({'clock': clock} if clock else {}))

    def keys(self, study, block):
        return [key for _, key in study.block_keys(block)]

    def run_sessions(self, study):
        """The run keys in the order their sessions were opened (warm-up, readiness and tool-list sessions left out)."""
        keys = {key for block in study.plan['blocks'] for key in self.keys(study, block)}
        return [run_id for _, run_id in self.sessions if run_id in keys]

    # ------------------------------------------------------------------ the whole schedule
    def test_every_block_runs_in_schedule_order_with_its_checks_and_records(self):
        fingerprints = Fingerprints()
        study = self.study(fingerprints=fingerprints)
        self.assertEqual(study.run(), 'complete')
        blocks = study.plan['blocks']
        self.assertEqual([e[1] for e in FakeStack.log if e[0] == 'start'], [b['arm'] for b in blocks])
        self.assertEqual(len([e for e in FakeStack.log if e[0] == 'teardown']), 17)
        self.assertEqual(fingerprints.calls, 17)
        results = [json.loads(p.read_text()) for p in (study.dir / 'runs').glob('*/result.json')]
        self.assertEqual(len(results), 16 * 2 + 8)
        self.assertTrue(all(r['outcome'] == 'correct' for r in results))
        events = read_jsonl(study.dir / 'blocks.jsonl')
        self.assertEqual([e['block'] for e in events if e['event'] == 'start'], [b['id'] for b in blocks])
        self.assertEqual([e['block'] for e in events if e['event'] == 'end'], [b['id'] for b in blocks])
        self.assertTrue(all(e['session'] == 's-1' and e['fingerprint'] == 'fp-1' for e in events if e['event'] == 'start'))
        checks = read_jsonl(study.dir / 'provenance' / 'checks.jsonl')
        self.assertEqual([c['block'] for c in checks], [b['id'] for b in blocks])
        self.assertTrue(all(c['result'] == 'match' for c in checks))
        for block in blocks:
            self.assertEqual(json.loads((study.dir / 'provenance' / ('%s.json' % block['id'])).read_text())['block'], block['id'])
        bundle = json.loads((study.dir / 'bundle.json').read_text())
        self.assertIn('blocks.jsonl', bundle['files'])
        self.assertIn('provenance/%s.json' % blocks[0]['id'], bundle['files'])

    def test_each_run_records_its_block_and_round(self):
        study = self.study()
        study.run()
        block = next(b for b in study.plan['blocks'] if b['row'] == 3)
        for index, key in enumerate(self.keys(study, block), start=1):
            record = json.loads((study.dir / 'runs' / key / 'result.json').read_text())
            self.assertEqual((record['block'], record['row'], record['position'], record['half'], record['session']),
                             (block['id'], 3, block['position'], 'H1', 's-1'))
            self.assertEqual((record['orderInBlock'], record['requeued'], record['vendorErrors']), (index, False, 0))
            self.assertEqual(record['harnessToolCalls'], {'calculate': 0, 'calculateErrors': 0, 'askRequester': 0})
            self.assertNotIn('trial', record)
        header = (study.dir / 'scores.csv').read_text().splitlines()[0].split(',')
        for column in ('block', 'row', 'position', 'half', 'session', 'requeued', 'vendorErrors', 'calculateCalls', 'askRequesterCalls'):
            self.assertIn(column, header)

    def test_the_outage_service_is_stopped_around_each_of_its_runs(self):
        study = self.study()
        study.run()
        runs_of_p3 = sum(1 for b in study.plan['blocks'] for r in b['runs'] if r['task'] == 'P3')
        self.assertEqual(runs_of_p3, 4 * 2 + 2)
        self.assertEqual([e for e in FakeStack.log if e[0] in ('stop', 'restore')], [('stop', 'assets'), ('restore', 'assets')] * runs_of_p3)

    def test_the_manifest_records_the_schedule_tools_contract_and_fingerprint_command(self):
        study = self.study()
        study.run()
        text = (study.dir / 'manifest.json').read_text(encoding='utf-8')
        manifest = json.loads(text)
        self.assertEqual(manifest['schedule'], study.plan)
        self.assertEqual(manifest['identity']['plan'], study.plan)
        self.assertEqual(manifest['stackRunsPerBlock'], 1)
        self.assertNotIn('stackRunsPerScenario', manifest)
        self.assertEqual(manifest['vendorErrorRequeues'], 1)
        self.assertEqual(manifest['harnessTools']['names'], ['calculate', 'ask_requester'])
        self.assertEqual(manifest['scoringContract']['version'], 1)
        self.assertEqual(manifest['datasetFingerprint']['command']['argv'], ['fingerprint', '--db-password', provenance.MASK])
        self.assertNotIn('hunter2', text)
        self.assertEqual(sorted(manifest['provenance']['intended']), sorted(ARMS + ['alpha']))

    def test_each_run_stores_its_tool_results(self):
        steps = {'model-a': [turn('', [('t', 'lookup', {})]), turn('', [('c', 'calculate', {'operation': 'count', 'sources': [{'result_id': 'x'}]})])]}
        study = self.study(factory=self.clients(steps))
        study.run()
        first = next(r for b in study.plan['blocks'] for r, key in study.block_keys(b) if r['model'] == 'model-a')
        key = next(k for b in study.plan['blocks'] for r, k in study.block_keys(b) if r is first)
        stored = read_jsonl(study.dir / 'runs' / key / 'results.jsonl')
        self.assertEqual([s['tool'] for s in stored], ['lookup'])
        record = json.loads((study.dir / 'runs' / key / 'result.json').read_text())
        self.assertEqual(record['harnessToolCalls'], {'calculate': 1, 'calculateErrors': 1, 'askRequester': 0})
        self.assertEqual(record['toolCalls'], 2)
        tool_events = [e for e in read_jsonl(study.dir / 'runs' / key / 'transcript.jsonl') if e['kind'] == 'tool']
        self.assertTrue(tool_events[0]['text'].startswith('result_id: %s-1\n' % harness_tools.run_tag(key, 1)))
        self.assertIn('is not a result id', tool_events[1]['harness']['error'])

    def test_nothing_written_holds_a_key_the_stored_tool_results_included(self):
        secret = 'sk-ant-SECRETSECRETSECRET'

        def leaky(scenario, run_id):
            return FakeToolSession([{'name': 'lookup', 'description': 'd', 'input_schema': {'type': 'object'}}],
                                   {'lookup': lambda a: 'the service leaked ' + secret})
        steps = {'model-a': [turn('', [('t', 'lookup', {'q': secret})])]}
        study = self.study(factory=self.clients(steps), session_factory=leaky)
        study.run()
        self.assertTrue(any((study.dir / 'runs').glob('*/results.jsonl')))
        for path in study.dir.rglob('*'):
            if path.is_file():
                self.assertNotIn(secret, path.read_text(encoding='utf-8'), path.name)

    # ------------------------------------------------------------------ resume per block
    def test_a_stopped_study_resumes_inside_the_schedule_block_by_block(self):
        calls = {'n': 0}

        def killer(system, transcript, tools):
            calls['n'] += 1
            if calls['n'] == 5:
                raise RuntimeError('the process was killed')
            return submit({'value': 'blue'})

        def factory(model):
            return FakeVendorClient([killer] * 500, max_output_tokens=100, model=model)
        first = self.study(factory=factory)
        with self.assertRaisesRegex(RuntimeError, 'killed'):
            first.run()
        blocks = first.plan['blocks']
        done = {p.parent.name: p.read_text() for p in (first.dir / 'runs').glob('*/result.json')}
        self.assertEqual(len(done), 4)
        self.assertEqual(set(done), set(self.keys(first, blocks[0]) + self.keys(first, blocks[1])))
        FakeStack.log = []
        self.sessions = []
        second = self.study()
        self.assertEqual(second.run(resume=True), 'complete')
        self.assertEqual([e[1] for e in FakeStack.log if e[0] == 'start'], [b['arm'] for b in blocks[2:]])
        for key, text in done.items():
            self.assertEqual((second.dir / 'runs' / key / 'result.json').read_text(), text)
        killed = self.keys(second, blocks[2])[0]
        self.assertEqual(json.loads((second.dir / 'runs' / killed / 'result.json').read_text())['attempt'], 2)
        self.assertEqual(len(list((second.dir / 'runs').glob('*/result.json'))), 40)
        starts = [e for e in read_jsonl(second.dir / 'blocks.jsonl') if e['event'] == 'start' and e['block'] == blocks[2]['id']]
        self.assertEqual([s['start'] for s in starts], [1, 2])

    def test_a_budget_stop_resumes_at_its_block_without_repeating_finished_runs(self):
        config = self.config(budgets=budgets(vb=400))
        del config['harness_tools']
        first = self.study(config)
        self.assertEqual(first.run(), 'budget_stop')
        stopped = next(json.loads(p.read_text()) for p in (first.dir / 'runs').glob('*/result.json')
                       if json.loads(p.read_text())['outcome'] == 'budget_stop')
        finished = {p.parent.name: p.read_text() for p in (first.dir / 'runs').glob('*/result.json') if p.parent.name != stopped['runKey']}
        FakeStack.log = []
        config['budgets']['vb']['tokens'] = 10_000_000
        second = self.study(config)
        self.assertEqual(second.run(resume=True), 'complete')
        restarted = [e[1] for e in FakeStack.log if e[0] == 'start']
        index = [b['id'] for b in second.plan['blocks']].index(stopped['block'])
        self.assertEqual(restarted, [b['arm'] for b in second.plan['blocks'][index:]])
        for key, text in finished.items():
            self.assertEqual((second.dir / 'runs' / key / 'result.json').read_text(), text)

    def test_a_resume_refuses_a_changed_schedule(self):
        self.study().run()
        with self.assertRaisesRegex(RuntimeError, 'differ from the stored manifest'):
            self.study(self.config(schedule={'design': 'williams-4-half', 'arms': ['gamma', 'beta', 'delta', 'epsilon'], 'reference': 'alpha'},
                                   seed=8)).run(resume=True)
        with self.assertRaisesRegex(RuntimeError, 'differ from the stored manifest'):
            self.study(self.config(harness_tools=['calculate'])).run(resume=True)

    # ------------------------------------------------------------------ the dataset fingerprint
    def test_a_changed_fingerprint_refuses_its_block_before_any_run(self):
        fingerprints = Fingerprints({'fingerprint': 'fp-1', 'session': 's-1'}, {'fingerprint': 'fp-1', 'session': 's-1'},
                                    {'fingerprint': 'fp-2', 'session': 's-1'})
        study = self.study(fingerprints=fingerprints)
        with self.assertRaises(FingerprintRefused) as caught:
            study.run()
        third = study.plan['blocks'][2]
        self.assertEqual(caught.exception.block, third['id'])
        self.assertIn("differs from the study's first", str(caught.exception))
        self.assertIn('differs from the first of session s-1', str(caught.exception))
        self.assertFalse(any((study.dir / 'runs' / k).exists() for k in self.keys(study, third)))
        self.assertEqual(json.loads((study.dir / 'bundle.json').read_text())['status'], 'fingerprint_refused')
        refused = [e for e in read_jsonl(study.dir / 'blocks.jsonl') if e['event'] == 'refused']
        self.assertEqual([(e['block'], e['reason'], e['fingerprint']) for e in refused], [(third['id'], 'fingerprint', 'fp-2')])
        self.assertEqual(FakeStack.log[-1], ('teardown', third['arm']))
        # with the database back to its fingerprint, the resume continues at that block
        FakeStack.log = []
        again = self.study(fingerprints=Fingerprints())
        self.assertEqual(again.run(resume=True), 'complete')
        self.assertEqual([e[1] for e in FakeStack.log if e[0] == 'start'], [b['arm'] for b in again.plan['blocks'][2:]])

    def test_a_new_session_with_the_same_fingerprint_runs_and_is_recorded(self):
        fingerprints = Fingerprints({'fingerprint': 'fp-1', 'session': 's-1'}, {'fingerprint': 'fp-1', 'session': 's-1'},
                                    {'fingerprint': 'fp-1', 'session': 's-2'})
        study = self.study(fingerprints=fingerprints)
        self.assertEqual(study.run(), 'complete')
        sessions = [e['session'] for e in read_jsonl(study.dir / 'blocks.jsonl') if e['event'] == 'start']
        self.assertEqual(sessions, ['s-1', 's-1'] + ['s-2'] * 15)
        key = self.keys(study, study.plan['blocks'][2])[0]
        self.assertEqual(json.loads((study.dir / 'runs' / key / 'result.json').read_text())['session'], 's-2')

    def test_a_new_session_with_another_fingerprint_is_refused(self):
        fingerprints = Fingerprints({'fingerprint': 'fp-1', 'session': 's-1'}, {'fingerprint': 'fp-2', 'session': 's-2'})
        study = self.study(fingerprints=fingerprints)
        with self.assertRaisesRegex(FingerprintRefused, "differs from the study's first"):
            study.run()

    def test_an_unreadable_fingerprint_refuses_the_block(self):
        for reading in ('not json', '{"fingerprint": "fp-1"}', '{"fingerprint": "", "session": "s"}', RuntimeError('exited with 1')):
            with self.subTest(reading=reading):
                study = self.study(run_id='u%d' % abs(hash(str(reading))), fingerprints=Fingerprints(reading))
                with self.assertRaisesRegex(FingerprintRefused, 'could not be read'):
                    study.run()
                self.assertEqual(list((study.dir / 'runs').glob('*')) if (study.dir / 'runs').exists() else [], [])

    def test_parse_fingerprint(self):
        self.assertEqual(parse_fingerprint('{"fingerprint": "a", "session": "b", "rows": 3}\n'), {'fingerprint': 'a', 'session': 'b'})
        for bad in ('', '[]', '{"session": "b"}', '{"fingerprint": 1, "session": "b"}'):
            with self.assertRaises(ValueError):
                parse_fingerprint(bad)

    # ------------------------------------------------------------------ provenance per block
    def test_a_provenance_mismatch_at_a_later_block_refuses_that_block(self):
        docker = fake_docker()

        def change_image(call):
            if call == 1:  # after the first block's observation, the stack runs another image
                docker.containers[0]['Image'] = 'sha256:' + 'b' * 64
        study = self.study(docker=docker, fingerprints=Fingerprints(on_call=change_image))
        with self.assertRaises(provenance.ProvenanceRefused) as caught:
            study.run()
        second = study.plan['blocks'][1]
        self.assertIn('block %s' % second['id'], str(caught.exception))
        checks = read_jsonl(study.dir / 'provenance' / 'checks.jsonl')
        self.assertEqual([(c['block'], c['result']) for c in checks], [(study.plan['blocks'][0]['id'], 'match'), (second['id'], 'mismatch')])
        self.assertEqual(json.loads((study.dir / 'bundle.json').read_text())['status'], 'provenance_refused')
        self.assertEqual(len(list((study.dir / 'runs').glob('*/result.json'))), 2)

    # ------------------------------------------------------------------ vendor errors
    def first_block_models(self, study):
        return [r['model'] for r in study.plan['blocks'][0]['runs']]

    def test_a_vendor_error_is_queued_again_once_at_the_end_of_its_block(self):
        probe = self.study(run_id='probe')
        first_model = self.first_block_models(probe)[0]
        study = self.study(factory=self.clients({first_model: [VendorFatalError('bad request')]}))
        self.assertEqual(study.run(), 'complete')
        block = study.plan['blocks'][0]
        one, two = self.keys(study, block)
        self.assertEqual(self.run_sessions(study)[:4], [one, two, one, self.keys(study, study.plan['blocks'][1])[0]])
        record = json.loads((study.dir / 'runs' / one / 'result.json').read_text())
        self.assertEqual((record['outcome'], record['requeued'], record['vendorErrors'], record['attempt']), ('correct', True, 1, 2))
        self.assertEqual(json.loads((study.dir / 'runs' / one / 'attempts' / '001' / 'result.json').read_text())['outcome'], 'error')

    def test_a_second_vendor_error_is_recorded_as_it_is(self):
        probe = self.study(run_id='probe')
        first_model = self.first_block_models(probe)[0]
        study = self.study(factory=self.clients({first_model: [VendorFatalError('one'), VendorFatalError('two')]}))
        self.assertEqual(study.run(), 'complete')
        one = self.keys(study, study.plan['blocks'][0])[0]
        record = json.loads((study.dir / 'runs' / one / 'result.json').read_text())
        self.assertEqual((record['outcome'], record['requeued'], record['vendorErrors']), ('vendor_error', True, 2))
        row = next(r for r in read_jsonl(study.dir / 'scores.jsonl') if r['runKey'] == one)
        self.assertEqual((row['outcome'], row['score']), ('vendor_error', ''))
        end = next(e for e in read_jsonl(study.dir / 'blocks.jsonl') if e['event'] == 'end')
        self.assertEqual(end['outcomes'], {'correct': 1, 'vendor_error': 1})
        factory = self.clients()
        self.assertEqual(self.study(factory=factory).run(resume=True), 'complete')
        self.assertEqual(sum(len(c.calls) for c in factory.made.values()), 0)

    def test_the_requeue_survives_a_stop_of_the_study(self):
        probe = self.study(run_id='probe')
        models = self.first_block_models(probe)
        study = self.study(factory=self.clients({models[0]: [VendorFatalError('bad request')], models[1]: [RuntimeError('killed')]}))
        with self.assertRaisesRegex(RuntimeError, 'killed'):
            study.run()
        one, two = self.keys(study, study.plan['blocks'][0])
        self.assertEqual(json.loads((study.dir / 'runs' / one / 'result.json').read_text())['outcome'], 'error')
        self.sessions = []
        again = self.study()
        self.assertEqual(again.run(resume=True), 'complete')
        self.assertEqual(self.run_sessions(again)[:2], [two, one])
        record = json.loads((again.dir / 'runs' / one / 'result.json').read_text())
        self.assertEqual((record['outcome'], record['requeued'], record['vendorErrors']), ('correct', True, 1))

    # ------------------------------------------------------------------ tools and the scoring contract
    def test_a_scenario_tool_named_like_a_harness_tool_is_refused_before_any_run(self):
        factory = self.clients()

        def clashing(scenario, run_id):
            return self.session_factory(scenario, run_id, tools=[{'name': 'calculate', 'description': 'd', 'input_schema': {}}])
        with self.assertRaises(harness_tools.HarnessToolClash):
            self.study(factory=factory, session_factory=clashing).run()
        self.assertEqual(sum(len(c.calls) for c in factory.made.values()), 0)

    def test_a_version_2_scorer_gets_the_requester_log_and_may_return_abstained(self):
        (self.corpus / 'scoring.py').write_text(V2_SCORING, encoding='utf-8')
        config = self.config(scenario_order=['alpha'], trials=1)
        del config['schedule'], config['dataset_fingerprint']
        def ask_then_abstain(system, transcript, tools):
            if transcript[-1]['role'] == 'user':  # the start of a run: ask first
                return turn('', [('q', 'ask_requester', {'question': 'Which count?'})])
            return submit({'value': 'ABSTAIN'})
        study = self.study(config, factory=self.clients({'model-a': [ask_then_abstain] * 50}))
        self.assertEqual(study.run(), 'complete')
        records = {json.loads(p.read_text())['model']: json.loads(p.read_text()) for p in (study.dir / 'runs').glob('alpha__P1__*/result.json')}
        self.assertEqual(records['model-a']['outcome'], 'abstained')
        self.assertEqual(records['model-a']['askRequester'][0]['question'], 'Which count?')
        self.assertTrue(records['model-a']['score']['clarified'])
        self.assertEqual(records['model-b']['outcome'], 'correct')
        self.assertFalse(records['model-b']['score']['clarified'])
        rows = read_jsonl(study.dir / 'scores.jsonl')
        self.assertIn('clarified', rows[0])
        self.assertEqual({r['outcome'] for r in rows}, {'abstained', 'correct'})
        manifest = json.loads((study.dir / 'manifest.json').read_text())
        self.assertEqual(manifest['identity']['scoringContract'], 2)
        self.assertEqual(manifest['scoringContract']['version'], 2)
        factory = self.clients()
        self.assertEqual(self.study(config, factory=factory).run(resume=True), 'complete')  # abstained is a finished run
        self.assertEqual(sum(len(c.calls) for c in factory.made.values()), 0)

    def test_a_scorer_that_breaks_the_contract_stops_the_study(self):
        (self.corpus / 'scoring.py').write_text(BROKEN_SCORING, encoding='utf-8')
        study = self.study()
        with self.assertRaisesRegex(scoring_contract.ScoringContractError, 'maybe'):
            study.run()
        self.assertEqual(json.loads((study.dir / 'bundle.json').read_text())['status'], 'scoring_error')
        self.assertEqual(list((study.dir / 'runs').glob('*/result.json')), [])

    # ------------------------------------------------------------------ study 1 unchanged, and the config
    def test_a_study_1_config_keeps_its_exact_plan_identity(self):
        config = self.config(scenario_order=['alpha', 'beta'], trials=2)
        for name in ('schedule', 'dataset_fingerprint', 'harness_tools'):
            del config[name]
        study = self.study(config)
        identity = study.plan_identity()
        self.assertEqual(set(identity), {'plan', 'models', 'limits', 'systemPrompt', 'taskSet', 'trials', 'seed', 'guides', 'corpusFreeze',
                                         'pricesDated'})
        expected = {'plan': study.plan, 'models': MODELS['models'], 'limits': study.limits.as_dict(), 'systemPrompt': SYSTEM_PROMPT,
                    'taskSet': 'dev', 'trials': 2, 'seed': 7, 'guides': {'alpha': None, 'beta': None},
                    'corpusFreeze': sha256_file(self.corpus / 'corpus-manifest.json'), 'pricesDated': PRICES['dated']}
        self.assertEqual(sha256_json(identity), sha256_json(expected))
        self.assertIsInstance(study.plan, list)

    def test_load_config_needs_the_fingerprint_with_a_schedule_and_the_order_without(self):
        path = Path(self.tmp.name) / 'config.json'
        config = self.config()
        path.write_text(json.dumps(config), encoding='utf-8')
        self.assertEqual(load_config(path)['schedule']['design'], schedule.DESIGN)
        del config['dataset_fingerprint']
        path.write_text(json.dumps(config), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'dataset_fingerprint'):
            load_config(path)
        del config['schedule']
        path.write_text(json.dumps(config), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'scenario_order'):
            load_config(path)

    def test_a_schedule_without_a_fingerprint_command_or_with_a_bad_one_is_refused(self):
        for command, message in ((None, 'dataset_fingerprint'), ({'argv': []}, 'non-empty argv'), ({'argv': ['x'], 'shell': True}, 'unknown keys')):
            config = self.config(dataset_fingerprint=command)
            with self.assertRaisesRegex(ValueError, message):
                self.study(config)

    # ------------------------------------------------------------------ the void-block rule: attempts and health
    def events(self, study, kind=None):
        return [e for e in read_jsonl(study.dir / 'blocks.jsonl') if kind is None or e['event'] == kind]

    def outage_runs(self, block):
        return sum(1 for r in block['runs'] if r['task'] == 'P3')

    def test_health_is_checked_at_the_start_after_every_restore_every_n_runs_and_at_the_end(self):
        health = Health()
        study = self.study(self.config(health_every_runs=1), health=health)
        self.assertEqual(study.run(), 'complete')
        checks = read_jsonl(study.dir / 'health.jsonl')
        for block in study.plan['blocks']:
            points = [c['point'] for c in checks if c['block'] == block['id']]
            runs = len(block['runs'])
            self.assertEqual(points[0], 'start')
            self.assertEqual(points[-1], 'end')
            self.assertEqual(points.count('restore'), self.outage_runs(block))
            self.assertEqual(points.count('periodic'), runs - self.outage_runs(block), 'after an outage run the restore check stands for it')
        self.assertTrue(all(c['result'] == 'up' and c['attempt'] == 1 for c in checks))
        self.assertTrue(all(c['polls'] == 1 for c in checks if c['point'] == 'restore'))
        self.assertEqual(health.calls, len(checks))
        self.assertTrue(all(e['attempt'] == 1 for e in self.events(study)))
        for path in (study.dir / 'runs').glob('*/result.json'):
            self.assertEqual(json.loads(path.read_text())['blockAttempt'], 1)
        self.assertIn('blockAttempt', (study.dir / 'scores.csv').read_text().splitlines()[0].split(','))
        manifest = json.loads((study.dir / 'manifest.json').read_text())
        self.assertEqual(manifest['voidRule']['healthEveryRuns'], 1)
        self.assertEqual(manifest['identity']['voidRule']['health']['alpha']['argv'], ['health', 'alpha'])
        self.assertEqual(sorted(manifest['voidRule']['triggers']), ['health', 'provenance', 'restore'])

    def test_the_health_interval_defaults_to_ten_runs_and_a_resume_cannot_change_it(self):
        study = self.study()
        self.assertEqual(study.health_every, 10)
        study.run()
        self.assertEqual(json.loads((study.dir / 'manifest.json').read_text())['voidRule']['healthEveryRuns'], 10)
        with self.assertRaisesRegex(RuntimeError, 'differ from the stored manifest'):
            self.study(self.config(health_every_runs=5)).run(resume=True)
        for bad in (0, -1, 2.5, True, '10'):
            with self.assertRaisesRegex(ValueError, 'health_every_runs'):
                self.study(self.config(health_every_runs=bad))

    def test_a_schedule_needs_a_health_command_for_every_arm(self):
        config = self.config()
        del config['scenarios']['gamma']['health']
        with self.assertRaisesRegex(ValueError, 'scenarios.gamma.health'):
            self.study(config)

    def test_a_backend_down_at_the_block_end_voids_the_attempt_and_the_resume_repeats_it_whole(self):
        probe = self.study(run_id='probe')
        first = probe.plan['blocks'][0]
        end_call = 2 + self.outage_runs(first)  # start, one restore per outage run, end
        study = self.study(health=Health(down={end_call}))
        self.assertEqual(study.run(), 'block_void')
        keys = self.keys(study, first)
        void = self.events(study, 'void')
        self.assertEqual(len(void), 1)
        self.assertEqual((void[0]['block'], void[0]['attempt'], void[0]['trigger'], void[0]['point']), (first['id'], 1, 'health', 'end'))
        self.assertIn('backend missions is down: connection refused', void[0]['problems'])
        self.assertEqual(sorted(void[0]['runs']), sorted(keys))
        for key in keys:
            self.assertFalse((study.dir / 'runs' / key).exists(), 'no void result stays a run\'s current result')
            moved = json.loads((study.dir / 'runs-void' / first['id'] / '1' / key / 'result.json').read_text())
            self.assertEqual(moved['blockAttempt'], 1)
        self.assertEqual(read_jsonl(study.dir / 'scores.jsonl'), [])
        bundle = json.loads((study.dir / 'bundle.json').read_text())
        self.assertEqual(bundle['status'], 'block_void')
        self.assertEqual([a['block'] for a in bundle['voidAttempts']['attempts']], [first['id']])
        self.assertEqual(sum(v['runs'] for v in bundle['voidAttempts']['spend'].values()), len(keys))
        self.assertGreater(sum(v['dollars'] for v in bundle['voidAttempts']['spend'].values()), 0)
        self.assertIn('runs-void/%s/1/%s/result.json' % (first['id'], keys[0]), bundle['files'])
        self.assertNotIn('end', [e['event'] for e in self.events(study) if e['block'] == first['id']])
        self.assertEqual(FakeStack.log[-1], ('teardown', first['arm']))
        ledgers = {p.name: p.read_text() for p in study.dir.glob('budget-*.jsonl')}
        self.assertTrue(ledgers, 'the void attempt was billed and stays in the ledgers')
        # the resume repeats the block whole as attempt 2
        FakeStack.log = []
        self.sessions = []
        again = self.study()
        self.assertEqual(again.run(resume=True), 'complete')
        self.assertEqual([e[1] for e in FakeStack.log if e[0] == 'start'], [b['arm'] for b in again.plan['blocks']])
        self.assertEqual(self.run_sessions(again)[:len(keys)], keys)
        starts = [e for e in self.events(again, 'start') if e['block'] == first['id']]
        self.assertEqual([(s['attempt'], s['runsFinishedBefore']) for s in starts], [(1, 0), (2, 0)])
        ends = [e for e in self.events(again, 'end') if e['block'] == first['id']]
        self.assertEqual([e['attempt'] for e in ends], [2])
        for key in keys:
            record = json.loads((again.dir / 'runs' / key / 'result.json').read_text())
            self.assertEqual((record['blockAttempt'], record['attempt']), (2, 1))
        self.assertTrue(all(e['attempt'] == 1 for e in self.events(again) if e['block'] != first['id']))
        self.assertEqual(len(list((again.dir / 'runs').glob('*/result.json'))), 40)
        self.assertEqual(json.loads((again.dir / 'bundle.json').read_text())['voidAttempts']['attempts'][0]['attempt'], 1)

    def test_a_backend_down_at_the_block_start_voids_an_attempt_that_ran_nothing(self):
        study = self.study(health=Health(down={1}))
        self.assertEqual(study.run(), 'block_void')
        first = study.plan['blocks'][0]
        void = self.events(study, 'void')[0]
        self.assertEqual((void['attempt'], void['point'], void['runs'], void['spend']), (1, 'start', [], {}))
        self.assertEqual(list((study.dir / 'runs').glob('*')) if (study.dir / 'runs').exists() else [], [])
        self.assertEqual(sum(len(c.calls) for c in study.clients.values()), 0, 'no paid request in a block found down at its start')
        self.assertIn('attempt 1, is void', str(study.void))
        self.assertEqual(self.study().run(resume=True), 'complete')
        starts = [e['attempt'] for e in read_jsonl(study.dir / 'blocks.jsonl') if e['event'] == 'start' and e['block'] == first['id']]
        self.assertEqual(starts, [1, 2])

    def test_a_backend_down_every_n_runs_voids_the_attempt(self):
        config = self.config(health_every_runs=1)
        probe = self.study(config, run_id='probe')
        first = probe.plan['blocks'][0]
        if first['runs'][0]['task'] == 'P3':
            self.skipTest('the first run of this schedule is an outage run')
        study = self.study(config, health=Health(down={2}))
        self.assertEqual(study.run(), 'block_void')
        void = self.events(study, 'void')[0]
        self.assertEqual((void['trigger'], void['point']), ('health', 'periodic'))
        self.assertEqual(void['runs'], self.keys(study, first)[:1])
        periodic = [c for c in read_jsonl(study.dir / 'health.jsonl') if c['point'] == 'periodic']
        self.assertEqual((periodic[0]['result'], periodic[0]['afterRun']), ('down', void['runs'][0]))

    def test_an_unreadable_health_check_is_a_void_trigger(self):
        for reading in ('not json', '{"backends": {}}', '{"backends": {"missions": {"up": "yes"}}}', RuntimeError('exited with 2')):
            with self.subTest(reading=reading):
                study = self.study(run_id='h%d' % abs(hash(str(reading))), health=Health(reading=reading))
                self.assertEqual(study.run(), 'block_void')
                void = self.events(study, 'void')[0]
                self.assertEqual(void['point'], 'start')
                self.assertIn('could not be read', void['problems'][0])
                self.assertEqual(read_jsonl(study.dir / 'health.jsonl')[0]['result'], 'unreadable')

    def outage_block(self, study):
        return next(b for b in study.plan['blocks'] if any(r['task'] == 'P3' for r in b['runs']))

    def test_a_restore_waits_for_every_backend_and_records_its_polls(self):
        config = self.config()
        state = {'restore': None, 'polls': 0}

        def down_after_restore(call):
            log = FakeStack.log
            if len(log) >= 2 and log[-2] == ('restore', 'assets') and state['restore'] != len(log):
                state['polls'] += 1
                if state['polls'] <= 2:  # two polls down after each restore, then up
                    return True
                state.update(restore=len(log), polls=0)
            return False
        study = self.study(config, health=Health(down_if=down_after_restore), clock=Clock())
        self.assertEqual(study.run(), 'complete')
        restores = [c for c in read_jsonl(study.dir / 'health.jsonl') if c['point'] == 'restore']
        self.assertTrue(restores and all(c['result'] == 'up' and c['polls'] == 3 for c in restores))

    def test_a_restore_that_does_not_come_back_in_time_voids_the_attempt(self):
        config = self.config()
        for scenario in config['scenarios'].values():
            scenario['ready_timeout_seconds'] = 5
        study = self.study(config, health=Health(down_if=lambda call: len(FakeStack.log) >= 2 and FakeStack.log[-2] == ('restore', 'assets')),
                           clock=Clock())
        self.assertEqual(study.run(), 'block_void')
        block = self.outage_block(study)
        void = self.events(study, 'void')[0]
        self.assertEqual((void['block'], void['trigger'], void['point']), (block['id'], 'restore', 'restore'))
        self.assertIn('within 5 seconds', void['problems'][0])
        last = [c for c in read_jsonl(study.dir / 'health.jsonl') if c['point'] == 'restore'][-1]
        self.assertEqual(last['result'], 'down')
        self.assertGreater(last['polls'], 1)
        self.assertIn(last['afterRun'], void['runs'])

    def test_a_backend_down_in_the_provenance_observation_is_a_void_trigger_and_a_wrong_backend_is_still_refused(self):
        docker = fake_docker()
        docker.containers[0]['State'] = {'Status': 'exited'}
        study = self.study(docker=docker)
        self.assertEqual(study.run(), 'block_void')
        void = self.events(study, 'void')[0]
        self.assertEqual((void['trigger'], void['point'], void['attempt']), ('provenance', 'start', 1))
        self.assertIn('not running', void['problems'][0])
        self.assertEqual(read_jsonl(study.dir / 'provenance' / 'checks.jsonl')[-1]['result'], 'down')
        docker = fake_docker()
        docker.containers[0]['State'] = {'Status': 'exited'}
        docker.containers[0]['Image'] = 'sha256:' + 'c' * 64
        with self.assertRaises(provenance.ProvenanceRefused):
            self.study(run_id='wrong', docker=docker).run()

    def test_an_interrupted_move_of_a_void_attempt_is_finished_by_the_resume(self):
        probe = self.study(run_id='probe')
        first = probe.plan['blocks'][0]
        study = self.study(health=Health(down={2 + self.outage_runs(first)}))
        self.assertEqual(study.run(), 'block_void')
        key = self.keys(study, first)[0]
        shutil.move(str(study.dir / 'runs-void' / first['id'] / '1' / key), str(study.dir / 'runs' / key))  # as if the move was cut short
        self.assertEqual(self.study().run(resume=True), 'complete')
        self.assertTrue((study.dir / 'runs-void' / first['id'] / '1' / key / 'result.json').exists())
        self.assertEqual(json.loads((study.dir / 'runs' / key / 'result.json').read_text())['blockAttempt'], 2)

    def test_a_resume_after_a_repeated_block_leaves_the_repeat_alone(self):
        probe = self.study(run_id='probe')
        first = probe.plan['blocks'][0]
        study = self.study(health=Health(down={2 + self.outage_runs(first)}))
        self.assertEqual(study.run(), 'block_void')
        self.assertEqual(self.study().run(resume=True), 'complete')
        repeat = {k: (study.dir / 'runs' / k / 'result.json').read_text() for k in self.keys(study, first)}
        FakeStack.log = []
        factory = self.clients()
        self.assertEqual(self.study(factory=factory).run(resume=True), 'complete', 'a second resume after the repeat runs nothing')
        self.assertEqual([e for e in FakeStack.log if e[0] == 'start'], [])
        self.assertEqual(sum(len(c.calls) for c in factory.made.values()), 0)
        for key, text in repeat.items():
            self.assertEqual((study.dir / 'runs' / key / 'result.json').read_text(), text)
        self.assertEqual(sorted(p.name for p in (study.dir / 'runs-void' / first['id'] / '1').iterdir()), sorted(repeat))

    def test_an_in_flight_folder_of_the_repeat_is_not_taken_for_the_void_attempt(self):
        probe = self.study(run_id='probe')
        first = probe.plan['blocks'][0]
        study = self.study(health=Health(down={2 + self.outage_runs(first)}))
        self.assertEqual(study.run(), 'block_void')
        key = self.keys(study, first)[0]

        def killer(system, transcript, tools):
            raise RuntimeError('the process was killed')
        with self.assertRaisesRegex(RuntimeError, 'killed'):  # attempt 2 starts and dies inside its first run
            self.study(factory=lambda model: FakeVendorClient([killer] * 5, max_output_tokens=100, model=model)).run(resume=True)
        self.assertTrue((study.dir / 'runs' / key).exists())
        self.assertEqual(self.study().run(resume=True), 'complete')
        self.assertEqual(json.loads((study.dir / 'runs' / key / 'result.json').read_text())['blockAttempt'], 2)

    def test_a_restore_that_answers_only_after_its_deadline_voids_the_attempt(self):
        config = self.config()
        for scenario in config['scenarios'].values():
            scenario['ready_timeout_seconds'] = 5
        clock = Clock()

        def slow_after_restore(call):
            if len(FakeStack.log) >= 2 and FakeStack.log[-2] == ('restore', 'assets'):
                clock.now += 20  # the probe answers healthy, twenty seconds later
        health = Health(on_call=slow_after_restore)
        study = self.study(config, health=health, clock=clock)
        self.assertEqual(study.run(), 'block_void')
        void = self.events(study, 'void')[0]
        self.assertEqual((void['trigger'], void['point']), ('restore', 'restore'))
        self.assertIn('only after the deadline', void['problems'][0])
        restore = [c for c in read_jsonl(study.dir / 'health.jsonl') if c['point'] == 'restore'][-1]
        self.assertEqual(restore['result'], 'down')
        timeouts = [t for t in health.timeouts if t is not None]
        self.assertTrue(timeouts and all(0 < t <= 5 for t in timeouts), 'the restore probe gets the rest of the deadline')

    def test_a_missing_backend_with_its_declared_endpoint_is_a_void_trigger(self):
        prov = dict(PROVENANCE, routing={'endpoints': {'http://127.0.0.1:8083/': 'missions-stub'}})
        config = self.config()
        for scenario in config['scenarios'].values():
            scenario['provenance'] = prov
        study = self.study(config, docker=FakeDocker([]))
        self.assertEqual(study.run(), 'block_void')
        void = self.events(study, 'void')[0]
        self.assertEqual(void['trigger'], 'provenance')
        self.assertTrue(any(p.startswith('endpoint ') for p in void['problems']))
        # an endpoint of a service that is no backend still refuses the block
        prov = dict(PROVENANCE, routing={'endpoints': {'http://127.0.0.1:8170/': 'router'}})
        config = self.config()
        for scenario in config['scenarios'].values():
            scenario['provenance'] = prov
        with self.assertRaises(provenance.ProvenanceRefused):
            self.study(config, run_id='router', docker=FakeDocker([])).run()

    def test_a_finished_block_whose_attempt_did_not_end_is_run_again_to_its_end(self):
        study = self.study()
        study.run()
        first = study.plan['blocks'][0]
        lines = (study.dir / 'blocks.jsonl').read_text().splitlines()
        index = next(i for i, line in enumerate(lines) if json.loads(line)['event'] == 'end' and json.loads(line)['block'] == first['id'])
        (study.dir / 'blocks.jsonl').write_text('\n'.join(lines[:index] + lines[index + 1:]) + '\n')
        FakeStack.log = []
        factory = self.clients()
        self.assertEqual(self.study(factory=factory).run(resume=True), 'complete')
        self.assertEqual([e[1] for e in FakeStack.log if e[0] == 'start'], [first['arm']])
        self.assertEqual(sum(len(c.calls) for c in factory.made.values()), 0)
        self.assertEqual(sum(1 for e in self.events(study, 'end') if e['block'] == first['id']), 1)

    def test_the_corpus_comes_from_the_option_or_the_config(self):
        corpus2 = runner_module.HERE.parent / 'corpus2'
        self.assertEqual(runner_module.corpus_of({}), runner_module.DEFAULT_CORPUS)
        self.assertEqual(runner_module.corpus_of({'corpus_dir': str(corpus2)}), corpus2)
        self.assertEqual(runner_module.corpus_of({}, str(corpus2)), corpus2)
        self.assertEqual(runner_module.corpus_of({'corpus_dir': str(corpus2)}, str(corpus2)), corpus2)
        with self.assertRaisesRegex(ValueError, 'differs from the config'):
            runner_module.corpus_of({'corpus_dir': str(corpus2)}, str(runner_module.DEFAULT_CORPUS))

    # ------------------------------------------------------------------ the budget across study runs
    def earlier_run(self, run_id='old', output_tokens=1_000_000, unsettled=0):
        folder = self.root / run_id
        folder.mkdir(parents=True)
        (folder / 'manifest.json').write_text(json.dumps({'models': {'model-a': {'vendor': 'va', 'priceEntry': PRICES['models']['model-a']},
                                                                     'model-b': {'vendor': 'vb', 'priceEntry': PRICES['models']['model-b']}}}))
        lines = [{'event': 'reserve', 'seq': 1, 'tokens': 10}, {'event': 'settle', 'seq': 1, 'usage': {'output': output_tokens}}]
        if unsettled:
            lines.append({'event': 'reserve', 'seq': 2, 'tokens': unsettled})
        (folder / 'budget-va.jsonl').write_text(''.join(json.dumps(line) + '\n' for line in lines))
        return folder

    def test_the_earlier_runs_spend_counts_against_the_ceiling_and_is_recorded(self):
        self.earlier_run(output_tokens=1_000_000, unsettled=100_000)  # 10 dollars settled, 1 dollar unsettled at the output price
        study = self.study(self.config(earlier_study_runs=['old']))
        self.assertEqual(study.run(), 'complete')
        manifest = json.loads((study.dir / 'manifest.json').read_text())
        carry = manifest['budgetCarry']
        self.assertEqual(manifest['identity']['earlierStudyRuns'], ['old'])
        self.assertEqual(carry['runs'][0]['runId'], 'old')
        self.assertEqual(carry['runs'][0]['ledgers']['va']['sha256'], sha256_file(self.root / 'old' / 'budget-va.jsonl'))
        self.assertAlmostEqual(carry['totals']['va'], 11.0)
        self.assertNotIn('vb', carry['totals'])
        bundle = json.loads((study.dir / 'bundle.json').read_text())
        self.assertAlmostEqual(bundle['budgets']['va']['carriedDollars'], 11.0)
        self.assertEqual(bundle['budgets']['vb']['carriedDollars'], 0.0)
        self.assertEqual(bundle['budgets']['va']['dollarCeiling'], 85.0)

    def test_the_carried_spend_can_stop_the_run_at_the_ceiling(self):
        self.earlier_run(output_tokens=1_000_000)
        config = self.config(earlier_study_runs=['old'], budgets=budgets(ceiling=10.0005))
        study = self.study(config)
        self.assertEqual(study.run(), 'budget_stop')
        stopped = next(json.loads(p.read_text()) for p in (study.dir / 'runs').glob('*/result.json'))
        self.assertEqual(stopped['model'], 'model-a')
        self.assertIn('carried from earlier study runs', stopped['reason'] + json.dumps(stopped))

    def test_a_listed_earlier_run_that_is_missing_refuses_the_start(self):
        with self.assertRaisesRegex(BudgetCarryRefused, 'nowhere'):
            self.study(self.config(earlier_study_runs=['nowhere'])).run()
        self.assertFalse((self.root / 's2').exists())
        with self.assertRaisesRegex(ValueError, 'itself'):
            self.study(self.config(earlier_study_runs=['s2']))
        with self.assertRaisesRegex(ValueError, 'distinct'):
            self.study(self.config(earlier_study_runs=['a', 'a']))

    def test_a_changed_earlier_ledger_refuses_the_resume(self):
        folder = self.earlier_run()
        config = self.config(earlier_study_runs=['old'], budgets=budgets(vb=400))
        self.assertEqual(self.study(config).run(), 'budget_stop')
        with open(folder / 'budget-va.jsonl', 'a') as handle:
            handle.write(json.dumps({'event': 'reserve', 'seq': 9, 'tokens': 5}) + '\n')
        config['budgets']['vb']['tokens'] = 10_000_000
        with self.assertRaisesRegex(BudgetCarryRefused, 'old \\(va\\)'):
            self.study(config).run(resume=True)

    def test_every_vendor_budget_needs_its_ceiling_and_basis(self):
        for change, message in ((lambda b: b['va'].pop('ceiling_basis'), 'ceiling_basis'), (lambda b: b['vb'].update(ceiling_basis=' '), 'ceiling_basis'),
                                (lambda b: b['va'].pop('dollar_ceiling'), 'dollar_ceiling'), (lambda b: b['va'].update(dollar_ceiling=0), 'dollar_ceiling')):
            config = self.config()
            change(config['budgets'])
            with self.assertRaisesRegex(ValueError, message):
                self.study(config)

    def test_a_resume_with_another_ceiling_records_the_old_and_new_values(self):
        config = self.config(budgets=budgets(vb=400))
        self.assertEqual(self.study(config).run(), 'budget_stop')
        config['budgets']['vb']['tokens'] = 10_000_000
        config['budgets']['va']['dollar_ceiling'] = 95.0
        with self.assertRaisesRegex(RuntimeError, 'needs its basis'):
            self.study(config).run(resume=True)
        config['budgets']['va']['ceiling_basis'] = "the lead developer's raise of 2026-11-05"
        study = self.study(config)
        self.assertEqual(study.run(resume=True), 'complete')
        resumes = read_jsonl(study.dir / 'resumes.jsonl')
        self.assertEqual(len(resumes), 1)
        self.assertEqual(resumes[0]['ceilingChanges'], [{'vendor': 'va', 'old': {'dollar_ceiling': 85.0, 'ceiling_basis': 'decision D (2026-10-27)'},
                                                         'new': {'dollar_ceiling': 95.0,
                                                                 'ceiling_basis': "the lead developer's raise of 2026-11-05"}}])
        self.assertEqual(resumes[0]['ceilings']['va']['dollar_ceiling'], 95.0)


if __name__ == '__main__':
    unittest.main()
