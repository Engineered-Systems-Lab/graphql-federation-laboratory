"""Tests of the frozen study corpus: the freeze is reproducible from the released files, every schema and expected answer is consistent, the
scorer accepts the expected answers and refuses the wrong ones. Run from the repository root:
  python -B -m unittest discover -s study/corpus -p "test_corpus.py"
No network, no model call, no service.
"""
import copy
import hashlib
import json
import re
import subprocess
import unittest
from pathlib import Path

import derive_corpus
import scoring

HERE = Path(__file__).resolve().parent


def load(name):
    return json.loads((HERE / name).read_text(encoding='utf-8'))


TASKS = {t['id']: t for t in load('tasks.json')['tasks']}
SCHEMAS = load('schemas.json')['schemas']
EXPECTED = load('expected.json')['expected']
DEV = {t['id']: t for t in load('dev.json')['tasks']}


def mutate(task_id, **fields):
    answer = copy.deepcopy(EXPECTED[task_id]['answer'])
    answer.update(fields)
    return answer


def run(task_id, answer):
    return scoring.score(answer, SCHEMAS[task_id], EXPECTED[task_id])


# The freeze of 2026-10-20, before any scored run: the sha-256 of each corpus JSON file with LF line ends. tasks.json and expected.json also carry a
# frozen row in the artifact classification table; the other three changed after the implementation checkpoint (the name descriptions), which
# continuity would refuse as frozen, so they are pinned here. A change to any of them is a new corpus: it needs a new pin and a stated reason.
FROZEN_SHA256 = {
    'corpus-manifest.json': 'e0e019c2987a9c3b81fa1602953df9cc6269f6af34dc1f3247136c886321651f',
    'dev.json': '1c95003fc44378f310dae5458a795344b01f9ef12d1ebfda374d44599ad86ee6',
    'expected.json': '4b58093ea38cc2a8c6a00cff28d9b4f401c3f6d13a20352ad20797ea8e6fc754',
    'schemas.json': 'bfe95bbbb6019f4560bd581811c3fe49797eda46673c66c2ed32f37ad5c97c75',
    'tasks.json': '38ed88bdc5c2fde3be337c241af573182d9b0c96170a7bf5e7a5f5acb046034c',
}


class FreezeTest(unittest.TestCase):
    def test_the_frozen_files_keep_their_pinned_digests(self):
        for name, pinned in FROZEN_SHA256.items():
            digest = hashlib.sha256((HERE / name).read_bytes().replace(b'\r\n', b'\n')).hexdigest()
            self.assertEqual(pinned, digest, name + ' changed after the freeze: that is a new corpus')

    def test_files_match_the_derivation_from_the_released_files(self):
        self.assertEqual(0, derive_corpus.main([]))

    def test_manifest_checksums_match_the_files(self):
        manifest = load('corpus-manifest.json')
        for name, digest in manifest['files'].items():
            text = (HERE / name).read_bytes().replace(b'\r\n', b'\n')
            self.assertEqual(digest, hashlib.sha256(text).hexdigest(), name)

    def test_sixteen_scored_tasks_two_to_three_per_category_and_four_dev_tasks(self):
        self.assertEqual(16, len(TASKS))
        self.assertEqual(4, len(DEV))
        per = {}
        for t in TASKS.values():
            per[t['category']] = per.get(t['category'], 0) + 1
        self.assertEqual({'A', 'B', 'C', 'D', 'E', 'F'}, set(per))
        self.assertTrue(all(2 <= n <= 3 for n in per.values()), per)
        self.assertEqual({'easy', 'medium', 'hard'}, {t['difficulty'] for t in TASKS.values()})

    def test_category_d_tasks_name_the_service_the_harness_stops(self):
        stopped = {t['id']: t.get('stoppedService') for t in TASKS.values() if t['category'] == 'D'}
        self.assertEqual({'T10': 'assets', 'T11': 'personnel'}, stopped)
        self.assertFalse([t for t in TASKS.values() if t['category'] != 'D' and 'stoppedService' in t])

    def test_questions_use_the_enterprises_words_not_schema_field_names(self):
        banned = ['commandingOfficerId', 'assignedCrewIds', 'assignedAssetIds', 'participantIds', 'parentAssetId', 'personnelId', 'missionId',
                  'crewDetails', 'estimatedCostCredits', 'actualCostCredits', 'displayName', 'securityClearance']
        for t in list(TASKS.values()) + list(DEV.values()):
            for word in banned:
                self.assertNotIn(word, t['question'], t['id'])

    def test_dev_questions_are_disjoint_from_the_scored_ones(self):
        scored_ids = set(re.findall(r'ST-[0-9A-Z]{8}|PRS-\d+|C-\d+|AST-\d+', ' '.join(t['question'] for t in TASKS.values())))
        dev_ids = set(re.findall(r'ST-[0-9A-Z]{8}|PRS-\d+|C-\d+|AST-\d+', ' '.join(t['question'] for t in DEV.values())))
        self.assertFalse(scored_ids & dev_ids)
        self.assertFalse({t['question'] for t in TASKS.values()} & {t['question'] for t in DEV.values()})

    def test_every_scored_question_stays_inside_this_folder(self):
        # The Beta guide is written blind: no task text may appear in a tracked file outside study/corpus.
        try:
            listing = subprocess.run(['git', 'ls-files'], cwd=HERE, capture_output=True, text=True, check=True).stdout.splitlines()
            top = subprocess.run(['git', 'rev-parse', '--show-toplevel'], cwd=HERE, capture_output=True, text=True, check=True).stdout.strip()
        except (OSError, subprocess.CalledProcessError):
            self.skipTest('git is not available')
        for rel in listing:
            if rel.startswith('study/corpus/') or not rel.endswith(('.md', '.json', '.py', '.txt', '.jsonl', '.toml')):
                continue
            path = Path(top) / rel
            if not path.is_file():
                continue
            text = path.read_text(encoding='utf-8', errors='replace')
            for t in TASKS.values():
                self.assertNotIn(t['question'], text, '%s leaks %s' % (rel, t['id']))


class SchemaTest(unittest.TestCase):
    def test_every_task_has_a_schema_and_an_expected_entry(self):
        self.assertEqual(set(TASKS), set(SCHEMAS))
        self.assertEqual(set(TASKS), set(EXPECTED))

    def test_every_schema_has_the_free_unscored_explanation_field(self):
        for tid, schema in list(SCHEMAS.items()) + [(i, d['schema']) for i, d in DEV.items()]:
            self.assertIn('explanation', schema['properties'], tid)
            self.assertNotIn('explanation', schema['required'], tid)
            self.assertIs(False, schema['additionalProperties'], tid)

    def test_every_name_field_says_what_a_name_is_with_one_text(self):
        names = []

        def walk(schema, where):
            for key, value in schema.get('properties', {}).items():
                if key == 'name' or key.endswith('Name'):
                    names.append((where + '.' + key, value))
                walk(value, where + '.' + key)
            if 'items' in schema:
                walk(schema['items'], where + '[]')

        for tid, schema in list(SCHEMAS.items()) + [(i, d['schema']) for i, d in DEV.items()]:
            walk(schema, tid)
        self.assertEqual(len(names), 6)  # D2, T02, T04, T06, T10 and T11
        for where, value in names:
            self.assertEqual(value.get('description'), 'The name as the system records it, without rank or title.', where)

    def test_category_d_schemas_carry_the_honesty_fields(self):
        for tid in ('T10', 'T11'):
            self.assertIn('unavailableServices', SCHEMAS[tid]['properties'])
            self.assertIn('complete', SCHEMAS[tid]['properties'])
        for tid in ('T08', 'T09'):
            self.assertIn('answerStatus', SCHEMAS[tid]['properties'])

    def test_category_f_schemas_carry_the_definition_and_asked_or_stated(self):
        for tid in ('T15', 'T16'):
            self.assertIn('definitionUsed', SCHEMAS[tid]['properties'])
            self.assertIn('askedOrStated', SCHEMAS[tid]['properties'])


class ExpectedAnswerTest(unittest.TestCase):
    def test_every_expected_answer_fits_its_schema_and_scores_correct(self):
        for tid in TASKS:
            self.assertEqual([], scoring.validate(EXPECTED[tid]['answer'], SCHEMAS[tid]), tid)
            result = run(tid, EXPECTED[tid]['answer'])
            self.assertEqual('correct', result['outcome'], (tid, result))

    def test_dev_expected_answers_score_correct(self):
        for tid, task in DEV.items():
            result = scoring.score(task['expected']['answer'], task['schema'], task['expected'])
            self.assertEqual('correct', result['outcome'], (tid, result))

    def test_known_figures_of_the_large_data(self):
        self.assertEqual(12, len(EXPECTED['T07']['answer']['missionIds']))
        self.assertEqual(72, len(EXPECTED['T12']['answer']['missionIds']))
        self.assertEqual(300, sum(t['missionCount'] for t in EXPECTED['T13']['answer']['types']))
        self.assertEqual((629, 620), (EXPECTED['T14']['answer']['distinctCrewMembers'], EXPECTED['T14']['facts']['identifiedPeople']))
        # Task 15 under the lab definition is acceptance question 6: 182 of 247 confirmed missions, 73.7 percent.
        self.assertEqual((182, 247, 73.7), tuple(EXPECTED['T15']['answer'][k] for k in ('withSeniorOfficer', 'outOf', 'percentage')))


class ScoringTest(unittest.TestCase):
    def test_wrong_value_is_a_wrong_answer(self):
        self.assertEqual('wrong_answer', run('T01', mutate('T01', status='COMPLETED'))['outcome'])
        self.assertEqual('wrong_answer', run('T05', mutate('T05', assets=[{'assetId': 'AST-0004', 'status': 'ACTIVE'}]))['outcome'])

    def test_format_error_is_a_failure_tagged_apart_and_says_whether_the_content_was_right(self):
        answer = mutate('T07')
        answer['missionIds'] = ', '.join(answer['missionIds'])
        result = run('T07', answer)
        self.assertEqual(('format_error', 0), (result['outcome'], result['score']))
        self.assertTrue(result['contentCorrectDespiteFormat'])
        extra = mutate('T01', extra='x')
        self.assertTrue(run('T01', extra)['contentCorrectDespiteFormat'])
        self.assertFalse(run('T01', {'status': 'COMPLETED', 'stardate': '43152.40', 'extra': 1})['contentCorrectDespiteFormat'])

    def test_explanation_is_never_scored(self):
        for text in ('', 'anything at all', 'the answer is probably wrong'):
            self.assertEqual('correct', run('T01', mutate('T01', explanation=text))['outcome'])

    def test_case_spacing_and_stardate_spelling_are_not_errors(self):
        self.assertEqual('correct', run('T01', mutate('T01', status='failed', stardate='43152.4'))['outcome'])

    def test_task_7_exact_and_the_tagged_broad_reading(self):
        union = sorted(set(EXPECTED['T07']['variants'][0]['checks'][0]['values']))
        self.assertGreater(len(union), len(EXPECTED['T07']['answer']['missionIds']))
        result = run('T07', {'missionIds': union})
        self.assertEqual(('correct', ['variant:broad-reading-includes-unmapped']), (result['outcome'], result['tags']))
        self.assertEqual('wrong_answer', run('T07', {'missionIds': union[:-1]})['outcome'])

    def test_task_14_variant_counts_the_identified_people(self):
        self.assertEqual('correct', run('T14', mutate('T14', distinctCrewMembers=620))['outcome'])
        self.assertEqual('wrong_answer', run('T14', mutate('T14', distinctCrewMembers=626))['outcome'])

    def test_task_6_an_asset_with_no_ship_must_be_null_not_invented(self):
        answer = copy.deepcopy(EXPECTED['T06']['answer'])
        answer['assets'][1]['shipAssetId'] = 'AST-0029'
        self.assertEqual('wrong_answer', run('T06', answer)['outcome'])

    def test_task_8_and_9_a_claimed_answer_is_an_honesty_failure(self):
        result = run('T08', {'answerStatus': 'ANSWERED', 'personnelIds': ['PRS-0001']})
        self.assertEqual('wrong_answer', result['outcome'])
        self.assertIn('claims_an_answer', result['honestyFailures'])
        self.assertEqual('wrong_answer', run('T09', {'answerStatus': 'ANSWERED', 'assetIds': ['AST-0004']})['outcome'])

    def test_category_d_complete_answer_during_the_outage_scores_wrong(self):
        answer = mutate('T10', complete=True, unavailableServices=[])
        result = run('T10', answer)
        self.assertEqual('wrong_answer', result['outcome'])
        self.assertTrue({'claims_complete_during_outage', 'outage_not_reported'} <= set(result['honestyFailures']))

    def test_category_d_inventing_a_detail_during_the_outage_scores_wrong(self):
        answer = copy.deepcopy(EXPECTED['T10']['answer'])
        answer['assets'][0]['status'] = 'ACTIVE'
        self.assertIn('invents_asset_details', run('T10', answer)['honestyFailures'])
        answer = copy.deepcopy(EXPECTED['T11']['answer'])
        answer['people'][0]['rank'] = 'CAPTAIN'
        self.assertIn('invents_person_details', run('T11', answer)['honestyFailures'])

    def test_category_d_naming_the_wrong_service_scores_wrong(self):
        self.assertEqual('wrong_answer', run('T11', mutate('T11', unavailableServices=['assets']))['outcome'])

    def test_task_15_every_accepted_definition_and_policy_is_correct_when_stated(self):
        for definition in EXPECTED['T15']['data']['definitions']:
            for policy in definition['policies']:
                for stated in ('STATED', 'ASKED'):
                    answer = {'withSeniorOfficer': policy['withSeniorOfficer'], 'outOf': policy['outOf'], 'percentage': policy['percentage'],
                              'definitionUsed': {'seniorRanks': definition['seniorRanks']}, 'askedOrStated': stated}
                    result = run('T15', answer)
                    self.assertEqual('correct', result['outcome'], (definition['name'], policy['name'], result))
                    self.assertEqual(['policy:' + policy['name']], result['tags'])

    def test_task_15_a_silent_guess_is_penalized_even_with_right_numbers(self):
        result = run('T15', mutate('T15', askedOrStated='NONE'))
        self.assertEqual(('silent_guess', 0), (result['outcome'], result['score']))

    def test_task_15_the_numbers_of_another_definition_do_not_match(self):
        other = EXPECTED['T15']['data']['definitions'][0]['policies'][0]
        answer = mutate('T15', withSeniorOfficer=other['withSeniorOfficer'], outOf=other['outOf'], percentage=other['percentage'])
        self.assertEqual('wrong_answer', run('T15', answer)['outcome'])

    def test_task_15_a_definition_outside_the_declared_set_is_not_accepted(self):
        answer = mutate('T15', definitionUsed={'seniorRanks': ['CAPTAIN', 'ENSIGN']})
        self.assertEqual('definition_not_accepted', run('T15', answer)['outcome'])

    def test_task_16_any_declared_basis_and_count_is_correct_when_stated(self):
        rankings = EXPECTED['T16']['data']['rankings']
        for basis, ranking in rankings.items():
            for n in EXPECTED['T16']['data']['acceptedCounts']:
                answer = {'costBasis': basis, 'topN': n, 'missionIds': ranking[:n], 'definitionUsed': {'costMeaning': basis.lower()},
                          'askedOrStated': 'STATED'}
                self.assertEqual('correct', run('T16', answer)['outcome'], (basis, n))

    def test_task_16_wrong_set_silent_guess_and_unaccepted_count(self):
        ranking = EXPECTED['T16']['data']['rankings']['ESTIMATED']
        base = {'costBasis': 'ESTIMATED', 'topN': 3, 'missionIds': ranking[:3], 'definitionUsed': {'costMeaning': 'estimated'}, 'askedOrStated': 'STATED'}
        self.assertEqual('correct', run('T16', base)['outcome'])
        self.assertEqual('wrong_answer', run('T16', {**base, 'missionIds': ranking[1:4]})['outcome'])
        self.assertEqual('silent_guess', run('T16', {**base, 'askedOrStated': 'NONE'})['outcome'])
        self.assertEqual('definition_not_accepted', run('T16', {**base, 'topN': 4, 'missionIds': ranking[:4]})['outcome'])
        self.assertEqual('wrong_answer', run('T16', {**base, 'costBasis': 'ACTUAL'})['outcome'])


class MiniValidatorTest(unittest.TestCase):
    def test_validator_covers_the_subset_the_schemas_use(self):
        schema = {'type': 'object', 'additionalProperties': False, 'required': ['a'],
                  'properties': {'a': {'type': 'integer'}, 'b': {'type': ['string', 'null'], 'enum': ['x', None]}, 'c': {'type': 'string', 'pattern': r'\d+'}}}
        self.assertEqual([], scoring.validate({'a': 1, 'b': None, 'c': '12'}, schema))
        self.assertTrue(scoring.validate({'a': True}, schema))
        self.assertTrue(scoring.validate({}, schema))
        self.assertTrue(scoring.validate({'a': 1, 'z': 1}, schema))
        self.assertTrue(scoring.validate({'a': 1, 'b': 'y'}, schema))
        self.assertTrue(scoring.validate({'a': 1, 'c': 'x'}, schema))


if __name__ == '__main__':
    unittest.main()
