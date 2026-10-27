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
from fakes import FakeVendorClient, submit, turn
from mcp_client import FakeToolSession
from runner import SYSTEM_PROMPT, FingerprintRefused, Study, load_config, parse_fingerprint
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
        scenarios = {name: {'mcp_url': name, 'stack': {}, 'warmup_calls': [{'tool': 'lookup', 'arguments': {}}], 'provenance': PROVENANCE}
                     for name in ARMS + ['alpha']}
        base = {'scenarios': scenarios, 'models': ['model-a', 'model-b'], 'seed': 7, 'task_set': 'dev', 'warmup_passes': 1,
                'budgets': {'va': {'tokens': 10_000_000}, 'vb': {'tokens': 10_000_000}}, 'limits': {'max_tool_calls': 5, 'retry_backoff_seconds': 0},
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

    def study(self, config=None, run_id='s2', factory=None, fingerprints=None, docker=None, session_factory=None):
        return Study(config or self.config(), MODELS, PRICES, run_id, root=self.root, corpus_dir=self.corpus,
                     client_factory=factory or self.clients(), session_factory=session_factory or self.session_factory, stack_factory=FakeStack,
                     redactor=Redactor(['sk-ant-SECRETSECRETSECRET']), sleep=lambda s: None, docker=docker or fake_docker(),
                     fingerprint_runner=fingerprints or Fingerprints())

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
        config = self.config(budgets={'va': {'tokens': 10_000_000}, 'vb': {'tokens': 400}})
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


if __name__ == '__main__':
    unittest.main()
