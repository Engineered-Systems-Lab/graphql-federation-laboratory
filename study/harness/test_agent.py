"""Tests of the agent loop with fake vendor clients and a fake tool session: scoring, limits, budget stop, retries, redaction."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from agent import SYSTEM_PROMPT, AgentRun, Limits
from budget import Budget
from fakes import FakeVendorClient, submit, turn
from mcp_client import FakeToolSession
from study_common import Redactor, read_jsonl
from vendors import VendorFatalError, VendorTransientError

SCORING = Path(__file__).resolve().parent.parent / 'corpus' / 'scoring.py'
spec = importlib.util.spec_from_file_location('scoring_under_test', SCORING)
scoring = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scoring)

SCHEMA = {'type': 'object', 'additionalProperties': False, 'properties': {'value': {'type': 'string'}, 'explanation': {'type': 'string'}},
          'required': ['value']}
EXPECTED = {'taskId': 'X', 'checks': [{'op': 'scalar', 'path': 'value', 'spec': {'equals': 'blue'}}]}
PRICE = {'input': 2.0, 'cached_read': 0.2, 'cache_write': 2.5, 'output': 10.0}
TASK = {'id': 'X', 'question': 'invented question', 'schema': SCHEMA}


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


class AgentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.events = []
        self.clock = Clock()

    def budget(self, limit=1_000_000):
        return Budget('fake', 'fake-model', limit, PRICE, '2026-10-20', Path(self.tmp.name) / 'b.jsonl')

    def session(self, **handlers):
        handlers.setdefault('lookup', lambda a: 'result for ' + json.dumps(a))
        return FakeToolSession([{'name': 'lookup', 'description': 'd', 'input_schema': {'type': 'object'}}], handlers)

    def run_task(self, steps, limits=None, budget=None, session=None, redactor=None, sleep=None):
        client = FakeVendorClient(steps)
        agent = AgentRun(client, session or self.session(), budget or self.budget(), limits or Limits(), lambda s: scoring.score(s, SCHEMA, EXPECTED),
                         self.events.append, redactor or Redactor(), clock=self.clock, sleep=sleep or (lambda s: None), run_id='k')
        return agent.run(TASK), client

    def test_tools_then_a_correct_submission(self):
        result, client = self.run_task([turn('looking', [('t1', 'lookup', {'q': 1})]), submit({'value': 'blue', 'explanation': 'e'})])
        self.assertEqual(result['outcome'], 'correct')
        self.assertEqual(result['toolCalls'], 1)
        self.assertEqual(result['turns'], 2)
        self.assertEqual(result['usageTokens'], 30)
        system, transcript, names = client.calls[0]
        self.assertEqual(system, SYSTEM_PROMPT)
        self.assertEqual(names, ['lookup', 'submit_answer'])
        self.assertEqual(client.calls[1][1][-1]['role'], 'tool')

    def test_a_wrong_answer_and_a_format_error_are_told_apart(self):
        wrong, _ = self.run_task([submit({'value': 'red'})])
        self.assertEqual(wrong['outcome'], 'wrong_answer')
        fmt, _ = self.run_task([submit({'value': 'blue', 'extra': 1})])
        self.assertEqual(fmt['outcome'], 'format_error')
        self.assertTrue(fmt['score']['contentCorrectDespiteFormat'])
        self.assertEqual(fmt['score']['score'], 0)

    def test_tool_call_cap_is_did_not_finish_with_the_spend_counted(self):
        steps = [turn('', [('a', 'lookup', {}), ('b', 'lookup', {})]), turn('', [('c', 'lookup', {})])]
        result, _ = self.run_task(steps, limits=Limits(max_tool_calls=2))
        self.assertEqual((result['outcome'], result['reason']), ('did_not_finish', 'tool_calls'))
        self.assertEqual(result['toolCalls'], 2)
        self.assertEqual(result['usageTokens'], 30)

    def test_wall_clock_cap(self):
        def slow(args):
            self.clock.now += 100
            return 'late'
        result, _ = self.run_task([turn('', [('a', 'lookup', {})]), submit({'value': 'blue'})], limits=Limits(max_wall_seconds=50),
                                  session=self.session(lookup=slow))
        self.assertEqual((result['outcome'], result['reason']), ('did_not_finish', 'wall_clock'))

    def test_token_cap(self):
        result, _ = self.run_task([turn('', [('a', 'lookup', {})], usage=(500, 0, 0, 500)), submit({'value': 'blue'})],
                                  limits=Limits(max_task_tokens=900))
        self.assertEqual((result['outcome'], result['reason']), ('did_not_finish', 'tokens'))

    def test_no_submission_is_nudged_then_did_not_finish(self):
        result, client = self.run_task([turn('thinking'), turn('still'), turn('no')], limits=Limits(max_nudges=2))
        self.assertEqual((result['outcome'], result['reason']), ('did_not_finish', 'no_submission'))
        self.assertEqual(len(client.calls), 3)

    def test_a_nudge_can_lead_to_a_submission(self):
        result, _ = self.run_task([turn('thinking'), submit({'value': 'blue'})])
        self.assertEqual(result['outcome'], 'correct')

    def test_budget_stop_is_not_a_score(self):
        result, client = self.run_task([submit({'value': 'blue'})], budget=self.budget(limit=1000))  # needs 1000 output + the input
        self.assertEqual(result['outcome'], 'budget_stop')
        self.assertEqual(client.calls, [])
        self.assertIsNone(result['score'])
        self.assertIn('budget_stop', [e['kind'] for e in self.events])

    def test_a_transient_error_is_retried_recorded_and_costed(self):
        sleeps = []
        budget = self.budget()
        result, _ = self.run_task([VendorTransientError('rate limit'), submit({'value': 'blue'})], budget=budget, sleep=sleeps.append)
        self.assertEqual(result['outcome'], 'correct')
        self.assertEqual(budget.retries, 1)
        self.assertEqual(len(sleeps), 1)
        self.assertIn('retry', [e['kind'] for e in self.events])
        ledger = read_jsonl(Path(self.tmp.name) / 'b.jsonl')
        self.assertEqual([e['event'] for e in ledger], ['reserve', 'settle', 'reserve', 'settle'])

    def test_each_request_is_timed_on_its_own_without_tool_time(self):
        def after(seconds, step):
            def run(system, transcript, tools):
                self.clock.now += seconds
                return step
            return run

        def slow_lookup(arguments):
            self.clock.now += 7.0
            return 'slow'

        budget = self.budget()
        steps = [after(0.5, VendorTransientError('rate limit')), after(2.5, turn('', [('t1', 'lookup', {})])),
                 after(1.25, submit({'value': 'blue'}))]
        self.run_task(steps, budget=budget, session=self.session(lookup=slow_lookup))
        assistant = [e for e in self.events if e['kind'] == 'message' and e['role'] == 'assistant']
        self.assertEqual([e['requestSeconds'] for e in assistant], [2.5, 1.25])
        self.assertEqual([e['requestSeconds'] for e in self.events if e['kind'] == 'retry'], [0.5])
        self.assertEqual([e['seconds'] for e in self.events if e['kind'] == 'tool'], [7.0])
        for e in assistant:
            self.assertLessEqual(e['requestStart'], e['requestEnd'])
        settled = [e for e in read_jsonl(Path(self.tmp.name) / 'b.jsonl') if e['event'] == 'settle']
        self.assertEqual([e['requestSeconds'] for e in settled], [0.5, 2.5, 1.25])
        self.assertTrue(all(e['requestStart'] and e['requestEnd'] for e in settled))

    def test_retries_are_bounded(self):
        steps = [VendorTransientError('x')] * 5
        result, _ = self.run_task(steps, limits=Limits(max_retries=2))
        self.assertEqual(result['outcome'], 'error')

    def test_a_fatal_error_releases_the_reservation_and_ends_the_run(self):
        budget = self.budget()
        result, _ = self.run_task([VendorFatalError('bad request')], budget=budget)
        self.assertEqual(result['outcome'], 'error')
        self.assertEqual(budget.remaining_tokens, 1_000_000)

    def test_a_key_is_redacted_from_everything_written(self):
        secret = 'sk-ant-SECRETSECRETSECRETSECRET'
        session = self.session(lookup=lambda a: 'the tool leaked ' + secret)
        self.run_task([turn('', [('a', 'lookup', {})]), submit({'value': 'blue', 'explanation': secret})], session=session,
                      redactor=Redactor([secret]))
        self.assertNotIn(secret, json.dumps(self.events))
        self.assertIn('[REDACTED]', json.dumps(self.events))

    def test_only_the_scenario_tools_and_submit_answer_are_offered(self):
        _, client = self.run_task([submit({'value': 'blue'})])
        self.assertEqual(client.calls[0][2], ['lookup', 'submit_answer'])


if __name__ == '__main__':
    unittest.main()
