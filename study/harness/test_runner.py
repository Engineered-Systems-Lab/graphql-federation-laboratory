"""Tests of the run protocol with a fake stack, fake MCP sessions and fake vendor clients: the plan, the split-plot order, results saved at once,
the budget stop and the resume, the service stops, the manifest and the bundle. No real model call, no stack, no key."""
import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from fakes import FakeDocker, FakeVendorClient, container, submit, turn
from mcp_client import FakeToolSession
from runner import Study, build_plan, load_tasks, run_key
from study_common import Redactor, child_environment, read_jsonl, sha256_file

CORPUS = Path(__file__).resolve().parent.parent / 'corpus'
SCHEMA = {'type': 'object', 'additionalProperties': False, 'properties': {'value': {'type': 'string'}}, 'required': ['value']}


def task(task_id, category='A', stopped=None):
    return {'id': task_id, 'category': category, 'question': 'invented question ' + task_id, 'schema': SCHEMA, 'stoppedService': stopped,
            'expected': {'taskId': task_id, 'checks': [{'op': 'scalar', 'path': 'value', 'spec': {'equals': 'blue'}}]}}


MODELS = {'models': {'model-a': {'vendor': 'va', 'request': {}, 'max_output_tokens': 100}, 'model-b': {'vendor': 'vb', 'request': {}, 'max_output_tokens': 100}}}
PRICES = {'dated': '2026-10-20', 'models': {m: {'input': 2.0, 'cached_read': 0.2, 'cache_write': 2.5, 'output': 10.0} for m in ('model-a', 'model-b')}}
STUB_ID = 'sha256:' + 'a' * 64
PROVENANCE = {'compose_projects': ['lab'], 'backends': {'missions': {'mode': 'simulated', 'service': 'missions-stub', 'image_id': STUB_ID}}}


def fake_docker():
    """The scripted stack every scenario of these tests declares: one simulated Missions backend."""
    return FakeDocker([container('lab', 'missions-stub', 'stub:1', STUB_ID)])


class FakeStack:
    log = []

    def __init__(self, scenario):
        self.scenario = scenario

    def start(self):
        self.log.append(('start', self.scenario))

    def wait_ready(self, run_id, timeout):
        self.log.append(('ready', self.scenario))

    def stop_service(self, name):
        self.log.append(('stop', name))

    def start_service(self, name):
        self.log.append(('restore', name))

    def teardown(self):
        self.log.append(('teardown', self.scenario))


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.corpus = root / 'corpus'
        self.corpus.mkdir()
        shutil.copy(CORPUS / 'scoring.py', self.corpus / 'scoring.py')
        (self.corpus / 'corpus-manifest.json').write_text('{"freeze": "test"}\n', encoding='utf-8')
        self.write_dev([task('P1'), task('P2'), task('P3', 'D', 'assets'), task('P4')])
        self.root = root / 'results'
        FakeStack.log = []
        self.sessions = []

    def write_dev(self, tasks):
        (self.corpus / 'dev.json').write_text(json.dumps({'tasks': [{k: v for k, v in t.items()} for t in tasks]}), encoding='utf-8')

    def config(self, **over):
        base = {'scenarios': {'alpha': {'mcp_url': 'x', 'stack': {}, 'warmup_calls': [{'tool': 'lookup', 'arguments': {}}], 'provenance': PROVENANCE},
                              'beta': {'mcp_url': 'y', 'stack': {}, 'guide_file': str(self.guide()), 'provenance': PROVENANCE}},
                'scenario_order': ['alpha', 'beta'], 'models': ['model-a', 'model-b'], 'trials': 2, 'seed': 7, 'task_set': 'dev',
                'warmup_passes': 2, 'budgets': {'va': {'tokens': 1_000_000}, 'vb': {'tokens': 1_000_000}},
                'limits': {'max_tool_calls': 5, 'retry_backoff_seconds': 0}, 'telemetry': {'apollo': 'off', 'cosmo': 'off'},
                'declared_settings': {'apollo_introspection': True}}
        base.update(over)
        return base

    def guide(self):
        path = Path(self.tmp.name) / 'guide.md'
        path.write_text('A guide.\n', encoding='utf-8')
        return path

    def session_factory(self, scenario, run_id):
        session = FakeToolSession([{'name': 'lookup', 'description': 'd', 'input_schema': {'type': 'object'}}], {'lookup': lambda a: 'ok'})
        self.sessions.append((scenario, run_id))
        return session

    def clients(self, answer_by_model=None, fail_after=None):
        answers = answer_by_model or {}
        made = {}

        def factory(model):
            def step(system, transcript, tools):
                return submit({'value': answers.get(model, 'blue')})
            client = FakeVendorClient([step] * 500, max_output_tokens=100, model=model)
            made[model] = client
            return client
        factory.made = made
        return factory

    def study(self, config=None, run_id='r1', factory=None, **kw):
        return Study(config or self.config(), MODELS, PRICES, run_id, root=self.root, corpus_dir=self.corpus,
                     client_factory=factory or self.clients(), session_factory=self.session_factory, stack_factory=FakeStack,
                     redactor=Redactor(['sk-ant-SECRETSECRETSECRET']), sleep=lambda s: None, docker=kw.pop('docker', fake_docker()), **kw)

    # ------------------------------------------------------------------ the plan
    def test_plan_is_deterministic_and_models_are_counterbalanced(self):
        tasks = load_tasks(self.corpus, 'dev')
        one, two = build_plan(self.config(), tasks), build_plan(self.config(), tasks)
        self.assertEqual(one, two)
        self.assertEqual([p['scenario'] for p in one], ['alpha', 'beta'])
        for scenario in one:
            self.assertEqual(len(scenario['units']), 8)
            firsts = [u['models'][0] for u in scenario['units']]
            self.assertEqual(firsts.count('model-a'), firsts.count('model-b'))
            for unit in scenario['units']:
                self.assertEqual(sorted(unit['models']), ['model-a', 'model-b'])
        self.assertNotEqual([u['task'] for u in one[0]['units']], [u['task'] for u in one[1]['units']] * 1 or None)
        changed = build_plan(self.config(seed=8), tasks)
        self.assertNotEqual(one, changed)

    # ------------------------------------------------------------------ a whole study
    def test_one_stack_run_per_scenario_with_the_models_nested(self):
        study = self.study()
        self.assertEqual(study.run(), 'complete')
        starts = [e for e in FakeStack.log if e[0] == 'start']
        self.assertEqual(starts, [('start', 'alpha'), ('start', 'beta')])
        results = sorted((study.dir / 'runs').glob('*/result.json'))
        self.assertEqual(len(results), 2 * 4 * 2 * 2)  # scenarios x tasks x models x trials
        scores = read_jsonl(study.dir / 'scores.jsonl')
        self.assertTrue(all(row['outcome'] == 'correct' and row['score'] == 1 for row in scores))
        self.assertTrue((study.dir / 'scores.csv').exists())
        # models are interleaved per task: consecutive runs of one scenario alternate vendors within a unit
        order = [json.loads(p.read_text())['model'] for p in sorted((study.dir / 'runs').glob('alpha__*/result.json'), key=lambda p: json.loads(p.read_text())['finishedAt'])]
        self.assertEqual(order.count('model-a'), order.count('model-b'))

    def test_phase_labelled_samples(self):
        study = self.study()
        study.run()
        samples = read_jsonl(study.dir / 'samples.jsonl')
        phases = {s['phase'] for s in samples}
        self.assertEqual(phases, {'cold', 'warm-up', 'measurement'})
        self.assertEqual([s['kind'] for s in samples if s['phase'] == 'cold' and s['scenario'] == 'alpha'], ['cold_start', 'cold_first_request'])
        self.assertEqual(sum(1 for s in samples if s['kind'] == 'warmup_call' and s['scenario'] == 'alpha'), 1)  # 2 passes x 1 call - the cold one

    def test_the_stopped_service_is_restored_around_the_honesty_task(self):
        study = self.study()
        study.run()
        stops = [e for e in FakeStack.log if e[0] in ('stop', 'restore')]
        self.assertEqual(stops, [('stop', 'assets'), ('restore', 'assets')] * 4)  # two trials x two scenarios
        self.assertEqual(FakeStack.log[-1], ('teardown', 'beta'))

    def test_beta_gets_the_guide_in_its_prompt_and_alpha_does_not(self):
        factory = self.clients()
        study = self.study(factory=factory)
        study.run()
        systems = {s for c in factory.made.values() for s, _, _ in c.calls}
        self.assertEqual(len(systems), 2)
        self.assertTrue(any('A guide.' in s for s in systems))
        self.assertTrue(any('A guide.' not in s for s in systems))

    def test_session_carries_the_run_key_for_the_server_log(self):
        self.study().run()
        keys = {run_id for _, run_id in self.sessions}
        self.assertIn(run_key('alpha', 'P1', 'model-a', 1), keys)

    # ------------------------------------------------------------------ budget stop and resume
    def test_budget_stop_keeps_completed_runs_and_a_resume_runs_only_the_rest(self):
        config = self.config(budgets={'va': {'tokens': 1_000_000}, 'vb': {'tokens': 400}})  # a few runs fit, then the vendor b budget ends
        first = self.study(config)
        self.assertEqual(first.run(), 'budget_stop')
        done = {p.parent.name: json.loads(p.read_text())['outcome'] for p in (first.dir / 'runs').glob('*/result.json')}
        stopped = [k for k, o in done.items() if o == 'budget_stop']
        completed = [k for k, o in done.items() if o != 'budget_stop']
        self.assertEqual(len(stopped), 1)
        self.assertGreater(len(completed), 0)
        before = {k: (first.dir / 'runs' / k / 'result.json').read_text() for k in completed}
        bundle = json.loads((first.dir / 'bundle.json').read_text())
        self.assertEqual(bundle['status'], 'budget_stop')
        # resume with a larger budget
        config['budgets']['vb']['tokens'] = 1_000_000
        second = self.study(config)
        self.assertEqual(second.run(resume=True), 'complete')
        for key, text in before.items():  # completed work is never repeated or overwritten
            self.assertEqual((second.dir / 'runs' / key / 'result.json').read_text(), text)
        rerun = second.dir / 'runs' / stopped[0]
        self.assertEqual(json.loads((rerun / 'result.json').read_text())['attempt'], 2)
        self.assertTrue((rerun / 'attempts' / '001' / 'result.json').exists())  # the earlier attempt is archived, not lost
        self.assertEqual(len(read_jsonl(second.dir / 'resumes.jsonl')), 1)
        self.assertEqual(len(list((second.dir / 'runs').glob('*/result.json'))), 32)

    def test_the_budget_ledger_survives_the_resume(self):
        config = self.config(budgets={'va': {'tokens': 1_000_000}, 'vb': {'tokens': 400}})
        first = self.study(config)
        first.run()
        spent = first.budgets['vb'].spent.total
        config['budgets']['vb']['tokens'] = 1_000_000
        second = self.study(config)
        second.budget_for('model-b')
        self.assertEqual(second.budgets['vb'].spent.total, spent)

    def test_a_resume_refuses_a_changed_study_and_a_second_start_refuses_to_overwrite(self):
        study = self.study()
        study.run()
        with self.assertRaisesRegex(RuntimeError, 'already exists'):
            self.study().run()
        with self.assertRaisesRegex(RuntimeError, 'differ from the stored manifest'):
            self.study(self.config(trials=3)).run(resume=True)
        with self.assertRaisesRegex(RuntimeError, 'differ from the stored manifest'):
            self.study(self.config(limits={'max_tool_calls': 6})).run(resume=True)

    def test_a_completed_study_resumes_to_nothing(self):
        study = self.study()
        study.run()
        factory = self.clients()
        again = self.study(factory=factory)
        self.assertEqual(again.run(resume=True), 'complete')
        self.assertEqual(sum(len(c.calls) for c in factory.made.values()), 0)

    # ------------------------------------------------------------------ records
    def test_manifest_has_the_facts_and_no_absolute_path_and_no_key(self):
        study = self.study()
        study.run()
        text = (study.dir / 'manifest.json').read_text(encoding='utf-8')
        manifest = json.loads(text)
        for field in ('commit', 'treeDirty', 'sdkVersions', 'models', 'pricesTableDate', 'limits', 'tokenBudgets', 'telemetry', 'declaredSettings', 'machine',
                      'planHash', 'harnessFiles', 'datasetHashes', 'provenance'):
            self.assertIn(field, manifest)
        self.assertEqual(manifest['models']['model-a']['priceEntry']['output'], 10.0)
        self.assertEqual(manifest['pricesTableDate'], '2026-10-20')
        self.assertEqual(manifest['identity']['corpusFreeze'], sha256_file(self.corpus / 'corpus-manifest.json'))
        self.assertIsNone(re.search(r'[A-Za-z]:[\\/]', text))
        self.assertIsNone(re.search(r'"/(?:home|usr|var|tmp|dev|Users)/', text))
        self.assertNotIn(self.tmp.name.replace('\\', '\\\\'), text)

    def test_bundle_checksum_names_every_file(self):
        study = self.study()
        study.run()
        bundle = json.loads((study.dir / 'bundle.json').read_text())
        self.assertIn('manifest.json', bundle['files'])
        self.assertIn('scores.csv', bundle['files'])
        self.assertTrue(any(name.endswith('transcript.jsonl') for name in bundle['files']))
        for name, digest in bundle['files'].items():
            self.assertEqual(sha256_file(study.dir / name), digest)
        self.assertEqual(len(bundle['checksum']), 64)

    def test_nothing_written_holds_a_key(self):
        secret = 'sk-ant-SECRETSECRETSECRET'

        def factory(model):
            return FakeVendorClient([turn(secret + ' leaked in text', [('a', 'lookup', {'q': secret})]), submit({'value': 'blue'})] * 300,
                                    max_output_tokens=100)
        study = self.study(self.config(trials=1, scenario_order=['alpha']), factory=factory)
        study.run()
        for path in study.dir.rglob('*'):
            if path.is_file():
                self.assertNotIn(secret, path.read_text(encoding='utf-8'), path.name)

    def test_credentials_are_stripped_from_stack_environments(self):
        env = child_environment({'ANTHROPIC_API_KEY': 'x', 'OPENAI_API_KEY': 'y', 'PATH': 'p', 'KEEP': '1'})
        self.assertEqual(env, {'PATH': 'p', 'KEEP': '1'})
        self.assertEqual(child_environment({'A': '1'}, extra={'B': '2'}), {'A': '1', 'B': '2'})

    def test_the_real_corpus_loads_for_both_task_sets(self):
        dev, scored = load_tasks(CORPUS, 'dev'), load_tasks(CORPUS, 'scored')
        self.assertEqual((len(dev), len(scored)), (4, 16))
        self.assertEqual({t['id'] for t in scored if t['stoppedService']}, {'T10', 'T11'})
        self.assertTrue(all(t['schema'] and t['expected'] for t in dev + scored))

    def test_a_vendor_with_two_models_is_refused(self):
        models = {'models': {'a': {'vendor': 'v', 'request': {}, 'max_output_tokens': 1}, 'b': {'vendor': 'v', 'request': {}, 'max_output_tokens': 1}}}
        with self.assertRaisesRegex(ValueError, 'one model per vendor'):
            Study(self.config(models=['a', 'b']), models, PRICES, 'r', root=self.root, corpus_dir=self.corpus, session_factory=self.session_factory,
                  stack_factory=FakeStack)


if __name__ == '__main__':
    unittest.main()
