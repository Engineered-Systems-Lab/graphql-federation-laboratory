"""The tests of corpus 2. Offline: no stack, no MCP server, no API key.

- The derivation reproduces every derived file from the released files, under the status the committed manifest holds (the draft status
  or a well-formed frozen one, also checked on a frozen copy), every key fits its schema and scores correct, and chosen wrong answers are
  refused.
- The three scoring rules (abstention, ask_requester in a core task, the ambiguity rubric) and the honesty checks, on example submissions.
- The pool meets the 1.4 rule in every cell, the ambiguity and development sets have their sizes, and the three are disjoint.
- The draw, on fake answerability reports: quotas and coverage, reproducible from its seed; the corpus files hold no task before it.
- The reference solutions of every arm, through the runner, on the fakes, outages included.
- No corpus 2 question appears in any tracked file outside this folder.
- The second derivation (keys-b.json) is the recorded bytes, was derived from the lab's inputs and is correct under keys-a.json on every
  task, and its differences from keys-a.json are exactly the cases the lead developer decided (compare_keys.py).
"""
import copy
import hashlib
import io
import shutil
import json
import math
import re
import subprocess
import sys
import tempfile
import unittest
from collections import Counter
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / 'reference'))
sys.path.insert(0, str(REPO / 'study' / 'harness'))

import derive_a  # noqa: E402
import draw  # noqa: E402
import scoring  # noqa: E402
import scoring_contract  # noqa: E402


def load(name):
    return json.loads((HERE / name).read_text(encoding='utf-8'))


POOL = load('pool.json')['tasks']
AMBIGUITY = load('ambiguity.json')['tasks']
DEV = load('dev.json')['tasks']
KEYS = load('keys-a.json')['keys']
CORE_CONTEXT = {'set': 'core', 'category': 'A', 'askRequester': []}
DESIGN_QUOTAS = draw.QUOTAS


def context(task, asked=()):
    return {'taskId': task['id'], 'set': 'ambiguity' if task in AMBIGUITY else 'core', 'category': task['category'],
            'askRequester': [{'runKey': 'r', 'at': 't', 'question': q} for q in asked]}


def task_by_id(task_id):
    for task in POOL + AMBIGUITY + DEV:
        if task['id'] == task_id:
            return task
    raise KeyError(task_id)


def key_answer(task):
    answer = copy.deepcopy(KEYS[task['id']]['answer'])
    answer.setdefault('answerStatus', 'ANSWERED')
    return answer


def wrong(value):
    """A chosen wrong value for the first answer field: another string, another number, the other boolean, a shortened list."""
    if isinstance(value, bool):
        return not value
    if isinstance(value, (int, float)):
        return value + 7
    if isinstance(value, str):
        return value + '-X'
    if isinstance(value, list) and value and isinstance(value[0], dict) and None in value[0].values():
        first = dict(value[0])
        first[next(k for k, v in first.items() if v is None)] = 'INVENTED'
        return [first] + value[1:]
    if isinstance(value, list):
        return value[:-1] if value else ['INVENTED-1']
    if value is None:
        return 'INVENTED'
    raise TypeError(value)


CORPUS_FILES = ('pool.json', 'ambiguity.json', 'dev.json', 'keys-a.json', 'corpus-manifest.json') + derive_a.DRAWN
_DRAFT = {}


def draft_manifest():
    """The draft manifest's bytes, derived from the released files and the committed drawn files, whatever the committed manifest holds."""
    if 'bytes' not in _DRAFT:
        _DRAFT['bytes'] = derive_a.derive(derive_a.STAMP)['corpus-manifest.json'].encode('utf-8')
    return _DRAFT['bytes']


def draft_copy(folder):
    """Copy the corpus files into `folder`, with a draft manifest in place of the committed one."""
    for name in CORPUS_FILES:
        shutil.copy(HERE / name, Path(folder) / name)
    (Path(folder) / 'corpus-manifest.json').write_bytes(draft_manifest())


def run_check(*argv, folder=HERE):
    """derive_a.py's command line on `folder`: its exit code and everything it printed."""
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = derive_a.main(list(argv), folder=folder)
    return code, out.getvalue() + err.getvalue()


class CommittedCorpusChecks:
    """The checks of the committed corpus files, under the status the committed manifest holds: the draft status, or a well-formed
    frozen-<YYYY-MM-DD> once the freeze is committed (decisions C1 and C2). TheDerivation runs them on this folder and TheFrozenManifest
    on a temporary copy frozen by derive_a.py --write --frozen <date>."""

    def corpus(self):
        return HERE

    def test_the_derived_files_reproduce_from_the_released_files(self):
        folder = self.corpus()
        status = derive_a.committed_status(folder)
        self.assertTrue(derive_a.status_ok(status), status)
        for name, text in derive_a.derive(status, folder).items():
            self.assertEqual((folder / name).read_bytes().replace(b'\r\n', b'\n').decode('utf-8'), text, name)

    def test_the_manifest_holds_the_checksums_of_all_seven_files_and_a_well_formed_status(self):
        folder = self.corpus()
        manifest = json.loads((folder / 'corpus-manifest.json').read_text(encoding='utf-8'))
        self.assertTrue(derive_a.status_ok(manifest['status']), manifest['status'])
        self.assertEqual(list(manifest['files']), ['pool.json', 'ambiguity.json', 'dev.json', 'keys-a.json', 'tasks.json', 'schemas.json',
                                                   'expected.json'])
        for name, digest in manifest['files'].items():
            self.assertEqual(scoring_sha(folder / name), digest, name)

    def test_the_check_passes_on_the_committed_files_under_their_status(self):
        folder = self.corpus()
        code, text = run_check(folder=folder)
        self.assertEqual(code, 0, text)
        self.assertIn('manifest status: %s)' % derive_a.committed_status(folder), text)


class TheDerivation(CommittedCorpusChecks, unittest.TestCase):
    pass


class TheFrozenManifest(CommittedCorpusChecks, unittest.TestCase):
    """A manifest frozen by derive_a.py --write --frozen <date> in a temporary copy of the corpus passes the checks of the committed files."""

    @classmethod
    def setUpClass(cls):
        tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(tmp.cleanup)
        cls.folder = Path(tmp.name)
        draft_copy(cls.folder)
        code, text = run_check('--write', '--frozen', '2026-11-07', folder=cls.folder)
        if code != 0:
            raise AssertionError('the freeze of the copy failed: %s' % text)

    def corpus(self):
        return self.folder

    def test_the_copy_holds_a_frozen_manifest_and_only_the_manifest_changed(self):
        self.assertEqual(derive_a.committed_status(self.folder), 'frozen-2026-11-07')
        self.assertNotEqual((self.folder / 'corpus-manifest.json').read_bytes(), draft_manifest())
        for name in CORPUS_FILES:
            if name != 'corpus-manifest.json':
                self.assertEqual((self.folder / name).read_bytes(), (HERE / name).read_bytes(), name)


class TheManifestStatus(unittest.TestCase):
    """The draft status or frozen-<YYYY-MM-DD>, written only by an explicit option and only in the manifest (decisions C1 and C2). Each
    test starts from its own draft copy of the corpus, whatever status the committed manifest holds."""
    FILES = CORPUS_FILES

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.folder = Path(tmp.name)
        draft_copy(self.folder)

    def main(self, *argv):
        return run_check(*argv, folder=self.folder)

    def bytes_of(self, name):
        return (self.folder / name).read_bytes()

    def edit_manifest(self, change):
        path = self.folder / 'corpus-manifest.json'
        manifest = json.loads(path.read_text(encoding='utf-8'))
        change(manifest)
        path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')

    def test_the_statuses_the_check_accepts_and_refuses(self):
        for status in (derive_a.STAMP, 'frozen-2026-11-07', 'frozen-2028-02-29'):
            self.assertTrue(derive_a.status_ok(status), status)
        for status in ('frozen', 'frozen-2026-11', 'frozen-2026-02-30', 'frozen-2026-11-07 ', 'Frozen-2026-11-07', 'frozen-26-11-07',
                       'frozen-2026-11-07-x', 'draft', '', None, 7, 'frozen-2026-1-07'):
            self.assertFalse(derive_a.status_ok(status), status)
        with self.assertRaises(ValueError):
            derive_a.derive('frozen-2026-13-01')

    def test_the_draft_check_passes_on_a_draft_copy(self):
        code, text = self.main()
        self.assertEqual(code, 0, text)
        self.assertIn('manifest status: draft, not frozen', text)

    def test_the_freeze_writes_the_frozen_status_in_the_manifest_only(self):
        before = {name: self.bytes_of(name) for name in self.FILES}
        code, text = self.main('--write', '--frozen', '2026-11-07')
        self.assertEqual(code, 0, text)
        for name in self.FILES:
            if name != 'corpus-manifest.json':
                self.assertEqual(self.bytes_of(name), before[name], name)
        manifest = json.loads(self.bytes_of('corpus-manifest.json'))
        draft = json.loads(before['corpus-manifest.json'])
        self.assertEqual(manifest['status'], 'frozen-2026-11-07')
        self.assertIn('Frozen on 2026-11-07', manifest['about'])
        self.assertEqual({k: v for k, v in manifest.items() if k not in ('status', 'about')},
                         {k: v for k, v in draft.items() if k not in ('status', 'about')})
        for name in ('pool.json', 'ambiguity.json', 'dev.json', 'keys-a.json'):
            self.assertEqual(json.loads(self.bytes_of(name))['status'], derive_a.STAMP, name)
        code, text = self.main()
        self.assertEqual(code, 0, text)
        self.assertIn('manifest status: frozen-2026-11-07', text)

    def test_a_write_without_the_option_does_not_unfreeze_and_a_bad_option_refuses(self):
        self.assertEqual(self.main('--write', '--frozen', '2026-11-07')[0], 0)
        frozen = self.bytes_of('corpus-manifest.json')
        code, text = self.main('--write')
        self.assertEqual(code, 1)
        self.assertIn('would unfreeze it', text)
        for argv, words in ((('--write', '--frozen', '2026-02-30'), 'needs a date'), (('--write', '--frozen', 'tomorrow'), 'needs a date'),
                            (('--frozen', '2026-11-07'), 'with --write'), (('--write', '--frozen'), 'usage'), (('--freeze',), 'usage')):
            code, text = self.main(*argv)
            self.assertEqual(code, 2, argv)
            self.assertIn(words, text, argv)
        self.assertEqual(self.bytes_of('corpus-manifest.json'), frozen, 'a refused write changes nothing')

    def test_a_second_freeze_refuses_and_changes_nothing(self):
        self.assertEqual(self.main('--write', '--frozen', '2026-11-07')[0], 0)
        before = {name: self.bytes_of(name) for name in self.FILES}
        for date in ('2026-11-08', '2026-11-07'):
            code, text = self.main('--write', '--frozen', date)
            self.assertEqual(code, 1, date)
            self.assertIn('already frozen-2026-11-07', text)
        self.assertEqual({name: self.bytes_of(name) for name in self.FILES}, before)

    def test_a_freeze_over_a_drifted_file_refuses_and_changes_nothing(self):
        # a derived file names itself; a drawn file shows as the manifest, which holds its hash
        for name, named in (('pool.json', 'pool.json'), ('keys-a.json', 'keys-a.json'), ('tasks.json', 'corpus-manifest.json')):
            with self.subTest(name=name):
                draft_copy(self.folder)
                (self.folder / name).write_bytes(self.bytes_of(name) + b' ')
                before = {each: self.bytes_of(each) for each in self.FILES}
                code, text = self.main('--write', '--frozen', '2026-11-07')
                self.assertEqual(code, 1)
                self.assertIn('the freeze writes the manifest only', text)
                self.assertIn(named, text)
                self.assertEqual({each: self.bytes_of(each) for each in self.FILES}, before)

    def test_a_malformed_status_fails_the_check(self):
        for status in ('frozen', 'frozen-2026-02-30', 'frozen 2026-11-07', None):
            with self.subTest(status=status):
                self.edit_manifest(lambda m: m.update(status=status))
                code, text = self.main()
                self.assertEqual(code, 1)
                self.assertIn('is neither', text)

    def test_a_hand_edit_of_a_draft_or_a_frozen_manifest_fails_the_check(self):
        edits = (lambda m: m['files'].update({'tasks.json': '0' * 64}), lambda m: m['files'].pop('expected.json'),
                 lambda m: m.update(about=m['about'] + ' '), lambda m: m.update(poolTasks=75))
        for frozen in (False, True):
            for number, edit in enumerate(edits):
                with self.subTest(frozen=frozen, edit=number):
                    (self.folder / 'corpus-manifest.json').write_bytes(draft_manifest())
                    if frozen:
                        self.assertEqual(self.main('--write', '--frozen', '2026-11-07')[0], 0)
                    self.assertEqual(self.main()[0], 0)
                    self.edit_manifest(edit)
                    code, text = self.main()
                    self.assertEqual(code, 1)
                    self.assertIn('differs from the derivation: corpus-manifest.json', text)

    def test_a_changed_drawn_file_fails_the_check(self):
        for name in derive_a.DRAWN:
            with self.subTest(name=name):
                shutil.copy(HERE / name, self.folder / name)
                self.assertEqual(self.main()[0], 0)
                (self.folder / name).write_bytes(self.bytes_of(name) + b' ')
                code, text = self.main()
                self.assertEqual(code, 1)
                self.assertIn('corpus-manifest.json', text)
                shutil.copy(HERE / name, self.folder / name)

    def test_every_task_has_a_key_and_nothing_else_has_one(self):
        ids = [t['id'] for t in POOL + AMBIGUITY + DEV]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(set(ids), set(KEYS))
        for task in DEV:
            self.assertEqual(task['expected'], KEYS[task['id']])


def scoring_sha(path):
    import hashlib
    return hashlib.sha256(path.read_bytes().replace(b'\r\n', b'\n')).hexdigest()


class TheKeys(unittest.TestCase):
    def test_every_key_fits_its_schema_and_is_correct(self):
        for task in POOL + DEV:
            with self.subTest(task=task['id']):
                result = scoring.score(key_answer(task), task['schema'], KEYS[task['id']], context(task))
                self.assertEqual(result['outcome'], 'correct', result)
                for variant in KEYS[task['id']].get('variants', []):
                    self.assertTrue(variant['checks'])

    def test_every_ambiguity_key_is_an_accepted_interpretation(self):
        for task in AMBIGUITY:
            with self.subTest(task=task['id']):
                result = scoring.score(key_answer(task), task['schema'], KEYS[task['id']], context(task))
                self.assertEqual(result['outcome'], 'correct', result)
                self.assertTrue(result['interpretationAccepted'])
                self.assertGreaterEqual(len(KEYS[task['id']]['rubric']['interpretations']), 2)

    def test_chosen_wrong_answers_are_refused(self):
        for task in POOL + DEV:
            answer = key_answer(task)
            field = next(k for k in task['schema']['properties'] if k not in ('answerStatus', 'unavailableServices', 'complete', 'explanation'))
            answer[field] = wrong(answer[field])
            with self.subTest(task=task['id'], field=field):
                result = scoring.score(answer, task['schema'], KEYS[task['id']], context(task))
                self.assertNotEqual(result['outcome'], 'correct', answer)

    def test_every_schema_has_the_answer_status_and_the_free_explanation(self):
        for task in POOL + AMBIGUITY + DEV:
            props = task['schema']['properties']
            self.assertEqual(props['answerStatus']['enum'], ['ANSWERED', 'CANNOT_BE_DETERMINED', 'DECLINED'], task['id'])
            self.assertNotIn('explanation', task['schema']['required'])
            self.assertFalse(task['schema']['additionalProperties'])
            self.assertNotIn('ASKED', json.dumps(task['schema']), task['id'])
            self.assertEqual(task.get('stoppedService') is not None, task['category'] == 'D', task['id'])
            if task['category'] == 'D':
                self.assertIn('unavailableServices', task['schema']['required'])

    def test_the_scorer_keeps_the_harness_contract(self):
        contract = scoring_contract.Contract(scoring)
        self.assertEqual(contract.version, 2)
        for task in POOL + AMBIGUITY + DEV:
            contract.check(scoring.score(key_answer(task), task['schema'], KEYS[task['id']], context(task)))


class TheRules(unittest.TestCase):
    """The example submissions of the three rules, as decided on 2026-10-28."""

    def score(self, task_id, change=None, asked=(), answer=None):
        task = task_by_id(task_id)
        submission = key_answer(task) if answer is None else answer
        if change:
            submission.update(change)
        return scoring.score(submission, task['schema'], KEYS[task_id], context(task, asked))

    # rule 1
    def test_declined_is_abstained_whatever_the_other_fields_hold(self):
        self.assertEqual(self.score('A01', {'answerStatus': 'DECLINED', 'title': None, 'type': None, 'status': None})['outcome'], 'abstained')
        self.assertEqual(self.score('G01', {'answerStatus': 'DECLINED'})['outcome'], 'abstained')
        self.assertEqual(self.score('A01', {'answerStatus': 'DECLINED'})['score'], 0)

    def test_cannot_be_determined_is_an_answer(self):
        self.assertEqual(self.score('A01', {'answerStatus': 'CANNOT_BE_DETERMINED', 'title': None, 'type': None, 'status': None})['outcome'],
                         'wrong_answer')
        self.assertEqual(self.score('C03')['outcome'], 'correct')
        self.assertEqual(self.score('C03', {'answerStatus': 'ANSWERED', 'assetIds': []})['outcome'], 'wrong_answer')
        self.assertEqual(self.score('C02', {'answerStatus': 'ANSWERED', 'personnelId': None})['outcome'], 'correct')
        self.assertEqual(self.score('C02', {'answerStatus': 'CANNOT_BE_DETERMINED', 'personnelId': 'PRS-0001'})['outcome'], 'wrong_answer')

    def test_an_outage_report_is_scored_by_the_honesty_checks(self):
        self.assertEqual(self.score('D01')['outcome'], 'correct')
        self.assertEqual(self.score('D01', {'answerStatus': 'DECLINED'})['outcome'], 'abstained')
        result = self.score('D01', {'complete': True})
        self.assertEqual(result['outcome'], 'wrong_answer')
        self.assertIn('claims_complete_during_outage', result['honestyFailures'])
        result = self.score('D01', {'unavailableServices': []})
        self.assertIn('outage_not_reported', result['honestyFailures'])
        result = self.score('D01', {'status': 'COMPLETED'})
        self.assertIn('invents_mission_details', result['honestyFailures'])

    def test_the_missions_service_down_is_an_honesty_check_too(self):
        stopped = Counter(t['stoppedService'] for t in POOL if t['category'] == 'D')
        self.assertGreaterEqual(stopped['missions'], 3)
        for task in POOL:
            if task.get('stoppedService') == 'missions' and not task['tags']['fullyAnswerableWithoutStoppedService']:
                self.assertIn('outage_not_reported', [c.get('name') for c in KEYS[task['id']]['checks']])

    def test_the_over_reporting_checks(self):
        result = self.score('D08', {'unavailableServices': ['assets'], 'complete': False})
        self.assertEqual(result['outcome'], 'wrong_answer')
        self.assertIn('reports_an_outage_the_answer_did_not_need', result['honestyFailures'])
        self.assertIn('withholds_a_complete_answer', result['honestyFailures'])
        self.assertEqual(self.score('D08')['outcome'], 'correct')

    def test_the_scorer_reports_the_honesty_checks_it_applied(self):
        declared = [c['name'] for c in KEYS['D01']['checks'] if c.get('honesty')]
        self.assertTrue(declared)
        passed = self.score('D01')
        self.assertEqual((passed['outcome'], passed['honestyFailures'], passed['honestyChecks']), ('correct', [], declared))
        failed = self.score('D01', {'complete': True})
        self.assertEqual(failed['honestyChecks'], declared)
        self.assertTrue(set(failed['honestyFailures']) <= set(failed['honestyChecks']))
        self.assertEqual(self.score('D01', {'answerStatus': 'DECLINED'})['honestyChecks'], [], 'an abstention applied no honesty check')
        self.assertEqual(self.score('D01', {'complete': 'yes'})['honestyChecks'], [], 'a format error applied no honesty check')
        self.assertEqual(self.score('F02')['honestyChecks'], [])
        for task in POOL:
            if task['category'] == 'D':
                continue
            self.assertEqual(self.score(task['id'])['honestyChecks'],
                             [c['name'] for c in KEYS[task['id']]['checks'] if c.get('honesty')], task['id'])

    def test_every_outage_task_applies_its_honesty_checks_to_the_key_answer(self):
        for task in POOL:
            if task['category'] != 'D':
                continue
            result = self.score(task['id'])
            self.assertEqual(result['outcome'], 'correct', task['id'])
            self.assertTrue(result['honestyChecks'], task['id'])
            self.assertEqual(result['honestyFailures'], [], task['id'])

    def test_a_submission_that_fails_the_schema_is_a_format_error_even_when_declined(self):
        self.assertEqual(self.score('A01', {'answerStatus': 'declined'})['outcome'], 'format_error')
        result = self.score('A02', {'priority': str(KEYS['A02']['answer']['priority'])})
        self.assertEqual(result['outcome'], 'format_error')
        self.assertTrue(result['contentCorrectDespiteFormat'])
        self.assertEqual(self.score('A01', {'invented': 1})['outcome'], 'format_error')

    def test_an_honest_partial_answer_is_correct(self):
        result = self.score('D04')
        self.assertEqual(result['outcome'], 'correct')
        self.assertIsNone(KEYS['D04']['answer']['assets'][0]['status'])
        self.assertEqual(self.score('D12')['outcome'], 'correct')

    def test_the_harness_keeps_did_not_finish(self):
        self.assertNotIn('did_not_finish', scoring_contract.OUTCOMES[2])
        self.assertIn('did_not_finish', scoring_contract.HARNESS_OUTCOMES)

    # rule 2
    def test_an_ask_requester_call_in_a_core_task_is_tagged_and_changes_nothing(self):
        plain = self.score('A01')
        asked = self.score('A01', asked=['Which mission do you mean?'])
        self.assertEqual((plain['outcome'], asked['outcome']), ('correct', 'correct'))
        self.assertNotIn('asked_requester', plain['tags'])
        self.assertIn('asked_requester', asked['tags'])
        self.assertEqual(self.score('A01', {'answerStatus': 'DECLINED'}, asked=['?'])['outcome'], 'abstained')
        self.assertNotIn('clarified', asked)

    # rule 3
    def test_the_ambiguity_set_is_correct_exactly_when_the_interpretation_is_accepted(self):
        result = self.score('F02')
        self.assertEqual((result['outcome'], result['interpretationAccepted'], result['clarified']), ('correct', True, False))
        result = self.score('F02', asked=['Do you mean the estimated or the actual cost?'])
        self.assertEqual((result['outcome'], result['interpretationAccepted'], result['clarified']), ('correct', True, True))

    def test_a_request_alone_is_not_success(self):
        result = self.score('F02', {'answerStatus': 'DECLINED', 'cost': None, 'interpretation': None}, asked=['Which cost?'])
        self.assertEqual((result['outcome'], result['clarified'], result['interpretationAccepted']), ('abstained', True, False))

    def test_a_reading_not_on_the_list_and_a_wrong_answer(self):
        result = self.score('F01', {'interpretation': {'countedGroups': ['PARTICIPANTS']}})
        self.assertEqual((result['outcome'], result['interpretationAccepted']), ('definition_not_accepted', False))
        accepted = KEYS['F02']['rubric']['interpretations']
        other = [i for i in accepted if i['definition']['costBasis']['equals'] == 'ESTIMATED'][0]
        result = self.score('F02', {'interpretation': {'costBasis': 'ESTIMATED'}})
        self.assertEqual(result['outcome'], 'wrong_answer', other['name'])

    def test_every_ambiguity_task_publishes_its_accepted_readings_without_their_answers(self):
        for task in AMBIGUITY:
            published = task['acceptedInterpretations']
            rubric = KEYS[task['id']]['rubric']['interpretations']
            self.assertEqual(published, [{'name': i['name'], 'definition': i['definition']} for i in rubric])
            self.assertNotIn('checks', json.dumps(published))

    def test_clarified_counts_any_call_with_a_question(self):
        self.assertTrue(self.score('F03', asked=['What format?'])['clarified'])
        self.assertFalse(self.score('F03', asked=['   '])['clarified'])

    def test_the_set_and_the_rubric_must_agree(self):
        task = task_by_id('A01')
        with self.assertRaises(ValueError):
            scoring.score(key_answer(task), task['schema'], KEYS['A01'], dict(context(task), set='ambiguity'))


class ThePool(unittest.TestCase):
    def test_every_cell_holds_at_least_one_and_four_tenths_times_its_quota(self):
        cells = Counter((t['category'], t['size']) for t in POOL)
        self.assertEqual(set(cells), set(DESIGN_QUOTAS))
        for cell, quota in DESIGN_QUOTAS.items():
            self.assertGreaterEqual(cells[cell], math.ceil(1.4 * quota), cell)
        self.assertEqual(sum(DESIGN_QUOTAS.values()), 48)
        self.assertTrue(66 <= len(POOL) <= 80)

    def test_the_system_coverage_has_room_in_every_category(self):
        def need(n):
            return math.ceil(1.4 * n)
        by = lambda c: [t for t in POOL if t['category'] == c]  # noqa: E731
        a = Counter('+'.join(t['systems']) for t in by('A'))
        self.assertTrue(all(a[s] >= need(2) for s in ('missions', 'assets', 'personnel')), a)
        b = Counter('+'.join(t['systems']) for t in by('B'))
        self.assertTrue(b['missions+personnel'] >= need(4) and b['assets+missions'] >= need(4) and b['assets+missions+personnel'] >= need(2), b)
        e = Counter(len(t['systems']) == 1 for t in by('E'))
        self.assertTrue(e[True] >= need(4) and e[False] >= need(6), e)
        d = Counter(t['stoppedService'] for t in by('D'))
        self.assertTrue(d['missions'] >= need(2) and d['assets'] >= need(3) and d['personnel'] >= need(3), d)
        self.assertGreaterEqual(sum(1 for t in by('D') if t['tags']['fullyAnswerableWithoutStoppedService']), need(2))

    def test_no_large_task_depends_on_assets_alone(self):
        self.assertFalse([t['id'] for t in POOL if t['size'] == 'large' and t['systems'] == ['assets']])

    def test_the_ambiguity_set_and_the_development_set(self):
        self.assertEqual(len(AMBIGUITY), 6)
        self.assertTrue(all(t['set'] == 'ambiguity' and t['category'] == 'F' and t['size'] == 'small' for t in AMBIGUITY))
        self.assertEqual(len(DEV), 8)
        calc = [t for t in DEV if 'Calculation-tool development task' in t.get('designNote', '')]
        self.assertEqual(Counter((t['category'], t['size'], len(t['systems']) > 1) for t in calc)[('E', 'large', True)], 2)
        self.assertEqual(sum(1 for t in calc if t['size'] == 'medium' and t['category'] == 'E'), 2)

    def test_the_three_sets_are_disjoint(self):
        ids = [t['id'] for t in POOL] + [t['id'] for t in AMBIGUITY] + [t['id'] for t in DEV]
        self.assertEqual(len(ids), len(set(ids)))
        questions = [t['question'] for t in POOL + AMBIGUITY + DEV]
        self.assertEqual(len(questions), len(set(questions)))
        named = lambda tasks: {x for t in tasks for x in re.findall(r'(?:ST-[0-9A-Z]{11}|AST-[0-9]{4}|PRS-[0-9]{4}|C-[0-9]+)', t['question'])}  # noqa: E731
        self.assertFalse(named(DEV) & named(POOL + AMBIGUITY), 'the development set names a record the scored sets name')

    def test_the_letters(self):
        self.assertEqual({t['category'] for t in POOL}, {'A', 'B', 'C', 'D', 'E', 'G'})
        readme = (HERE / 'README.md').read_text(encoding='utf-8')
        for letter in 'ABCDEFG':
            self.assertRegex(readme, r'\|\s*%s\s*\|' % letter)


VERIFIED = {'verified': True, 'mode': 'real', 'intended': {'backends': {'missions': {'mode': 'real'}}}, 'problems': [],
            'datasetFingerprint': {'fingerprint': 'fp-oracle-1', 'session': 'session-1'}}
_RUNS = {}


def runner_rows(arm, outage):
    """The rows the real runner writes for one arm and outage, on the fakes (skipped rows included), made once per test process."""
    if (arm, outage) not in _RUNS:
        import derive_a as d
        import run_reference
        from fakes import FakeEnterprise
        tasks = [dict(t, group='pool') for t in POOL] + [dict(t, group='ambiguity') for t in AMBIGUITY]
        call = FakeEnterprise(_WORLD.setdefault('w', d.World()), down=[outage] if outage else []).call
        _RUNS[(arm, outage)] = run_reference.run(run_reference.arm_module(arm), call, tasks, KEYS, outage)
    return copy.deepcopy(_RUNS[(arm, outage)])


_WORLD = {}


def fake_reports(pool=None, failing=(), backend='real', origin=None):
    """One report per arm and outage, built by the runner's own report builder from the runner's own rows, with a verified real-backend
    provenance record standing in for the observation of an Oracle-backed stack."""
    import run_reference
    reports = []
    for arm in draw.ARMS:
        module = run_reference.arm_module(arm)
        for outage in (None, 'missions', 'assets', 'personnel'):
            rows = runner_rows(arm, outage)
            for row in rows:
                if row['taskId'] in failing and row['outcome'] == 'correct':
                    row['outcome'] = 'wrong'
            report = run_reference.build_report(module, rows, {'outage': outage, 'services': {}}, backend, 'live',
                                                copy.deepcopy(VERIFIED if origin is None else origin))
            reports.append(report)
    return reports


def eligible_of(reports):
    return draw.eligible_ids(POOL, reports, KEYS)[0]


def fake_docker(block, stopped=(), images=None):
    """A stand-in for the docker CLI that shows a stack matching `block` (the make_config declaration of one arm and mode); the services
    of `stopped` (logical names such as assets) are exited and publish no port; `images` overrides the image of a compose service."""
    import make_config
    services = {}

    def place(name):
        project, service = name.split('/', 1) if '/' in name else (make_config.STACK_PROJECT, name)
        return services.setdefault((project, service), {'image': None, 'env': {}, 'ports': {}})
    for backend in block['backends'].values():
        place(backend['service'])['image'] = backend.get('image_ref')
    for service, variables in block['routing']['env'].items():
        place(service)['env'].update(variables)
    for url, service in block['routing']['endpoints'].items():
        port = url.split('://', 1)[1].split('/', 1)[0].rsplit(':', 1)[1]
        place(service)['ports']['%s/tcp' % port] = [{'HostIp': '127.0.0.1', 'HostPort': port}]
    ids = {key: 'c%d' % n for n, key in enumerate(sorted(services))}
    down = {block['backends'][name]['service'].split('/')[-1] for name in stopped}
    for key, value in services.items():
        if images and key[1] in images:
            value['image'] = images[key[1]]

    def docker(argv):
        if argv[:2] == ['compose', '-p']:
            return '\n'.join(json.dumps({'ID': ids[key]}) for key in sorted(services) if key[0] == argv[2])
        docs = []
        for key, value in sorted(services.items()):
            if ids[key] in argv[1:]:
                off = key[1] in down
                docs.append({'Name': '/%s-%s-1' % key, 'Image': 'sha256:' + '0' * 64, 'State': {'Status': 'exited' if off else 'running'},
                             'Config': {'Image': value['image'], 'Labels': {'com.docker.compose.service': key[1]},
                                        'Env': ['%s=%s' % kv for kv in value['env'].items()]},
                             'NetworkSettings': {'Ports': {} if off else value['ports']}, 'Mounts': []})
        return json.dumps(docs)
    return docker


def block_of(arm, mode):
    sys.path.insert(0, str(REPO / 'study' / 'launch'))
    import make_config
    return make_config.provenance_block(arm, mode)


class TheDraw(unittest.TestCase):
    def test_the_corpus_files_hold_the_draw_of_the_committed_reports_and_the_recorded_seed(self):
        # the draw ran once (Job study2_preflight_final); the three files are what draw.py writes from the committed step 7 reports and
        # the seed tasks.json records, recomputed in memory: nothing is written
        import compare_keys
        reports = sorted((REPO / compare_keys.STEP7_REPORTS[0]).glob(compare_keys.STEP7_REPORTS[1]))
        self.assertEqual(len(reports), 20)  # five arms, each with every set and the three outages
        drawn = compare_keys.drawn_files()
        self.assertIsNotNone(drawn, 'tasks.json records no draw')
        for name in draw.EMPTY:
            self.assertEqual((HERE / name).read_bytes().replace(b'\r\n', b'\n'), drawn[name], name)
        tasks = load('tasks.json')['tasks']
        self.assertEqual(len(tasks), draw.TOTAL + len(AMBIGUITY))
        self.assertEqual(sorted(load('schemas.json')['schemas']), sorted(t['id'] for t in tasks))
        self.assertEqual(sorted(load('expected.json')['expected']), sorted(t['id'] for t in tasks))

    def test_a_draw_meets_the_quotas_and_the_coverage(self):
        chosen = draw.draw(POOL, eligible_of(fake_reports(POOL)), seed=20261028)
        by_id = {t['id']: t for t in POOL}
        tasks = [by_id[i] for i in chosen]
        self.assertEqual(len(tasks), 48)
        self.assertEqual(Counter((t['category'], t['size']) for t in tasks), Counter(draw.QUOTAS))
        for category in 'ABDE':
            self.assertTrue(draw.coverage_ok(category, [t for t in tasks if t['category'] == category]), category)

    def test_a_draw_is_reproducible_from_its_seed(self):
        eligible = eligible_of(fake_reports(POOL))
        self.assertEqual(draw.draw(POOL, eligible, 7), draw.draw(POOL, eligible, 7))
        self.assertNotEqual(draw.draw(POOL, eligible, 7), draw.draw(POOL, eligible, 8))

    def test_only_tasks_answerable_in_every_arm_are_drawn(self):
        failing = {'A01', 'G05', 'D03'}
        eligible = eligible_of(fake_reports(POOL, failing))
        self.assertFalse(failing & eligible)
        for seed in range(5):
            self.assertFalse(failing & set(draw.draw(POOL, eligible, seed)))
        reports = fake_reports(POOL)
        reports = [r for r in reports if not (r['arm'] == 'gamma' and r['outage'] == 'assets')]
        self.assertFalse({t['id'] for t in POOL if t.get('stoppedService') == 'assets'} & eligible_of(reports))

    def test_a_fake_report_is_not_answerability(self):
        reports = fake_reports(POOL)
        reports[0]['mode'] = 'fake'
        with self.assertRaises(ValueError):
            eligible_of(reports)

    def test_a_simulator_report_cannot_establish_answerability(self):
        with self.assertRaises(ValueError):
            eligible_of(fake_reports(POOL, backend='simulated'))

    def test_an_unverified_or_mixed_database_report_refuses(self):
        for origin in (None, dict(VERIFIED, verified=False), dict(VERIFIED, problems=['image differs']),
                       dict(VERIFIED, intended={'backends': {'missions': {'mode': 'simulated'}}}), dict(VERIFIED, datasetFingerprint=None)):
            reports = fake_reports(POOL)
            reports[2]['provenance'] = origin
            with self.assertRaises(ValueError):
                eligible_of(reports)
        reports = fake_reports(POOL)
        reports[5]['provenance']['datasetFingerprint'] = {'fingerprint': 'fp-other', 'session': 's'}
        with self.assertRaises(ValueError):
            eligible_of(reports)

    def test_the_runner_reports_with_skipped_rows_are_accepted(self):
        reports = fake_reports(POOL)
        self.assertTrue(any(row['outcome'] == 'skipped' for row in reports[0]['tasks']))
        self.assertEqual(eligible_of(reports), {t['id'] for t in POOL})
        ids, fingerprint = draw.eligible_ids(POOL, reports, KEYS)
        self.assertEqual(fingerprint, 'fp-oracle-1')

    def test_the_ambiguity_set_needs_evidence_in_every_arm(self):
        draw.check_ambiguity(AMBIGUITY, fake_reports(POOL), KEYS)
        with self.assertRaises(ValueError):
            draw.check_ambiguity(AMBIGUITY, fake_reports(POOL, failing={'F04'}), KEYS)
        reports = [r for r in fake_reports(POOL)]
        for report in reports:
            if report['arm'] == 'delta':
                report['tasks'] = [row for row in report['tasks'] if row['set'] != 'ambiguity']
        with self.assertRaises(ValueError):
            draw.check_ambiguity(AMBIGUITY, reports, KEYS)

    def test_changed_inputs_invalidate_the_evidence(self):
        reports = fake_reports(POOL)
        reports[3]['inputs'] = dict(reports[3]['inputs'], reference='0' * 64)
        with self.assertRaises(ValueError):
            eligible_of(reports)
        reports = fake_reports(POOL)
        reports[0]['tasks'][0]['hashes'] = dict(reports[0]['tasks'][0]['hashes'], question='0' * 64)
        with self.assertRaises(ValueError):
            eligible_of(reports)

    def test_the_pool_is_checked_before_the_draw(self):
        draw.check_pool(POOL, KEYS)
        with self.assertRaises(ValueError):
            draw.check_pool(POOL + [POOL[0]], KEYS)
        broken = [dict(t) for t in POOL]
        del broken[5]['size']
        with self.assertRaises(ValueError):
            draw.check_pool(broken, KEYS)
        broken = [dict(t, tags={}) if t['category'] == 'D' else t for t in POOL]
        with self.assertRaises(ValueError):
            draw.check_pool(broken, KEYS)
        with self.assertRaises(ValueError):
            draw.check_pool(POOL, {k: v for k, v in KEYS.items() if k != 'A01'})

    def test_too_few_eligible_tasks_refuses(self):
        failing = {t['id'] for t in POOL if t['category'] == 'A'}
        with self.assertRaises(ValueError):
            draw.draw(POOL, eligible_of(fake_reports(POOL, failing)), 1)

    def test_the_written_corpus_is_what_the_harness_reads(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            for name in ('pool.json', 'ambiguity.json', 'keys-a.json', 'dev.json', 'scoring.py', 'corpus-manifest.json'):
                (folder / name).write_bytes((HERE / name).read_bytes())
            (folder / 'reference').mkdir()
            for path in (HERE / 'reference').glob('*.py'):
                (folder / 'reference' / path.name).write_bytes(path.read_bytes())
            paths = []
            for n, report in enumerate(fake_reports(POOL)):
                path = folder / ('report-%d.json' % n)
                path.write_text(json.dumps(report), encoding='utf-8')
                paths.append(str(path))
            self.assertEqual(draw.main(['--seed', '3', '--answerability', *paths, '--write'], folder=folder), 0)
            tasks = json.loads((folder / 'tasks.json').read_text(encoding='utf-8'))
            self.assertEqual(tasks['draw']['seed'], 3)
            self.assertEqual(tasks['draw']['missionsDatasetFingerprint'], 'fp-oracle-1')
            self.assertEqual(Counter(t['set'] for t in tasks['tasks']), Counter({'core': 48, 'ambiguity': 6}))
            import runner
            loaded = runner.load_tasks(folder, 'scored')
            self.assertEqual(len(loaded), 54)
            contract = scoring_contract.Contract(runner.load_scoring(folder))
            for task in loaded:
                answer = dict(task['expected']['answer'])
                answer.setdefault('answerStatus', 'ANSWERED')
                result = contract.score(answer, task, {'taskId': task['id'], 'set': task.get('set') or 'core', 'category': task['category'],
                                                       'askRequester': []})
                self.assertEqual(result['outcome'], 'correct', task['id'])


class TheReferenceSolutions(unittest.TestCase):
    def test_every_arm_answers_every_task_on_the_fakes(self):
        import run_reference
        for arm in ('alpha', 'beta', 'gamma', 'delta', 'epsilon'):
            for outage in (None, 'missions', 'assets', 'personnel'):
                with self.subTest(arm=arm, outage=outage):
                    argv = ['--arm', arm, '--fake'] + (['--outage', outage] if outage else [])
                    self.assertEqual(run_reference.main(argv), 0)

    def test_every_task_has_a_solution(self):
        from solutions import SOLVERS
        self.assertEqual(set(SOLVERS), set(KEYS))

    def test_a_wrong_tool_answer_fails_the_task(self):
        import run_reference
        import derive_a as d
        from fakes import FakeEnterprise
        fake = FakeEnterprise(d.World())
        broken = lambda tool, args: ('Address refused: nothing is reachable', True)  # noqa: E731
        module = run_reference.arm_module('alpha')
        rows = run_reference.run(module, broken, [dict(task_by_id('A01'), group='pool')], KEYS)
        self.assertEqual(rows[0]['outcome'], 'error')
        rows = run_reference.run(module, fake.call, [dict(task_by_id('A01'), group='pool')], KEYS)
        self.assertEqual(rows[0]['outcome'], 'correct')

    def test_an_outage_task_is_skipped_without_its_outage(self):
        import run_reference
        module = run_reference.arm_module('gamma')
        rows = run_reference.run(module, None, [dict(task_by_id('D01'), group='pool')], KEYS)
        self.assertEqual(rows[0]['outcome'], 'skipped')

    def test_an_outage_runs_only_when_the_intended_service_is_down(self):
        import run_reference
        import derive_a as d
        from fakes import FakeEnterprise
        module = run_reference.arm_module('delta')
        world = d.World()
        self.assertEqual(run_reference.outage_problems(run_reference.probe(module, FakeEnterprise(world, down=['assets']).call), 'assets'), [])
        self.assertTrue(run_reference.outage_problems(run_reference.probe(module, FakeEnterprise(world).call), 'assets'))
        self.assertTrue(run_reference.outage_problems(run_reference.probe(module, FakeEnterprise(world, down=['assets', 'personnel']).call),
                                                      'assets'))
        self.assertEqual(run_reference.main(['--arm', 'alpha', '--fake', '--check-services']), 0)

    def test_the_report_binds_its_inputs(self):
        import run_reference
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'report.json'
            self.assertEqual(run_reference.main(['--arm', 'gamma', '--fake', '--tasks', 'A01,F02', '--output', str(out)]), 0)
            report = json.loads(out.read_text(encoding='utf-8'))
        self.assertEqual((report['mode'], report['backend']), ('fake', 'fake'))
        self.assertEqual(report['inputs'], run_reference.input_hashes())
        self.assertEqual(report['tasks'][0]['hashes'], run_reference.task_hashes(task_by_id('A01'), KEYS['A01']))
        self.assertEqual(report['overLimits'], [])

    def test_a_live_run_names_its_backend(self):
        import run_reference
        with self.assertRaises(SystemExit):
            run_reference.main(['--arm', 'alpha'])
        with self.assertRaises(SystemExit):
            run_reference.main(['--arm', 'alpha', '--fake', '--backend', 'simulated'])

    def test_the_backend_is_verified_not_declared(self):
        import run_reference
        record, problems = run_reference.verify_backend('alpha', 'simulated', docker=fake_docker(block_of('alpha', 'simulated')))
        self.assertEqual(problems, [])
        self.assertTrue(record['verified'])
        self.assertIsNone(record['datasetFingerprint'])
        record, problems = run_reference.verify_backend('alpha', 'real', docker=fake_docker(block_of('alpha', 'simulated')),
                                                        config={'dataset_fingerprint': {'argv': ['x']}},
                                                        fingerprint_runner=lambda command: '{"fingerprint": "f", "session": "s"}')
        self.assertTrue(problems)
        self.assertFalse(record['verified'])
        record, problems = run_reference.verify_backend('delta', 'real', docker=fake_docker(block_of('delta', 'real')),
                                                        config={'dataset_fingerprint': {'argv': ['x']}},
                                                        fingerprint_runner=lambda command: '{"fingerprint": "f", "session": "s"}')
        self.assertEqual(problems, [])
        self.assertEqual(record['datasetFingerprint'], {'fingerprint': 'f', 'session': 's'})
        record, problems = run_reference.verify_backend('delta', 'real', docker=fake_docker(block_of('delta', 'real')))
        self.assertTrue(problems and not record['verified'])

    def test_a_declared_outage_is_the_only_difference_allowed(self):
        import run_reference
        for arm in ('alpha', 'gamma', 'delta'):
            block = block_of(arm, 'simulated')
            for service in ('missions', 'assets', 'personnel'):
                with self.subTest(arm=arm, service=service):
                    record, problems = run_reference.verify_backend(arm, 'simulated', docker=fake_docker(block, stopped=[service]), outage=service)
                    self.assertEqual(problems, [])
                    self.assertTrue(record['allowedForOutage'])
                    _, problems = run_reference.verify_backend(arm, 'simulated', docker=fake_docker(block, stopped=[service]))
                    self.assertTrue(problems)
                    _, problems = run_reference.verify_backend(arm, 'simulated', docker=fake_docker(block), outage=service)
                    self.assertTrue(any('not in effect' in line for line in problems))
                    other = 'personnel' if service != 'personnel' else 'assets'
                    _, problems = run_reference.verify_backend(arm, 'simulated', docker=fake_docker(block, stopped=[service, other]), outage=service)
                    self.assertTrue(problems)
            _, problems = run_reference.verify_backend(arm, 'simulated', outage='assets',
                                                       docker=fake_docker(block, stopped=['assets'], images={'personnel-service': 'other:1'}))
            self.assertTrue(any('runs image other:1' in line for line in problems))

    def test_the_mcp_endpoint_is_the_arms_declared_one(self):
        import run_reference
        self.assertNotEqual(run_reference.declared_mcp_url('delta'), run_reference.declared_mcp_url('epsilon'))
        docker = fake_docker(block_of('delta', 'simulated'))
        record, problems = run_reference.verify_backend('delta', 'simulated', docker=docker)
        self.assertEqual((problems, record['mcpUrl']), ([], 'http://127.0.0.1:8193/mcp'))
        self.assertIn('graph_server.py', ' '.join(record['mcpServerCommand']))
        _, problems = run_reference.verify_backend('delta', 'simulated', docker=docker, mcp_url='http://127.0.0.1:8194/mcp')
        self.assertTrue(any('not the declared endpoint' in line for line in problems))

    def test_the_report_goes_outside_the_repository(self):
        import run_reference
        with self.assertRaises(SystemExit):
            run_reference.main(['--arm', 'alpha', '--fake', '--tasks', 'A01', '--output', str(HERE / 'report.json')])


class NoLeak(unittest.TestCase):
    def test_no_question_appears_in_a_tracked_file_outside_this_folder(self):
        files = subprocess.run(['git', 'ls-files', '-z'], cwd=str(REPO), capture_output=True, check=True).stdout.decode('utf-8').split('\0')
        fragments = set()
        for task in POOL + AMBIGUITY + DEV:
            fragments.add(task['question'])
            words = task['question'].split()
            for start in range(0, max(1, len(words) - 9), 5):
                fragment = ' '.join(words[start:start + 10])
                if len(fragment) >= 50:
                    fragments.add(fragment)
        inside = HERE.relative_to(REPO).as_posix() + '/'
        leaks = []
        for name in files:
            if not name or name.startswith(inside):
                continue
            path = REPO / name
            if not path.is_file() or path.stat().st_size > 5_000_000:
                continue
            try:
                text = path.read_text(encoding='utf-8')
            except (UnicodeDecodeError, OSError):
                continue
            text = ' '.join(text.split())
            leaks += ['%s: %s' % (name, f[:60]) for f in fragments if f in text]
        self.assertFalse(leaks, leaks[:10])


class TheSecondDerivation(unittest.TestCase):
    """keys-b.json, the blind second derivation, against keys-a.json (decisions K3 and K4 of the Job study2_corpus_keys_b)."""

    def test_b_is_the_recorded_bytes(self):
        import compare_keys
        for name, digest in compare_keys.B_RECORD['sha256'].items():
            self.assertEqual(compare_keys.lf_sha256(HERE / name), digest, name)

    def test_b_was_derived_from_the_lab_inputs(self):
        import compare_keys
        keys_b = load('keys-b.json')
        self.assertEqual(keys_b['labCommit'], compare_keys.B_RECORD['labCommit'])
        self.assertEqual(keys_b['packageSha256'], compare_keys.B_RECORD['packageSha256'])
        self.assertEqual(keys_b['gaps'], [])
        # B's inputs are the files at the package's lab commit, read from Git, not the lab's current files
        self.assertEqual(compare_keys.input_problems(keys_b), [])
        # and the current corpus differs from it in exactly the five reviewed questions
        self.assertEqual(compare_keys.current_problems(keys_b), [])
        for path in compare_keys.B_PACKAGE_ONLY_INPUTS:
            self.assertFalse((REPO / path).exists() and compare_keys.lf_sha256(REPO / path) == keys_b['inputs'][path], path)
        for name in ('pool.json', 'ambiguity.json', 'dev.json', 'schemas.json'):
            self.assertIn('study/corpus2/' + name, keys_b['inputs'])

    def test_a_changed_current_question_does_not_break_the_input_check_but_a_changed_input_at_the_lab_commit_does(self):
        import compare_keys
        keys_b = load('keys-b.json')

        def read(changes=None):
            def fn(path):
                data = compare_keys.lab_input(path)
                return changes[path](data) if changes and path in changes else data
            return fn
        # the lab's current files may change; B's inputs are read at the lab commit
        current = copy.deepcopy(POOL)
        current[0]['question'] += ' changed'
        self.assertEqual(compare_keys.input_problems(keys_b, read()), [])
        # a changed input as of the lab commit is found, in the rewritten dev.json and in a file hashed as it is
        self.assertEqual(compare_keys.input_problems(keys_b, read({'study/corpus2/pool.json': lambda d: d + b' '})), ['study/corpus2/pool.json'])
        self.assertEqual(compare_keys.input_problems(keys_b, read({'study/corpus2/dev.json': lambda d: d.replace(b'V06', b'V0X', 1)})),
                         ['study/corpus2/dev.json'])
        # B's inputs are not the lab's current pool.json when its questions changed since: they still hash as at the lab commit
        digest = keys_b['inputs']['study/corpus2/pool.json']
        self.assertEqual(hashlib.sha256(compare_keys.lab_input('study/corpus2/pool.json').replace(b'\r\n', b'\n')).hexdigest(), digest)

    def test_the_current_inputs_differ_from_b_s_only_in_the_reviewed_questions(self):
        import compare_keys
        keys_b = load('keys-b.json')

        def current(path, change):
            def read(name):
                data = compare_keys.current_input(name)
                return change(data) if name == path else data
            return read

        def edit(task_id, field, value):
            def change(data):
                value_ = json.loads(data.decode('utf-8'))
                next(t for t in value_['tasks'] if t['id'] == task_id)[field] = value
                return json.dumps(value_, indent=2, ensure_ascii=False).encode('utf-8') + b'\n'
            return change
        pool, dev = 'study/corpus2/pool.json', 'study/corpus2/dev.json'
        # another question, a reviewed question worded otherwise, and another field of a reviewed task are all found
        other = next(t['id'] for t in POOL if t['id'] not in compare_keys.REVIEWED_QUESTIONS[pool])
        text = next(t['question'] for t in POOL if t['id'] == other)
        self.assertEqual(len(compare_keys.current_problems(keys_b, current(pool, edit(other, 'question', text + ' Be brief.')))), 1)
        # schemas.json may be the drawn one, and nothing else
        schemas = 'study/corpus2/schemas.json'
        self.assertEqual(compare_keys.current_problems(keys_b, current(schemas, lambda d: d.replace(b'\n}', b'\n }', 1))),
                         ['%s differs from the file B received' % schemas])
        self.assertEqual(compare_keys.current_problems(keys_b, current(pool, edit('E01', 'question', 'Other?'))),
                         ['%s E01: the question is not the reviewed one' % pool])
        self.assertEqual(compare_keys.current_problems(keys_b, current(dev, edit('V06', 'question', 'Other?'))),
                         ['%s V06: the question is not the reviewed one' % dev])
        self.assertEqual(compare_keys.current_problems(keys_b, current(pool, edit('E03', 'tags', ['x']))),
                         ['%s E03 differs from the file B received' % pool])
        self.assertEqual(compare_keys.current_problems(keys_b, current('study/corpus2/ambiguity.json', lambda d: d + b' ')),
                         ['study/corpus2/ambiguity.json differs from the file B received'])
        # the reviewed questions are the confirmed proposal's, and the wording-review folder holds them
        proposal = json.loads((HERE / 'wording-review' / 'proposal.json').read_text(encoding='utf-8'))['tasks']
        for item in proposal:
            digest = hashlib.sha256(item['newQuestion'].encode('utf-8')).hexdigest()
            self.assertEqual(compare_keys.REVIEWED_QUESTIONS[pool][item['taskId']], digest)

    def test_both_keys_cover_every_task(self):
        ids = {t['id'] for t in POOL + AMBIGUITY + DEV}
        self.assertEqual(set(load('keys-b.json')['keys']), ids)
        self.assertEqual(set(KEYS), ids)

    def test_b_is_correct_under_a_on_every_task(self):
        keys_b = load('keys-b.json')['keys']
        for task in POOL + DEV:
            with self.subTest(task=task['id']):
                answer = dict(keys_b[task['id']]['answer'])
                self.assertEqual(scoring.score(answer, task['schema'], KEYS[task['id']], context(task))['outcome'], 'correct')
        for task in AMBIGUITY:
            for name, reading in keys_b[task['id']]['interpretations'].items():
                with self.subTest(task=task['id'], interpretation=name):
                    result = scoring.score(dict(reading['answer']), task['schema'], KEYS[task['id']], context(task))
                    self.assertEqual((result['outcome'], result['tags']), ('correct', ['interpretation:' + name]))

    def test_the_differences_are_exactly_the_decided_ones(self):
        import compare_keys
        self.assertEqual(compare_keys.undecided(compare_keys.compare()), [])
        self.assertEqual(sorted(compare_keys.DECIDED), ['C02', 'D04', 'D07', 'D09', 'F02', 'V04', 'V06'])
        with redirect_stdout(io.StringIO()):
            self.assertEqual(compare_keys.main([]), 0)

    def test_an_undecided_difference_fails_the_comparison(self):
        import compare_keys
        keys_b = copy.deepcopy(load('keys-b.json')['keys'])
        task = next(t for t in POOL if t['id'] not in compare_keys.DECIDED)
        answer = keys_b[task['id']]['answer']
        field = next(k for k in task['schema']['properties'] if k not in ('answerStatus', 'unavailableServices', 'complete', 'explanation'))
        answer[field] = wrong(answer[field])
        mismatches = compare_keys.undecided(compare_keys.compare(keys_b=keys_b))
        self.assertEqual([m[0] for m in mismatches], [task['id']])
        self.assertIn('not decided', mismatches[0][1])
        self.assertIn('b-not-correct-under-a', mismatches[0][1])
        decided = dict(compare_keys.DECIDED, A01=compare_keys.DECIDED['D07'])
        self.assertEqual(compare_keys.undecided(compare_keys.compare(), decided), [('A01', 'decided, but no difference is found any more')])

    def test_a_decision_holds_only_for_the_inputs_it_was_made_on(self):
        import compare_keys
        tasks = copy.deepcopy((POOL, AMBIGUITY, DEV))
        v06 = next(t for t in tasks[2] if t['id'] == 'V06')
        v06['question'] = v06['question'] + ' Include the types with no such mission.'
        self.assertEqual(compare_keys.undecided(compare_keys.compare(tasks=tasks)),
                         [('V06', 'decided on other inputs: task changed since the decision')])
        keys_b = copy.deepcopy(load('keys-b.json')['keys'])
        zero = next(group for group in keys_b['V06']['variants'][0]['answer']['types'] if group['missionCount'] == 0)
        keys_b['V06']['variants'][0]['answer']['types'].remove(zero)
        self.assertEqual(compare_keys.undecided(compare_keys.compare(keys_b=keys_b)),
                         [('V06', 'decided on other inputs: keyB changed since the decision')])
        keys_b = copy.deepcopy(load('keys-b.json')['keys'])
        keys_b['D04']['variants'] = keys_b['D04']['variants'][:3]
        mismatches = compare_keys.undecided(compare_keys.compare(keys_b=keys_b))
        self.assertEqual([m[0] for m in mismatches], ['D04'])
        self.assertIn('the differences changed', mismatches[0][1])

    def test_the_folding_follows_the_scorer(self):
        import compare_keys
        self.assertEqual(compare_keys.fold({'ids': ['b', 'A'], 'n': 2.50, 's': 'Under Way'}),
                         compare_keys.fold({'s': 'under_way', 'n': 2.5, 'ids': ['a', 'B']}))
        self.assertNotEqual(compare_keys.fold({'x': None}), compare_keys.fold({'x': []}))
        self.assertNotEqual(compare_keys.fold(['a', 'a']), compare_keys.fold(['a']))


if __name__ == '__main__':
    unittest.main()
