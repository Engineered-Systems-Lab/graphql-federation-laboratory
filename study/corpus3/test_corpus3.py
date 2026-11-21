"""The tests of corpus 3. Offline: no stack, no MCP server, no API key.

- The derivation reproduces every derived file from corpus 2's frozen files and the released files, under the status the committed
  manifest holds (the draft status or a well-formed frozen one, also checked on a temporary frozen copy); the freeze
  (derive_a3.py --write --frozen <date>) writes the manifest alone and refuses what it must.
- The carried tasks equal corpus 2's by hash: every record, schema and key of the 76 pool tasks, the 6 ambiguity tasks and the 8
  development tasks, dev.json and scoring.py byte for byte, bound to corpus 2's frozen manifest.
- Every new task has a key that fits its schema and scores correct, chosen wrong answers are refused, and it has a solver and its
  direction fields; every scored task has direction fields from the rule, and the rule gives the counts the scope names.
- The reference solutions of every arm, through the runner, on the fakes, outages included; a report hashes every file they run.
- The harness reads the folder: its corpus check accepts the manifest and its loader reads the scored and the development sets.
- No new question appears in a tracked file outside this folder, and corpus 2's leak check accepts this folder's files.
- The second derivation (keys-b3.json): B's three files are the recorded bytes, every input B hashed is the file of the keys-b3 package
  rebuilt from Git at the package's lab commit, B's answer is correct under keys A on every new task, and its differences from keys A are
  exactly the cases the lead developer decided (compare_keys3.py).
"""
import copy
import hashlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
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


CORPUS_FILES = derive_a3.WRITTEN + ('corpus-manifest.json',)
_DRAFT = {}


def draft_manifest():
    """The draft manifest's bytes, derived from corpus 2 and the released files, whatever the committed manifest holds."""
    if 'bytes' not in _DRAFT:
        _DRAFT['bytes'] = derive_a3.derive(derive_a3.STAMP)['corpus-manifest.json'].encode('utf-8')
    return _DRAFT['bytes']


def draft_copy(folder):
    """Copy the derived files into `folder`, with a draft manifest in place of the committed one."""
    for name in derive_a3.WRITTEN:
        shutil.copy(HERE / name, Path(folder) / name)
    (Path(folder) / 'corpus-manifest.json').write_bytes(draft_manifest())


def run_check(*argv, folder=HERE):
    """derive_a3.py's command line on `folder`: its exit code and everything it printed."""
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = derive_a3.main(list(argv), folder=folder)
    return code, out.getvalue() + err.getvalue()


def harness_runner():
    """The harness's runner.py, loaded under its own name."""
    harness = str(REPO / 'study' / 'harness')
    if harness not in sys.path:
        sys.path.append(harness)  # appended, so no harness module shadows a corpus module
    spec = importlib.util.spec_from_file_location('harness_runner', REPO / 'study' / 'harness' / 'runner.py')
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    return runner


class CommittedCorpusChecks:
    """The checks of the committed corpus files, under the status the committed manifest holds: the draft status, or a well-formed
    frozen-<YYYY-MM-DD> once the freeze is committed. TheDerivation runs them on this folder and TheFrozenManifest on a temporary copy
    frozen by derive_a3.py --write --frozen <date>."""

    def corpus(self):
        return HERE

    def manifest(self):
        return load('corpus-manifest.json', self.corpus())

    def test_every_derived_file_reproduces(self):
        folder = self.corpus()
        status = derive_a3.committed_status(folder)
        self.assertTrue(derive_a3.status_ok(status), status)
        self.assertEqual(derive_a3.stale_files(derive_a3.derive(status), folder), [])

    def test_the_manifest_lists_every_file_the_harness_reads(self):
        folder, manifest = self.corpus(), self.manifest()
        for name in derive_a3.WRITTEN:
            self.assertEqual(manifest['files'][name], hashlib.sha256(lf(folder / name)).hexdigest(), name)
        self.assertTrue(derive_a3.status_ok(manifest['status']), manifest['status'])

    def test_the_check_passes_on_the_committed_files_under_their_status(self):
        folder = self.corpus()
        code, text = run_check(folder=folder)
        self.assertEqual(code, 0, text)
        self.assertIn('manifest status: %s)' % derive_a3.committed_status(folder), text)

    def test_corpus2_is_its_frozen_manifest(self):
        self.assertEqual(derive_a3.sha256_lf(CORPUS2 / 'corpus-manifest.json'), derive_a3.FREEZE2)
        self.assertEqual(self.manifest()['corpus2Manifest'], derive_a3.FREEZE2)

    def test_the_harness_accepts_the_manifest(self):
        runner = harness_runner()
        runner.check_corpus(self.corpus(), 'scored')
        runner.check_corpus(self.corpus(), 'dev')


class TheDerivation(CommittedCorpusChecks, unittest.TestCase):
    def test_the_counts(self):
        sets = Counter(t['set'] for t in TASKS['tasks'])
        self.assertEqual((sets['core'], sets['ambiguity'], len(NEW_IDS)), (107, 6, 31))
        self.assertEqual((MANIFEST['coreTasks'], MANIFEST['newTasks'], MANIFEST['ambiguityTasks'], MANIFEST['devTasks']), (107, 31, 6, 8))
        ids = [t['id'] for t in TASKS['tasks']]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(set(ids), set(SCHEMAS))
        self.assertEqual(set(ids), set(EXPECTED))
        self.assertEqual(set(KEYS), set(ids) | {t['id'] for t in DEV2})


class TheFrozenManifest(CommittedCorpusChecks, unittest.TestCase):
    """A manifest frozen by derive_a3.py --write --frozen <date> in a temporary copy of the corpus passes the checks of the committed
    files."""

    @classmethod
    def setUpClass(cls):
        tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(tmp.cleanup)
        cls.folder = Path(tmp.name)
        draft_copy(cls.folder)
        code, text = run_check('--write', '--frozen', '2026-11-21', folder=cls.folder)
        if code != 0:
            raise AssertionError('the freeze of the copy failed: %s' % text)

    def corpus(self):
        return self.folder

    def test_the_copy_holds_a_frozen_manifest_and_only_the_manifest_changed(self):
        self.assertEqual(derive_a3.committed_status(self.folder), 'frozen-2026-11-21')
        self.assertNotEqual((self.folder / 'corpus-manifest.json').read_bytes(), draft_manifest())
        for name in derive_a3.WRITTEN:
            self.assertEqual((self.folder / name).read_bytes(), (HERE / name).read_bytes(), name)


class TheManifestStatus(unittest.TestCase):
    """The draft status or frozen-<YYYY-MM-DD>, written only by an explicit option and only in the manifest. Each test starts from its own
    draft copy of the corpus, whatever status the committed manifest holds."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.folder = Path(tmp.name)
        draft_copy(self.folder)

    def main(self, *argv):
        return run_check(*argv, folder=self.folder)

    def bytes_of(self, name):
        return (self.folder / name).read_bytes()

    def all_bytes(self):
        return {name: self.bytes_of(name) for name in CORPUS_FILES}

    def edit_manifest(self, change):
        path = self.folder / 'corpus-manifest.json'
        manifest = json.loads(path.read_text(encoding='utf-8'))
        change(manifest)
        path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')

    def test_the_statuses_the_check_accepts_and_refuses(self):
        for status in (derive_a3.STAMP, 'frozen-2026-11-21', 'frozen-2028-02-29'):
            self.assertTrue(derive_a3.status_ok(status), status)
        for status in ('frozen', 'frozen-2026-11', 'frozen-2026-02-30', 'frozen-2026-11-21 ', 'Frozen-2026-11-21', 'frozen-26-11-21',
                       'frozen-2026-11-21-x', 'draft', '', None, 7, 'frozen-2026-1-21'):
            self.assertFalse(derive_a3.status_ok(status), status)
        with self.assertRaises(ValueError):
            derive_a3.derive('frozen-2026-13-01')

    def test_the_draft_check_passes_on_a_draft_copy(self):
        code, text = self.main()
        self.assertEqual(code, 0, text)
        self.assertIn('manifest status: draft, not frozen', text)

    def test_the_freeze_writes_the_frozen_status_in_the_manifest_only(self):
        before = self.all_bytes()
        code, text = self.main('--write', '--frozen', '2026-11-21')
        self.assertEqual(code, 0, text)
        for name in derive_a3.WRITTEN:
            self.assertEqual(self.bytes_of(name), before[name], name)
        manifest = json.loads(self.bytes_of('corpus-manifest.json'))
        draft = json.loads(before['corpus-manifest.json'])
        self.assertEqual(manifest['status'], 'frozen-2026-11-21')
        self.assertIn('Frozen on 2026-11-21', manifest['about'])
        self.assertEqual({k: v for k, v in manifest.items() if k not in ('status', 'about')},
                         {k: v for k, v in draft.items() if k not in ('status', 'about')})
        self.assertEqual(json.loads(self.bytes_of('keys-a.json'))['status'], derive_a3.STAMP)
        code, text = self.main()
        self.assertEqual(code, 0, text)
        self.assertIn('manifest status: frozen-2026-11-21', text)

    def test_a_write_without_the_option_does_not_unfreeze_and_a_bad_option_refuses(self):
        self.assertEqual(self.main('--write', '--frozen', '2026-11-21')[0], 0)
        before = self.all_bytes()
        code, text = self.main('--write')
        self.assertEqual(code, 1)
        self.assertIn('replaces only a draft manifest', text)
        for argv, words in ((('--write', '--frozen', '2026-02-30'), 'needs a date'), (('--write', '--frozen', 'tomorrow'), 'needs a date'),
                            (('--write', '--frozen', '2026-11-21T00:00'), 'needs a date'), (('--frozen', '2026-11-21'), 'with --write'),
                            (('--write', '--frozen'), 'usage'), (('--freeze',), 'usage')):
            code, text = self.main(*argv)
            self.assertEqual(code, 2, argv)
            self.assertIn(words, text, argv)
        self.assertEqual(self.all_bytes(), before, 'a refused write changes nothing')

    def test_a_malformed_date_refuses_on_a_draft_and_writes_nothing(self):
        before = self.all_bytes()
        for date in ('2026-02-30', '2026-11-1', '21-11-2026', ''):
            code, text = self.main('--write', '--frozen', date)
            self.assertEqual(code, 2, date)
            self.assertIn('needs a date', text, date)
        self.assertEqual(self.all_bytes(), before)

    def test_a_second_freeze_refuses_and_changes_nothing(self):
        self.assertEqual(self.main('--write', '--frozen', '2026-11-21')[0], 0)
        before = self.all_bytes()
        for date in ('2026-11-22', '2026-11-21'):
            code, text = self.main('--write', '--frozen', date)
            self.assertEqual(code, 1, date)
            self.assertIn('already frozen-2026-11-21', text)
        self.assertEqual(self.all_bytes(), before)

    def test_a_freeze_over_a_drifted_file_refuses_and_changes_nothing(self):
        for name in derive_a3.WRITTEN:
            with self.subTest(name=name):
                draft_copy(self.folder)
                (self.folder / name).write_bytes(self.bytes_of(name) + b' ')
                before = self.all_bytes()
                code, text = self.main('--write', '--frozen', '2026-11-21')
                self.assertEqual(code, 1)
                self.assertIn('the freeze writes the manifest only', text)
                self.assertIn(name, text)
                self.assertEqual(self.all_bytes(), before)

    def test_a_malformed_status_fails_the_check(self):
        for status in ('frozen', 'frozen-2026-02-30', 'frozen 2026-11-21', None):
            with self.subTest(status=status):
                self.edit_manifest(lambda m: m.update(status=status))
                code, text = self.main()
                self.assertEqual(code, 1)
                self.assertIn('is neither', text)

    def test_a_hand_edit_of_a_draft_or_a_frozen_manifest_fails_the_check(self):
        edits = (lambda m: m['files'].update({'tasks.json': '0' * 64}), lambda m: m['files'].pop('expected.json'),
                 lambda m: m.update(about=m['about'] + ' '), lambda m: m.update(newTasks=30))
        for frozen in (False, True):
            for number, edit in enumerate(edits):
                with self.subTest(frozen=frozen, edit=number):
                    (self.folder / 'corpus-manifest.json').write_bytes(draft_manifest())
                    if frozen:
                        self.assertEqual(self.main('--write', '--frozen', '2026-11-21')[0], 0)
                    self.assertEqual(self.main()[0], 0)
                    self.edit_manifest(edit)
                    code, text = self.main()
                    self.assertEqual(code, 1)
                    self.assertIn('differs from the derivation: corpus-manifest.json', text)

    def test_a_failed_freeze_leaves_the_draft_manifest_whole(self):
        """A write that fails part way (24 bytes written, then an error) or a swap that fails leaves the draft manifest byte for byte
        and no temporary file behind."""
        from unittest import mock
        real_fdopen = os.fdopen

        def failing_fdopen(*args, **kwargs):
            out = real_fdopen(*args, **kwargs)
            real_write = out.write

            def write(data):
                real_write(data[:24])
                raise OSError('injected write failure after 24 bytes')
            out.write = write
            return out
        before = self.all_bytes()
        for patch in (mock.patch.object(derive_a3.os, 'fdopen', failing_fdopen),
                      mock.patch.object(derive_a3.os, 'replace', side_effect=OSError('injected replace failure'))):
            with self.subTest(patch=patch.attribute), patch:
                with self.assertRaises(OSError):
                    self.main('--write', '--frozen', '2026-11-21')
            self.assertEqual(self.all_bytes(), before)
            self.assertEqual(sorted(p.name for p in self.folder.iterdir()), sorted(CORPUS_FILES))
        code, text = self.main()
        self.assertEqual(code, 0, text)
        self.assertIn('manifest status: draft, not frozen', text)

    def test_a_write_does_not_replace_a_frozen_manifest(self):
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
        runner = harness_runner()
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


class TheSecondDerivation(unittest.TestCase):
    """keys-b3.json, the blind second derivation of the new keys, against keys-a.json (entries 5 and 6 of the Job study3_corpus_keys_b,
    decisions J4 and J7). derive_b3.py and test_derive_b3.py check the package's MANIFEST.json and run only in a copy of the package."""

    @classmethod
    def setUpClass(cls):
        import compare_keys3
        cls.c = compare_keys3
        cls.keys_b = load('keys-b3.json')
        cls.package = compare_keys3.package_files()

    def test_b_is_the_recorded_bytes(self):
        for name, digest in self.c.B_RECORD['sha256'].items():
            self.assertEqual(self.c.lf_sha256(HERE / name), digest, name)
        self.assertEqual(sorted(self.c.B_RECORD['sha256']), ['derive_b3.py', 'keys-b3.json', 'test_derive_b3.py'])

    def test_b_was_derived_from_the_package_at_the_lab_commit(self):
        keys_b = self.keys_b
        self.assertEqual(keys_b['derivation'], 'B')
        self.assertEqual(keys_b['labCommit'], self.c.B_RECORD['labCommit'])
        self.assertEqual(keys_b['packageSha256'], self.c.B_RECORD['packageSha256'])
        self.assertEqual(keys_b['gaps'], [])
        self.assertEqual(set(keys_b['keys']), set(NEW_IDS))
        # the package rebuilt from Git at the lab commit is the one B received, and B hashed exactly its files, each as it is there
        self.assertEqual(self.c.package_problems(self.package), [])
        self.assertEqual(self.c.input_problems(keys_b, self.package), [])
        self.assertEqual(len(keys_b['inputs']), 70)
        # and the lab's current files are still the ones B received
        self.assertEqual(self.c.current_problems(keys_b, then=self.package), [])

    def test_a_changed_input_is_found(self):
        files = dict(self.package)
        files['study/corpus3/tasks.json'] = files['study/corpus3/tasks.json'] + b' '
        self.assertEqual(self.c.input_problems(self.keys_b, files), ['study/corpus3/tasks.json'])
        files = dict(self.package)
        files['extra.json'] = b'{}'
        del files['study/corpus3/schemas.json']
        self.assertEqual(self.c.input_problems(self.keys_b, files), ['study/corpus3/schemas.json', 'extra.json'])
        files = dict(self.package)
        files[self.c.blind.MANIFEST] = files[self.c.blind.MANIFEST].replace(b'"keys-b3"', b'"keys-bX"', 1)
        self.assertEqual(len(self.c.package_problems(files)), 2)
        current = dict(self.package)
        current['study/corpus3/tasks.json'] = b'{}'
        current[self.c.blind.README] = b'other'
        self.assertEqual(self.c.current_problems(self.keys_b, current, self.package), ['study/corpus3/tasks.json'])

    def test_the_package_is_rebuilt_by_the_builder_of_the_lab_commit(self):
        commit = self.c.B_RECORD['labCommit']
        self.assertEqual(self.c.blind.__name__, 'compare_keys3_blind_' + commit)
        self.assertEqual(self.c.git_blob(commit, self.c.BUILDER), subprocess.run(
            ['git', '-C', str(REPO), 'cat-file', 'blob', '%s:%s' % (commit, self.c.BUILDER)], check=True, capture_output=True).stdout)
        # a change of the working tree's builder, such as a fourth package name, does not reach the reconstruction
        spec = importlib.util.spec_from_file_location('test_corpus3_working_blind', REPO / self.c.BUILDER)
        working = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(working)
        working.PACKAGES = working.PACKAGES + ('another',)
        self.assertIsNot(working, self.c.blind)
        self.assertEqual(self.c.blind.plan.__code__.co_filename, '%s:%s' % (commit, self.c.BUILDER))
        self.assertEqual(self.c.blind.PACKAGES, ('guide', 'keys-b', 'keys-b3'))
        self.assertEqual(self.c.package_problems(self.c.package_files()), [])

    def test_the_current_files_are_packaged_with_the_lab_commits_definitions(self):
        class Changed:
            """The working tree with a changed builder folder: another package definition and another builder."""
            def __init__(self, inner):
                self.inner = inner

            def read(self, path):
                if path.startswith('study/blind/'):
                    return b'{"version": 1, "packages": {"another": {}}}'
                return self.inner.read(path)

            def files_under(self, folder):
                return self.inner.files_under(folder)
        source = self.c.CurrentSource(Changed(self.c.blind.WorkingSource(REPO)))
        self.assertEqual(self.c.current_problems(self.keys_b, self.c.package_files(source), self.package), [])

    def test_the_comparison_scores_with_this_folders_scorer(self):
        self.assertEqual(Path(self.c.compare2.scoring.__file__).resolve(), (HERE / 'scoring.py').resolve())
        self.assertEqual(Path(self.c.compare2.__file__).resolve(), (CORPUS2 / 'compare_keys.py').resolve())

    def test_b_is_correct_under_a_on_every_new_task(self):
        for task in self.c.new_tasks():
            with self.subTest(task=task['id']):
                answer = dict(self.keys_b['keys'][task['id']]['answer'])
                ctx = {'taskId': task['id'], 'set': 'core', 'category': task['category'], 'askRequester': []}
                self.assertEqual(self.c.scoring3.score(answer, task['schema'], KEYS[task['id']], ctx)['outcome'], 'correct')

    def test_the_differences_are_exactly_the_decided_ones(self):
        self.assertEqual(self.c.undecided(self.c.compare()), [])
        self.assertEqual(sorted(self.c.DECIDED), [])
        with redirect_stdout(io.StringIO()):
            self.assertEqual(self.c.main([]), 0)

    def test_an_undecided_difference_fails_the_comparison(self):
        keys_b = copy.deepcopy(self.keys_b['keys'])
        keys_b['B16']['answer']['missions'].pop()
        found = self.c.compare(keys_b=keys_b)
        self.assertEqual(sorted(found), ['B16'])
        self.assertEqual([kind for kind, _ in found['B16']['differences']], ['b-not-correct-under-a', 'answer-differs'])
        mismatches = self.c.undecided(found)
        self.assertEqual([m[0] for m in mismatches], ['B16'])
        self.assertIn('not decided', mismatches[0][1])
        # a declared variant of B that A's checks refuse is a difference too
        keys_b = copy.deepcopy(self.keys_b['keys'])
        keys_b['C14']['variants'] = [{'answer': {'answerStatus': 'ANSWERED', 'missionIds': ['ST-00000LD4Q']}, 'reason': 'test'}]
        self.assertEqual([kind for kind, _ in self.c.compare(keys_b=keys_b)['C14']['differences']],
                         ['variants-differ', 'b-variant-not-correct-under-a'])
        # and a decided case that is no longer found fails as well
        decided = {'B16': {'decision': 'test', 'differences': [], 'sha256': {}}}
        self.assertEqual(self.c.undecided(self.c.compare(), decided), [('B16', 'decided, but no difference is found any more')])

    def test_a_decision_holds_only_for_the_inputs_it_was_made_on(self):
        keys_b = copy.deepcopy(self.keys_b['keys'])
        keys_b['B16']['answer']['missions'].pop()
        found = self.c.compare(keys_b=keys_b)
        decided = {'B16': dict(found['B16'], decision='test')}
        self.assertEqual(self.c.undecided(found, decided), [])
        tasks = copy.deepcopy(self.c.new_tasks())
        tasks[0]['question'] += ' Changed.'
        self.assertEqual(self.c.undecided(self.c.compare(keys_b=keys_b, tasks=tasks), decided),
                         [('B16', 'decided on other inputs: task changed since the decision')])

    def test_the_keys_must_cover_the_new_tasks(self):
        keys_b = copy.deepcopy(self.keys_b['keys'])
        del keys_b['E27']
        with self.assertRaises(ValueError):
            self.c.compare(keys_b=keys_b)


if __name__ == '__main__':
    unittest.main()
