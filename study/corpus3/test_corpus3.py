"""The tests of corpus 3. Offline: no stack, no MCP server, no API key.

- The derivation reproduces every derived file from corpus 2's frozen files and the released files.
- The carried tasks equal corpus 2's by hash: every record, schema and key of the 76 pool tasks, the 6 ambiguity tasks and the 8
  development tasks, dev.json and scoring.py byte for byte, bound to corpus 2's frozen manifest.
- Every new task has a key that fits its schema and scores correct, chosen wrong answers are refused, and it has a solver and its
  direction fields; every scored task has direction fields from the rule, and the rule gives the counts the scope names.
- The reference solutions of every arm, through the runner, on the fakes, outages included; a report hashes every file they run.
- The harness reads the folder: its corpus check accepts the manifest and its loader reads the scored and the development sets.
- No new question appears in a tracked file outside this folder, and corpus 2's leak check accepts this folder's files.
"""
import copy
import hashlib
import io
import json
import subprocess
import sys
import unittest
from collections import Counter
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
CORPUS2 = REPO / 'study' / 'corpus2'
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / 'reference'))

import derive_a3  # noqa: E402  (puts corpus 2 on sys.path)
import run_reference  # noqa: E402  (corpus 3's; it loads corpus 2's under another name)
import scoring  # noqa: E402
from solutions3 import NEW, SOLVERS  # noqa: E402


def load(name, folder=HERE):
    return json.loads((folder / name).read_text(encoding='utf-8'))


TASKS = load('tasks.json')
SCHEMAS = load('schemas.json')['schemas']
EXPECTED = load('expected.json')['expected']
KEYS = load('keys-a.json')['keys']
MANIFEST = load('corpus-manifest.json')
POOL2 = load('pool.json', CORPUS2)['tasks']
AMBIGUITY2 = load('ambiguity.json', CORPUS2)['tasks']
DEV2 = load('dev.json', CORPUS2)['tasks']
KEYS2 = load('keys-a.json', CORPUS2)['keys']
NEW_IDS = MANIFEST['newTaskIds']
BY_ID = {t['id']: t for t in TASKS['tasks']}


def record_bytes(record):
    return json.dumps(record, ensure_ascii=False, separators=(',', ':')).encode('utf-8')


def lf(path):
    return Path(path).read_bytes().replace(b'\r\n', b'\n')


class TheDerivation(unittest.TestCase):
    def test_every_derived_file_reproduces(self):
        self.assertEqual(derive_a3.stale_files(derive_a3.derive()), [])

    def test_the_manifest_lists_every_file_the_harness_reads(self):
        for name in derive_a3.WRITTEN:
            self.assertEqual(MANIFEST['files'][name], hashlib.sha256(lf(HERE / name)).hexdigest(), name)
        self.assertEqual(MANIFEST['status'], derive_a3.STAMP)

    def test_corpus2_is_its_frozen_manifest(self):
        self.assertEqual(derive_a3.sha256_lf(CORPUS2 / 'corpus-manifest.json'), derive_a3.FREEZE2)
        self.assertEqual(MANIFEST['corpus2Manifest'], derive_a3.FREEZE2)

    def test_the_counts(self):
        sets = Counter(t['set'] for t in TASKS['tasks'])
        self.assertEqual((sets['core'], sets['ambiguity'], len(NEW_IDS)), (107, 6, 31))
        self.assertEqual((MANIFEST['coreTasks'], MANIFEST['newTasks'], MANIFEST['ambiguityTasks'], MANIFEST['devTasks']), (107, 31, 6, 8))
        ids = [t['id'] for t in TASKS['tasks']]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(set(ids), set(SCHEMAS))
        self.assertEqual(set(ids), set(EXPECTED))
        self.assertEqual(set(KEYS), set(ids) | {t['id'] for t in DEV2})

    def test_a_write_does_not_replace_a_frozen_manifest(self):
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / 'corpus-manifest.json').write_text(json.dumps({'status': 'frozen-2026-12-01'}), encoding='utf-8')
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                code = derive_a3.main(['--write'], folder)
            self.assertEqual(code, 1)
            self.assertEqual(sorted(p.name for p in Path(folder).iterdir()), ['corpus-manifest.json'])


class TheCarriedTasks(unittest.TestCase):
    """Decision C2: every carried task is corpus 2's, byte for byte, and bound to its corpus 2 hash."""

    def test_records_are_byte_identical(self):
        carried = [{k: v for k, v in t.items() if k != 'schema'} for t in POOL2] + [{k: v for k, v in t.items() if k != 'schema'} for t in AMBIGUITY2]
        mine = [t for t in TASKS['tasks'] if t['id'] not in NEW_IDS]
        self.assertEqual([record_bytes(t) for t in mine], [record_bytes(t) for t in carried])

    def test_schemas_and_keys_are_corpus2s(self):
        for t in POOL2 + AMBIGUITY2:
            self.assertEqual(record_bytes(SCHEMAS[t['id']]), record_bytes(t['schema']), t['id'])
            self.assertEqual(record_bytes(EXPECTED[t['id']]), record_bytes(KEYS2[t['id']]), t['id'])
            self.assertEqual(record_bytes(KEYS[t['id']]), record_bytes(KEYS2[t['id']]), t['id'])
        for t in DEV2:
            self.assertEqual(record_bytes(KEYS[t['id']]), record_bytes(KEYS2[t['id']]), t['id'])

    def test_the_bindings_hold(self):
        bound = MANIFEST['carried']
        self.assertEqual(set(bound), {t['id'] for t in POOL2 + AMBIGUITY2 + DEV2})
        for t in POOL2 + AMBIGUITY2 + DEV2:
            self.assertEqual(bound[t['id']], {'record': derive_a3.digest(t), 'schema': derive_a3.digest(t['schema']),
                                              'key': derive_a3.digest(KEYS2[t['id']])}, t['id'])
        # and the corpus 3 side has the same content
        for t in POOL2 + AMBIGUITY2:
            mine = dict(BY_ID[t['id']], schema=SCHEMAS[t['id']])
            self.assertEqual(derive_a3.digest(mine), bound[t['id']]['record'], t['id'])
            self.assertEqual(derive_a3.digest(EXPECTED[t['id']]), bound[t['id']]['key'], t['id'])

    def test_dev_and_the_scorer_are_byte_identical(self):
        self.assertEqual(lf(HERE / 'dev.json'), lf(CORPUS2 / 'dev.json'))
        self.assertEqual(lf(HERE / 'scoring.py'), lf(CORPUS2 / 'scoring.py'))

    def test_a_changed_carried_record_is_caught(self):
        t = copy.deepcopy(POOL2[0])
        t['size'] = 'large' if t['size'] != 'large' else 'small'
        self.assertNotEqual(derive_a3.digest(t), MANIFEST['carried'][t['id']]['record'])


class TheNewTasks(unittest.TestCase):
    def test_new_ids_do_not_clash_and_follow_the_letters(self):
        old = {t['id'] for t in POOL2 + AMBIGUITY2 + DEV2}
        self.assertFalse(old & set(NEW_IDS))
        for tid in NEW_IDS:
            self.assertEqual(BY_ID[tid]['category'], tid[0])
            self.assertIn(BY_ID[tid]['category'], 'BCE')  # decision C4: study 2's letters

    def test_every_new_task_has_its_parts(self):
        for tid in NEW_IDS:
            t = BY_ID[tid]
            self.assertEqual(t['set'], 'core')
            self.assertIn(t['size'], ('small', 'medium', 'large'))
            self.assertTrue(t['question'].strip())
            self.assertIn('explanation', SCHEMAS[tid]['properties'])
            self.assertIn(tid, EXPECTED)
            self.assertIn(tid, NEW)
            self.assertIn(tid, TASKS['directions'])
        self.assertEqual(set(NEW), set(NEW_IDS))

    def test_every_key_scores_correct_and_wrong_answers_fail(self):
        for tid in NEW_IDS:
            answer = copy.deepcopy(KEYS[tid]['answer'])
            answer.setdefault('answerStatus', 'ANSWERED')
            context = {'taskId': tid, 'set': 'core', 'category': BY_ID[tid]['category'], 'askRequester': []}
            self.assertEqual(scoring.score(answer, SCHEMAS[tid], KEYS[tid], context)['outcome'], 'correct', tid)
            wrong = copy.deepcopy(answer)
            field = next(k for k in wrong if k not in ('answerStatus', 'explanation'))
            value = wrong[field]
            if isinstance(value, list) and value:
                wrong[field] = value[:-1]
            elif isinstance(value, list):
                wrong[field] = ['ST-00000LD4Q'] if field == 'missionIds' else value
            elif isinstance(value, int):
                wrong[field] = value + 7
            elif isinstance(value, float):
                wrong[field] = value + 7.0
            else:
                wrong[field] = str(value) + '-X'
            self.assertNotEqual(scoring.score(wrong, SCHEMAS[tid], KEYS[tid], context)['outcome'], 'correct', tid)

    def test_the_spread(self):
        new = [BY_ID[t] for t in NEW_IDS]
        self.assertEqual(Counter(t['size'] for t in new), Counter({'medium': 17, 'small': 10, 'large': 4}))
        three = [t['id'] for t in new if len(t['systems']) == 3]
        self.assertEqual(sorted(three), ['B30', 'B31', 'E26', 'E27'])


class TheDirections(unittest.TestCase):
    """Decision C5: every scored task gets direction and csl from one rule."""

    def test_every_scored_task_has_valid_fields(self):
        d = TASKS['directions']
        self.assertEqual(set(d), set(BY_ID))
        for tid, v in d.items():
            self.assertEqual(set(v), {'direction', 'csl', 'anchor', 'requiredSystems'}, tid)
            self.assertIn(v['direction'], derive_a3.DIRECTIONS)
            self.assertIn(v['csl'], derive_a3.CSL)
            self.assertIn(v['anchor'], ('missions', 'personnel', 'assets'))

    def test_required_systems_are_kept_apart_from_the_anchor(self):
        d = TASKS['directions']
        for tid, v in d.items():
            want = ['missions'] if tid in ('B10', 'B11', 'B12') else sorted(BY_ID[tid]['systems'])
            self.assertEqual(v['requiredSystems'], want, tid)
        # the tasks that start from an identifier but need only Missions and the mapping
        for tid in ('B10', 'B12', 'B28', 'C16', 'E20', 'E22'):
            self.assertEqual(d[tid]['requiredSystems'], ['missions'], tid)
            self.assertNotEqual(d[tid]['anchor'], 'missions', tid)
            self.assertEqual(d[tid]['direction'], 'reverse', tid)

    def test_the_counts_the_scope_names(self):
        d = TASKS['directions']
        carried = {k: v for k, v in d.items() if k not in NEW_IDS}
        new = {k: v for k, v in d.items() if k in NEW_IDS}
        self.assertEqual(sorted(k for k, v in carried.items() if v['direction'] == 'reverse'), ['B10', 'B12', 'E15'])
        self.assertEqual(sorted(k for k, v in carried.items() if v['csl'] == 'link-integrity'), ['C04', 'C10', 'C11', 'C12'])
        self.assertEqual(sum(1 for v in carried.values() if v['direction'] == 'forward'), 20)
        self.assertEqual(sum(1 for v in d.values() if v['direction'] == 'forward'), 24)
        self.assertEqual(d['B11'], {'direction': 'none', 'csl': None, 'anchor': 'missions', 'requiredSystems': ['missions']})
        self.assertEqual(Counter((v['direction'], v['csl']) for v in new.values()),
                         Counter({('reverse', 'reverse-lookup'): 18, ('reverse', 'far-side-aggregate'): 9, ('forward', None): 4}))
        for t in TASKS['tasks']:
            if t['set'] == 'ambiguity' or t['category'] == 'D':
                self.assertEqual((d[t['id']]['direction'], d[t['id']]['csl']), ('none', None), t['id'])

    def test_the_rule(self):
        c = derive_a3.classify
        self.assertEqual(c({'id': 'x', 'category': 'B', 'systems': ['missions', 'personnel']}, 'personnel'), ('reverse', 'reverse-lookup'))
        self.assertEqual(c({'id': 'x', 'category': 'B', 'systems': ['missions']}, 'assets'), ('reverse', 'reverse-lookup'))
        # the required systems, not the systems listed, decide
        self.assertEqual(c({'id': 'x', 'category': 'B', 'systems': ['missions', 'personnel']}, 'missions', ['missions']), ('none', None))
        self.assertEqual(c({'id': 'x', 'category': 'C', 'systems': ['assets', 'missions']}, 'assets'), ('reverse', 'reverse-lookup'))
        self.assertEqual(c({'id': 'x', 'category': 'E', 'systems': ['assets', 'missions']}, 'assets'), ('reverse', 'far-side-aggregate'))
        self.assertEqual(c({'id': 'x', 'category': 'C', 'systems': ['assets', 'missions']}, 'missions'), ('none', 'link-integrity'))
        self.assertEqual(c({'id': 'x', 'category': 'C', 'systems': ['missions']}, 'missions'), ('none', None))
        self.assertEqual(c({'id': 'x', 'category': 'B', 'systems': ['missions', 'personnel']}, 'missions'), ('forward', None))
        self.assertEqual(c({'id': 'x', 'category': 'A', 'systems': ['personnel']}, 'missions'), ('none', None))
        self.assertEqual(c({'id': 'x', 'category': 'D', 'systems': ['missions', 'personnel']}, 'personnel'), ('none', None))
        self.assertEqual(c({'id': 'x', 'set': 'ambiguity', 'category': 'F', 'systems': ['missions']}, 'missions'), ('none', None))
        with self.assertRaises(ValueError):
            c({'id': 'x', 'category': 'B', 'systems': ['personnel']}, 'personnel')
        with self.assertRaises(ValueError):
            c({'id': 'x', 'category': 'B', 'systems': ['missions']}, 'elsewhere')


class TheReferenceSolutions(unittest.TestCase):
    def test_every_task_has_a_solver(self):
        self.assertEqual(set(KEYS) - set(SOLVERS), set())

    def run_fake(self, arm, *extra):
        out = io.StringIO()
        with redirect_stdout(out):
            code = run_reference.main(['--arm', arm, '--fake'] + list(extra))
        return code, out.getvalue()

    def test_every_arm_on_the_fakes(self):
        for arm in run_reference.R2.ARMS:
            code, text = self.run_fake(arm, '--set', 'all')
            self.assertEqual(code, 0, text)
            self.assertIn('"correct": 106', text, arm)
            for outage, n in (('missions', 4), ('assets', 6), ('personnel', 5)):
                code, text = self.run_fake(arm, '--outage', outage)
                self.assertEqual(code, 0, text)
                self.assertIn('"correct": %d' % n, text, (arm, outage))

    def test_every_listed_required_system_is_needed(self):
        """For every scored task outside category D that requires more than one service, stopping any one of them breaks its answer
        in at least one arm on the fakes: no task, carried or new, counts a service its answer can do without (B11 did, before
        CARRIED_REQUIRED). The check is as strong as the solutions: a solution that reads a service it does not need hides it."""
        world = run_reference.R2_world()
        fakes = run_reference.corpus2_fakes()
        keys = run_reference.load_keys()
        for task in run_reference.load_tasks(['core']):
            required = TASKS['directions'][task['id']]['requiredSystems']
            if task.get('stoppedService') or len(required) < 2:
                continue
            for service in required:
                call = fakes.FakeEnterprise(world, down=[service]).call
                outcomes = {run_reference.run_task(run_reference.R2.arm_module(arm), call, task, keys[task['id']])['outcome']
                            for arm in run_reference.R2.ARMS}
                self.assertNotEqual(outcomes, {'correct'}, (task['id'], service))

    def test_every_new_task_needs_only_its_required_systems(self):
        """With every service outside a task's requiredSystems stopped, its solution is still correct in every arm: no task lists a
        service its answer does not need to read, and none reads one it does not list."""
        world = run_reference.R2_world()
        fakes = run_reference.corpus2_fakes()
        keys = run_reference.load_keys()
        tasks = {t['id']: t for t in run_reference.load_tasks(['core'])}
        for tid in NEW_IDS + ['B10', 'B11', 'B12']:
            required = TASKS['directions'][tid]['requiredSystems']
            down = [s for s in ('missions', 'assets', 'personnel') if s not in required]
            call = fakes.FakeEnterprise(world, down=down).call
            for arm in run_reference.R2.ARMS:
                row = run_reference.run_task(run_reference.R2.arm_module(arm), call, tasks[tid], keys[tid])
                self.assertEqual(row['outcome'], 'correct', (tid, arm, down, row.get('error'), row.get('submissions')))
            if len(required) > 1:  # and each listed service is needed: stopping it breaks the answer in Direct Access
                for service in required:
                    call = fakes.FakeEnterprise(world, down=[service]).call
                    row = run_reference.run_task(run_reference.R2.arm_module('alpha'), call, tasks[tid], keys[tid])
                    self.assertNotEqual(row['outcome'], 'correct', (tid, service))

    def test_the_scorer_that_runs_is_this_folders_and_the_report_hashes_it(self):
        loaded = Path(run_reference.scoring.__file__).resolve()
        self.assertEqual(loaded, (HERE / 'scoring.py').resolve())
        scorer = run_reference.input_hashes()['scorer']
        self.assertEqual(scorer, {'path': 'study/corpus3/scoring.py', 'sha256': run_reference.digest(loaded.read_bytes())})
        self.assertIsNot(run_reference.scoring, sys.modules.get('scoring'))

    def test_a_selection_with_nothing_to_run_is_refused(self):
        # every selected task would be skipped: a non-D task under an outage, a D task without its outage or under another one
        for extra in (['--set', 'core', '--tasks', 'B16', '--outage', 'missions'], ['--tasks', 'D01'], ['--tasks', 'D01', '--outage', 'assets'],
                      ['--set', 'ambiguity', '--outage', 'personnel']):
            with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
                run_reference.main(['--arm', 'alpha', '--fake'] + extra)
            self.assertEqual(raised.exception.code, 2, extra)
        # a D task under its own outage runs
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(run_reference.main(['--arm', 'alpha', '--fake', '--tasks', 'D01', '--outage', 'missions']), 0)
        self.assertIn('"correct": 1', out.getvalue())

    def test_unknown_task_ids_are_refused(self):
        for given in ('Z99', 'B16,Z99', ',', ''):
            with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
                run_reference.main(['--arm', 'alpha', '--fake', '--tasks', given])
            self.assertEqual(raised.exception.code, 2, given)
        # an id of another set is unknown in this one
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            run_reference.main(['--arm', 'alpha', '--fake', '--set', 'dev', '--tasks', 'B16'])
        # an explicit empty --tasks never runs the whole set
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
            run_reference.main(['--arm', 'alpha', '--fake', '--set', 'dev', '--tasks', ''])
        self.assertEqual(raised.exception.code, 2)

    def test_a_solver_with_no_submission_is_an_error(self):
        saved = run_reference.SOLVERS['B16']
        world = run_reference.R2_world()
        call = run_reference.corpus2_fakes().FakeEnterprise(world).call
        task = {t['id']: t for t in run_reference.load_tasks(['core'])}['B16']
        try:
            run_reference.SOLVERS['B16'] = lambda acc: []
            row = run_reference.run_task(run_reference.R2.arm_module('alpha'), call, task, KEYS['B16'])
        finally:
            run_reference.SOLVERS['B16'] = saved
        self.assertEqual((row['outcome'], row['error']), ('error', 'the solver returned no submission'))

    def test_a_report_hashes_every_file_the_solutions_run(self):
        inputs = run_reference.input_hashes()
        names = set(inputs['referenceFiles'])
        for folder in (CORPUS2 / 'reference', HERE / 'reference'):
            for p in folder.glob('*.py'):
                self.assertIn(p.relative_to(REPO).as_posix(), names)
        for name in run_reference.INPUT_FILES:
            self.assertIn(name, inputs)

    def test_the_report_goes_outside_the_repository(self):
        with self.assertRaises(SystemExit):
            run_reference.main(['--arm', 'alpha', '--fake', '--tasks', 'B16', '--output', str(HERE / 'report.json')])


class TheHarnessReadsIt(unittest.TestCase):
    def test_corpus_check_and_loader(self):
        import importlib.util
        sys.path.append(str(REPO / 'study' / 'harness'))  # appended, so no harness module shadows a corpus module
        spec = importlib.util.spec_from_file_location('harness_runner', REPO / 'study' / 'harness' / 'runner.py')
        runner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(runner)
        runner.check_corpus(HERE, 'scored')
        runner.check_corpus(HERE, 'dev')
        scored = runner.load_tasks(HERE, 'scored')
        self.assertEqual([t['id'] for t in scored], [t['id'] for t in TASKS['tasks']])
        self.assertEqual(len(runner.load_tasks(HERE, 'dev')), 8)


class NoLeak(unittest.TestCase):
    def fragments(self):
        """The new questions and their 10-word windows of at least 50 characters, as test_corpus2.py takes them, leaving out the
        windows that are also in a corpus 2 question: the new questions reuse corpus 2's defining phrases (who is on a mission, when a
        reference counts), which corpus 2's own leak check already guards."""
        shared = [' '.join(t['question'].split()) for t in POOL2 + AMBIGUITY2 + DEV2]
        out = set()
        for tid in NEW_IDS:
            q = BY_ID[tid]['question']
            out.add(q)
            words = q.split()
            for start in range(0, max(1, len(words) - 9), 5):
                fragment = ' '.join(words[start:start + 10])
                if len(fragment) >= 50 and not any(fragment in q for q in shared):
                    out.add(fragment)
        return out

    def test_no_new_question_appears_in_a_tracked_file_outside_this_folder(self):
        files = subprocess.run(['git', 'ls-files', '-z'], cwd=str(REPO), capture_output=True, check=True).stdout.decode('utf-8').split('\0')
        inside = HERE.relative_to(REPO).as_posix() + '/'
        fragments, leaks = self.fragments(), []
        for name in files:
            if not name or name.startswith(inside):
                continue
            path = REPO / name
            if not path.is_file() or path.stat().st_size > 5_000_000:
                continue
            try:
                text = ' '.join(path.read_text(encoding='utf-8').split())
            except (UnicodeDecodeError, OSError):
                continue
            leaks += ['%s: %s' % (name, f[:60]) for f in fragments if f in text]
        self.assertFalse(leaks, leaks[:10])

    def test_the_new_questions_are_new(self):
        old = {t['question'] for t in POOL2 + AMBIGUITY2 + DEV2}
        self.assertFalse(old & {BY_ID[t]['question'] for t in NEW_IDS})

    def test_corpus2s_leak_check_accepts_this_folder(self):
        """The narrowed check of test_corpus2.py (decision C1), run on this folder's files as they are, tracked or not. It runs in a
        process of its own, in corpus 2's folder, so that corpus 2's modules never meet this folder's."""
        script = '\n'.join([
            'import json, sys',
            'from pathlib import Path',
            'import test_corpus2 as t2',
            'here, repo = Path(sys.argv[1]), Path(sys.argv[2])',
            'check = t2.NoLeak("test_the_corpus3_exception_is_narrow")',
            'fragments, allowed = check.fragments(), t2.corpus2_records()',
            'leaks = []',
            'for path in sorted(here.rglob("*")):',
            '    if path.is_file() and path.suffix in (".json", ".py", ".md"):',
            '        leaks += check.leaks_in(path.relative_to(repo).as_posix(), path.read_text(encoding="utf-8"), fragments, allowed)',
            'print(json.dumps(leaks))', ''])
        done = subprocess.run([sys.executable, '-B', '-c', script, str(HERE), str(REPO)], cwd=str(CORPUS2), capture_output=True,
                              text=True, encoding='utf-8')
        self.assertEqual(done.returncode, 0, done.stderr)
        leaks = json.loads(done.stdout.strip().splitlines()[-1])
        self.assertEqual(leaks, [], leaks[:10])


if __name__ == '__main__':
    unittest.main()
