"""Tests of the scoring contract: study 1's scorer works unchanged as version 1 and scores exactly as when called directly; a version-2 scorer
receives the context with the ask_requester log and may return abstained; a result that breaks the contract is refused. Invented schemas
and expected entries only; the real study-1 scorer is loaded as the harness loads it."""
import importlib.util
import types
import unittest
from pathlib import Path

import scoring_contract as sc

SCORING = Path(__file__).resolve().parent.parent / 'corpus' / 'scoring.py'
spec = importlib.util.spec_from_file_location('scoring_contract_under_test', SCORING)
study1 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(study1)

SCHEMA = {'type': 'object', 'additionalProperties': False, 'properties': {'value': {'type': 'string'}, 'explanation': {'type': 'string'}},
          'required': ['value']}
TASK = {'id': 'X', 'schema': SCHEMA, 'expected': {'taskId': 'X', 'checks': [{'op': 'scalar', 'path': 'value', 'spec': {'equals': 'blue'}}],
                                                  'variants': [{'name': 'navy', 'checks': [{'op': 'scalar', 'path': 'value', 'spec': {'equals': 'navy'}}]}]}}


def module(version=2, result=None, record=None):
    """A scorer module with SCORING_CONTRACT = version whose score returns `result` (or a function of the arguments)."""
    m = types.ModuleType('fake_scoring')
    if version is not None:
        m.SCORING_CONTRACT = version

    def score(submission, schema, expected, context=None):
        if record is not None:
            record.append(context)
        return result(submission, context) if callable(result) else result
    m.score = score
    return m


class Version1Tests(unittest.TestCase):
    def test_the_study_1_scorer_is_version_1_and_scores_exactly_as_before(self):
        contract = sc.Contract(study1, SCORING)
        self.assertEqual(contract.version, 1)
        self.assertEqual(contract.outcomes, ('correct', 'wrong_answer', 'format_error', 'silent_guess', 'definition_not_accepted'))
        for submission in ({'value': 'blue'}, {'value': 'navy'}, {'value': 'red'}, {'value': 'blue', 'extra': 1}, {}, {'value': 3}):
            direct = study1.score(submission, SCHEMA, TASK['expected'])
            self.assertEqual(contract.score(submission, TASK, {'askRequester': [{'question': 'ignored'}]}), direct)
        self.assertEqual(contract.score({'value': 'navy'}, TASK, {})['tags'], ['variant:navy'])

    def test_describe_names_the_version_the_outcomes_and_the_scorer_hash(self):
        described = sc.Contract(study1, SCORING).describe()
        self.assertEqual(described['version'], 1)
        self.assertEqual(described['correctOutcomes'], ['correct'])
        self.assertEqual(described['harnessOutcomes'], ['did_not_finish', 'vendor_error'])
        self.assertEqual(len(described['scorerSha256']), 64)
        self.assertNotIn('ambiguityFlags', described)


class Version2Tests(unittest.TestCase):
    def test_the_context_reaches_the_scorer_and_abstained_is_accepted(self):
        seen = []
        contract = sc.Contract(module(result=lambda s, c: {'score': 0, 'outcome': 'abstained', 'tags': []}, record=seen))
        context = {'taskId': 'X', 'set': 'ambiguity', 'category': 'F', 'askRequester': [{'question': 'Which ranks?', 'runKey': 'k'}]}
        self.assertEqual(contract.score({'value': 'none'}, TASK, context)['outcome'], 'abstained')
        self.assertEqual(seen, [context])
        self.assertIn('abstained', contract.outcomes)
        self.assertNotIn('silent_guess', contract.outcomes)

    def test_the_ambiguity_flags_are_booleans(self):
        contract = sc.Contract(module(result={'score': 1, 'outcome': 'correct', 'clarified': True, 'interpretationAccepted': False}))
        self.assertTrue(contract.score({}, TASK, {})['clarified'])
        bad = sc.Contract(module(result={'score': 1, 'outcome': 'correct', 'clarified': 'yes'}))
        with self.assertRaisesRegex(sc.ScoringContractError, 'clarified'):
            bad.score({}, TASK, {})

    def test_a_result_that_breaks_the_contract_is_refused(self):
        for result, message in (({'score': 0, 'outcome': 'silent_guess'}, 'does not have'),
                                ({'score': 1, 'outcome': 'wrong_answer'}, 'exactly when'),
                                ({'score': 0, 'outcome': 'correct'}, 'exactly when'),
                                ({'score': True, 'outcome': 'correct'}, 'must be 0 or 1'),
                                ({'outcome': 'correct'}, 'must be 0 or 1'),
                                ('correct', 'not a dict')):
            with self.assertRaisesRegex(sc.ScoringContractError, message):
                sc.Contract(module(result=result)).score({}, TASK, {})

    def test_an_unknown_version_or_a_scorer_without_score_is_refused(self):
        for version in (3, '2', True, 0):
            with self.assertRaisesRegex(sc.ScoringContractError, 'SCORING_CONTRACT'):
                sc.Contract(module(version=version, result={}))
        with self.assertRaisesRegex(sc.ScoringContractError, 'no score function'):
            sc.Contract(types.ModuleType('empty'))

    def test_version_2_describes_its_flags(self):
        described = sc.Contract(module(result={})).describe()
        self.assertEqual(described['version'], 2)
        self.assertEqual(described['ambiguityFlags'], ['clarified', 'interpretationAccepted'])
        self.assertIn('abstained', described['outcomes'])


if __name__ == '__main__':
    unittest.main()
